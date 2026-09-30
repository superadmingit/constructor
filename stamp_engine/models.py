"""Модели данных.

ГЛАВНОЕ ПРАВИЛО ПРОГРАММЫ: у каждого числа есть источник.
«Не знаю» — это не ноль и не «наверное нормально». Проверка, для которой
нет данных, получает статус НЕТ ДАННЫХ, а не ОК.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from .geometry import Contour

KN_PER_TONNE = 9.80665

# Источники значений. Порядок не важен, важна категория.
RELIABLE_SOURCES = {"measured", "nameplate", "passport", "certificate", "stated", "calculated"}
SOURCE_RU = {
    "measured": "измерено",
    "nameplate": "с шильдика",
    "passport": "из паспорта",
    "certificate": "из сертификата",
    "stated": "со слов",
    "calculated": "рассчитано",
    "assumed": "ДОПУЩЕНИЕ",
    "norm": "по нормам цеха",
    "unknown": "НЕТ ДАННЫХ",
}


@dataclass
class Val:
    """Число с источником: откуда мы его знаем."""
    value: Any = None
    source: str = "unknown"
    note: str = ""

    @property
    def known(self) -> bool:
        return self.value is not None and self.source != "unknown"

    @property
    def assumed(self) -> bool:
        return self.source in ("assumed", "norm")

    def src_ru(self) -> str:
        return SOURCE_RU.get(self.source, self.source)

    @staticmethod
    def parse(raw) -> "Val":
        if raw is None:
            return Val()
        if isinstance(raw, Val):
            return raw
        if isinstance(raw, dict):
            src = raw.get("source", "stated")
            if src not in SOURCE_RU:
                raise ValueError(f"Неизвестный источник значения: {src!r}")
            v = raw.get("value")
            return Val(v, src if v is not None else "unknown", raw.get("note", ""))
        return Val(raw, "stated")


@dataclass
class Hole:
    id: str
    kind: str                  # "round" | "slot"
    cx: float
    cy: float
    d: float = 0.0             # для round
    length: float = 0.0        # для slot: полная длина по оси паза
    width: float = 0.0         # для slot: ширина
    angle_deg: float = 0.0     # для slot: 0 — паз вдоль X, 90 — вдоль Y
    tol_plus: float = 0.0      # допуск на размер отверстия, мм (+)
    tol_minus: float = 0.0     # (−), число положительное
    source: str = "stated"
    on: str = "base"           # где отверстие на гнутой детали: base или id полки

    def perimeter(self) -> float:
        import math
        if self.kind == "round":
            return math.pi * self.d
        straight = max(self.length - self.width, 0.0)
        return 2 * straight + math.pi * self.width

    def size(self) -> float:
        """Размер, определяющий пуансон: диаметр или ширина паза."""
        return self.d if self.kind == "round" else self.width

    def half_extent(self, axis: str) -> float:
        """Полуразмер отверстия вдоль оси X ('x') или Y ('y')."""
        if self.kind == "round":
            return self.d / 2
        along_x = abs(self.angle_deg) % 180 < 45 or abs(self.angle_deg) % 180 > 135
        long_half, short_half = self.length / 2, self.width / 2
        if axis == "x":
            return long_half if along_x else short_half
        return short_half if along_x else long_half


@dataclass
class Bend:
    """Гиб на развёртке.

    Линия гиба задаётся одним из способов:
      line = [[x0, y0], [x1, y1]] — отрезок средней линии зоны гиба (так её выдаёт развёртка);
      axis + pos — прямая x = pos (axis='x') или y = pos (axis='y'), длина берётся по контуру.
    clip=True: line — это прямая, реальную длину обрезает контур заготовки.
    angle_deg — на сколько градусов отгибаем от плоскости (90 — под прямым углом).
    direction — 'down' или 'up' относительно лицевой стороны."""
    id: str
    angle_deg: float
    r_in: Val
    direction: str
    axis: str = ""
    pos: float = 0.0
    line: Optional[list] = None
    clip: bool = False
    title: str = ""
    flange_straight_mm: Val = field(default_factory=Val)

    def frame(self):
        """(точка на линии, единичное направление) в координатах развёртки."""
        import math
        if self.line:
            (x0, y0), (x1, y1) = self.line
            l = math.hypot(x1 - x0, y1 - y0)
            return (x0, y0), ((x1 - x0) / l, (y1 - y0) / l)
        if self.axis == "x":
            return (self.pos, 0.0), (0.0, 1.0)
        if self.axis == "y":
            return (0.0, self.pos), (1.0, 0.0)
        raise ValueError(f"Гиб {self.id}: нет ни line, ни axis/pos")

    def chords(self, contour) -> list:
        """Участки линии гиба, лежащие на заготовке: [(t0, t1)] вдоль frame()."""
        import math
        p0, u = self.frame()
        if self.line and not self.clip:
            (x0, y0), (x1, y1) = self.line
            return [(0.0, math.hypot(x1 - x0, y1 - y0))]
        return contour.chord_on_ray(p0, u)


@dataclass
class Part:
    id: str
    revision: str
    title: str
    material_group: str
    material_grade: Val
    sigma_b_mpa: Val
    thickness: Val
    series: Val
    contour: Contour
    contour_status: str
    holes: list
    bends: list
    open_questions: list
    answers: list = field(default_factory=list)
    bend_x: Val = field(default_factory=Val)     # x детали: перекрывает таблицу норм
    recalc: dict = field(default_factory=dict)
    sensitivity: list = field(default_factory=list)
    flat_warnings: list = field(default_factory=list)

    @staticmethod
    def from_dict(d: dict) -> "Part":
        holes = [Hole(**h) for h in d.get("holes", [])]
        bends = []
        for b in d.get("bends", []):
            b = dict(b)
            b["r_in"] = Val.parse(b.get("r_in"))
            b["flange_straight_mm"] = Val.parse(b.get("flange_straight_mm"))
            bends.append(Bend(**b))
        return Part(
            id=d["id"],
            revision=d.get("revision", ""),
            title=d.get("title", ""),
            material_group=d["material"]["group"],
            material_grade=Val.parse(d["material"].get("grade")),
            sigma_b_mpa=Val.parse(d["material"].get("sigma_b_mpa")),
            thickness=Val.parse(d["thickness_mm"]),
            series=Val.parse(d.get("series")),
            contour=Contour(d["blank"]["contour"]),
            contour_status=d["blank"].get("status", "unknown"),
            holes=holes,
            bends=bends,
            open_questions=d.get("open_questions", []),
            answers=d.get("answers", []),
            bend_x=Val.parse(d.get("bend_x")),
            recalc=d.get("recalc", {}),
            sensitivity=d.get("sensitivity", []),
            flat_warnings=d.get("flat_warnings", []),
        )


@dataclass
class Press:
    id: str
    name: str
    kind: str                       # crank_open | crank_closed | hydraulic | other | unknown
    model: Val
    force_kn: Val
    stroke_mm: Val
    shut_height_max_mm: Val         # расстояние стол(или плита)—ползун в НМТ при поднятой регулировке
    shut_adjust_mm: Val             # величина регулировки
    table_lr_mm: Val                # стол слева-направо
    table_fb_mm: Val                # стол спереди-назад
    shank_d_mm: Val                 # отверстие под хвостовик
    feed: list = field(default_factory=list)
    notes: str = ""

    @property
    def force_t(self) -> Optional[float]:
        return self.force_kn.value / KN_PER_TONNE if self.force_kn.known else None

    @staticmethod
    def from_dict(d: dict) -> "Press":
        force = d.get("force_kn")
        if force is None and d.get("force_t") is not None:
            f = Val.parse(d["force_t"])
            force = {"value": f.value * KN_PER_TONNE if f.known else None,
                     "source": f.source, "note": (f.note + " (пересчёт из тонн)").strip()}
        return Press(
            id=d["id"], name=d.get("name", d["id"]), kind=d.get("kind", "unknown"),
            model=Val.parse(d.get("model")), force_kn=Val.parse(force),
            stroke_mm=Val.parse(d.get("stroke_mm")),
            shut_height_max_mm=Val.parse(d.get("shut_height_max_mm")),
            shut_adjust_mm=Val.parse(d.get("shut_adjust_mm")),
            table_lr_mm=Val.parse(d.get("table_lr_mm")),
            table_fb_mm=Val.parse(d.get("table_fb_mm")),
            shank_d_mm=Val.parse(d.get("shank_d_mm")),
            feed=d.get("feed", []), notes=d.get("notes", ""),
        )


@dataclass
class Shop:
    name: str
    presses: list
    has_guillotine: Optional[bool]     # None: не знаем
    heat_treatment: str             # "yes" | "outsourced" | "no" | "unknown"
    machines: list

    @staticmethod
    def from_dict(d: dict) -> "Shop":
        return Shop(
            name=d.get("name", "Цех"),
            presses=[Press.from_dict(p) for p in d.get("presses", [])],
            has_guillotine=d.get("has_guillotine"),
            heat_treatment=d.get("heat_treatment", "unknown"),
            machines=d.get("machines", []),
        )
