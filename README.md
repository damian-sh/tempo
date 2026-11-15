# Tempo

Apoyo para la **postrera** en el Corredor Seco. Tempo usa lluvia y temperatura de NASA para comparar tres estrategias de rotación en una parcela y muestra qué habría funcionado en años parecidos.

> Tempo apoya la decisión y no reemplaza el criterio agronómico local.

## Uso

```bash
python -m venv ~/.venvs/tempo && ~/.venvs/tempo/bin/pip install -r requirements.txt
export TEMPO_GEE_PROJECT=<tu-proyecto-gee>   # solo por variable de entorno
~/.venvs/tempo/bin/python fetch.py           # POWER + SoilGrids + IMERG/SRTM (GEE)
~/.venvs/tempo/bin/python engine.py          # out/<zona>.json
~/.venvs/tempo/bin/python build_page.py      # web/index.html (sin --demo)
~/.venvs/tempo/bin/python -m pytest tests -q
```

Caché fuera del repo: `~/.cache/tempo` (sobrescribible con `TEMPO_CACHE`).

## Fuentes

| Fuente | Uso | Cómo |
|---|---|---|
| GPM IMERG V07 (GEE) | Lluvia diaria (día local UTC-6) y balance hídrico | Reducción en servidor al punto |
| NASA POWER Daily AG | Temperatura, radiación, HR, ET0; respaldo de lluvia | API por punto |
| SRTM GL1 (GEE) | Elevación y pendiente de la parcela | Reducción en servidor al punto |
| ISRIC SoilGrids v2 | Textura y carbono, 0-30 cm | API por punto |

No se usan GLDAS, GAEZ, SMAP, ERA5, Sentinel-2, Landsat, ECOSTRESS ni GEDI.

## Supuestos (sin fuente o no validados)

- **SUPUESTO:** umbral de 150 mm de lluvia tardía para frijol (`crops.json`, `excess_rain_late_mm`). Placeholder; requiere validación local.
- **SUPUESTO:** parámetros de cultivo (Kc, duración de etapas, `p` de agotamiento uniforme = 0.5). Base FAO-56 sin ajustar a la región.
- **Suelo parcela:** SoilGrids v2 real (arcilla 42.6 %, arena 25.6 %) → clase `clayey`, WHC 130 mm (`soil_whc_mm`, valor de tabla = SUPUESTO).
- **SUPUESTO:** elevación de la parcela = celda de POWER/SRTM. Punto: 13.796406, -89.801031 (convertido de 13°47'47.06"N 89°48'03.71"W).

## Límites conocidos

- **Circularidad:** 2026 está en `DOCUMENTED_DROUGHT_YEARS` y en el año a predecir. CHECK 1 no es una validación independiente hasta que se quite o se confirme con reportes posteriores.
- **Señal débil:** la canícula no correlaciona con la lluvia Sep-Nov (Spearman 0.04 Morazán, −0.18 Choluteca).
- **Estrategia dominante:** Tempo elige C (segunda maíz) en 24 de 25 años en Morazán y 25 de 25 en Choluteca. Igualar "misma estrategia siempre" le gana o empata. Si las estrategias no se distinguen, la lectura es de temporada, no una recomendación fuerte.
- **Balance hídrico:** zona radicular fija y `p` uniforme, no sigue FAO-56 completo (Zr dinámica, `p` por cultivo, Ky). Ver hallazgos de auditoría AGY.
- **Hargreaves:** usa (Tmax+Tmin)/2, forma original FAO-56 eq. 52 (D4). El cambio de ET0 medio anual frente a la versión con T2M se reporta en `inputs.et0_change_vs_t2m_pct`.
- **Temperatura sin elevación:** si falta `elevation_m`, no se corrige (`inputs.temp_correction_c = null`) y `warnings[]` lo indica (D3).
- **Sin verificación de campo:** no hay datos de cosecha locales.

## Hindcast

Ver [hindcast.md](hindcast.md): año por año, 2001-2025, leave-one-out.

## Uso de IA

- **Claude** (Haiku 5.5): orquestación, código de `fetch.py`/`engine.py` y pruebas.
- **Devin** (API v3): sesión de auditoría técnica y verificación de CHECK 1-3.
- **AGY**: auditoría independiente en modo solo lectura (fórmulas FAO-56, leave-one-out, circularidad, temperatura sin elevación).

Todo resultado fue revisado contra los tests. Los hallazgos no confirmados no se aplicaron al modelo.

## Pendiente

- Decisiones del equipo: quitar 2026 de la lista de sequías; `p` por cultivo; corrección de temperatura cuando falta elevación.
- Validación agronómica local (CENTA).
- Página publicada: no. Solo generada localmente.
