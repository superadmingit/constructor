"""Проверка: встанет ли штамп на пресс.

Нет данных о прессе — статус «нет данных», а не «подходит»."""
from __future__ import annotations

from dataclasses import dataclass, field

from .models import KN_PER_TONNE, Press
from .norms import Norms


@dataclass
class PressCheck:
    press_id: str
    press_name: str
    status: str                  # ok | fail | unknown — итог по всем проверкам
    lines: list = field(default_factory=list)   # (уровень, текст)
    force_status: str = "unknown"  # итог только по усилию


def _worst(levels):
    if "fail" in levels:
        return "fail"
    if "unknown" in levels:
        return "unknown"
    return "ok"


def check_die_on_press(required_kn: float, footprint, press: Press, norms: Norms,
                       die_height_mm: float | None = None, needs_coil_feed: bool = False) -> PressCheck:
    lines = []
    margin = norms.get("press.force_margin")

    # 1. Усилие
    if not press.force_kn.known:
        lines.append(("unknown", "Номинальное усилие пресса неизвестно"))
    else:
        allowed = press.force_kn.value * margin
        need_t, allow_t = required_kn / KN_PER_TONNE, allowed / KN_PER_TONNE
        if required_kn <= allowed:
            lines.append(("ok", f"Усилие: нужно {need_t:.1f} т, можно {allow_t:.1f} т "
                                f"({margin:.0%} от {press.force_t:.0f} т)"))
        else:
            lines.append(("fail", f"Усилие: нужно {need_t:.1f} т, а можно только {allow_t:.1f} т "
                                  f"({margin:.0%} от {press.force_t:.0f} т)"))

    # 2. Стол
    if footprint is None:
        lines.append(("unknown", "Размер штампа ещё не известен"))
    elif not (press.table_lr_mm.known and press.table_fb_mm.known):
        lines.append(("unknown", f"Размер стола неизвестен (штамп ≈ {footprint[0]:.0f}×{footprint[1]:.0f} мм, оценка)"))
    else:
        m = norms.get("press.table_clamp_margin_mm")
        t_lr, t_fb = press.table_lr_mm.value, press.table_fb_mm.value
        fits = any(a + 2 * m <= t_lr and b <= t_fb
                   for a, b in (footprint, (footprint[1], footprint[0])))
        lines.append(("ok" if fits else "fail",
                      f"Стол {t_lr:.0f}×{t_fb:.0f} мм, штамп ≈ {footprint[0]:.0f}×{footprint[1]:.0f} мм "
                      f"+ по {m:.0f} мм под прихваты (оценка)"))

    # 3. Закрытая высота
    if die_height_mm is None:
        lines.append(("unknown", "Закрытая высота штампа появится на этапе проекта штампа"))
    elif not (press.shut_height_max_mm.known and press.shut_adjust_mm.known):
        lines.append(("unknown", "Закрытая высота пресса неизвестна"))
    else:
        hmax = press.shut_height_max_mm.value
        hmin = hmax - press.shut_adjust_mm.value
        g = norms.get("press.shut_height_margin_mm")
        ok = hmin + g <= die_height_mm <= hmax - g
        lines.append(("ok" if ok else "fail",
                      f"Закрытая высота: штамп {die_height_mm:.0f} мм, пресс {hmin:.0f}–{hmax:.0f} мм"))

    # 4. Подача из рулона для прогрессивного штампа
    if needs_coil_feed:
        if not press.feed:
            lines.append(("unknown", "Неизвестно, есть ли подача полосы/рулона"))
        elif not ({"coil", "roll"} & set(press.feed)):
            lines.append(("fail", "Нет валковой подачи или раскатки рулона"))
        else:
            lines.append(("ok", "Подача полосы есть"))

    return PressCheck(press.id, press.name, _worst([l[0] for l in lines]), lines, lines[0][0])
