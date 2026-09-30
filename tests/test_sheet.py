"""Общая модель листовой детали: развёртка, 3D, чертёж, шаблоны. Числа посчитаны вручную."""
import json
import math
from pathlib import Path

import pytest

from stamp_engine.loader import load_part
from stamp_engine.models import Shop
from stamp_engine.norms import Norms
from stamp_engine.planner import Planner
from stamp_engine.sheet import NotSupported, SheetError, joggle_numbers, unfold
from stamp_engine.sheet.families import FAMILIES, InputError, build, measurement_plan

ROOT = Path(__file__).resolve().parent.parent
NORMS = Norms.load()


def load(name):
    return json.loads((ROOT / "examples" / name).read_text(encoding="utf-8"))


def rect(w, l):
    return [[0, 0], [w, 0], [w, l], [0, l]]


def part(outline, flanges=(), **kw):
    d = {"thickness_mm": 2.0, "bend_radius_mm": 2.0, "k_factor": 0.4, "base": {"outline": outline}, "flanges": list(flanges)}
    d.update(kw)
    return d


def width(flat):
    b = flat.bbox()
    return b[2] - b[0], b[3] - b[1]


# --- развёртка: сверка с ручным расчётом -------------------------------------------
def test_angle_flat_length_by_hand():
    # уголок 40 × 30 наружные, S=2, r=2, x=0,4: BD = 2·4 − π/2·2,8 = 3,602 → 40 + 30 − 3,602
    f = unfold(part(rect(40, 100), [{"edge": 1, "angle": 90, "direction": "up", "height": 30}]), NORMS)
    assert width(f) == pytest.approx((66.398, 100.0), abs=1e-3)
    assert f.bends[0]["line"][0][0] == pytest.approx(40 - 4 + 4.398 / 2, abs=1e-3)      # середина зоны гиба


def test_channel_flat_length_by_hand():
    fl = [{"edge": 1, "angle": 90, "direction": "up", "height": 25}, {"edge": 3, "angle": 90, "direction": "up", "height": 25}]
    assert width(unfold(part(rect(60, 100), fl), NORMS))[0] == pytest.approx(60 + 25 + 25 - 2 * 3.602, abs=1e-3)


def test_orientation_does_not_matter():
    cw = [[0, 0], [0, 100], [40, 100], [40, 0]]                        # тот же уголок, обход по часовой
    f = unfold(part(cw, [{"edge": 2, "angle": 90, "direction": "up", "height": 30}]), NORMS)
    assert width(f)[0] == pytest.approx(66.398, abs=1e-3)


def test_neutral_layer_from_norms_when_not_given():
    d = part(rect(40, 100), [{"edge": 1, "angle": 90, "direction": "up", "height": 30}])
    del d["k_factor"]
    f = unfold(d, NORMS)                                                 # r/S = 1 → x = 0,32 по таблице
    assert f.bends[0]["x"] == pytest.approx(0.32)
    assert width(f)[0] == pytest.approx(40 + 30 - (8 - math.pi / 2 * (2 + 0.64)), abs=1e-3)


def test_partial_flange_leaves_steps():
    f = unfold(part(rect(40, 100), [{"edge": 1, "angle": 90, "direction": "up", "height": 30, "span": [20, 80]}]), NORMS)
    xs = sorted({round(p[0], 3) for p in f.contour})
    assert xs == [0.0, 40.0, 66.398]                                     # ступенька там, где полки нет
    assert len(f.contour) == 8


def test_joggle_matches_real_surfaces():
    """Ступенька: независимый расчёт по реальным поверхностям (дуги r и r+S), см. протокол проверки rev.E."""
    j = joggle_numbers(4.48, 45, 3.0, 3.0, 0.4)
    assert (j["s"], j["p"], j["f"], j["dl"]) == pytest.approx((2.6078, 8.2079, 9.2051, 0.9972), abs=2e-4)


def test_flange_holes_positions():
    f = unfold(load("skoba_u.json"), NORMS)
    x0 = f.bbox()[0]
    got = {h["id"]: (round(h["cx"] - x0, 3), round(h["cy"], 3)) for h in f.holes}
    # наружная длина полки 25, BD = 8 − π/2·(2 + 0,64) = 3,853; отверстие в 10 от края полки
    assert got == {"H1": (41.147, 30.0), "H2": (72.294, 30.0), "H3": (10.0, 30.0)}


# --- защита от ошибок описания ------------------------------------------------------
def test_box_corner_not_supported():
    fl = [{"edge": 0, "angle": 90, "direction": "up", "height": 20}, {"edge": 1, "angle": 90, "direction": "up", "height": 20}]
    with pytest.raises(NotSupported):
        unfold(part(rect(50, 50), fl), NORMS)


def test_flange_on_arc_not_supported():
    with pytest.raises(NotSupported):
        unfold(part([[0, 0, 0], [40, 0, 0.5], [40, 40, 0], [0, 40, 0]], [{"edge": 1, "angle": 90, "height": 20}]), NORMS)


def test_flange_touching_other_part_is_caught():
    lshape = [[0, 0], [60, 0], [60, 20], [20, 20], [20, 60], [0, 60]]
    with pytest.raises(SheetError):
        unfold(part(lshape, [{"edge": 2, "angle": 90, "direction": "up", "height": 50}]), NORMS)


