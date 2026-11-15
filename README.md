# Tempo

Apoyo para la **postrera** en el Corredor Seco. Tempo usa lluvia y temperatura de NASA para comparar tres estrategias de rotación en una parcela y muestra qué habría funcionado en años parecidos.

> Tempo apoya la decisión y no reemplaza el criterio agronómico local.

## Uso

```bash
python -m venv ~/.venvs/tempo && ~/.venvs/tempo/bin/pip install -r requirements.txt
export TEMPO_GEE_PROJECT=<tu-proyecto-gee>   # solo por variable de entorno
~/.venvs/tempo/bin/python fetch.py           # POWER + SoilGrids + IMERG/SRTM (GEE)
~/.venvs/tempo/bin/python engine.py          # out/<zona>.json
~/.venvs/tempo/bin/python hindcast_md.py     # hindcast.md desde out/<zona>.json
~/.venvs/tempo/bin/python engine.py          # out/<zona>.json (lluvia IMERG + relleno POWER)
~/.venvs/tempo/bin/python engine.py --rain-source power   # solo lluvia NASA POWER
~/.venvs/tempo/bin/python build_page.py      # web/index.html (página única heredada)
~/.venvs/tempo/bin/python build_site.py      # web/site/*.html (ES) y web/site/*-en.html (EN)
~/.venvs/tempo/bin/python -m pytest tests -q
```

### Varios sitios (parcelas)

```bash
~/.venvs/tempo/bin/python build_parcels.py --run          # por sitio de parcelas.json: fetch (si falta caché) + engine
~/.venvs/tempo/bin/python build_parcels.py --run --ids somoto --refresh   # un sitio, descarga de nuevo
~/.venvs/tempo/bin/python build_parcels.py                # solo web/parcelas/data.json desde out/<id>.json
~/.venvs/tempo/bin/python fetch.py --sites parcelas.json --ids somoto     # solo descarga
python -m http.server 8000                                # desde la raíz del repo
# abrir http://localhost:8000/web/parcelas/
```

- `parcelas.json`: id, nombre, municipio, departamento, país, lat, lon, `fuente_coordenadas`,
  `fuente_admin` y `estado` (`activo` se procesa). Coordenada sin verificar = fuente que empieza con `SUPUESTO`.
- Cada sitio usa su propia caché `~/.cache/tempo/<id>/` y escribe `out/<id>.json`. Si la caché es de otro
  punto o quedó incompleta, se mueve a `<id>.anterior-<fecha>` (no se borra) y se descarga de nuevo.
  El resultado de cada corrida queda en `~/.cache/tempo/<id>/pipeline.json`; un fallo no detiene a los demás sitios.
- Sin `TEMPO_GEE_PROJECT`, IMERG y SRTM no se descargan: el sitio queda "parcial" (lluvia 100 % POWER,
  sin corrección de temperatura por elevación). Nada se rellena con valores inventados.
- `web/parcelas/data.json` lista los sitios con `out/<id>.json` y los pendientes (con motivo). Es un archivo generado.
- "Lectura de temporada": misma regla que `build_site.py` (la mejor estrategia supera a la segunda por menos de 0,05)
  o, en la validación, elegir siempre la misma estrategia empata o supera a Tempo.
- `config.ZONES` sigue con la parcela del usuario; `engine.py`, `hindcast_md.py` y `build_site.py` no cambian.

Caché fuera del repo: `~/.cache/tempo` (sobrescribible con `TEMPO_CACHE`). La lluvia POWER
(`PRECTOTCORR`) se guarda además en `~/.cache/tempo/<zona>/precip_power.json` (JSON compacto, ~50 KB).

## Sensibilidad a la fuente de lluvia

`out/<zona>.json` incluye `rain_source_sensitivity` (IMERG vs POWER), calculado siempre con ambas
fuentes, sea cual sea `--rain-source`:

- `windows.{primera,canicula,sep_nov}` (May-Ago, Jul-Ago, Sep-Nov): `bias_mm` (media anual de
  POWER − IMERG), `bias_pct` (relativo al total IMERG), `spearman` (totales anuales), `n_years`
  (solo años con IMERG completo en la ventana) y `by_year`.
- `verdict_changes`: años en que la estrategia elegida por el hindcast leave-one-out (`validate`)
  cambia entre la corrida con IMERG y la corrida con POWER.
- Sin `imerg.csv` (sin GEE) el bloque queda `available: false`.

## Sensibilidad a supuestos

`out/<zona>.json` incluye `sensitivity`: el hindcast leave-one-out se repite con capacidad de agua
(WHC) 60, 90 y 130 mm y sin la regla de 150 mm del frijol. Los valores por defecto no cambian.
Por variante: `pick_changes` (años cuya elección difiere de la corrida base), medias de puntaje,
margen frente a la práctica actual, prueba de signos y el estado de CHECK 1.

