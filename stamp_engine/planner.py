"""Планировщик операций и схем штамповки.

Вход: деталь (развёртка, отверстия, гибы) + нормы + цех.
Выход: три схемы — какие штампы нужны, в каком порядке, какое усилие,
на какие прессы встают.

  A — совмещённый штамп (вырубка контура + пробивка за один ход) и гибочные;
  B — заготовка на гильотине, потом штамп обрубки уступов + пробивки, и гибочные;
  C — прогрессивный штамп (всё в одном, полоса шагает по позициям).

Порядок гибов здесь — ПРЕДЛОЖЕНИЕ по простым правилам. Его подтверждает конструктор.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

from .calc import (blank_size, clearance_per_side_mm, cutting_force, die_bend_force,
                   pierce_size)
from .checks import run_checks
from .geometry import Segment, segments_centroid, segments_length
from .models import KN_PER_TONNE, Part, Shop
from .norms import Norms
from .press import check_die_on_press


@dataclass
class BendGroup:
    kind: str                 # Z | U | L
    bends: list
    title: str


@dataclass
class Die:
    name: str
    purpose: str
    force_lines: list          # (что, кН)
    total_kn: float
    footprint: tuple | None
    cop: tuple | None = None   # центр давления (x, y)
    cop_offset: float | None = None
    tool_sizes: list = field(default_factory=list)
    notes: list = field(default_factory=list)
    press_checks: list = field(default_factory=list)
    needs_coil_feed: bool = False

    @property
    def total_t(self) -> float:
        return self.total_kn / KN_PER_TONNE


@dataclass
class Scheme:
    key: str
    title: str
    pre_ops: list
    dies: list
    notes: list = field(default_factory=list)
    suitable: bool = True
    verdict: str = ""


# ---------------------------------------------------------------------
def _line(b):
    p0, u = b.frame()
    return p0, u


def _parallel(b1, b2) -> bool:
    (_, u1), (_, u2) = _line(b1), _line(b2)
    return abs(u1[0] * u2[1] - u1[1] * u2[0]) < 1e-6


def _offset(b, pt) -> float:
    """Расстояние со знаком от линии гиба b до точки pt."""
    p0, u = _line(b)
    return (pt[0] - p0[0]) * (-u[1]) + (pt[1] - p0[1]) * u[0]


def group_bends(part: Part, norms: Norms) -> list[BendGroup]:
    """Подсечки (встречные гибы рядом) → U (две одинаковые полки по краям) → одиночные."""
    s = part.thickness.value
    gap = norms.get("geometry_rules.joggle_max_gap_over_s") * s
    x0, y0, x1, y1 = part.contour.bbox()
    center = ((x0 + x1) / 2, (y0 + y1) / 2)
    used, groups = set(), []
    bends = part.bends
    for i, b1 in enumerate(bends):
        for b2 in bends[i + 1:]:
            if {b1.id, b2.id} & used or not _parallel(b1, b2):
                continue
            if b1.direction != b2.direction and abs(_offset(b1, _line(b2)[0])) <= gap:
                groups.append(BendGroup("Z", [b1, b2], f"Подсечка (ступенька): {b1.id} + {b2.id}"))
                used |= {b1.id, b2.id}
    for i, b1 in enumerate(bends):
        for b2 in bends[i + 1:]:
            if {b1.id, b2.id} & used or not _parallel(b1, b2):
                continue
            d2 = _offset(b1, _line(b2)[0])            # всё меряем от линии b1: знак не зависит от направления линий
            dc = _offset(b1, center)
            between = dc * d2 > 0 and abs(dc) < abs(d2)
            if (b1.direction == b2.direction and abs(b1.angle_deg - b2.angle_deg) <= 1.0 and abs(d2) > gap
                    and between):
                groups.append(BendGroup("U", [b1, b2], f"Гибка двух полок за ход: {b1.id} + {b2.id}"))
                used |= {b1.id, b2.id}
    for b in bends:
        if b.id not in used:
            groups.append(BendGroup("L", [b], f"Гибка одной полки: {b.id}"))
    order = {"Z": 0, "U": 1, "L": 2}
    groups.sort(key=lambda g: order[g.kind])
    return groups


def _hole_segments(h):
    """Отверстие как набор сегментов (для центра давления)."""
    if h.kind == "round":
        r = h.d / 2
        return [Segment(h.cx + r, h.cy, h.cx - r, h.cy, 1.0),
                Segment(h.cx - r, h.cy, h.cx + r, h.cy, 1.0)]
    a = math.radians(h.angle_deg)
    ux, uy = math.cos(a), math.sin(a)
    vx, vy = -uy, ux
    half, r = max(h.length - h.width, 0) / 2, h.width / 2
    p = [(h.cx + ux * half + vx * r, h.cy + uy * half + vy * r),
         (h.cx - ux * half + vx * r, h.cy - uy * half + vy * r),
         (h.cx - ux * half - vx * r, h.cy - uy * half - vy * r),
         (h.cx + ux * half - vx * r, h.cy + uy * half - vy * r)]
    return [Segment(*p[0], *p[1]), Segment(*p[1], *p[2], 1.0),
            Segment(*p[2], *p[3]), Segment(*p[3], *p[0], 1.0)]


def _footprint(w: float, h: float) -> tuple:
    """Грубая оценка габарита нижней плиты штампа: рабочая зона + 40 мм стенки
    + 50 мм под колонки слева и справа. Уточняется на этапе проекта штампа."""
    return (w + 2 * (40 + 50), h + 2 * 40)


class Planner:
    def __init__(self, part: Part, shop: Shop, norms: Norms):
        self.part, self.shop, self.norms = part, shop, norms
        self.s = part.thickness.value
        self.mat = norms.material(part.material_group)
        self.findings, extra = run_checks(part, norms)
        self.bend_geo = extra["bend_geometry"]
        self.hole_after = extra["hole_after"]
        self.sigma_b = extra["sigma_b"]
        self.z = clearance_per_side_mm(self.s, self.mat["clearance_pct"])
        self.groups = group_bends(part, norms)
        bb = part.contour.bbox()
        self.bbox = bb
        self.w, self.h = bb[2] - bb[0], bb[3] - bb[1]
        self.center = ((bb[0] + bb[2]) / 2, (bb[1] + bb[3]) / 2)

    # --- отверстия: до или после гибки ----------------------------------
    def holes_before(self):
        return [h for h in self.part.holes if h.id not in self.hole_after]

    def holes_after_group(self, g: BendGroup):
        """Отверстия, которые надо пробить сразу после группы гибов g."""
        ids = {b.id for b in g.bends}
        out = []
        for h in self.part.holes:
            after = self.hole_after.get(h.id, [])
            if not after:
                continue
            last = max(i for i, gg in enumerate(self.groups) if {b.id for b in gg.bends} & set(after))
            if self.groups[last] is g and ids & set(after):
                out.append(h)
        return out

    # --- штампы ---------------------------------------------------------
    def _cut_die(self, name, purpose, contour_segments, holes, contour_kind) -> Die:
        lines, sizes, notes = [], [], []
        segs = list(contour_segments)
        l_contour = segments_length(segs)
        if l_contour > 0:
            lines.append((f"{contour_kind}: длина реза {l_contour:.1f} мм", None))
        for h in holes:
            segs += _hole_segments(h)
            lines.append((f"Пробивка {h.id}: периметр {h.perimeter():.1f} мм", None))
            sizes.append((h.id, pierce_size(h.size(), h.tol_plus, self.z)))
            if h.tol_plus == 0 and h.tol_minus == 0:
                notes.append(f"{h.id}: допуск отверстия не задан — пуансон по номиналу. Задайте допуск.")
        total_len = segments_length(segs)
        cf = cutting_force(total_len, self.s, self.sigma_b, self.norms)
        lines += [(f"Срез: {self.norms.get('cutting.k_force')} × {total_len:.1f} мм × {self.s} мм × "
                   f"τ {cf.tau_mpa:.0f} МПа", cf.p_cut_kn),
                  ("Съём с пуансона", cf.p_strip_kn),
                  (f"Проталкивание ({cf.n_in_land} шт. в пояске)", cf.p_push_kn)]
        cop = segments_centroid(segs)
        off = math.hypot(cop[0] - self.center[0], cop[1] - self.center[1])
        n_features = (1 if contour_segments else 0) + len(holes)
        if n_features > 1 and off > self.norms.get("press.cop_offset_warn_mm"):
            notes.append(f"Центр давления смещён от центра заготовки на {off:.0f} мм: "
                         f"ось хвостовика ставить в точку ({cop[0]:.1f}; {cop[1]:.1f}).")
        return Die(name, purpose, lines, cf.total_kn, _footprint(self.w, self.h), cop, off,
                   sizes, notes)

    def _bend_die(self, g: BendGroup, idx: int) -> Die:
        lengths = [self.bend_geo[b.id]["length"] for b in g.bends]
        bf = die_bend_force(g.kind, lengths, self.s, self.sigma_b, self.norms)
        lines = [(f"Длина линий гиба: {', '.join(f'{l:.1f}' for l in lengths)} мм", None),
                 ("Свободная гибка", bf.air_kn),
                 (f"С дожимом ×{self.norms.get('bending.bottoming_factor')} (для точного угла)",
                  bf.bottomed_kn - bf.air_kn),
                 ("Прижим/выталкиватель", bf.pad_kn)]
        notes = []
        for b in g.bends:
            geo = self.bend_geo[b.id]
            notes.append(f"{b.id}: угол {b.angle_deg:g}°, r = {geo['r']:.1f} мм"
                         f"{'' if geo['r_known'] else ' (не измерен)'}, x = {geo['x']:.2f}, "
                         f"зона гиба на развёртке {geo['ba']:.2f} мм")
        if g.kind != "L" or g.bends[0].angle_deg < 85:
            notes.append("Угол «не 90°» или две полки за ход — пружинение подбирается при приладке.")
        return Die(f"Штамп {idx}: {g.title.split(':')[0].lower()}", g.title, lines,
                   bf.total_kn, _footprint(self.w, self.h), notes=notes)

    def _pierce_after_die(self, holes, g: BendGroup, idx: int) -> Die:
        d = self._cut_die(f"Штамп {idx}: пробивка после гибки",
                          f"Пробивка {', '.join(h.id for h in holes)} после «{g.title}»",
                          [], holes, "")
        d.notes.append("Деталь уже с гибом: опора под место пробивки должна повторять форму детали.")
        d.notes.append("Вопрос конструктору: можно ли совместить эту пробивку со следующей гибкой в одном штампе?")
        return d

    def _tail_dies(self, start_idx: int) -> list:
        dies, idx = [], start_idx
        for g in self.groups:
            dies.append(self._bend_die(g, idx))
            idx += 1
            after = self.holes_after_group(g)
            if after:
                dies.append(self._pierce_after_die(after, g, idx))
                idx += 1
        return dies

    # --- схемы ----------------------------------------------------------
    def scheme_a(self) -> Scheme:
        c = self.part.contour
        die1 = self._cut_die("Штамп 1: совмещённый (вырубка + пробивка)",
                             "Вырубка всего контура и пробивка отверстий за один ход",
                             c.segments, self.holes_before(), "Вырубка контура")
        die1.tool_sizes.insert(0, ("контур (габарит)", blank_size(self.w, 0.0, self.z)))
        pre = [f"Нарезать полосу шириной ≈ {self.w + 2 * 1.5 * self.s:.1f} мм на гильотине (оценка)"]
        return Scheme("A", "Совмещённый штамп + гибочные", pre, [die1] + self._tail_dies(2))

    def scheme_b(self) -> Scheme:
        c = self.part.contour
        pre = [f"Гильотина: заготовка {self.w:.2f} × {self.h:.2f} мм "
               f"(точность резки ±{self.norms.get('shop.guillotine_tol_mm')} мм влияет на высоту полок)"]
        dies = []
        if c.is_rectangle():
            if self.holes_before():
                dies.append(self._cut_die("Штамп 1: пробивка", "Пробивка отверстий",
                                          [], self.holes_before(), ""))
        else:
            d = self._cut_die("Штамп 1: обрубка уступов + пробивка",
                              "Обрезает углы прямоугольной заготовки по контуру и пробивает отверстия",
                              c.segments_off_bbox(), self.holes_before(), "Обрубка уступов")
            d.notes.append("Обрубка режет с одной стороны пуансона — боковая сила. "
                           "Нужна опора (пятка) у пуансона.")
            dies.append(d)
        scheme = Scheme("B", "Гильотина + обрубка/пробивка + гибочные", pre,
                        dies + self._tail_dies(len(dies) + 1))
        if self.shop.has_guillotine is False:
            scheme.suitable = False
            scheme.verdict = "В цехе нет гильотины."
        elif self.shop.has_guillotine is None:
            scheme.verdict = "Наличие гильотины в цехе не подтверждено."
        return scheme

    def scheme_c(self) -> Scheme:
        s = self.s
        n = self.norms
        bridge = n.get("progressive.bridge_over_s") * s
        side = n.get("progressive.side_web_over_s") * s
        pitch = min(self.w, self.h) + bridge
        strip_w = max(self.w, self.h) + 2 * side
        stations = ["Пробивка отверстий и пилотов"]
        if not self.part.contour.is_rectangle():
            stations.append("Обрубка уступов")
        for g in self.groups:
            stations.append(g.title)
            if self.holes_after_group(g):
                stations.append("Пробивка после гибки")
        stations.append("Отрезка детали от полосы")
        stations += ["Пустая позиция"] * int(n.get("progressive.idle_stations"))
        cut_len = (segments_length(self.part.contour.segments_off_bbox()) +
                   sum(h.perimeter() for h in self.part.holes) + max(self.w, self.h))
        cf = cutting_force(cut_len, s, self.sigma_b, n)
        bend_total = sum(die_bend_force(g.kind, [self.bend_geo[b.id]["length"] for b in g.bends],
                                        s, self.sigma_b, n).total_kn for g in self.groups)
        length = len(stations) * pitch + 2 * 60
        die = Die("Прогрессивный штамп", f"{len(stations)} позиций, шаг ≈ {pitch:.1f} мм",
                  [(f"Резка всех позиций (≈{cut_len:.0f} мм реза)", cf.total_kn),
                   ("Все гибы", bend_total)],
                  cf.total_kn + bend_total, (length, strip_w + 2 * 80),
                  notes=[f"Позиции: {' → '.join(stations)}",
                         f"Полоса ≈ {strip_w:.1f} мм, длина штампа ≈ {length:.0f} мм (оценка)"],
                  needs_coil_feed=True)
        sch = Scheme("C", "Прогрессивный штамп", [f"Рулон/полоса шириной ≈ {strip_w:.1f} мм"], [die])
        reasons = []
        if max(self.w, self.h) > n.get("progressive.max_blank_mm_first"):
            reasons.append(f"деталь {max(self.w, self.h):.0f} мм — больше {n.get('progressive.max_blank_mm_first'):.0f} мм "
                           f"для первого прогрессивного штампа")
        dirs = []
        for b in self.part.bends:
            if not any(_parallel(b, d) for d in dirs):
                dirs.append(b)
        if len(dirs) > 1:
            reasons.append("гибы в двух направлениях — в полосе это сложно")
        ser = self.part.series
        if ser.known and ser.value < n.get("progressive.min_series_per_year"):
            reasons.append(f"серия {ser.value:,} шт. меньше порога окупаемости "
                           f"{n.get('progressive.min_series_per_year'):,} шт/год (уточнить: в год или всего?)"
                           .replace(",", " "))
        if reasons:
            sch.suitable = False
            sch.verdict = "Не рекомендуется сейчас: " + "; ".join(reasons) + "."
        return sch

    # --- всё вместе -----------------------------------------------------
    def plan(self) -> list[Scheme]:
        schemes = [self.scheme_a(), self.scheme_b(), self.scheme_c()]
        for sch in schemes:
            for d in sch.dies:
                d.press_checks = [check_die_on_press(d.total_kn, d.footprint, p, self.norms,
                                                     needs_coil_feed=d.needs_coil_feed)
                                  for p in self.shop.presses]
            if sch.suitable:
                no_press = [d.name for d in sch.dies
                            if all(pc.force_status == "fail" for pc in d.press_checks)]
                unconfirmed = [d.name for d in sch.dies
                               if not any(pc.force_status == "ok" for pc in d.press_checks)]
                if no_press:
                    sch.suitable = False
                    sch.verdict = "Ни один пресс не тянет по усилию: " + "; ".join(no_press) + "."
                elif unconfirmed:
                    sch.verdict = (sch.verdict + " " if sch.verdict else "") + \
                        "Не подтверждено (нет данных о прессах) для: " + "; ".join(unconfirmed) + "."
        return schemes

    def recommend(self, schemes: list[Scheme]) -> Scheme | None:
        ok = [s for s in schemes if s.suitable]
        if not ok:
            return None
        return min(ok, key=lambda s: (len(s.dies), max((d.total_kn for d in s.dies), default=0.0)))
