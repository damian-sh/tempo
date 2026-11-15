"""Tempo decision engine and output builder.

Run after fetch.py:
    python engine.py                       # all zones in config.ZONES
    python engine.py --zones morazan --seeds maize,bean
    python engine.py --weights food=1,income=0.5,soil=1,water=0.5,labor=0.3
    python engine.py --rain-source power   # NASA POWER rain only (default: imerg)

Writes out/<zone>.json (read by the web interface) and prints the hindcast
validation that decides whether the recommendation is worth showing.
"""
from __future__ import annotations

import argparse
import copy
import json
import math
import os

import numpy as np
import pandas as pd

import config
import hindcast as hc
import indicators as ind

DEFAULT_WEIGHTS = {"food": 1.0, "income": 0.5, "soil": 0.5, "water": 0.5, "labor": 0.3}
CLIMATE_WEIGHT = 0.6        # share of the final score that comes from the hindcast
STEEP_SLOPE_PCT = 15        # above this, soil protection weighs 1.5x
OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out")
SENSITIVITY_WHC_MM = (60, 90, 130)   # sandy / default / clayey in crops.json
CURRENT_PRACTICE = "A"                # relay bean after maize; kept on ties (no change without margin)
# Robust recommendation (D10). Both values are SUPUESTOS, not measured errors.
ROBUST_TIE = 0.005                    # scores are rounded to 3 decimals; closer than this is a tie
ROBUST_MARGIN = 0.05                  # same reading threshold as the site verdict (build_site.READ_MARGIN)
CONFIDENCE_ORDER = ("baja", "media", "alta")

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
    """Mean seasonal crop water demand per strategy, weighted by land share (0.6 / 0.4).

    The crops dict keeps the strategy's crop order (main crop first), as built by run_hindcast.
    """
    out = {}
    sub = hcdf[hcdf["year"].isin(years) & hcdf["complete"]]
    for skey, g in sub.groupby("strategy"):
        vals = []
        for parts in g["crops"]:
            shares = hc.LAND_SHARE[len(parts)]
            vals.append(sum(s * p["water_demand_mm"] for s, p in zip(shares, parts.values())))
        out[skey] = float(np.mean(vals)) if vals else None
    return out


def bare_days(segments: list[dict], year_len: int = 365) -> int:
    """Days of the year with no crop, for a rotation that repeats every year.

    Segments are [start, end) in day-of-year; days past the year end wrap into January.
    """
    covered = set()
    for sg in segments:
        covered.update((d - 1) % year_len + 1 for d in range(sg["start"], sg["end"]))
    return year_len - len(covered)


def final_score(climate: float, attrs: dict, weights: dict, slope_pct: float | None) -> float:
    w = dict(weights)
    if slope_pct is not None and slope_pct > STEEP_SLOPE_PCT:
        w["soil"] = w.get("soil", 0) * 1.5
    tot = sum(w.values()) or 1
    pref = sum(w[k] * attrs[k] for k in w) / tot
    return round(CLIMATE_WEIGHT * climate + (1 - CLIMATE_WEIGHT) * pref, 3)


# The former traffic light (stats["A"] failure rate, failure = score 0) was removed: it read
# the bean relay as if it were maize, and no observed yields or discriminating drought check
# back any risk threshold. See DECISIONES.md.


# ---------------------------------------------------------------- validation
def history_years(years) -> list[int]:
    """Years usable for validation, ranks and reference statistics: before TARGET_YEAR (D1)."""
    return sorted(int(y) for y in years if int(y) < config.TARGET_YEAR)


def _best(stats: dict) -> tuple[str, bool]:
    """Best strategy by (mean score, -failure rate). On a tie keep the current practice if it is
    tied, else the first key: a tie is not a reason to change. Returns (key, tied)."""
    key = lambda k: (stats[k]["mean_score"], -stats[k]["failure_rate"])
    top = max(key(k) for k in stats)
    tied = sorted(k for k in stats if key(k) == top)
    pick = CURRENT_PRACTICE if CURRENT_PRACTICE in tied else tied[0]
    return pick, len(tied) > 1


def sign_test_p(n_better: int, n_worse: int) -> float | None:
    """Two-sided exact sign test (ties dropped). None when there is nothing to test."""
    n = n_better + n_worse
    if n == 0:
        return None
    k = min(n_better, n_worse)
    return round(min(1.0, 2 * sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n), 4)


