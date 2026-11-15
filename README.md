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

### Mapa: elegir la parcela con un clic

Demo sin servidor (para el jurado, ver [docs/jurado.md](docs/jurado.md)): `cd web/app && python -m http.server 8000`.
Si `/api` no responde, la app lee la instantánea de `web/app/demo/` (`python export_demo.py`) y avisa
de que analizar puntos nuevos necesita el servidor.

```bash
export TEMPO_GEE_PROJECT=<tu-proyecto-gee>   # opcional; sin él, IMERG y SRTM quedan como faltantes
~/.venvs/tempo/bin/python server.py          # o: python server.py (con pandas/requests instalados)
# abrir http://localhost:8000
```

- Pantalla principal: mapa (Leaflet 1.9.4 desde cdnjs, mosaicos de OpenStreetMap). Toque la parcela,
  pulse "Analizar este punto" y el panel consulta el estado cada 4 s hasta mostrar el resultado:
  veredicto, condiciones, las tres opciones, lluvia IMERG y POWER, suelo, elevación, sensibilidad
  (sin la regla de 150 mm y con POWER) y límites. "Análisis hechos" lista y marca en el mapa todo
  lo ya analizado. El buscador solo encuentra los sitios de `parcelas.json`.
- Solo puntos con latitud 12 a 15 y longitud −90,5 a −87 (El Salvador y el Corredor Seco cercano).
- Servidor solo con biblioteca estándar, escucha en 127.0.0.1. API: `POST /api/jobs {lat, lon, nombre?}`,
  `GET /api/jobs`, `GET /api/jobs/<id>` (`en_cola | procesando | listo | parcial | error`, mensaje,
  faltantes), `GET /api/jobs/<id>/result`, `GET /api/sitios`.
- Cola: un worker en hilo, un análisis a la vez. Registro en `~/.cache/tempo/jobs/<id>.json`, datos y
  resultado en `~/.cache/tempo/jobs/<id>/`; `id` = sha256 de lat/lon redondeados a 6 decimales. Un punto
  ya analizado se devuelve sin recalcular. Al reiniciar, lo que estaba en cola o procesando vuelve a la
  cola; IMERG se guarda año por año (`imerg_parts/`) y no se descarga de nuevo.
- Si el punto coincide con un sitio de `parcelas.json` que ya tiene caché descargada, se copian esos
  archivos en lugar de descargar.
- Si falla una fuente, el análisis queda "parcial" con la lista de faltantes (sin GEE: lluvia 100 %
  POWER y sin corrección de temperatura por elevación; sin SoilGrids: capacidad de agua por defecto
  del modelo). Sin NASA POWER no hay análisis ("error"). Nada se rellena con datos inventados.
- Suelo: si la API REST de ISRIC falla o no tiene valor en el punto, se usan los mismos mapas
  SoilGrids v2.0 desde Earth Engine (el punto, o el promedio en 1 y 2 km; el radio se muestra).
- Recalcular lo guardado con el motor actual (reusa los datos, reintenta solo lo que faltó):
  `python server.py --reanalizar` (todos) o `python server.py --reanalizar <id> ...`.
- Cada resultado muestra hasta qué día llegan los datos de lluvia (IMERG y POWER) y cuándo se descargaron.
- Respaldo Meteomatics: si NASA POWER no responde, temperatura, humedad y lluvia diarias se piden a
  Meteomatics (`METEOMATICS_USER`, `METEOMATICS_PASSWORD` y `METEOMATICS_VALID_UNTIL` en `.env`, nunca
  en el repo). El análisis queda "parcial" con el aviso y la página lo dice. Después de la fecha de
  vencimiento no se intenta. Sesgo conocido: en Nacaome (2024) Meteomatics da 2 813 mm de lluvia
  frente a 1 911 mm de POWER y Tmax unos 3 °C más alta (punto a 37 m frente a la celda de POWER).
- Límites: un punto nuevo tarda minutos (IMERG se pide año por año a Earth Engine); el resultado no se
  actualiza solo (para datos nuevos, borre `~/.cache/tempo/jobs/<id>*`); IMERG es una celda de ~10 km y
  POWER de ~50 km, no la lluvia exacta de la parcela; el servidor es local, sin usuarios ni
  autenticación, y no debe exponerse a internet; el mapa necesita internet para los mosaicos y Leaflet.

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

### Recomendación robusta en el mapa (D10)

El mapa (`web/app`) recomienda una opción aunque el veredicto estricto no se cumpla. El motor calcula
el puntaje de cada opción para el año actual en varios escenarios: lluvia IMERG o POWER, con o sin la
regla de 150 mm del frijol, y suelo de 60/90/130 mm. Recomienda la opción con el mejor peor caso
(maximin) y le pone una confianza: alta (gana en todos con margen ≥ 0,05), media (nunca más de 0,05
detrás de la mejor y margen base ≥ 0,05) o baja (el resto). Sin IMERG la confianza es como mucho baja; con suelo por defecto o
si CHECK 1 no es evaluable, como mucho media. Si el veredicto estricto se cumple, se recomienda esa opción con confianza alta. La
tabla de escenarios se muestra en el resultado. Umbrales: SUPUESTOS (ver DECISIONES.md, D10).
Confianza alta exige además que las pruebas estrictas no cambien la elección (rev. 2).

### Qué hace distinto Tempo (y qué no)

| | Tempo | FEWS NET / USGS GeoWRSI | FAO ASIS-Country |
|---|---|---|---|
| Qué mide | Balance de agua tipo WRSI simplificado (D5) para tres opciones de postrera | WRSI de cultivo; incluye maíz de postrera en Centroamérica (temporada ago–dic) | Estrés agrícola con vegetación y temperatura de superficie satelitales, cada 10 días |
| Escala | Un punto elegido por el usuario | Malla regional | Malla nacional (portales de El Salvador, Guatemala, Honduras) |
| Pregunta que responde | ¿Qué opción de siembra aguanta mejor una temporada como esta, y con qué confianza? | ¿Cómo va el cultivo en la región? | ¿Dónde hay estrés agrícola? |
| Validación en campo | Pendiente (sin rendimientos) | Operativo desde hace años | Operativo, reconocido como bien público digital (2024) |

Tempo no reemplaza esos sistemas ni compite con su cobertura; agrega la comparación de opciones de
rotación por parcela con su incertidumbre. Fuentes:
[GeoWRSI (FEWS NET)](https://help.fews.net/en/tools/v3/chapter-11-geowrsi),
[productos WRSI de USGS para Centroamérica](https://earlywarning.usgs.gov/fews/product/927/),
[FAO ASIS-Country para Centroamérica](https://www.fao.org/americas/publications/User-Manual-Agrigultural-Stress-Index-System-Country-Level-/en),
[FAO Earth Observation](https://www.fao.org/giews/earthobservation/index.jsp).

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
