"""Validity fixes: ties in CHECK 1 / D6, water demand by land share, bare days across the year
end, TARGET_YEAR out of validation, absolute OUT_DIR, no --demo, simulate_crop and the
leave-one-out. Synthetic data only, except the tests marked as reading out/<zone>.json.
"""
import os
import subprocess
import sys

import numpy as np
import pandas as pd
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import config  # noqa: E402
import engine  # noqa: E402
import hindcast as hc  # noqa: E402
from test_checks import ZONES, load  # noqa: E402

MAIZE = {"stages_days": [20, 30, 30, 20], "kc": {"ini": 0.3, "mid": 1.2, "end": 0.6},
         "heat_stress_tmax_c": 35}
BEAN = {"stages_days": [15, 20, 20, 15], "kc": {"ini": 0.4, "mid": 1.15, "end": 0.35},
        "heat_stress_tmax_c": 32, "excess_rain_late_mm": 150}


def daily(p, start="2010-01-01", days=400, et0=5.0):
    idx = pd.date_range(start, periods=days)
    p = np.full(days, p, dtype=float) if np.isscalar(p) else np.asarray(p, dtype=float)
    return pd.DataFrame({"P": p, "ET0": et0, "Tmax": 30.0, "Tmin": 20.0}, index=idx)


# ---------------------------------------------------------------- simulate_crop
def test_simulate_crop_wet_season_is_good():
    r = hc.simulate_crop(daily(20.0), pd.Timestamp("2010-03-01"), MAIZE, 100)
    assert r["wrsi"] == 100.0 and r["wrsi_flowering"] == 100.0 and r["class"] == "good"
    assert r["water_demand_mm"] == pytest.approx(5.0 * hc.kc_curve(MAIZE).sum(), abs=0.1)
    assert r["harvest"] == "2010-06-08"  # 100-day cycle, planting day included


def test_simulate_crop_dry_season_fails():
    r = hc.simulate_crop(daily(0.0), pd.Timestamp("2010-03-01"), MAIZE, 100)
    assert r["wrsi"] < 60 and r["class"] == "failure" and r["rain_in_cycle_mm"] == 0.0


def test_simulate_crop_incomplete_season_is_none():
    df = daily(5.0, days=60)
    assert hc.simulate_crop(df, pd.Timestamp("2010-01-01"), MAIZE, 100) is None
    df = daily(5.0)
    df.iloc[30, df.columns.get_loc("P")] = np.nan
    assert hc.simulate_crop(df, pd.Timestamp("2010-01-01"), MAIZE, 100) is None


def test_simulate_crop_bean_excess_rain_rule():
    with_rule = hc.simulate_crop(daily(20.0), pd.Timestamp("2010-03-01"), BEAN, 100)
    no_rule = hc.simulate_crop(daily(20.0), pd.Timestamp("2010-03-01"),
                               {k: v for k, v in BEAN.items() if k != "excess_rain_late_mm"}, 100)
    assert with_rule["wrsi"] == no_rule["wrsi"] == 100.0
    assert with_rule["excess_rain"] and with_rule["class"] == "partial"
    assert not no_rule["excess_rain"] and no_rule["class"] == "good"


def test_simulate_crop_flowering_stress_downgrades():
    p = np.zeros(400)
    p[:110] = 20.0  # wet until ~20 days before flowering, then dry
    r = hc.simulate_crop(daily(p), pd.Timestamp("2010-03-01"), MAIZE, 100)
    assert r["wrsi_flowering"] < 60
    assert r["class"] == hc._downgrade(hc._classify(r["wrsi"]))
    assert 0 <= r["wrsi"] <= 100


# ---------------------------------------------------------------- ties (CHECK 1, D6)
def _primera_inputs(wet_years, dry_year):
    years = list(wet_years) + [dry_year]
    idx = pd.date_range(f"{min(years)}-01-01", f"{max(years)}-12-31")
    p = np.full(len(idx), 20.0)
    p[idx.year == dry_year] = 0.0
    df = pd.DataFrame({"P": p, "ET0": 5.0, "Tmax": 30.0, "Tmin": 20.0}, index=idx)
    ind = pd.DataFrame({"primera_onset": [pd.Timestamp(f"{y}-05-15") for y in sorted(years)]},
                       index=sorted(years))
    return df, ind