def validate(hcdf: pd.DataFrame, indic: pd.DataFrame, complete_years: list[int]) -> dict:
    """Leave-one-out: pick the strategy with the best analog mean score (climate only)
    and compare its real outcome with the current practice (A, relay bean after maize).

    TARGET_YEAR (and later) is dropped from both the evaluated years and the analogs (D1).
    """
    assert max(config.VALIDATION_DROUGHT_YEARS) < config.TARGET_YEAR, \
        "validation years overlap the target year (D1)"
    complete_years = history_years(complete_years)
    rows = []
    for y in complete_years:
        cls, analogs = hc.analog_years(y, indic, complete_years)
        stats = hc.strategy_stats(hcdf, analogs)
        if not stats:
            continue
        pick, tied = _best(stats)
        real = hcdf[(hcdf["year"] == y) & hcdf["complete"]].set_index("strategy")["score"]
        if pick not in real or CURRENT_PRACTICE not in real:
            continue
        others = hc.strategy_stats(hcdf, [o for o in complete_years if o != y])
        clim, _ = _best(others)
        rows.append({"year": y, "canicula_class": cls, "pick": pick, "pick_tied": tied,
                     "score_pick": float(real[pick]), "score_A": float(real[CURRENT_PRACTICE]),
                     "clim_pick": clim, "score_clim": float(real[clim]),
                     "best_possible": float(real.max())})
    v = pd.DataFrame(rows)
    if v.empty:
        return {"n_years": 0}
    better = int((v["score_pick"] > v["score_A"]).sum())
    worse = int((v["score_pick"] < v["score_A"]).sum())
    return {
        "n_years": int(len(v)),
        "years": [int(y) for y in v["year"]],
        "mean_margin_vs_current": round(float((v["score_pick"] - v["score_A"]).mean()), 3),
        "mean_margin_vs_same_every_year": round(float((v["score_pick"] - v["score_clim"]).mean()), 3),
        "sign_test_p": sign_test_p(better, worse),
        "n_years_pick_tied": int(v["pick_tied"].sum()),
        "mean_score_tempo": round(float(v["score_pick"].mean()), 2),
        "mean_score_current": round(float(v["score_A"].mean()), 2),
        "mean_score_same_every_year": round(float(v["score_clim"].mean()), 2),
        "mean_score_best_possible": round(float(v["best_possible"].mean()), 2),
        "failure_years_tempo": int((v["score_pick"] == 0).sum()),
        "failure_years_current": int((v["score_A"] == 0).sum()),
        "years_tempo_better": better,
        "years_tempo_worse": worse,
        "picks": v["pick"].value_counts().to_dict(),
        "by_year": v.to_dict(orient="records"),
    }


def hindcast_years(validation: dict, hcdf: pd.DataFrame, pm: pd.DataFrame, worst_third: int,
                   years: list[int], evaluable: bool = True) -> list[dict]:
    """One row per year: leave-one-out pick, per-crop WRSI/class, and the D6 hit/fallo.

    hit/fallo only for years in config.VALIDATION_DROUGHT_YEARS (cited source, D6): "hit" when the
    primera maize WRSI ranks in the worst third of the record (same rule as CHECK 1), else "fallo".
    When CHECK 1 is not discriminative (most years tie at WRSI 100) every documented year is
    "no_evaluable": a tie cannot be a hit.
    """
    picks = {int(r["year"]): r for r in validation.get("by_year", [])}
    pmi = pm.set_index("year") if not pm.empty else pd.DataFrame()
    rows = []
    for y in years:
        crops_y = {}
        for parts in hcdf.loc[hcdf["year"] == y, "crops"]:
            for c, r in parts.items():
                crops_y.setdefault(c, {"wrsi": r["wrsi"], "class": r["class"]})
        pk = picks.get(y)
        prim = None
        if y in pmi.index:
            pr = pmi.loc[y]
            prim = {"wrsi": float(pr["wrsi"]), "class": pr["class"], "rank_driest": int(pr["rank_driest"])}
        source = config.VALIDATION_DROUGHT_YEARS.get(y)
        result = None
        if source is not None and not evaluable:
            result = "no_evaluable"
        elif source is not None:
            result = "hit" if prim is not None and prim["rank_driest"] <= worst_third else "fallo"
        rows.append({"year": int(y),
                     "strategy": pk["pick"] if pk else None,
                     "canicula_class": pk["canicula_class"] if pk else None,
                     "score_strategy": pk["score_pick"] if pk else None,
                     "score_current": pk["score_A"] if pk else None,
                     "crops": crops_y, "primera_maize": prim,
                     "documented": source is not None, "result": result, "source": source})
    return rows
