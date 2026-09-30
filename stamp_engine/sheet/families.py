"""Типовые детали (шаблоны) и планы замеров для рабочих.

Рабочий не описывает рёбра и полки. Он выбирает по картинке тип детали и вводит размеры по буквам
(A, B, C…), каждую с подсказкой «что это и чем мерить». Отсюда собирается общая модель детали
(stamp_engine.sheet), дальше всё как у любой детали: развёртка, 3D, чертёж, расчёт штампов.

Непохожую на шаблоны деталь собирает оператор в редакторе модели (тот же формат, больше свободы).

Каждое значение хранит источник: measured (измерил), stated (со слов), assumed (не знаю → взято по умолчанию).
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Measure:
    key: str
    title: str
    what: str
    how: list
    tool: str
    lo: float
    hi: float
    unit: str = "мм"
    default: str | None = None        # "S" — равен толщине; число — значение по умолчанию; None — обязателен


@dataclass
class Family:
    key: str
    title: str
    hint: str
    measures: list = field(default_factory=list)
    faces: list = field(default_factory=list)     # где могут быть отверстия


S_ = Measure("S", "Толщина металла", "Толщина листа, из которого сделана деталь.",
             ["Штангенциркуль, наружные губки.", "Мерить на плоском месте, не на гибе.", "Три раза в разных местах."],
             "штангенциркуль", 0.3, 12)
R_ = Measure("R", "Внутренний радиус гиба", "Насколько плавно согнут металл, изнутри гиба.",
             ["Радиусомер: подобрать шаблон, который прилегает изнутри гиба без просвета.",
              "Нет радиусомера — «Не знаю», программа примет радиус равным толщине и пометит это."],
             "радиусомер", 0.2, 30, default="S")
U_ = Measure("U", "Угол полки", "На сколько градусов полка отогнута от основания. Прямой угол — 90.",
             ["Угломер: одна сторона на основание, другая на полку.", "Похоже на прямой угол — пишите 90."],
             "угломер", 10, 135, unit="°", default="90")

FAMILIES = {
    "plate": Family("plate", "Пластина", "Плоская деталь без гибов", [
        Measure("A", "Длина", "Самая длинная сторона.", ["Штангенциркуль или рулетка, по наружным краям."],
                "штангенциркуль", 2, 3000),
        Measure("B", "Ширина", "Поперёк длины.", ["По наружным краям."], "штангенциркуль", 2, 3000),
        S_], ["base"]),
    "angle": Family("angle", "Уголок", "Основание и одна полка", [
        Measure("A", "Длина", "Длина детали вдоль линии гиба.", ["По наружным краям, вдоль гиба."], "штангенциркуль", 5, 3000),
        Measure("B", "Ширина основания", "От свободного края основания до наружной стороны полки.",
                ["Наружные губки: одна на свободный край основания, другая на наружную сторону полки."],
                "штангенциркуль", 3, 1000),
        Measure("C", "Высота полки", "От наружной стороны основания до края полки.",
                ["Поставьте деталь на стол основанием вниз, измерьте высоту до края полки."],
                "штангенциркуль", 3, 1000),
        S_, R_, U_], ["base", "flange_1"]),
    "channel": Family("channel", "Скоба (П-профиль)", "Основание и две полки в одну сторону", [
        Measure("A", "Длина", "Длина детали вдоль гибов.", ["По наружным краям, вдоль гибов."], "штангенциркуль", 5, 3000),
        Measure("B", "Наружная ширина", "Поперёк детали, по наружным сторонам обеих полок.",
                ["Наружные губки поперёк детали, у основания полок."], "штангенциркуль", 5, 1000),
        Measure("C", "Высота полок", "От наружной стороны основания до края полки.",
                ["Деталь основанием вниз на стол, высота до края полки. Измерьте обе полки: если разные, скажите."],
                "штангенциркуль", 3, 1000),
        S_, R_, U_], ["base", "flange_1", "flange_2"]),
    "zprofile": Family("zprofile", "Z-профиль", "Основание и две полки в разные стороны", [
        Measure("A", "Длина", "Длина детали вдоль гибов.", ["По наружным краям."], "штангенциркуль", 5, 3000),
        Measure("B", "Ширина основания", "Между наружными сторонами двух полок, поперёк основания.",
                ["Наружные губки поперёк основания, у гибов."], "штангенциркуль", 5, 1000),
        Measure("C", "Высота верхней полки", "От наружной стороны основания до края полки, которая вверх.",
                ["Штангенциркуль вертикально, от основания до края полки."], "штангенциркуль", 3, 1000),
        Measure("D", "Высота нижней полки", "То же для полки, которая вниз.",
                ["Переверните деталь и измерьте так же."], "штангенциркуль", 3, 1000),
        S_, R_, U_], ["base", "flange_1", "flange_2"]),
}


class InputError(ValueError):
    """Не хватает размера или он явно неверный. Текст — для рабочего."""


def _take(fam: Family, values: dict) -> dict:
    """Проверяет и достаёт значения. values: {буква: число | {"value", "source"} | None («не знаю»)}."""
    out = {}
    for m in fam.measures:
        raw = values.get(m.key)
        v = raw.get("value") if isinstance(raw, dict) else raw
        src = raw.get("source", "measured") if isinstance(raw, dict) else "measured"
        if v is None:
            if m.default is None:
                raise InputError(f"Нужен размер {m.key} — {m.title.lower()}.")
            v = out["S"]["value"] if m.default == "S" else float(m.default)
            src = "assumed"
        v = float(v)
        if not m.lo <= v <= m.hi:
            raise InputError(f"{m.key} = {v:g} {m.unit}: обычно от {m.lo:g} до {m.hi:g}. Проверьте число и единицы.")
        out[m.key] = {"value": v, "source": src}
    return out


def build(family: str, values: dict, holes: list | None = None, meta: dict | None = None) -> dict:
    """Собирает модель детали из шаблона.

    holes: [{"face": "base"|"flange_1"|"flange_2", "kind": "round"|"slot", "d"|("length","width"),
             "x","y" (для base: x от левого края основания, y от переднего торца) |
             "s","e" (для полки: s вдоль от переднего торца, e от свободного края полки)}]
    Передний торец один для всей детали (y = 0), поэтому рабочий меряет все отверстия от одного края."""
    if family not in FAMILIES:
        raise InputError(f"Нет такого типа детали: {family}. Есть: {', '.join(FAMILIES)}.")
    fam = FAMILIES[family]
    v = _take(fam, values)
    val = lambda k: v[k]["value"]
    A, S = val("A"), val("S")
    spec = dict(meta or {})
    mat = spec.get("material") or {}
    if not mat.get("group"):
        raise InputError("Выберите материал детали (сталь, нержавейка, алюминий, латунь).")
    spec.setdefault("id", "NEW")
    spec.update({"family": family, "thickness_mm": v["S"], "measurements": v})
    if "R" in v:
        spec["bend_radius_mm"] = v["R"]
    B = val("B")
    spec["base"] = {"outline": [[0, 0], [B, 0], [B, A], [0, A]], "holes": []}
    fl = []
    ang = v.get("U", {"value": 90.0, "source": "assumed"})
    if family == "angle":
        fl = [{"id": "F1", "title": "Полка", "edge": 1, "angle": ang, "direction": "up", "height": v["C"]}]
    elif family == "channel":
        fl = [{"id": "F1", "title": "Полка правая", "edge": 1, "angle": ang, "direction": "up", "height": v["C"]},
              {"id": "F2", "title": "Полка левая", "edge": 3, "angle": ang, "direction": "up", "height": v["C"]}]
    elif family == "zprofile":
        fl = [{"id": "F1", "title": "Полка вверх", "edge": 1, "angle": ang, "direction": "up", "height": v["C"]},
              {"id": "F2", "title": "Полка вниз", "edge": 3, "angle": ang, "direction": "down", "height": v["D"]}]
    if family != "plate" and S >= min(val(k) for k in ("C", "D") if k in v):
        raise InputError("Высота полки меньше толщины металла — проверьте C (и D).")
    spec["flanges"] = fl
    for i, h in enumerate(holes or []):
        face = h.get("face", "base")
        hh = {k: h[k] for k in h if k != "face"}
        hh.setdefault("id", f"H{i + 1}")
        if face == "base":
            spec["base"]["holes"].append(hh)
        else:
            idx = int(face.split("_")[1]) - 1
            if idx >= len(fl):
                raise InputError(f"Отверстие {hh['id']}: у детали нет полки {idx + 1}.")
            if fl[idx]["edge"] == 3 and "s" in hh:          # ребро 3 идёт от заднего торца к переднему
                hh["s"] = A - float(hh["s"])
            fl[idx].setdefault("holes", []).append(hh)
    spec.setdefault("blank_status", "preliminary")
    return spec


def measurement_plan(family: str) -> list:
    """Список замеров для экрана рабочего: буква, название, что это, как мерить, чем, диапазон."""
    return [m.__dict__.copy() for m in FAMILIES[family].measures]
