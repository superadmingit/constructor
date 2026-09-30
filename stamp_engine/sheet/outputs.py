"""Файлы для людей и станков из модели детали.

  write_flat_dxf  — DXF развёртки: CONTOUR (одна замкнутая полилиния с дугами), HOLES, BEND, NOTES. Миллиметры.
  write_drawing   — PDF: лист 1 — гнутая деталь (виды из 3D + габариты), лист 2 — развёртка в масштабе,
                    таблица координат отверстий от угла заготовки, таблица гибов.
Чертёж выводится из той же модели, что 3D и развёртка, поэтому они не могут разойтись.
"""
from __future__ import annotations

import datetime as _dt
import math
import os
import tempfile

from ..geometry import Contour
from .unfold import Flat

DIR_RU = {"up": "вверх", "down": "вниз"}


def _clip_bend(b: dict, contour: Contour):
    """Отрезок линии гиба, лежащий на заготовке."""
    (x0, y0), (x1, y1) = b["line"]
    l = math.hypot(x1 - x0, y1 - y0)
    u = ((x1 - x0) / l, (y1 - y0) / l)
    if not b.get("clip"):
        return [((x0, y0), (x1, y1))]
    return [((x0 + u[0] * a, y0 + u[1] * a), (x0 + u[0] * c, y0 + u[1] * c))
            for a, c in contour.chord_on_ray((x0, y0), u)]


def _slot_poly(h):
    a = math.radians(h["angle_deg"])
    ux, uy = math.cos(a), math.sin(a)
    vx, vy = -uy, ux
    half, r = (h["length"] - h["width"]) / 2, h["width"] / 2
    cx, cy = h["cx"], h["cy"]
    return [(cx + ux * half + vx * r, cy + uy * half + vy * r, 1.0),
            (cx - ux * half + vx * r, cy - uy * half + vy * r, 0.0),
            (cx - ux * half - vx * r, cy - uy * half - vy * r, 1.0),
            (cx + ux * half - vx * r, cy + uy * half - vy * r, 0.0)]


def write_flat_dxf(spec: dict, flat: Flat, path: str) -> None:
    import ezdxf
    doc = ezdxf.new("R2010", setup=True)
    doc.header["$INSUNITS"] = 4
    doc.header["$MEASUREMENT"] = 1
    for name, col, lt in (("CONTOUR", 7, "CONTINUOUS"), ("HOLES", 7, "CONTINUOUS"), ("BEND", 5, "DASHED"),
                          ("NOTES", 3, "CONTINUOUS")):
        doc.layers.add(name, color=col, linetype=lt)
    m = doc.modelspace()
    m.add_lwpolyline([tuple(p) for p in flat.contour], format="xyb", close=True, dxfattribs={"layer": "CONTOUR"})
    for h in flat.holes:
        if h["kind"] == "round":
            m.add_circle((h["cx"], h["cy"]), h["d"] / 2, dxfattribs={"layer": "HOLES"})
        else:
            m.add_lwpolyline(_slot_poly(h), format="xyb", close=True, dxfattribs={"layer": "HOLES"})
    c = Contour(flat.contour)
    for b in flat.bends:
        for p0, p1 in _clip_bend(b, c):
            m.add_line(p0, p1, dxfattribs={"layer": "BEND"})
    x0, y0, _, _ = c.bbox()
    status = spec.get("blank_status", "preliminary")
    for i, t in enumerate([f"{spec.get('id', '')}  FLAT PATTERN  S={flat.T:g} mm",
                           "PRELIMINARY - NOT FOR TOOLING" if status != "confirmed" else "CONFIRMED"]):
        m.add_text(t, height=2.5, dxfattribs={"layer": "NOTES"}).set_placement((x0, y0 - 8 - 4.5 * i))
    doc.saveas(path)


# ---------------------------------------------------------------------- PDF
def _fmt(v, nd=2):
    return f"{v:.{nd}f}".replace(".", ",")


