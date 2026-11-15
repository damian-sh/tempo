/* Tempo: mapa de parcelas y comparación honesta de opciones de postrera con datos NASA.
   Vanilla JS sin dependencias aparte de Leaflet. Todo lo que se muestra como dato sale del
   resultado del modelo (/api/jobs/<id>/result); lo que falta se dice, no se rellena. */
"use strict";

const BOUNDS = { latMin: 12, latMax: 15, lonMin: -90.5, lonMax: -87.0 };
const POLL_MS = 4000;
const BASE_TITLE = document.title;
const COLORS = { listo: "#2f6b3f", parcial: "#b07a12", error: "#a4281b", en_cola: "#5f6f94", procesando: "#5f6f94" };

const SHOWCASE_SITES = {
  parcela: { lat: 13.796406, lon: -89.801031, id: "c994b1f9c85a940e" },
  choluteca: { lat: 13.30, lon: -87.19, id: "44c5015f05bd7873" },
  morazan: { lat: 13.70, lon: -88.13, id: "3fbc891a8f31ac90" },
  nacaome: { lat: 13.5306, lon: -87.4870, id: "63e1cac4e49c6a6c" },
  chinandega: { lat: 12.6290, lon: -87.1310, id: "1cf264e9bcba7eca" },
};
const DEMO_BY_ID = Object.fromEntries(Object.entries(SHOWCASE_SITES).map(([k, s]) => [s.id, k]));

