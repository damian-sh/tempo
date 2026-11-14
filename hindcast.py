"""Water-balance hindcast of postrera strategies.

For every year we plant each crop at the detected postrera onset and run a
daily soil-water bucket (FEWS NET WRSI style):
    SW = min(SW + P, WHC)
    PET = Kc * ET0
    AET = PET if SW >= 0.5*WHC else PET * SW / (0.5*WHC)
    WRSI = 100 * sum(AET) / sum(PET)
Classes: >=80 good, 60-80 partial, <60 failure. A crop is downgraded one class
when the flowering (mid-season) WRSI is below 60, because water stress at
flowering costs the most yield.

Intercrops share the land. A strategy's yearly score is the land-share-weighted
score of its crops (main crop 0.6, bean 0.4). This is an assumption to validate:
it is what makes intercropping a trade-off (less in good years, more in bad ones)
instead of always winning.
"""
from __future__ import annotations

import json
import os

import numpy as np
import pandas as pd

CLASS_SCORE = {"good": 1.0, "partial": 0.5, "failure": 0.0}
LAND_SHARE = {1: [1.0], 2: [0.6, 0.4]}
LATE_PLANTING = "09-30"


def load_crops(path: str = None) -> dict:
    path = path or os.path.join(os.path.dirname(__file__), "crops.json")
    with open(path) as f:
        return json.load(f)


def kc_curve(crop: dict) -> np.ndarray:
    ini, dev, mid, late = crop["stages_days"]
    k = crop["kc"]
    return np.concatenate([
        np.full(ini, k["ini"]),
        np.linspace(k["ini"], k["mid"], dev, endpoint=False),
        np.full(mid, k["mid"]),
        np.linspace(k["mid"], k["end"], late),
    ])


def _classify(wrsi: float) -> str:
    if wrsi >= 80:
        return "good"
    if wrsi >= 60:
        return "partial"
    return "failure"


def _downgrade(cls: str) -> str:
    return {"good": "partial", "partial": "failure", "failure": "failure"}[cls]


def simulate_crop(df: pd.DataFrame, plant: pd.Timestamp, crop: dict, whc: float) -> dict | None:
    kc = kc_curve(crop)
    n = len(kc)
    window = df.loc[plant: plant + pd.Timedelta(days=n - 1)]
    if len(window) < n or window["P"].isna().any() or window["ET0"].isna().any():
        return None  # season not complete in the data

    p = window["P"].values
    pet = kc * window["ET0"].values
    sw = 0.5 * whc          # sown after onset rains: soil starts half full
    aet = np.zeros(n)
    for i in range(n):
        sw = min(sw + p[i], whc)
        a = pet[i] if sw >= 0.5 * whc else pet[i] * sw / (0.5 * whc)
        a = min(a, sw)
        aet[i] = a
        sw -= a

    ini, dev, mid, _ = crop["stages_days"]
    f0, f1 = ini + dev, ini + dev + mid
    wrsi = 100 * aet.sum() / pet.sum()
    wrsi_flower = 100 * aet[f0:f1].sum() / pet[f0:f1].sum()
    heat_days = int((window["Tmax"].values[f0:f1] > crop["heat_stress_tmax_c"]).sum())

    cls = _classify(wrsi)
    if wrsi_flower < 60:
        cls = _downgrade(cls)
    # Excess moisture at maturity (beans rot or sprout in the pod): placeholder threshold.
    late_rain = float(p[f1:].sum())
    excess = "excess_rain_late_mm" in crop and late_rain > crop["excess_rain_late_mm"]
    if excess:
        cls = _downgrade(cls)
    return {"wrsi": round(float(wrsi), 1), "wrsi_flowering": round(float(wrsi_flower), 1),
            "heat_days_flowering": heat_days, "class": cls,
            "late_rain_mm": round(late_rain, 1), "excess_rain": bool(excess),
            "water_demand_mm": round(float(pet.sum()), 1),
            "rain_in_cycle_mm": round(float(p.sum()), 1),
            "harvest": (plant + pd.Timedelta(days=n - 1)).date().isoformat()}


def planting_date(year: int, ind: pd.DataFrame) -> tuple[pd.Timestamp, bool]:
    onset = ind.loc[year, "postrera_onset"] if year in ind.index else None
    if onset is not None and pd.notna(onset):
        return pd.Timestamp(onset), False
    return pd.Timestamp(f"{year}-{LATE_PLANTING}"), True


def run_hindcast(df: pd.DataFrame, ind: pd.DataFrame, crops: dict, whc: float) -> pd.DataFrame:
    """One row per (year, strategy) with crop results and the strategy score."""
    rows = []
    for year in ind.index:
        plant, late = planting_date(year, ind)
        for skey, strat in crops["strategies"].items():
            shares = LAND_SHARE[len(strat["crops"])]
            parts, score, complete = {}, 0.0, True
            for cname, share in zip(strat["crops"], shares):
                r = simulate_crop(df, plant, crops["crops"][cname], whc)
                if r is None:
                    complete = False
                    break
                parts[cname] = r
                score += share * CLASS_SCORE[r["class"]]
            rows.append({"year": year, "strategy": skey, "plant_date": plant.date().isoformat(),
                         "late_planting": late, "complete": complete,
                         "score": round(score, 2) if complete else None, "crops": parts})
    return pd.DataFrame(rows)


# ---------------------------------------------------------------- analogs
def canicula_class(value: float, reference: pd.Series) -> str:
    """Tercile of canicula length relative to the reference years."""
    q1, q2 = reference.quantile([1 / 3, 2 / 3])
    if value <= q1:
        return "short"
    if value <= q2:
        return "normal"
    return "long"


def analog_years(year: int, ind: pd.DataFrame, complete_years: list[int]) -> tuple[str, list[int]]:
    """Years with the same canicula tercile, excluding the target year (leave-one-out)."""
    ref_years = [y for y in complete_years if y != year]
    ref = ind.loc[ref_years, "canicula_days"]
    cls = canicula_class(ind.loc[year, "canicula_days"], ref)
    analogs = [y for y in ref_years if canicula_class(ind.loc[y, "canicula_days"], ref) == cls]
    return cls, analogs


def strategy_stats(hc: pd.DataFrame, years: list[int]) -> dict:
    out = {}
    sub = hc[hc["year"].isin(years) & hc["complete"]]
    for skey, g in sub.groupby("strategy"):
        out[skey] = {"n_years": int(len(g)),
                     "mean_score": round(float(g["score"].mean()), 2),
                     "failure_rate": round(float((g["score"] == 0).mean()), 2),
                     "good_rate": round(float((g["score"] >= 0.99).mean()), 2)}
    return out


def primera_maize_check(df: pd.DataFrame, ind: pd.DataFrame, crops: dict, whc: float) -> pd.DataFrame:
    """Primera maize WRSI per year, planted at the detected primera onset.

    Used only as an external check: years with documented drought losses should
    come out among the worst years of the record.
    """
    rows = []
    for year in ind.index:
        onset = ind.loc[year, "primera_onset"]
        if onset is None or pd.isna(onset):
            continue
        r = simulate_crop(df, pd.Timestamp(onset), crops["crops"]["maize"], whc)
        if r is not None:
            rows.append({"year": int(year), "wrsi": r["wrsi"], "wrsi_flowering": r["wrsi_flowering"], "class": r["class"]})
    out = pd.DataFrame(rows)
    if not out.empty:
        out["rank_driest"] = out["wrsi"].rank(method="min").astype(int)  # 1 = worst year
    return out