# ---------------------------------------------------------------- rain source
# Rain windows compared between IMERG and POWER (same as the yearly indicators).
RAIN_WINDOWS = {"primera": ("05-01", "08-31"), "canicula": ("07-01", "08-31"),
                "sep_nov": ("09-01", "11-30")}


def _complete_years(hcdf: pd.DataFrame) -> list[int]:
    return sorted(hcdf.groupby("year")["complete"].all().loc[lambda s: s].index.tolist())


def _hindcast_picks(df: pd.DataFrame, crops: dict, whc: float) -> dict:
    indic = ind.yearly_indicators(df)
    hcdf = hc.run_hindcast(df, indic, crops, whc)
    return validate(hcdf, indic, _complete_years(hcdf))


def _primera_check(df: pd.DataFrame, indic: pd.DataFrame, crops: dict, whc: float) -> tuple[pd.DataFrame, dict]:
    """CHECK 1 on years before TARGET_YEAR: documented droughts in the worst third of primera maize WRSI."""
    pm = hc.primera_maize_check(df, indic.loc[history_years(indic.index)], crops, whc)
    doc = [y for y in sorted(config.VALIDATION_DROUGHT_YEARS) if not pm.empty and y in set(pm["year"])]
    third = max(1, round(len(pm) / 3)) if not pm.empty else 0
    ranks = pm.set_index("year")["rank_driest"] if not pm.empty else pd.Series(dtype=int)
    # CHECK 1 is only informative if the WRSI actually varies. Ties at 100 share the highest
    # rank, and the check is marked not evaluable when most years tie.
    discriminative = bool(not pm.empty and (pm["wrsi"] < 100.0).sum() >= len(pm) / 2)
    return pm, {
        "n_years": int(len(pm)), "worst_third_size": int(third), "documented": doc,
        "documented_in_worst_third": [int(y) for y in doc if int(ranks.loc[y]) <= third],
        "documented_rank": {str(y): int(ranks.loc[y]) for y in doc},
        "n_at_max_wrsi": int((pm["wrsi"] >= 100.0).sum()) if not pm.empty else 0,
        "discriminative": discriminative,
        "status": "evaluable" if discriminative else "no_evaluable",
        "rank_method": "max (ties take the highest rank; 1 = driest)",
    }


def _crops_without_bean_rule(crops: dict) -> dict:
    out = copy.deepcopy(crops)
    for c in out["crops"].values():
        c.pop("excess_rain_late_mm", None)
    return out


def parameter_sensitivity(df: pd.DataFrame, crops: dict, whc: float) -> dict:
    """Re-run the leave-one-out hindcast with other soil water capacities and without the bean
    excess-rain rule. Defaults are never changed here; this only reports how much the verdict
    depends on them. A "pick change" is a year whose LOO pick differs from the baseline run.
    """
    indic = ind.yearly_indicators(df)

    def run(c, w):
        hcdf = hc.run_hindcast(df, indic, c, w)
        v = validate(hcdf, indic, _complete_years(hcdf))
        _, pc = _primera_check(df, indic, c, w)
        return v, pc

    base_v, _ = run(crops, whc)
    base = {r["year"]: r for r in base_v.get("by_year", [])}
    variants = {f"whc_{w}": (crops, w) for w in SENSITIVITY_WHC_MM}
    variants["no_bean_excess_rule"] = (_crops_without_bean_rule(crops), whc)
    runs = {}
    for name, (c, w) in variants.items():
        v, pc = run(c, w)
        by = {r["year"]: r for r in v.get("by_year", [])}
        common = sorted(set(base) & set(by))
        changes = [{"year": int(y), "pick_baseline": base[y]["pick"], "pick": by[y]["pick"]}
                   for y in common if by[y]["pick"] != base[y]["pick"]]
        runs[name] = {
            "whc_mm": w, "bean_excess_rule": name != "no_bean_excess_rule",
            "n_years": v.get("n_years", 0), "n_years_compared": len(common),
            "pick_changes": changes, "n_pick_changes": len(changes),
            "picks": v.get("picks", {}), "n_years_pick_tied": v.get("n_years_pick_tied"),
            "mean_score_tempo": v.get("mean_score_tempo"),
            "mean_score_current": v.get("mean_score_current"),
            "mean_score_same_every_year": v.get("mean_score_same_every_year"),
            "mean_margin_vs_current": v.get("mean_margin_vs_current"),
            "years_tempo_better": v.get("years_tempo_better"),
            "years_tempo_worse": v.get("years_tempo_worse"),
            "sign_test_p": v.get("sign_test_p"),
            "check1": {k: pc[k] for k in ("n_at_max_wrsi", "n_years", "discriminative",
                                          "documented_rank", "documented_in_worst_third")},
        }
    return {
        "method": "leave-one-out hindcast re-run per variant; pick changes vs the baseline run",
        "baseline": {"whc_mm": whc,
                     "bean_excess_rain_late_mm": crops["crops"]["bean"].get("excess_rain_late_mm")},
        "runs": runs,
        "max_pick_changes": max(r["n_pick_changes"] for r in runs.values()),
    }


