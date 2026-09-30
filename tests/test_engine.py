"""Проверки расчётного ядра. Запуск: python -m pytest -q

Числа в тестах посчитаны вручную — если тест упал, значит изменилась формула
или норма, и это надо осознанно подтвердить."""
import copy
import json
import math
from pathlib import Path

import pytest

from stamp_engine.calc import (air_bend_force_kn, bend_allowance_mm, blank_size,
                               cutting_force, pierce_size)
from stamp_engine.geometry import Contour, Segment
from stamp_engine.loader import load_part
from stamp_engine.models import Part, Press, Shop
from stamp_engine.norms import Norms
from stamp_engine.planner import Planner
from stamp_engine.press import check_die_on_press
from stamp_engine.report import build_report

ROOT = Path(__file__).resolve().parent.parent
NORMS = Norms.load()


def load(name):
    return json.loads((ROOT / "examples" / name).read_text(encoding="utf-8"))


# --- формулы ------------------------------------------------------------
def test_bend_allowance_90deg():
    # BA = π/2 · (3 + 0,32·3) = 6,2204 мм
    assert bend_allowance_mm(90, 3.0, 3.0, 0.32) == pytest.approx(6.2204, abs=1e-3)


def test_neutral_layer_table():
    assert NORMS.x_for(1.0) == pytest.approx(0.32)
    assert NORMS.x_for(0.9) == pytest.approx(0.31)      # между 0,8→0,30 и 1,0→0,32
    assert NORMS.x_for(0.01) == pytest.approx(0.21)     # ниже таблицы — крайнее значение
    assert NORMS.x_for(50) == pytest.approx(0.50)


def test_cutting_force_round_hole():
    # Ø10, S=1, σв=400: L=31,416; τ=320; P=1,2·31,416·1·320 = 12,064 кН
    cf = cutting_force(math.pi * 10, 1.0, 400, NORMS)
    assert cf.p_cut_kn == pytest.approx(12.064, abs=1e-3)
    assert cf.n_in_land == 4                             # поясок 4 мм / S 1 мм
    assert cf.total_kn == pytest.approx(12.064 * (1 + 0.05 + 0.05 * 4), abs=1e-3)


def test_air_bend_matches_press_brake_charts():
    # 3 мм, 1 м, σв 450, V=24: 224 кН ≈ 22,9 т/м — как в таблицах листогибов
    assert air_bend_force_kn(1000, 3.0, 450, NORMS) == pytest.approx(224.44, abs=0.1)


def test_tool_sizes():
    p = pierce_size(12.0, 0.18, 0.21)                   # отверстие: размер задаёт пуансон
    assert (p.punch, p.die) == pytest.approx((12.18, 12.60))
    b = blank_size(100.0, 0.35, 0.21)                   # контур: размер задаёт матрица
    assert (b.die, b.punch) == pytest.approx((99.65, 99.23))


# --- геометрия ----------------------------------------------------------
def test_arc_bulge_center():
    s = Segment(36.23, 110.524, 31.23, 115.524, -0.414214)
    cx, cy, r, _, theta = s.arc()
    assert (cx, cy, r) == pytest.approx((36.23, 115.524, 5.0), abs=1e-3)
    assert theta == pytest.approx(-math.pi / 2, abs=1e-4)


def test_gem0004_perimeter():
    # ручной расчёт по rev.E: 477,83 мм
    # развёртка из общей модели; периметр меньше прежних 477,83 на 2×0,5 мм (исправлена ступенька)
    c = load_part(load("gem0004.json"), NORMS).contour
    assert c.perimeter() == pytest.approx(476.9, abs=0.2)
    assert not c.is_rectangle()


# --- пресс: нет данных ≠ подходит ----------------------------------------
def test_unknown_press_is_never_ok():
    pr = Press.from_dict({"id": "X", "name": "без данных"})
    pc = check_die_on_press(100.0, (300, 200), pr, NORMS)
    assert pc.force_status == "unknown"
    assert pc.status != "ok"


def test_press_force_fail():
    pr = Press.from_dict({"id": "P63", "force_t": {"value": 63, "source": "nameplate"}})
    pc = check_die_on_press(88 * 9.80665, None, pr, NORMS)
    assert pc.force_status == "fail"


# --- планировщик на GEM0004 ---------------------------------------------
@pytest.fixture
def planner():
    return Planner(load_part(load("gem0004.json"), NORMS),
                   Shop.from_dict(load("shop_example.json")), NORMS)


def test_bend_groups(planner):
    assert [g.kind for g in planner.groups] == ["Z", "U", "L"]


def test_hole_near_joggle_pierced_after(planner):
    assert planner.hole_after == {"H2": ["J.2"]}


def test_recommends_guillotine_scheme(planner):
    schemes = planner.plan()
    best = planner.recommend(schemes)
    assert best.key == "B"
    assert not next(s for s in schemes if s.key == "C").suitable


def test_draft_banner_until_approved(planner):
    schemes = planner.plan()
    assert "ЧЕРНОВИК" in build_report(planner, schemes, planner.recommend(schemes))


def test_no_banner_when_everything_confirmed():
    data = copy.deepcopy(NORMS.data)
    data["meta"]["status"] = "approved"
    part = load("gem0004.json")
    part["blank_status"] = "confirmed"
    pl = Planner(load_part(part, Norms(data)), Shop.from_dict(load("shop_example.json")), Norms(data))
    schemes = pl.plan()
    assert "ЧЕРНОВИК" not in build_report(pl, schemes, pl.recommend(schemes))


