"""Иллюстрации для страницы сбора данных.

Все рисунки в ширину 520 единиц, чтобы на телефоне (≈360 px) подписи в 14–15 единиц
читались как 10–11 px. Оформление задаёт CSS страницы через классы:
  body, ln, ln2, edge, hid, hid-fill, ghost, dim, ext, ax, lead, zone, metal2,
  lbl, lbl-s, note, plate*, call/calln.
Подсвечиваемые части — группы <g id="t-..." class="t">; страница добавляет класс "on".
Маркеры стрелок (#arr) лежат в общем спрайте страницы.
"""
from __future__ import annotations

import math


def n(v):
    s = f"{v:.1f}"
    return s[:-2] if s.endswith(".0") else s


def rect(x, y, w, h, cls="body", rx=0):
    r = f' rx="{n(rx)}"' if rx else ""
    return f'<rect x="{n(x)}" y="{n(y)}" width="{n(w)}" height="{n(h)}"{r} class="{cls}"/>'


def line(x1, y1, x2, y2, cls="ln"):
    return f'<line x1="{n(x1)}" y1="{n(y1)}" x2="{n(x2)}" y2="{n(y2)}" class="{cls}"/>'


def circ(cx, cy, r, cls="body"):
    return f'<circle cx="{n(cx)}" cy="{n(cy)}" r="{n(r)}" class="{cls}"/>'


def path(d, cls="body"):
    return f'<path d="{d}" class="{cls}"/>'


def poly(pts, cls="body", close=True):
    d = "M" + " L".join(f"{n(x)},{n(y)}" for x, y in pts) + (" Z" if close else "")
    return path(d, cls)


def text(x, y, s, cls="lbl", anchor=None, rot=None):
    a = f' text-anchor="{anchor}"' if anchor else ""
    r = f' transform="rotate({rot} {n(x)} {n(y)})"' if rot is not None else ""
    return f'<text x="{n(x)}" y="{n(y)}" class="{cls}"{a}{r}>{s}</text>'


def lead(x1, y1, x2, y2):
    return line(x1, y1, x2, y2, "lead")


def dim(x1, y1, x2, y2):
    return (f'<line x1="{n(x1)}" y1="{n(y1)}" x2="{n(x2)}" y2="{n(y2)}" class="dim" '
            f'marker-start="url(#arr)" marker-end="url(#arr)"/>')


def ext(x1, y1, x2, y2):
    return line(x1, y1, x2, y2, "ext")


def grp(gid, inner, cls="t"):
    return f'<g id="{gid}" class="{cls}">{inner}</g>'


def svg(w, h, inner, label):
    return (f'<svg viewBox="0 0 {w} {h}" xmlns="http://www.w3.org/2000/svg" role="img" '
            f'aria-label="{label}">{inner}</svg>')


def scaled(k, inner):
    return f'<g transform="scale({k})">{inner}</g>'