def rain_source_sensitivity(df_imerg: pd.DataFrame, df_power: pd.DataFrame,
                            crops: dict, whc: float) -> dict:
    """Compare IMERG and POWER rain per window and check whether the chosen strategy changes.

    Per window and year, totals are compared only when every day has IMERG (P_src == "IMERG")
    and POWER is complete. bias = POWER - IMERG; bias_pct is relative to the IMERG total.
    verdict_changes lists the years whose leave-one-out pick (validate) differs between a
    run with IMERG rain (POWER gap-filled, the default) and a run with POWER rain only.
    """
    if not (df_imerg["P_src"] == "IMERG").any():
        return {"available": False, "reason": "no IMERG days in cache (imerg.csv missing or empty)"}
    windows = {}
    for name, (a, b) in RAIN_WINDOWS.items():
        rows = []
        for y in history_years(set(df_imerg.index.year) & set(df_power.index.year)):
            wi = df_imerg.loc[f"{y}-{a}":f"{y}-{b}"]
            wp = df_power["P"].loc[f"{y}-{a}":f"{y}-{b}"]
            n_days = (pd.Timestamp(f"{y}-{b}") - pd.Timestamp(f"{y}-{a}")).days + 1
            if len(wi) < n_days or len(wp) < n_days or (wi["P_src"] != "IMERG").any() \
                    or wi["P"].isna().any() or wp.isna().any():
                continue
            rows.append({"year": int(y), "imerg_mm": round(float(wi["P"].sum()), 1),
                         "power_mm": round(float(wp.sum()), 1)})
        t = pd.DataFrame(rows, columns=["year", "imerg_mm", "power_mm"])
        if t.empty:
            windows[name] = {"months": f"{a}..{b}", "n_years": 0, "bias_mm": None, "bias_pct": None,
                             "spearman": None, "by_year": []}
            continue
        si = t["imerg_mm"].sum()
        rho = t["imerg_mm"].corr(t["power_mm"], method="spearman") if len(t) >= 3 else None
        windows[name] = {
            "months": f"{a}..{b}", "n_years": int(len(t)),
            "mean_imerg_mm": round(float(t["imerg_mm"].mean()), 1),
            "mean_power_mm": round(float(t["power_mm"].mean()), 1),
            "bias_mm": round(float((t["power_mm"] - t["imerg_mm"]).mean()), 1),
            "bias_pct": round(float(100 * (t["power_mm"].sum() - si) / si), 1) if si else None,
            "spearman": None if rho is None or pd.isna(rho) else round(float(rho), 2),
            "by_year": t.to_dict(orient="records"),
        }

    v_i, v_p = _hindcast_picks(df_imerg, crops, whc), _hindcast_picks(df_power, crops, whc)
    by_i = {r["year"]: r for r in v_i.get("by_year", [])}
    by_p = {r["year"]: r for r in v_p.get("by_year", [])}
    common = sorted(set(by_i) & set(by_p))
    changes = [{"year": int(y), "pick_imerg": by_i[y]["pick"], "pick_power": by_p[y]["pick"],
                "score_imerg": by_i[y]["score_pick"], "score_power": by_p[y]["score_pick"]}
               for y in common if by_i[y]["pick"] != by_p[y]["pick"]]
    return {
        "available": True,
        "convention": "bias = POWER - IMERG; bias_pct relative to IMERG; years with complete IMERG only",
        "windows": windows,
        "n_years_compared": len(common),
        "verdict_changes": changes,
        "n_verdict_changes": len(changes),
        "picks": {"imerg": v_i.get("picks", {}), "power": v_p.get("picks", {})},
        "mean_score_tempo": {"imerg": v_i.get("mean_score_tempo"), "power": v_p.get("mean_score_tempo")},
    }