const I18N = {
  es: {
    brand_badge: "Datos NASA",
    tagline: "Qué sembrar en la postrera, con 25 años de lluvia satelital",
    search_label: "Buscar un lugar registrado",
    search_ph: "Buscar lugar",
    search_go: "Ir",
    search_none: "No está entre los lugares registrados. Toca el mapa o escribe coordenadas.",
    how_btn: "Cómo funciona",
    lang_other: "EN",
    lang_other_label: "Switch to English",
    map_label: "Mapa: toca un punto para elegir la parcela",
    examples_label: "Ejemplos ya analizados",
    examples_title: "Ejemplos",
    chip_parcela: "Ahuachapán · zona alta",
    chip_choluteca: "Choluteca · Corredor Seco",
    chip_morazan: "Morazán · ladera",
    chip_nacaome: "Nacaome · Golfo de Fonseca",
    chip_chinandega: "Chinandega · Nicaragua",
    legend_done: "Analizado",
    legend_partial: "Parcial (faltó una fuente)",
    legend_area: "Zona cubierta",
    layers_label: "Capa del mapa",
    layer_sat: "Satélite",
    layer_map: "Mapa",
    handle_label: "Agrandar o achicar el panel",
    tab_punto: "Parcela",
    tab_lista: "Guardados",
    intro_title: "¿Qué conviene sembrar en la postrera?",
    intro_desc: "Elige un punto del Corredor Seco. Tempo revisa <strong>25 años de lluvia medida por satélite</strong>, el relieve y el suelo de ese lugar, compara tres opciones de siembra y te dice <strong>cuán segura es la comparación</strong>.",
    btn_demo: "Ver un ejemplo ya analizado",
    btn_pick: "Elegir mi parcela en el mapa",
    step1: "<strong>Toca tu parcela</strong> en el mapa, dentro del recuadro punteado.",
    step2: "<strong>Tempo descarga los datos</strong> de NASA y del suelo. Si el punto es nuevo, tarda unos minutos.",
    step3: "<strong>Ves las tres opciones</strong> (frijol en relevo, sorgo + frijol, segunda maíz) y si alguna gana con claridad.",
    coords_label: "¿Tienes coordenadas? Escríbelas (latitud, longitud)",
    coords_go: "Usar",
    coords_bad: "Escribe dos números, por ejemplo 13.79, -89.80.",
    coverage: "Zona cubierta: El Salvador, sur de Honduras y norte de Nicaragua (latitud 12 a 15, longitud −90,5 a −87).",
    intro_date: "En noviembre la postrera del año ya está sembrada: Tempo muestra cómo responde cada opción en una temporada como la de este año, para planificar la próxima siembra.",
    picking_title: "Toca tu parcela en el mapa",
    picking_desc: "Acerca el mapa con los dedos o con + y −. El punto debe quedar dentro del recuadro punteado.",
    cancel: "Cancelar",
    pick_title: "Parcela elegida",
    pick_name: "Nombre de la parcela (opcional)",
    pick_name_ph: "Ej.: El Roble, lote 2",
    go: "Analizar esta parcela",
    pick_note: "Si este punto ya se analizó, el resultado aparece al instante. Si es nuevo, tarda unos minutos y puedes cerrar la página.",
    out_of_bounds: "Este punto queda fuera de la zona cubierta (recuadro punteado). Tempo no lo analiza.",
    back_home: "← Volver al inicio",
    prog_note: "Puedes cerrar la página: el resultado queda guardado en la pestaña «Guardados» y en el mapa.",
    st_en_cola: "En cola",
    st_procesando: "Analizando",
    st_listo: "Listo",
    st_parcial: "Parcial",
    st_error: "Error",
    queue_pos: (n) => `puesto ${n} en la cola`,
    elapsed: (m, s) => `Lleva ${m ? `${m} min ` : ""}${s} s. Un punto nuevo suele tardar varios minutos.`,
    poll_retry: "Sin respuesta del servidor; reintentando…",
    title_running: "Analizando · Tempo",
    title_done: "Listo · Tempo",
    list_title: "Análisis guardados",
    list_desc: "Toca uno para abrirlo. Marca dos o tres para compararlos.",
    list_empty: "Todavía no hay análisis. Toca el mapa para empezar.",
    compare_go: "Comparar",
    compare_n: (n) => `${n} marcados`,
    compare_max: "Puedes comparar hasta 3 a la vez.",
    compare_title: "Comparación",
    verdict_row: "Recomendación",
    compare_close: "Cerrar comparación",
    compare_loading: "Cargando…",
    select_for_compare: (name) => `Marcar ${name} para comparar`,
    unnamed: "Punto sin nombre",
    near: (x) => `Cerca de ${x}`,
    example: "Ejemplo",
    ex_parcela: "Ahuachapán, El Salvador",
    ex_choluteca: "Choluteca, Honduras",
    ex_morazan: "San Francisco Gotera, Morazán",
    ex_nacaome: "Nacaome, Valle, Honduras",
    ex_chinandega: "Chinandega, Nicaragua",
    demo_line: "Ejemplo ya analizado. Toca el mapa para analizar tu parcela.",
    season: (y) => `Postrera ${y}`,
    from_cache: "Ya estaba analizado: resultado al instante.",
    confirm_new: "¿Analizar este punto?",
    confirm_yes: "Sí, elegir este punto",
    verdict_kind: (y) => `Veredicto · Postrera ${y}`,
    rec_kind: (y) => `Lectura de la postrera ${y} · para planificar ${Number(y) + 1 || ""}`,
    planted: (y, d) => `La postrera ${y} ya se sembró (≈${d}). Esta lectura sirve para planificar la siembra ${Number(y) + 1} con su técnico de campo, no para decidir hoy.`,
    rain_unc: (i, p, n, t) => `Incertidumbre de lluvia: en sep–nov el satélite (IMERG, celda ~10 km) da ${i} mm y el modelo (POWER, ~50 km) ${p} mm en promedio. Con POWER, la elección histórica cambia en ${n} de ${t} años.`,
    val_title: "Prueba con años pasados (2001–2025)",
    val_desc: "Para cada año pasado se eligió con este método sin mirar ese año, y se comparó con lo que realmente pasó en el balance de agua.",
    val_picks: (txt) => `Opción elegida: ${txt}`,
    val_scores: (m, a, s) => `Puntaje medio: método ${m} · práctica actual (A) ${a} · elegir siempre la misma opción ${s}`,
    val_margin: (c, n) => `Ventaja sobre la práctica actual: ${c} puntos con la regla de 150 mm del frijol; ${n} sin la regla.`,
    val_rule: "Esa ventaja depende de la regla de 150 mm, un supuesto sin validar.",
    val_same: "Elegir siempre la misma opción da el mismo puntaje: el método todavía no demuestra ventaja sobre una regla fija.",
    val_diff: "La lectura de arriba usa solo años con canícula parecida a la de este año y el peor caso entre escenarios; por eso puede no coincidir con la opción más elegida en el pasado.",
    val_years: (n) => `${n} años`,
    conf: { alta: "Confianza alta", media: "Confianza media", baja: "Confianza baja" },
    conf_help: {
      alta: "Gana en todos los escenarios con margen suficiente y pasa las pruebas estrictas.",
      media: "Supera a la segunda por 0,05 o más y nunca queda lejos de la mejor en ningún escenario.",
      baja: "La diferencia es mínima o en algún escenario otra opción la supera con claridad.",
    },
    rec_tag: "Recomendada",
    rec_tag_robust: "Recomendada (la más segura)",
    basis_title: "En qué se basa la recomendación",
    basis_desc: (n) => `El modelo calculó el puntaje de cada opción en ${n} escenarios: las dos fuentes de lluvia, con y sin la regla de 150 mm del frijol, y otros tipos de suelo. Se recomienda la opción con el mejor puntaje en su peor escenario.`,
    basis_scenario: "Escenario",
    basis_worst: "Peor caso",
    sc_rain: { imerg: "Lluvia satélite (IMERG)", power: "Lluvia modelo (POWER)" },
    sc_rain_mm: "Lluvia modelo (Meteomatics, respaldo)",
    season_title: (y) => `Así va la postrera ${y} (solo lluvia medida)`,
    season_desc: (d) => `Balance de agua de este año con la lluvia observada hasta el ${d}. No usa pronóstico; no estima rendimiento.`,
    season_done: (sc, cls) => `Ciclo terminado · puntaje ${sc} (${cls})`,
    season_field: (h, n) => `En campo · cosecha ~${h} · faltan ${n} días de datos`,
    cls_name: { good: "buena cosecha", partial: "cosecha parcial", poor: "cosecha pobre", failure: "pérdida" },
    backup_line: "NASA POWER no respondió: temperatura y lluvia de modelo vienen de Meteomatics (respaldo), que puede dar valores distintos a POWER.",
    sc_rule_on: "con regla 150 mm",
    sc_rule_off: "sin regla 150 mm",
    sc_soil: (w) => `suelo ${w} mm`,
    data_line: (d, f) => `Datos de lluvia hasta el ${d}${f ? ` · descargados el ${f}` : ""}`,
    data_detail: (i, p) => `IMERG hasta ${i || "s/d"} · NASA POWER hasta ${p || "s/d"}`,
    soil_radius: (km) => `promedio de ${km} km alrededor`,
    verdict_clear_lbl: "Hay una opción claramente mejor",
    verdict_unclear_lbl: "Ninguna opción gana con claridad",
    why_title: "¿Qué tan segura es la comparación?",
    cond_ok: "Cumple",
    cond_no: "No cumple",
    partial_title: "Análisis parcial: faltaron fuentes",
    partial_desc: "Tempo no inventó esos datos. Donde faltan, usa el valor por defecto del modelo y lo indica.",
    warnings_title: "Advertencias del modelo",
    facts_title: "La temporada en este punto",
    f_canicula: "Canícula",
    f_canicula_val: (d, c) => `${d} días${c ? ` (${c})` : ""}`,
    f_rain_ja: "Lluvia jul–ago",
    f_rain_ja_val: (a, m) => a === null ? `normal ${m} mm` : `${a} mm (normal ${m})`,
    f_soil: "Agua útil del suelo",
    f_soil_default: "valor por defecto",
    canicula_cls: { short: "corta", normal: "normal", long: "larga" },
    opts_title: "Las tres opciones",
    opts_score: "Puntaje",
    opts_help: "Puntaje promedio en los años más parecidos a esta temporada: 1 = buena cosecha, 0 = pérdida.",
    tag_best: "Mejor opción",
    tag_top: "Puntaje más alto",
    fails: (f, n) => `Falló en ${f} de ${n} años parecidos`,
    cycle: (d) => `Ciclo de ${d} días`,
    nfix: "fija nitrógeno",
    margin_line: (m) => `Diferencia entre las dos primeras: ${m} puntos. Por debajo de 0,05 Tempo no habla de ventaja clara.`,
    margin_line_rec: (m) => `En el escenario base la diferencia entre las dos primeras es de ${m} puntos. La recomendación se decide por el peor caso de cada opción (tabla de abajo).`,
    why_title_rec: "Pruebas del veredicto estricto",
    why_desc_rec: "Miran los 25 años pasados: si la elección cambia con los supuestos o con la fuente de lluvia. Si alguna falla, Tempo no declara un ganador claro y recomienda por peor caso, con la confianza indicada arriba.",
    hydro_title: "Lluvia en este punto",
    hydro_desc: "Lluvia acumulada (mm) de mayo a noviembre según NASA GPM IMERG, 2001–2025. La franja de canícula marca su duración, no su fecha exacta.",
    hydro_band: "Rango normal (20–80 %)",
    hydro_median: "Año típico",
    hydro_current: "Este año",
    hydro_canicula: "Canícula",
    hydro_aria: (y) => `Gráfico de lluvia de mayo a noviembre: rango normal, año típico y ${y}.`,
    tech_title: "Datos técnicos y fuentes",
    t_elev: "Elevación",
    t_slope: "Pendiente",
    t_soil: "Suelo",
    t_soil_none: "sin dato de SoilGrids",
    texture: { clayey: "arcilloso", loamy: "franco", sandy: "arenoso" },
    t_sources_title: "Lluvia: satélite (IMERG) frente a modelo (POWER)",
    t_sources_desc: "Si las dos fuentes no coinciden, la lluvia real del punto es incierta.",
    t_window: "Ventana",
    t_bias: "Diferencia",
    windows: { primera: "Primera (may–ago)", canicula: "Canícula (jul–ago)", sep_nov: "Postrera (sep–nov)" },
    t_missions: "Fuentes usadas",
    t_mission: "Fuente",
    t_variable: "Variable",
    t_res: "Resolución",
    v_imerg: "Lluvia diaria por satélite (2001–2025)",
    v_power: "Temperatura y radiación (evapotranspiración)",
    v_srtm: "Elevación y pendiente",
    v_soil: "Arcilla y arena (0–30 cm)",
    t_json: "Descargar datos completos (JSON)",
    act_share: "Compartir",
    act_print: "Imprimir",
    act_new: "Otra parcela",
    shared: "Resumen copiado. Pégalo en WhatsApp o en un mensaje.",
    share_fail: "No se pudo copiar. Selecciona el texto manualmente.",
    err_title: "No se pudo analizar esta parcela",
    err_generic: "Uno de los servicios de datos no respondió. Suele ser temporal: reintenta en unos minutos.",
    err_detail: "Detalle técnico",
    err_retry: "Reintentar",
    err_open: "No se pudo abrir el análisis. Revisa tu conexión y reintenta.",
    close: "Cerrar",
    modal_title: "Cómo funciona Tempo",
    unit_days: "días",
    nodata: "s/d",
  },
  en: {
    brand_badge: "NASA data",
    tagline: "What to plant in the postrera, from 25 years of satellite rainfall",
    search_label: "Search a registered place",
    search_ph: "Search place",
    search_go: "Go",
    search_none: "Not among the registered places. Tap the map or type coordinates.",
    how_btn: "How it works",
    lang_other: "ES",
    lang_other_label: "Cambiar a español",
    map_label: "Map: tap a point to choose the plot",
    examples_label: "Already analyzed examples",
    examples_title: "Examples",
    chip_parcela: "Ahuachapán · highlands",
    chip_choluteca: "Choluteca · Dry Corridor",
    chip_morazan: "Morazán · hillside",
    chip_nacaome: "Nacaome · Gulf of Fonseca",
    chip_chinandega: "Chinandega · Nicaragua",
    legend_done: "Analyzed",
    legend_partial: "Partial (a source was missing)",
    legend_area: "Covered area",
    layers_label: "Map layer",
    layer_sat: "Satellite",
    layer_map: "Map",
    handle_label: "Expand or shrink the panel",
    tab_punto: "Plot",
    tab_lista: "Saved",
    intro_title: "What should be planted in the postrera?",
    intro_desc: "Choose a point in the Dry Corridor. Tempo reviews <strong>25 years of satellite-measured rainfall</strong>, the terrain and the soil at that spot, compares three planting options and tells you <strong>how certain the comparison is</strong>.",
    btn_demo: "See an analyzed example",
    btn_pick: "Choose my plot on the map",
    step1: "<strong>Tap your plot</strong> on the map, inside the dashed box.",
    step2: "<strong>Tempo downloads the data</strong> from NASA and soil maps. A new point takes a few minutes.",
    step3: "<strong>You see the three options</strong> (relay bean, sorghum + bean, second maize) and whether any clearly wins.",
    coords_label: "Have coordinates? Type them (latitude, longitude)",
    coords_go: "Use",
    coords_bad: "Type two numbers, for example 13.79, -89.80.",
    coverage: "Covered area: El Salvador, southern Honduras and northern Nicaragua (latitude 12 to 15, longitude −90.5 to −87).",
    intro_date: "In November this year's postrera is already planted: Tempo shows how each option responds in a season like this one, to plan the next planting.",
    picking_title: "Tap your plot on the map",
    picking_desc: "Zoom with two fingers or with + and −. The point must be inside the dashed box.",
    cancel: "Cancel",
    pick_title: "Chosen plot",
    pick_name: "Plot name (optional)",
    pick_name_ph: "E.g. El Roble, lot 2",
    go: "Analyze this plot",
    pick_note: "If this point was already analyzed, the result shows instantly. A new point takes a few minutes and you can close the page.",
    out_of_bounds: "This point is outside the covered area (dashed box). Tempo does not analyze it.",
    back_home: "← Back to start",
    prog_note: "You can close the page: the result is saved in the «Saved» tab and on the map.",
    st_en_cola: "Queued",
    st_procesando: "Analyzing",
    st_listo: "Ready",
    st_parcial: "Partial",
    st_error: "Error",
    queue_pos: (n) => `position ${n} in the queue`,
    elapsed: (m, s) => `Running for ${m ? `${m} min ` : ""}${s} s. A new point usually takes several minutes.`,
    poll_retry: "No response from the server; retrying…",
    title_running: "Analyzing · Tempo",
    title_done: "Ready · Tempo",
    list_title: "Saved analyses",
    list_desc: "Tap one to open it. Tick two or three to compare them.",
    list_empty: "No analyses yet. Tap the map to start.",
    compare_go: "Compare",
    compare_n: (n) => `${n} ticked`,
    compare_max: "You can compare up to 3 at a time.",
    compare_title: "Comparison",
    verdict_row: "Recommendation",
    compare_close: "Close comparison",
    compare_loading: "Loading…",
    select_for_compare: (name) => `Tick ${name} to compare`,
    unnamed: "Unnamed point",
    near: (x) => `Near ${x}`,
    example: "Example",
    ex_parcela: "Ahuachapán, El Salvador",
    ex_choluteca: "Choluteca, Honduras",
    ex_morazan: "San Francisco Gotera, Morazán",
    ex_nacaome: "Nacaome, Valle, Honduras",
    ex_chinandega: "Chinandega, Nicaragua",
    demo_line: "Already analyzed example. Tap the map to analyze your plot.",
    season: (y) => `Postrera ${y}`,
    from_cache: "Already analyzed: instant result.",
    confirm_new: "Analyze this point?",
    confirm_yes: "Yes, choose this point",
    verdict_kind: (y) => `Verdict · Postrera ${y}`,
    rec_kind: (y) => `Reading of the ${y} postrera · to plan ${Number(y) + 1 || ""}`,
    planted: (y, d) => `The ${y} postrera is already planted (≈${d}). Use this reading to plan the ${Number(y) + 1} planting with your field technician, not to decide today.`,
    rain_unc: (i, p, n, t) => `Rainfall uncertainty: in Sep–Nov the satellite (IMERG, ~10 km cell) gives ${i} mm and the model (POWER, ~50 km) ${p} mm on average. With POWER, the historical choice changes in ${n} of ${t} years.`,
    val_title: "Test against past years (2001–2025)",
    val_desc: "For each past year the method chose without looking at that year, and the choice was compared with what actually happened in the water balance.",
    val_picks: (txt) => `Option chosen: ${txt}`,
    val_scores: (m, a, s) => `Mean score: method ${m} · current practice (A) ${a} · always the same option ${s}`,
    val_margin: (c, n) => `Advantage over current practice: ${c} points with the 150 mm bean rule; ${n} without it.`,
    val_rule: "That advantage depends on the 150 mm rule, an unvalidated assumption.",
    val_same: "Always choosing the same option scores the same: the method does not yet beat a fixed rule.",
    val_diff: "The reading above uses only years with a canícula like this year's and the worst case across scenarios, so it may differ from the option chosen most often in the past.",
    val_years: (n) => `${n} years`,
    conf: { alta: "High confidence", media: "Medium confidence", baja: "Low confidence" },
    conf_help: {
      alta: "Wins in every scenario by a sufficient margin and passes the strict checks.",
      media: "Beats the runner-up by 0.05 or more and is never far behind the best in any scenario.",
      baja: "The difference is minimal, or in some scenario another option clearly beats it.",
    },
    rec_tag: "Recommended",
    rec_tag_robust: "Recommended (safest)",
    basis_title: "What the recommendation is based on",
    basis_desc: (n) => `The model scored each option in ${n} scenarios: both rainfall sources, with and without the 150 mm bean rule, and other soil types. It recommends the option with the best score in its worst scenario.`,
    basis_scenario: "Scenario",
    basis_worst: "Worst case",
    sc_rain: { imerg: "Satellite rain (IMERG)", power: "Model rain (POWER)" },
    sc_rain_mm: "Model rain (Meteomatics, backup)",
    season_title: (y) => `How the ${y} postrera is going (measured rain only)`,
    season_desc: (d) => `This year's water balance with rainfall observed through ${d}. No forecast; yields are not estimated.`,
    season_done: (sc, cls) => `Cycle finished · score ${sc} (${cls})`,
    season_field: (h, n) => `In the field · harvest ~${h} · ${n} days of data still missing`,
    cls_name: { good: "good harvest", partial: "partial harvest", poor: "poor harvest", failure: "failure" },
    backup_line: "NASA POWER did not respond: temperature and model rainfall come from Meteomatics (backup), which may differ from POWER.",
    sc_rule_on: "with 150 mm rule",
    sc_rule_off: "without 150 mm rule",
    sc_soil: (w) => `soil ${w} mm`,
    data_line: (d, f) => `Rainfall data through ${d}${f ? ` · downloaded ${f}` : ""}`,
    data_detail: (i, p) => `IMERG through ${i || "n/a"} · NASA POWER through ${p || "n/a"}`,
    soil_radius: (km) => `average within ${km} km`,
    verdict_clear_lbl: "One option is clearly better",
    verdict_unclear_lbl: "No option clearly wins",
    why_title: "How certain is the comparison?",
    cond_ok: "Passes",
    cond_no: "Fails",
    partial_title: "Partial analysis: some sources were missing",
    partial_desc: "Tempo did not invent that data. Where it is missing, the model default is used and flagged.",
    warnings_title: "Model warnings",
    facts_title: "The season at this point",
    f_canicula: "Canícula (midsummer drought)",
    f_canicula_val: (d, c) => `${d} days${c ? ` (${c})` : ""}`,
    f_rain_ja: "Jul–Aug rain",
    f_rain_ja_val: (a, m) => a === null ? `normal ${m} mm` : `${a} mm (normal ${m})`,
    f_soil: "Soil available water",
    f_soil_default: "model default",
    canicula_cls: { short: "short", normal: "normal", long: "long" },
    opts_title: "The three options",
    opts_score: "Score",
    opts_help: "Average score in the past years most similar to this season: 1 = good harvest, 0 = failure.",
    tag_best: "Best option",
    tag_top: "Highest score",
    fails: (f, n) => `Failed in ${f} of ${n} similar years`,
    cycle: (d) => `${d}-day cycle`,
    nfix: "fixes nitrogen",
    margin_line: (m) => `Gap between the top two: ${m} points. Below 0.05 Tempo does not claim a clear advantage.`,
    margin_line_rec: (m) => `In the base scenario the gap between the top two is ${m} points. The recommendation is decided by each option's worst case (table below).`,
    why_title_rec: "Strict verdict checks",
    why_desc_rec: "They look at the past 25 years: whether the choice changes with the assumptions or the rainfall source. If any fails, Tempo does not declare a clear winner and recommends by worst case, with the confidence shown above.",
    hydro_title: "Rainfall at this point",
    hydro_desc: "Accumulated rainfall (mm) from May to November per NASA GPM IMERG, 2001–2025. The canícula band shows its length, not its exact dates.",
    hydro_band: "Normal range (20–80 %)",
    hydro_median: "Typical year",
    hydro_current: "This year",
    hydro_canicula: "Canícula",
    hydro_aria: (y) => `Rainfall chart May to November: normal range, typical year and ${y}.`,
    tech_title: "Technical data and sources",
    t_elev: "Elevation",
    t_slope: "Slope",
    t_soil: "Soil",
    t_soil_none: "no SoilGrids data",
    texture: { clayey: "clayey", loamy: "loamy", sandy: "sandy" },
    t_sources_title: "Rainfall: satellite (IMERG) vs model (POWER)",
    t_sources_desc: "When the two sources disagree, the real rainfall at the point is uncertain.",
    t_window: "Window",
    t_bias: "Difference",
    windows: { primera: "Primera (May–Aug)", canicula: "Canícula (Jul–Aug)", sep_nov: "Postrera (Sep–Nov)" },
    t_missions: "Sources used",
    t_mission: "Source",
    t_variable: "Variable",
    t_res: "Resolution",
    v_imerg: "Daily satellite rainfall (2001–2025)",
    v_power: "Temperature and radiation (evapotranspiration)",
    v_srtm: "Elevation and slope",
    v_soil: "Clay and sand (0–30 cm)",
    t_json: "Download full data (JSON)",
    act_share: "Share",
    act_print: "Print",
    act_new: "Another plot",
    shared: "Summary copied. Paste it into WhatsApp or a message.",
    share_fail: "Could not copy. Select the text manually.",
    err_title: "This plot could not be analyzed",
    err_generic: "One of the data services did not respond. It is usually temporary: retry in a few minutes.",
    err_detail: "Technical detail",
    err_retry: "Retry",
    err_open: "Could not open the analysis. Check your connection and retry.",
    close: "Close",
    modal_title: "How Tempo works",
    unit_days: "days",
    nodata: "n/a",
  },
};