# =====================================================================
#  1. ПРЕСС, ВИД СБОКУ
# =====================================================================
def press_side() -> str:
    K = 0.72
    q = lambda v: v * K
    hatch = "".join(f"M{x},612 l12,12 " for x in range(20, 460, 40))
    o = []
    o.append(scaled(K, line(20, 612, 460, 612) + path(hatch, "ln2")))
    o.append(grp("t-frame", scaled(K, path("M110,600 L110,96 L410,96 L410,206 L196,206 L196,432 "
                                           "L448,432 L448,600 Z")) +
                 text(158, 94, "Станина", "lbl-s")))
    o.append(grp("t-flywheel", scaled(K, circ(112, 150, 72) + circ(112, 150, 14, "ln")) +
                 text(8, 32, "Маховик") + lead(38, 38, 58, 68)))
    o.append(grp("t-plate", scaled(K, rect(124, 300, 56, 36, "body", 3) +
                                   path("M132,310 h40 M132,318 h32 M132,326 h36", "ln2")) +
                 text(6, 208, "Шильдик") + lead(56, 214, q(124), q(318))))
    o.append(scaled(K, line(342, 110, 342, 560, "ax")))
    o.append(grp("t-slide", scaled(K, rect(292, 206, 100, 58) + rect(292, 270, 100, 58, "ghost")) +
                 text(336, 170, "Ползун") + lead(332, 166, q(392), q(235)) +
                 text(214, 184, "ВМТ", "note") + text(214, 230, "НМТ", "note")))
    o.append(grp("t-adjust", scaled(K, rect(330, 206, 24, 18) +
                                    path("M330,210 h24 M330,214 h24 M330,218 h24", "ln2")) +
                 text(336, 140, "Регулировка высоты") + lead(332, 136, q(354), q(212))))
    o.append(grp("t-shank", scaled(K, rect(330, 240, 24, 24, "hid-fill")) +
                 text(336, 200, "Отв. под хвостовик") + lead(332, 196, q(354), q(252))))
    o.append(grp("t-bolster", scaled(K, rect(262, 410, 176, 22)) +
                 text(336, 300, "Подштамп. плита") + lead(332, 296, q(438), q(421))))
    o.append(grp("t-table", scaled(K, line(196, 432, 448, 432, "edge")) +
                 text(336, 326, "Стол") + lead(332, 322, q(448), q(432))))
    o.append(grp("t-opening", scaled(K, rect(316, 410, 52, 84, "hid-fill")) +
                 text(336, 364, "Провальное отв.") + lead(332, 360, q(368), q(470))))
    o.append(grp("t-pedal", scaled(K, path("M492,604 l52,-10 l4,6 l-52,10 z")) +
                 text(340, 420, "Педаль", "lbl-s")))
    # размеры
    o.append(grp("t-stroke",
                 ext(q(292), q(264), 178, q(264)) + ext(q(292), q(328), 178, q(328)) +
                 dim(186, q(264) + 2, 186, q(328) - 2) + text(146, 216, "Ход", "lbl-s")))
    o.append(grp("t-shut",
                 ext(q(292), q(328), 158, q(328)) + ext(q(262), q(410), 158, q(410)) +
                 dim(166, q(328) + 2, 166, q(410) - 2) +
                 text(180, q(410) - 2, "Закрытая", "lbl-s", rot=-90) +
                 text(194, q(410) - 2, "высота", "lbl-s", rot=-90)))
    o.append(grp("t-throat",
                 dim(q(198), 127, q(342), 127) + text(176, 120, "Вылет", "lbl-s")))
    o.append(grp("t-tablefb",
                 dim(q(198), 328, q(446), 328) + text(148, 350, "Стол спереди-назад", "lbl-s")))
    o.append(text(336, 452, "Оператор стоит справа", "note"))
    return svg(520, 470, "".join(o), "Открытый кривошипный пресс, вид сбоку, с подписанными частями")


# =====================================================================
#  2. ШИЛЬДИК
# =====================================================================
def nameplate() -> str:
    rows = [("t-np-model", "Модель", "КД21··"),
            ("t-np-force", "Усилие номинальное, кН", "630"),
            ("t-np-stroke", "Ход ползуна, мм", "···"),
            ("t-np-spm", "Число ходов в минуту", "···"),
            ("t-np-num", "Заводской номер", "·····"),
            ("t-np-year", "Год выпуска", "19··")]
    o = [rect(10, 10, 500, 316, "plate", 10)]
    o += [circ(x, y, 6, "rivet") for x, y in ((30, 30), (490, 30), (30, 306), (490, 306))]
    o.append(text(260, 50, "ЗАВОД КУЗНЕЧНО-ПРЕССОВОГО ОБОРУДОВАНИЯ", "plate-h", "middle"))
    o.append(line(40, 62, 480, 62, "ln2"))
    o.append(text(260, 86, "ПРЕСС КРИВОШИПНЫЙ ОТКРЫТЫЙ", "plate-t", "middle"))
    y = 100
    for gid, name, val in rows:
        o.append(grp(gid, rect(34, y, 452, 30, "row", 4) + text(46, y + 21, name, "plate-t") +
                     text(340, y + 21, val, "plate-v")))
        y += 34
    o.append(text(260, 318, "пример: 630 кН ≈ 63 тонны (кН делите на 10)", "plate-s", "middle"))
    return svg(520, 336, "".join(o), "Пример шильдика пресса: где модель, усилие, ход")


