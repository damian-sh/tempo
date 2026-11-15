"""T2.2: POWER rain cache, --rain-source and rain_source_sensitivity. Synthetic data, no network."""
import json
import os
import sys

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config  # noqa: E402
import engine  # noqa: E402
import fetch  # noqa: E402
import hindcast as hc  # noqa: E402
import indicators as ind  # noqa: E402


def synthetic(years=range(2001, 2013), seed=0):
    idx = pd.date_range(f"{years[0]}-01-01", f"{years[-1]}-12-31")
    rng = np.random.default_rng(seed)
    wet = idx.month.isin([5, 6, 9, 10]) | ((idx.month == 7) & (idx.day < 10))
    p = np.where(wet & (rng.random(len(idx)) < 0.6), rng.gamma(2.0, 6.0, len(idx)), 0.0)
    df = pd.DataFrame({"P": p, "P_src": "IMERG", "Tmax": 30.0, "Tmin": 20.0, "ET0": 4.5}, index=idx)
    return df


def test_power_precip_json_roundtrip(tmp_path, monkeypatch):
    idx = pd.date_range("2001-01-01", periods=5)
    power = pd.DataFrame({"PRECTOTCORR": [0.0, 0.996, np.nan, 10.0, 2.5],
                          "T2M": 25.0, "T2M_MAX": 30.0, "T2M_MIN": 20.0, "RH2M": 80.0}, index=idx)
    js = fetch.power_precip_json(power)
    assert js["start"] == "2001-01-01" and js["end"] == "2001-01-05"
    assert js["values"] == [0.0, 0.996, None, 10.0, 2.5]
    assert "PRECTOTCORR" in fetch.POWER_PARAMS

    zone = tmp_path / "z"
    zone.mkdir()
    power.index.name = "date"
    power.assign(PRECTOTCORR=-1.0).to_csv(zone / "power.csv")  # JSON must win over the CSV
    (zone / "precip_power.json").write_text(json.dumps(js))
    pd.DataFrame({"imerg_mm": [5.0] * 5}, index=pd.Index(idx, name="date")).to_csv(zone / "imerg.csv")
    (zone / "meta.json").write_text(json.dumps({"zone": {"lat": 13.8}}))
    monkeypatch.setattr(config, "CACHE_DIR", str(tmp_path))

    df_p, info_p = ind.load_zone("z", "power")
    assert info_p["rain_source"] == "power" and (df_p["P_src"] == "POWER").all()
    assert df_p["P"].tolist()[:2] == [0.0, 0.996] and np.isnan(df_p["P"].iloc[2])
    df_i, info_i = ind.load_zone("z", "imerg")
    assert (df_i["P"] == 5.0).all() and info_i["share_days_imerg"] == 1.0
    with pytest.raises(ValueError):
        ind.load_zone("z", "chirps")

    t = os.path.getmtime(zone / "precip_power.json")
    os.utime(zone / "power.csv", (t + 10, t + 10))  # power.csv updated after the JSON -> JSON is stale
    df_s, _ = ind.load_zone("z", "power")
    assert (df_s["P"] == -1.0).all()


def test_cache_dir_outside_repo():
    repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    assert not os.path.abspath(config.CACHE_DIR).startswith(repo + os.sep)


def test_sensitivity_bias_and_spearman():
    crops = hc.load_crops()
    di = synthetic()
    dp = di.assign(P=di["P"] * 1.2, P_src="POWER")
    out = engine.rain_source_sensitivity(di, dp, crops, 130)
    assert out["available"]
    for name, w in out["windows"].items():
        assert w["n_years"] == 12, name
        assert w["bias_pct"] == pytest.approx(20.0, abs=0.1)
        assert w["bias_mm"] == pytest.approx(0.2 * w["mean_imerg_mm"], abs=0.2)
        assert w["spearman"] == 1.0
    assert out["n_years_compared"] > 0
    assert out["n_verdict_changes"] == len(out["verdict_changes"])


def test_sensitivity_same_source_no_verdict_change():
    crops = hc.load_crops()
    di = synthetic()
    out = engine.rain_source_sensitivity(di, di.assign(P_src="POWER"), crops, 130)
    assert out["verdict_changes"] == []
    assert all(w["bias_mm"] == 0 for w in out["windows"].values())


def test_sensitivity_detects_verdict_change(monkeypatch):
    crops = hc.load_crops()
    di = synthetic()
    dp = di.assign(P_src="POWER")
    fake = {
        "IMERG": {"picks": {"C": 3}, "mean_score_tempo": 1.0, "by_year": [
            {"year": 2001, "pick": "C", "score_pick": 1.0}, {"year": 2002, "pick": "C", "score_pick": 1.0},
            {"year": 2003, "pick": "C", "score_pick": 0.5}]},
        "POWER": {"picks": {"C": 2, "A": 1}, "mean_score_tempo": 0.9, "by_year": [
            {"year": 2001, "pick": "C", "score_pick": 1.0}, {"year": 2002, "pick": "A", "score_pick": 0.5},
            {"year": 2004, "pick": "A", "score_pick": 1.0}]},
    }
    monkeypatch.setattr(engine, "_hindcast_picks", lambda df, c, w: fake[df["P_src"].iloc[0]])
    out = engine.rain_source_sensitivity(di, dp, crops, 130)
    assert out["n_years_compared"] == 2
    assert out["verdict_changes"] == [{"year": 2002, "pick_imerg": "C", "pick_power": "A",
                                       "score_imerg": 1.0, "score_power": 0.5}]
    assert out["n_verdict_changes"] == 1
    assert out["mean_score_tempo"] == {"imerg": 1.0, "power": 0.9}


def test_sensitivity_skips_gap_filled_years_and_no_imerg():
    crops = hc.load_crops()
    di = synthetic()
    dp = di.assign(P_src="POWER")
    di.loc["2003-10-05", "P_src"] = "POWER"
    out = engine.rain_source_sensitivity(di, dp, crops, 130)
    assert out["windows"]["sep_nov"]["n_years"] == 11
    assert out["windows"]["primera"]["n_years"] == 12
    assert engine.rain_source_sensitivity(dp, dp, crops, 130)["available"] is False