# ---------------------------------------------------------------- robust recommendation (D10)
def season_scores(df: pd.DataFrame, crops: dict, whc: float, weights: dict, slope_pct: float | None,
                  year: int, keys: list[str]) -> dict[str, float]:
    """Final score per strategy for `year`, computed exactly like the strategy cards in build_zone
    (analog years of the same canícula tercile, history only), under the given rain/crops/soil."""
    indic = ind.yearly_indicators(df)
    if year not in indic.index:
        return {}
    hcdf = hc.run_hindcast(df, indic, crops, whc)
    complete = history_years(_complete_years(hcdf))
    if not complete:
        return {}
    _, analogs = hc.analog_years(year, indic, [y for y in complete if y != year] + [year])
    stats = hc.strategy_stats(hcdf, analogs)
    wd = mean_water_demand(hcdf, analogs or complete)
    out = {}
    for k in keys:
        st = stats.get(k)
        if st and st.get("mean_score") is not None:
            out[k] = final_score(st["mean_score"], strategy_attributes(k, crops, wd), weights, slope_pct)
    return out


def robust_pick(scenarios: dict[str, dict[str, float]]) -> dict | None:
    """Maximin over scenarios: the strategy whose lowest score across scenarios is highest.

    Only strategies scored in every scenario compete. Ties on the worst case go to the higher mean,
    then to the current practice (no change without margin), then alphabetical. Returns None when
    fewer than two strategies can be compared.
    """
    names = [n for n, s in scenarios.items() if s]
    if not names:
        return None
    keys = sorted(set.intersection(*(set(scenarios[n]) for n in names)))
    if len(keys) < 2:
        return None
    worst = {k: min(scenarios[n][k] for n in names) for k in keys}
    mean = {k: sum(scenarios[n][k] for n in names) / len(names) for k in keys}
    best_in = {n: max(scenarios[n][k] for k in keys) for n in names}
    regret = {k: max(best_in[n] - scenarios[n][k] for n in names) for k in keys}
    order = sorted(keys, key=lambda k: (-worst[k], -mean[k], k != CURRENT_PRACTICE, k))
    pick, second = order[0], order[1]
    wins = [n for n in names if scenarios[n][pick] >= best_in[n] - ROBUST_TIE]
    return {
        "pick": pick, "second": second,
        "worst": {k: round(worst[k], 3) for k in keys},
        "mean": {k: round(mean[k], 3) for k in keys},
        "max_regret": {k: round(regret[k], 3) for k in keys},
        "worst_margin": round(worst[pick] - worst[second], 3),
        "wins": wins, "n_wins": len(wins), "n_scenarios": len(names),
    }


def robust_confidence(rp: dict, rain_compared: bool, soil_measured: bool,
                      check1_ok: bool = True, strict_ok: bool = True,
                      base_margin: float | None = None) -> tuple[str, list[str]]:
    """Confidence label for a robust pick, with the reasons that capped it (D10 rev. 2, SUPUESTO).

    First gate: in the base scenario the pick must beat the next option by ROBUST_MARGIN; a smaller
    gap is "baja" (no real difference, so no reason to change practice).
    alta : best (or tied) in every scenario, worst case ahead of the runner-up by ROBUST_MARGIN,
           and the strict historical checks pass (no pick change without the 150 mm rule or with
           POWER instead of IMERG).
    media: never more than ROBUST_MARGIN behind the best option of any scenario.
    baja : otherwise. The pick is still the safest under the scenarios, and the reasons say why.
    Caps: without IMERG max baja; soil default, documented-drought check not evaluable, or strict
    checks failing: max media.
    """
    n, w = rp["n_scenarios"], rp["n_wins"]
    regret = rp["max_regret"][rp["pick"]]
    caps = []
    if base_margin is not None and base_margin < ROBUST_MARGIN:
        level = "baja"
        caps.append("margin")
    elif w == n and rp["worst_margin"] >= ROBUST_MARGIN:
        level = "alta"
    elif regret <= ROBUST_MARGIN:
        level = "media"
    else:
        level = "baja"
    if not strict_ok:
        caps.append("strict")
        if level == "alta":
            level = "media"
    if not rain_compared:
        caps.append("rain")
        level = "baja"
    if not soil_measured:
        caps.append("soil")
        if level == "alta":
            level = "media"
    if not check1_ok:
        caps.append("check1")
        if level == "alta":
            level = "media"
    return level, caps