# =====================================================================
#  3. СТОЛ СВЕРХУ
# =====================================================================
def table_top() -> str:
    o = []
    o.append(rect(100, 24, 320, 40, "body"))
    o.append(text(260, 50, "Станина (сзади)", "lbl-s", "middle"))
    o.append(grp("t-tabletop", rect(100, 64, 320, 220, "body") + "".join(
        line(100, y, 420, y, "hid") for y in (110, 174, 238))))
    o.append(text(112, 104, "Т-образные пазы", "note"))
    o.append(grp("t-opening", rect(206, 132, 108, 84, "hid-fill", 10) +
                 text(260, 178, "Провал", "lbl-s", "middle")))
    o.append(grp("t-tablelr", ext(100, 284, 100, 322) + ext(420, 284, 420, 322) +
                 dim(102, 314, 418, 314) + text(260, 306, "Слева-направо", "lbl", "middle") +
                 text(100, 340, "слева", "note", "middle") + text(420, 340, "справа", "note", "middle")))
    o.append(grp("t-tablefb", ext(420, 64, 458, 64) + ext(420, 284, 458, 284) +
                 dim(452, 66, 452, 282) + text(486, 174, "Спереди-назад", "lbl", "middle", rot=-90)))
    o.append(path("M260,368 l-14,26 h28 z", "body"))
    o.append(text(260, 414, "Оператор стоит здесь (спереди)", "lbl-s", "middle"))
    return svg(520, 430, "".join(o), "Стол пресса сверху: размеры слева-направо и спереди-назад")


# =====================================================================
#  4. ПОЛЗУН СНИЗУ (отверстие под хвостовик)
# =====================================================================
def ram_bottom() -> str:
    o = []
    o.append(grp("t-ramface", rect(60, 50, 400, 230, "body") + "".join(
        line(x, 50, x, 280, "hid") for x in (140, 380)) +
        text(260, 272, "Нижняя плоскость ползуна", "lbl-s", "middle")))
    o.append(grp("t-shank-hole", circ(260, 168, 44, "hid-fill") + circ(260, 168, 2.5, "ln")))
    o.append(grp("t-shank-d", dim(218, 168, 302, 168) + text(260, 150, "Ø ? мм", "lbl", "middle") +
                 ext(216, 168, 216, 226) + ext(304, 168, 304, 226)))
    o.append(grp("t-jaws-in", rect(217, 158, 13, 20, "body") + rect(290, 158, 13, 20, "body") +
                 text(260, 246, "внутренние губки штангенциркуля", "lbl-s", "middle") +
                 lead(224, 234, 224, 180) + lead(296, 234, 296, 180)))
    o.append(text(260, 312, "Смотрим снизу вверх, на плоскость, к которой крепят штамп", "note", "middle"))
    return svg(520, 330, "".join(o), "Нижняя плоскость ползуна и отверстие под хвостовик")


# =====================================================================
#  5. ШТАНГЕНЦИРКУЛЬ
# =====================================================================
def caliper() -> str:
    o = []
    o.append(grp("t-scale", rect(50, 130, 440, 30, "body") + "".join(
        line(70 + i * 12, 130, 70 + i * 12, 130 + (14 if i % 5 == 0 else 8), "ln2") for i in range(0, 34)) +
        text(300, 190, "Штанга со шкалой", "lbl", "middle") + lead(300, 176, 300, 162)))
    o.append(grp("t-jaws-out", rect(50, 160, 24, 90) + rect(170, 160, 24, 90) +
                 rect(74, 200, 96, 50, "metal2") + text(122, 232, "деталь", "lbl-s", "middle") +
                 text(122, 274, "Наружные губки", "lbl", "middle") + lead(122, 262, 90, 252)))
    o.append(grp("t-jaws-in", rect(50, 76, 20, 54) + rect(172, 76, 20, 54) +
                 text(122, 52, "Внутренние губки", "lbl", "middle") + lead(122, 58, 122, 84) +
                 text(122, 112, "отверстие", "lbl-s", "middle")))
    o.append(grp("t-vernier", rect(170, 124, 110, 42, "body") + "".join(
        line(180 + i * 9, 154, 180 + i * 9, 166, "ln2") for i in range(0, 10)) +
        text(226, 20, "Нониус (подвижная шкала)", "lbl", "middle") + lead(226, 26, 226, 122)))
    o.append(grp("t-lock", rect(288, 116, 24, 14, "body", 2) +
                 text(372, 96, "Винт-фиксатор", "lbl", "middle") + lead(340, 102, 312, 118)))
    o.append(grp("t-depth", rect(490, 138, 26, 6, "body") +
                 text(430, 226, "Глубиномер", "lbl", "middle") + lead(444, 212, 506, 148) +
                 text(430, 244, "(выдвигается с торца)", "lbl-s", "middle")))
    return svg(520, 292, "".join(o), "Штангенциркуль: части и типы губок")


