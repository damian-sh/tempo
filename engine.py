"""Tempo decision engine and output builder.

Run after fetch.py:
    python engine.py                       # all zones in config.ZONES
    python engine.py --zones morazan --seeds maize,bean
    python engine.py --weights food=1,income=0.5,soil=1,water=0.5,labor=0.3

Writes out/<zone>.json (read by the web interface) and prints the hindcast
validation that decides whether the recommendation is worth showing.
"""
from __future__ import annotations

import argparse
import json
import os

import numpy as np
import pandas as pd

import config
import hindcast as hc
import indicators as ind

DEFAULT_WEIGHTS = {"food": 1.0, "income": 0.5, "soil": 0.5, "water": 0.5, "labor": 0.3}
CLIMATE_WEIGHT = 0.6        # share of the final score that comes from the hindcast
STEEP_SLOPE_PCT = 15        # above this, soil protection weighs 1.5x
OUT_DIR = "out"

RISKS = {
    "A": ["Beans are hit by both drought at flowering and heavy rain at maturity.",
          "Short ground cover: soil is bare again by December."],
    "B": ["Sorghum is less valued as human food than maize or beans.",
          "Longer cycle: sorghum harvest falls into the dry season (December-January).",
          "Seed of local sorghum (maicillo) varieties must be confirmed."],
    "C": ["Highest water demand; late planting pushes grain filling into the dry season.",
          "No nitrogen returned to the soil; maize after maize depletes it.",
          "Skipping the bean crop removes the household's main protein and cash crop."],
}
GAPS = [
    "Rainfall is a ~10 km satellite cell (IMERG) or a ~55 km model cell (POWER), not the parcel. "
    "IMERG is known to miss part of the rain in mountain terrain.",
    "Crop parameters (cycle, water use) are FAO-56 defaults not yet validated by a local agronomist.",
    "Mixed-plot land shares (0.6 / 0.4) and the bean excess-rain threshold (150 mm at maturity) are assumptions; yields are not modeled.",
    "Soil data is SoilGrids at 250 m unless the technician enters field data.",
]


# ---------------------------------------------------------------- attributes
def strategy_attributes(skey: str, crops: dict, water_demand: dict[str, float]) -> dict:
    strat = crops["strategies"][skey]
    shares = hc.LAND_SHARE[len(strat["crops"])]
    t = [crops["crops"][c]["traits"] for c in strat["crops"]]
    w = lambda k: sum(s * tr[k] for s, tr in zip(shares, t))
    nfix = any(tr["nitrogen_fixing"] for tr in t)
    wd = water_demand.get(skey)
    wd_all = [v for v in water_demand.values() if v is not None]
    water = None
    if wd is not None and wd_all and max(wd_all) > min(wd_all):
        water = 1 - (wd - min(wd_all)) / (max(wd_all) - min(wd_all))
    return {"food": round(w("food"), 2), "income": round(w("income"), 2),
            "soil": round(0.6 * w("ground_cover") + 0.4 * (1.0 if nfix else 0.0), 2),
            "water": round(water, 2) if water is not None else 0.5,
            "labor": round(1 - w("labor"), 2), "nitrogen_fixing": nfix}


def mean_water_demand(hcdf: pd.DataFrame, years: list[int]) -> dict[str, float]:
    out = {}
    sub = hcdf[hcdf["year"].isin(years) & hcdf["complete"]]
    for skey, g in sub.groupby("strategy"):
        shares_by_crop = None
        vals = []
        for parts in g["crops"]:
            vals.append(np.mean([p["water_demand_mm"] for p in parts.values()]))
        out[skey] = float(np.mean(vals)) if vals else None
    return out


def final_score(climate: float, attrs: dict, weights: dict, slope_pct: float | None) -> float:
    w = dict(weights)
    if slope_pct is not None and slope_pct > STEEP_SLOPE_PCT:
        w["soil"] = w.get("soil", 0) * 1.5
    tot = sum(w.values()) or 1
    pref = sum(w[k] * attrs[k] for k in w) / tot
    return round(CLIMATE_WEIGHT * climate + (1 - CLIMATE_WEIGHT) * pref, 3)


def traffic_light(maize_failure_rate: float) -> str:
    if maize_failure_rate >= 0.5:
        return "red"
    if maize_failure_rate >= 0.25:
        return "yellow"
    return "green"


