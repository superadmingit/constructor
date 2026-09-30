"""Веб-сервис: любой человек открывает страницу, выбирает тип детали, вводит размеры и получает
развёртку (DXF), 3D (STEP), чертёж (PDF) и расчёт штампов.

Запуск локально:  uvicorn app.main:app --port 7860
"""
from __future__ import annotations

import json
import shutil
import time
import uuid
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel, Field

from stamp_engine.loader import part_dict
from stamp_engine.models import KN_PER_TONNE, Part, Shop
from stamp_engine.norms import Norms
from stamp_engine.planner import Planner
from stamp_engine.report import build_report
from stamp_engine.sheet import NotSupported, SheetError, unfold
from stamp_engine.sheet.families import FAMILIES, InputError, build, measurement_plan
from stamp_engine.sheet.outputs import flat_svg, iso_png, write_drawing, write_flat_dxf
from stamp_engine.sheet.solid import build_solid, export_step

ROOT = Path(__file__).resolve().parent
JOBS = Path("/tmp/constructor_jobs")
JOB_TTL_S = 3 * 3600
NORMS = Norms.load()
MATERIALS = {k: v["title"] for k, v in NORMS.data["materials"].items()}

app = FastAPI(title="Конструктор штампов", docs_url="/api/docs", redoc_url=None)


class Hole(BaseModel):
    face: str = "base"
    kind: str = "round"
    d: float | None = None
    length: float | None = None
    width: float | None = None
    x: float | None = None
    y: float | None = None
    s: float | None = None
    e: float | None = None
    angle: float = 0.0


class CalcRequest(BaseModel):
    family: str
    values: dict = Field(description="Размеры по буквам: {'A': 60, 'R': null, ...}; null = «не знаю»")
    material: str = "soft_steel"
    sigma_b_mpa: float | None = None
    holes: list[Hole] = []
    series_per_year: int | None = None
    presses_t: list[float] = [16, 25, 40, 63, 100, 160]
    part_id: str = "НОВАЯ"
    name: str = ""


def _cleanup():
    JOBS.mkdir(parents=True, exist_ok=True)
    now = time.time()
    for d in JOBS.iterdir():
        if d.is_dir() and now - d.stat().st_mtime > JOB_TTL_S:
            shutil.rmtree(d, ignore_errors=True)


@app.get("/", response_class=HTMLResponse)
def index():
    return (ROOT / "static" / "index.html").read_text(encoding="utf-8")


@app.get("/api/families")
def families():
    return {"families": [{"key": k, "title": f.title, "hint": f.hint, "faces": f.faces, "measures": measurement_plan(k)}
                         for k, f in FAMILIES.items()],
            "materials": MATERIALS}


@app.get("/api/health")
def health():
    return {"ok": True}


def _hole_dict(h: Hole) -> dict:
    d = {"face": h.face, "kind": h.kind}
    if h.kind == "round":
        if not h.d:
            raise InputError("Отверстие: укажите диаметр.")
        d["d"] = {"value": h.d, "source": "measured"}
    else:
        if not (h.length and h.width):
            raise InputError("Паз: укажите длину и ширину.")
        if h.length <= h.width:
            raise InputError("Паз: длина должна быть больше ширины.")
        d.update(length={"value": h.length, "source": "measured"}, width={"value": h.width, "source": "measured"},
                 angle=h.angle)
    if h.face == "base":
        if h.x is None or h.y is None:
            raise InputError("Отверстие в основании: укажите X и Y от левого нижнего угла.")
        d.update(x=h.x, y=h.y)
    else:
        if h.s is None or h.e is None:
            raise InputError("Отверстие в полке: укажите «вдоль» и «от края полки».")
        d.update(s=h.s, e=h.e)
    return d


