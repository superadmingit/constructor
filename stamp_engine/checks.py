"""Проверки технологичности детали (до проектирования штампа).

Каждая проверка возвращает Finding со статусом:
  ok      — норма выполнена
  warn    — можно, но с риском; решает конструктор
  error   — так делать нельзя, нужна другая схема или правка детали
  unknown — не хватает данных; это НЕ «ок»
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

from .calc import bend_allowance_mm, punch_stress_mpa
from .models import Part
from .norms import Norms


@dataclass
class Finding:
    level: str
    code: str
    text: str
    refs: list = field(default_factory=list)   # id элементов детали


def _dist_point_segment(px, py, ax, ay, bx, by) -> float:
    dx, dy = bx - ax, by - ay
    l2 = dx * dx + dy * dy
    t = 0.0 if l2 == 0 else max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / l2))
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))


def _dist_point_polygon(px, py, poly) -> float:
    return min(_dist_point_segment(px, py, *poly[i], *poly[(i + 1) % len(poly)])
               for i in range(len(poly)))


def _hole_axis_points(h, n: int = 9):
    """Точки на оси отверстия (для паза — по его длине)."""
    if h.kind == "round":
        return [(h.cx, h.cy)], h.d / 2
    half = max(h.length - h.width, 0.0) / 2
    a = math.radians(h.angle_deg)
    pts = [(h.cx + math.cos(a) * half * t, h.cy + math.sin(a) * half * t)
           for t in [-1 + 2 * i / (n - 1) for i in range(n)]]
    return pts, h.width / 2


def hole_edge_distance(h, poly) -> float:
    pts, r = _hole_axis_points(h)
    return min(_dist_point_polygon(x, y, poly) for x, y in pts) - r


def hole_hole_distance(h1, h2) -> float:
    p1, r1 = _hole_axis_points(h1)
    p2, r2 = _hole_axis_points(h2)
    return min(math.hypot(a[0] - b[0], a[1] - b[1]) for a in p1 for b in p2) - r1 - r2


def bend_geometry(part: Part, norms: Norms) -> dict:
    """Для каждого гиба: BA, x, реальная длина линии гиба на заготовке."""
    s = part.thickness.value
    out = {}
    for b in part.bends:
        r = b.r_in.value if b.r_in.known else s     # нет данных — r = S, с пометкой
        x = part.bend_x.value if part.bend_x.known else norms.x_for(r / s)
        ba = bend_allowance_mm(b.angle_deg, r, s, x)
        p0, u = b.frame()
        chords = b.chords(part.contour)
        length = sum(c[1] - c[0] for c in chords)
        measured = b.r_in.known and not b.r_in.assumed
        out[b.id] = {"r": r, "r_known": measured, "x": x, "ba": ba, "p0": p0, "u": u,
                     "chords": chords, "length": length}
    return out


def _hole_extents(h, u):
    """Полуразмеры отверстия вдоль линии u и поперёк неё."""
    if h.kind == "round":
        return h.d / 2, h.d / 2
    a = math.radians(h.angle_deg)
    c = abs(math.cos(a) * u[0] + math.sin(a) * u[1])      # |cos| угла между пазом и линией
    sn = math.sqrt(max(0.0, 1 - c * c))
    half = max(h.length - h.width, 0) / 2
    return half * c + h.width / 2, half * sn + h.width / 2


def hole_to_bend_distance(h, b, bg) -> float | None:
    """От края отверстия до ближайшей касательной линии гиба (на развёртке).

    None — отверстие не лежит напротив линии гиба (далеко по длине)."""
    p0, u = bg["p0"], bg["u"]
    t_c = (h.cx - p0[0]) * u[0] + (h.cy - p0[1]) * u[1]
    along, across = _hole_extents(h, u)
    lo, hi = t_c - along, t_c + along
    if not any(c0 - 1e-6 <= hi and lo <= c1 + 1e-6 for c0, c1 in bg["chords"]):
        return None
    d = abs((h.cx - p0[0]) * (-u[1]) + (h.cy - p0[1]) * u[0])
    return d - across - bg["ba"] / 2


def run_checks(part: Part, norms: Norms) -> tuple[list, dict]:
    s = part.thickness.value
    mat = norms.material(part.material_group)
    sigma_b = part.sigma_b_mpa.value if part.sigma_b_mpa.known else mat["sigma_b_mpa"]
    poly = part.contour.polygon(32)
    f: list[Finding] = []

    # --- данные ---------------------------------------------------------
    if not part.sigma_b_mpa.known:
        f.append(Finding("warn", "sigma_b_assumed",
                         f"σв не задан — взято {sigma_b:.0f} МПа из норм (верхняя граница). "
                         f"Возьмите σв из сертификата на металл.", []))
    if part.contour_status == "recalculated":
        f.append(Finding("warn", "blank_recalculated",
                         "Развёртка пересчитана по замерам, но не подтверждена пробным гибом: x и радиус гиба "
                         "могут отличаться. Вырубной штамп делать после пробной заготовки.", []))
    elif part.contour_status != "confirmed":
        f.append(Finding("warn", "blank_preliminary",
                         "Развёртка не подтверждена: до вырубного штампа согните пробную заготовку и сверьте размеры "
                         "детали. Штампы по неподтверждённой развёртке не изготавливать.", []))
    for w in part.flat_warnings:
        f.append(Finding("warn", "flat_warning", w, []))

    # --- отверстия ------------------------------------------------------
    k_min_d = mat["min_hole_d_over_s"]
    allow = norms.get("tooling.punch_compressive_allow_mpa")
    for h in part.holes:
        size = h.size()
        lvl = "ok" if size >= k_min_d * s else "error"
        f.append(Finding(lvl, "hole_min_d",
                         f"{h.id}: размер {size:.2f} мм против минимума {k_min_d:.1f}·S = {k_min_d * s:.2f} мм",
                         [h.id]))
        if h.kind == "round":
            area = math.pi * h.d ** 2 / 4
        else:
            area = max(h.length - h.width, 0) * h.width + math.pi * h.width ** 2 / 4
        sigma = punch_stress_mpa(h.perimeter(), area, s, sigma_b, norms)
        lvl = "ok" if sigma <= allow else ("warn" if sigma <= 1.25 * allow else "error")
        f.append(Finding(lvl, "punch_stress",
                         f"{h.id}: сжатие пуансона {sigma:.0f} МПа при допустимом {allow:.0f} МПа",
                         [h.id]))
        e = hole_edge_distance(h, poly)
        need = norms.get("geometry_rules.hole_edge_min_over_s") * s
        f.append(Finding("ok" if e >= need else "warn", "hole_edge",
                         f"{h.id}: перемычка до края детали {e:.2f} мм (норма ≥ {need:.2f})", [h.id]))

    need_hh = norms.get("geometry_rules.hole_hole_min_over_s") * s
    for i, h1 in enumerate(part.holes):
        for h2 in part.holes[i + 1:]:
            d = hole_hole_distance(h1, h2)
            f.append(Finding("ok" if d >= need_hh else "warn", "hole_hole",
                             f"{h1.id}–{h2.id}: перемычка {d:.2f} мм (норма ≥ {need_hh:.2f})",
                             [h1.id, h2.id]))

    # --- гибы -----------------------------------------------------------
    bg = bend_geometry(part, norms)
    k_r = mat["min_bend_r_over_s"]
    for b in part.bends:
        g = bg[b.id]
        if not g["r_known"]:
            f.append(Finding("unknown", "bend_r",
                             f"{b.id}: внутренний радиус гиба не измерен — принят r = {g['r']:.1f} мм", [b.id]))
        elif g["r"] < k_r * s:
            f.append(Finding("warn", "bend_r",
                             f"{b.id}: радиус {g['r']:.1f} мм меньше нормы {k_r:.1f}·S — риск трещины", [b.id]))
        else:
            f.append(Finding("ok", "bend_r", f"{b.id}: радиус {g['r']:.1f} мм в норме", [b.id]))
        if b.flange_straight_mm.known:
            need = norms.get("geometry_rules.flange_straight_min_over_s") * s
            lvl = "ok" if b.flange_straight_mm.value >= need else "warn"
            f.append(Finding(lvl, "flange_short",
                             f"{b.id}: прямой участок полки {b.flange_straight_mm.value:.1f} мм "
                             f"(норма ≥ {need:.1f})", [b.id]))

    # отверстие рядом с гибом
    need_hb = norms.get("geometry_rules.hole_bend_min_over_s") * s
    hole_after = {}
    for h in part.holes:
        for b in part.bends:
            d = hole_to_bend_distance(h, b, bg[b.id])
            if d is None:
                continue
            if d < need_hb:
                hole_after.setdefault(h.id, []).append(b.id)
                f.append(Finding("warn", "hole_near_bend",
                                 f"{h.id}: {max(d, 0):.2f} мм до начала гиба {b.id} (норма ≥ {need_hb:.1f}). "
                                 f"Пробивать ПОСЛЕ этого гиба, иначе отверстие вытянется.", [h.id, b.id]))

    # пересечение линий гибов (две зоны гиба в одной точке металла)
    crossings = []
    for i, b1 in enumerate(part.bends):
        for b2 in part.bends[i + 1:]:
            g1, g2 = bg[b1.id], bg[b2.id]
            (p1, u1), (p2, u2) = (g1["p0"], g1["u"]), (g2["p0"], g2["u"])
            den = u1[0] * u2[1] - u1[1] * u2[0]
            if abs(den) < 1e-6:
                continue
            dx, dy = p2[0] - p1[0], p2[1] - p1[1]
            t1 = (dx * u2[1] - dy * u2[0]) / den
            t2 = (dx * u1[1] - dy * u1[0]) / den
            if any(c0 < t1 < c1 for c0, c1 in g1["chords"]) and any(c0 < t2 < c1 for c0, c1 in g2["chords"]):
                crossings.append((b1.id, b2.id, p1[0] + t1 * u1[0], p1[1] + t1 * u1[1]))
    if crossings:
        pts = ", ".join(f"{a}×{b} в ({x:.1f}; {y:.1f})" for a, b, x, y in crossings)
        f.append(Finding("warn", "bends_cross",
                         f"Линии гибов пересекаются на заготовке: {pts}. Нужен вырез-разгрузка "
                         f"или подтверждение конструктора, что полка там сходит на нет.",
                         sorted({c[0] for c in crossings} | {c[1] for c in crossings})))
    return f, {"bend_geometry": bg, "hole_after": hole_after, "sigma_b": sigma_b}