const NAMES = {
  es: { A: "Frijol en relevo tras maíz", B: "Sorgo (maicillo) + frijol", C: "Segunda maíz" },
  en: { A: "Relay bean after maize", B: "Sorghum (maicillo) + bean", C: "Second maize" },
};
const NAME_NOTE = { es: { A: "práctica actual" }, en: { A: "current practice" } };

// ------------------------------------------------------------------ utilidades
const $ = (id) => document.getElementById(id);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const isNum = (x) => typeof x === "number" && Number.isFinite(x);
const inBounds = (lat, lon) => lat >= BOUNDS.latMin && lat <= BOUNDS.latMax && lon >= BOUNDS.lonMin && lon <= BOUNDS.lonMax;
const isMobile = () => window.matchMedia("(max-width: 767px)").matches;

const state = {
  view: "intro",
  pick: null,
  jobId: null,
  timer: null,
  jobs: [],
  sitios: [],
  compare: new Set(),
  lang: (() => { try { return localStorage.getItem("tempo_lang") || "es"; } catch (_) { return "es"; } })(),
  lastResult: null,
};

const t = () => I18N[state.lang] || I18N.es;
const num = (x, nd = 0) => isNum(x)
  ? Number(x).toLocaleString(state.lang === "en" ? "en-US" : "es-ES", { minimumFractionDigits: nd, maximumFractionDigits: nd })
  : t().nodata;
const coord = (lat, lon, nd = 4) => `${Number(lat).toFixed(nd)}, ${Number(lon).toFixed(nd)}`;

function announce(msg) {
  const a = $("announcer");
  a.textContent = "";
  setTimeout(() => { a.textContent = msg; }, 50);
}

function showToast(msg) {
  document.querySelector(".toast")?.remove();
  const el = document.createElement("div");
  el.className = "toast";
  el.textContent = msg;
  document.body.appendChild(el);
  announce(msg);
  setTimeout(() => el.remove(), 3200);
}

// ------------------------------------------------------------------ i18n del HTML estático
function applyI18n() {
  const cur = t();
  document.documentElement.lang = state.lang;
  document.querySelectorAll("[data-i18n]").forEach((el) => { const v = cur[el.dataset.i18n]; if (typeof v === "string") el.textContent = v; });
  document.querySelectorAll("[data-i18n-html]").forEach((el) => { const v = cur[el.dataset.i18nHtml]; if (typeof v === "string") el.innerHTML = v; });
  document.querySelectorAll("[data-i18n-ph]").forEach((el) => { const v = cur[el.dataset.i18nPh]; if (typeof v === "string") el.placeholder = v; });
  document.querySelectorAll("[data-i18n-label]").forEach((el) => { const v = cur[el.dataset.i18nLabel]; if (typeof v === "string") el.setAttribute("aria-label", v); });
  const lb = $("btn-lang");
  lb.textContent = cur.lang_other;
  lb.setAttribute("aria-label", cur.lang_other_label);
  lb.setAttribute("lang", state.lang === "es" ? "en" : "es");
  $("modal-title").textContent = cur.modal_title;
  if (modal.open) renderModal();
}

// ------------------------------------------------------------------ mapa
const map = L.map("map", { zoomControl: true }).setView([13.75, -88.9], 8);
map.attributionControl.setPosition("bottomleft");

const tileStreet = L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
  maxZoom: 19, attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
});
const tileSat = L.tileLayer("https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}", {
  maxZoom: 19, attribution: "Tiles &copy; Esri, Maxar, Earthstar Geographics, USDA, USGS",
});
const tileSatLabels = L.tileLayer("https://server.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}", {
  maxZoom: 19, attribution: "&copy; Esri Boundaries &amp; Places",
});
const satGroup = L.layerGroup([tileSat, tileSatLabels]).addTo(map);

function setLayer(sat) {
  if (sat) { map.removeLayer(tileStreet); satGroup.addTo(map); }
  else { map.removeLayer(satGroup); tileStreet.addTo(map); }
  $("btn-layer-sat").classList.toggle("active", sat);
  $("btn-layer-map").classList.toggle("active", !sat);
  $("btn-layer-sat").setAttribute("aria-pressed", String(sat));
  $("btn-layer-map").setAttribute("aria-pressed", String(!sat));
}
$("btn-layer-sat").addEventListener("click", () => setLayer(true));
$("btn-layer-map").addEventListener("click", () => setLayer(false));

L.rectangle([[BOUNDS.latMin, BOUNDS.lonMin], [BOUNDS.latMax, BOUNDS.lonMax]], {
  color: "#6fbf83", weight: 1.5, dashArray: "5 5", fill: false, interactive: false,
}).addTo(map);

const jobsLayer = L.layerGroup().addTo(map);
let pickMarker = null;

function placeMarker(lat, lon) {
  if (pickMarker) pickMarker.setLatLng([lat, lon]);
  else pickMarker = L.circleMarker([lat, lon], {
    radius: 9, color: "#ffffff", weight: 3, fillColor: "#1f2420", fillOpacity: 1, interactive: false,
  }).addTo(map);
  pickMarker.bringToFront();
}

function focusMap(lat, lon) {
  const z = Math.max(map.getZoom(), 11);
  if (map.getBounds().pad(-0.2).contains([lat, lon]) && map.getZoom() >= 11) return;
  map.flyTo([lat, lon], z, { duration: 0.7 });
}

// Un toque en el mapa elige punto solo cuando no hay un análisis abierto; si lo hay, pregunta.
map.on("click", (e) => {
  const { lat, lng } = e.latlng;
  if (state.view === "intro" || state.view === "picking" || state.view === "pick") {
    choosePoint(lat, lng);
    return;
  }
  const cur = t();
  const box = document.createElement("div");
  box.className = "confirm-pop";
  box.innerHTML = `<p>${esc(cur.confirm_new)}</p><p class="coords">${coord(lat, lng)}</p>`;
  const b = document.createElement("button");
  b.type = "button";
  b.className = "primary";
  b.textContent = cur.confirm_yes;
  b.addEventListener("click", () => { map.closePopup(); choosePoint(lat, lng); });
  box.appendChild(b);
  L.popup({ closeButton: true, autoPan: true }).setLatLng(e.latlng).setContent(box).openOn(map);
  setTimeout(() => b.focus(), 50);
});

