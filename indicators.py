"""Daily series and yearly season indicators for one zone.

Inputs come from cache/<zone>/ (written by fetch.py).
Precipitation: GPM IMERG local-day totals when available, otherwise NASA POWER
PRECTOTCORR (each day is flagged with its source).
Temperature: NASA POWER, corrected for elevation with a 6.5 C/km lapse rate
when the parcel elevation (SRTM or manual) and the POWER cell elevation are known.
Reference evapotranspiration: Hargreaves (FAO-56 eq. 52).
"""
from __future__ import annotations

import json
import math
import os
from dataclasses import dataclass

import numpy as np
import pandas as pd

import config

LAPSE_C_PER_M = 0.0065
RAIN_DAY_MM = 1.0          # a day with >= 1 mm counts as rainy


@dataclass
class OnsetRule:
    window_days: int = 5
    min_total_mm: float = 25.0
    min_rain_days: int = 2
    false_check_days: int = 30
    false_dry_spell_days: int = 7


# ---------------------------------------------------------------- loading
def _read_json(path: str) -> dict:
    if not os.path.exists(path):
        return {}
    with open(path) as f:
        return json.load(f)


def load_zone(zone_key: str) -> tuple[pd.DataFrame, dict]:
    d = os.path.join(config.CACHE_DIR, zone_key)
    meta = _read_json(os.path.join(d, "meta.json"))
    soil = _read_json(os.path.join(d, "soil.json"))
    terrain = _read_json(os.path.join(d, "terrain.json"))

    power = pd.read_csv(os.path.join(d, "power.csv"), parse_dates=["date"], index_col="date")
    df = pd.DataFrame(index=power.index)

    # Precipitation: IMERG first, POWER as gap filler.
    df["P"] = power["PRECTOTCORR"]
    df["P_src"] = "POWER"
    imerg_path = os.path.join(d, "imerg.csv")
    if os.path.exists(imerg_path):
        im = pd.read_csv(imerg_path, parse_dates=["date"], index_col="date")["imerg_mm"]
        im = im.reindex(df.index)
        has = im.notna()
        df.loc[has, "P"] = im[has]
        df.loc[has, "P_src"] = "IMERG"

    # Temperature with elevation correction.
    cell_elev = meta.get("power_cell_elevation_m")
    parcel_elev = terrain.get("elevation_m")
    dT = 0.0
    if cell_elev is not None and parcel_elev is not None:
        dT = -LAPSE_C_PER_M * (parcel_elev - cell_elev)
    df["Tmax"] = power["T2M_MAX"] + dT
    df["Tmin"] = power["T2M_MIN"] + dT
    df["Tmean"] = power["T2M"] + dT
    df["RH"] = power.get("RH2M")

    lat = meta.get("zone", {}).get("lat")
    df["ET0"] = hargreaves_et0(df["Tmax"], df["Tmin"], df["Tmean"], lat)

    info = {"meta": meta, "soil": soil, "terrain": terrain, "temp_correction_c": round(dT, 2),
            "share_days_imerg": round(float((df["P_src"] == "IMERG").mean()), 3)}
    return df, info


# ---------------------------------------------------------------- ET0
def extraterrestrial_radiation_mm(lat_deg: float, doy: np.ndarray) -> np.ndarray:
    """Ra in mm/day of evaporation equivalent (FAO-56 eq. 21, times 0.408)."""
    phi = math.radians(lat_deg)
    dr = 1 + 0.033 * np.cos(2 * np.pi * doy / 365)
    delta = 0.409 * np.sin(2 * np.pi * doy / 365 - 1.39)
    ws = np.arccos(np.clip(-np.tan(phi) * np.tan(delta), -1, 1))
    ra_mj = (24 * 60 / np.pi) * 0.0820 * dr * (
        ws * np.sin(phi) * np.sin(delta) + np.cos(phi) * np.cos(delta) * np.sin(ws))
    return 0.408 * ra_mj