def robust_recommendation(by_src: dict[str, pd.DataFrame], rain_compared: bool, crops: dict, whc: float,
                          weights: dict, slope_pct: float | None, year: int, keys: list[str],
                          soil_measured: bool, base_src: str = "imerg", check1_ok: bool = True,
                          strict_ok: bool = True) -> dict:
    """Scores of each strategy for `year` under the uncertainties the verdict already reports:
    rain source (IMERG or POWER), the 150 mm bean rule (with or without) and soil water capacity
    (SENSITIVITY_WHC_MM). Defaults never change; this only chooses the option that holds up best."""
    nb = _crops_without_bean_rule(crops)
    plan = [("base", base_src, crops, whc), ("no_bean_rule", base_src, nb, whc)]
    alt = "power" if base_src != "power" else "imerg"
    if rain_compared:
        plan += [(alt, alt, crops, whc), (f"{alt}_no_bean_rule", alt, nb, whc)]
    plan += [(f"whc_{w}", base_src, crops, w) for w in SENSITIVITY_WHC_MM if w != whc]
    scenarios, defs = {}, {}
    for name, src, c, w in plan:
        s = season_scores(by_src[src], c, w, weights, slope_pct, year, keys)
        if s:
            scenarios[name] = s
            defs[name] = {"rain": src, "bean_rule": c is crops, "whc_mm": w}
    rp = robust_pick(scenarios)
    if rp is None:
        return {"available": False, "reason": "fewer than two strategies scored in every scenario",
                "scenarios": scenarios, "scenario_defs": defs}
    base = scenarios.get("base") or {}
    others = [v for k, v in base.items() if k != rp["pick"]]
    base_margin = round(base[rp["pick"]] - max(others), 3) if rp["pick"] in base and others else None
    level, caps = robust_confidence(rp, rain_compared, soil_measured, check1_ok, strict_ok, base_margin)
    return {"available": True, "method": "maximin over scenarios (best worst-case score)",
            "tie": ROBUST_TIE, "margin": ROBUST_MARGIN, **rp, "base_margin": base_margin,
            "confidence": level, "confidence_caps": caps,
            "scenarios": scenarios, "scenario_defs": defs}


def current_season(hcdf: pd.DataFrame, crops: dict, year: int, last_day) -> list[dict]:
    """How the current postrera is going with MEASURED rain only (no forecast, no analogs).

    A strategy whose crops already reached harvest has a real simulated outcome for this year
    (water balance with observed rain; yields are not modeled). The others are still in the field:
    harvest date and days of data still missing are reported, never filled.
    """
    out = []
    rows = hcdf[hcdf["year"] == year]
    for r in rows.itertuples():
        harvest = pd.Timestamp(r.plant_date)
        ends = []
        for c in crops["strategies"][r.strategy]["crops"]:
            ini, dev, mid, late = crops["crops"][c]["stages_days"]
            ends.append(harvest + pd.Timedelta(days=ini + dev + mid + late))
        end = max(ends)
        missing = max(0, (end - pd.Timestamp(last_day)).days) if last_day is not None else None
        out.append({"strategy": r.strategy, "plant_date": r.plant_date, "harvest_date": end.date().isoformat(),
                    "complete": bool(r.complete), "score": r.score if r.complete else None,
                    "days_missing": None if r.complete else missing,
                    "crops": {c: {"wrsi": p["wrsi"], "class": p["class"]} for c, p in (r.crops or {}).items()}
                    if r.complete else {}})
    return out


def data_dates(df: pd.DataFrame, df_power: pd.DataFrame, meta: dict) -> dict:
    """Last observed day of each rain series and when the data was downloaded."""
    def last(s):
        i = s.last_valid_index()
        return _ts(i) if i is not None else None
    imerg_days = df.index[df["P_src"] == "IMERG"] if "P_src" in df.columns else []
    return {"rain_last_day": last(df["P"]),
            "imerg_last_day": _ts(imerg_days.max()) if len(imerg_days) else None,
            "power_last_day": last(df_power["P"]) if "P" in df_power.columns else None,
            "fetched_utc": (meta or {}).get("fetched_utc"),
            "weather_backup": ((meta or {}).get("weather_backup") or {}).get("source"),
            "requested_end": (meta or {}).get("end")}


# ---------------------------------------------------------------- per zone
def _ts(x):
    return None if x is None or (isinstance(x, float) and np.isnan(x)) or pd.isna(x) else pd.Timestamp(x).date().isoformat()