# ---------------------------------------------------------------- validation
def validate(hcdf: pd.DataFrame, indic: pd.DataFrame, complete_years: list[int]) -> dict:
    """Leave-one-out: pick the strategy with the best analog mean score (climate only)
    and compare its real outcome with always planting maize alone (A)."""
    assert max(config.VALIDATION_DROUGHT_YEARS) < config.TARGET_YEAR, \
        "validation years overlap the target year (D1)"
    rows = []
    for y in complete_years:
        cls, analogs = hc.analog_years(y, indic, complete_years)
        stats = hc.strategy_stats(hcdf, analogs)
        if not stats:
            continue
        pick = max(stats, key=lambda k: (stats[k]["mean_score"], -stats[k]["failure_rate"]))
        real = hcdf[(hcdf["year"] == y) & hcdf["complete"]].set_index("strategy")["score"]
        if pick not in real or "A" not in real:
            continue
        others = hc.strategy_stats(hcdf, [o for o in complete_years if o != y])
        clim = max(others, key=lambda k: (others[k]["mean_score"], -others[k]["failure_rate"]))
        rows.append({"year": y, "canicula_class": cls, "pick": pick,
                     "score_pick": float(real[pick]), "score_A": float(real["A"]),
                     "clim_pick": clim, "score_clim": float(real[clim]),
                     "best_possible": float(real.max())})
    v = pd.DataFrame(rows)
    if v.empty:
        return {"n_years": 0}
    return {
        "n_years": int(len(v)),
        "mean_score_tempo": round(float(v["score_pick"].mean()), 2),
        "mean_score_current": round(float(v["score_A"].mean()), 2),
        "mean_score_same_every_year": round(float(v["score_clim"].mean()), 2),
        "mean_score_best_possible": round(float(v["best_possible"].mean()), 2),
        "failure_years_tempo": int((v["score_pick"] == 0).sum()),
        "failure_years_current": int((v["score_A"] == 0).sum()),
        "years_tempo_better": int((v["score_pick"] > v["score_A"]).sum()),
        "years_tempo_worse": int((v["score_pick"] < v["score_A"]).sum()),
        "picks": v["pick"].value_counts().to_dict(),
        "by_year": v.to_dict(orient="records"),
    }


# ---------------------------------------------------------------- per zone
def _ts(x):
    return None if x is None or (isinstance(x, float) and np.isnan(x)) or pd.isna(x) else pd.Timestamp(x).date().isoformat()


