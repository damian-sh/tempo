"""Recomendación robusta (D10): maximin entre escenarios, nivel de confianza, resumen y suelo de respaldo."""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import engine  # noqa: E402
import server  # noqa: E402

NAMES = {"A": "Frijol en relevo tras maíz", "B": "Sorgo (maicillo) + frijol", "C": "Segunda maíz"}
FMT = lambda x, nd=3: "s/d" if x is None else f"{x:.{nd}f}".replace(".", ",")


# ---------------------------------------------------------------- maximin
def test_pick_is_best_worst_case_not_best_base():
    # C gana en el escenario base, pero B tiene el mejor peor caso (0,72 frente a 0,70 y 0,60).
    sc = {"base": {"A": 0.70, "B": 0.72, "C": 0.80},
          "power": {"A": 0.78, "B": 0.74, "C": 0.60}}
    rp = engine.robust_pick(sc)
    assert rp["pick"] == "B"
    assert rp["worst"] == {"A": 0.70, "B": 0.72, "C": 0.60}
    assert rp["wins"] == []  # B no es primera en ningún escenario: por eso la confianza no sube


def test_pick_maximin_exact():
    sc = {"s1": {"A": 0.70, "B": 0.75, "C": 0.90}, "s2": {"A": 0.80, "B": 0.76, "C": 0.50}}
    rp = engine.robust_pick(sc)
    assert rp["pick"] == "B" and rp["second"] == "A"
    assert rp["worst_margin"] == pytest.approx(0.05)


def test_tie_keeps_current_practice():
    sc = {"s1": {"A": 0.8, "B": 0.8}, "s2": {"A": 0.8, "B": 0.8}}
    assert engine.robust_pick(sc)["pick"] == engine.CURRENT_PRACTICE


def test_only_strategies_scored_everywhere_compete():
    sc = {"s1": {"A": 0.5, "B": 0.6, "C": 0.99}, "s2": {"A": 0.5, "B": 0.6}}
    rp = engine.robust_pick(sc)
    assert set(rp["worst"]) == {"A", "B"} and rp["pick"] == "B"


def test_none_when_fewer_than_two_options():
    assert engine.robust_pick({}) is None
    assert engine.robust_pick({"s1": {"A": 0.5}}) is None
    assert engine.robust_pick({"s1": {}, "s2": {}}) is None


# ---------------------------------------------------------------- confianza
def _rp(n_wins, n, worst_margin, regret):
    return {"pick": "A", "n_wins": n_wins, "n_scenarios": n, "worst_margin": worst_margin,
            "max_regret": {"A": regret}}


def test_confidence_levels():
    assert engine.robust_confidence(_rp(6, 6, 0.06, 0.0), True, True) == ("alta", [])
    assert engine.robust_confidence(_rp(3, 6, 0.01, 0.02), True, True) == ("media", [])
    assert engine.robust_confidence(_rp(3, 6, 0.05, 0.13), True, True) == ("baja", [])


def test_confidence_capped_without_measured_soil_or_imerg():
    assert engine.robust_confidence(_rp(6, 6, 0.2, 0.0), True, False) == ("media", ["soil"])
    assert engine.robust_confidence(_rp(6, 6, 0.2, 0.0), False, True) == ("baja", ["rain"])
    assert engine.robust_confidence(_rp(6, 6, 0.2, 0.0), True, True, check1_ok=False) == ("media", ["check1"])


def test_confidence_needs_base_margin_and_strict_checks():
    # Margen base < 0,05: baja aunque gane en todos los escenarios ("no hay razón para cambiar").
    assert engine.robust_confidence(_rp(6, 6, 0.2, 0.0), True, True, base_margin=0.003) == ("baja", ["margin"])
    # Pruebas estrictas fallidas: nunca alta.
    assert engine.robust_confidence(_rp(6, 6, 0.2, 0.0), True, True, strict_ok=False, base_margin=0.06) == ("media", ["strict"])
    # Todo en orden: alta.
    assert engine.robust_confidence(_rp(6, 6, 0.2, 0.0), True, True, strict_ok=True, base_margin=0.06) == ("alta", [])


