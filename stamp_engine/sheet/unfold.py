"""Модель листовой детали и развёртка. Общая для любой детали, ни одной конкретной детали здесь нет.

Деталь описывается так, как её мерит рабочий на гнутом образце:

  base      — основание: плоская грань, вид сверху (в плане). Контур вершинами [x, y, bulge]
              (bulge — дуга к следующей вершине, как в DXF). Отверстия основания — в тех же координатах.
  flanges   — полки на ПРЯМЫХ рёбрах основания: ребро = номер вершины, с которой оно начинается.
              Полка может занимать часть ребра (span) и иметь переменную высоту (profile).
  joggles   — подсечки (ступеньки) поперёк основания.

СОГЛАШЕНИЕ О РАЗМЕРАХ (его соблюдают формы ввода, рабочий об этом не думает):
  * Ребро основания с полкой проходит по «наружному острому углу» — там, где сходятся наружные поверхности
    основания и полки. Для полки 90° это обычный наружный размер штангенциркулем.
  * Высота полки H — габаритная: от наружной поверхности основания до самой дальней точки кромки полки,
    перпендикулярно основанию. Так мерят, поставив деталь на стол.
  * Угол полки — на сколько градусов отогнута от плоскости основания (90 — прямой угол).
  * Отверстие в полке: s — вдоль ребра от его начала до центра, e — от свободной кромки полки до центра.
  * Подсечка: offset — на сколько поднимается (опускается) дальняя часть, angle — наклон ступеньки,
    line — линия в плане, где ступенька начинается (at="start") или кончается (at="end").

Формулы развёртки (стандартная модель нейтрального слоя):
  OSSB = (r+S)·tg(θ/2)      наружный отступ от острого угла до начала гиба
  BA   = θ·(r + x·S)        длина нейтрального слоя в гибе, x — K-фактор
  BD   = 2·OSSB − BA        укорочение на гиб: развёртка = сумма наружных размеров − Σ BD
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

EPS = 1e-6


class SheetError(ValueError):
    """Деталь описана так, что построить её нельзя. Текст — для человека."""


class NotSupported(SheetError):
    """Такой тип детали программа пока не делает. Деталь уходит конструктору."""


# ------------------------------------------------------------------ helpers
def _val(v, default=None):
    if isinstance(v, dict):
        return v.get("value", default) if v.get("source") != "unknown" else default
    return default if v is None else v


def _src(v, default="stated"):
    return v.get("source", default) if isinstance(v, dict) else default


def _sub(a, b):
    return (a[0] - b[0], a[1] - b[1])


def _add(a, b, k=1.0):
    return (a[0] + k * b[0], a[1] + k * b[1])


def _dot(a, b):
    return a[0] * b[0] + a[1] * b[1]


def _cross(a, b):
    return a[0] * b[1] - a[1] * b[0]


def _unit(a):
    l = math.hypot(*a)
    return (a[0] / l, a[1] / l)


def _signed_area(pts):
    return 0.5 * sum(_cross(pts[i], pts[(i + 1) % len(pts)]) for i in range(len(pts)))


# ------------------------------------------------------------------ bend math
def bend_numbers(theta_deg: float, r: float, T: float, x: float) -> dict:
    th = math.radians(theta_deg)
    ossb = (r + T) * math.tan(th / 2)
    ba = th * (r + x * T)
    return {"theta": th, "ossb": ossb, "ba": ba, "bd": 2 * ossb - ba}


def joggle_numbers(e: float, gamma_deg: float, r: float, T: float, x: float) -> dict:
    """Подсечка: две равные дуги в разные стороны и прямой наклонный участок между ними.

    Подъём поверхности: (2r+S)(1−cos γ) + s·sin γ = e  →  s.
    В плане ступенька занимает p = (2r+S)·sin γ + s·cos γ, в развёртке f = 2·γ·(r+x·S) + s."""
    g = math.radians(gamma_deg)
    s = (e - (2 * r + T) * (1 - math.cos(g))) / math.sin(g)
    if s < 0:
        raise SheetError(f"Подсечка высотой {e:g} мм при радиусе {r:g} и угле {gamma_deg:g}° невозможна: "
                         f"два гиба уже дают больше. Проверьте высоту ступеньки или радиус.")
    p = (2 * r + T) * math.sin(g) + s * math.cos(g)
    ba = g * (r + x * T)
    f = 2 * ba + s
    return {"gamma": g, "s": s, "p": p, "f": f, "dl": f - p, "ba": ba}


# ------------------------------------------------------------------ geometry objects
@dataclass
class FlangeGeo:
    id: str
    title: str
    edge: int
    V0: tuple
    t: tuple                  # направление ребра
    n: tuple                  # наружу от основания, в плоскости основания
    L: float                  # длина ребра
    s0: float
    s1: float
    stations: list            # [(s, Lo)] — Lo: наружная длина полки от острого угла до кромки
    theta_deg: float
    direction: str
    r: float
    x: float
    x_src: str
    r_src: str
    nums: dict
    holes: list

    def Lo(self, s: float) -> float:
        st = self.stations
        if s <= st[0][0]:
            return st[0][1]
        for (sa, la), (sb, lb) in zip(st, st[1:]):
            if sa - EPS <= s <= sb + EPS:
                return la if sb - sa < EPS else la + (lb - la) * (s - sa) / (sb - sa)
        return st[-1][1]

    def at(self, s: float, n: float) -> tuple:
        """Точка в плане: s вдоль ребра, n наружу от острого угла."""
        return _add(_add(self.V0, self.t, s), self.n, n)


@dataclass
class JoggleGeo:
    id: str
    title: str
    P0: tuple                 # точка на линии НАЧАЛА ступеньки (в плане)
    u: tuple                  # направление линии
    nrm: tuple                # к дальней (смещённой) стороне
    offset: float
    gamma_deg: float
    direction: str            # дальняя сторона поднимается (up) или опускается (down)
    r: float
    x: float
    nums: dict

    def shift(self, p) -> float:
        """На сколько точка плана сдвигается в развёртке (вдоль nrm)."""
        c = _dot(_sub(p, self.P0), self.nrm)
        if c <= 0:
            return 0.0
        if c >= self.nums["p"]:
            return self.nums["dl"]
        return self.nums["dl"] * c / self.nums["p"]


@dataclass
class Flat:
    contour: list             # [[x, y, bulge]] развёртка, против часовой
    holes: list               # отверстия для ядра (плоские координаты)
    bends: list               # линии гибов для ядра
    flanges: list
    joggles: list
    warnings: list = field(default_factory=list)
    T: float = 0.0

    def bbox(self):
        xs = [p[0] for p in self.contour]
        ys = [p[1] for p in self.contour]
        return min(xs), min(ys), max(xs), max(ys)


# ------------------------------------------------------------------ main
def _x_for(spec, r, T, norms):
    k = spec.get("k_factor")
    if _val(k) is not None:
        return float(_val(k)), _src(k)
    if norms is None:
        raise SheetError("Нет K-фактора: задайте k_factor в детали или передайте нормы цеха.")
    return norms.x_for(r / T), "norm"


def _parse_flange(i_f, f, outline, orient, T, r_def, spec, norms, warn):
    n_v = len(outline)
    e = f.get("edge")
    if not isinstance(e, int) or not 0 <= e < n_v:
        raise SheetError(f"Полка {f.get('id', i_f + 1)}: ребро {e!r} не существует (у основания {n_v} рёбер).")
    V0, V1 = outline[e][:2], outline[(e + 1) % n_v][:2]
    if abs(outline[e][2]) > EPS:
        raise NotSupported(f"Полка {f.get('id')}: ребро {e} — дуга. Полки на кривых рёбрах (отбортовка) пока не делаем.")
    L = math.hypot(*_sub(V1, V0))
    t = _unit(_sub(V1, V0))
    n = (t[1], -t[0]) if orient > 0 else (-t[1], t[0])
    theta = float(_val(f.get("angle"), 90.0))
    if not 1.0 <= theta <= 135.0:
        raise NotSupported(f"Полка {f.get('id')}: угол {theta:g}° вне диапазона 1–135°.")
    direction = f.get("direction", "up")
    if direction not in ("up", "down"):
        raise SheetError(f"Полка {f.get('id')}: direction должно быть up или down.")
    r = float(_val(f.get("radius"), r_def))
    x, x_src = _x_for(spec, r, T, norms)
    nums = bend_numbers(theta, r, T, x)
    span = f.get("span") or [0.0, L]
    s0, s1 = float(span[0]), float(span[1])
    if not (-EPS <= s0 < s1 <= L + EPS):
        raise SheetError(f"Полка {f.get('id')}: участок {span} выходит за ребро длиной {L:.2f} мм.")
    th = math.radians(theta)
    if f.get("profile"):
        prof = sorted((float(s), float(H)) for s, H in f["profile"])
    else:
        H = _val(f.get("height"))
        if H is None:
            raise SheetError(f"Полка {f.get('id')}: не задана высота.")
        prof = [(s0, float(H)), (s1, float(H))]
    stations = []
    for s, H in prof:
        Lo = (H - T * math.cos(th)) / math.sin(th)
        if H <= T + 1e-9:
            raise SheetError(f"Полка {f.get('id')}: высота {H:g} мм не больше толщины листа.")
        stations.append((min(max(s, s0), s1), Lo))
    if stations[0][0] > s0 + EPS:
        stations.insert(0, (s0, stations[0][1]))
    if stations[-1][0] < s1 - EPS:
        stations.append((s1, stations[-1][1]))
    if min(lo for _, lo in stations) < nums["ossb"] + 2 * T and not f.get("allow_short"):
        short = min(lo for _, lo in stations) - nums["ossb"]
        warn.append(f"Полка {f.get('id')}: прямой участок местами {max(short, 0):.1f} мм — меньше 2·S. "
                    f"Короткую полку ровно не согнуть; если так и задумано (полка сходит на нет), это видно на образце.")
    return FlangeGeo(f.get("id", f"F{i_f + 1}"), f.get("title", ""), e, V0, t, n, L, s0, s1, stations,
                     theta, direction, r, x, x_src, _src(f.get("radius"), _src(spec.get("bend_radius_mm"))),
                     nums, f.get("holes", []))


def _parse_joggle(i_j, j, T, r_def, spec, norms):
    (ax, ay), (bx, by) = j["line"]
    u = _unit((bx - ax, by - ay))
    far = j.get("far_point")
    if far is None:
        raise SheetError(f"Подсечка {j.get('id')}: укажите far_point — любую точку на смещённой стороне.")
    nrm = (-u[1], u[0])
    if _dot(_sub(far, (ax, ay)), nrm) < 0:
        nrm = (u[1], -u[0])
    r = float(_val(j.get("radius"), r_def))
    x, _ = _x_for(spec, r, T, norms)
    e = float(_val(j.get("offset")))
    gamma = float(_val(j.get("angle"), 45.0))
    nums = joggle_numbers(e, gamma, r, T, x)
    P0 = (ax, ay)
    if j.get("at", "start") == "end":
        P0 = _add(P0, nrm, -nums["p"])
    return JoggleGeo(j.get("id", f"J{i_j + 1}"), j.get("title", "Подсечка"), P0, u, nrm, e, gamma,
                     j.get("direction", "up"), r, x, nums)


def _cleanup(pts):
    """Убирает совпадающие точки, точки на прямой и «шипы» (возврат по той же прямой)."""
    changed = True
    while changed and len(pts) > 3:
        changed = False
        out = []
        n = len(pts)
        for i in range(n):
            a, b, c = pts[i - 1], pts[i], pts[(i + 1) % n]
            if math.hypot(b[0] - a[0], b[1] - a[1]) < 1e-6:
                changed = True
                continue
            if abs(a[2]) < EPS and abs(b[2]) < EPS:
                ab, bc = _sub(b[:2], a[:2]), _sub(c[:2], b[:2])
                lab, lbc = math.hypot(*ab), math.hypot(*bc)
                if lab > 1e-9 and lbc > 1e-9 and abs(_cross(ab, bc)) / (lab * lbc) < 1e-7:
                    changed = True               # прямая или шип: вершина лишняя
                    continue
            out.append(b)
        pts = out
    return pts


def unfold(spec: dict, norms=None) -> Flat:
    T = float(_val(spec["thickness_mm"]))
    r_def = float(_val(spec.get("bend_radius_mm"), T))
    base = spec["base"]
    outline = [(float(v[0]), float(v[1]), float(v[2]) if len(v) > 2 else 0.0) for v in base["outline"]]
    if len(outline) < 3:
        raise SheetError("Контур основания: нужно минимум 3 вершины.")
    orient = 1 if _signed_area([v[:2] for v in outline]) > 0 else -1
    warn: list[str] = []

    flanges = [_parse_flange(i, f, outline, orient, T, r_def, spec, norms, warn)
               for i, f in enumerate(spec.get("flanges", []))]
    by_edge: dict[int, list] = {}
    for fg in flanges:
        by_edge.setdefault(fg.edge, []).append(fg)
    n_v = len(outline)
    for e, fl in by_edge.items():
        fl.sort(key=lambda f: f.s0)
        for a, b in zip(fl, fl[1:]):
            if b.s0 < a.s1 + EPS:
                raise SheetError(f"Полки {a.id} и {b.id} на одном ребре перекрываются.")
        nxt = by_edge.get((e + 1) % n_v)
        if nxt and fl[-1].s1 > fl[-1].L - EPS and nxt[0].s0 < EPS:
            raise NotSupported(f"Полки {fl[-1].id} и {nxt[0].id} сходятся в углу (коробка, лоток). "
                               f"Угловую разгрузку программа пока не строит — такую деталь ведёт конструктор.")

    joggles = [_parse_joggle(i, j, T, r_def, spec, norms) for i, j in enumerate(spec.get("joggles", []))]
    for a, b in zip(joggles, joggles[1:]):
        if abs(_cross(a.u, b.u)) > 1e-6:
            raise NotSupported("Непараллельные подсечки пока не поддерживаются.")

    def phi(p):
        q = p
        for j in joggles:
            q = _add(q, j.nrm, j.shift(p))
        return q

    # ---- обход контура: рёбра с полками заменяются контуром полки -------------
    pts = []
    for i, (vx, vy, b) in enumerate(outline):
        fl = by_edge.get(i)
        if not fl:
            pts.append((vx, vy, b))
            continue
        pts.append((vx, vy, 0.0))
        for f in fl:
            if f.s0 > EPS:
                pts.append((*f.at(f.s0, 0.0), 0.0))
            for s, lo in f.stations:
                pts.append((*f.at(s, lo - f.nums["bd"]), 0.0))
            if f.s1 < f.L - EPS:
                pts.append((*f.at(f.s1, 0.0), 0.0))
    for p in pts:
        for j in joggles:
            c = _dot(_sub(p[:2], j.P0), j.nrm)
            if 0 < c < j.nums["p"]:
                warn.append(f"Подсечка {j.id}: вершина контура ({p[0]:.1f}; {p[1]:.1f}) попадает в зону ступеньки — "
                            f"её положение в развёртке приближённое. Проверьте на пробной заготовке.")
                break
    flat_pts = _cleanup([(*phi(p[:2]), p[2]) for p in pts])

    _check_overlaps(outline, flanges, flat_pts, phi)

    # ---- отверстия --------------------------------------------------------
    holes = []
    for h in base.get("holes", []):
        holes.append(_hole_out(h, phi((float(h["x"]), float(h["y"]))), float(h.get("angle", 0.0))))
    for f in flanges:
        for h in f.holes:
            s = float(h["s"])
            u_c = f.Lo(s) - float(h["e"])
            if u_c <= 0:
                raise SheetError(f"Отверстие {h.get('id')} в полке {f.id}: e больше высоты полки.")
            c = f.at(s, u_c - f.nums["bd"])
            ang = math.degrees(math.atan2(f.t[1], f.t[0])) + float(h.get("angle", 0.0))
            holes.append(_hole_out(h, phi(c), ang, on=f.id))

    # ---- линии гибов --------------------------------------------------------
    bends = []
    for f in flanges:
        nc = -f.nums["ossb"] + f.nums["ba"] / 2
        p0, p1 = phi(f.at(f.s0, nc)), phi(f.at(f.s1, nc))
        bends.append({"id": f.id, "title": f.title or f"Полка на ребре {f.edge}",
                      "line": [list(p0), list(p1)], "angle_deg": round(f.theta_deg, 4),
                      "r_in": {"value": f.r, "source": f.r_src}, "direction": f.direction,
                      "x": f.x, "ba": f.nums["ba"]})
    for j in joggles:
        opp = "down" if j.direction == "up" else "up"
        for k, (cc, d) in enumerate(((j.nums["ba"] / 2, j.direction),
                                     (j.nums["ba"] + j.nums["s"] + j.nums["ba"] / 2, opp)), start=1):
            mid = _add(j.P0, j.nrm, cc)
            bends.append({"id": f"{j.id}.{k}", "title": f"{j.title}, гиб {k}",
                          "line": [list(_add(mid, j.u, -1e4)), list(_add(mid, j.u, 1e4))],
                          "angle_deg": j.gamma_deg, "r_in": {"value": j.r, "source": "stated"},
                          "direction": d, "x": j.x, "ba": j.nums["ba"], "clip": True})
    return Flat([list(p) for p in flat_pts], holes, bends, flanges, joggles, warn, T)


def _check_overlaps(outline, flanges, flat_pts, phi):
    """Полка в развёртке не должна налезать на основание и другие полки и не должна к ним прилегать:
    иначе её не отогнуть без выреза (разгрузки). Такая ошибка обычно значит неверный номер ребра или высоту."""
    from shapely.geometry import Polygon
    from ..geometry import Contour
    poly = Polygon(Contour([list(p) for p in flat_pts]).polygon(16))
    if not poly.is_valid:
        raise SheetError("Развёртка пересекает сама себя: полка налезает на другую часть детали. "
                         "Проверьте номера рёбер, высоты и направления полок.")
    base = Polygon([phi(p) for p in Contour([list(v) for v in outline]).polygon(16)]).buffer(0)
    eps = 0.05
    regions = []
    for f in flanges:
        pts = [phi(f.at(f.s0, eps)), phi(f.at(f.s1, eps))]
        pts += [phi(f.at(s, max(lo - f.nums["bd"], eps + 1e-3))) for s, lo in reversed(f.stations)]
        reg = Polygon(pts).buffer(0)
        if reg.is_empty or reg.area < 1e-6:
            continue
        if reg.intersection(base).length > 1e-6 or reg.intersection(base).area > 1e-6:
            raise SheetError(f"Полка {f.id} в развёртке налезает на основание или прилегает к нему вне своего "
                             f"ребра: без выреза-разгрузки её не отогнуть. Проверьте ребро, высоту, направление.")
        for g, other in regions:
            if reg.intersects(other):
                raise SheetError(f"Полки {g} и {f.id} в развёртке задевают друг друга. Нужен вырез-разгрузка.")
        regions.append((f.id, reg))


def _hole_out(h, c, angle_deg, on="base"):
    kind = h.get("kind", "round")
    out = {"id": h.get("id", "H"), "kind": kind, "cx": round(c[0], 4), "cy": round(c[1], 4),
           "source": _src(h.get("d", h.get("width")), "measured"), "on": on}
    if kind == "round":
        out["d"] = float(_val(h["d"]))
    elif kind == "slot":
        out.update(length=float(_val(h["length"])), width=float(_val(h["width"])), angle_deg=angle_deg % 180)
    else:
        raise NotSupported(f"Отверстие {h.get('id')}: вид {kind!r} пока не поддерживается (есть round, slot).")
    for k in ("tol_plus", "tol_minus"):
        if k in h:
            out[k] = float(h[k])
    return out


def to_part_dict(spec: dict, flat: Flat) -> dict:
    """Описание детали для расчётного ядра (Part.from_dict)."""
    keep = {k: v for k, v in spec.items() if k not in ("base", "flanges", "joggles", "bend_radius_mm", "k_factor")}
    keep.update({
        "blank": {"status": spec.get("blank_status", "preliminary"), "contour": flat.contour},
        "holes": flat.holes,
        "bends": [{k: v for k, v in b.items() if k in ("id", "title", "line", "angle_deg", "r_in", "direction", "clip")}
                  for b in flat.bends],
        "bend_x": ({"value": flat.bends[0]["x"], "source": _src(spec.get("k_factor"), "norm")}
                   if flat.bends else None),
        "flat_warnings": flat.warnings,
    })
    return keep
