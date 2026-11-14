# Tempo

Decision support for the **postrera** (second planting season) in the Central American Dry Corridor.
Tempo reads 25 years of NASA rainfall and temperature to compare three crop-rotation strategies
for a parcel, and explains which one would have held up in years like this one.

> Tempo supports, and does not replace, local agronomic expertise.

## Quick start

```bash
pip install -r requirements.txt
python fetch.py --no-gee     # NASA POWER + SoilGrids only (fast, no auth)
python fetch.py              # + GPM IMERG and SRTM via Google Earth Engine (set GEE_PROJECT in config.py)
python engine.py             # indicators, hindcast, recommendation -> out/<zone>.json
```

Options:

```bash
python fetch.py --lat 13.70 --lon -88.13 --key myparcel
python engine.py --zones morazan --seeds maize,bean --weights food=1,soil=1,water=0.5
```

## Pipeline

| Step | File | What it does |
| --- | --- | --- |
| 1 | `fetch.py` | Queries APIs point by point and caches results in `cache/<zone>/` |
| 2 | `indicators.py` | Daily series (IMERG rain, POWER temperature corrected for elevation, Hargreaves ET0) and yearly indicators: rainy-season onset, false onset, canícula length, postrera onset |
| 3 | `hindcast.py` | Daily soil-water bucket (FEWS NET WRSI style) for each crop and strategy, every year since 2001 |
| 4 | `engine.py` | Canícula-analog years, leave-one-out validation, scoring with farmer priorities, JSON output |
| — | `crops.json` | Crop and strategy parameters (FAO-56 defaults, to be validated locally) |

## Use of NASA data

| Dataset | Used for |
| --- | --- |
| GPM IMERG V07 (half-hourly, summed by local day) | All rainfall indicators and the water balance |
| NASA POWER daily (AG community) | Temperature, ET0, heat stress; rainfall gap filler |
| SRTM GL1 (30 m) | Parcel elevation (temperature correction) and slope (erosion weight) |

## Data sources & licenses

To be completed: NASA (open, cite DOIs), ISRIC SoilGrids (CC BY 4.0), FAO-56 parameters.