def build_zone(zone: config.Zone, weights: dict, seeds: set[str] | None) -> dict:
    crops = hc.load_crops()
    df, info = ind.load_zone(zone.key)
    indic = ind.yearly_indicators(df)

    texture = info["soil"].get("texture_class") or "default"
    whc = crops["soil_whc_mm"].get(texture, crops["soil_whc_mm"]["default"])
    slope_pct = info["terrain"].get("slope_pct")

    hcdf = hc.run_hindcast(df, indic, crops, whc)
    complete_years = sorted(hcdf.groupby("year")["complete"].all().loc[lambda s: s].index.tolist())
    validation = validate(hcdf, indic, complete_years)

    # Does canicula length say anything about the postrera? (Spearman rank correlation)
    piv = hcdf[hcdf["complete"]].pivot(index="year", columns="strategy", values="score").astype(float)
    can = indic.loc[piv.index, "canicula_days"].astype(float)
    rain = indic.loc[piv.index, "rain_sep_nov_mm"].astype(float)
    def _sp(a, b):
        r = a.corr(b, method="spearman")
        return None if pd.isna(r) else round(float(r), 2)
    skill = {"n_years": int(len(piv)),
             "canicula_vs_sep_nov_rain": _sp(can, rain),
             "canicula_vs_score": {k: _sp(can, piv[k]) for k in piv.columns}}

    # External check: does the model see the documented primera droughts?
    pm = hc.primera_maize_check(df, indic, crops, whc)
    doc = [y for y in sorted(config.VALIDATION_DROUGHT_YEARS) if not pm.empty and y in set(pm["year"])]
    third = max(1, round(len(pm) / 3)) if not pm.empty else 0
    primera_check = {
        "years": pm.assign(documented=pm["year"].isin(list(config.VALIDATION_DROUGHT_YEARS))).to_dict(orient="records") if not pm.empty else [],
        "n_years": int(len(pm)), "worst_third_size": int(third), "documented": doc,
        "documented_in_worst_third": [int(y) for y in doc if int(pm.set_index("year").loc[y, "rank_driest"]) <= third],
    }

    # Current season = latest year with a canicula reading.
    cur = int(indic.index.max())
    cls, analogs = hc.analog_years(cur, indic, [y for y in complete_years if y != cur] + [cur]) \
        if cur not in complete_years else hc.analog_years(cur, indic, complete_years)
    stats = hc.strategy_stats(hcdf, analogs)
    all_stats = hc.strategy_stats(hcdf, complete_years)
    wd = mean_water_demand(hcdf, analogs or complete_years)

    cards = []
    for skey, strat in crops["strategies"].items():
        available = seeds is None or all(c in seeds for c in strat["crops"])
        attrs = strategy_attributes(skey, crops, wd)
        st = stats.get(skey, {"mean_score": None, "failure_rate": None, "good_rate": None, "n_years": 0})
        score = final_score(st["mean_score"], attrs, weights, slope_pct) if st["mean_score"] is not None else None
        ev = hcdf[(hcdf["strategy"] == skey) & hcdf["year"].isin(analogs) & hcdf["complete"]]
        cards.append({
            "key": skey, "label": strat["label"], "description": strat["description"], "crops": strat["crops"],
            "available": available, "score": score if available else None,
            "analog_stats": st, "all_years_stats": all_stats.get(skey), "attributes": attrs,
            "why": (f"In {st['n_years']} past years with a {cls} canícula like {cur}, this strategy "
                    f"scored {st['mean_score']} on average (1 = good harvest, 0 = failure) and failed in "
                    f"{int(round(100 * (st['failure_rate'] or 0)))}% of them."),
            "evidence": [{"year": int(r.year), "score": r.score,
                          "crops": {c: {"wrsi": p["wrsi"], "class": p["class"]} for c, p in r.crops.items()}}
                         for r in ev.itertuples()],
            "benefits": [b for b in [
                "Fixes nitrogen for the next primera." if attrs["nitrogen_fixing"] else None,
                "Keeps more of the soil covered." if attrs["soil"] >= 0.5 else None,
                "Lower water demand than the alternatives." if attrs["water"] >= 0.6 else None,
                "Highest food value." if attrs["food"] >= 0.9 else None,
                "Spreads risk across two crops." if len(strat["crops"]) > 1 else None,
            ] if b],
            "gaps": GAPS,
            "risks": RISKS.get(skey, []),
        })
    ranked = sorted([c for c in cards if c["score"] is not None], key=lambda c: -c["score"])
    recommended = ranked[0]["key"] if ranked else None
    maize_fail = stats.get("A", {}).get("failure_rate")

    # Chart: 10-day rain of the current year vs the 2001-(cur-1) normal band.
    clim = ind.climatology(df, [y for y in complete_years if y != cur])
    roll = df["P"].rolling(10, min_periods=10).sum()
    cur_series = roll[roll.index.year == cur]
    chart = {"doy": clim.index.tolist(),
             "p20": clim["p20"].round(1).tolist(), "p50": clim["p50"].round(1).tolist(),
             "p80": clim["p80"].round(1).tolist(),
             "current": {int(d.dayofyear): round(float(v), 1) for d, v in cur_series.dropna().items()}}

    # Heatmap: rain per 10-day period for every year (36 per year; None where not observed yet).
    p = df["P"]
    dek = np.minimum((p.index.dayofyear - 1) // 10, 35)
    cnt = p.groupby([p.index.year, dek]).count().unstack()
    tot = p.groupby([p.index.year, dek]).sum(min_count=1).unstack()
    tot = tot.where(cnt >= 8)
    heat = {"years": [int(y) for y in tot.index],
            "mm": [[None if pd.isna(v) else round(float(v), 1) for v in row] for row in tot.values]}

    # Rotation calendar for the current year: primera maize, then each postrera option.
    def seg(crop_key, start, season):
        ini, dev, mid, late = crops["crops"][crop_key]["stages_days"]
        d0 = int(pd.Timestamp(start).dayofyear)
        return {"crop": crop_key, "season": season, "start": d0, "end": d0 + ini + dev + mid + late,
                "flower_start": d0 + ini + dev, "flower_end": d0 + ini + dev + mid}
    plant_cur, late_cur = hc.planting_date(cur, indic)
    prim = indic.loc[cur, "primera_onset"]
    prim_seg = [seg("maize", prim, "primera")] if prim is not None and pd.notna(prim) else []
    for card in cards:
        segs = prim_seg + [seg(c, plant_cur, "postrera") for c in card["crops"]]
        covered = set()
        for sg in segs:
            covered.update(range(sg["start"], min(sg["end"], 366)))
        card["rotation"] = segs
        card["bare_days"] = 365 - len(covered)

    yearly = []
    for y, r in indic.iterrows():
        yearly.append({"year": int(y), "primera_onset": _ts(r["primera_onset"]),
                       "primera_false_onset": r["primera_false_onset"],
                       "canicula_days": int(r["canicula_days"]), "canicula_start": _ts(r["canicula_start"]),
                       "rain_jul_aug_mm": r["rain_jul_aug_mm"], "postrera_onset": _ts(r["postrera_onset"]),
                       "rain_sep_nov_mm": r["rain_sep_nov_mm"]})

    return {
        "zone": zone.__dict__,
        "current_year": cur,
        "current": {"canicula_days": int(indic.loc[cur, "canicula_days"]), "canicula_class": cls,
                    "postrera_onset": _ts(indic.loc[cur, "postrera_onset"]),
                    "analog_years": analogs,
                    "traffic_light": traffic_light(maize_fail) if maize_fail is not None else None,
                    "recommended": recommended},
        "strategies": cards,
        "validation": validation,
        "skill": skill,
        "primera_check": primera_check,
        "yearly": yearly,
        "chart": chart,
        "heat": heat,
        "postrera_planting": {"date": plant_cur.date().isoformat(), "late_default": bool(late_cur)},
        "inputs": {"texture_class": texture, "whc_mm": whc, "slope_pct": slope_pct,
                   "weights": weights, "seeds": sorted(seeds) if seeds else None,
                   "temp_correction_c": info["temp_correction_c"],
                   "share_days_imerg": info["share_days_imerg"], "soil": info["soil"],
                   "terrain": info["terrain"], "sources": info["meta"].get("sources")},
    }


def clean_json(obj):
    """Replace NaN/inf with None so browsers can JSON.parse the output."""
    if isinstance(obj, dict):
        return {k: clean_json(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [clean_json(v) for v in obj]
    if isinstance(obj, (float, np.floating)):
        return None if not np.isfinite(obj) else float(obj)
    if isinstance(obj, np.integer):
        return int(obj)
    if isinstance(obj, np.bool_):
        return bool(obj)
    return obj


def print_summary(out: dict) -> None:
    z, v, c = out["zone"], out["validation"], out["current"]
    print(f"\n=== {z['key']} — {z['name']}")
    print(f"  Rain days from IMERG: {100 * out['inputs']['share_days_imerg']:.0f}%  |  "
          f"temp correction {out['inputs']['temp_correction_c']} C  |  WHC {out['inputs']['whc_mm']} mm")
    pc, sk = out["primera_check"], out["skill"]
    print(f"  CHECK 1 - documented droughts: {len(pc['documented_in_worst_third'])} of {len(pc['documented'])} "
          f"documented years fall in the model's worst {pc['worst_third_size']} of {pc['n_years']} primera years "
          f"({pc['documented_in_worst_third']} of {pc['documented']})")
    print(f"  CHECK 2 - canicula as a signal (Spearman, n={sk['n_years']}): vs Sep-Nov rain {sk['canicula_vs_sep_nov_rain']}, "
          f"vs strategy score {sk['canicula_vs_score']}")
    if v.get("n_years"):
        print(f"  CHECK 3 - hindcast ({v['n_years']} years, leave-one-out, climate-only pick), mean score:")
        print(f"    Tempo {v['mean_score_tempo']} | current practice {v['mean_score_current']} | "
              f"same strategy every year {v['mean_score_same_every_year']} | perfect hindsight {v['mean_score_best_possible']}")
        print(f"    failure years: Tempo {v['failure_years_tempo']} vs current {v['failure_years_current']}; "
              f"Tempo better in {v['years_tempo_better']}, worse in {v['years_tempo_worse']}; picks {v['picks']}")
    print(f"  {out['current_year']}: canícula {c['canicula_days']} days ({c['canicula_class']}), "
          f"light {c['traffic_light']}, recommended {c['recommended']}, analogs {c['analog_years']}")
    for s in out["strategies"]:
        print(f"    [{s['key']}] {s['label']:<26} score {s['score']}  analog {s['analog_stats']}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--zones", help="comma-separated zone keys (default: all)")
    ap.add_argument("--seeds", help="comma-separated available seeds, e.g. maize,bean")
    ap.add_argument("--weights", help="e.g. food=1,income=0.5,soil=1,water=0.5,labor=0.3")
    a = ap.parse_args()

    weights = dict(DEFAULT_WEIGHTS)
    if a.weights:
        for kv in a.weights.split(","):
            k, v = kv.split("=")
            weights[k.strip()] = float(v)
    seeds = set(s.strip() for s in a.seeds.split(",")) if a.seeds else None
    keys = set(a.zones.split(",")) if a.zones else None

    os.makedirs(OUT_DIR, exist_ok=True)
    for z in config.ZONES:
        if keys and z.key not in keys:
            continue
        out = build_zone(z, weights, seeds)
        with open(os.path.join(OUT_DIR, f"{z.key}.json"), "w") as f:
            json.dump(clean_json(out), f, indent=1, default=str, allow_nan=False)
        print_summary(out)


if __name__ == "__main__":
    main()