// ------------------------------------------------------------------ vistas del panel
function show(which) {
  state.view = which;
  for (const id of ["intro", "picking", "pick", "progress", "result"]) $(id).hidden = id !== which;
  $("map").classList.toggle("is-picking", which === "picking" || which === "intro" || which === "pick");
  if (which !== "progress") document.title = BASE_TITLE;
  $("view-punto").scrollTop = 0;
}

function setUrl(jobId, replace) {
  const url = jobId ? `${location.pathname}?job=${encodeURIComponent(jobId)}` : location.pathname;
  if (url === location.pathname + location.search) return;
  history[replace ? "replaceState" : "pushState"]({ job: jobId || null }, "", url);
}

function goHome(push = true) {
  stopPolling();
  state.jobId = null;
  state.lastResult = null;
  setActiveChip(null);
  showTab("punto");
  show("intro");
  setPanel("half");
  if (push) setUrl(null);
}

function startPicking() {
  stopPolling();
  showTab("punto");
  show("picking");
  if (isMobile()) setPanel("min");
  announce(t().picking_title);
}

function choosePoint(lat, lon, nombre) {
  lat = Math.round(lat * 1e6) / 1e6;
  lon = Math.round(lon * 1e6) / 1e6;
  stopPolling();
  state.pick = { lat, lon };
  state.jobId = null;
  setActiveChip(null);
  placeMarker(lat, lon);
  showTab("punto");
  show("pick");
  $("pick-coords").textContent = coord(lat, lon, 5);
  $("pick-name").value = nombre || "";
  const err = $("pick-error");
  const ok = inBounds(lat, lon);
  err.textContent = ok ? "" : t().out_of_bounds;
  err.hidden = ok;
  $("go").disabled = !ok;
  setPanel("half");
  setTimeout(() => (ok ? $("go") : $("pick-name")).focus({ preventScroll: true }), 80);
}

document.querySelectorAll("[data-cancel-pick]").forEach((b) => b.addEventListener("click", () => goHome()));
$("btn-intro-pick").addEventListener("click", startPicking);
$("btn-intro-demo").addEventListener("click", () => openSite("parcela"));

function setActiveChip(key) {
  document.querySelectorAll(".chip-btn").forEach((b) => {
    const on = b.dataset.site === key;
    b.classList.toggle("active", on);
    b.setAttribute("aria-pressed", String(on));
  });
}

function openSite(key, push = true) {
  const s = SHOWCASE_SITES[key];
  if (!s) return;
  setActiveChip(key);
  openResult(s.id, { push }).catch(() => showToast(t().err_open));
}
document.querySelectorAll(".chip-btn[data-site]").forEach((b) => b.addEventListener("click", () => openSite(b.dataset.site)));

// Coordenadas escritas a mano (también es la alternativa de teclado al mapa)
$("coords-form").addEventListener("submit", (e) => {
  e.preventDefault();
  const raw = $("coords-in").value.trim();
  const parts = raw.includes(";") ? raw.split(";").map((x) => x.replace(",", ".")) : raw.split(/[\s,]+/);
  const nums = parts.map((x) => parseFloat(x)).filter((x) => Number.isFinite(x));
  const err = $("coords-error");
  if (nums.length !== 2) { err.textContent = t().coords_bad; err.hidden = false; return; }
  err.hidden = true;
  const [lat, lon] = nums;
  focusMap(lat, lon);
  choosePoint(lat, lon);
});

// ------------------------------------------------------------------ API
async function api(path, opts) {
  const r = await fetch(path, opts);
  let body = null;
  try { body = await r.json(); } catch (_) { /* respuesta no JSON */ }
  if (!r.ok && r.status !== 202) {
    const e = new Error((body && body.error) || `HTTP ${r.status}`);
    e.status = r.status;
    throw e;
  }
  return body;
}

$("go").addEventListener("click", async () => {
  if (!state.pick) return;
  const btn = $("go");
  btn.disabled = true;
  $("pick-error").hidden = true;
  try {
    const nombre = $("pick-name").value.trim();
    const rec = await api("/api/jobs", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ lat: state.pick.lat, lon: state.pick.lon, ...(nombre ? { nombre } : {}) }),
    });
    state.jobId = rec.id;
    setUrl(rec.id);
    refreshJobs();
    if (rec.cache) await openResult(rec.id, { note: t().from_cache, push: false });
    else { renderProgress(rec); startPolling(rec.id); }
  } catch (e) {
    $("pick-error").textContent = humanError(e.message);
    $("pick-error").hidden = false;
  } finally {
    btn.disabled = false;
  }
});

function startPolling(id) {
  stopPolling();
  const tick = async () => {
    if (state.jobId !== id) return;
    try {
      const rec = await api(`/api/jobs/${id}`);
      if (rec.estado === "listo" || rec.estado === "parcial") {
        refreshJobs();
        await openResult(id, { push: false });
        document.title = t().title_done;
        return;
      }
      if (rec.estado === "error") { refreshJobs(); renderError(rec); return; }
      renderProgress(rec);
    } catch (_) {
      $("prog-msg").textContent = t().poll_retry;
    }
    state.timer = setTimeout(tick, POLL_MS);
  };
  state.timer = setTimeout(tick, POLL_MS);
}
function stopPolling() { if (state.timer) clearTimeout(state.timer); state.timer = null; }

function renderProgress(rec) {
  const cur = t();
  if (state.view !== "progress") { show("progress"); announce(cur[`st_${rec.estado}`] || rec.estado); }
  const pos = rec.estado === "en_cola" && rec.posicion > 1 ? ` · ${cur.queue_pos(rec.posicion)}` : "";
  $("prog-estado").textContent = (cur[`st_${rec.estado}`] || rec.estado) + pos;
  $("prog-msg").textContent = rec.mensaje || "";
  const pct = Math.max(4, Math.round(100 * (rec.progreso || 0)));
  $("meter-fill").style.width = pct + "%";
  $("meter").setAttribute("aria-valuenow", String(pct));
  const start = Date.parse(rec.iniciado || rec.creado || "");
  if (Number.isFinite(start)) {
    const secs = Math.max(0, Math.round((Date.now() - start) / 1000));
    $("prog-time").textContent = cur.elapsed(Math.floor(secs / 60), secs % 60);
  } else $("prog-time").textContent = "";
  document.title = cur.title_running;
  if (rec.lat !== undefined) placeMarker(rec.lat, rec.lon);
}

// Mensajes del servidor que no están pensados para personas (excepciones, HTML de un proxy)
function humanError(msg) {
  const m = String(msg || "");
  if (!m || /<\s*(html|!doctype|body)/i.test(m) || /Error:|Exception|Traceback|HTTP \d{3}/.test(m) || m.length > 240) return t().err_generic;
  return m;
}

function renderError(rec) {
  const cur = t();
  show("result");
  const friendly = humanError(rec.mensaje);
  const raw = String(rec.mensaje || "");
  $("result").innerHTML = `
    <button type="button" class="link-btn" data-home>${esc(cur.back_home)}</button>
    <p class="place">${esc(displayName(rec))} <span class="coords">${coord(rec.lat, rec.lon)}</span></p>
    <h1>${esc(cur.err_title)}</h1>
    <p class="error">${esc(friendly)}</p>
    ${missingHtml(rec.faltantes, [])}
    ${friendly !== raw && raw ? `<details class="err-detail"><summary>${esc(cur.err_detail)}</summary><pre>${esc(raw.slice(0, 1200))}</pre></details>` : ""}
    <div class="row-actions"><button type="button" class="primary" data-retry>${esc(cur.err_retry)}</button></div>`;
  $("result").querySelector("[data-retry]").addEventListener("click", () => { choosePoint(rec.lat, rec.lon, rec.nombre); $("go").click(); });
  $("result").querySelector("[data-home]").addEventListener("click", () => goHome());
  announce(cur.err_title);
}

// ------------------------------------------------------------------ nombres de lugar
function nearestSite(lat, lon) {
  let best = null, bestD = Infinity;
  for (const s of state.sitios) {
    const label = s.municipio || s.departamento || (s.nombre && !/usuario/i.test(s.nombre) ? s.nombre.replace(/^Cerca de\s+/i, "") : null);
    if (!label || !isNum(s.lat) || !isNum(s.lon)) continue;
    const d = Math.hypot((s.lat - lat) * 111, (s.lon - lon) * 108);
    if (d < bestD) { bestD = d; best = label; }
  }
  return bestD <= 30 ? best : null;
}

function displayName(r) {
  const cur = t();
  const demo = DEMO_BY_ID[r.id];
  if (demo) return `${cur.example}: ${cur[`ex_${demo}`]}`;
  if (r.nombre && !/usuario/i.test(r.nombre)) return r.nombre;
  const near = nearestSite(r.lat, r.lon);
  return near ? cur.near(near) : cur.unnamed;
}

function missingHtml(faltantes, advertencias) {
  const cur = t();
  const f = faltantes || [], w = advertencias || [];
  if (!f.length && !w.length) return "";
  return `<div class="notice" role="note">
    ${f.length ? `<p class="notice-title">${esc(cur.partial_title)}</p><p>${esc(cur.partial_desc)}</p><ul>${f.map((x) => `<li lang="es">${esc(x)}</li>`).join("")}</ul>` : ""}
    ${w.length ? `<p class="notice-title">${esc(cur.warnings_title)}</p><ul>${w.map((x) => `<li lang="es">${esc(x)}</li>`).join("")}</ul>` : ""}
  </div>`;
}

// ------------------------------------------------------------------ resultado
async function openResult(id, { note, push = true } = {}) {
  stopPolling();
  state.jobId = id;
  const [rec, res] = await Promise.all([api(`/api/jobs/${id}`), api(`/api/jobs/${id}/result`)]);
  if (state.jobId !== id) return;
  state.lastResult = { rec, res, note };
  state.pick = { lat: rec.lat, lon: rec.lon };
  setActiveChip(DEMO_BY_ID[id] || null);
  placeMarker(rec.lat, rec.lon);
  focusMap(rec.lat, rec.lon);
  map.closePopup();
  showTab("punto");
  renderResult();
  if (push) setUrl(id);
  setPanel(isMobile() ? "full" : "half");
  const rr = recOf(res.resumen);
  announce(rr ? `${t().rec_kind(res.resumen.anio || "")}: ${verdictTitle(res.resumen)}. ${t().conf[rr.confianza] || ""}` : verdictTitle(res.resumen));
}

