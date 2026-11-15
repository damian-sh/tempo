"""Fetch and cache all point data Tempo needs.

Sources
- NASA POWER daily API (no auth): temperature, humidity, radiation, precipitation (backup).
- ISRIC SoilGrids v2 API (no auth): clay, sand, silt, soil organic carbon, 0-30 cm.
- Google Earth Engine (optional, needs a registered project):
    * GPM IMERG V07 half-hourly -> local-day precipitation totals
    * SRTM GL1 30 m -> parcel elevation and slope

Usage
    python fetch.py                 # all zones in config.ZONES
    python fetch.py --lat 13.7 --lon -88.13 --key myparcel
    python fetch.py --no-gee        # POWER + SoilGrids only

Output: ~/.cache/tempo/<zone>/power.csv, precip_power.json, imerg.csv, soil.json, terrain.json,
meta.json (outside the repo; override with TEMPO_CACHE)
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import time

import pandas as pd
import requests

import config

POWER_URL = "https://power.larc.nasa.gov/api/temporal/daily/point"
POWER_PARAMS = ["T2M", "T2M_MAX", "T2M_MIN", "RH2M", "ALLSKY_SFC_SW_DWN", "PRECTOTCORR"]
POWER_FILL = -999.0
POWER_RAIN = "PRECTOTCORR"
assert POWER_RAIN in POWER_PARAMS

SOILGRIDS_URL = "https://rest.isric.org/soilgrids/v2.0/properties/query"
SOIL_PROPS = ["clay", "sand", "silt", "soc"]
SOIL_DEPTHS = {"0-5cm": 5, "5-15cm": 10, "15-30cm": 15}  # label -> thickness (cm)


# --------------------------------------------------------------------------- helpers
def _end_date() -> str:
    if config.END_DATE:
        return config.END_DATE
    return (dt.date.today() - dt.timedelta(days=1)).isoformat()


def _get(url: str, params, retries: int = 4, timeout: int = 120) -> dict:
    last = None
    for attempt in range(retries):
        try:
            r = requests.get(url, params=params, timeout=timeout)
            if r.status_code == 200:
                return r.json()
            last = f"HTTP {r.status_code}: {r.text[:300]}"
        except requests.RequestException as e:  # network hiccup
            last = str(e)
        time.sleep(2 ** attempt)
    raise RuntimeError(f"Request failed after {retries} tries: {url}\n{last}")


# --------------------------------------------------------------------------- POWER
def parse_power(payload: dict) -> tuple[pd.DataFrame, float | None]:
    """Turn a POWER daily JSON payload into a DataFrame (index = date)."""
    params = payload["properties"]["parameter"]
    df = pd.DataFrame(params)
    df.index = pd.to_datetime(df.index, format="%Y%m%d")
    df = df.replace(POWER_FILL, float("nan")).sort_index()
    coords = payload.get("geometry", {}).get("coordinates", [])
    cell_elev = float(coords[2]) if len(coords) >= 3 else None  # POWER grid-cell elevation
    return df, cell_elev


def fetch_power(lat: float, lon: float, start: str, end: str) -> tuple[pd.DataFrame, float | None]:
    """Fetch in 5-year chunks to keep each request small."""
    s, e = pd.Timestamp(start), pd.Timestamp(end)
    frames, cell_elev = [], None
    cur = s
    while cur <= e:
        chunk_end = min(pd.Timestamp(year=cur.year + 4, month=12, day=31), e)
        payload = _get(POWER_URL, {
            "parameters": ",".join(POWER_PARAMS),
            "community": "AG",
            "latitude": lat,
            "longitude": lon,
            "start": cur.strftime("%Y%m%d"),
            "end": chunk_end.strftime("%Y%m%d"),
            "format": "JSON",
        })
        df, elev = parse_power(payload)
        frames.append(df)
        cell_elev = cell_elev if cell_elev is not None else elev
        cur = chunk_end + pd.Timedelta(days=1)
    out = pd.concat(frames)
    out = out[~out.index.duplicated()]
    out.index.name = "date"
    return out, cell_elev


def power_precip_json(power: pd.DataFrame) -> dict:
    """Compact daily POWER rain cache: start date plus one value (mm, as served) per day, null = missing."""
    p = power[POWER_RAIN]
    idx = pd.date_range(p.index.min(), p.index.max(), freq="D")
    p = p.reindex(idx)
    return {"source": f"NASA POWER daily, community AG, {POWER_RAIN}", "units": "mm/day",
            "start": idx[0].date().isoformat(), "end": idx[-1].date().isoformat(),
            "values": [None if pd.isna(v) else float(v) for v in p.values]}


# --------------------------------------------------------------------------- SoilGrids
def parse_soilgrids(payload: dict) -> dict:
    """Thickness-weighted 0-30 cm mean for each property, in conventional units."""
    out = {}
    for layer in payload["properties"]["layers"]:
        name = layer["name"]
        d_factor = layer.get("unit_measure", {}).get("d_factor", 1) or 1
        units = layer.get("unit_measure", {}).get("target_units", "")
        num, den = 0.0, 0.0
        for d in layer["depths"]:
            thick = SOIL_DEPTHS.get(d["label"])
            val = d["values"].get("mean")
            if thick is None or val is None:
                continue
            num += (val / d_factor) * thick
            den += thick
        out[name] = {"value_0_30cm": round(num / den, 2) if den else None, "units": units}
    return out


def fetch_soilgrids(lat: float, lon: float) -> dict:
    params = [("lon", lon), ("lat", lat), ("value", "mean")]
    params += [("property", p) for p in SOIL_PROPS]
    params += [("depth", d) for d in SOIL_DEPTHS]
    return parse_soilgrids(_get(SOILGRIDS_URL, params))


def texture_class(clay_pct: float | None, sand_pct: float | None) -> str | None:
    """Coarse texture class used by the decision engine (not the full USDA triangle)."""
    if clay_pct is None or sand_pct is None:
        return None
    if clay_pct >= 35:
        return "clayey"
    if sand_pct >= 60:
        return "sandy"
    return "loamy"


# --------------------------------------------------------------------------- Earth Engine
def gee_init() -> bool:
    if not config.GEE_PROJECT:
        print("  [GEE] no project set in config.GEE_PROJECT -> skipping IMERG/SRTM")
        return False
    try:
        import ee
        try:
            ee.Initialize(project=config.GEE_PROJECT)
        except Exception:
            ee.Authenticate()
            ee.Initialize(project=config.GEE_PROJECT)
        return True
    except Exception as e:
        print(f"  [GEE] init failed ({e}) -> skipping IMERG/SRTM")
        return False


def fetch_imerg_year(lat: float, lon: float, year: int, end: str) -> pd.DataFrame:
    """Daily precipitation (mm) for one year, aggregated by LOCAL calendar day.

    IMERG V07 half-hourly 'precipitation' is a rate in mm/hr, so each image
    contributes rate * 0.5 h. Local day d spans [d 00:00 local, d+1 00:00 local).
    """
    import ee

    point = ee.Geometry.Point([lon, lat])
    coll = ee.ImageCollection("NASA/GPM_L3/IMERG_V07").select("precipitation")
    offset_h = -config.LOCAL_UTC_OFFSET_HOURS  # local midnight = 06:00 UTC for UTC-6

    first = dt.date(year, 1, 1)
    last = min(dt.date(year, 12, 31), dt.date.fromisoformat(end))
    n_days = (last - first).days + 1
    start_utc = ee.Date(f"{first.isoformat()}T00:00:00", "UTC").advance(offset_h, "hour")

    def daily(i):
        d0 = start_utc.advance(ee.Number(i), "day")
        d1 = d0.advance(1, "day")
        day_coll = coll.filterDate(d0, d1)
        # Empty day (no granules) -> band-less sum() breaks multiply; use a 0-band-safe constant.
        full = day_coll.sum().multiply(0.5).rename("p_mm")
        empty = ee.Image.constant(0).rename("p_mm").updateMask(ee.Image.constant(0))
        img = ee.Image(ee.Algorithms.If(day_coll.size().gt(0), full, empty))
        return img.set({"system:time_start": d0.millis(), "n_images": day_coll.size()})

    daily_coll = ee.ImageCollection(ee.List.sequence(0, n_days - 1).map(daily))

    def to_feature(img):
        val = img.reduceRegion(ee.Reducer.first(), point, 11132).get("p_mm")
        return ee.Feature(None, {"t": img.get("system:time_start"),
                                 "p_mm": val, "n": img.get("n_images")})

    feats = daily_coll.map(to_feature).getInfo()["features"]
    rows = []
    for f in feats:
        p = f["properties"]
        # Local date = UTC start shifted back by the offset.
        local = (dt.datetime.utcfromtimestamp(p["t"] / 1000) - dt.timedelta(hours=offset_h)).date()
        complete = p.get("n", 0) == 48
        rows.append({"date": pd.Timestamp(local),
                     "imerg_mm": p.get("p_mm") if complete else None,
                     "imerg_halfhours": p.get("n", 0)})
    return pd.DataFrame(rows).set_index("date")


def fetch_imerg(lat: float, lon: float, start: str, end: str) -> pd.DataFrame:
    frames = []
    for year in range(pd.Timestamp(start).year, pd.Timestamp(end).year + 1):
        print(f"    IMERG {year} ...", end=" ", flush=True)
        df = fetch_imerg_year(lat, lon, year, end)
        print(f"{df['imerg_mm'].notna().sum()} complete days")
        frames.append(df)
    return pd.concat(frames)


def fetch_terrain(lat: float, lon: float) -> dict:
    """SRTM elevation at the parcel and mean slope in a 150 m radius."""
    import ee

    dem = ee.Image("USGS/SRTMGL1_003").select("elevation")
    slope = ee.Terrain.slope(dem)
    pt = ee.Geometry.Point([lon, lat])
    elev = dem.reduceRegion(ee.Reducer.first(), pt, 30).get("elevation").getInfo()
    slope_mean = slope.reduceRegion(ee.Reducer.mean(), pt.buffer(150), 30).get("slope").getInfo()
    return {"elevation_m": elev,
            "slope_deg": round(slope_mean, 2) if slope_mean is not None else None,
            "slope_pct": round(100 * __import__("math").tan(__import__("math").radians(slope_mean)), 1)
            if slope_mean is not None else None,
            "source": "SRTM GL1 v003 (USGS/SRTMGL1_003) via Google Earth Engine"}


# --------------------------------------------------------------------------- main
def run_zone(zone: config.Zone, use_gee: bool) -> None:
    end = _end_date()
    out_dir = os.path.join(config.CACHE_DIR, zone.key)
    os.makedirs(out_dir, exist_ok=True)
    print(f"\n== {zone.key}: {zone.name} ({zone.lat}, {zone.lon})")

    meta = {"zone": zone.__dict__, "start": config.START_DATE, "end": end,
            "fetched_utc": dt.datetime.utcnow().isoformat(timespec="seconds"),
            "local_utc_offset_h": config.LOCAL_UTC_OFFSET_HOURS, "sources": {}}

    print("  POWER ...")
    power, cell_elev = fetch_power(zone.lat, zone.lon, config.START_DATE, end)
    power.to_csv(os.path.join(out_dir, "power.csv"))
    with open(os.path.join(out_dir, "precip_power.json"), "w") as f:
        json.dump(power_precip_json(power), f, separators=(",", ":"))
    meta["power_cell_elevation_m"] = cell_elev
    meta["sources"]["power"] = f"NASA POWER daily, community AG, params {POWER_PARAMS}"
    print(f"    {len(power)} days, cell elevation {cell_elev} m")

    print("  SoilGrids ...")
    try:
        soil = fetch_soilgrids(zone.lat, zone.lon)
        soil["texture_class"] = texture_class(soil.get("clay", {}).get("value_0_30cm"),
                                              soil.get("sand", {}).get("value_0_30cm"))
        soil["source"] = "ISRIC SoilGrids v2.0, mean, thickness-weighted 0-30 cm"
    except RuntimeError as e:
        print(f"    SoilGrids failed: {e}")
        soil = {"error": str(e)}
    with open(os.path.join(out_dir, "soil.json"), "w") as f:
        json.dump(soil, f, indent=2)

    if use_gee:
        print("  IMERG (GEE) ...")
        imerg = fetch_imerg(zone.lat, zone.lon, config.START_DATE, end)
        imerg.to_csv(os.path.join(out_dir, "imerg.csv"))
        meta["sources"]["imerg"] = "GPM IMERG V07 half-hourly (NASA/GPM_L3/IMERG_V07), summed by local day"
        print("  SRTM (GEE) ...")
        terrain = fetch_terrain(zone.lat, zone.lon)
    else:
        terrain = {"elevation_m": zone.parcel_elevation_m, "slope_deg": None, "slope_pct": None,
                   "source": "manual" if zone.parcel_elevation_m else "unavailable"}
        meta["sources"]["imerg"] = "not fetched; precipitation falls back to POWER PRECTOTCORR"
    with open(os.path.join(out_dir, "terrain.json"), "w") as f:
        json.dump(terrain, f, indent=2)

    with open(os.path.join(out_dir, "meta.json"), "w") as f:
        json.dump(meta, f, indent=2)
    print(f"  saved to {out_dir}/")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--lat", type=float)
    ap.add_argument("--lon", type=float)
    ap.add_argument("--key", default="custom")
    ap.add_argument("--no-gee", action="store_true")
    args = ap.parse_args()

    zones = config.ZONES
    if args.lat is not None and args.lon is not None:
        zones = [config.Zone(args.key, args.key, args.lat, args.lon)]

    use_gee = (not args.no_gee) and gee_init()
    for z in zones:
        run_zone(z, use_gee)


if __name__ == "__main__":
    main()
