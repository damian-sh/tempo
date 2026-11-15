"""Servidor local de Tempo: mapa en web/app/ y una cola de análisis por punto.

    python server.py                 # http://localhost:8000 (solo 127.0.0.1)
    python server.py --port 8080 --host 127.0.0.1

Solo biblioteca estándar en el servidor. El worker reutiliza fetch.py (NASA POWER, SoilGrids,
IMERG y SRTM por Google Earth Engine con TEMPO_GEE_PROJECT) y engine.build_zone.

API
    POST /api/jobs            {lat, lon, nombre?} -> {id, estado, cache}
    GET  /api/jobs            lista de análisis (sin el resultado completo)
    GET  /api/jobs/<id>       estado: en_cola | procesando | listo | parcial | error
    GET  /api/jobs/<id>/result  JSON del análisis (resumen + salida de engine)
    GET  /api/sitios          sitios de parcelas.json (para el buscador)

Disco (fuera del repo, TEMPO_CACHE sobrescribe ~/.cache/tempo):
    jobs/<id>.json            registro del job (estado, mensaje, faltantes); si está listo o parcial,
                              un POST al mismo punto lo devuelve sin recalcular
    jobs/<id>/                caché de datos del punto (power.csv, imerg.csv, soil.json, ...)
    jobs/<id>/result.json     salida completa
id = sha256("lat,lon" redondeados a 6 decimales)[:16]. Los jobs en_cola o procesando se vuelven
a encolar al arrancar, así la cola sobrevive reinicios. Si una fuente falla, el job queda
"parcial" con la lista de faltantes; nada se rellena con datos inventados.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import queue
import shutil
import threading
import traceback
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

import config

HERE = os.path.dirname(os.path.abspath(__file__))
WEB_DIR = os.path.join(HERE, "web")

# El Salvador y su parte del Corredor Seco (incluye franjas de Guatemala y Honduras).
LAT_MIN, LAT_MAX = 12.0, 15.0
LON_MIN, LON_MAX = -90.5, -87.0
ESTADOS = ("en_cola", "procesando", "listo", "parcial", "error")
TERMINADOS = ("listo", "parcial")
MAX_BODY = 4096
COORD_TOL = 1e-6
DATA_FILES = ("power.csv", "precip_power.json", "imerg.csv", "soil.json", "terrain.json", "meta.json")

MSG_COLA = "En cola. Tarda unos minutos: descargamos lluvia satelital de NASA para tu punto."


def _now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def jobs_dir() -> str:
    return os.path.join(config.CACHE_DIR, "jobs")


def job_id(lat: float, lon: float) -> str:
    key = f"{round(float(lat), 6):.6f},{round(float(lon), 6):.6f}"
    return hashlib.sha256(key.encode()).hexdigest()[:16]


def validate_point(body) -> tuple[dict | None, str | None]:
    """{lat, lon, nombre?} -> (punto limpio, None) o (None, motivo)."""
    if not isinstance(body, dict):
        return None, "El cuerpo debe ser un objeto JSON con lat y lon."
    try:
        lat, lon = float(body["lat"]), float(body["lon"])
    except (KeyError, TypeError, ValueError):
        return None, "Faltan lat y lon numéricos."
    if lat != lat or lon != lon:  # NaN
        return None, "lat y lon deben ser números."
    if not (LAT_MIN <= lat <= LAT_MAX and LON_MIN <= lon <= LON_MAX):
        return None, (f"El punto ({lat:.4f}, {lon:.4f}) queda fuera de El Salvador y el Corredor Seco "
                      f"(lat {LAT_MIN:g} a {LAT_MAX:g}, lon {LON_MIN:g} a {LON_MAX:g}).")
    nombre = body.get("nombre")
    nombre = str(nombre).strip()[:80] if nombre else None
    return {"lat": round(lat, 6), "lon": round(lon, 6), "nombre": nombre or None}, None


# ---------------------------------------------------------------------------- store
class JobStore:
    """Registros de jobs en memoria, cada cambio escrito en jobs/<id>.json (escritura atómica)."""

    def __init__(self, root: str | None = None):
        self.root = root or jobs_dir()
        os.makedirs(self.root, exist_ok=True)
        self.lock = threading.RLock()
        self.jobs: dict[str, dict] = {}
        for f in sorted(os.listdir(self.root)):
            if f.endswith(".json") and not f.startswith("."):
                try:
                    with open(os.path.join(self.root, f), encoding="utf-8") as fh:
                        rec = json.load(fh)
                    if rec.get("id") == f[:-5]:
                        self.jobs[rec["id"]] = rec
                except (OSError, ValueError):
                    continue

    def path(self, jid: str) -> str:
        return os.path.join(self.root, f"{jid}.json")

    def data_dir(self, jid: str) -> str:
        return os.path.join(self.root, jid)

    def result_path(self, jid: str) -> str:
        return os.path.join(self.data_dir(jid), "result.json")

    def get(self, jid: str) -> dict | None:
        with self.lock:
            rec = self.jobs.get(jid)
            return dict(rec) if rec else None

    def all(self) -> list[dict]:
        with self.lock:
            return sorted((dict(r) for r in self.jobs.values()), key=lambda r: r.get("creado", ""))

    def save(self, rec: dict) -> dict:
        with self.lock:
            rec = {**rec, "actualizado": _now()}
            tmp = os.path.join(self.root, f".{rec['id']}.json.tmp")
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(rec, f, ensure_ascii=False, indent=1)
            os.replace(tmp, self.path(rec["id"]))
            self.jobs[rec["id"]] = rec
            return dict(rec)

    def update(self, jid: str, **fields) -> dict:
        with self.lock:
            return self.save({**self.jobs[jid], **fields})


# ---------------------------------------------------------------------------- queue
class JobQueue:
    """Un worker en hilo, un job a la vez. processor(rec, store, progress) -> dict con
    estado (listo | parcial | error), mensaje, faltantes y, si hay, resultado."""

    def __init__(self, store: JobStore, processor=None):
        self.store = store
        self.processor = processor or process_point
        self.q: queue.Queue[str] = queue.Queue()
        self.pending: list[str] = []
        self.plock = threading.Lock()
        self.thread: threading.Thread | None = None
        # Reanudar: lo que quedó en cola o a medio procesar vuelve a la cola, en orden de llegada.
        for rec in store.all():
            if rec.get("estado") in ("en_cola", "procesando"):
                store.update(rec["id"], estado="en_cola", mensaje=MSG_COLA + " (reanudado tras reinicio)",
                             progreso=0.0)
                self._put(rec["id"])

    def _put(self, jid: str) -> None:
        with self.plock:
            self.pending.append(jid)
        self.q.put(jid)

    def position(self, jid: str) -> int | None:
        with self.plock:
            return self.pending.index(jid) + 1 if jid in self.pending else None

    def submit(self, point: dict) -> tuple[dict, bool]:
        """(registro, cache). cache=True: ya hay análisis para ese punto y no se recalcula."""
        jid = job_id(point["lat"], point["lon"])
        with self.store.lock:
            rec = self.store.get(jid)
            if rec and rec.get("estado") in TERMINADOS and os.path.exists(self.store.result_path(jid)):
                return rec, True
            if rec and rec.get("estado") in ("en_cola", "procesando"):
                return rec, False
            rec = self.store.save({
                "id": jid, "lat": point["lat"], "lon": point["lon"],
                "nombre": point.get("nombre") or (rec or {}).get("nombre"),
                "estado": "en_cola", "mensaje": MSG_COLA, "faltantes": [], "progreso": 0.0,
                "creado": (rec or {}).get("creado") or _now(), "intentos": (rec or {}).get("intentos", 0) + 1,
            })
        self._put(jid)
        return rec, False

    def start(self) -> "JobQueue":
        self.thread = threading.Thread(target=self._loop, name="tempo-worker", daemon=True)
        self.thread.start()
        return self

    def _loop(self) -> None:
        while True:
            jid = self.q.get()
            if jid is None:
                return
            try:
                self.run_one(jid)
            finally:
                with self.plock:
                    if jid in self.pending:
                        self.pending.remove(jid)
                self.q.task_done()

    def stop(self) -> None:
        self.q.put(None)  # type: ignore[arg-type]
        if self.thread:
            self.thread.join(timeout=5)

    def run_one(self, jid: str) -> dict:
        rec = self.store.get(jid)
        if not rec or rec.get("estado") != "en_cola":
            return rec or {}
        rec = self.store.update(jid, estado="procesando", mensaje="Empezando el análisis.", progreso=0.02,
                                iniciado=_now())

        def progress(mensaje: str, frac: float | None = None):
            fields = {"mensaje": mensaje}
            if frac is not None:
                fields["progreso"] = round(max(0.0, min(1.0, frac)), 3)
            self.store.update(jid, **fields)

        try:
            out = self.processor(rec, self.store, progress)
        except Exception as e:  # noqa: BLE001 - el error queda en el job, el worker sigue
            traceback.print_exc()
            # Solo la primera línea, corta: algunos servicios devuelven páginas HTML como error.
            out = {"estado": "error", "mensaje": f"Falló el análisis: {_err(e)}", "faltantes": []}
        estado = out.get("estado", "error")
        if estado not in ("listo", "parcial", "error"):
            estado = "error"
        fields = {"estado": estado, "mensaje": out.get("mensaje", ""), "faltantes": out.get("faltantes", []),
                  "progreso": 1.0, "terminado": _now()}
        if "veredicto" in out:
            fields["veredicto"] = out["veredicto"]
        if out.get("resultado") is not None and estado in TERMINADOS:
            os.makedirs(self.store.data_dir(jid), exist_ok=True)
            tmp = self.store.result_path(jid) + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(out["resultado"], f, ensure_ascii=False, allow_nan=False, default=str)
            os.replace(tmp, self.store.result_path(jid))
        return self.store.update(jid, **fields)


# ---------------------------------------------------------------------------- worker
def _err(e: Exception) -> str:
    """Primera línea del error, corta (sin el HTML que devuelven algunos servidores)."""
    first = (str(e).strip().splitlines() or [""])[0]
    return f"{type(e).__name__}: {first[:200]}"


def _write_json(path: str, obj) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2)


def _read_json(path: str):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def _same_point(meta, lat, lon) -> bool:
    try:
        z = meta["zone"]
        return abs(float(z["lat"]) - lat) < COORD_TOL and abs(float(z["lon"]) - lon) < COORD_TOL
    except (KeyError, TypeError, ValueError):
        return False


def registered_cache(lat: float, lon: float) -> str | None:
    """Caché ya descargada por build_parcels/fetch para un sitio de parcelas.json en este mismo
    punto (meta.json con la misma coordenada y power.csv presente). Se copia, no se descarga."""
    try:
        sites = config.load_sites()
    except (OSError, ValueError, KeyError):
        return None
    for s in sites:
        if abs(float(s["lat"]) - lat) >= COORD_TOL or abs(float(s["lon"]) - lon) >= COORD_TOL:
            continue
        d = os.path.join(config.CACHE_DIR, s["id"])
        if os.path.exists(os.path.join(d, "power.csv")) and _same_point(_read_json(os.path.join(d, "meta.json")), lat, lon):
            return d
    return None


def gee_ready() -> tuple[bool, str | None]:
    """Earth Engine sin pasos interactivos (el worker no puede abrir un navegador)."""
    if not config.GEE_PROJECT:
        return False, "TEMPO_GEE_PROJECT no está definido"
    try:
        import ee
        ee.Initialize(project=config.GEE_PROJECT)
        return True, None
    except Exception as e:  # noqa: BLE001
        return False, f"Earth Engine no inicializó: {type(e).__name__}: {str(e)[:200]}"


def missing_from_files(d: str) -> list[str]:
    """Faltantes según lo que hay en disco para el punto."""
    out = []
    if not os.path.exists(os.path.join(d, "power.csv")):
        out.append("NASA POWER (temperatura y lluvia diaria): sin dato")
    elif (_read_json(os.path.join(d, "meta.json")) or {}).get("weather_backup"):
        out.append("NASA POWER (temperatura y lluvia diaria): no respondió; se usó el respaldo Meteomatics")
    if not os.path.exists(os.path.join(d, "imerg.csv")):
        out.append("IMERG (lluvia satelital): sin dato; lluvia 100 % NASA POWER")
    terrain = _read_json(os.path.join(d, "terrain.json")) or {}
    if terrain.get("elevation_m") is None:
        out.append("SRTM (elevación): sin dato; temperatura sin corrección por elevación")
    if terrain.get("slope_pct") is None:
        out.append("SRTM (pendiente): sin dato")
    soil = _read_json(os.path.join(d, "soil.json")) or {}
    if soil.get("error") or not soil.get("texture_class"):
        out.append("SoilGrids (suelo): sin dato; capacidad de agua por defecto del modelo")
    return out


def fetch_soil(fm, lat: float, lon: float, progress, gee, errors: dict) -> dict:
    """Suelo de SoilGrids: primero la API REST de ISRIC; si falla o no tiene valor en el punto,
    los mismos mapas desde Earth Engine (punto, luego 1 y 2 km alrededor). Nunca se inventa:
    si ninguna vía da arcilla y arena, queda el error y el modelo usa su valor por defecto."""
    tex = lambda s: fm.texture_class((s.get("clay") or {}).get("value_0_30cm"), (s.get("sand") or {}).get("value_0_30cm"))
    rest_err = None
    progress("Consultando el suelo en ISRIC SoilGrids.", 0.15)
    try:
        soil = fm.fetch_soilgrids(lat, lon)
        soil["texture_class"] = tex(soil)
        if soil["texture_class"]:
            soil["source"] = "ISRIC SoilGrids v2.0, mean, thickness-weighted 0-30 cm"
            soil["radius_m"] = 0
            return soil
        rest_err = "la API REST no tiene valor en este punto"
    except Exception as e:  # noqa: BLE001
        rest_err = _err(e)
    ok, why = (gee or gee_ready)()
    if ok and hasattr(fm, "fetch_soilgrids_gee"):
        progress("SoilGrids REST sin dato; consultando los mismos mapas en Earth Engine.", 0.17)
        try:
            soil = fm.fetch_soilgrids_gee(lat, lon)
            soil["texture_class"] = tex(soil)
            r = soil.get("radius_m", 0)
            soil["source"] = ("ISRIC SoilGrids v2.0 vía Google Earth Engine, 0-30 cm"
                              + (f", promedio en {r // 1000} km alrededor (el punto exacto no tiene dato)" if r else ""))
            soil["rest_error"] = rest_err
            return soil
        except Exception as e:  # noqa: BLE001
            why = _err(e)
    errors["soilgrids"] = f"REST: {rest_err}; Earth Engine: {why}"
    return {"error": errors["soilgrids"]}


def fetch_point(lat: float, lon: float, d: str, progress, fetch_mod=None, gee=None) -> dict:
    """Descarga cada fuente que falte en d (reanuda lo ya descargado). Devuelve errores por fuente."""
    import fetch as fetch_default
    fm = fetch_mod or fetch_default
    os.makedirs(d, exist_ok=True)
    end = fm._end_date()
    errors: dict[str, str] = {}
    meta_path = os.path.join(d, "meta.json")
    meta = _read_json(meta_path)
    if not _same_point(meta, lat, lon):
        # Archivos de otro punto (no debería pasar con id por coordenada): no se mezclan.
        for f in DATA_FILES:
            if os.path.exists(os.path.join(d, f)):
                os.remove(os.path.join(d, f))
        meta = {"zone": {"key": os.path.basename(d), "name": os.path.basename(d), "lat": lat, "lon": lon,
                         "parcel_elevation_m": None},
                "start": config.START_DATE, "end": end, "fetched_utc": _now(),
                "local_utc_offset_h": config.LOCAL_UTC_OFFSET_HOURS, "sources": {}}
        _write_json(meta_path, meta)

    if not os.path.exists(os.path.join(d, "power.csv")):
        progress("Descargando temperatura y lluvia diaria de NASA POWER (2001 a hoy).", 0.05)
        try:
            power, cell_elev = fm.fetch_power(lat, lon, config.START_DATE, end)
            power.to_csv(os.path.join(d, "power.csv"))
            with open(os.path.join(d, "precip_power.json"), "w") as f:
                json.dump(fm.power_precip_json(power), f, separators=(",", ":"))
            meta["power_cell_elevation_m"] = cell_elev
            meta["sources"]["power"] = f"NASA POWER daily, community AG, params {fm.POWER_PARAMS}"
            _write_json(meta_path, meta)
        except Exception as e:  # noqa: BLE001
            power_err = _err(e)
            # Respaldo: Meteomatics con las mismas columnas. Si tampoco responde, no hay análisis.
            try:
                if not hasattr(fm, "fetch_meteomatics"):
                    raise RuntimeError("respaldo no disponible")
                progress("NASA POWER no respondió; descargando temperatura y lluvia de Meteomatics (respaldo).", 0.08)
                power, cell_elev = fm.fetch_meteomatics(lat, lon, config.START_DATE, end)
            except Exception as e2:  # noqa: BLE001
                errors["power"] = f"{power_err}; respaldo Meteomatics: {_err(e2)}"
                return errors  # sin temperatura no se sigue
            power.to_csv(os.path.join(d, "power.csv"))
            with open(os.path.join(d, "precip_power.json"), "w") as f:
                json.dump(fm.power_precip_json(power), f, separators=(",", ":"))
            meta["power_cell_elevation_m"] = cell_elev
            meta["sources"]["power"] = fm.METEOMATICS_SOURCE
            meta["weather_backup"] = {"source": "meteomatics", "power_error": power_err, "fetched_utc": _now()}
            _write_json(meta_path, meta)
            errors["power_respaldo"] = f"NASA POWER: {power_err}; se usó Meteomatics"

    soil_path = os.path.join(d, "soil.json")
    soil = _read_json(soil_path)
    if not soil or soil.get("error") or not soil.get("texture_class"):
        soil = fetch_soil(fm, lat, lon, progress, gee, errors)
        _write_json(soil_path, soil)

    terrain_path = os.path.join(d, "terrain.json")
    terrain = _read_json(terrain_path)
    need_imerg = not os.path.exists(os.path.join(d, "imerg.csv"))
    need_srtm = not terrain or terrain.get("elevation_m") is None
    if need_imerg or need_srtm:
        ok, why = (gee or gee_ready)()
        if not ok:
            if need_imerg:
                errors["imerg"] = why
                meta["sources"]["imerg"] = "not fetched; precipitation falls back to POWER PRECTOTCORR"
            if need_srtm:
                errors["srtm"] = why
                _write_json(terrain_path, {"elevation_m": None, "slope_deg": None, "slope_pct": None,
                                           "source": "unavailable"})
            _write_json(meta_path, meta)
        else:
            if need_imerg:
                _fetch_imerg_parts(fm, lat, lon, end, d, progress, errors)
                if "imerg" not in errors:
                    meta["sources"]["imerg"] = ("GPM IMERG V07 half-hourly (NASA/GPM_L3/IMERG_V07), "
                                                "summed by local day")
                    _write_json(meta_path, meta)
            if need_srtm:
                progress("Consultando elevación y pendiente (SRTM 30 m).", 0.88)
                try:
                    _write_json(terrain_path, fm.fetch_terrain(lat, lon))
                except Exception as e:  # noqa: BLE001
                    errors["srtm"] = _err(e)
                    _write_json(terrain_path, {"elevation_m": None, "slope_deg": None, "slope_pct": None,
                                               "source": "unavailable"})
    return errors


def _fetch_imerg_parts(fm, lat, lon, end, d, progress, errors) -> None:
    """IMERG año por año en d/imerg_parts/<año>.csv, así un reinicio no repite lo ya bajado.
    imerg.csv se escribe solo si todos los años llegaron."""
    import pandas as pd
    parts = os.path.join(d, "imerg_parts")
    os.makedirs(parts, exist_ok=True)
    y0, y1 = int(config.START_DATE[:4]), int(end[:4])
    years = list(range(y0, y1 + 1))
    frames = []
    for i, y in enumerate(years):
        p = os.path.join(parts, f"{y}.csv")
        if y < y1 and os.path.exists(p):
            frames.append(pd.read_csv(p, parse_dates=["date"], index_col="date"))
            continue
        progress(f"Descargando lluvia satelital IMERG de NASA, año {y} ({i + 1} de {len(years)}).",
                 0.2 + 0.65 * i / len(years))
        last = None
        for _ in range(2):
            try:
                df = fm.fetch_imerg_year(lat, lon, y, end)
                df.to_csv(p)
                frames.append(df)
                last = None
                break
            except Exception as e:  # noqa: BLE001
                last = _err(e)
        if last:
            errors["imerg"] = f"año {y}: {last}"
            return
    pd.concat(frames).to_csv(os.path.join(d, "imerg.csv"))


SCENARIO_LABELS = {
    "base": "Lluvia de satélite (IMERG) con la regla de 150 mm del frijol",
    "no_bean_rule": "IMERG sin la regla de 150 mm del frijol",
    "power": "Lluvia del modelo NASA POWER con la regla de 150 mm",
    "power_no_bean_rule": "NASA POWER sin la regla de 150 mm",
    "imerg": "Lluvia de satélite (IMERG) con la regla de 150 mm",
    "imerg_no_bean_rule": "IMERG sin la regla de 150 mm",
}


def scenario_label(name: str) -> str:
    if name.startswith("whc_"):
        return f"Suelo con {name[4:]} mm de agua útil (en vez del valor del punto)"
    return SCENARIO_LABELS.get(name, name)


def robust_summary(out: dict, clear_pick: str | None, names: dict, fmt) -> dict | None:
    """Recomendación (D10). Con veredicto claro, la opción del veredicto con confianza alta.
    Si no, la opción más robusta del motor (maximin) con su confianza y en qué se basa.
    None si el motor no pudo comparar al menos dos opciones en todos los escenarios."""
    rb = out.get("robust") or {}
    if not rb.get("available") and clear_pick is None:
        return None
    escenarios = []
    for n, s in (rb.get("scenarios") or {}).items():
        best = max(s, key=s.get) if s else None
        escenarios.append({"clave": n, "nombre": scenario_label(n), "puntajes": s, "mejor": best,
                           **(rb.get("scenario_defs") or {}).get(n, {})})
    base = {"metodo": rb.get("method"), "escenarios": escenarios, "n_escenarios": rb.get("n_scenarios"),
            "umbral": rb.get("margin"), "empate": rb.get("tie")}
    if clear_pick is not None:
        return {"clave": clear_pick, "confianza": "alta", "origen": "veredicto",
                "texto": "Pasa las cuatro condiciones del veredicto: margen suficiente, no cambia sin la "
                         "regla de 150 mm ni con otra fuente de lluvia, y el modelo distingue las sequías documentadas.",
                "limites": [], **base}
    pick, second = rb["pick"], rb["second"]
    n, wins, regret = rb["n_scenarios"], rb["n_wins"], rb["max_regret"][pick]
    peor = (f"su puntaje más bajo es {fmt(rb['worst'][pick])}, frente a {fmt(rb['worst'][second])} "
            f"de {names[second].lower()}")
    if wins == n:
        texto = f"{names[pick]} queda primera o empatada en los {n} escenarios calculados; {peor}."
    else:
        texto = (f"Ninguna opción gana en todos los escenarios. {names[pick]} es la que mejor aguanta el peor "
                 f"caso: en {n} escenarios {peor}. Queda primera o empatada en {wins} de {n}"
                 + (f" y, cuando no, como mucho {fmt(regret)} puntos detrás." if regret > 0 else "."))
    limites = []
    if "soil" in rb.get("confidence_caps", []):
        limites.append("El suelo es un valor por defecto (faltó SoilGrids): la confianza no puede ser alta.")
    if "check1" in rb.get("confidence_caps", []):
        limites.append("El modelo no distingue los años de sequía documentados: la confianza no puede ser alta.")
    if "strict" in rb.get("confidence_caps", []):
        limites.append("Las pruebas estrictas fallan: en los años pasados la elección cambia sin la regla de 150 mm "
                       "del frijol o con otra fuente de lluvia. La confianza no puede ser alta.")
    if "margin" in rb.get("confidence_caps", []):
        bm = rb.get("base_margin")
        if pick == "A":
            limites.append(f"En el escenario base ninguna alternativa supera a la práctica actual por 0,05 o más "
                           f"(diferencia {fmt(abs(bm) if bm is not None else None)}): no hay razón para cambiar.")
        else:
            limites.append(f"En el escenario base {names[pick].lower()} supera a la siguiente opción por solo "
                           f"{fmt(bm)} puntos (menos de 0,05): la diferencia es mínima.")
    if "rain" in rb.get("confidence_caps", []):
        limites.append("Sin lluvia IMERG no se pudo comparar con otra fuente: la confianza queda en baja.")
    if rb["confidence"] == "baja" and not limites:
        limites.append(f"En algún escenario otra opción la supera por {fmt(regret)} puntos (más que el umbral "
                       f"{fmt(rb.get('margin'), 2)}, un SUPUESTO): confirme con el técnico de campo.")
    return {"clave": pick, "confianza": rb["confidence"], "origen": "robusta", "texto": texto,
            "peor_puntaje": rb["worst"], "arrepentimiento_max": rb["max_regret"], "gana_en": rb["wins"],
            "limites": limites, **base}


def data_summary(out: dict) -> dict:
    """Fechas reales de los datos usados: último día con lluvia y cuándo se descargó."""
    dd = out.get("data_dates") or {}
    return {"lluvia_hasta": dd.get("rain_last_day"), "imerg_hasta": dd.get("imerg_last_day"),
            "power_hasta": dd.get("power_last_day"), "descargado_utc": dd.get("fetched_utc"),
            "respaldo_clima": dd.get("weather_backup")}


def summarize(out: dict, faltantes: list[str]) -> dict:
    """Resumen en español para el panel. Un ganador solo se nombra si se cumplen las cuatro
    condiciones de build_site.verdict y la validación no empata con elegir siempre lo mismo."""
    import build_parcels
    import build_site
    names = build_site.NAMES["es"]
    conds = dict(build_site.verdict(out))
    season = build_parcels.season_reading(out)
    cur, year = out["current"], out["current_year"]
    rec, margin = cur.get("recommended"), cur.get("margin_over_second")
    claro = all(conds.values()) and not season["lectura_temporada"] and rec is not None
    fmt = lambda x, nd=3: "s/d" if x is None else f"{x:.{nd}f}".replace(".", ",")
    if claro:
        titulo = f"Para {year}, el modelo favorece: {names[rec].lower()}"
        texto = (f"Ventaja de {fmt(margin)} puntos sobre la segunda opción, y la elección no cambia "
                 "con otros supuestos ni con otra fuente de lluvia.")
    else:
        titulo = f"Ninguna opción es claramente mejor para este punto en {year}"
        texto = ("El puntaje más alto es para "
                 f"{names.get(rec, str(rec)).lower()}, con {fmt(margin)} puntos sobre la segunda opción, "
                 "y el resultado depende de supuestos sin validar. Léalo como una descripción de la "
                 "temporada, no como una recomendación.") if rec else "No hay puntajes suficientes para ordenar las opciones."
    recomendacion = robust_summary(out, rec if claro else None, names, fmt)
    if recomendacion and not claro:
        titulo = (f"Lectura de la postrera {year} para planificar {year + 1}: "
                  f"{names[recomendacion['clave']].lower()}, confianza {recomendacion['confianza']}")
        texto = recomendacion["texto"]
    pc, rs = out.get("primera_check", {}), out.get("rain_source_sensitivity", {})
    runs = out.get("sensitivity", {}).get("runs", {})
    nb = runs.get("no_bean_excess_rule", {})
    motivos = {
        "margin": f"Margen entre las dos mejores: {fmt(margin)} (umbral de lectura {fmt(build_site.READ_MARGIN, 2)}, un SUPUESTO).",
        "params": (f"Sin la regla de 150 mm del frijol, la elección cambia en {nb.get('n_pick_changes')} de "
                   f"{nb.get('n_years_compared')} años." if nb else "Sensibilidad a supuestos no disponible."),
        "rain": (f"Con NASA POWER en lugar de IMERG, la elección cambia en {rs.get('n_verdict_changes')} de "
                 f"{rs.get('n_years_compared')} años." if rs.get("available")
                 else "Sin IMERG no se puede comparar con otra fuente de lluvia."),
        "check1": ("Prueba de sequías documentadas: el modelo distingue los años de sequía citados." if pc.get("discriminative")
                   else "Prueba de sequías documentadas no evaluable: el modelo no distingue los años de sequía citados."),
    }
    windows = {k: {kk: w.get(kk) for kk in ("months", "n_years", "mean_imerg_mm", "mean_power_mm",
                                             "bias_mm", "bias_pct", "spearman")}
               for k, w in (rs.get("windows") or {}).items()}
    sens = {k: {"n_pick_changes": r.get("n_pick_changes"), "n_years_compared": r.get("n_years_compared"),
                "mean_margin_vs_current": r.get("mean_margin_vs_current"), "whc_mm": r.get("whc_mm"),
                "bean_excess_rule": r.get("bean_excess_rule")} for k, r in runs.items()}
    v = out.get("validation", {})
    inp = out.get("inputs", {})
    return {
        "anio": year,
        "veredicto": {"claro": claro, "titulo": titulo, "texto": texto, "mejor": rec, "margen": margin,
                      "condiciones": [{"clave": k, "cumple": bool(ok), "texto": motivos[k]} for k, ok in conds.items()],
                      "razones_lectura": season["razones"],
                      "recomienda": recomendacion is not None, "recomendacion": recomendacion},
        "datos": data_summary(out),
        "temporada_actual": [{"clave": s["strategy"], "nombre": names.get(s["strategy"], s["strategy"]),
                              "siembra": s["plant_date"], "cosecha": s["harvest_date"], "completa": s["complete"],
                              "puntaje": s["score"], "dias_faltan": s["days_missing"], "cultivos": s["crops"]}
                             for s in out.get("current_season", [])],
        "estrategias": [{"clave": s["key"], "nombre": names.get(s["key"], s["label"]), "puntaje": s.get("score"),
                         "fallo_pct": None if (s.get("analog_stats") or {}).get("failure_rate") is None
                         else round(100 * s["analog_stats"]["failure_rate"]),
                         "anios_parecidos": (s.get("analog_stats") or {}).get("n_years")}
                        for s in out.get("strategies", [])],
        "lluvia": {**build_parcels.rain_summary(out), "ventanas_imerg_vs_power": windows,
                   "cambios_con_power": rs.get("n_verdict_changes") if rs.get("available") else None},
        "suelo": {**build_parcels.soil_summary(out),
                  "radio_m": ((out.get("inputs") or {}).get("soil") or {}).get("radius_m")},
        "terreno": {**{k: (inp.get("terrain") or {}).get(k) for k in ("elevation_m", "slope_pct", "source")},
                    "correccion_temp_c": inp.get("temp_correction_c")},
        "sensibilidad": sens,
        "validacion": {"anios": v.get("n_years"), "tempo": v.get("mean_score_tempo"),
                       "practica_actual": v.get("mean_score_current"),
                       "misma_siempre": v.get("mean_score_same_every_year"),
                       "margen_medio": v.get("mean_margin_vs_current"), "p_signos": v.get("sign_test_p"),
                       "elecciones": v.get("picks") or {},
                       "anios_mejor": v.get("years_tempo_better"), "anios_peor": v.get("years_tempo_worse"),
                       "margen_sin_regla": (runs.get("no_bean_excess_rule") or {}).get("mean_margin_vs_current")},
        "faltantes": faltantes,
        "advertencias": out.get("warnings", []),
    }


def process_point(rec: dict, store: JobStore, progress, fetch_mod=None, gee=None, engine_mod=None) -> dict:
    """Trabajo real: datos del punto (reutiliza caché propia o de un sitio registrado), engine, resumen."""
    lat, lon, jid = float(rec["lat"]), float(rec["lon"]), rec["id"]
    d = store.data_dir(jid)
    os.makedirs(d, exist_ok=True)
    src = registered_cache(lat, lon)
    if src and not os.path.exists(os.path.join(d, "power.csv")):
        progress("Este punto ya tiene datos descargados en parcelas.json: se reutilizan.", 0.1)
        for f in DATA_FILES:
            if os.path.exists(os.path.join(src, f)):
                shutil.copy2(os.path.join(src, f), os.path.join(d, f))
    errors = fetch_point(lat, lon, d, progress, fetch_mod, gee)
    faltantes = missing_from_files(d)
    detalle = [f"{k}: {v}" for k, v in errors.items()]
    if "power" in errors:
        return {"estado": "error", "faltantes": faltantes,
                "mensaje": "No se pudo descargar NASA POWER; sin temperatura no hay análisis. " + errors["power"]}

    progress("Calculando balance de agua y comparando estrategias (2001 a hoy).", 0.92)
    if engine_mod is None:
        import engine as engine_mod
    rel = os.path.relpath(d, config.CACHE_DIR)  # indicators.load_zone lee CACHE_DIR/<clave>
    zone = config.Zone(rel, rec.get("nombre") or f"Punto {lat:.6f}, {lon:.6f}", lat, lon)
    out = engine_mod.clean_json(engine_mod.build_zone(zone, dict(engine_mod.DEFAULT_WEIGHTS), None, "imerg"))
    resumen = summarize(out, faltantes)
    estado = "parcial" if faltantes else "listo"
    mensaje = ("Análisis listo con todas las fuentes." if estado == "listo" else
               "Análisis parcial: faltan fuentes y no se rellenaron con datos inventados.")
    if detalle:
        mensaje += " Detalle: " + " | ".join(detalle)
    return {"estado": estado, "mensaje": mensaje, "faltantes": faltantes,
            "veredicto": {"claro": resumen["veredicto"]["claro"], "titulo": resumen["veredicto"]["titulo"],
                          "anio": resumen["anio"],
                          "recomendacion": ({"clave": resumen["veredicto"]["recomendacion"]["clave"],
                                             "confianza": resumen["veredicto"]["recomendacion"]["confianza"]}
                                            if resumen["veredicto"].get("recomendacion") else None)},
            "resultado": {"resumen": resumen, "analisis": out}}


# ---------------------------------------------------------------------------- http
def public(rec: dict, q: JobQueue | None = None) -> dict:
    keys = ("id", "lat", "lon", "nombre", "estado", "mensaje", "faltantes", "progreso", "creado",
            "actualizado", "iniciado", "terminado", "veredicto")
    out = {k: rec.get(k) for k in keys if k in rec}
    if q and rec.get("estado") == "en_cola":
        out["posicion"] = q.position(rec["id"])
    return out


def sites_public() -> list[dict]:
    try:
        sites = config.load_sites()
    except (OSError, ValueError, KeyError):
        return []
    keys = ("id", "nombre", "municipio", "departamento", "pais", "lat", "lon", "fuente_coordenadas")
    return [{k: s.get(k) for k in keys} for s in sites]


def make_handler(store: JobStore, q: JobQueue, web_dir: str = WEB_DIR):
    class Handler(SimpleHTTPRequestHandler):
        server_version = "Tempo/1"

        def __init__(self, *a, **kw):
            super().__init__(*a, directory=web_dir, **kw)

        def log_message(self, fmt, *args):  # menos ruido: solo errores
            if args and str(args[1] if len(args) > 1 else "").startswith(("4", "5")):
                super().log_message(fmt, *args)

        def end_headers(self):
            self.send_header("X-Content-Type-Options", "nosniff")
            super().end_headers()

        def _json(self, code: int, obj) -> None:
            body = json.dumps(obj, ensure_ascii=False, allow_nan=False, default=str).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def _job_path(self, path: str):
            parts = path.strip("/").split("/")  # api jobs <id> [result]
            if len(parts) >= 3 and parts[:2] == ["api", "jobs"]:
                jid = parts[2]
                if len(jid) == 16 and all(c in "0123456789abcdef" for c in jid):
                    return jid, parts[3:]
            return None, None

        def do_GET(self):
            path = urlparse(self.path).path
            if path in ("/", ""):
                self.send_response(HTTPStatus.FOUND)
                self.send_header("Location", "/app/")
                self.end_headers()
                return
            if path == "/api/jobs":
                return self._json(200, {"jobs": [public(r, q) for r in store.all()]})
            if path == "/api/sitios":
                return self._json(200, {"sitios": sites_public()})
            if path.startswith("/api/"):
                jid, rest = self._job_path(path)
                rec = store.get(jid) if jid else None
                if not rec:
                    return self._json(404, {"error": "No existe ese análisis."})
                if rest == []:
                    return self._json(200, public(rec, q))
                if rest == ["result"]:
                    p = store.result_path(jid)
                    if rec.get("estado") not in TERMINADOS or not os.path.exists(p):
                        return self._json(409, {"error": "El análisis todavía no tiene resultado.",
                                                "estado": rec.get("estado")})
                    with open(p, "rb") as f:
                        body = f.read()
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json; charset=utf-8")
                    self.send_header("Content-Length", str(len(body)))
                    self.send_header("Cache-Control", "no-store")
                    self.end_headers()
                    self.wfile.write(body)
                    return
                return self._json(404, {"error": "Ruta no encontrada."})
            return super().do_GET()

        def do_POST(self):
            path = urlparse(self.path).path
            if path != "/api/jobs":
                return self._json(404, {"error": "Ruta no encontrada."})
            try:
                n = int(self.headers.get("Content-Length") or 0)
            except ValueError:
                n = -1
            if n <= 0 or n > MAX_BODY:
                return self._json(400, {"error": "Cuerpo vacío o demasiado grande."})
            try:
                body = json.loads(self.rfile.read(n).decode("utf-8"))
            except (ValueError, UnicodeDecodeError):
                return self._json(400, {"error": "JSON inválido."})
            point, err = validate_point(body)
            if err:
                return self._json(400, {"error": err})
            rec, cached = q.submit(point)
            return self._json(200 if cached else 202, {**public(rec, q), "cache": cached})

    return Handler


def make_server(host: str = "127.0.0.1", port: int = 8000, store: JobStore | None = None,
                processor=None, start_worker: bool = True):
    store = store or JobStore()
    q = JobQueue(store, processor)
    if start_worker:
        q.start()
    httpd = ThreadingHTTPServer((host, port), make_handler(store, q))
    httpd.daemon_threads = True
    return httpd, store, q


def reanalyze(store: JobStore, ids: list[str] | None = None, processor=None) -> list[dict]:
    """Vuelve a correr el análisis de jobs ya terminados con el motor actual. Reutiliza los datos
    descargados y solo pide de nuevo las fuentes que faltaron (p. ej. SoilGrids caído).
    Incluye los que quedaron en cola o procesando por un corte: correr con el servidor detenido."""
    q = JobQueue(store, processor)
    done = []
    for rec in sorted(store.all(), key=lambda r: r.get("creado", "")):
        if (ids and rec["id"] not in ids) or rec.get("estado") not in TERMINADOS + ("error", "en_cola", "procesando"):
            continue
        store.update(rec["id"], estado="en_cola", mensaje=MSG_COLA + " (reanálisis)", progreso=0.0)
        out = q.run_one(rec["id"])
        print(f"  {rec['id']} {out.get('estado')}: {(out.get('veredicto') or {}).get('titulo', out.get('mensaje'))}")
        done.append(out)
    return done


def main() -> None:
    ap = argparse.ArgumentParser(description="Tempo: mapa y cola de análisis por punto")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--reanalizar", nargs="*", metavar="ID",
                    help="Recalcula los análisis guardados (todos, o los ID dados) con el motor actual y sale. "
                         "Correr con el servidor detenido.")
    a = ap.parse_args()
    if a.reanalizar is not None:
        reanalyze(JobStore(), a.reanalizar or None)
        return
    httpd, store, q = make_server(a.host, a.port)
    print(f"Tempo en http://localhost:{a.port}/  (jobs en {store.root})")
    if not config.GEE_PROJECT:
        print("TEMPO_GEE_PROJECT no está definido: los puntos nuevos quedan 'parcial' sin IMERG ni SRTM.")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()
        q.stop()


if __name__ == "__main__":
    main()