function renderResult() {
  if (!state.lastResult) return;
  const { rec, res, note } = state.lastResult;
  show("result");
  $("result").innerHTML = resultHtml(rec, res.resumen || {}, res.analisis || {}, note);
  const root = $("result");
  root.querySelector("[data-home]").addEventListener("click", () => goHome());
  root.querySelector("[data-share]").addEventListener("click", () => share(rec, res.resumen || {}));
  root.querySelector("[data-print]").addEventListener("click", () => window.print());
  root.querySelector("[data-new]").addEventListener("click", startPicking);
}

const stratName = (k) => NAMES[state.lang]?.[k] || NAMES.es[k] || k;

const recOf = (r) => (r && r.veredicto && r.veredicto.recomendacion) || null;
const LOCALE = () => (state.lang === "en" ? "en-US" : "es-ES");
const fmtDate = (iso) => {
  if (!iso) return null;
  const d = new Date(iso.length === 10 ? `${iso}T12:00:00` : iso);
  return Number.isNaN(d.getTime()) ? null : d.toLocaleDateString(LOCALE(), { day: "numeric", month: "short", year: "numeric" });
};

function verdictTitle(r) {
  const v = r.veredicto || {};
  const rc = recOf(r);
  if (rc) return stratName(rc.clave);
  if (state.lang === "es" && v.titulo) return v.titulo;
  const y = r.anio || "";
  return v.claro ? `${stratName(v.mejor)} is clearly the best option for this point in ${y}`
    : `No option is clearly better for this point in ${y}`;
}

function verdictText(r) {
  const v = r.veredicto || {};
  const rc = recOf(r);
  if (rc) {
    if (state.lang === "es" && rc.texto) return rc.texto;
    if (rc.origen === "veredicto") return "It passes the four verdict checks: enough margin, no change without the 150 mm bean rule or with another rainfall source, and the model detects the documented droughts.";
    const w = rc.peor_puntaje || {}, pick = rc.clave;
    const second = Object.keys(w).filter((k) => k !== pick).sort((a, b) => w[b] - w[a])[0];
    const regret = (rc.arrepentimiento_max || {})[pick] || 0;
    const worstTxt = `its lowest score is ${num(w[pick], 3)}, versus ${num(w[second], 3)} for ${stratName(second).toLowerCase()}`;
    const wins = (rc.gana_en || []).length;
    if (wins === rc.n_escenarios) return `${stratName(pick)} is first or tied in all ${rc.n_escenarios} scenarios computed; ${worstTxt}.`;
    return `No option wins in every scenario. ${stratName(pick)} holds up best in the worst case: across ${rc.n_escenarios} scenarios ${worstTxt}. It is first or tied in ${wins} of ${rc.n_escenarios}${regret > 0 ? `, and otherwise at most ${num(regret, 3)} points behind.` : "."}`;
  }
  if (state.lang === "es" && v.texto) return v.texto;
  const m = num(v.margen, 3);
  return v.claro
    ? `It scores ${m} points above the second option and passes the checks below.`
    : `The highest score goes to ${stratName(v.mejor).toLowerCase()}, ${m} points above the second option, and the result depends on unvalidated assumptions. Read it as a description of the season, not as a recommendation.`;
}

function postreraCycle(an, key) {
  const st = (an.strategies || []).find((s) => s.key === key);
  if (!st) return { days: null, nfix: false };
  const post = (st.rotation || []).filter((x) => x.season === "postrera").map((x) => x.end - x.start);
  return { days: post.length ? Math.max(...post) : null, nfix: !!st.attributes?.nitrogen_fixing };
}

function resultHtml(rec, r, an, note) {
  const cur = t();
  const v = r.veredicto || {};
  const ll = r.lluvia || {}, su = r.suelo || {}, te = r.terreno || {};
  const claro = !!v.claro;
  const rc = recOf(r);
  const recKey = rc ? rc.clave : null;

  // Opciones: del resumen del modelo, ordenadas por puntaje
  const estr = (r.estrategias || []).slice().sort((a, b) => (b.puntaje ?? -1) - (a.puntaje ?? -1));
  const rows = estr.map((s, i) => {
    const k = s.clave;
    const cyc = postreraCycle(an, k);
    const sub = [cyc.days ? cur.cycle(cyc.days) : null, cyc.nfix ? cur.nfix : null].filter(Boolean).join(" · ");
    const n = s.anios_parecidos, fails = isNum(s.fallo_pct) && isNum(n) ? Math.round((s.fallo_pct / 100) * n) : null;
    let tag = "";
    if (recKey && k === recKey) tag = `<span class="opt-tag is-best">${esc(rc.origen === "veredicto" ? cur.rec_tag : cur.rec_tag_robust)}</span>`;
    else if (i === 0) tag = `<span class="opt-tag ${!recKey && claro ? "is-best" : ""}">${esc(!recKey && claro ? cur.tag_best : cur.tag_top)}</span>`;
    const isTop = recKey ? k === recKey : i === 0;
    const note2 = NAME_NOTE[state.lang]?.[k];
    const pct = isNum(s.puntaje) ? Math.max(0, Math.min(100, s.puntaje * 100)) : 0;
    return `<li class="opt ${isTop ? "is-top" : ""}">
      <div class="opt-head">
        <span class="opt-key" aria-hidden="true">${esc(k)}</span>
        <span class="opt-name">${esc(stratName(k))}${note2 ? ` <span class="opt-note">(${esc(note2)})</span>` : ""}</span>
        <span class="opt-score"><span class="sr-only">${esc(cur.opts_score)}: </span>${num(s.puntaje, 3)}</span>
      </div>
      <div class="opt-bar" aria-hidden="true"><span style="width:${pct.toFixed(1)}%"></span></div>
      <p class="opt-sub">${tag}${esc(sub)}${sub && fails !== null ? " · " : ""}${fails !== null ? esc(cur.fails(fails, n)) : ""}</p>
    </li>`;
  }).join("");

  const conds = (v.condiciones || []).map((c) => `
    <li class="${c.cumple ? "ok" : "no"}">
      <span class="cond-mark">${c.cumple
        ? '<svg viewBox="0 0 16 16" width="14" height="14" aria-hidden="true"><path d="M3 8.5 6.5 12 13 4.5" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>'
        : '<svg viewBox="0 0 16 16" width="14" height="14" aria-hidden="true"><path d="M4 4l8 8M12 4l-8 8" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>'}
        <span class="sr-only">${esc(c.cumple ? cur.cond_ok : cur.cond_no)}:</span></span>
      <span lang="es">${esc(String(c.texto || "").replace(/\s*\(CHECK 1\)/, ""))}</span>
    </li>`).join("");

  // La temporada: solo valores del modelo; el suelo por defecto se marca
  const soilDefault = su.clase_usada === "default" || !su.textura;
  const cls = cur.canicula_cls[ll.canicula_clase] || ll.canicula_clase || "";
  const facts = [
    isNum(ll.canicula_dias) ? [cur.f_canicula, cur.f_canicula_val(ll.canicula_dias, cls)] : null,
    isNum(ll.jul_ago_mediana_mm) ? [cur.f_rain_ja, cur.f_rain_ja_val(isNum(ll.jul_ago_actual_mm) ? num(ll.jul_ago_actual_mm) : null, num(ll.jul_ago_mediana_mm))] : null,
    isNum(su.whc_mm) ? [cur.f_soil, `${num(su.whc_mm)} mm${soilDefault ? ` (${cur.f_soil_default})` : su.radio_m ? ` (${cur.soil_radius(su.radio_m / 1000)})` : ""}`] : null,
  ].filter(Boolean);

  const win = ll.ventanas_imerg_vs_power || {};
  const winRows = Object.keys(win).map((k) => {
    const w = win[k];
    return `<tr><td>${esc(cur.windows[k] || k)}</td><td class="n">${num(w.mean_imerg_mm)} mm</td><td class="n">${num(w.mean_power_mm)} mm</td>
      <td class="n">${isNum(w.bias_pct) ? num(w.bias_pct) + " %" : cur.nodata}</td></tr>`;
  }).join("");

  const texture = su.textura ? (cur.texture[su.textura] || su.textura) : cur.t_soil_none;
  const dd = r.datos || {};
  const dataLine = dd.lluvia_hasta ? `<p class="data-line">${esc(cur.data_line(fmtDate(dd.lluvia_hasta), fmtDate(dd.descargado_utc)))}</p>` : "";
  const ts = Array.isArray(r.temporada_actual) ? r.temporada_actual : [];
  const sowing = ts.map((x) => x.siembra).filter(Boolean).sort()[0];
  const plantedHtml = sowing && dd.lluvia_hasta && sowing <= dd.lluvia_hasta
    ? `<p class="planted-note" role="note">${esc(cur.planted(r.anio || "", fmtDate(sowing)))}</p>` : "";
  const sn = (ll.ventanas_imerg_vs_power || {}).sep_nov || {};
  const rainUnc = isNum(sn.mean_imerg_mm) && isNum(sn.mean_power_mm) && isNum(ll.cambios_con_power)
    ? `<p class="rain-unc">${esc(cur.rain_unc(num(sn.mean_imerg_mm), num(sn.mean_power_mm), ll.cambios_con_power, ll.anios_comparados || sn.n_years || ""))}</p>` : "";
  const va = r.validacion || {};
  const picksTxt = Object.entries(va.elecciones || {}).sort((a, b) => b[1] - a[1]).map(([k, n]) => `${stratName(k)} (${cur.val_years(n)})`).join(", ");
  const valHtml = isNum(va.tempo) ? `<section class="block" aria-labelledby="val-h">
      <h2 id="val-h">${esc(cur.val_title)}</h2>
      <p class="fineprint">${esc(cur.val_desc)}</p>
      <ul class="val">
        ${picksTxt ? `<li>${esc(cur.val_picks(picksTxt))}</li>` : ""}
        <li>${esc(cur.val_scores(num(va.tempo, 2), num(va.practica_actual, 2), num(va.misma_siempre, 2)))}</li>
        ${isNum(va.margen_medio) ? `<li>${esc(cur.val_margin(num(va.margen_medio, 2), isNum(va.margen_sin_regla) ? num(va.margen_sin_regla, 2) : cur.nodata))}${isNum(va.margen_sin_regla) && va.margen_sin_regla < va.margen_medio ? ` ${esc(cur.val_rule)}` : ""}</li>` : ""}
        ${isNum(va.misma_siempre) && va.misma_siempre >= va.tempo ? `<li>${esc(cur.val_same)}</li>` : ""}
      </ul>
      <p class="fineprint">${esc(cur.val_diff)}</p>
    </section>` : "";
  const seasonHtml = ts.length && dd.lluvia_hasta ? `<section class="block" aria-labelledby="season-h">
      <h2 id="season-h">${esc(cur.season_title(r.anio || ""))}</h2>
      <p class="fineprint">${esc(cur.season_desc(fmtDate(dd.lluvia_hasta)))}</p>
      <ul class="season">${ts.slice().sort((a, b) => a.clave.localeCompare(b.clave)).map((x) => {
        const cls = Object.values(x.cultivos || {}).map((c) => cur.cls_name[c.class] || c.class);
        const state = x.completa ? cur.season_done(num(x.puntaje, 2), cls.join(", ")) : cur.season_field(fmtDate(x.cosecha), x.dias_faltan);
        return `<li class="${x.completa ? "is-done" : "is-field"}"><span class="opt-key" aria-hidden="true">${esc(x.clave)}</span><span><strong>${esc(stratName(x.clave))}</strong><br><span class="muted">${esc(state)}</span></span></li>`;
      }).join("")}</ul>
    </section>` : "";
  const basisHtml = rc && Array.isArray(rc.escenarios) && rc.escenarios.length ? basisTable(rc, cur, dd.respaldo_clima) : "";
  const demo = DEMO_BY_ID[rec.id];
  const missing = (r.faltantes && r.faltantes.length) ? r.faltantes : (rec.faltantes || []);

  return `
    <button type="button" class="link-btn" data-home>${esc(cur.back_home)}</button>
    <p class="place">${esc(displayName(rec))} <span class="coords">${coord(rec.lat, rec.lon)}</span></p>
    ${dataLine}
    ${dd.respaldo_clima === "meteomatics" ? `<p class="data-line">${esc(cur.backup_line)}</p>` : ""}
    ${demo ? `<p class="demo-line">${esc(cur.demo_line)}</p>` : ""}
    ${plantedHtml}
    ${note ? `<p class="demo-line">${esc(note)}</p>` : ""}

    <section class="verdict ${rc ? `is-rec conf-${esc(rc.confianza)}` : claro ? "is-clear" : "is-open"}" aria-labelledby="verdict-h">
      <p class="verdict-kind">${esc(rc ? cur.rec_kind(r.anio || "") : cur.verdict_kind(r.anio || ""))}</p>
      <h1 id="verdict-h">${esc(verdictTitle(r))}</h1>
      ${rc ? `<p class="conf-line"><span class="conf-badge conf-${esc(rc.confianza)}">${esc(cur.conf[rc.confianza] || rc.confianza)}</span> <span class="conf-help">${esc(cur.conf_help[rc.confianza] || "")}</span></p>` : ""}
      <p class="verdict-text">${esc(verdictText(r))}</p>
      ${rainUnc}
      ${rc && rc.limites && rc.limites.length ? `<ul class="limits">${rc.limites.map((x) => `<li lang="es">${esc(x)}</li>`).join("")}</ul>` : ""}
    </section>

    ${missingHtml(missing, r.advertencias)}

    <section class="block" aria-labelledby="opts-h">
      <h2 id="opts-h">${esc(cur.opts_title)}</h2>
      <ol class="opts">${rows}</ol>
      ${isNum(v.margen) ? `<p class="fineprint">${esc(rc && rc.origen === "robusta" ? cur.margin_line_rec(num(v.margen, 3)) : cur.margin_line(num(v.margen, 3)))}</p>` : ""}
      <p class="fineprint">${esc(cur.opts_help)}</p>
    </section>

    ${seasonHtml}

    ${basisHtml}

    ${valHtml}

    ${conds ? `<section class="block" aria-labelledby="why-h">
      <h2 id="why-h">${esc(rc && rc.origen === "robusta" ? cur.why_title_rec : cur.why_title)}</h2>
      ${rc && rc.origen === "robusta" ? `<p class="fineprint">${esc(cur.why_desc_rec)}</p>` : ""}
      <ul class="conds">${conds}</ul>
    </section>` : ""}

    ${facts.length ? `<section class="block" aria-labelledby="facts-h">
      <h2 id="facts-h">${esc(cur.facts_title)}</h2>
      <dl class="facts">${facts.map(([k, val]) => `<div><dt>${esc(k)}</dt><dd>${esc(val)}</dd></div>`).join("")}</dl>
    </section>` : ""}

    ${hydrographHtml(an.chart, ll.canicula_dias, r.anio)}

    <details class="tech">
      <summary>${esc(cur.tech_title)}</summary>
      <dl class="facts compact">
        <div><dt>${esc(cur.t_elev)}</dt><dd>${isNum(te.elevation_m) ? `${num(te.elevation_m)} m` : cur.nodata}</dd></div>
        <div><dt>${esc(cur.t_slope)}</dt><dd>${isNum(te.slope_pct) ? `${num(te.slope_pct, 1)} %` : cur.nodata}</dd></div>
        <div><dt>${esc(cur.t_soil)}</dt><dd>${esc(texture)}</dd></div>
      </dl>
      ${dd.lluvia_hasta ? `<p class="fineprint">${esc(cur.data_detail(fmtDate(dd.imerg_hasta), fmtDate(dd.power_hasta)))}${su.fuente ? ` · ${esc(su.fuente)}` : ""}</p>` : ""}
      ${winRows ? `<h3>${esc(cur.t_sources_title)}</h3><p class="fineprint">${esc(cur.t_sources_desc)}</p>
      <div class="table-wrap"><table>
        <thead><tr><th>${esc(cur.t_window)}</th><th class="n">IMERG</th><th class="n">POWER</th><th class="n">${esc(cur.t_bias)}</th></tr></thead>
        <tbody>${winRows}</tbody></table></div>` : ""}
      <h3>${esc(cur.t_missions)}</h3>
      <div class="table-wrap"><table>
        <thead><tr><th>${esc(cur.t_mission)}</th><th>${esc(cur.t_variable)}</th><th class="n">${esc(cur.t_res)}</th></tr></thead>
        <tbody>
          <tr><td>NASA GPM IMERG V07</td><td>${esc(cur.v_imerg)}</td><td class="n">~10 km</td></tr>
          <tr><td>NASA POWER</td><td>${esc(cur.v_power)}</td><td class="n">~50 km</td></tr>
          <tr><td>NASA SRTM GL1</td><td>${esc(cur.v_srtm)}</td><td class="n">30 m</td></tr>
          <tr><td>ISRIC SoilGrids v2</td><td>${esc(cur.v_soil)}</td><td class="n">250 m</td></tr>
        </tbody></table></div>
      <p><a href="/api/jobs/${encodeURIComponent(rec.id)}/result" target="_blank" rel="noopener">${esc(cur.t_json)}</a></p>
    </details>

    <div class="result-actions">
      <button type="button" class="primary" data-share>${esc(cur.act_share)}</button>
      <button type="button" class="secondary" data-print>${esc(cur.act_print)}</button>
      <button type="button" class="secondary" data-new>${esc(cur.act_new)}</button>
    </div>`;
}

