"""T2.1: year-by-year hindcast table in out/<zone>.json and hindcast.md generated from it."""
import os
import sys

import pandas as pd
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config  # noqa: E402
import engine  # noqa: E402
import hindcast_md  # noqa: E402
from test_checks import HERE, ZONES, load  # noqa: E402

YEARS = list(range(2001, 2026))
ROW_KEYS = {"year", "strategy", "crops", "documented", "result", "source"}


def _synthetic(years):
    crops = {"maize": {"wrsi": 70.0, "class": "partial"}}
    hcdf = pd.DataFrame([{"year": y, "strategy": "C", "complete": True, "score": 0.5, "crops": crops}
                         for y in years])
    pm = pd.DataFrame({"year": years, "wrsi": [float(i) for i in range(len(years))], "class": "failure"})
    pm["rank_driest"] = pm["wrsi"].rank(method="min").astype(int)
    validation = {"by_year": [{"year": y, "pick": "C", "canicula_class": "short",
                               "score_pick": 0.5, "score_A": 1.0} for y in years]}
    return validation, hcdf, pm


def test_hit_fallo_only_for_cited_years(monkeypatch):
    monkeypatch.setattr(config, "VALIDATION_DROUGHT_YEARS", {2001: "cita a", 2003: "cita b"})
    validation, hcdf, pm = _synthetic([2001, 2002, 2003])
    rows = engine.hindcast_years(validation, hcdf, pm, worst_third=1, years=[2001, 2002, 2003])
    by = {r["year"]: r for r in rows}
    assert by[2001]["result"] == "hit" and by[2001]["source"] == "cita a"
    assert by[2003]["result"] == "fallo" and by[2003]["documented"]
    assert by[2002]["result"] is None and by[2002]["source"] is None and not by[2002]["documented"]
    assert by[2001]["crops"]["maize"] == {"wrsi": 70.0, "class": "partial"}


def test_missing_year_still_gets_a_row(monkeypatch):
    monkeypatch.setattr(config, "VALIDATION_DROUGHT_YEARS", {2002: "cita"})
    validation, hcdf, pm = _synthetic([2001])
    rows = engine.hindcast_years(validation, hcdf, pm, worst_third=1, years=[2001, 2002])
    assert [r["year"] for r in rows] == [2001, 2002]
    assert rows[1]["strategy"] is None and rows[1]["crops"] == {} and rows[1]["result"] == "fallo"


@pytest.mark.parametrize("z", ZONES)
def test_hindcast_years_table(z):
    rows = load(z)["hindcast"]["years"]
    assert [r["year"] for r in rows] == YEARS
    for r in rows:
        assert ROW_KEYS <= set(r)
        cited = config.VALIDATION_DROUGHT_YEARS.get(r["year"])
        assert r["documented"] == (cited is not None)
        assert r["source"] == cited
        assert (r["result"] in ("hit", "fallo")) if cited else r["result"] is None
        for c in r["crops"].values():
            assert c["class"] in ("good", "partial", "failure") and 0 <= c["wrsi"] <= 100


def test_hindcast_md_is_generated_from_json():
    zones = hindcast_md.load_zones()
    if not zones:
        pytest.skip("run engine.py first")
    with open(os.path.join(HERE, "hindcast.md"), encoding="utf-8") as f:
        assert f.read() == hindcast_md.render(zones), "hindcast.md is stale: run hindcast_md.py"