def vernier() -> str:
    x = lambda mm: 30 + (mm - 20) * 28
    o = [rect(20, 44, 484, 44, "body")]
    for m in range(20, 38):
        xx = x(m)
        if xx > 500:
            break
        o.append(line(xx, 88, xx, 88 - (20 if m % 5 == 0 else 12), "ln2"))
        if m % 5 == 0:
            o.append(text(xx, 56, str(m), "lbl-s", "middle"))
    o.append(text(490, 70, "мм", "note", "end"))
    x0 = x(23.4)
    o.append(rect(x0 - 8, 88, 270, 42, "metal2"))
    for i in range(11):
        o.append(line(x0 + 25.2 * i, 88, x0 + 25.2 * i, 88 + (26 if i in (0, 5, 10) else 16), "ln"))
    for i in (0, 5, 10):
        o.append(text(x0 + 25.2 * i, 152, str(i), "lbl-s", "middle"))
    o.append(grp("t-int", line(x0, 44, x0, 88, "edge") + lead(x0, 40, x0 - 30, 26) +
                 text(20, 20, "1. Нулевая риска нониуса", "lbl")))
    o.append(grp("t-dec", line(x0 + 100.8, 88, x0 + 100.8, 114, "edge") +
                 lead(x0 + 100.8, 162, x0 + 100.8, 118) +
                 text(x0 + 100.8, 180, "2. Совпавшая риска", "lbl", "middle")))
    o.append(text(260, 214, "Целые мм: слева от нуля нониуса, здесь 23", "lbl-s", "middle"))
    o.append(text(260, 234, "Десятые: номер совпавшей риски, здесь 4 → 0,4", "lbl-s", "middle"))
    o.append(text(260, 260, "Итого 23,4 мм", "lbl", "middle"))
    return svg(520, 272, "".join(o), "Как читать штангенциркуль с нониусом: пример 23,4 мм")


# =====================================================================
#  10. РАДИУС ГИБА
# =====================================================================
def bend_radius() -> str:
    o = []
    o.append(path("M148,20 L184,20 L184,110 A36,36 0 0 0 220,146 L420,146 L420,182 L220,182 "
                  "A72,72 0 0 1 148,110 Z", "body"))
    o.append(grp("t-gauge", circ(220, 110, 36, "hid-fill") +
                 path("M244,86 L330,20 L346,36 L256,104", "body") +
                 text(340, 66, "радиусомер", "lbl-s") + text(340, 84, "(шаблон нужного R)", "lbl-s")))
    o.append(grp("t-rin", line(220, 110, 194.5, 135.5, "dim") + circ(220, 110, 2.5, "ln") +
                 text(206, 122, "r", "lbl")))
    o.append(grp("t-thk", dim(148, 60, 184, 60) + text(166, 50, "S", "lbl", "middle")))
    o.append(text(360, 180, "Толщина S", "lbl-s") + lead(356, 176, 300, 164))
    o.append(text(20, 214, "Внутренний радиус r: шаблон, который прилегает к внутренней", "lbl-s"))
    o.append(text(20, 234, "стороне гиба без просвета, и есть радиус.", "lbl-s"))
    return svg(520, 250, "".join(o), "Как найти внутренний радиус гиба радиусомером")


# =====================================================================
#  11. ШТАМП В РАЗРЕЗЕ (закрыт), позиции с номерами
# =====================================================================
DIE_LEGEND = [
    (1, "t-d1", "Верхняя плита", "крепится к ползуну пресса через хвостовик"),
    (2, "t-d2", "Хвостовик", "круглый штырь сверху: входит в отверстие ползуна и центрирует штамп"),
    (3, "t-d3", "Втулка", "в верхней плите, скользит по колонке"),
    (4, "t-d4", "Колонка", "запрессована в нижнюю плиту, ведёт верх штампа без перекоса"),
    (5, "t-d5", "Пуансонодержатель", "держит пуансоны в верхней части штампа"),
    (6, "t-d6", "Подкладная плита", "закалённая пластина над пуансоном, чтобы он не вдавливался в мягкую плиту"),
    (7, "t-d7", "Пуансон", "нажимает на металл сверху; при пробивке размер отверстия задаёт он"),
    (8, "t-d8", "Съёмник", "снимает полосу с пуансона при подъёме и прижимает её при резке"),
    (9, "t-d9", "Пружина съёмника", "даёт усилие прижима и съёма"),
    (10, "t-d10", "Полоса или заготовка", "листовой металл, который обрабатывают"),
    (11, "t-d11", "Отход (высечка)", "вырезанный кусок; при пробивке падает вниз через провал"),
    (12, "t-d12", "Матрица", "закалённый блок с окном по форме пуансона; при вырубке размер детали задаёт она"),
    (13, "t-d13", "Нижняя плита", "лежит на столе пресса, на ней стоит матрица"),
    (14, "t-d14", "Провал", "окно в нижней плите и матрице, через него уходит отход"),
    (15, "t-d15", "Поясок матрицы", "прямой участок окна, ниже окно расширяется, чтобы отход не застревал"),
    (16, "t-d16", "Зазор", "щель между пуансоном и матрицей на сторону, около 5–10% толщины металла"),
]


