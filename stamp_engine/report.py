"""Отчёт для человека (Markdown, по-русски)."""
from __future__ import annotations

import re

from .models import KN_PER_TONNE
from .planner import Planner

STATUS_RU = {"preliminary": "предварительная", "recalculated": "пересчитана по замерам, не подтверждена пробным гибом",
             "confirmed": "подтверждена", "unknown": "неизвестно"}

ICON = {"ok": "✓", "warn": "⚠", "error": "✗", "unknown": "?", "fail": "✗"}
LEVEL_RU = {"error": "Нельзя так делать", "warn": "Риск — решает конструктор",
            "unknown": "Нет данных (это не «ок»)", "ok": "В норме"}


def _t(kn):
    return "—" if kn is None else f"{kn / KN_PER_TONNE:.1f}"


def build_report(pl: Planner, schemes, best) -> str:
    p, n = pl.part, pl.norms
    out = []
    w = out.append
    w(f"# Технологический расчёт: {p.id} ({p.revision})")
    w("")
    banners = []
    if not n.approved:
        banners.append("нормы цеха не утверждены конструктором")
    if p.contour_status == "recalculated":
        banners.append("развёртка пересчитана по замерам, но не подтверждена пробным гибом")
    elif p.contour_status != "confirmed":
        banners.append("развёртка предварительная (есть открытые замеры)")
    if banners:
        w(f"> **ЧЕРНОВИК — НЕ ДЛЯ ИЗГОТОВЛЕНИЯ:** {'; '.join(banners)}.")
        w("")

    # 1. Исходные данные
    x0, y0, x1, y1 = p.contour.bbox()
    w("## 1. Исходные данные")
    w("")
    w("| Параметр | Значение | Источник |")
    w("|---|---|---|")
    w(f"| Материал | {p.material_grade.value or '—'} | {p.material_grade.src_ru()} |")
    sb = p.sigma_b_mpa
    w(f"| Предел прочности σв | {pl.sigma_b:.0f} МПа | "
      f"{sb.src_ru() if sb.known else 'по нормам цеха (верхняя граница)'} |")
    w(f"| Толщина S | {p.thickness.value} мм | {p.thickness.src_ru()} |")
    w(f"| Серия | {p.series.value if p.series.known else '—'} шт. {p.series.note} | {p.series.src_ru()} |")
    w(f"| Развёртка, габарит | {x1 - x0:.2f} × {y1 - y0:.2f} мм | "
      f"{STATUS_RU.get(p.contour_status, p.contour_status)} |")
    if p.bend_x.known:
        w(f"| Нейтральный слой x | {p.bend_x.value:g} | {p.bend_x.src_ru()} |")
    w(f"| Периметр развёртки | {p.contour.perimeter():.1f} мм | рассчитано |")
    w(f"| Зазор на сторону z | {pl.z:.3f} мм ({pl.mat['clearance_pct']}% от S) | по нормам цеха |")
    w("")

    # 2. Проверки
    w("## 2. Проверки детали")
    w("")
    for lvl in ("error", "warn", "unknown", "ok"):
        items = [f for f in pl.findings if f.level == lvl]
        if not items:
            continue
        w(f"**{ICON[lvl]} {LEVEL_RU[lvl]}** ({len(items)})")
        w("")
        for f in items:
            w(f"- {f.text}")
        w("")

    # 3. Схемы
    w("## 3. Схемы штамповки")
    w("")
    w("| Схема | Штампов | Самый тяжёлый штамп, т | Итог |")
    w("|---|---|---|---|")
    for s in schemes:
        heavy = max((d.total_kn for d in s.dies), default=None)
        mark = "подходит" if s.suitable else "не подходит"
        w(f"| {s.key}. {s.title} | {len(s.dies)} | {_t(heavy)} | {mark}{(' — ' + s.verdict) if s.verdict else ''} |")
    w("")
    for s in schemes:
        w(f"### Схема {s.key}. {s.title}")
        w("")
        if s.verdict:
            w(f"_{s.verdict}_")
            w("")
        for op in s.pre_ops:
            w(f"- Подготовка: {op}")
        if s.pre_ops:
            w("")
        for d in s.dies:
            fits = [pc.press_name for pc in d.press_checks if pc.force_status == "ok"]
            w(f"#### {d.name} — {_t(d.total_kn)} т")
            w("")
            w(f"{d.purpose}.")
            w("")
            w("| Составляющая | т |")
            w("|---|---|")
            for label, kn in d.force_lines:
                w(f"| {label} | {_t(kn)} |")
            w(f"| **Итого** | **{_t(d.total_kn)}** |")
            w("")
            if d.tool_sizes:
                w("| Элемент | Операция | Номинал | Пуансон | Матрица | Правило |")
                w("|---|---|---|---|---|---|")
                for ref, ts in d.tool_sizes:
                    w(f"| {ref} | {ts.what} | {ts.nominal:.2f} | {ts.punch:.3f} | {ts.die:.3f} | {ts.rule} |")
                w("")
            for note in d.notes:
                w(f"- {note}")
            w(f"- Проходит по усилию на прессах: {', '.join(fits) if fits else 'нет'}")
            w("")
            w("<details><summary>Проверка по каждому прессу</summary>")
            w("")
            for pc in d.press_checks:
                w(f"- **{pc.press_name}** — {ICON[pc.status]} "
                  f"{'подходит' if pc.status == 'ok' else ('не подходит' if pc.status == 'fail' else 'не подтверждено')}")
                for lvl, text in pc.lines:
                    w(f"  - {ICON[lvl]} {text}")
            w("")
            w("</details>")
            w("")

    # 4. Рекомендация
    w("## 4. Рекомендация программы")
    w("")
    if best is None:
        w("Ни одна схема не проходит. Нужны данные о прессах или другая технология.")
    else:
        w(f"**Схема {best.key}: {best.title}** — "
          + (f"{len(best.dies)} штампов, самый тяжёлый {_t(max(d.total_kn for d in best.dies))} т. " if best.dies
             else "штампы не нужны, достаточно гильотины. ")
          + "Выбрана как допустимая схема с наименьшим числом штампов и меньшим усилием.")
    w("")
    w("Порядок гибов — предложение по простым правилам (подсечки → две полки → одиночные). "
      "Его подтверждает конструктор.")
    w("")

    # 5. Вопросы
    w("## 5. Что нужно подтвердить")
    w("")
    if not n.approved:
        w("- Нормы цеха: лист согласования (≈30 минут, один раз для всех деталей).")
    for q in p.open_questions:
        w(f"- {q['text']} _(влияет на: {q.get('affects', '—')})_")
    w("")
    text = "\n".join(out)
    return re.sub(r"(?<=\d)\.(?=\d)", ",", text)   # десятичная запятая