// Tabla de escenarios: puntaje de cada opción en cada supuesto y su peor caso
function basisTable(rc, cur, backup) {
  const keys = [...new Set(rc.escenarios.flatMap((e) => Object.keys(e.puntajes || {})))].sort();
  const scName = (e) => [(backup === "meteomatics" && e.rain === "power") ? cur.sc_rain_mm : (cur.sc_rain[e.rain] || e.rain), e.bean_rule === false ? cur.sc_rule_off : cur.sc_rule_on,
    isNum(e.whc_mm) ? cur.sc_soil(e.whc_mm) : null].filter(Boolean).join(" · ");
  const worst = {};
  for (const k of keys) {
    const vals = rc.escenarios.map((e) => e.puntajes?.[k]).filter(isNum);
    worst[k] = (rc.peor_puntaje && isNum(rc.peor_puntaje[k])) ? rc.peor_puntaje[k] : (vals.length ? Math.min(...vals) : null);
  }
  const cell = (k, v, best) => `<td class="n${k === rc.clave ? " is-rec" : ""}${best ? " is-best" : ""}">${num(v, 3)}</td>`;
  const rows = rc.escenarios.map((e) => `<tr><th scope="row">${esc(scName(e))}</th>${keys.map((k) => cell(k, e.puntajes?.[k], k === e.mejor)).join("")}</tr>`).join("");
  return `<section class="block" aria-labelledby="basis-h">
    <h2 id="basis-h">${esc(cur.basis_title)}</h2>
    <p class="fineprint">${esc(cur.basis_desc(rc.escenarios.length))}</p>
    <div class="table-wrap"><table class="basis">
      <thead><tr><th>${esc(cur.basis_scenario)}</th>${keys.map((k) => `<th class="n${k === rc.clave ? " is-rec" : ""}"><abbr title="${esc(stratName(k))}">${esc(k)}</abbr></th>`).join("")}</tr></thead>
      <tbody>${rows}</tbody>
      <tfoot><tr><th scope="row">${esc(cur.basis_worst)}</th>${keys.map((k) => `<td class="n${k === rc.clave ? " is-rec" : ""}">${num(worst[k], 3)}</td>`).join("")}</tr></tfoot>
    </table></div>
    <p class="fineprint">${keys.map((k) => `${esc(k)} = ${esc(stratName(k))}`).join(" · ")}</p>
  </section>`;
}

// Gráfico de lluvia: banda p20–p80, mediana y el año en curso, de mayo a noviembre
function hydrographHtml(chart, caniculaDias, anio) {
  if (!chart || !Array.isArray(chart.doy) || !Array.isArray(chart.p50)) return "";
  const cur = t();
  const W = 400, H = 170, padL = 34, padR = 10, padT = 14, padB = 22;
  const plotW = W - padL - padR, plotH = H - padT - padB;
  const d0 = 121, d1 = 334;
  const idx = chart.doy.map((d, i) => (d >= d0 && d <= d1 ? i : -1)).filter((i) => i >= 0);
  if (!idx.length) return "";
  const curr = chart.current || {};
  const currPts = idx.filter((i) => isNum(curr[String(chart.doy[i])]));
  const maxVal = Math.max(10, ...idx.map((i) => chart.p80?.[i] || 0), ...currPts.map((i) => curr[String(chart.doy[i])]));
  const X = (d) => padL + ((d - d0) / (d1 - d0)) * plotW;
  const Y = (v) => padT + plotH - (Math.min(maxVal, Math.max(0, v || 0)) / maxVal) * plotH;
  const pts = (arr) => arr.map(([d, v]) => `${X(d).toFixed(1)},${Y(v).toFixed(1)}`).join(" ");

  const band = Array.isArray(chart.p20) && Array.isArray(chart.p80)
    ? `<polygon class="h-band" points="${pts(idx.map((i) => [chart.doy[i], chart.p80[i]]))} ${pts(idx.slice().reverse().map((i) => [chart.doy[i], chart.p20[i]]))}"/>` : "";
  const median = `<polyline class="h-median" points="${pts(idx.map((i) => [chart.doy[i], chart.p50[i]]))}"/>`;
  const current = currPts.length ? `<polyline class="h-current" points="${pts(currPts.map((i) => [chart.doy[i], curr[String(chart.doy[i])]]))}"/>` : "";
  const can = isNum(caniculaDias) && caniculaDias > 0
    ? `<rect class="h-canicula" x="${X(196).toFixed(1)}" y="${padT}" width="${Math.max(6, X(196 + caniculaDias) - X(196)).toFixed(1)}" height="${plotH}"/>` : "";
  const months = (state.lang === "en" ? ["May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov"] : ["may", "jun", "jul", "ago", "sep", "oct", "nov"]);
  const mDoy = [135, 166, 196, 227, 258, 288, 319];
  const monthsSvg = months.map((m, i) => `<text class="h-axis" x="${X(mDoy[i]).toFixed(1)}" y="${H - 6}" text-anchor="middle">${m}</text>`).join("");
  const grid = [0, maxVal / 2, maxVal].map((v) => `<line class="h-grid" x1="${padL}" x2="${W - padR}" y1="${Y(v).toFixed(1)}" y2="${Y(v).toFixed(1)}"/>
    <text class="h-axis" x="${padL - 5}" y="${(Y(v) + 3).toFixed(1)}" text-anchor="end">${Math.round(v)}</text>`).join("");

  return `<section class="block" aria-labelledby="hydro-h">
    <h2 id="hydro-h">${esc(cur.hydro_title)}</h2>
    <p class="fineprint">${esc(cur.hydro_desc)}</p>
    <figure class="chart">
      <svg viewBox="0 0 ${W} ${H}" role="img" aria-label="${esc(cur.hydro_aria(anio || ""))}">${grid}${can}${band}${median}${current}${monthsSvg}</svg>
      <figcaption class="chart-legend">
        <span><i class="k-band"></i>${esc(cur.hydro_band)}</span>
        <span><i class="k-median"></i>${esc(cur.hydro_median)}</span>
        ${current ? `<span><i class="k-current"></i>${esc(cur.hydro_current)} (${esc(anio || "")})</span>` : ""}
        ${can ? `<span><i class="k-canicula"></i>${esc(cur.hydro_canicula)}</span>` : ""}
      </figcaption>
    </figure>
  </section>`;
}

