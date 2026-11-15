"""Fetch and cache all point data Tempo needs.

Sources
- NASA POWER daily API (no auth): temperature, humidity, radiation, precipitation (backup).
- Meteomatics API (credentials in .env): backup for temperature, humidity and rain when POWER fails.
- ISRIC SoilGrids v2 API (no auth): clay, sand, silt, soil organic carbon, 0-30 cm.
- Google Earth Engine (optional, needs a registered project):
    * GPM IMERG V07 half-hourly -> local-day precipitation totals
    * SRTM GL1 30 m -> parcel elevation and slope

Usage
    python fetch.py                 # all zones in config.ZONES
    python fetch.py --lat 13.7 --lon -88.13 --key myparcel
    python fetch.py --no-gee        # POWER + SoilGrids only
    python fetch.py --sites parcelas.json --ids somoto   # points from a registry file

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


# --------------------------------------------------------------------------- Meteomatics (respaldo)
METEOMATICS_URL = "https://api.meteomatics.com"
# Meteomatics parameter -> POWER column it replaces (same units: mm/day, degC, %).
METEOMATICS_PARAMS = {"precip_24h:mm": "PRECTOTCORR", "t_max_2m_24h:C": "T2M_MAX",
                      "t_min_2m_24h:C": "T2M_MIN", "t_mean_2m_24h:C": "T2M",
                      "relative_humidity_mean_2m_24h:p": "RH2M"}
METEOMATICS_SOURCE = ("Meteomatics API (precip_24h, t_max/t_min/t_mean_2m_24h, relative_humidity_mean_2m_24h), "
                      "local day UTC-6; backup because NASA POWER did not respond")


def meteomatics_available(today: dt.date | None = None) -> tuple[bool, str | None]:
    """(True, None) when credentials exist and the account has not expired."""
    if not (config.METEOMATICS_USER and config.METEOMATICS_PASSWORD):
        return False, "Meteomatics sin credenciales (METEOMATICS_USER/METEOMATICS_PASSWORD)"
    if config.METEOMATICS_VALID_UNTIL:
        try:
            until = dt.date.fromisoformat(config.METEOMATICS_VALID_UNTIL)
        except ValueError:
            return False, "METEOMATICS_VALID_UNTIL no es una fecha AAAA-MM-DD"
        if (today or dt.date.today()) > until:
            return False, f"cuenta Meteomatics vencida el {until.isoformat()}"
    return True, None


def parse_meteomatics(payload: dict, offset_h: int = config.LOCAL_UTC_OFFSET_HOURS) -> tuple[pd.DataFrame, float | None]:
    """Meteomatics JSON -> DataFrame with POWER column names, indexed by LOCAL calendar day.

    A 24 h value stamped at T covers (T-24h, T]. Requests are stamped at local midnight in UTC, so the
    value stamped at day d+1 06:00Z (UTC-6) is local day d.
    """
    if payload.get("status") != "OK":
        raise RuntimeError(f"Meteomatics status {payload.get('status')}: {payload.get('message')}")
    cols, elev = {}, None
    for block in payload.get("data", []):
        dates = block["coordinates"][0]["dates"]
        if block["parameter"] == "elevation:m":
            vals = [d["value"] for d in dates if d.get("value") is not None]
            elev = float(vals[0]) if vals else None
            continue
        col = METEOMATICS_PARAMS.get(block["parameter"])
        if col is None:
            continue
        s = {}
        for d in dates:
            t = pd.Timestamp(d["date"]).tz_convert(None) + pd.Timedelta(hours=offset_h)
            v = d.get("value")
            # -999 is Meteomatics' "no data"
            s[(t - pd.Timedelta(days=1)).normalize()] = None if v is None or v <= -999 else float(v)
        cols[col] = pd.Series(s, dtype=float)
    df = pd.DataFrame(cols).sort_index()
    df.index.name = "date"
    df["ALLSKY_SFC_SW_DWN"] = float("nan")   # not requested; the engine does not use it
    return df[[c for c in POWER_PARAMS if c in df.columns]], elev


def fetch_meteomatics(lat: float, lon: float, start: str, end: str,
                      retries: int = 2, timeout: int = 90) -> tuple[pd.DataFrame, float | None]:
    """Daily temperature, humidity and rain from Meteomatics, same shape as fetch_power."""
    ok, why = meteomatics_available()
    if not ok:
        raise RuntimeError(why)
    offset = -config.LOCAL_UTC_OFFSET_HOURS
    params = ",".join([*METEOMATICS_PARAMS, "elevation:m"])
    s, e = pd.Timestamp(start), pd.Timestamp(end)
    frames, elev, cur = [], None, s
    while cur <= e:
        chunk_end = min(pd.Timestamp(year=cur.year + 4, month=12, day=31), e)
        t0 = (cur + pd.Timedelta(days=1, hours=offset)).strftime("%Y-%m-%dT%H:%M:%SZ")
        t1 = (chunk_end + pd.Timedelta(days=1, hours=offset)).strftime("%Y-%m-%dT%H:%M:%SZ")
        url = f"{METEOMATICS_URL}/{t0}--{t1}:P1D/{params}/{lat},{lon}/json"
        last = None
        for attempt in range(retries):
            try:
                r = requests.get(url, auth=(config.METEOMATICS_USER, config.METEOMATICS_PASSWORD), timeout=timeout)
                if r.status_code == 200:
                    df, el = parse_meteomatics(r.json())
                    break
                last = f"HTTP {r.status_code}"   # the body may echo the request; keep it out of logs
            except (requests.RequestException, ValueError) as ex:
                last = type(ex).__name__
            time.sleep(2 ** attempt)
        else:
            raise RuntimeError(f"Meteomatics no respondió ({last})")
        frames.append(df)
        elev = elev if elev is not None else el
        cur = chunk_end + pd.Timedelta(days=1)
    out = pd.concat(frames)
    return out[~out.index.duplicated()], elev


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
    # Plazo corto: si la API de ISRIC no responde, el servidor pasa a los mismos mapas en Earth Engine.
    return parse_soilgrids(_get(SOILGRIDS_URL, params, retries=3, timeout=40))


SOILGRIDS_GEE = "projects/soilgrids-isric/{prop}_mean"   # same SoilGrids v2.0 maps, served by Earth Engine
SOILGRIDS_GEE_RADII_M = (0, 1000, 2000)                    # point first, then the mean of the surroundings
SOIL_D_FACTOR = {"clay": 10, "sand": 10, "silt": 10, "soc": 10}   # g/kg -> %, dg/kg -> g/kg
SOIL_UNITS = {"clay": "%", "sand": "%", "silt": "%", "soc": "g/kg"}


def fetch_soilgrids_gee(lat: float, lon: float) -> dict:
    """SoilGrids v2.0 from Earth Engine, used when the ISRIC REST API fails or has no value.

    The exact 250 m cell first; if it has no data (towns, water bodies), the mean of the cells
    within 1 km, then 2 km. The radius used is recorded so the page can say so. Raises when no
    radius has data or Earth Engine is not available.
    """
    import ee

    pt = ee.Geometry.Point([lon, lat])
    bands = lambda p: [f"{p}_{d}_mean" for d in SOIL_DEPTHS]
    for radius in SOILGRIDS_GEE_RADII_M:
        geom, red = (pt, ee.Reducer.first()) if radius == 0 else (pt.buffer(radius), ee.Reducer.mean())
        out = {}
        for p in SOIL_PROPS:
            vals = ee.Image(SOILGRIDS_GEE.format(prop=p)).select(bands(p)).reduceRegion(red, geom, 250).getInfo()
            num = den = 0.0
            for d, thick in SOIL_DEPTHS.items():
                v = vals.get(f"{p}_{d}_mean")
                if v is None:
                    continue
                num += (v / SOIL_D_FACTOR[p]) * thick
                den += thick
            out[p] = {"value_0_30cm": round(num / den, 2) if den else None, "units": SOIL_UNITS[p]}
        if out["clay"]["value_0_30cm"] is not None and out["sand"]["value_0_30cm"] is not None:
            out["radius_m"] = radius
            return out
    raise RuntimeError("SoilGrids sin dato en el punto ni en 2 km a la redonda")


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
    ap.add_argument("--sites", help="JSON file with a list of points (e.g. parcelas.json); "
                                    "fetches every entry with estado 'activo'")
    ap.add_argument("--ids", help="with --sites: comma-separated ids to fetch (default: all active)")
    args = ap.parse_args()

    zones = config.ZONES
    if args.sites:
        zones = config.site_zones(config.load_sites(args.sites))
        if args.ids:
            wanted = set(args.ids.split(","))
            zones = [z for z in zones if z.key in wanted]
    if args.lat is not None and args.lon is not None:
        zones = [config.Zone(args.key, args.key, args.lat, args.lon)]

    use_gee = (not args.no_gee) and gee_init()
    for z in zones:
        run_zone(z, use_gee)


if __name__ == "__main__":
    main()
