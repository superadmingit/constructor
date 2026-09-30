"""3D-модель гнутой детали по той же модели, что и развёртка (OpenCascade через CadQuery).

Строится из частей: плиты основания, дуги гибов (кольцевые секторы радиусов r и r+S), плоские полки,
зона подсечки. Затем объединение и вырезка отверстий. Выход: STEP (открывает любой CAD: NX, SolidWorks,
Компас, Onshape, Fusion) и картинки проекций.

Упрощения v1 (пишутся в warnings): одна подсечка; полка, проходящая через зону подсечки, в самой зоне
не строится (обычно она там сходит на нет).
"""
from __future__ import annotations

import math

import cadquery as cq

from .unfold import EPS, Flat, NotSupported, _dot, _sub

BIG = 1000.0


def _poly_plan(outline, n_arc=24):
    from ..geometry import Contour
    return Contour([list(v) for v in outline]).polygon(n_arc)


def _dir(a):
    return (math.cos(a), math.sin(a))


def _plane_for_edge(f, sa, sb):
    """Плоскость, в которой локальные (x, y) = (n наружу, z вверх), выдавливание вдоль ребра от sa до sb."""
    t3 = cq.Vector(f.t[0], f.t[1], 0)
    n3 = cq.Vector(f.n[0], f.n[1], 0)
    sign = f.t[0] * f.n[1] - f.t[1] * f.n[0]
    if sign < 0:
        o = f.at(sb, 0.0)
        return cq.Plane(origin=(o[0], o[1], 0), xDir=n3, normal=-t3)
    o = f.at(sa, 0.0)
    return cq.Plane(origin=(o[0], o[1], 0), xDir=n3, normal=t3)


def _bend_geom(f, zo):
    """Центр дуги, углы начала и конца, направление полки после дуги — в координатах (n, z)."""
    T, r = f._T, f.r
    RO = r + T
    th = math.radians(f.theta_deg)
    if f.direction == "down":
        c = (-f.nums["ossb"], zo - RO)
        a0, a1 = math.pi / 2, math.pi / 2 - th
        d = (math.cos(th), -math.sin(th))
    else:
        c = (-f.nums["ossb"], zo - T + RO)
        a0, a1 = -math.pi / 2, -math.pi / 2 + th
        d = (math.cos(th), math.sin(th))
    return c, a0, a1, d, RO


def _bend_solid(f, sa, sb, zo):
    c, a0, a1, _, RO = _bend_geom(f, zo)
    r = f.r
    am = (a0 + a1) / 2
    P = lambda R, a: (c[0] + R * math.cos(a), c[1] + R * math.sin(a))
    wp = (cq.Workplane(_plane_for_edge(f, sa, sb)).moveTo(*P(RO, a0)).threePointArc(P(RO, am), P(RO, a1))
          .lineTo(*P(r, a1)).threePointArc(P(r, am), P(r, a0)).close().extrude(sb - sa))
    return wp


def _flange_plate(f, sa, sb, zo):
    """Плоская часть полки: от конца дуги на длину Lo(s) − OSSB вдоль полки."""
    c, _, a1, d, RO = _bend_geom(f, zo)
    Po = (c[0] + RO * math.cos(a1), c[1] + RO * math.sin(a1))
    ls = lambda s: f.Lo(s) - f.nums["ossb"]
    ss = sorted({sa, sb} | {s for s, _ in f.stations if sa < s < sb})
    # участки, где полка длиннее дуги
    pts, prev = [], None
    for s in ss:
        if prev is not None and (ls(prev) > 0) != (ls(s) > 0):
            k = ls(prev) / (ls(prev) - ls(s))
            pts.append(prev + k * (s - prev))
        pts.append(s)
        prev = s
    s_lo = min((s for s in pts if ls(s) >= -1e-9), default=None)
    s_hi = max((s for s in pts if ls(s) >= -1e-9), default=None)
    if s_lo is None or s_hi - s_lo < 1e-3:
        return None, None
    prof = [s for s in pts if s_lo - 1e-9 <= s <= s_hi + 1e-9]
    t3 = cq.Vector(f.t[0], f.t[1], 0)
    n3 = cq.Vector(f.n[0], f.n[1], 0)
    d3 = n3 * d[0] + cq.Vector(0, 0, 1) * d[1]
    o = f.at(0.0, Po[0])
    origin = cq.Vector(o[0], o[1], Po[1])
    plane = cq.Plane(origin=origin, xDir=t3, normal=t3.cross(d3))
    outline = [(s_lo, 0.0), (s_hi, 0.0)] + [(s, max(ls(s), 0.0)) for s in reversed(prof)]
    clean = []
    for p in outline:
        if not clean or math.hypot(p[0] - clean[-1][0], p[1] - clean[-1][1]) > 1e-6:
            clean.append(p)
    inward = cq.Vector(-math.cos(a1), 0, -math.sin(a1))
    inward3 = n3 * inward.x + cq.Vector(0, 0, 1) * inward.z
    sgn = 1 if plane.zDir.dot(inward3) > 0 else -1
    plate = cq.Workplane(plane).polyline(clean).close().extrude(sgn * f._T)
    return plate, (plane, sgn)