# ---------------------------------------------------------------- resumen del servidor
def _out(robust, claro_rec=None):
    return {"robust": robust, "current": {"recommended": claro_rec, "margin_over_second": 0.01}}


def test_summary_uses_robust_pick_with_reasons():
    sc = {"base": {"A": 0.70, "B": 0.75, "C": 0.90}, "power": {"A": 0.80, "B": 0.76, "C": 0.50}}
    rp = engine.robust_pick(sc)
    level, caps = engine.robust_confidence(rp, True, False)
    robust = {"available": True, "method": "maximin", "margin": 0.05, "tie": 0.005, **rp,
              "confidence": level, "confidence_caps": caps, "scenarios": sc,
              "scenario_defs": {"base": {"rain": "imerg"}, "power": {"rain": "power"}}}
    r = server.robust_summary(_out(robust), None, NAMES, FMT)
    assert r["clave"] == "B" and r["origen"] == "robusta" and r["confianza"] == level
    assert "0,750" in r["texto"] and "en 2 escenarios" in r["texto"]
    assert any("SoilGrids" in x for x in r["limites"])
    assert [e["clave"] for e in r["escenarios"]] == ["base", "power"]
    assert r["escenarios"][0]["mejor"] == "C"


def test_summary_clear_verdict_is_high_confidence():
    r = server.robust_summary(_out({"available": False}), "A", NAMES, FMT)
    assert r["clave"] == "A" and r["confianza"] == "alta" and r["origen"] == "veredicto"


def test_summary_none_without_comparison():
    assert server.robust_summary(_out({"available": False}), None, NAMES, FMT) is None
    assert server.robust_summary({}, None, NAMES, FMT) is None


# ---------------------------------------------------------------- suelo: REST y respaldo en Earth Engine
class FakeSoil:
    def __init__(self, rest=None, rest_exc=None, gee=None, gee_exc=None):
        self.rest, self.rest_exc, self.gee_val, self.gee_exc = rest, rest_exc, gee, gee_exc
        self.gee_calls = 0
    texture_class = staticmethod(__import__("fetch").texture_class)

    def fetch_soilgrids(self, lat, lon):
        if self.rest_exc:
            raise self.rest_exc
        return dict(self.rest)

    def fetch_soilgrids_gee(self, lat, lon):
        self.gee_calls += 1
        if self.gee_exc:
            raise self.gee_exc
        return dict(self.gee_val)


SOIL_OK = {"clay": {"value_0_30cm": 38.0}, "sand": {"value_0_30cm": 30.0}}
SOIL_NULL = {"clay": {"value_0_30cm": None}, "sand": {"value_0_30cm": None}}
noop = lambda *a, **k: None


def test_soil_rest_ok_skips_gee():
    fm, errors = FakeSoil(rest=SOIL_OK), {}
    s = server.fetch_soil(fm, 13.3, -87.2, noop, lambda: (True, None), errors)
    assert s["texture_class"] == "clayey" and s["radius_m"] == 0 and fm.gee_calls == 0 and not errors


def test_soil_rest_null_uses_gee_neighbourhood():
    fm, errors = FakeSoil(rest=SOIL_NULL, gee={**SOIL_OK, "radius_m": 1000}), {}
    s = server.fetch_soil(fm, 13.3, -87.2, noop, lambda: (True, None), errors)
    assert s["texture_class"] == "clayey" and "1 km alrededor" in s["source"] and not errors


def test_soil_rest_down_uses_gee_point():
    fm, errors = FakeSoil(rest_exc=RuntimeError("503"), gee={**SOIL_OK, "radius_m": 0}), {}
    s = server.fetch_soil(fm, 13.3, -87.2, noop, lambda: (True, None), errors)
    assert s["texture_class"] == "clayey" and "alrededor" not in s["source"] and "503" in s["rest_error"]


