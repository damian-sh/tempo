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


# Demo zones in the Central American Dry Corridor (approximate coordinates).
ZONES = [
    Zone("morazan", "San Francisco Gotera, Morazan, El Salvador", 13.70, -88.13),
    Zone("choluteca", "Choluteca, Honduras", 13.30, -87.19),
]

START_DATE = "2001-01-01"   # IMERG daily record starts mid-2000; use full years
END_DATE = None             # None = yesterday

# Local time offset used to build local calendar days from IMERG half-hourly data.
LOCAL_UTC_OFFSET_HOURS = -6

# Google Earth Engine cloud project id. Leave as None to skip GEE (POWER-only mode).
GEE_PROJECT = _os.environ.get("TEMPO_GEE_PROJECT")  # set via env; never hardcode

import os as _os
# Cache lives outside the repo (plan rule). Override with TEMPO_CACHE.
CACHE_DIR = _os.environ.get("TEMPO_CACHE", _os.path.expanduser("~/.cache/tempo"))

# Years with documented drought losses in the Dry Corridor's primera season, used as an
# external check of the water-balance model (FEWS NET / WFP / FAO-GIEWS / Oxfam reports).
DOCUMENTED_DROUGHT_YEARS = [2014, 2015, 2018, 2026]