// ------------------------------------------------------------------ compartir
function shareText(rec, r) {
  const v = r.veredicto || {}, ll = r.lluvia || {}, su = r.suelo || {};
  const en = state.lang === "en";
  const scores = (r.estrategias || []).map((s) => `${s.clave} ${num(s.puntaje, 3)}`).join(" · ");
  const soilDefault = su.clase_usada === "default" || !su.textura;
  const missing = r.faltantes || rec.faltantes || [];
  const lines = [
    `Tempo · ${t().season(r.anio || "")} · ${displayName(rec)} (${coord(rec.lat, rec.lon)})`,
    recOf(r) ? `${t().rec_kind(r.anio || "")}: ${verdictTitle(r)} (${t().conf[recOf(r).confianza] || recOf(r).confianza})` : verdictTitle(r),
    verdictText(r),
    scores ? `${en ? "Scores (1 = good harvest)" : "Puntajes (1 = buena cosecha)"}: ${scores}  [A ${stratName("A")}, B ${stratName("B")}, C ${stratName("C")}]` : null,
    isNum(ll.canicula_dias) ? `${en ? "Canícula" : "Canícula"}: ${ll.canicula_dias} ${t().unit_days}.` + (isNum(ll.jul_ago_actual_mm) && isNum(ll.jul_ago_mediana_mm) ? ` ${en ? "Jul–Aug rain" : "Lluvia jul–ago"}: ${num(ll.jul_ago_actual_mm)} mm (${en ? "normal" : "normal"} ${num(ll.jul_ago_mediana_mm)} mm).` : "") : null,
    isNum(su.whc_mm) ? `${en ? "Soil available water" : "Agua útil del suelo"}: ${num(su.whc_mm)} mm${soilDefault ? ` (${t().f_soil_default})` : ""}.` : null,
    missing.length ? `${en ? "Missing sources" : "Fuentes faltantes"}: ${missing.length}.` : null,
    (r.datos && r.datos.lluvia_hasta) ? t().data_line(fmtDate(r.datos.lluvia_hasta), fmtDate(r.datos.descargado_utc)) + "." : null,
    `${en ? "Data" : "Datos"}: NASA GPM IMERG, NASA POWER, NASA SRTM, ISRIC SoilGrids.`,
    `${location.origin}${location.pathname}?job=${rec.id}`,
  ];
  return lines.filter(Boolean).join("\n");
}

async function share(rec, r) {
  const text = shareText(rec, r);
  if (navigator.share) {
    try { await navigator.share({ title: "Tempo", text }); return; } catch (e) { if (e && e.name === "AbortError") return; }
  }
  try {
    if (navigator.clipboard?.writeText) await navigator.clipboard.writeText(text);
    else {
      const ta = document.createElement("textarea");
      ta.value = text; ta.style.position = "fixed"; ta.style.opacity = "0";
      document.body.appendChild(ta); ta.select(); document.execCommand("copy"); ta.remove();
    }
    showToast(t().shared);
  } catch (_) {
    showToast(t().share_fail);
  }
}

// ------------------------------------------------------------------ guardados y comparación
async function refreshJobs() {
  try { state.jobs = (await api("/api/jobs")).jobs || []; } catch (_) { return; }
  renderJobs();
}

function renderJobs() {
  const cur = t();
  jobsLayer.clearLayers();
  const ul = $("jobs");
  ul.innerHTML = "";
  $("n-jobs").textContent = state.jobs.length ? `(${state.jobs.length})` : "";
  if (!state.jobs.length) ul.innerHTML = `<li class="muted empty">${esc(cur.list_empty)}</li>`;
  for (const j of [...state.jobs].reverse()) {
    const name = displayName(j);
    const m = L.circleMarker([j.lat, j.lon], { radius: 8, color: "#fff", weight: 2, fillColor: COLORS[j.estado] || "#666", fillOpacity: 0.95 })
      .bindTooltip(`${esc(name)} · ${esc(cur[`st_${j.estado}`] || j.estado)}`)
      .on("click", (ev) => { L.DomEvent.stopPropagation(ev); openJob(j); });
    jobsLayer.addLayer(m);

    const done = j.estado === "listo" || j.estado === "parcial";
    const li = document.createElement("li");
    li.className = "job";
    const jr = j.veredicto && j.veredicto.recomendacion;
    const verdict = jr ? `${cur.rec_tag}: ${stratName(jr.clave)} · ${cur.conf[jr.confianza] || jr.confianza}`
      : j.veredicto ? (state.lang === "es" ? j.veredicto.titulo : (j.veredicto.claro ? "One option is clearly better" : "No option clearly wins")) : humanError(j.mensaje);
    const when = Date.parse(j.creado || "");
    li.innerHTML = `
      ${done ? `<input type="checkbox" class="job-check" aria-label="${esc(cur.select_for_compare(name))}" ${state.compare.has(j.id) ? "checked" : ""}>` : `<span class="job-check-sp"></span>`}
      <button type="button" class="job-open">
        <span class="t"><span class="dot st-${esc(j.estado)}" aria-hidden="true"></span>${esc(name)}</span>
        <span class="s">${esc(cur[`st_${j.estado}`] || j.estado)}${Number.isFinite(when) ? ` · ${new Date(when).toLocaleDateString(state.lang === "en" ? "en-US" : "es-ES", { day: "numeric", month: "short" })}` : ""} · ${coord(j.lat, j.lon, 3)}</span>
        <span class="s">${esc(verdict)}</span>
      </button>`;
    li.querySelector(".job-open").addEventListener("click", () => openJob(j));
    const cb = li.querySelector(".job-check");
    if (cb) cb.addEventListener("change", () => {
      if (cb.checked && state.compare.size >= 3) { cb.checked = false; showToast(cur.compare_max); return; }
      cb.checked ? state.compare.add(j.id) : state.compare.delete(j.id);
      updateCompareBar();
    });
    ul.appendChild(li);
  }
  if (pickMarker) pickMarker.bringToFront();
  updateCompareBar();
}

function updateCompareBar() {
  const n = state.compare.size;
  $("compare-bar").hidden = n < 2;
  $("compare-count").textContent = t().compare_n(n);
}

function openJob(j) {
  focusMap(j.lat, j.lon);
  if (j.estado === "listo" || j.estado === "parcial") openResult(j.id).catch(() => showToast(t().err_open));
  else if (j.estado === "error") { state.jobId = j.id; showTab("punto"); renderError(j); setUrl(j.id); }
  else { state.jobId = j.id; showTab("punto"); renderProgress(j); startPolling(j.id); setUrl(j.id); }
}

$("btn-compare").addEventListener("click", async () => {
  const cur = t();
  const ids = [...state.compare];
  const box = $("compare");
  box.hidden = false;
  box.innerHTML = `<p class="muted">${esc(cur.compare_loading)}</p>`;
  let data;
  try {
    data = await Promise.all(ids.map(async (id) => ({ rec: state.jobs.find((x) => x.id === id) || (await api(`/api/jobs/${id}`)), res: await api(`/api/jobs/${id}/result`) })));
  } catch (_) { box.innerHTML = `<p class="error">${esc(cur.err_open)}</p>`; return; }
  const col = (fn) => data.map((d) => `<td>${fn(d.res.resumen || {}, d.rec)}</td>`).join("");
  const sc = (k) => (r) => { const s = (r.estrategias || []).find((x) => x.clave === k); return s ? num(s.puntaje, 3) : cur.nodata; };
  box.innerHTML = `
    <h2>${esc(cur.compare_title)}</h2>
    <div class="table-wrap"><table class="compare-table">
      <thead><tr><th></th>${data.map((d) => `<th>${esc(displayName(d.rec))}</th>`).join("")}</tr></thead>
      <tbody>
        <tr><th>${esc(cur.verdict_row)}</th>${col((r) => { const rr = recOf(r); return rr ? `<strong>${esc(stratName(rr.clave))}</strong><br><span class="muted">${esc(cur.conf[rr.confianza] || rr.confianza)}</span>` : esc(r.veredicto?.claro ? cur.verdict_clear_lbl : cur.verdict_unclear_lbl); })}</tr>
        <tr><th>A · ${esc(stratName("A"))}</th>${col(sc("A"))}</tr>
        <tr><th>B · ${esc(stratName("B"))}</th>${col(sc("B"))}</tr>
        <tr><th>C · ${esc(stratName("C"))}</th>${col(sc("C"))}</tr>
        <tr><th>${esc(cur.f_canicula)}</th>${col((r) => isNum(r.lluvia?.canicula_dias) ? `${r.lluvia.canicula_dias} ${esc(cur.unit_days)}` : cur.nodata)}</tr>
        <tr><th>${esc(cur.f_rain_ja)}</th>${col((r) => isNum(r.lluvia?.jul_ago_actual_mm) ? `${num(r.lluvia.jul_ago_actual_mm)} / ${num(r.lluvia.jul_ago_mediana_mm)} mm` : cur.nodata)}</tr>
        <tr><th>${esc(cur.f_soil)}</th>${col((r) => isNum(r.suelo?.whc_mm) ? `${num(r.suelo.whc_mm)} mm${(r.suelo.clase_usada === "default" || !r.suelo.textura) ? "*" : ""}` : cur.nodata)}</tr>
      </tbody></table></div>
    <p class="fineprint">* ${esc(cur.f_soil_default)}. ${esc(cur.opts_help)}</p>
    <button type="button" class="secondary" id="btn-compare-close">${esc(cur.compare_close)}</button>`;
  $("btn-compare-close").addEventListener("click", () => { box.hidden = true; box.innerHTML = ""; });
  box.scrollIntoView({ block: "start", behavior: "smooth" });
});