def test_primera_ties_rank_last_not_first():
    df, ind = _primera_inputs(range(2001, 2009), 2009)
    pm = hc.primera_maize_check(df, ind, {"crops": {"maize": MAIZE}}, 100).set_index("year")
    assert pm.loc[2009, "rank_driest"] == 1
    # Eight years tie at WRSI 100: with method="min" they all got rank 2 and fell in the
    # "worst third". They must share the highest rank instead.
    assert (pm.drop(2009)["wrsi"] == 100.0).all()
    assert (pm.drop(2009)["rank_driest"] == len(pm)).all()


def _hy_inputs(years, rank):
    crops = {"maize": {"wrsi": 100.0, "class": "good"}}
    hcdf = pd.DataFrame([{"year": y, "strategy": "C", "complete": True, "score": 1.0, "crops": crops}
                         for y in years])
    pm = pd.DataFrame({"year": years, "wrsi": 100.0, "class": "good", "rank_driest": rank})
    return {"by_year": []}, hcdf, pm


def test_d6_not_evaluable_when_not_discriminative(monkeypatch):
    monkeypatch.setattr(config, "VALIDATION_DROUGHT_YEARS", {2001: "cita"})
    validation, hcdf, pm = _hy_inputs([2001, 2002, 2003], 1)
    rows = engine.hindcast_years(validation, hcdf, pm, 1, [2001, 2002, 2003], evaluable=False)
    by = {r["year"]: r for r in rows}
    assert by[2001]["result"] == "no_evaluable" and by[2001]["documented"]
    assert by[2002]["result"] is None


def test_d6_still_hit_when_evaluable(monkeypatch):
    monkeypatch.setattr(config, "VALIDATION_DROUGHT_YEARS", {2001: "cita"})
    validation, hcdf, pm = _hy_inputs([2001, 2002, 2003], 1)
    rows = engine.hindcast_years(validation, hcdf, pm, 1, [2001, 2002, 2003], evaluable=True)
    assert rows[0]["result"] == "hit"


# ---------------------------------------------------------------- water demand, bare days
def test_mean_water_demand_weighted_by_land_share():
    parts = {"sorghum": {"water_demand_mm": 400.0}, "bean": {"water_demand_mm": 200.0}}
    hcdf = pd.DataFrame([{"year": 2001, "strategy": "B", "complete": True, "score": 1.0, "crops": parts},
                         {"year": 2001, "strategy": "C", "complete": True, "score": 1.0,
                          "crops": {"maize": {"water_demand_mm": 300.0}}}])
    wd = engine.mean_water_demand(hcdf, [2001])
    assert wd["B"] == pytest.approx(0.6 * 400 + 0.4 * 200)
    assert wd["C"] == pytest.approx(300.0)


def test_bare_days_wraps_past_year_end():
    # 100 days from DOY 300: 66 days in this year, 34 in January (the rotation repeats yearly).
    assert engine.bare_days([{"start": 300, "end": 400}]) == 365 - 100
    # Overlapping segments are not double counted.
    assert engine.bare_days([{"start": 100, "end": 200}, {"start": 150, "end": 250}]) == 365 - 150
    assert engine.bare_days([{"start": 1, "end": 500}]) == 0


# ---------------------------------------------------------------- leave-one-out, TARGET_YEAR
def _loo_inputs(years, scores):
    """scores: {year: {strategy: score}}; canicula_days 10 for every year -> one tercile."""
    rows = [{"year": y, "strategy": k, "complete": True, "score": s, "crops": {}}
            for y in years for k, s in scores[y].items()]
    indic = pd.DataFrame({"canicula_days": [10] * len(years)}, index=years)
    return pd.DataFrame(rows), indic


def test_validate_excludes_target_year():
    t = config.TARGET_YEAR
    years = list(range(t - 5, t + 1))
    hcdf, indic = _loo_inputs(years, {y: {"A": 0.5, "C": 1.0} for y in years})
    v = engine.validate(hcdf, indic, years)
    assert t not in [r["year"] for r in v["by_year"]]
    assert v["n_years"] == 5


