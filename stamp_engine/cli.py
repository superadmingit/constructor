"""Запуск для любой детали:

    python -m stamp_engine.cli examples/skoba_u.json examples/shop_example.json --out out/

Деталь — модель гнутой детали (ключ "base") или готовая развёртка (ключ "blank").
Цех — JSON цеха или выгрузка страницы данных цеха.

В папке out/ появятся:
    report_<ID>.md       технологический расчёт: проверки, схемы штамповки, усилия, прессы
    <ID>_razvertka.dxf   развёртка для NX, AutoCAD, станков (мм)
    <ID>.step            3D гнутой детали для любого CAD
    <ID>_chertezh.pdf    чертёж: виды детали + развёртка с таблицей координат
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from .importer import shop_dict
from .loader import part_dict
from .models import Part, Shop
from .norms import DEFAULT_PATH, Norms
from .planner import Planner
from .report import build_report


def main(argv=None):
    ap = argparse.ArgumentParser(description="Деталь → развёртка, 3D, чертёж, расчёт штампов")
    ap.add_argument("part", help="JSON детали")
    ap.add_argument("shop", help="JSON цеха (прессы) или выгрузка страницы данных цеха")
    ap.add_argument("--norms", default=str(DEFAULT_PATH), help="YAML норм цеха")
    ap.add_argument("--out", default=".", help="папка для результатов")
    ap.add_argument("--no-3d", action="store_true", help="без 3D и чертежа (быстрее)")
    a = ap.parse_args(argv)

    raw = json.loads(Path(a.part).read_text(encoding="utf-8"))
    shop = Shop.from_dict(shop_dict(json.loads(Path(a.shop).read_text(encoding="utf-8"))))
    norms = Norms.load(a.norms)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    pid = raw.get("id", "part")

    files = []
    if "base" in raw:
        from .sheet import unfold
        from .sheet.outputs import write_drawing, write_flat_dxf
        flat = unfold(raw, norms)
        write_flat_dxf(raw, flat, str(out / f"{pid}_razvertka.dxf"))
        files.append(f"{pid}_razvertka.dxf")
        if not a.no_3d:
            from .sheet.solid import build_solid, export_step
            solid, notes = build_solid(raw, flat)
            export_step(solid, str(out / f"{pid}.step"))
            write_drawing(raw, flat, solid, str(out / f"{pid}_chertezh.pdf"))
            files += [f"{pid}.step", f"{pid}_chertezh.pdf"]
            for n in notes:
                print("3D:", n)

    part = Part.from_dict(part_dict(raw, norms))
    pl = Planner(part, shop, norms)
    schemes = pl.plan()
    md = build_report(pl, schemes, pl.recommend(schemes))
    (out / f"report_{pid}.md").write_text(md, encoding="utf-8")
    files.insert(0, f"report_{pid}.md")
    print("Готово:", ", ".join(files))


if __name__ == "__main__":
    main()