def _cut_flange_holes(solid, f, plane_sgn, zo):
    if not f.holes or plane_sgn is None:
        return solid
    plane, sgn = plane_sgn
    for h in f.holes:
        s = float(h["s"])
        u = f.Lo(s) - float(h["e"]) - f.nums["ossb"]
        wp = cq.Workplane(plane).center(s, u)
        if h.get("kind", "round") == "round":
            cutter = wp.circle(_v(h["d"]) / 2).extrude(3 * f._T, both=True)
        else:
            cutter = wp.slot2D(_v(h["length"]), _v(h["width"]), float(h.get("angle", 0.0))).extrude(3 * f._T, both=True)
        solid = solid.cut(cutter)
    return solid


def _v(x):
    return float(x["value"]) if isinstance(x, dict) else float(x)


def build_solid(spec: dict, flat: Flat):
    """Твёрдое тело гнутой детали (cq.Workplane) и список упрощений."""
    from shapely.geometry import Polygon

    T = flat.T
    notes = []
    for f in flat.flanges:
        f._T = T
    base_pts = _poly_plan(spec["base"]["outline"])
    base_poly = Polygon(base_pts)
    for f in flat.flanges:
        strip = Polygon([f.at(f.s0, -f.nums["ossb"]), f.at(f.s1, -f.nums["ossb"]),
                         f.at(f.s1, BIG), f.at(f.s0, BIG)])
        base_poly = base_poly.difference(strip)

    if len(flat.joggles) > 1:
        raise NotSupported("3D: больше одной подсечки пока не строим (развёртка при этом считается).")
    jog = flat.joggles[0] if flat.joggles else None

    def half(poly, lo=None, hi=None):
        if jog is None:
            return poly
        u, nrm, P0 = jog.u, jog.nrm, jog.P0
        def pt(c, t):
            return (P0[0] + nrm[0] * c + u[0] * t, P0[1] + nrm[1] * c + u[1] * t)
        c0 = -BIG if lo is None else lo
        c1 = BIG if hi is None else hi
        region = Polygon([pt(c0, -BIG), pt(c1, -BIG), pt(c1, BIG), pt(c0, BIG)])
        return poly.intersection(region)

    zo_far = 0.0
    if jog is not None:
        zo_far = jog.offset if jog.direction == "up" else -jog.offset

    parts = []

    def plate(poly, zo):
        geoms = [poly] if poly.geom_type == "Polygon" else list(getattr(poly, "geoms", []))
        for g in geoms:
            if g.is_empty or g.area < 1e-6:
                continue
            pts = list(g.exterior.coords)[:-1]
            parts.append(cq.Workplane("XY").workplane(offset=zo).polyline(pts).close().extrude(-T))

    if jog is None:
        plate(base_poly, 0.0)
    else:
        plate(half(base_poly, hi=0.0), 0.0)
        plate(half(base_poly, lo=jog.nums["p"]), zo_far)
        parts.append(_joggle_solid(jog, T, half(Polygon(base_pts), lo=0.0, hi=jog.nums["p"]), zo_far))

    for f in flat.flanges:
        pieces = [(f.s0, f.s1, 0.0)]
        if jog is not None:
            cs = [_dot(_sub(f.at(s, 0.0), jog.P0), jog.nrm) for s in (f.s0, f.s1)]
            p = jog.nums["p"]
            if min(cs) >= p - EPS:
                pieces = [(f.s0, f.s1, zo_far)]
            elif max(cs) > EPS:
                def s_at(cv):
                    return f.s0 + (cv - cs[0]) / (cs[1] - cs[0]) * (f.s1 - f.s0)
                near = sorted((f.s0, min(max(s_at(0.0), f.s0), f.s1)) if cs[0] <= 0 else (min(max(s_at(0.0), f.s0), f.s1), f.s1))
                far = sorted((min(max(s_at(p), f.s0), f.s1), f.s1) if cs[1] >= p else (f.s0, min(max(s_at(p), f.s0), f.s1)))
                pieces = [(near[0], near[1], 0.0), (far[0], far[1], zo_far)]
                notes.append(f"Полка {f.id} проходит через зону подсечки: на участке ступеньки не показана.")
        for sa, sb, zo in pieces:
            if sb - sa < 1e-3:
                continue
            parts.append(_bend_solid(f, sa, sb, zo))
            pl, ps = _flange_plate(f, sa, sb, zo)
            if pl is not None:
                parts.append(_cut_flange_holes(pl, f, ps, zo))

    solid = parts[0]
    for p in parts[1:]:
        solid = solid.union(p, clean=True)

    zmin, zmax = -T - abs(zo_far) - 5, abs(zo_far) + 5
    for h in spec["base"].get("holes", []):
        x, y = float(h["x"]), float(h["y"])
        wp = cq.Workplane("XY").workplane(offset=zmin).center(x, y)
        if h.get("kind", "round") == "round":
            cutter = wp.circle(_v(h["d"]) / 2).extrude(zmax - zmin)
        else:
            cutter = wp.slot2D(_v(h["length"]), _v(h["width"]), float(h.get("angle", 0.0))).extrude(zmax - zmin)
        solid = solid.cut(cutter)
    return solid, notes