@app.post("/api/calculate")
def calculate(req: CalcRequest):
    _cleanup()
    if req.material not in MATERIALS:
        raise HTTPException(400, "Неизвестный материал.")
    if not req.presses_t or any(not (1 <= t <= 2000) for t in req.presses_t):
        raise HTTPException(400, "Прессы: укажите усилие в тоннах, от 1 до 2000.")
    pid = "".join(ch for ch in req.part_id if ch.isalnum() or ch in "-_")[:32] or "PART"
    meta = {"id": pid, "name": req.name[:80] or FAMILIES.get(req.family, FAMILIES["plate"]).title,
            "material": {"group": req.material,
                         "sigma_b_mpa": ({"value": req.sigma_b_mpa, "source": "certificate"} if req.sigma_b_mpa
                                         else {"value": None, "source": "unknown"})},
            "series": ({"value": req.series_per_year, "source": "stated", "note": "в год"} if req.series_per_year
                       else {"value": None, "source": "unknown"})}
    try:
        spec = build(req.family, req.values, holes=[_hole_dict(h) for h in req.holes], meta=meta)
        flat = unfold(spec, NORMS)
        solid, notes = build_solid(spec, flat)
    except (InputError, SheetError, NotSupported) as e:
        raise HTTPException(400, str(e))

    job = uuid.uuid4().hex[:12]
    d = JOBS / job
    d.mkdir(parents=True)
    files = {"pdf": f"{pid}_chertezh.pdf", "dxf": f"{pid}_razvertka.dxf", "step": f"{pid}.step",
             "report": f"report_{pid}.md", "model": f"{pid}_model.json"}
    write_drawing(spec, flat, solid, str(d / files["pdf"]))
    write_flat_dxf(spec, flat, str(d / files["dxf"]))
    export_step(solid, str(d / files["step"]))
    iso_png(solid, str(d / "iso.png"))
    (d / files["model"]).write_text(json.dumps(spec, ensure_ascii=False, indent=1), encoding="utf-8")

    shop = Shop.from_dict({"has_guillotine": None, "presses": [
        {"id": f"P{i}", "name": f"Пресс {t:g} т", "force_t": {"value": t, "source": "stated"}}
        for i, t in enumerate(req.presses_t)]})
    part = Part.from_dict(part_dict(spec, NORMS))
    pl = Planner(part, shop, NORMS)
    schemes = pl.plan()
    best = pl.recommend(schemes)
    (d / files["report"]).write_text(build_report(pl, schemes, best), encoding="utf-8")

    x0, y0, x1, y1 = flat.bbox()
    bb = solid.val().BoundingBox()
    counts = {}
    for f in pl.findings:
        counts[f.level] = counts.get(f.level, 0) + 1
    return {
        "job": job,
        "blank": {"w": round(x1 - x0, 2), "l": round(y1 - y0, 2)},
        "formed": [round(bb.xlen, 2), round(bb.ylen, 2), round(bb.zlen, 2)],
        "x_factor": flat.bends[0]["x"] if flat.bends else None,
        "warnings": flat.warnings + notes + [f.text for f in pl.findings if f.level in ("error", "warn")],
        "unknown": [f.text for f in pl.findings if f.level == "unknown"],
        "counts": counts,
        "schemes": [{"key": s.key, "title": s.title, "suitable": s.suitable, "verdict": s.verdict,
                     "dies": [{"name": x.name, "t": round(x.total_kn / KN_PER_TONNE, 1),
                               "presses": [pc.press_name for pc in x.press_checks if pc.force_status == "ok"]}
                              for x in s.dies]} for s in schemes],
        "recommended": best.key if best else None,
        "flat_svg": flat_svg(flat),
        "files": {k: f"/files/{job}/{v}" for k, v in files.items()},
        "iso": f"/files/{job}/iso.png",
    }


@app.get("/files/{job}/{name}")
def files(job: str, name: str):
    if not job.isalnum() or "/" in name or ".." in name:
        raise HTTPException(404)
    p = JOBS / job / name
    if not p.is_file():
        raise HTTPException(404, "Файл устарел (хранится 3 часа). Посчитайте заново.")
    return FileResponse(p, filename=name)
