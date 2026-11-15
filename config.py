"""Tempo configuration: demo zones, date range, data-source switches."""
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class Zone:
    key: str
    name: str
    lat: float
    lon: float
    # Optional manual parcel elevation (m). Used when Earth Engine/SRTM is unavailable.
    parcel_elevation_m: Optional[float] = None


# Zones run by engine.py / hindcast_md.py / build_site.py. Kept to the user's parcel so the
# single-parcel outputs (hindcast.md, web/site) do not change. Multi-site runs go through the
# registry below (parcelas.json) and build_parcels.py.
ZONES = [
    Zone("parcela", "Parcela del usuario, El Salvador", 13.796406, -89.801031),
]

# Site registry: parcelas.json (id, nombre, municipio, departamento, lat, lon, coordinate source,
# estado). load_sites() validates it; site_zones() turns entries into Zone objects (key = id).
import json as _json_reg
import os as _os_reg
import re as _re_reg

SITES_FILE = _os_reg.path.join(_os_reg.path.dirname(_os_reg.path.abspath(__file__)), "parcelas.json")
_SITE_ID = _re_reg.compile(r"^[a-z0-9][a-z0-9-]*$")  # safe as a cache dir and out/<id>.json name


def load_sites(path: str = SITES_FILE) -> list[dict]:
    """All registry entries, validated: unique safe ids, numeric lat/lon in range."""
    with open(path, encoding="utf-8") as f:
        sites = _json_reg.load(f)["sitios"]
    seen = set()
    for s in sites:
        sid = s.get("id", "")
        if not _SITE_ID.match(sid):
            raise ValueError(f"invalid site id in {path}: {sid!r}")
        if sid in seen:
            raise ValueError(f"duplicate site id in {path}: {sid}")
        seen.add(sid)
        lat, lon = float(s["lat"]), float(s["lon"])
        if not (-90 <= lat <= 90 and -180 <= lon <= 180):
            raise ValueError(f"lat/lon out of range for {sid}: {lat}, {lon}")
    return sites


def site_zones(sites: list[dict], only_active: bool = True) -> list[Zone]:
    """Registry entries -> Zone objects. only_active keeps entries with estado == "activo"."""
    return [Zone(s["id"], ", ".join(x for x in (s["nombre"], s.get("departamento"), s.get("pais")) if x),
                 float(s["lat"]), float(s["lon"]), s.get("parcel_elevation_m"))
            for s in sites if not only_active or s.get("estado") == "activo"]

START_DATE = "2001-01-01"   # IMERG daily record starts mid-2000; use full years
END_DATE = None             # None = yesterday

# Local time offset used to build local calendar days from IMERG half-hourly data.
LOCAL_UTC_OFFSET_HOURS = -6

# Google Earth Engine cloud project id. Leave as None to skip GEE (POWER-only mode).
import os as _os_gee
# .env (ignorado por git) se lee siempre; una variable ya exportada en el entorno tiene prioridad.
if True:
    _env_f = _os_reg.path.join(_os_reg.path.dirname(_os_reg.path.abspath(__file__)), ".env")
    if _os_reg.path.exists(_env_f):
        with open(_env_f, encoding="utf-8") as _ef:
            for _line in _ef:
                _line = _line.strip()
                if _line.startswith("export "):
                    _line = _line[7:].strip()
                if _line and not _line.startswith("#") and "=" in _line:
                    _k, _v = _line.split("=", 1)
                    _os_gee.environ.setdefault(_k.strip(), _v.strip().strip("'\""))
GEE_PROJECT = _os_gee.environ.get("TEMPO_GEE_PROJECT")  # set via env; never hardcode

# Meteomatics: respaldo de temperatura y lluvia cuando NASA POWER no responde. Credenciales solo
# por entorno o .env; nunca en el código. Después de METEOMATICS_VALID_UNTIL no se intenta.
METEOMATICS_USER = _os_gee.environ.get("METEOMATICS_USER")
METEOMATICS_PASSWORD = _os_gee.environ.get("METEOMATICS_PASSWORD")
METEOMATICS_VALID_UNTIL = _os_gee.environ.get("METEOMATICS_VALID_UNTIL")  # AAAA-MM-DD, opcional

import os as _os
# Cache lives outside the repo (plan rule). Override with TEMPO_CACHE.
CACHE_DIR = _os.environ.get("TEMPO_CACHE", _os.path.expanduser("~/.cache/tempo"))

# Season Tempo forecasts. Never part of the validation set (D1).
TARGET_YEAR = 2026

# Years with documented primera drought losses in El Salvador's Dry Corridor, used as an
# external check of the water-balance model (CHECK 1). Only years <= 2025 with a cited
# source (D1, D6). 2026 is a reported event, not used for validation.
VALIDATION_DROUGHT_YEARS = {
    # 2015 removed: its ReliefWeb GLIDE URL returned 404 and no verified 2015-specific source
    # was found (D6). Add back only with a verifiable citation.
    2014: "FAO, 29 Jun 2016, ReliefWeb GLIDE DR-2014-000132-HND "
          "(https://reliefweb.int/disaster/dr-2014-000132-hnd): loss of staple grain crops in "
          "El Salvador since mid-2014.",
    2018: "ReliefWeb GLIDE DR-2018-000106-SLV (https://reliefweb.int/disaster/dr-2018-000106-slv): "
          "over 90,000 metric tons of corn lost, red alert.",
}