def die_section() -> str:
    K, DX = 0.66, 8
    q = lambda v: DX + v * K
    qy = lambda v: (v - 60) * K
    S = lambda inner: f'<g transform="translate({DX},{n(-60 * K)}) scale({K})">{inner}</g>'
    zig = lambda x: path("M" + " L".join(f"{x + (10 if i % 2 else -10)},{262 + i * 13.7:.1f}" for i in range(9)) +
                         f" L{x},372", "ln")
    def call(num, x, y):        # кружок с номером в абсолютных координатах
        return circ(x, y, 9, "call") + text(x, y + 4.5, str(num), "calln", "middle")
    d = []
    d.append(grp("t-d13", S(rect(70, 470, 240, 50) + rect(450, 470, 240, 50)) + call(13, q(90), qy(495))))
    d.append(grp("t-d14", S(rect(310, 470, 140, 50, "zone")) + call(14, q(380), qy(495))))
    d.append(grp("t-d12", S(poly([(150, 410), (344, 410), (344, 426), (322, 470), (150, 470)]) +
                            poly([(416, 410), (610, 410), (610, 470), (438, 470), (416, 426)])) +
                 call(12, q(210), qy(440))))
    d.append(grp("t-d15", S(rect(344, 410, 72, 16, "zone")) + call(15, q(440), qy(418)) +
                 lead(q(440) - 9, qy(418), q(416), qy(418))))
    d.append(grp("t-d4", S(rect(106, 200, 20, 270) + rect(634, 200, 20, 270) +
                           rect(106, 470, 20, 30, "hid") + rect(634, 470, 20, 30, "hid") +
                           rect(106, 176, 20, 24, "hid") + rect(634, 176, 20, 24, "hid")) + call(4, q(116), qy(330))))
    d.append(grp("t-d1", S(rect(70, 150, 620, 50)) + call(1, q(190), qy(175))))
    d.append(grp("t-d3", S(rect(96, 150, 40, 50, "metal2") + rect(624, 150, 40, 50, "metal2")) +
                 call(3, q(150) + 0, qy(140)) + lead(q(150), qy(140) + 9, q(134), qy(160))))
    d.append(grp("t-d2", S(rect(350, 90, 60, 60) + path("M350,104 h60 M350,112 h60", "ln2")) + call(2, q(380), qy(120))))
    d.append(grp("t-d5", S(rect(150, 200, 460, 60)) + call(5, q(200), qy(230))))
    d.append(grp("t-d6", S(rect(310, 200, 140, 12, "metal2")) + call(6, q(470), qy(206)) +
                 lead(q(470) - 9, qy(206), q(450), qy(206))))
    d.append(grp("t-d7", S(rect(350, 260, 60, 158) + rect(350, 212, 60, 48, "hid")) + call(7, q(380), qy(320))))
    d.append(grp("t-d8", S(rect(170, 372, 174, 30) + rect(416, 372, 174, 30)) + call(8, q(250), qy(387))))
    d.append(grp("t-d9", S(zig(200) + zig(560) + line(200, 262, 200, 402, "hid") + line(560, 262, 560, 402, "hid")) +
                 call(9, q(200) + 24, qy(330))))
    d.append(grp("t-d10", S(rect(130, 402, 214, 8, "metal2") + rect(416, 402, 214, 8, "metal2")) +
                 call(10, q(560), qy(431)) + lead(q(560), qy(431) - 9, q(560), qy(410))))
    d.append(grp("t-d11", S(rect(350, 418, 60, 8, "metal2")) + call(11, q(380), qy(455)) +
                 lead(q(380), qy(455) - 9, q(380), qy(426))))
    d.append(grp("t-d16", S(rect(344, 414, 6, 12, "zone") + rect(410, 414, 6, 12, "zone")) +
                 call(16, q(300), qy(440)) + lead(q(300) + 9, qy(440) - 3, q(344), qy(420))))
    d.append(grp("t-dshut", ext(q(692), qy(150), 486, qy(150)) + ext(q(692), qy(520), 486, qy(520)) +
                 dim(480, qy(150) + 2, 480, qy(520) - 2) +
                 text(496, (qy(150) + qy(520)) / 2 + 52, "Закрытая высота штампа", "lbl-s", "middle", rot=-90)))
    d.append(text(260, 360, "Разрез, штамп закрыт. Не в масштабе.", "note", "middle"))
    return svg(520, 372, "".join(d), "Штамп в разрезе с пронумерованными деталями")


