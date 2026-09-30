"""Печатает для конструктора два листа из norms/shop_norms.yaml:

  1) «Нормы цеха — лист согласования» (один раз, ≈30 минут);
  2) «Лист проверки штампа» (на каждый штамп, ≈10 минут).

Запуск:  python tools/make_norms_pdf.py  [выходной.pdf]
"""
from __future__ import annotations

import sys
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table,
                                TableStyle)

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from stamp_engine.norms import Norms  # noqa: E402

FONT_DIR = Path("/usr/share/fonts/truetype/dejavu")
pdfmetrics.registerFont(TTFont("DV", str(FONT_DIR / "DejaVuSans.ttf")))
pdfmetrics.registerFont(TTFont("DVB", str(FONT_DIR / "DejaVuSans-Bold.ttf")))

INK = colors.HexColor("#1C2430")
GREEN = colors.HexColor("#3F6E58")
YELLOW = colors.HexColor("#FFF3C4")
GRID = colors.HexColor("#9AA5A0")

H1 = ParagraphStyle("h1", fontName="DVB", fontSize=15, leading=19, textColor=INK, spaceAfter=3)
H2 = ParagraphStyle("h2", fontName="DVB", fontSize=10.5, leading=14, textColor=GREEN,
                    spaceBefore=6, spaceAfter=3)
P = ParagraphStyle("p", fontName="DV", fontSize=8.6, leading=11.5, textColor=INK, alignment=TA_LEFT)
SMALL = ParagraphStyle("s", parent=P, fontSize=7.6, leading=9.6)
CELL = ParagraphStyle("c", parent=P, fontSize=7.8, leading=9.8)
CELLB = ParagraphStyle("cb", parent=CELL, fontName="DVB")

# Нормы, которые сильнее всего влияют на результат — их конструктор смотрит первыми
MAIN = [
    ("materials.soft_steel.clearance_pct", "Зазор пуансон–матрица, мягкая сталь"),
    ("materials.soft_steel.sigma_b_mpa", "σв мягкой стали, если нет сертификата"),
    ("cutting.k_force", "Коэффициент запаса к усилию резки"),
    ("bending.x_table", "Нейтральный слой (K-фактор): таблица x по r/S"),
    ("geometry_rules.hole_bend_min_over_s", "От отверстия до начала гиба (иначе пробивать после гибки)"),
    ("geometry_rules.flange_straight_min_over_s", "Минимальный прямой участок полки"),
    ("bending.bottoming_factor", "Гибка с дожимом: во сколько раз больше свободной"),
    ("press.force_margin", "Предельная загрузка пресса"),
    ("tooling.heat_treat_required_series", "С какой серии рабочие детали только закалённые"),
    ("tooling.punch_compressive_allow_mpa", "Допустимое сжатие пуансона"),
]


def fmt(v):
    if isinstance(v, list):
        return "  ".join(f"{a:g}→{b:.2f}".replace(".", ",") for a, b in v)
    if isinstance(v, float):
        return f"{v:g}".replace(".", ",")
    return str(v)


def row(norms, key, title, n):
    it = norms.item(key)
    return [Paragraph(str(n), CELL), Paragraph(title, CELLB),
            Paragraph(f"{fmt(it['value'])} {it.get('unit', '')}", CELLB),
            Paragraph(str(it.get("typical", "")), CELL), Paragraph(it.get("why", ""), CELL),
            "", ""]


def norms_table(rows, widths):
    head = [Paragraph(h, CELLB) for h in ("№", "Норма", "Предлагаем", "Обычно", "Зачем", "✓", "Ваше значение")]
    t = Table([head] + rows, colWidths=widths, repeatRows=1)
    t.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.4, GRID),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E6ECE9")),
        ("BACKGROUND", (5, 1), (6, -1), YELLOW),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 1.6), ("BOTTOMPADDING", (0, 0), (-1, -1), 1.6),
    ]))
    return t