def test_soil_never_invented_when_everything_fails():
    fm, errors = FakeSoil(rest_exc=RuntimeError("503"), gee_exc=RuntimeError("sin dato")), {}
    s = server.fetch_soil(fm, 13.3, -87.2, noop, lambda: (True, None), errors)
    assert "error" in s and "texture_class" not in s and "soilgrids" in errors
    fm2, errors2 = FakeSoil(rest=SOIL_NULL), {}
    s2 = server.fetch_soil(fm2, 13.3, -87.2, noop, lambda: (False, "sin GEE"), errors2)
    assert "error" in s2 and fm2.gee_calls == 0 and "sin GEE" in errors2["soilgrids"]


def test_run_one_error_message_is_one_short_line(tmp_path):
    store = server.JobStore(str(tmp_path / "jobs"))

    def boom(rec, st, progress):
        raise RuntimeError("<html><body>503 Service Unavailable</body></html>\n" + "x" * 500)
    q = server.JobQueue(store, boom)
    rec, _ = q.submit({"lat": 13.5, "lon": -88.0})
    out = q.run_one(rec["id"])
    assert out["estado"] == "error" and "\n" not in out["mensaje"] and len(out["mensaje"]) < 260


# ---------------------------------------------------------------- Meteomatics como respaldo de NASA POWER
import datetime as _dt  # noqa: E402

import fetch  # noqa: E402


def _mm_payload():
    d = lambda iso, v: {"date": iso, "value": v}
    blk = lambda p, vals: {"parameter": p, "coordinates": [{"lat": 13.5, "lon": -87.5, "dates": vals}]}
    stamps = ["2026-11-02T06:00:00Z", "2026-11-03T06:00:00Z"]
    return {"status": "OK", "data": [
        blk("precip_24h:mm", [d(stamps[0], 4.2), d(stamps[1], -999)]),
        blk("t_max_2m_24h:C", [d(s, 33.0) for s in stamps]),
        blk("t_min_2m_24h:C", [d(s, 22.0) for s in stamps]),
        blk("t_mean_2m_24h:C", [d(s, 27.5) for s in stamps]),
        blk("relative_humidity_mean_2m_24h:p", [d(s, 70.0) for s in stamps]),
        blk("elevation:m", [d(s, 37.0) for s in stamps]),
    ]}


def test_meteomatics_maps_to_local_day_and_power_columns():
    df, elev = fetch.parse_meteomatics(_mm_payload(), offset_h=-6)
    assert elev == 37.0
    assert [str(x.date()) for x in df.index] == ["2026-11-01", "2026-11-02"]  # 06:00Z del día d+1 = día local d
    assert set(fetch.POWER_PARAMS) == set(df.columns)
    assert df.loc["2026-11-01", "PRECTOTCORR"] == 4.2
    assert pd_isna(df.loc["2026-11-02", "PRECTOTCORR"])  # -999 = sin dato, nunca 0


def pd_isna(x):
    import pandas as pd
    return pd.isna(x)


def test_meteomatics_bad_status_raises():
    with pytest.raises(RuntimeError):
        fetch.parse_meteomatics({"status": "error", "message": "Unauthorized"})


def test_meteomatics_expired_or_without_credentials(monkeypatch):
    monkeypatch.setattr(fetch.config, "METEOMATICS_USER", "u")
    monkeypatch.setattr(fetch.config, "METEOMATICS_PASSWORD", "p")
    monkeypatch.setattr(fetch.config, "METEOMATICS_VALID_UNTIL", "2026-11-22")
    assert fetch.meteomatics_available(_dt.date(2026, 11, 22)) == (True, None)
    ok, why = fetch.meteomatics_available(_dt.date(2026, 11, 23))
    assert not ok and "vencida" in why
    monkeypatch.setattr(fetch.config, "METEOMATICS_PASSWORD", None)
    assert fetch.meteomatics_available(_dt.date(2026, 11, 1))[0] is False