def test_loo_pick_ignores_the_evaluated_year():
    years = list(range(2001, 2008))
    scores = {y: {"A": 0.5, "C": 1.0} for y in years}
    base = engine.validate(*_loo_inputs(years, scores), years)
    scores[2004] = {"A": 1.0, "C": 0.0}  # only the evaluated year changes
    v = engine.validate(*_loo_inputs(years, scores), years)
    r = {x["year"]: x for x in v["by_year"]}[2004]
    assert r["pick"] == {x["year"]: x for x in base["by_year"]}[2004]["pick"] == "C"
    assert r["score_pick"] == 0.0 and r["score_A"] == 1.0


def test_loo_analogs_never_include_the_year():
    indic = pd.DataFrame({"canicula_days": [3, 5, 10, 12, 20, 25]}, index=range(2001, 2007))
    for y in indic.index:
        _, analogs = hc.analog_years(y, indic, list(indic.index))
        assert y not in analogs


def test_validate_tie_keeps_current_practice_and_is_flagged():
    years = list(range(2001, 2006))
    hcdf, indic = _loo_inputs(years, {y: {"A": 1.0, "B": 1.0, "C": 1.0} for y in years})
    v = engine.validate(hcdf, indic, years)
    assert all(r["pick"] == "A" and r["pick_tied"] for r in v["by_year"])
    assert v["n_years_pick_tied"] == len(years)


def test_validate_reports_margin_and_sign_test():
    years = list(range(2001, 2011))
    hcdf, indic = _loo_inputs(years, {y: {"A": 0.5, "C": 1.0} for y in years})
    v = engine.validate(hcdf, indic, years)
    assert v["mean_margin_vs_current"] == pytest.approx(0.5)
    assert v["sign_test_p"] == pytest.approx(2 * 0.5 ** 10, abs=1e-4)


# ---------------------------------------------------------------- sensitivity
def test_parameter_sensitivity_block():
    from test_sources import synthetic
    crops = hc.load_crops()
    out = engine.parameter_sensitivity(synthetic(), crops, 130)
    assert set(out["runs"]) == {"whc_60", "whc_90", "whc_130", "no_bean_excess_rule"}
    assert out["baseline"] == {"whc_mm": 130, "bean_excess_rain_late_mm": 150}
    assert out["runs"]["whc_130"]["n_pick_changes"] == 0  # same as the baseline
    for r in out["runs"].values():
        assert r["n_pick_changes"] == len(r["pick_changes"])
        assert all(c["year"] < config.TARGET_YEAR for c in r["pick_changes"])
    assert crops["crops"]["bean"]["excess_rain_late_mm"] == 150  # input not mutated


# ---------------------------------------------------------------- paths, CLI
def test_out_dir_is_absolute_next_to_engine():
    assert os.path.isabs(engine.OUT_DIR)
    assert engine.OUT_DIR == os.path.join(ROOT, "out")


def test_build_page_has_no_demo_flag():
    r = subprocess.run([sys.executable, os.path.join(ROOT, "build_page.py"), "--help"],
                       capture_output=True, text=True, cwd=ROOT)
    assert r.returncode == 0 and "--demo" not in r.stdout


def test_no_traffic_light_without_validated_base():
    assert not hasattr(engine, "traffic_light")


# ---------------------------------------------------------------- output (needs engine.py run)
@pytest.mark.parametrize("z", ZONES)
def test_output_excludes_target_year_and_light(z):
    d = load(z)
    t = config.TARGET_YEAR
    assert "traffic_light" not in d["current"]
    assert all(y["year"] < t for y in d["primera_check"]["years"])
    assert d["skill"]["n_years"] == len(d["skill"]["years"]) and max(d["skill"]["years"]) < t
    assert all(r["year"] < t for r in d["validation"]["by_year"])
    assert "sensitivity" in d and set(d["sensitivity"]["runs"]) >= {"whc_60", "whc_90", "whc_130",
                                                                    "no_bean_excess_rule"}
    pc = d["primera_check"]
    for r in d["hindcast"]["years"]:
        if r["documented"] and not pc["discriminative"]:
            assert r["result"] == "no_evaluable"