def build(out_path: Path):
    norms = Norms.load()
    doc = SimpleDocTemplate(str(out_path), pagesize=landscape(A4), leftMargin=12 * mm,
                            rightMargin=12 * mm, topMargin=10 * mm, bottomMargin=10 * mm,
                            title="Нормы цеха — лист согласования")
    W = landscape(A4)[0] - 24 * mm
    widths = [8 * mm, 62 * mm, 34 * mm, 26 * mm, W - 8 * mm - 62 * mm - 34 * mm - 26 * mm - 12 * mm - 38 * mm,
              12 * mm, 38 * mm]
    story = [
        Paragraph("Нормы цеха для расчёта штампов — лист согласования", H1),
        Paragraph("Один раз, около 30 минут. Программа считает все детали по этим числам: "
                  "усилия, зазоры, размеры пуансонов и матриц, выбор пресса. Пока лист не подписан, "
                  "каждый результат программы помечен «ЧЕРНОВИК — НЕ ДЛЯ ИЗГОТОВЛЕНИЯ».", P),
        Spacer(1, 2),
        Paragraph("Как заполнять: согласны — поставьте ✓. Не согласны — впишите своё значение. "
                  "Не уверены — оставьте пусто, спросим отдельно. Можно ответить голосовым: "
                  "«пункт 3 — ставим 1,3».", P),
        Paragraph("Часть 1. Главное — 10 пунктов (сильнее всего влияют на результат)", H2),
        norms_table([row(norms, k, t, i + 1) for i, (k, t) in enumerate(MAIN)], widths),
    ]

    # Часть 2: материалы — одной матрицей
    mats = norms.data["materials"]
    mhead = [Paragraph(h, CELLB) for h in ("Материал", "σв без сертификата, МПа",
                                            "Зазор, % S на сторону", "Мин. отверстие, × S",
                                            "Мин. радиус гиба, × S", "✓ / ваши правки")]
    mrows = [mhead]
    for g in mats.values():
        mrows.append([Paragraph(g["title"], CELLB)] +
                     [Paragraph(f"<b>{fmt(g[k]['value'])}</b>  <font size=6.5>(обычно {g[k]['typical']})</font>", CELL)
                      for k in ("sigma_b_mpa", "clearance_pct", "min_hole_d_over_s", "min_bend_r_over_s")] + [""])
    mt = Table(mrows, colWidths=[70 * mm, 38 * mm, 38 * mm, 34 * mm, 34 * mm, W - 214 * mm])
    mt.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.4, GRID),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E6ECE9")),
        ("BACKGROUND", (5, 1), (5, -1), YELLOW),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 2.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5),
    ]))

    # Часть 2: остальные нормы — по одной строке
    main_keys = {k for k, _ in MAIN}
    rows, n = [], len(MAIN)
    for section in ("cutting", "geometry_rules", "bending", "press", "tooling", "shop"):
        for key, it in norms.data[section].items():
            full = f"{section}.{key}"
            if full in main_keys:
                continue
            n += 1
            rows.append(row(norms, full, it.get("title", key), n))
    story += [PageBreak(),
              Paragraph("Часть 2. Остальное — достаточно пробежать глазами", H2),
              Paragraph("Материалы (у главного пункта 1 и 2 — мягкая сталь; здесь остальные значения)", SMALL),
              mt, Spacer(1, 5),
              norms_table(rows, widths),
              Spacer(1, 3),
              Paragraph("Нормы для прогрессивных штампов согласуем отдельно, когда дойдём до них.", SMALL),
              Spacer(1, 5),
              Paragraph("Нормы утвердил: ______________________   Дата: ____________   "
                        "Подпись: ______________", P)]

    # Лист проверки штампа
    story += [PageBreak(),
              Paragraph("Лист проверки штампа — около 10 минут на штамп", H1),
              Paragraph("Числа (усилия, зазоры, исполнительные размеры, пресс) программа уже проверила "
                        "по утверждённым нормам. От вас — только то, что видит опыт. Ответ можно "
                        "голосовым: номер пункта и что не так.", P),
              Spacer(1, 4),
              Paragraph("Деталь: ____________   Штамп №: ____   Схема: ____   Дата: ____________", P),
              Spacer(1, 4)]
    checks = [
        "Схема и порядок операций верные? Если нет — какой порядок.",
        "Базирование: заготовка встаёт в штамп однозначно (упоры, фиксаторы), перевернуть нельзя?",
        "Пуансоны и матрицы: исполнительные размеры и зазор — годятся?",
        "Материал и твёрдость рабочих деталей (марка стали, HRC) — годятся?",
        "Нет тонких мест: стенки матрицы, перемычки, крепёж, штифты?",
        "Съём и выталкивание: деталь и отход не застрянут, отход уходит в провал или в сторону?",
        "Гибка: есть чем подправить угол при приладке (дожим, регулировка, прокладки)?",
        "Штамп и пресс: закрытая высота, хвостовик, крепление к столу — сходятся?",
        "Безопасность: руки рабочего не заходят под ползун при подаче и съёме детали?",
        "Что бы вы изменили — своими словами.",
    ]
    t = Table([[Paragraph("№", CELLB), Paragraph("Вопрос", CELLB), Paragraph("✓ / ✗", CELLB),
                Paragraph("Комментарий", CELLB)]] +
              [[Paragraph(str(i + 1), CELL), Paragraph(q, CELL), "", ""] for i, q in enumerate(checks)],
              colWidths=[8 * mm, 120 * mm, 18 * mm, W - 146 * mm], rowHeights=[None] + [11.5 * mm] * 10)
    t.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.4, GRID),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E6ECE9")),
        ("BACKGROUND", (2, 1), (3, -1), YELLOW),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    story += [t, Spacer(1, 8),
              Paragraph("Решение:   ☐ можно изготавливать     ☐ доработать (что — в комментариях)     "
                        "☐ нужен разговор", CELLB),
              Spacer(1, 6),
              Paragraph("Проверил: ______________________   Подпись: ______________", P)]
    doc.build(story)


if __name__ == "__main__":
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "norms_approval.pdf"
    build(out)
    print(f"PDF: {out}")