def _joggle_solid(j, T, zone_poly, zo_far):
    """Сечение ступеньки (дуги r и r+S, прямой участок s), протянутое вдоль линии и обрезанное контуром."""
    r = j.r
    RO = r + T
    g = math.radians(j.gamma_deg)
    s = j.nums["s"]
    C1 = (0.0, r)
    top1 = [(C1[0] + r * math.cos(a), C1[1] + r * math.sin(a)) for a in (-math.pi / 2, -math.pi / 2 + g / 2, -math.pi / 2 + g)]
    e1 = top1[-1]
    e2 = (e1[0] + s * math.cos(g), e1[1] + s * math.sin(g))
    C2 = (e2[0] + RO * math.sin(g), e2[1] - RO * math.cos(g))
    top2 = [(C2[0] + RO * math.cos(a), C2[1] + RO * math.sin(a)) for a in (math.pi / 2 + g, math.pi / 2 + g / 2, math.pi / 2)]
    bot2 = [(C2[0] + r * math.cos(a), C2[1] + r * math.sin(a)) for a in (math.pi / 2, math.pi / 2 + g / 2, math.pi / 2 + g)]
    bot1 = [(C1[0] + RO * math.cos(a), C1[1] + RO * math.sin(a)) for a in (-math.pi / 2 + g, -math.pi / 2 + g / 2, -math.pi / 2)]
    if j.direction == "up":
        F = lambda p: p                          # ближняя плита: верх z=0, низ z=−S
    else:
        F = lambda p: (p[0], -T - p[1])          # зеркально относительно середины листа
    nrm3 = cq.Vector(j.nrm[0], j.nrm[1], 0)
    plane = cq.Plane(origin=(j.P0[0], j.P0[1], 0), xDir=nrm3, normal=nrm3.cross(cq.Vector(0, 0, 1)))
    wp = (cq.Workplane(plane).moveTo(*F(top1[0])).threePointArc(F(top1[1]), F(top1[2])).lineTo(*F(top2[0]))
          .threePointArc(F(top2[1]), F(top2[2])).lineTo(*F(bot2[0])).threePointArc(F(bot2[1]), F(bot2[2]))
          .lineTo(*F(bot1[0])).threePointArc(F(bot1[1]), F(bot1[2])).close().extrude(BIG, both=True))
    geoms = [zone_poly] if zone_poly.geom_type == "Polygon" else list(zone_poly.geoms)
    zone = None
    for g_ in geoms:
        if g_.is_empty:
            continue
        pr = (cq.Workplane("XY").workplane(offset=-T - abs(zo_far) - 5).polyline(list(g_.exterior.coords)[:-1])
              .close().extrude(2 * abs(zo_far) + T + 10))
        zone = pr if zone is None else zone.union(pr)
    return wp.intersect(zone)


def export_step(solid, path: str) -> None:
    cq.exporters.export(solid, path)


def export_views_svg(solid, path: str, direction=(1, -1, 0.8), w=640, h=420) -> None:
    cq.exporters.export(solid, path, opt={"width": w, "height": h, "marginLeft": 10, "marginTop": 10,
                                          "showAxes": False, "projectionDir": direction, "strokeWidth": 0.4,
                                          "strokeColor": (29, 37, 40), "hiddenColor": (160, 170, 166),
                                          "showHidden": False})