class FakeFetchMM:
    POWER_PARAMS = ["T2M"]
    METEOMATICS_SOURCE = "Meteomatics (prueba)"

    def __init__(self, mm_fails=False):
        self.mm_fails = mm_fails

    def _end_date(self):
        return "2026-11-13"

    def fetch_power(self, lat, lon, start, end):
        raise RuntimeError("POWER caído")

    def fetch_meteomatics(self, lat, lon, start, end):
        if self.mm_fails:
            raise RuntimeError("Meteomatics no respondió (HTTP 401)")
        import pandas as pd
        df = pd.DataFrame({"PRECTOTCORR": [1.0, 2.0]}, index=pd.to_datetime(["2001-01-01", "2001-01-02"]))
        df.index.name = "date"
        return df, 37.0

    def power_precip_json(self, power):
        return {"values": [1.0, 2.0]}

    def fetch_soilgrids(self, lat, lon):
        raise RuntimeError("SoilGrids caído")

    def texture_class(self, c, s):
        return None


class _Eng:
    DEFAULT_WEIGHTS = {}

    def build_zone(self, zone, weights, seeds, rain_source):
        return {"zone": zone.__dict__}

    def clean_json(self, x):
        return x


def test_power_down_uses_meteomatics_and_says_so(tmp_path, monkeypatch):
    store = server.JobStore(str(tmp_path / "jobs"))
    monkeypatch.setattr(server, "registered_cache", lambda lat, lon: None)
    monkeypatch.setattr(server, "summarize", lambda out, f: {"anio": 2026, "veredicto": {"claro": False, "titulo": "t"}})
    rec = {"id": server.job_id(13.53, -87.49), "lat": 13.53, "lon": -87.49}
    out = server.process_point(rec, store, lambda *a: None, fetch_mod=FakeFetchMM(),
                               gee=lambda: (False, "sin GEE"), engine_mod=_Eng())
    assert out["estado"] == "parcial"
    assert any("Meteomatics" in f for f in out["faltantes"])
    with open(os.path.join(store.data_dir(rec["id"]), "meta.json")) as f:
        meta = __import__("json").load(f)
    assert meta["weather_backup"]["source"] == "meteomatics" and meta["power_cell_elevation_m"] == 37.0


def test_power_and_backup_down_is_error(tmp_path, monkeypatch):
    store = server.JobStore(str(tmp_path / "jobs"))
    monkeypatch.setattr(server, "registered_cache", lambda lat, lon: None)
    rec = {"id": server.job_id(13.52, -87.48), "lat": 13.52, "lon": -87.48}
    out = server.process_point(rec, store, lambda *a: None, fetch_mod=FakeFetchMM(mm_fails=True),
                               gee=lambda: (False, "sin GEE"), engine_mod=_Eng())
    assert out["estado"] == "error" and "POWER" in out["mensaje"] and "Meteomatics" in out["mensaje"]


# ---------------------------------------------------------------- temporada en curso, solo lluvia medida
def test_current_season_reports_done_and_in_field_without_filling():
    import pandas as pd
    crops = {"strategies": {"A": {"crops": ["bean"]}, "C": {"crops": ["maize"]}},
             "crops": {"bean": {"stages_days": [15, 25, 20, 10]}, "maize": {"stages_days": [20, 30, 30, 20]}}}
    hcdf = pd.DataFrame([
        {"year": 2026, "strategy": "A", "plant_date": "2026-08-29", "complete": True, "score": 1.0,
         "crops": {"bean": {"wrsi": 98.0, "class": "good"}}},
        {"year": 2026, "strategy": "C", "plant_date": "2026-08-29", "complete": False, "score": None, "crops": {}},
        {"year": 2025, "strategy": "A", "plant_date": "2025-08-29", "complete": True, "score": 0.5, "crops": {}},
    ])
    cs = {x["strategy"]: x for x in engine.current_season(hcdf, crops, 2026, pd.Timestamp("2026-11-12"))}
    assert set(cs) == {"A", "C"}
    assert cs["A"]["complete"] and cs["A"]["score"] == 1.0 and cs["A"]["harvest_date"] == "2026-11-07"
    assert cs["C"]["score"] is None and cs["C"]["harvest_date"] == "2026-12-07" and cs["C"]["days_missing"] == 25