Resultado en la parcela (base WHC 130 mm): WHC 60 cambia 3 de 25 años (2007, 2011, 2018) y con ella
CHECK 1 sí discrimina; WHC 90 y 130 no cambian nada; **sin la regla de 150 mm cambian 25 de 25 años**
y la ventaja de Tempo sobre la práctica actual pasa de 0.18 a 0.00. Toda la ventaja viene de ese
umbral, que es un SUPUESTO.

## Cómo se lee el veredicto del sitio

El sitio solo nombra una opción cuando se cumplen cuatro condiciones: margen entre las dos mejores
>= 0.05 (umbral de lectura, SUPUESTO), ninguna elección cambia en `sensitivity`, ninguna cambia con
POWER en lugar de IMERG, y CHECK 1 es evaluable. Si falla alguna, el titular dice que ninguna
opción es claramente mejor. En la parcela hoy no se cumple ninguna (margen 2026: 0.003).

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

- **Circularidad (D1):** `VALIDATION_DROUGHT_YEARS` solo contiene años <= 2025 con cita; `TARGET_YEAR` = 2026 queda fuera (aserción en `engine.validate`, test `test_no_circularity`).
- **TARGET_YEAR fuera de todo cálculo de validación:** 2026 no entra en `validate`, en el ranking de CHECK 1, en `skill` ni en la comparación de fuentes de lluvia; los años análogos de 2026 salen solo de 2001-2025.
- **CHECK 1 no evaluable:** en la parcela, 23 de 25 años (2001-2025) dan WRSI de maíz de primera = 100. La lluvia de la ventana de primera (730–1600 mm) supera la ET0 (~480 mm) incluso en 2014 y 2018, así que el modelo no ve estrés en esos años. Esto es un resultado de los datos de este punto, no un error de la ecuación. Los empates toman el rango más alto (`method="max"`): antes, con `method="min"`, los años empatados contaban como "entre los peores" y 2014 y 2018 salían como "hit" por empate. Ahora CHECK 1 queda `status: no_evaluable` y D6 marca esos años `no_evaluable` (JSON, `hindcast.md` y sitio). No se ajustó el balance para forzar estrés.
- **Sin semáforo:** se quitó `traffic_light`. Leía `stats["A"]` (frijol en relevo) como si fuera maíz y solo contaba fallo con puntaje 0; no hay rendimientos ni una prueba de sequías que respalde un umbral.
- **Señal débil:** la canícula no correlaciona con la lluvia Sep-Nov (Spearman −0.21, 25 años).
- **Estrategia dominante:** Tempo elige C (segunda maíz) en 25 de 25 años; "misma estrategia siempre" empata (margen 0.00). Frente a la práctica actual el margen es 0.18 (9 años mejor, 0 peor, prueba de signos p = 0.0039), pero desaparece sin la regla de 150 mm.
- **Empates entre estrategias:** si dos estrategias empatan en los años análogos, se mantiene la práctica actual (A) y el año se marca `pick_tied`.
- **Balance hídrico:** zona radicular fija y `p` uniforme, no sigue FAO-56 completo (Zr dinámica, `p` por cultivo, Ky). Ver hallazgos de auditoría AGY.
- **Hargreaves:** usa (Tmax+Tmin)/2, forma original FAO-56 eq. 52 (D4). El cambio de ET0 medio anual frente a la versión con T2M se reporta en `inputs.et0_change_vs_t2m_pct`.
- **Temperatura sin elevación:** si falta `elevation_m`, no se corrige (`inputs.temp_correction_c = null`) y `warnings[]` lo indica (D3).
- **Sin verificación de campo:** no hay datos de cosecha locales.

## Hindcast

Ver [hindcast.md](hindcast.md): año por año, 2001-2025, leave-one-out. La tabla vive en `out/<zona>.json` (`hindcast.years`: estrategia elegida, WRSI y clase por cultivo, `documented`, `result` hit/fallo/no_evaluable según D6, `source`); `hindcast.md` lo genera `hindcast_md.py`, no se edita a mano.

## Uso de IA

- **Claude** (Haiku 5.5): orquestación, código de `fetch.py`/`engine.py` y pruebas.
- **Devin** (API v3): sesión de auditoría técnica y verificación de CHECK 1-3.
- **AGY**: auditoría independiente en modo solo lectura (fórmulas FAO-56, leave-one-out, circularidad, temperatura sin elevación).

Todo resultado fue revisado contra los tests. Los hallazgos no confirmados no se aplicaron al modelo.

## Pendiente

- Decisiones del equipo: quitar 2026 de la lista de sequías; `p` por cultivo; corrección de temperatura cuando falta elevación.
- `web/template.html` (página única heredada) usa `cur.traffic_light || "green"`: sin el campo muestra verde. Hay que quitar ese indicador del template.
- Validación agronómica local (CENTA).
- Página publicada: no. Solo generada localmente.
