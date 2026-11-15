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
    Zone("parcela", "Parcela del usuario, El Salvador", 13.796406, -89.801031),
]

START_DATE = "2001-01-01"   # IMERG daily record starts mid-2000; use full years
END_DATE = None             # None = yesterday

# Local time offset used to build local calendar days from IMERG half-hourly data.
LOCAL_UTC_OFFSET_HOURS = -6

# Google Earth Engine cloud project id. Leave as None to skip GEE (POWER-only mode).
import os as _os_gee
GEE_PROJECT = _os_gee.environ.get("TEMPO_GEE_PROJECT")  # set via env; never hardcode

import os as _os
# Cache lives outside the repo (plan rule). Override with TEMPO_CACHE.
CACHE_DIR = _os.environ.get("TEMPO_CACHE", _os.path.expanduser("~/.cache/tempo"))

# Season Tempo forecasts. Never part of the validation set (D1).
TARGET_YEAR = 2026

# Years with documented primera drought losses in El Salvador's Dry Corridor, used as an
# external check of the water-balance model (CHECK 1). Only years <= 2025 with a cited
# source (D1, D6). 2026 is a reported event, not used for validation.
VALIDATION_DROUGHT_YEARS = {
    2014: "OCHA, 10 Dec 2014, via ReliefWeb GLIDE DR-2014-000132-HND "
          "(https://reliefweb.int/disaster/dr-2014-000132-hnd): staple grain losses in El Salvador.",
    2015: "FAO, 29 Jun 2016, via ReliefWeb GLIDE DR-2015-000114-SLV "
          "(https://reliefweb.int/disaster/dr-2014-000132-hnd): drought 2014-2017, El Salvador.",
    2018: "Gobierno de El Salvador, alerta roja por sequía (UN DPI, 26 Jul 2018), ReliefWeb GLIDE "
          "DR-2018-000106-SLV (https://reliefweb.int/disaster/dr-2018-000106-slv): >90,000 t maize lost.",
}
