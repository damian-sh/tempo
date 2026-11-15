"""Multi-site pipeline and index for the parcel browser (web/parcelas/).

    python build_parcels.py                      # web/parcelas/data.json from existing out/<id>.json
    python build_parcels.py --run                # per site: fetch (if cache missing) + engine, then build
    python build_parcels.py --run --ids somoto   # only these sites
    python build_parcels.py --run --refresh      # re-download even if the cache is there
    python build_parcels.py --run --no-gee       # POWER + SoilGrids only (IMERG/SRTM marked missing)

Sites come from parcelas.json (config.load_sites). Each site is isolated:
- cache:  <TEMPO_CACHE or ~/.cache/tempo>/<id>/ (written by fetch.py --sites ... --ids <id>)
- output: out/<id>.json (engine.build_zone, same defaults as engine.py)
- status: <cache>/<id>/pipeline.json (last run: fetch/engine result and error, if any)
A failure in one site is recorded and the next site still runs. Missing sources stay missing:
nothing is filled in here. Google Earth Engine only runs when TEMPO_GEE_PROJECT is set.

data.json lists the sites that have out/<id>.json ("parcelas") and the ones that do not
("pendientes"). Model parameters are not touched; every number is read from out/<id>.json.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import statistics
import subprocess
import sys

import config

HERE = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(HERE, "out")
WEB_DIR = os.path.join(HERE, "web", "parcelas")
DATA_JSON = os.path.join(WEB_DIR, "data.json")
COORD_TOL = 1e-6          # cache is reused only if its meta.json has the same point
SEASON_MARGIN = 0.05      # same threshold build_site.py uses for "lectura de temporada"
NAMES = {"A": "Frijol en relevo tras maíz (práctica actual)",
         "B": "Sorgo (maicillo) + frijol",
         "C": "Segunda maíz"}
DETAIL_PAGES = {"parcela": "../site/index.html"}  # build_site.py only renders the user's parcel


def _now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def _read(path: str):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


# ---------------------------------------------------------------- pipeline
def cache_dir(sid: str) -> str:
    return os.path.join(config.CACHE_DIR, sid)


def cache_state(site: dict) -> str:
    """'ok' (meta.json for this exact point), 'missing', or 'mismatch' (other point / broken)."""
    d = cache_dir(site["id"])
    if not os.path.isdir(d):
        return "missing"
    meta = _read(os.path.join(d, "meta.json"))
    if not meta or not os.path.exists(os.path.join(d, "power.csv")):
        return "mismatch"  # partial download: never mix it with a new one
    z = meta.get("zone", {})
    try:
        same = abs(float(z["lat"]) - float(site["lat"])) < COORD_TOL and \
            abs(float(z["lon"]) - float(site["lon"])) < COORD_TOL
    except (KeyError, TypeError, ValueError):
        same = False
    return "ok" if same else "mismatch"


def set_aside(sid: str) -> str | None:
    """Move an existing cache dir out of the way (never deleted) so old files are not reused."""
    d = cache_dir(sid)
    if not os.path.isdir(d):
        return None
    dst = f"{d}.anterior-{dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
    os.rename(d, dst)
    return dst


def run_fetch(sid: str, no_gee: bool) -> tuple[bool, str]:
    cmd = [sys.executable, os.path.join(HERE, "fetch.py"), "--sites", config.SITES_FILE, "--ids", sid]
    if no_gee:
        cmd.append("--no-gee")
    p = subprocess.run(cmd, cwd=HERE, capture_output=True, text=True)
    log = (p.stdout + p.stderr).strip()
    print("\n".join("    " + line for line in log.splitlines()[-12:]))
    return p.returncode == 0, log.splitlines()[-1] if log else ""


def run_engine(zone: config.Zone) -> tuple[bool, str]:
    import engine  # heavy imports only when the pipeline runs
    try:
        out = engine.build_zone(zone, dict(engine.DEFAULT_WEIGHTS), None, "imerg")
    except Exception as e:  # noqa: BLE001 - recorded per site, next site still runs
        return False, f"{type(e).__name__}: {e}"
    os.makedirs(OUT_DIR, exist_ok=True)
    tmp = os.path.join(OUT_DIR, f".{zone.key}.json.tmp")
    with open(tmp, "w") as f:
        json.dump(engine.clean_json(out), f, indent=1, default=str, allow_nan=False)
    os.replace(tmp, os.path.join(OUT_DIR, f"{zone.key}.json"))
    return True, ""


def run_pipeline(sites: list[dict], ids: set[str] | None, refresh: bool, no_gee: bool) -> None:
    zones = {z.key: z for z in config.site_zones(sites)}
    if not no_gee and not config.GEE_PROJECT:
        print("TEMPO_GEE_PROJECT no está definido: IMERG y SRTM quedan como faltantes en sitios nuevos.")
    for s in sites:
        sid = s["id"]
        if ids and sid not in ids:
            continue
        if sid not in zones:
            print(f"\n== {sid}: estado '{s.get('estado')}', no se procesa")
            continue
        print(f"\n== {sid} ({s['lat']}, {s['lon']})")
        status = {"id": sid, "utc": _now(), "fetch": None, "engine": None, "error": None}
        state = cache_state(s)
        if refresh or state != "ok":
            moved = set_aside(sid)
            if moved:
                print(f"  caché anterior ({state}) movida a {moved}")
            print("  fetch ...")
            ok, msg = run_fetch(sid, no_gee)
            status["fetch"] = "ok" if ok else "fallo"
            if not ok:
                status["error"] = f"fetch: {msg}"
        else:
            status["fetch"] = "caché"
            print(f"  caché reutilizada: {cache_dir(sid)}")
        if status["fetch"] != "fallo":
            print("  engine ...")
            ok, msg = run_engine(zones[sid])
            status["engine"] = "ok" if ok else "fallo"
            if not ok:
                status["error"] = f"engine: {msg}"
        if os.path.isdir(cache_dir(sid)):
            with open(os.path.join(cache_dir(sid), "pipeline.json"), "w") as f:
                json.dump(status, f, indent=2)
        print(f"  -> fetch {status['fetch']}, engine {status['engine']}"
              + (f", error: {status['error']}" if status["error"] else ""))


# ---------------------------------------------------------------- summary
def _num(x, nd=1):
    return None if x is None else round(float(x), nd)


def season_reading(d: dict) -> dict:
    """Same honesty rule as build_site.py, plus the dominant-strategy check from README."""
    scores = {s["key"]: s["score"] for s in d["strategies"] if s.get("score") is not None}
    reasons = []
    margin = None
    top = max(scores, key=scores.get) if scores else None
    if len(scores) >= 2:
        vals = sorted(scores.values())
        margin = round(vals[-1] - vals[-2], 3)
        if margin < SEASON_MARGIN:
            spread = f"{vals[-1] - vals[0]:.2f}".replace(".", ",")
            reasons.append(f"Las estrategias quedan a menos de {spread} puntos entre sí; "
                           f"la primera supera a la segunda por menos de {SEASON_MARGIN:.2f}".replace(".", ",", 1)
                           + ".")
    else:
        reasons.append("No hay suficientes estrategias con puntaje para ordenar.")
    v = d.get("validation", {})
    if v.get("n_years") and v.get("mean_score_tempo") is not None \
            and v["mean_score_tempo"] <= v.get("mean_score_same_every_year", -1):
        reasons.append("En la validación 2001–2025, elegir siempre la misma estrategia empata o supera a Tempo.")
    lectura = bool(reasons)
    if lectura:
        title = f"No hay una estrategia claramente mejor en {d.get('current_year')}: lectura de temporada, no una recomendación fuerte"
    else:
        title = f"Ventaja para {NAMES.get(top, top).lower()}"
    return {"lectura_temporada": lectura, "titulo": title, "razones": reasons,
            "mejor": top, "margen": margin, "puntajes": scores}


def rain_summary(d: dict) -> dict:
    cur = d.get("current_year")
    past = [y for y in d.get("yearly", []) if y["year"] < cur]
    now = next((y for y in d.get("yearly", []) if y["year"] == cur), {})

    def med(k):
        vals = [y[k] for y in past if y.get(k) is not None]
        return _num(statistics.median(vals)) if vals else None
    inp = d.get("inputs", {})
    rs = d.get("rain_source_sensitivity", {})
    return {"fuente": inp.get("rain_source"),
            "dias_imerg_pct": _num(100 * inp["share_days_imerg"], 0) if inp.get("share_days_imerg") is not None else None,
            "imerg_disponible": bool(rs.get("available")),
            "sep_nov_mediana_mm": med("rain_sep_nov_mm"),
            "jul_ago_mediana_mm": med("rain_jul_aug_mm"),
            "sep_nov_actual_mm": _num(now.get("rain_sep_nov_mm")),
            "jul_ago_actual_mm": _num(now.get("rain_jul_aug_mm")),
            "anios": [past[0]["year"], past[-1]["year"]] if past else None,
            "canicula_dias": d.get("current", {}).get("canicula_days"),
            "canicula_clase": d.get("current", {}).get("canicula_class"),
            "inicio_postrera": d.get("current", {}).get("postrera_onset"),
            "cambios_por_fuente": rs.get("n_verdict_changes") if rs.get("available") else None,
            "anios_comparados": rs.get("n_years_compared") if rs.get("available") else None}


def soil_summary(d: dict) -> dict:
    inp = d.get("inputs", {})
    soil = inp.get("soil") or {}
    val = lambda k: (soil.get(k) or {}).get("value_0_30cm") if isinstance(soil.get(k), dict) else None
    return {"textura": soil.get("texture_class"), "clase_usada": inp.get("texture_class"),
            "whc_mm": inp.get("whc_mm"), "arcilla_pct": val("clay"), "arena_pct": val("sand"),
            "limo_pct": val("silt"), "carbono_g_kg": val("soc"),
            "error": soil.get("error"), "fuente": soil.get("source")}


def missing_sources(d: dict) -> list[str]:
    inp = d.get("inputs", {})
    out = []
    if not d.get("rain_source_sensitivity", {}).get("available"):
        out.append("IMERG (lluvia satelital): no descargada; lluvia 100 % NASA POWER")
    terrain = inp.get("terrain") or {}
    if terrain.get("elevation_m") is None:
        out.append("SRTM (elevación): sin dato; temperatura sin corrección por elevación")
    if terrain.get("slope_pct") is None:
        out.append("SRTM (pendiente): sin dato")
    soil = inp.get("soil") or {}
    if soil.get("error") or not soil.get("texture_class"):
        out.append("SoilGrids (suelo): sin dato; capacidad de agua por defecto")
    return out


def summarize(site: dict, d: dict, mtime: float) -> dict:
    c, v, pc = d.get("current", {}), d.get("validation", {}), d.get("primera_check", {})
    return {
        **{k: site.get(k) for k in ("id", "nombre", "municipio", "departamento", "pais", "lat", "lon",
                                     "fuente_coordenadas", "fuente_admin", "estado")},
        "coordenada_supuesta": str(site.get("fuente_coordenadas", "")).startswith("SUPUESTO"),
        "datos": "parcial" if missing_sources(d) else "completo",
        "out": f"../../out/{site['id']}.json",
        "detalle": DETAIL_PAGES.get(site["id"]),
        "generado_utc": dt.datetime.fromtimestamp(mtime, dt.timezone.utc).isoformat(timespec="seconds"),
        "anio": d.get("current_year"),
        "veredicto": season_reading(d),
        "semaforo": c.get("traffic_light"),
        "recomendada": c.get("recommended"),
        "validacion": {"anios": v.get("n_years"), "tempo": v.get("mean_score_tempo"),
                       "practica_actual": v.get("mean_score_current"),
                       "misma_siempre": v.get("mean_score_same_every_year")},
        "check1_discriminante": pc.get("discriminative"),
        "lluvia": rain_summary(d),
        "suelo": soil_summary(d),
        "terreno": {k: (d.get("inputs", {}).get("terrain") or {}).get(k)
                    for k in ("elevation_m", "slope_pct", "source")},
        "faltantes": missing_sources(d),
        "advertencias": d.get("warnings", []),
    }


def build(sites: list[dict]) -> dict:
    parcelas, pendientes = [], []
    for s in sites:
        p = os.path.join(OUT_DIR, f"{s['id']}.json")
        d = _read(p)
        if d is None:
            st = _read(os.path.join(cache_dir(s["id"]), "pipeline.json")) or {}
            reason = st.get("error") or ("no procesado (estado " + str(s.get("estado")) + ")"
                                         if s.get("estado") != "activo" else "sin out/<id>.json: falta correr el pipeline")
            pendientes.append({**{k: s.get(k) for k in ("id", "nombre", "municipio", "departamento", "pais",
                                                         "lat", "lon", "fuente_coordenadas", "estado")},
                               "coordenada_supuesta": str(s.get("fuente_coordenadas", "")).startswith("SUPUESTO"),
                               "motivo": reason})
            continue
        parcelas.append(summarize(s, d, os.path.getmtime(p)))
    return {"generado_utc": _now(), "fuente": "parcelas.json + out/<id>.json",
            "parcelas": parcelas, "pendientes": pendientes}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", action="store_true", help="fetch (if needed) and run the engine per site first")
    ap.add_argument("--ids", help="comma-separated site ids (default: all active)")
    ap.add_argument("--refresh", action="store_true", help="re-download even if the cache matches")
    ap.add_argument("--no-gee", action="store_true", help="skip IMERG/SRTM (marked missing)")
    a = ap.parse_args()
    sites = config.load_sites()
    if a.run:
        run_pipeline(sites, set(a.ids.split(",")) if a.ids else None, a.refresh, a.no_gee)
    data = build(sites)
    os.makedirs(WEB_DIR, exist_ok=True)
    with open(DATA_JSON, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1, allow_nan=False)
    print(f"\n{os.path.relpath(DATA_JSON, HERE)}: {len(data['parcelas'])} con datos, "
          f"{len(data['pendientes'])} pendientes")
    for p in data["parcelas"]:
        v = p["veredicto"]
        print(f"  [{p['datos']}] {p['id']}: {v['titulo']} (mejor {v['mejor']}, margen {v['margen']})"
              + (f"; faltan: {len(p['faltantes'])}" if p["faltantes"] else ""))
    for p in data["pendientes"]:
        print(f"  [pendiente] {p['id']}: {p['motivo']}")


if __name__ == "__main__":
    main()
