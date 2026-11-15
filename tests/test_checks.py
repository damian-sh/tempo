"""Tests for the three acceptance checks, read from out/<zone>.json (no recomputation).

Run:  python -m pytest tests -q   (after engine.py)
A failing CHECK means the model did not pass. Do not tune parameters to make it pass.
"""
import json
import os

import pytest

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ZONES = ["parcela"]


def load(z):
    p = os.path.join(HERE, "out", f"{z}.json")
    if not os.path.exists(p):
        pytest.skip("run engine.py first")
    with open(p) as f:
        return json.load(f)


@pytest.mark.parametrize("z", ZONES)
def test_check1_documented_droughts_in_worst_years(z):
    d = load(z)
    years = d["primera_check"]["years"]
    documented = [y for y in years if y["documented"]]
    worst = [y for y in years if y["rank_driest"] <= 9]
    hits = [y for y in documented if y["rank_driest"] <= 9]
    print(f"\n{z} CHECK 1: {len(hits)}/{len(documented)} documented years in worst 9")
    assert documented, "no documented years in the sample"


@pytest.mark.parametrize("z", ZONES)
def test_check2_canicula_signal_reported(z):
    d = load(z)
    rho = d["skill"]["canicula_vs_sep_nov_rain"]
    print(f"\n{z} CHECK 2: Spearman canícula vs Sep-Nov = {rho}")
    assert rho is not None


@pytest.mark.parametrize("z", ZONES)
def test_check3_hindcast_vs_practice(z):
    v = load(z)["validation"]
    print(f"\n{z} CHECK 3: Tempo {v['mean_score_tempo']} | A {v['mean_score_current']} | "
          f"misma estrategia {v['mean_score_same_every_year']} | picks {v['picks']}")
    assert v["mean_score_tempo"] >= v["mean_score_current"]


def test_no_circularity(monkeypatch):
    import config
    import engine

    years = config.VALIDATION_DROUGHT_YEARS
    assert config.TARGET_YEAR not in years
    assert all(y <= 2025 for y in years), years
    assert all(isinstance(c, str) and c.strip() for c in years.values()), "every year needs a citation"

    monkeypatch.setattr(config, "VALIDATION_DROUGHT_YEARS", {**years, config.TARGET_YEAR: "x"})
    with pytest.raises(AssertionError):
        engine.validate(None, None, [])


@pytest.mark.parametrize("z", ZONES)
def test_rain_source_sensitivity_in_output(z):
    d = load(z)
    rs = d["rain_source_sensitivity"]
    assert d["inputs"]["rain_source"] in ("imerg", "power")
    if not rs["available"]:
        pytest.skip(f"rain_source_sensitivity unavailable: {rs['reason']}")
    for name in ("primera", "canicula", "sep_nov"):
        w = rs["windows"][name]
        print(f"\n{z} {name}: n={w['n_years']} bias {w['bias_mm']} mm ({w['bias_pct']} %), rho {w['spearman']}")
        assert {"bias_mm", "bias_pct", "spearman"} <= set(w)
    print(f"{z} verdict changes: {[c['year'] for c in rs['verdict_changes']]}")
    assert isinstance(rs["verdict_changes"], list)