def build_zone(zone: config.Zone, weights: dict, seeds: set[str] | None,
               rain_source: str = "imerg") -> dict:
    crops = hc.load_crops()
    df, info = ind.load_zone(zone.key, rain_source)
    indic = ind.yearly_indicators(df)

    texture = info["soil"].get("texture_class") or "default"
    whc = crops["soil_whc_mm"].get(texture, crops["soil_whc_mm"]["default"])
    slope_pct = info["terrain"].get("slope_pct")

    by_src = {rain_source: df}
    for src in ind.RAIN_SOURCES:
        by_src.setdefault(src, ind.load_zone(zone.key, src)[0])
    sensitivity = rain_source_sensitivity(by_src["imerg"], by_src["power"], crops, whc)

    hcdf = hc.run_hindcast(df, indic, crops, whc)
    complete_years = history_years(_complete_years(hcdf))   # never TARGET_YEAR (D1)
    validation = validate(hcdf, indic, complete_years)
    sensitivity_params = parameter_sensitivity(df, crops, whc)

    # Does canicula length say anything about the postrera? (Spearman rank correlation)
    hist = hcdf[hcdf["complete"] & hcdf["year"].isin(history_years(hcdf["year"].unique()))]
    piv = hist.pivot(index="year", columns="strategy", values="score").astype(float)
    can = indic.loc[piv.index, "canicula_days"].astype(float)
    rain = indic.loc[piv.index, "rain_sep_nov_mm"].astype(float)
    def _sp(a, b):
        r = a.corr(b, method="spearman")
        return None if pd.isna(r) else round(float(r), 2)
    skill = {"n_years": int(len(piv)), "years": [int(y) for y in piv.index],
             "canicula_vs_sep_nov_rain": _sp(can, rain),
             "canicula_vs_score": {k: _sp(can, piv[k]) for k in piv.columns}}

    # External check: does the model see the documented primera droughts?
    pm, primera_check = _primera_check(df, indic, crops, whc)
    primera_check["years"] = pm.assign(documented=pm["year"].isin(list(config.VALIDATION_DROUGHT_YEARS))
                                       ).to_dict(orient="records") if not pm.empty else []
    third = primera_check["worst_third_size"]
    hindcast = {
        "method": "leave-one-out by canicula tercile; hit/fallo only for cited drought years (D6), "
                  "primera maize WRSI in the worst third (ties ranked max); no_evaluable when "
                  "CHECK 1 is not discriminative",
        "worst_third_size": int(third),
        "check1_status": primera_check["status"],
        "years": hindcast_years(validation, hcdf, pm, third,
                                list(range(int(config.START_DATE[:4]), config.TARGET_YEAR)),
                                evaluable=primera_check["discriminative"]),
    }

    # Current season = latest year with a canicula reading. Analogs come from history only.
    cur = int(indic.index.max())
    cls, analogs = hc.analog_years(cur, indic, [y for y in complete_years if y != cur] + [cur])
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
    margin = round(ranked[0]["score"] - ranked[1]["score"], 3) if len(ranked) > 1 else None
    robust = robust_recommendation(by_src, bool(sensitivity.get("available")), crops, whc, weights, slope_pct,
                                   cur, [c["key"] for c in cards if c["available"]],
                                   soil_measured=info["soil"].get("texture_class") is not None,
                                   base_src=rain_source,
                                   check1_ok=bool(primera_check.get("discriminative")),
                                   strict_ok=(sensitivity_params.get("max_pick_changes", 1) == 0
                                              and bool(sensitivity.get("available"))
                                              and sensitivity.get("n_verdict_changes", 1) == 0))

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
        card["rotation"] = segs
        card["bare_days"] = bare_days(segs)

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
                    "recommended": recommended, "margin_over_second": margin},
        "robust": robust,
        "current_season": current_season(hcdf, crops, cur, df["P"].last_valid_index()),
        "data_dates": data_dates(df, by_src["power"], info.get("meta") or {}),
        "strategies": cards,
        "validation": validation,
        "sensitivity": sensitivity_params,
        "skill": skill,
        "primera_check": primera_check,
        "hindcast": hindcast,
        "rain_source_sensitivity": sensitivity,
        "yearly": yearly,
        "chart": chart,
        "heat": heat,
        "postrera_planting": {"date": plant_cur.date().isoformat(), "late_default": bool(late_cur)},
        "warnings": info["warnings"],
        "inputs": {"rain_source": rain_source, "texture_class": texture, "whc_mm": whc, "slope_pct": slope_pct,
                   "weights": weights, "seeds": sorted(seeds) if seeds else None,
                   "temp_correction_c": info["temp_correction_c"],
                   "et0_change_vs_t2m_pct": info["et0_change_vs_t2m_pct"],
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
    print(f"  Rain source: {out['inputs']['rain_source']}  |  Rain days from IMERG: {100 * out['inputs']['share_days_imerg']:.0f}%  |  "
          f"temp correction {out['inputs']['temp_correction_c']} C  |  WHC {out['inputs']['whc_mm']} mm  |  "
          f"ET0 vs T2M {out['inputs']['et0_change_vs_t2m_pct']} %")
    for w in out["warnings"]:
        print(f"  WARNING: {w}")
    pc, sk = out["primera_check"], out["skill"]
    if not pc.get("discriminative", True):
        print(f"  CHECK 1 NO DISCRIMINANTE (no evaluable): {pc['n_at_max_wrsi']} of {pc['n_years']} years tie at WRSI 100")
    print(f"  CHECK 1 - documented droughts: {len(pc['documented_in_worst_third'])} of {len(pc['documented'])} "
          f"documented years fall in the model's worst {pc['worst_third_size']} of {pc['n_years']} primera years "
          f"({pc['documented_in_worst_third']} of {pc['documented']}; ranks {pc['documented_rank']}, ties = max)")
    print(f"  CHECK 2 - canicula as a signal (Spearman, n={sk['n_years']}): vs Sep-Nov rain {sk['canicula_vs_sep_nov_rain']}, "
          f"vs strategy score {sk['canicula_vs_score']}")
    if v.get("n_years"):
        print(f"  CHECK 3 - hindcast ({v['n_years']} years, leave-one-out, climate-only pick), mean score:")
        print(f"    Tempo {v['mean_score_tempo']} | current practice {v['mean_score_current']} | "
              f"same strategy every year {v['mean_score_same_every_year']} | perfect hindsight {v['mean_score_best_possible']}")
        print(f"    failure years: Tempo {v['failure_years_tempo']} vs current {v['failure_years_current']}; "
              f"Tempo better in {v['years_tempo_better']}, worse in {v['years_tempo_worse']}; picks {v['picks']}")
        print(f"    margin vs current {v['mean_margin_vs_current']} (sign test p {v['sign_test_p']}); "
              f"tied picks {v['n_years_pick_tied']}")
    for name, r in out["sensitivity"]["runs"].items():
        print(f"  SENSITIVITY {name}: pick changes {r['n_pick_changes']} of {r['n_years_compared']} "
              f"{[c['year'] for c in r['pick_changes']]}; Tempo {r['mean_score_tempo']} vs A "
              f"{r['mean_score_current']}; picks {r['picks']}; CHECK 1 discriminative {r['check1']['discriminative']}")
    rs = out["rain_source_sensitivity"]
    if rs.get("available"):
        for name, w in rs["windows"].items():
            print(f"  RAIN SOURCE {name}: n={w['n_years']} bias {w['bias_mm']} mm ({w['bias_pct']} %), "
                  f"Spearman IMERG vs POWER {w['spearman']}")
        print(f"  RAIN SOURCE verdict changes: {rs['n_verdict_changes']} of {rs['n_years_compared']} years "
              f"{[c['year'] for c in rs['verdict_changes']]}; picks {rs['picks']}")
    else:
        print(f"  RAIN SOURCE sensitivity not available: {rs.get('reason')}")
    print(f"  {out['current_year']}: canícula {c['canicula_days']} days ({c['canicula_class']}), "
          f"recommended {c['recommended']} (margin over second {c['margin_over_second']}), analogs {c['analog_years']}")
    for s in out["strategies"]:
        print(f"    [{s['key']}] {s['label']:<26} score {s['score']}  analog {s['analog_stats']}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--zones", help="comma-separated zone keys (default: all)")
    ap.add_argument("--seeds", help="comma-separated available seeds, e.g. maize,bean")
    ap.add_argument("--weights", help="e.g. food=1,income=0.5,soil=1,water=0.5,labor=0.3")
    ap.add_argument("--rain-source", choices=ind.RAIN_SOURCES, default="imerg",
                    help="imerg: IMERG with POWER gap fill (default); power: NASA POWER only")
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
        out = build_zone(z, weights, seeds, a.rain_source)
        with open(os.path.join(OUT_DIR, f"{z.key}.json"), "w") as f:
            json.dump(clean_json(out), f, indent=1, default=str, allow_nan=False)
        print_summary(out)


if __name__ == "__main__":
    main()