// ------------------------------------------------------------------ buscador
async function loadSitios() {
  try { state.sitios = (await api("/api/sitios")).sitios || []; } catch (_) { state.sitios = []; }
  $("sitios").innerHTML = state.sitios.map((s) => `<option value="${esc(siteLabel(s))}"></option>`).join("");
  if (state.jobs.length) renderJobs();
  if (state.view === "result") renderResult();
}
const siteLabel = (s) => [s.nombre, s.municipio, s.departamento, s.pais].filter(Boolean).filter((x, i, a) => a.indexOf(x) === i).join(", ");
const norm = (s) => String(s).normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();

$("search").addEventListener("submit", (e) => {
  e.preventDefault();
  const q = norm($("q").value.trim());
  if (!q) return;
  const s = state.sitios.find((x) => norm(siteLabel(x)) === q) || state.sitios.find((x) => norm(siteLabel(x)).includes(q));
  if (!s) { $("q").setCustomValidity(t().search_none); $("q").reportValidity(); setTimeout(() => $("q").setCustomValidity(""), 2500); return; }
  toggleSearch(false);
  focusMap(s.lat, s.lon);
  choosePoint(s.lat, s.lon, s.nombre);
});

function toggleSearch(open) {
  const s = $("search");
  const willOpen = open ?? !s.classList.contains("is-open");
  s.classList.toggle("is-open", willOpen);
  $("btn-search-toggle").setAttribute("aria-expanded", String(willOpen));
  if (willOpen) $("q").focus();
}
$("btn-search-toggle").addEventListener("click", () => toggleSearch());

// ------------------------------------------------------------------ pestañas (con flechas) y panel
function showTab(which) {
  for (const k of ["punto", "lista"]) {
    const tab = $(`tab-${k}`);
    tab.setAttribute("aria-selected", String(k === which));
    tab.tabIndex = k === which ? 0 : -1;
    $(`view-${k}`).hidden = k !== which;
  }
}
$("tab-punto").addEventListener("click", () => showTab("punto"));
$("tab-lista").addEventListener("click", () => { showTab("lista"); refreshJobs(); });
document.querySelector(".tabs").addEventListener("keydown", (e) => {
  if (e.key !== "ArrowLeft" && e.key !== "ArrowRight") return;
  const next = $("tab-punto").getAttribute("aria-selected") === "true" ? "lista" : "punto";
  $(`tab-${next}`).click();
  $(`tab-${next}`).focus();
  e.preventDefault();
});

const SIZES = ["min", "half", "full"];
function setPanel(size) {
  $("panel").dataset.size = size;
  $("handle").setAttribute("aria-expanded", String(size === "full"));
  setTimeout(() => map.invalidateSize(), 300);
}
$("handle").addEventListener("click", () => {
  const i = SIZES.indexOf($("panel").dataset.size);
  setPanel(SIZES[(i + 1) % SIZES.length]);
});
let dragY = null;
$("handle").addEventListener("touchstart", (e) => { dragY = e.touches[0].clientY; }, { passive: true });
$("handle").addEventListener("touchend", (e) => {
  if (dragY === null) return;
  const dy = e.changedTouches[0].clientY - dragY;
  dragY = null;
  if (Math.abs(dy) < 25) return;
  const i = SIZES.indexOf($("panel").dataset.size);
  setPanel(SIZES[Math.max(0, Math.min(2, i + (dy < 0 ? 1 : -1)))]);
  e.preventDefault();
});

// ------------------------------------------------------------------ "Cómo funciona"
const modal = $("modal-metodo");
const MODAL = {
  es: `
    <p>Tempo responde una pregunta: <strong>para esta parcela y esta temporada, ¿cuál de tres opciones de postrera se comporta mejor, y cuán segura es esa respuesta?</strong></p>
    <ol class="how">
      <li><strong>El lugar.</strong> Tomamos la coordenada que tocaste dentro del Corredor Seco.</li>
      <li><strong>Los datos.</strong> Lluvia diaria de 2001 a 2025 por satélite (NASA GPM IMERG, ~10 km); temperatura y radiación (NASA POWER, ~50 km); elevación y pendiente (NASA SRTM, 30 m), que corrigen la temperatura por altura; y suelo de los primeros 30 cm (ISRIC SoilGrids, 250 m), que dice cuánta agua guarda. Si NASA POWER no responde, la temperatura y la lluvia de modelo vienen de Meteomatics como respaldo, y se avisa.</li>
      <li><strong>El agua de cada cultivo.</strong> Con el método FAO-56 se simula, año por año, cuánta agua necesitó cada cultivo y cuánta tuvo.</li>
      <li><strong>Años parecidos.</strong> Se buscan los años con una canícula parecida a la de este año y se promedia cómo le fue a cada opción en ellos: 1 es buena cosecha, 0 es pérdida.</li>
      <li><strong>La prueba de honestidad.</strong> Antes de decir que una opción gana, Tempo revisa si la diferencia es suficiente, si cambia al quitar un supuesto (la regla de 150 mm del frijol) y si cambia al usar otra fuente de lluvia. Si no pasa, dice «ninguna opción es claramente mejor».</li>
    </ol>
    <h3>Lo que Tempo todavía no hace</h3>
    <ul>
      <li>No estima rendimientos ni dinero.</li>
      <li>Los parámetros de cultivo son los de FAO-56; falta validarlos con agrónomos locales.</li>
      <li>La lluvia es la de una celda de satélite de ~10 km, no la de la parcela exacta.</li>
    </ul>
    <h3>Glosario</h3>
    <dl class="glossary">
      <div><dt>Postrera</dt><dd>Segunda siembra del año en Centroamérica, de agosto a noviembre.</dd></div>
      <div><dt>Canícula</dt><dd>Período seco a mitad de la temporada de lluvias, normalmente en julio y agosto.</dd></div>
      <div><dt>Puntaje</dt><dd>Promedio de 0 a 1 de cómo le fue a una opción en los años parecidos.</dd></div>
      <div><dt>Ventaja clara</dt><dd>Diferencia de 0,05 o más entre las dos mejores opciones, y que no cambie con los supuestos ni con la fuente de lluvia.</dd></div>
      <div><dt>Agua útil del suelo</dt><dd>Milímetros de agua que el suelo guarda para la raíz. Sin dato de suelo, Tempo usa un valor por defecto y lo avisa.</dd></div>
      <div><dt>IMERG y POWER</dt><dd>Dos estimaciones de lluvia de NASA. Si no coinciden, la lluvia del punto es incierta.</dd></div>
    </dl>`,
  en: `
    <p>Tempo answers one question: <strong>for this plot and this season, which of three postrera options performs best, and how certain is that answer?</strong></p>
    <ol class="how">
      <li><strong>The place.</strong> We take the coordinate you tapped inside the Dry Corridor.</li>
      <li><strong>The data.</strong> Daily satellite rainfall 2001–2025 (NASA GPM IMERG, ~10 km); temperature and radiation (NASA POWER, ~50 km); elevation and slope (NASA SRTM, 30 m), which correct temperature for altitude; and topsoil to 30 cm (ISRIC SoilGrids, 250 m), which tells how much water it stores. If NASA POWER does not respond, temperature and model rainfall come from Meteomatics as a backup, and the page says so.</li>
      <li><strong>Each crop's water.</strong> The FAO-56 method simulates, year by year, how much water each crop needed and how much it got.</li>
      <li><strong>Similar years.</strong> We find the years with a canícula like this year's and average how each option fared in them: 1 is a good harvest, 0 is a failure.</li>
      <li><strong>The honesty test.</strong> Before saying an option wins, Tempo checks whether the gap is large enough, whether it changes when an assumption is removed (the 150 mm bean rule) and whether it changes with another rainfall source. If it fails, it says «no option is clearly better».</li>
    </ol>
    <h3>What Tempo does not do yet</h3>
    <ul>
      <li>It does not estimate yields or money.</li>
      <li>Crop parameters are FAO-56 defaults; validation with local agronomists is pending.</li>
      <li>Rainfall is a ~10 km satellite cell, not the exact plot.</li>
    </ul>
    <h3>Glossary</h3>
    <dl class="glossary">
      <div><dt>Postrera</dt><dd>Second planting of the year in Central America, August to November.</dd></div>
      <div><dt>Canícula</dt><dd>Midsummer dry spell inside the rainy season, usually July and August.</dd></div>
      <div><dt>Score</dt><dd>Average from 0 to 1 of how an option fared in the similar years.</dd></div>
      <div><dt>Clear advantage</dt><dd>A gap of 0.05 or more between the top two options that holds without the assumptions and with the other rainfall source.</dd></div>
      <div><dt>Soil available water</dt><dd>Millimetres of water the soil holds for roots. Without soil data, Tempo uses a default and says so.</dd></div>
      <div><dt>IMERG and POWER</dt><dd>Two NASA rainfall estimates. When they disagree, rainfall at the point is uncertain.</dd></div>
    </dl>`,
};
function renderModal() { $("modal-body").innerHTML = MODAL[state.lang] || MODAL.es; }
$("btn-metodo").addEventListener("click", () => { renderModal(); modal.showModal(); });
$("modal-close").addEventListener("click", () => modal.close());
modal.addEventListener("click", (e) => { if (e.target === modal) modal.close(); });

// ------------------------------------------------------------------ idioma
$("btn-lang").addEventListener("click", () => {
  state.lang = state.lang === "es" ? "en" : "es";
  try { localStorage.setItem("tempo_lang", state.lang); } catch (_) { /* sin almacenamiento */ }
  applyI18n();
  renderJobs();
  if (state.view === "result" && state.lastResult) renderResult();
  if (!$("compare").hidden) $("btn-compare").click();
});

// ------------------------------------------------------------------ rutas (?job=, ?demo=) y arranque
function route() {
  const p = new URLSearchParams(location.search);
  const demo = p.get("demo"), job = p.get("job");
  if (demo && SHOWCASE_SITES[demo]) { setUrl(SHOWCASE_SITES[demo].id, true); openSite(demo, false); }
  else if (job) {
    api(`/api/jobs/${job}`).then((rec) => {
      if (rec.estado === "listo" || rec.estado === "parcial") return openResult(job, { push: false });
      if (rec.estado === "error") { state.jobId = job; renderError(rec); return; }
      state.jobId = job; renderProgress(rec); startPolling(job);
    }).catch(() => { goHome(false); setUrl(null, true); showToast(t().err_open); });
  } else goHome(false);
}
window.addEventListener("popstate", route);

applyI18n();
loadSitios();
refreshJobs();
route();