def hargreaves_et0(tmax: pd.Series, tmin: pd.Series, tmean: pd.Series, lat: float) -> pd.Series:
    doy = tmax.index.dayofyear.values
    ra = extraterrestrial_radiation_mm(lat, doy)
    tr = (tmax - tmin).clip(lower=0)
    return (0.0023 * (tmean + 17.8) * np.sqrt(tr) * ra).clip(lower=0)


# ---------------------------------------------------------------- season tools
def max_dry_spell(p: pd.Series) -> tuple[int, pd.Timestamp | None]:
    """Longest run of consecutive days with P < RAIN_DAY_MM. Returns (length, start)."""
    best, best_start, run, run_start = 0, None, 0, None
    for day, val in p.items():
        if pd.notna(val) and val < RAIN_DAY_MM:
            if run == 0:
                run_start = day
            run += 1
            if run > best:
                best, best_start = run, run_start
        else:
            run = 0
    return best, best_start


def find_onset(p: pd.Series, start: str, end: str, rule: OnsetRule = OnsetRule()) -> dict:
    """First day in [start, end] whose next `window_days` meet the onset rule.

    Also flags a false onset: a dry spell >= false_dry_spell_days within the
    following false_check_days.
    """
    s, e = pd.Timestamp(start), pd.Timestamp(end)
    for day in pd.date_range(s, e):
        w = p.loc[day: day + pd.Timedelta(days=rule.window_days - 1)]
        if len(w) < rule.window_days or w.isna().any():
            continue
        if w.sum() >= rule.min_total_mm and (w >= RAIN_DAY_MM).sum() >= rule.min_rain_days:
            after = p.loc[day + pd.Timedelta(days=rule.window_days):
                          day + pd.Timedelta(days=rule.window_days + rule.false_check_days - 1)]
            spell, _ = max_dry_spell(after)
            return {"date": day, "false_onset": bool(spell >= rule.false_dry_spell_days),
                    "dry_spell_after": int(spell)}
    return {"date": None, "false_onset": None, "dry_spell_after": None}


def yearly_indicators(df: pd.DataFrame, rule: OnsetRule = OnsetRule()) -> pd.DataFrame:
    rows = []
    last_day = df["P"].last_valid_index()
    for year in sorted(df.index.year.unique()):
        y = str(year)
        if pd.Timestamp(f"{y}-08-31") > last_day:
            continue  # not enough of the year to say anything about the canicula
        p = df["P"]
        primera = find_onset(p, f"{y}-04-01", f"{y}-06-30", rule)
        can_len, can_start = max_dry_spell(p.loc[f"{y}-07-01":f"{y}-08-31"])
        postrera = find_onset(p, f"{y}-08-15", f"{y}-09-30", rule)
        rows.append({
            "year": year,
            "primera_onset": primera["date"],
            "primera_false_onset": primera["false_onset"],
            "rain_may_aug_mm": round(float(p.loc[f"{y}-05-01":f"{y}-08-31"].sum()), 1),
            "canicula_days": can_len,
            "canicula_start": can_start,
            "rain_jul_aug_mm": round(float(p.loc[f"{y}-07-01":f"{y}-08-31"].sum()), 1),
            "postrera_onset": postrera["date"],
            "postrera_false_onset": postrera["false_onset"],
            "rain_sep_nov_mm": round(float(p.loc[f"{y}-09-01":f"{y}-11-30"].sum()), 1)
            if pd.Timestamp(f"{y}-11-30") <= last_day else None,
        })
    return pd.DataFrame(rows).set_index("year")


def climatology(df: pd.DataFrame, years: range | list) -> pd.DataFrame:
    """Day-of-year percentiles of 10-day accumulated rain, for the 'normal band' chart."""
    roll = df["P"].rolling(10, min_periods=10).sum()
    sub = roll[roll.index.year.isin(list(years))]
    g = sub.groupby(sub.index.dayofyear)
    return pd.DataFrame({"p20": g.quantile(0.2), "p50": g.quantile(0.5), "p80": g.quantile(0.8)})