def test_impossible_joggle_is_rejected():
    with pytest.raises(SheetError):
        joggle_numbers(1.0, 45, 3.0, 3.0, 0.4)


# --- GEM0004 как обычная деталь общей модели --------------------------------------
def test_gem0004_in_generic_model():
    f = unfold(load("gem0004.json"), NORMS)
    w, l = width(f)
    assert w == pytest.approx(99.99, abs=0.01)                          # как в rev.E
    assert l == pytest.approx(148.144, abs=0.01)                        # rev.E 148,641 минус исправление ступеньки 0,497
    assert len(f.contour) == 12                                          # «шипы» у уступа убраны
    h2 = next(h for h in f.holes if h["id"] == "H2")
    assert h2["cy"] == pytest.approx(116.342, abs=0.01)


# --- 3D и файлы -----------------------------------------------------------------------
cq = pytest.importorskip("cadquery")


@pytest.mark.parametrize("name,dims", [("skoba_u.json", (40, 60, 25)), ("gem0004.json", (94.55, 138.79, 15.41))])
def test_solid_matches_measured_part(name, dims):
    from stamp_engine.sheet.solid import build_solid
    spec = load(name)
    solid, _ = build_solid(spec, unfold(spec, NORMS))
    bb = solid.val().BoundingBox()
    assert solid.val().isValid()
    assert (bb.xlen, bb.ylen, bb.zlen) == pytest.approx(dims, abs=0.02)   # габариты = замеры образца


def test_files_are_written(tmp_path):
    import ezdxf
    from stamp_engine.sheet.outputs import write_drawing, write_flat_dxf
    from stamp_engine.sheet.solid import build_solid, export_step
    spec = load("skoba_u.json")
    flat = unfold(spec, NORMS)
    solid, _ = build_solid(spec, flat)
    write_flat_dxf(spec, flat, str(tmp_path / "f.dxf"))
    export_step(solid, str(tmp_path / "p.step"))
    write_drawing(spec, flat, solid, str(tmp_path / "d.pdf"))
    m = ezdxf.readfile(str(tmp_path / "f.dxf")).modelspace()
    assert [e for e in m.query("LWPOLYLINE") if e.dxf.layer == "CONTOUR"][0].closed
    assert (tmp_path / "p.step").stat().st_size > 1000 and (tmp_path / "d.pdf").stat().st_size > 5000


# --- шаблоны для рабочих ---------------------------------------------------------------
META = {"material": {"group": "soft_steel"}}


def test_material_is_required():
    with pytest.raises(InputError, match="материал"):
        build("plate", {"A": 80, "B": 50, "S": 3})

@pytest.mark.parametrize("fam,vals", [
    ("plate", {"A": 80, "B": 50, "S": 3}),
    ("angle", {"A": 100, "B": 40, "C": 30, "S": 2, "R": 2, "U": 90}),
    ("channel", {"A": 60, "B": 40, "C": 25, "S": 2, "R": None, "U": None}),
    ("zprofile", {"A": 100, "B": 50, "C": 20, "D": 25, "S": 2, "R": 2, "U": 90}),
])
def test_every_family_builds_to_the_end(fam, vals):
    from stamp_engine.sheet.solid import build_solid
    spec = build(fam, vals, holes=[{"face": "base", "kind": "round", "d": 8, "x": 20, "y": 25}], meta=dict(META, id=fam))
    flat = unfold(spec, NORMS)
    solid, _ = build_solid(spec, flat)
    assert solid.val().isValid()
    pl = Planner(load_part(spec, NORMS), Shop.from_dict(load("shop_example.json")), NORMS)
    assert pl.recommend(pl.plan()) is not None


def test_unknown_radius_is_marked_assumed():
    spec = build("channel", {"A": 60, "B": 40, "C": 25, "S": 2, "R": None, "U": None}, meta=META)
    assert spec["bend_radius_mm"] == {"value": 2.0, "source": "assumed"}
    assert spec["flanges"][0]["angle"]["source"] == "assumed"


def test_typo_is_caught_for_the_worker():
    with pytest.raises(InputError, match="B"):
        build("angle", {"A": 100, "B": 4000, "C": 30, "S": 2}, meta=META)


def test_channel_is_bent_in_one_die():
    spec = build("channel", {"A": 60, "B": 40, "C": 25, "S": 2, "R": 2, "U": 90}, meta=META)
    pl = Planner(load_part(spec, NORMS), Shop.from_dict(load("shop_example.json")), NORMS)
    assert [g.kind for g in pl.groups] == ["U"]


def test_measurement_plan_is_complete():
    for key, fam in FAMILIES.items():
        plan = measurement_plan(key)
        assert all(m["how"] and m["tool"] for m in plan)
        assert plan[0]["key"] == "A"


def test_flange_holes_measured_from_same_end():
    """Отверстия в левой и правой полке меряются от одного переднего торца."""
    holes = [{"face": "flange_1", "kind": "round", "d": 6, "s": 15, "e": 8},
             {"face": "flange_2", "kind": "round", "d": 6, "s": 15, "e": 8}]
    spec = build("channel", {"A": 60, "B": 40, "C": 25, "S": 2, "R": 2, "U": 90}, holes=holes, meta=META)
    ys = sorted(round(h["cy"], 3) for h in unfold(spec, NORMS).holes)
    assert ys == [15.0, 15.0]