# =====================================================================
#  12. ЗНАЧКИ СТАНКОВ (96×64)
# =====================================================================
def machine_icon(kind: str) -> str:
    b = "body"
    g = {
        "lathe": rect(6, 46, 84, 8) + rect(6, 20, 24, 26) + rect(30, 24, 6, 18) + rect(36, 28, 28, 10, "metal2") +
                 rect(68, 28, 14, 18) + poly([(44, 44), (52, 44), (48, 38)]),
        "mill": rect(10, 6, 14, 50) + rect(10, 6, 46, 14) + rect(38, 20, 6, 18) + rect(28, 44, 60, 8) + rect(10, 56, 78, 6),
        "drill": rect(12, 6, 10, 52) + rect(12, 6, 40, 14) + rect(46, 20, 4, 24) + rect(30, 46, 40, 6) + rect(8, 56, 62, 6),
        "jig": rect(10, 6, 14, 50) + rect(10, 6, 46, 14) + circ(66, 14, 8) + rect(38, 20, 6, 18) + rect(24, 44, 64, 8) +
               line(56, 48, 56, 52, "ln2") + line(72, 48, 72, 52, "ln2") + rect(10, 56, 78, 6),
        "grinder": circ(48, 24, 14) + circ(48, 24, 3, "ln") + rect(40, 6, 16, 6) + rect(12, 44, 72, 8) + rect(8, 52, 80, 8),
        "edm": rect(10, 6, 76, 8) + rect(10, 48, 76, 8) + line(48, 14, 48, 48, "hid") + rect(30, 30, 36, 12, "metal2") +
               rect(6, 56, 84, 6),
        "guillotine": rect(8, 44, 80, 10) + rect(14, 40, 68, 4, "metal2") + poly([(14, 10), (82, 24), (82, 30), (14, 16)]) +
                      rect(8, 6, 8, 40),
        "brake": poly([(28, 6), (68, 6), (54, 30), (42, 30)]) + poly([(20, 46), (76, 46), (76, 58), (20, 58)]) +
                 poly([(40, 46), (48, 38), (56, 46)], "hid-fill"),
        "furnace": rect(10, 14, 76, 44, "body", 6) + rect(22, 26, 30, 22, "hid-fill") + circ(70, 30, 5) + circ(70, 46, 5) +
                   path("M18,14 v-8 h60 v8", "ln"),
    }[kind]
    return f'<svg viewBox="0 0 96 64" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">{g}</svg>'


def press_type_icon(kind: str) -> str:
    if kind == "crank_open":
        body = (path("M14,86 L14,12 L66,12 L66,30 L32,30 L32,58 L74,58 L74,86 Z") + rect(46, 30, 16, 12))
    elif kind == "crank_closed":
        body = (rect(10, 10, 70, 18) + rect(10, 28, 12, 58) + rect(68, 28, 12, 58) + rect(22, 60, 46, 26) +
                rect(30, 28, 30, 12))
    elif kind == "hydraulic":
        body = (rect(10, 10, 70, 14) + rect(34, 2, 22, 32, "body", 3) + rect(10, 24, 10, 62) + rect(70, 24, 10, 62) +
                rect(26, 34, 38, 10) + rect(20, 66, 50, 20))
    else:
        body = rect(14, 14, 62, 72, "ghost", 6) + text(45, 58, "?", "lbl", "middle")
    return f'<svg viewBox="0 0 90 92" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">{body}</svg>'


FIGURES = {
    "press": (press_side, "Пресс сбоку"),
    "plate": (nameplate, "Шильдик"),
    "table": (table_top, "Стол сверху"),
    "ram": (ram_bottom, "Ползун снизу"),
    "caliper": (caliper, "Штангенциркуль"),
    "vernier": (vernier, "Как читать штангенциркуль"),
    "radius": (bend_radius, "Радиус гиба"),
    "die": (die_section, "Штамп в разрезе"),
}
