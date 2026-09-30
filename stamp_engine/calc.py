"""Инженерные формулы. Каждая функция — одна формула из справочной практики.

Единицы: длины в мм, напряжения в МПа (= Н/мм²), усилия в кН.
Коэффициенты — только из Norms (shop_norms.yaml), здесь их нет.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from .norms import Norms


# =====================================================================
#  РЕЗКА (вырубка, пробивка, обрубка)
# =====================================================================
@dataclass
class CutForce:
    cut_length_mm: float
    tau_mpa: float
    p_cut_kn: float       # усилие среза с коэффициентом запаса
    p_strip_kn: float     # съём металла с пуансона
    p_push_kn: float      # проталкивание через поясок матрицы
    n_in_land: int        # сколько отходов одновременно сидит в пояске

    @property
    def total_kn(self) -> float:
        return self.p_cut_kn + self.p_strip_kn + self.p_push_kn


def land_height_mm(s: float, norms: Norms) -> float:
    """Высота прямого пояска матрицы: не меньше минимума и не меньше k·S."""
    return max(norms.get("cutting.land_height_min_mm"), norms.get("cutting.land_height_over_s") * s)


def cutting_force(cut_length_mm: float, s: float, sigma_b: float, norms: Norms) -> CutForce:
    """P = k · L · S · τ,  τ = (0,7…0,85)·σв.

    Плюс съём (k_strip·P) и проталкивание (k_push·P на каждый отход в пояске)."""
    tau = norms.get("cutting.tau_over_sigma_b") * sigma_b
    p_cut = norms.get("cutting.k_force") * cut_length_mm * s * tau / 1000.0
    n = max(1, math.ceil(land_height_mm(s, norms) / s - 1e-9))
    return CutForce(
        cut_length_mm=cut_length_mm, tau_mpa=tau, p_cut_kn=p_cut,
        p_strip_kn=norms.get("cutting.k_strip") * p_cut,
        p_push_kn=norms.get("cutting.k_push") * p_cut * n,
        n_in_land=n,
    )


def punch_stress_mpa(perimeter_mm: float, area_mm2: float, s: float, sigma_b: float,
                     norms: Norms) -> float:
    """Напряжение сжатия в пуансоне: σ = P / A.

    Для круглого пуансона σ = 4·k·S·τ / d — чем тоньше пуансон, тем больше σ."""
    tau = norms.get("cutting.tau_over_sigma_b") * sigma_b
    p = norms.get("cutting.k_force") * perimeter_mm * s * tau
    return p / area_mm2


# =====================================================================
#  ГИБКА
# =====================================================================
def bend_allowance_mm(angle_deg: float, r_in: float, s: float, x: float) -> float:
    """Длина нейтрального слоя в зоне гиба: BA = φ · (r + x·S), φ в радианах.

    На развёртке зона гиба — полоса шириной BA между двумя касательными линиями."""
    return math.radians(angle_deg) * (r_in + x * s)


def air_bend_force_kn(length_mm: float, s: float, sigma_b: float, norms: Norms) -> float:
    """Свободная V-гибка: F = k · σв · L · S² / V,  V = (6…12)·S."""
    v = norms.get("bending.v_opening_over_s") * s
    return norms.get("bending.k_air") * sigma_b * length_mm * s * s / v / 1000.0


@dataclass
class BendForce:
    kind: str             # "L" одна полка, "U" две полки за ход, "Z" подсечка
    air_kn: float         # свободная гибка
    bottomed_kn: float    # с дожимом (калибровкой) — принимаем для штампа
    pad_kn: float         # прижим/выталкиватель

    @property
    def total_kn(self) -> float:
        return self.bottomed_kn + self.pad_kn


def die_bend_force(kind: str, lengths_mm: list, s: float, sigma_b: float, norms: Norms) -> BendForce:
    """Усилие гибки в штампе (с запасом): свободная гибка × коэффициент дожима + прижим.

    kind = "U": две полки за один ход (≈ вдвое больше, чем V той же длины);
    kind = "Z": подсечка — два встречных гиба, считаем как два гиба;
    kind = "L": одна полка."""
    if kind == "U":
        air = air_bend_force_kn(sum(lengths_mm) / len(lengths_mm), s, sigma_b, norms) * \
            norms.get("bending.u_factor")
    else:
        air = sum(air_bend_force_kn(l, s, sigma_b, norms) for l in lengths_mm)
    bottomed = air * norms.get("bending.bottoming_factor")
    return BendForce(kind, air, bottomed, bottomed * norms.get("bending.pad_factor"))


# =====================================================================
#  ЗАЗОР И ИСПОЛНИТЕЛЬНЫЕ РАЗМЕРЫ ПУАНСОНА И МАТРИЦЫ
# =====================================================================
def clearance_per_side_mm(s: float, clearance_pct: float) -> float:
    """Зазор на сторону z = (% от S) · S. Двусторонний зазор Z = 2z."""
    return s * clearance_pct / 100.0


@dataclass
class ToolSize:
    what: str             # "пробивка" | "вырубка"
    nominal: float
    punch: float
    die: float
    rule: str             # человеческое объяснение, откуда числа


def pierce_size(nominal: float, tol_plus: float, z: float) -> ToolSize:
    """ПРОБИВКА (отверстие): размер отверстия задаёт ПУАНСОН.

    Пуансон изнашивается и становится меньше, отверстие — тоже. Поэтому
    пуансон делаем по ВЕРХНЕЙ границе допуска отверстия, матрицу — больше
    на двусторонний зазор 2z."""
    punch = nominal + tol_plus
    return ToolSize("пробивка", nominal, punch, punch + 2 * z,
                    "пуансон = верхняя граница отверстия; матрица = пуансон + 2z")


def blank_size(nominal: float, tol_minus: float, z: float) -> ToolSize:
    """ВЫРУБКА (наружный контур): размер детали задаёт МАТРИЦА.

    Матрица изнашивается и становится больше, деталь — тоже. Поэтому
    матрицу делаем по НИЖНЕЙ границе размера детали, пуансон — меньше
    на двусторонний зазор 2z."""
    die = nominal - tol_minus
    return ToolSize("вырубка", nominal, die - 2 * z, die,
                    "матрица = нижняя граница детали; пуансон = матрица − 2z")
