"""Unit tests for Hargreaves ET0 (D4) and the elevation correction (D3). No cache needed."""
import os
import sys

import pandas as pd
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import indicators as ind  # noqa: E402

# Hand calculation, FAO-56, lat 13.8 N, DOY 250, Tmax 32 C, Tmin 20 C:
#   phi = 0.240855 rad
#   dr  = 1 + 0.033 cos(2*pi*250/365)          = 0.986881   (eq. 23)
#   d   = 0.409 sin(2*pi*250/365 - 1.39)       = 0.092463   (eq. 24)
#   ws  = arccos(-tan(phi) tan(d))             = 1.593574   (eq. 25)
#   Ra  = 24*60/pi * 0.082 * dr * (ws sin(phi) sin(d) + cos(phi) cos(d) sin(ws))
#       = 37.1609 MJ m-2 d-1 -> * 0.408        = 15.1616 mm/d (eq. 21)
#   Tmean = (32 + 20) / 2                      = 26.0
#   ET0 = 0.0023 * (26 + 17.8) * sqrt(12) * 15.1616 = 5.2910 mm/d (eq. 52)
ET0_HAND_MM = 5.2910


def test_hargreaves_fao56_eq52_synthetic_day():
    day = pd.DatetimeIndex(["2025-09-07"])  # DOY 250
    assert day.dayofyear[0] == 250
    et0 = ind.hargreaves_et0(pd.Series([32.0], index=day), pd.Series([20.0], index=day), 13.8)
    assert et0.iloc[0] == pytest.approx(ET0_HAND_MM, abs=0.01)


def test_hargreaves_default_tmean_is_tmax_tmin_mean():
    day = pd.DatetimeIndex(["2025-09-07"])
    tmax, tmin = pd.Series([32.0], index=day), pd.Series([20.0], index=day)
    explicit = ind.hargreaves_et0(tmax, tmin, 13.8, tmean=pd.Series([26.0], index=day))
    assert ind.hargreaves_et0(tmax, tmin, 13.8).iloc[0] == pytest.approx(explicit.iloc[0])


def test_et0_change_pct():
    idx = pd.date_range("2001-01-01", "2002-12-31")
    ref = pd.Series(4.0, index=idx)
    assert ind.et0_change_pct(ref * 1.05, ref) == pytest.approx(5.0)


@pytest.mark.parametrize("cell, parcel", [(607.66, None), (None, 900.0), (None, None)])
def test_elevation_missing_gives_null_and_warning(cell, parcel):
    dT, warnings = ind.elevation_correction(cell, parcel)
    assert dT is None
    assert any("sin corrección por elevación" in w for w in warnings)


def test_elevation_lapse_rate():
    dT, warnings = ind.elevation_correction(600.0, 1100.0)
    assert dT == pytest.approx(-0.0065 * 500)
    assert warnings == []