def write_drawing(spec: dict, flat: Flat, solid, path: str, view_png: dict | None = None) -> None:
    """PDF из двух листов A4 (альбом). solid — 3D (для видов), может быть None: тогда лист 1 без видов."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.backends.backend_pdf import PdfPages
    from matplotlib.patches import Rectangle

    plt.rcParams["font.family"] = "DejaVu Sans"
    draft = spec.get("blank_status", "preliminary") != "confirmed"
    mat = spec.get("material", {})
    grade = (mat.get("grade") or {}).get("value") or "марка не указана"
    today = _dt.date.today().strftime("%d.%m.%Y")
    W, H = 11.69, 8.27

    def frame(fig, title, sheet):
        ax = fig.add_axes([0, 0, 1, 1])
        ax.set_xlim(0, 297); ax.set_ylim(0, 210); ax.axis("off")
        ax.add_patch(Rectangle((10, 5), 282, 200, fill=False, lw=1.2))
        ax.add_patch(Rectangle((187, 5), 105, 34, fill=False, lw=1.0))
        ax.text(190, 33, str(spec.get("id", "")), fontsize=9, weight="bold")
        for i, line in enumerate(_wrap(str(spec.get("name", "")), 46)[:2]):
            ax.text(190, 28.5 - 3.6 * i, line, fontsize=7.2)
        ax.text(190, 19, f"Материал: {grade}, S = {_fmt(flat.T, 1)} мм", fontsize=7.2)
        ax.text(190, 14, title, fontsize=7.2)
        ax.text(190, 8.5, f"Лист {sheet} из 2      {today}", fontsize=7)
        if draft:
            ax.text(14, 199, "ЧЕРНОВИК — НЕ ДЛЯ ИЗГОТОВЛЕНИЯ ШТАМПА", fontsize=10, color="#B83A2E", weight="bold")
        return ax

    with PdfPages(path) as pdf:
        # ---------- лист 1: гнутая деталь ----------
        fig = plt.figure(figsize=(W, H))
        ax = frame(fig, "Деталь: виды из 3D-модели", 1)
        if solid is not None:
            bb = solid.val().BoundingBox()
            pr = projections(solid)
            fx0, fy0, fx1, fy1 = pr["front"]["bb"]
            tx0, ty0, tx1, ty1 = pr["top"]["bb"]
            lx0, ly0, lx1, ly1 = pr["left"]["bb"]
            gap = 16
            need_w = (fx1 - fx0) + (lx1 - lx0) + gap
            need_h = (fy1 - fy0) + (ty1 - ty0) + gap
            sc = next(k for k in (2, 1.5, 1, 0.75, 0.5, 0.4, 0.25, 0.2, 0.1) if need_w * k <= 165 and need_h * k <= 140)
            X0, Ytop = 24, 176
            place = {
                "front": (X0 - fx0 * sc, Ytop - fy1 * sc),
                "top": (X0 - tx0 * sc, Ytop - (fy1 - fy0) * sc - gap * sc - ty1 * sc),
                "left": (X0 + (fx1 - fx0) * sc + gap * sc - lx0 * sc, Ytop - fy1 * sc),
            }
            names = {"front": "Вид спереди", "top": "Вид сверху", "left": "Вид слева"}
            for k, (ox_, oy_) in place.items():
                for key, style in (("hid", dict(color="#9AA5A0", lw=0.45, ls=(0, (3, 2)))),
                                   ("vis", dict(color="#1D2528", lw=0.85))):
                    for pl in pr[k][key]:
                        ax.plot([ox_ + x * sc for x, _ in pl], [oy_ + y * sc for _, y in pl], **style)
                bx0, by0, bx1, by1 = pr[k]["bb"]
                ax.text(ox_ + bx0 * sc, oy_ + by1 * sc + 2.5, names[k], fontsize=7.5, color="#46534E")

            def hdim(x0_, x1_, y_, val):
                ax.annotate("", (x0_, y_), (x1_, y_), arrowprops=dict(arrowstyle="<->", lw=0.6, shrinkA=0, shrinkB=0))
                ax.text((x0_ + x1_) / 2, y_ + 0.8, _fmt(val), fontsize=7.5, ha="center", va="bottom")

            def vdim(x_, y0_, y1_, val):
                ax.annotate("", (x_, y0_), (x_, y1_), arrowprops=dict(arrowstyle="<->", lw=0.6, shrinkA=0, shrinkB=0))
                ax.text(x_ - 0.8, (y0_ + y1_) / 2, _fmt(val), fontsize=7.5, ha="right", va="center", rotation=90)

            ox_, oy_ = place["front"]
            hdim(ox_ + fx0 * sc, ox_ + fx1 * sc, oy_ + fy1 * sc + 7, fx1 - fx0)
            vdim(ox_ + fx0 * sc - 5, oy_ + fy0 * sc, oy_ + fy1 * sc, fy1 - fy0)
            ox_, oy_ = place["top"]
            vdim(ox_ + tx0 * sc - 5, oy_ + ty0 * sc, oy_ + ty1 * sc, ty1 - ty0)
            ox_, oy_ = place["left"]
            hdim(ox_ + lx0 * sc, ox_ + lx1 * sc, oy_ + ly1 * sc + 7, lx1 - lx0)
            ax.text(24, 52, f"Масштаб видов {'1:1' if sc == 1 else ('1:' + _fmt(1 / sc, 1).rstrip('0').rstrip(',') if sc < 1 else _fmt(sc, 1).rstrip('0').rstrip(',') + ':1')}. "
                            f"Размеры габаритные, по 3D-модели. Координаты отверстий — на листе 2.", fontsize=6.8, color="#46534E")
            iso = pr["iso"]
            ix0, iy0, ix1, iy1 = iso["bb"]
            isc = min(95 / (ix1 - ix0), 62 / (iy1 - iy0))
            iox, ioy = 190 - ix0 * isc, 132 - iy0 * isc
            for pl in iso["vis"]:
                ax.plot([iox + x * isc for x, _ in pl], [ioy + y * isc for _, y in pl], color="#1D2528", lw=0.7)
            ax.text(190, 132 + (iy1 - iy0) * isc + 3, "Общий вид (без масштаба)", fontsize=7.5, color="#46534E")
            ax.text(24, 46, f"Габарит гнутой детали: {_fmt(bb.xlen)} × {_fmt(bb.ylen)} × {_fmt(bb.zlen)} мм",
                    fontsize=8.5, weight="bold")
        rows = []
        for f in flat.flanges:
            hs = sorted({round(f.Lo(s) * math.sin(math.radians(f.theta_deg)) + flat.T * math.cos(math.radians(f.theta_deg)), 2)
                         for s, _ in f.stations})
            rows.append(f"{f.id}: {f.title or 'полка'} — угол {_fmt(f.theta_deg, 1)}° {DIR_RU[f.direction]}, "
                        f"высота {' … '.join(_fmt(v) for v in hs)} мм, R вн {_fmt(f.r, 1)}")
        for j in flat.joggles:
            rows.append(f"{j.id}: {j.title} — {DIR_RU[j.direction]} на {_fmt(j.offset)} мм, наклон {_fmt(j.gamma_deg, 0)}°, "
                        f"R вн {_fmt(j.r, 1)}")
        for i, t in enumerate(rows[:6]):
            ax.text(24, 38 - 4.2 * i, t, fontsize=7.0)
        pdf.savefig(fig); plt.close(fig)

        # ---------- лист 2: развёртка ----------
        fig = plt.figure(figsize=(W, H))
        ax = frame(fig, "Развёртка (заготовка)", 2)
        c = Contour(flat.contour)
        x0, y0, x1, y1 = c.bbox()
        bw, bh = x1 - x0, y1 - y0
        area_w, area_h = 160, 150
        scale = next(sc for sc in (1, 0.5, 0.4, 0.25, 0.2, 0.1) if bw * sc <= area_w and bh * sc <= area_h)
        ox, oy = 26 - x0 * scale, 40 + (150 - bh * scale) / 2 - y0 * scale
        P = lambda x, y: (ox + x * scale, oy + y * scale)
        poly = c.polygon(32) + [c.polygon(32)[0]]
        ax.plot(*zip(*[P(x, y) for x, y in poly]), color="#1D2528", lw=1.1)
        for hh in flat.holes:
            if hh["kind"] == "round":
                pts = [(hh["cx"] + hh["d"] / 2 * math.cos(a), hh["cy"] + hh["d"] / 2 * math.sin(a))
                       for a in [k * 2 * math.pi / 64 for k in range(65)]]
            else:
                sc_ = Contour([list(p) for p in _slot_poly(hh)])
                pts = sc_.polygon(16) + [sc_.polygon(16)[0]]
            ax.plot(*zip(*[P(x, y) for x, y in pts]), color="#1D2528", lw=0.9)
            cx, cy = P(hh["cx"], hh["cy"])
            ax.plot([cx - 2, cx + 2], [cy, cy], color="#7C8A84", lw=0.4)
            ax.plot([cx, cx], [cy - 2, cy + 2], color="#7C8A84", lw=0.4)
            ax.text(cx + 1.5, cy + 1.5, hh["id"], fontsize=6.5, color="#3F6A54")
        for b in flat.bends:
            for p0, p1 in _clip_bend(b, c):
                (ax_, ay_), (bx_, by_) = P(*p0), P(*p1)
                ax.plot([ax_, bx_], [ay_, by_], color="#2D5FA0", lw=0.8, ls=(0, (6, 3)))
                ax.text((ax_ + bx_) / 2, (ay_ + by_) / 2 + 1.2, b["id"], fontsize=6.5, color="#2D5FA0", ha="center")
        # габариты
        (ax0, ay0), (ax1, ay1) = P(x0, y0), P(x1, y1)
        ax.annotate("", (ax0, ay0 - 8), (ax1, ay0 - 8), arrowprops=dict(arrowstyle="<->", lw=0.7))
        ax.text((ax0 + ax1) / 2, ay0 - 7, _fmt(bw), fontsize=8, ha="center", va="bottom", weight="bold")
        ax.annotate("", (ax0 - 8, ay0), (ax0 - 8, ay1), arrowprops=dict(arrowstyle="<->", lw=0.7))
        ax.text(ax0 - 9.5, (ay0 + ay1) / 2, _fmt(bh), fontsize=8, ha="right", va="center", rotation=90, weight="bold")
        ax.text(ax0, ay0 - 14, f"Масштаб {'1:1' if scale == 1 else '1:' + _fmt(1 / scale, 0).rstrip(',0')}. "
                               f"Начало координат — левый нижний угол заготовки.", fontsize=6.8, color="#46534E")
        # таблицы
        tx, ty = 190, 186
        ax.text(tx, ty, "Отверстия (центр от угла заготовки)", fontsize=8, weight="bold")
        ty -= 5
        ax.text(tx, ty, "Поз.   X        Y        Размер", fontsize=7, family="DejaVu Sans Mono")
        for hh in flat.holes[:14]:
            ty -= 4
            size = f"Ø{_fmt(hh['d'])}" if hh["kind"] == "round" else f"паз {_fmt(hh['length'])}×{_fmt(hh['width'])}"
            ax.text(tx, ty, f"{hh['id']:<5} {_fmt(hh['cx'] - x0):>7}  {_fmt(hh['cy'] - y0):>7}   {size}",
                    fontsize=7, family="DejaVu Sans Mono")
        ty -= 8
        ax.text(tx, ty, "Гибы", fontsize=8, weight="bold")
        for b in flat.bends[:10]:
            ty -= 4
            ax.text(tx, ty, f"{b['id']}: {_fmt(b['angle_deg'], 1)}° {DIR_RU[b['direction']]}, R {_fmt(b['r_in']['value'], 1)}, "
                            f"зона гиба {_fmt(b['ba'])}", fontsize=6.8)
        ty -= 8
        xs = sorted({round(b["x"], 3) for b in flat.bends})
        for t in [f"K-фактор (нейтральный слой) x = {', '.join(_fmt(v, 2) for v in xs) or '—'}: "
                  f"по справочнику, проверить пробным гибом.",
                  "Точная геометрия — в DXF (слои CONTOUR, HOLES, BEND)."] + [f"⚠ {w}" for w in flat.warnings[:3]]:
            for line in _wrap(t, 60):
                ax.text(tx, ty, line, fontsize=6.6, color="#46534E")
                ty -= 3.6
        pdf.savefig(fig); plt.close(fig)


def _wrap(text, n):
    words, out, cur = text.split(), [], ""
    for w in words:
        if len(cur) + len(w) + 1 > n:
            out.append(cur); cur = w
        else:
            cur = (cur + " " + w).strip()
    if cur:
        out.append(cur)
    return out


VIEWS = {  # направление на наблюдателя, направление «вправо» на виде (первый угол, как в ЕСКД)
    "front": ((0, -1, 0), (1, 0, 0)),
    "top": ((0, 0, 1), (1, 0, 0)),
    "left": ((-1, 0, 0), (0, -1, 0)),
    "iso": ((1, -1, 0.8), None),
}


def projections(solid) -> dict:
    """Видимые и невидимые линии каждого вида в миллиметрах модели (удаление невидимых линий OpenCascade)."""
    from OCP.BRepLib import BRepLib
    from OCP.gp import gp_Ax2, gp_Dir, gp_Pnt
    from OCP.HLRAlgo import HLRAlgo_Projector
    from OCP.HLRBRep import HLRBRep_Algo, HLRBRep_HLRToShape
    import cadquery as cq

    shape = solid.val() if hasattr(solid, "val") else solid
    out = {}
    for name, (n, x) in VIEWS.items():
        hlr = HLRBRep_Algo()
        hlr.Add(shape.wrapped)
        ax2 = gp_Ax2(gp_Pnt(), gp_Dir(*n), gp_Dir(*x)) if x else gp_Ax2(gp_Pnt(), gp_Dir(*n))
        hlr.Projector(HLRAlgo_Projector(ax2))
        hlr.Update()
        hlr.Hide()
        hs = HLRBRep_HLRToShape(hlr)
        res = {"vis": [], "hid": []}
        for key, comps in (("vis", (hs.VCompound(), hs.Rg1LineVCompound(), hs.OutLineVCompound())),
                           ("hid", (hs.HCompound(), hs.OutLineHCompound()))):
            for comp in comps:
                if comp.IsNull():
                    continue
                BRepLib.BuildCurves3d_s(comp, 1e-6)
                for e in cq.Shape.cast(comp).Edges():
                    k = 2 if e.geomType() == "LINE" else 24
                    pts = [e.positionAt(i / k) for i in range(k + 1)]
                    res[key].append([(p.x, p.y) for p in pts])
        xs = [p[0] for pl in res["vis"] for p in pl]
        ys = [p[1] for pl in res["vis"] for p in pl]
        res["bb"] = (min(xs), min(ys), max(xs), max(ys))
        out[name] = res
    return out


# ---------------------------------------------------------------------- превью для веб-интерфейса
def flat_svg(flat: Flat, px: float = 520) -> str:
    """SVG развёртки: контур, отверстия, линии гибов с подписями. Координаты в мм, y вверх."""
    c = Contour(flat.contour)
    x0, y0, x1, y1 = c.bbox()
    m = 8
    w, h = x1 - x0 + 2 * m, y1 - y0 + 2 * m
    Y = lambda y: y1 + m - y + 0                    # переворот оси y
    X = lambda x: x - x0 + m
    pts = " ".join(f"{X(x):.2f},{Y(y):.2f}" for x, y in c.polygon(24))
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w:.1f} {h:.1f}" width="{px}" '
           f'role="img" aria-label="Развёртка">',
           f'<polygon points="{pts}" class="blank"/>']
    for hh in flat.holes:
        if hh["kind"] == "round":
            out.append(f'<circle cx="{X(hh["cx"]):.2f}" cy="{Y(hh["cy"]):.2f}" r="{hh["d"] / 2:.2f}" class="hole"/>')
        else:
            sp = Contour([list(p) for p in _slot_poly(hh)]).polygon(12)
            out.append('<polygon class="hole" points="' + " ".join(f"{X(x):.2f},{Y(y):.2f}" for x, y in sp) + '"/>')
    for b in flat.bends:
        for p0, p1 in _clip_bend(b, c):
            out.append(f'<line x1="{X(p0[0]):.2f}" y1="{Y(p0[1]):.2f}" x2="{X(p1[0]):.2f}" y2="{Y(p1[1]):.2f}" class="bend"/>')
    out.append("</svg>")
    return "".join(out)


def iso_png(solid, path: str) -> None:
    """Картинка общего вида гнутой детали (без масштаба)."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    iso = projections(solid)["iso"]
    fig = plt.figure(figsize=(6, 4), dpi=130)
    ax = fig.add_axes([0, 0, 1, 1]); ax.axis("off"); ax.set_aspect("equal")
    for pl in iso["vis"]:
        ax.plot([p[0] for p in pl], [p[1] for p in pl], color="#1D2528", lw=1.0)
    fig.savefig(path, transparent=True)
    plt.close(fig)
