/* Tempo: mapa de parcelas. Clic en el mapa -> marcador -> POST /api/jobs -> consulta de estado
   cada pocos segundos -> panel con el resultado. Todo texto dinámico pasa por esc(). */
"use strict";

const BOUNDS = { latMin: 12, latMax: 15, lonMin: -90.5, lonMax: -87 };
const POLL_MS = 4000;
const NAMES = { A: "Frijol en relevo tras maíz (práctica actual)", B: "Sorgo (maicillo) + frijol", C: "Segunda maíz" };
const ESTADO = { en_cola: "En cola", procesando: "Procesando", listo: "Listo", parcial: "Parcial (faltan fuentes)", error: "Error" };
const CLASE = { short: "corta", normal: "normal", long: "larga" };
const TEXTURA = { clayey: "arcilloso", loamy: "franco", sandy: "arenoso", default: "sin dato (valor por defecto)" };
const VENTANA = { primera: "Primera (may–ago)", canicula: "Canícula (jul–ago)", sep_nov: "Postrera (sep–nov)" };
const COLORS = { listo: "#2f6b3f", parcial: "#c48a1a", error: "#a4281b", en_cola: "#6b7fa8", procesando: "#6b7fa8" };

const $ = (id) => document.getElementById(id);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const num = (x, nd = 1) => (x === null || x === undefined || Number.isNaN(x)) ? "s/d"
  : Number(x).toLocaleString("es-ES", { minimumFractionDigits: nd, maximumFractionDigits: nd });
const inBounds = (lat, lon) => lat >= BOUNDS.latMin && lat <= BOUNDS.latMax && lon >= BOUNDS.lonMin && lon <= BOUNDS.lonMax;

const state = { pick: null, jobId: null, timer: null, jobs: [], layers: {} };

// ------------------------------------------------------------------ mapa
const map = L.map("map", { zoomControl: true, worldCopyJump: false }).setView([13.75, -88.9], 8);
L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
  maxZoom: 19,
  attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">colaboradores de OpenStreetMap</a>',
}).addTo(map);
L.rectangle([[BOUNDS.latMin, BOUNDS.lonMin], [BOUNDS.latMax, BOUNDS.lonMax]], {
  color: "#2f6b3f", weight: 1, dashArray: "4 4", fill: false, interactive: false,
}).addTo(map);
const jobsLayer = L.layerGroup().addTo(map);
let pickMarker = null;

map.on("click", (e) => choosePoint(e.latlng.lat, e.latlng.lng));

function choosePoint(lat, lon, nombre) {
  lat = Math.round(lat * 1e6) / 1e6;
  lon = Math.round(lon * 1e6) / 1e6;
  stopPolling();
  state.pick = { lat, lon };
  state.jobId = null;
  if (pickMarker) pickMarker.setLatLng([lat, lon]);
  else pickMarker = L.marker([lat, lon], { keyboard: false, title: "Punto elegido" }).addTo(map);
  showTab("punto");
  show("pick");
  $("pick-coords").textContent = coord(lat, lon);
  $("pick-name").value = nombre || "";
  const err = $("pick-error");
  if (!inBounds(lat, lon)) {
    err.textContent = "Este punto queda fuera de El Salvador y el Corredor Seco (recuadro del mapa). Tempo no lo analiza.";
    err.hidden = false;
    $("go").disabled = true;
  } else {
    err.hidden = true;
    $("go").disabled = false;
  }
  setPanel("half");
}

function show(which) {
  for (const id of ["intro", "pick", "progress", "result"]) $(id).hidden = id !== which;
}

// ------------------------------------------------------------------ API
async function api(path, opts) {
  const r = await fetch(path, opts);
  let body = null;
  try { body = await r.json(); } catch (_) { /* sin cuerpo JSON */ }
  if (!r.ok && r.status !== 202) {
    const e = new Error((body && body.error) || `HTTP ${r.status}`);
    e.status = r.status; e.body = body;
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
    refreshJobs();
    if (rec.cache) {
      await openResult(rec.id, "Este punto ya estaba analizado: se muestra el resultado guardado, sin recalcular.");
    } else {
      renderProgress(rec);
      startPolling(rec.id);
    }
  } catch (e) {
    $("pick-error").textContent = e.message;
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
        await openResult(id);
        return;
      }
      if (rec.estado === "error") {
        refreshJobs();
        renderError(rec);
        return;
      }
      renderProgress(rec);
    } catch (e) {
      $("prog-msg").textContent = `No se pudo consultar el estado (${e.message}). Se reintenta.`;
    }
    state.timer = setTimeout(tick, POLL_MS);
  };
  state.timer = setTimeout(tick, POLL_MS);
}
function stopPolling() { if (state.timer) clearTimeout(state.timer); state.timer = null; }

function renderProgress(rec) {
  show("progress");
  const pos = rec.estado === "en_cola" && rec.posicion > 1 ? ` · puesto ${rec.posicion} en la cola` : "";
  $("prog-estado").textContent = (ESTADO[rec.estado] || rec.estado) + pos;
  $("prog-msg").textContent = rec.mensaje || "";
  const pct = Math.max(2, Math.round(100 * (rec.progreso || 0)));
  $("meter-fill").style.width = pct + "%";
  $("meter").setAttribute("aria-valuenow", String(pct));
}

function renderError(rec) {
  show("result");
  $("result").innerHTML = `
    <p class="eyebrow">${esc(coordsTxt(rec))}</p>
    <h1>No se pudo analizar este punto</h1>
    <p class="error">${esc(rec.mensaje)}</p>
    ${faltantesHtml(rec.faltantes)}
    <p class="muted">Puede volver a intentarlo: un punto con error se vuelve a encolar.</p>
    <div class="actions"><button type="button" data-retry>Reintentar</button></div>`;
  $("result").querySelector("[data-retry]").addEventListener("click", () => {
    choosePoint(rec.lat, rec.lon, rec.nombre);
    $("go").click();
  });
}

const coord = (lat, lon, nd = 6) => `${Number(lat).toFixed(nd)}, ${Number(lon).toFixed(nd)}`;
const coordsTxt = (r) => (r.nombre ? r.nombre + " · " : "") + coord(r.lat, r.lon);

function faltantesHtml(f) {
  if (!f || !f.length) return "";
  return `<div class="notice"><strong>Faltan fuentes; no se rellenaron con datos inventados:</strong><ul>${f.map((x) => `<li>${esc(x)}</li>`).join("")}</ul></div>`;
}

// ------------------------------------------------------------------ resultado
async function openResult(id, note) {
  stopPolling();
  state.jobId = id;
  const [rec, res] = await Promise.all([api(`/api/jobs/${id}`), api(`/api/jobs/${id}/result`)]);
  state.pick = { lat: rec.lat, lon: rec.lon };
  if (pickMarker) pickMarker.setLatLng([rec.lat, rec.lon]);
  else pickMarker = L.marker([rec.lat, rec.lon], { keyboard: false, title: "Punto elegido" }).addTo(map);
  showTab("punto");
  show("result");
  $("result").innerHTML = resultHtml(rec, res.resumen, note);
  $("result").querySelector("[data-new]").addEventListener("click", () => { show("intro"); });
  $("result").scrollTop = 0;
  $("view-punto").scrollTop = 0;
}

function resultHtml(rec, r, note) {
  const v = r.veredicto, ll = r.lluvia, su = r.suelo, te = r.terreno, s = r.sensibilidad || {};
  const conds = v.condiciones.map((c) =>
    `<li class="${c.cumple ? "ok" : "no"}"><b>${c.cumple ? "Cumple" : "No cumple"}</b> ${esc(c.texto)}</li>`).join("");
  const nOk = v.condiciones.filter((c) => c.cumple).length;
  const best = Math.max(...r.estrategias.filter((e) => e.puntaje !== null).map((e) => e.puntaje));
  const strat = r.estrategias.map((e) => `<tr><td>${esc(e.nombre)}</td><td class="n">${num(e.puntaje, 3)}</td>
      <td class="n">${e.puntaje === null ? "s/d" : num(best - e.puntaje, 3)}</td><td class="n">${e.fallo_pct === null ? "s/d" : e.fallo_pct + " %"}</td></tr>`).join("");
  const win = ll.ventanas_imerg_vs_power || {};
  const winRows = Object.keys(win).map((k) => { const w = win[k]; return `<tr><td>${esc(VENTANA[k] || k)}</td>
      <td class="n">${num(w.mean_imerg_mm, 0)}</td><td class="n">${num(w.mean_power_mm, 0)}</td>
      <td class="n">${w.bias_pct === null ? "s/d" : num(w.bias_pct, 0) + " %"}</td><td class="n">${w.n_years ?? "s/d"}</td></tr>`; }).join("");
  const rainTable = ll.imerg_disponible && winRows ? `<div class="table-wrap"><table>
      <caption class="sr-only">Lluvia media por ventana, IMERG y NASA POWER</caption>
      <thead><tr><th>Ventana</th><th class="n">IMERG mm</th><th class="n">POWER mm</th><th class="n">POWER − IMERG</th><th class="n">Años</th></tr></thead>
      <tbody>${winRows}</tbody></table></div>`
    : `<p class="notice">Sin IMERG para este punto: la lluvia es 100 % NASA POWER y no se puede comparar con otra fuente.</p>`;
  const sensRow = (k, label) => s[k] ? `<tr><td>${esc(label)}</td><td class="n">${s[k].n_pick_changes} de ${s[k].n_years_compared}</td><td class="n">${num(s[k].mean_margin_vs_current, 2)}</td></tr>` : "";
  const cambiosPower = ll.cambios_con_power === null || ll.cambios_con_power === undefined
    ? `<tr><td>Con NASA POWER en lugar de IMERG</td><td class="n">no evaluable</td><td class="n">s/d</td></tr>`
    : `<tr><td>Con NASA POWER en lugar de IMERG</td><td class="n">${ll.cambios_con_power} de ${ll.anios_comparados}</td><td class="n">s/d</td></tr>`;
  const val = r.validacion || {};
  return `
  <p class="eyebrow">${esc(coordsTxt(rec))} · temporada ${esc(r.anio)}</p>
  ${note ? `<p class="badge ok">${esc(note)}</p>` : ""}
  ${rec.estado === "parcial" ? `<p class="badge">Resultado parcial</p>` : ""}
  <div class="verdict${v.claro ? " clear" : ""}">
    <h1>${esc(v.titulo)}</h1>
    <p>${esc(v.texto)}</p>
  </div>
  ${faltantesHtml(rec.faltantes)}

  <h2>Por qué se lee así</h2>
  <p class="muted">Tempo solo nombra una opción mejor cuando se cumplen las cuatro condiciones. Aquí se cumplen ${nOk} de 4.</p>
  <ul class="conds">${conds}</ul>
  ${(v.razones_lectura || []).length ? `<p class="muted">${v.razones_lectura.map(esc).join(" ")}</p>` : ""}

  <h2>Las tres opciones</h2>
  <div class="table-wrap"><table>
    <caption class="sr-only">Puntaje de cada estrategia</caption>
    <thead><tr><th>Estrategia</th><th class="n">Puntaje</th><th class="n">Dif. con el más alto</th><th class="n">Años con fallo</th></tr></thead>
    <tbody>${strat}</tbody></table></div>
  <p class="muted">Puntaje de 0 a 1: 60 % del clima en ${esc(r.estrategias[0]?.anios_parecidos ?? "s/d")} años con una canícula parecida y 40 % de prioridades del hogar. No es un rendimiento. Diferencias menores a 0,05 no distinguen opciones.</p>

  <h2>Lluvia</h2>
  <dl class="facts">
    <dt>Fuente usada</dt><dd>${ll.imerg_disponible ? `IMERG (satélite NASA) en ${num(ll.dias_imerg_pct, 0)} % de los días; el resto NASA POWER` : "NASA POWER (100 %)"}</dd>
    <dt>Canícula ${esc(r.anio)}</dt><dd>${esc(ll.canicula_dias ?? "s/d")} días (${esc(CLASE[ll.canicula_clase] || ll.canicula_clase || "s/d")})</dd>
    <dt>Inicio de postrera</dt><dd>${esc(ll.inicio_postrera || "s/d")}</dd>
    <dt>Sep–nov, mediana ${ll.anios ? esc(ll.anios.join("–")) : ""}</dt><dd>${num(ll.sep_nov_mediana_mm, 0)} mm</dd>
    <dt>Jul–ago ${esc(r.anio)}</dt><dd>${num(ll.jul_ago_actual_mm, 0)} mm (mediana ${num(ll.jul_ago_mediana_mm, 0)})</dd>
  </dl>
  <h3>IMERG y NASA POWER en este punto</h3>
  ${rainTable}

  <h2>Suelo y terreno</h2>
  <dl class="facts">
    <dt>Textura (0–30 cm)</dt><dd>${esc(TEXTURA[su.textura] || su.textura || "sin dato")}${su.arcilla_pct !== null && su.arcilla_pct !== undefined ? ` · arcilla ${num(su.arcilla_pct, 0)} %, arena ${num(su.arena_pct, 0)} %` : ""}</dd>
    <dt>Agua disponible usada</dt><dd>${esc(su.whc_mm ?? "s/d")} mm${su.textura ? "" : " (valor por defecto del modelo)"}</dd>
    <dt>Elevación</dt><dd>${te.elevation_m === null || te.elevation_m === undefined ? "sin dato (sin SRTM)" : num(te.elevation_m, 0) + " m (SRTM)"}</dd>
    <dt>Pendiente</dt><dd>${te.slope_pct === null || te.slope_pct === undefined ? "sin dato" : num(te.slope_pct, 1) + " %"}</dd>
    <dt>Ajuste de temperatura</dt><dd>${te.correccion_temp_c === null || te.correccion_temp_c === undefined ? "sin ajuste por elevación" : num(te.correccion_temp_c, 2) + " °C"}</dd>
  </dl>

  <h2>Sensibilidad: ¿cambia la elección?</h2>
  <div class="table-wrap"><table>
    <caption class="sr-only">Años en que cambia la estrategia elegida al cambiar un supuesto</caption>
    <thead><tr><th>Variante</th><th class="n">Años que cambian</th><th class="n">Ventaja sobre práctica actual</th></tr></thead>
    <tbody>${sensRow("no_bean_excess_rule", "Sin la regla de 150 mm del frijol")}${cambiosPower}
      ${sensRow("whc_60", "Capacidad de agua 60 mm")}${sensRow("whc_90", "Capacidad de agua 90 mm")}${sensRow("whc_130", "Capacidad de agua 130 mm")}</tbody></table></div>
  <p class="muted">Validación ${esc(val.anios ?? "s/d")} años (cada año sin usarlo): Tempo ${num(val.tempo, 2)}, práctica actual ${num(val.practica_actual, 2)}, elegir siempre lo mismo ${num(val.misma_siempre, 2)}.</p>

  <h2>Límites</h2>
  <ul class="limits">
    <li>Tempo apoya la decisión y no reemplaza el criterio agronómico local.</li>
    <li>La lluvia satelital IMERG representa una celda de unos 10 km; NASA POWER, unos 50 km. No es la lluvia exacta de su parcela.</li>
    <li>El suelo de SoilGrids es una estimación a 250 m, no un análisis de laboratorio.</li>
    <li>Los umbrales del modelo (como la regla de 150 mm del frijol y el margen de 0,05) son supuestos sin validar en campo.</li>
    <li>El puntaje compara opciones; no predice cosecha ni rendimiento.</li>
    <li>El resultado se calculó con datos hasta el día anterior a la descarga; no se actualiza solo.</li>
  </ul>
  <div class="actions"><button type="button" data-new>Elegir otro punto</button>
    <a href="/api/jobs/${esc(rec.id)}/result" target="_blank" rel="noopener">Ver JSON completo</a></div>`;
}

// ------------------------------------------------------------------ análisis hechos
async function refreshJobs() {
  try {
    const { jobs } = await api("/api/jobs");
    state.jobs = jobs;
  } catch (_) { return; }
  jobsLayer.clearLayers();
  const ul = $("jobs");
  ul.innerHTML = "";
  $("n-jobs").textContent = state.jobs.length ? `(${state.jobs.length})` : "";
  if (!state.jobs.length) {
    ul.innerHTML = `<li class="muted">Todavía no hay análisis. Toque el mapa para empezar.</li>`;
  }
  for (const j of [...state.jobs].reverse()) {
    const color = COLORS[j.estado] || "#666";
    const m = L.circleMarker([j.lat, j.lon], { radius: 8, color: "#fff", weight: 2, fillColor: color, fillOpacity: .95 })
      .bindTooltip(`${esc(j.nombre || "Punto")} · ${esc(ESTADO[j.estado] || j.estado)}`)
      .on("click", (ev) => { L.DomEvent.stopPropagation(ev); openJob(j); });
    jobsLayer.addLayer(m);
    const li = document.createElement("li");
    const vt = j.veredicto ? j.veredicto.titulo : (j.mensaje || "");
    li.innerHTML = `<button type="button"><span class="t"><span class="dot st-${esc(j.estado)}"></span>${esc(j.nombre || "Punto sin nombre")}</span>
      <span class="s">${coord(j.lat, j.lon, 4)} · ${esc(ESTADO[j.estado] || j.estado)}</span>
      <span class="s">${esc(vt)}</span></button>`;
    li.querySelector("button").addEventListener("click", () => openJob(j));
    ul.appendChild(li);
  }
}

function openJob(j) {
  map.setView([j.lat, j.lon], Math.max(map.getZoom(), 11));
  if (j.estado === "listo" || j.estado === "parcial") openResult(j.id).catch((e) => alert(e.message));
  else if (j.estado === "error") { state.jobId = j.id; showTab("punto"); renderError(j); }
  else { state.jobId = j.id; showTab("punto"); renderProgress(j); startPolling(j.id); }
  setPanel("half");
}

// ------------------------------------------------------------------ buscador (parcelas.json)
let sitios = [];
async function loadSitios() {
  try { sitios = (await api("/api/sitios")).sitios || []; } catch (_) { sitios = []; }
  const dl = $("sitios");
  dl.innerHTML = sitios.map((s) => `<option value="${esc(siteLabel(s))}"></option>`).join("");
}
const siteLabel = (s) => [s.nombre, s.municipio, s.departamento, s.pais].filter(Boolean).filter((x, i, a) => a.indexOf(x) === i).join(", ");
const norm = (s) => String(s).normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();

$("search").addEventListener("submit", (e) => {
  e.preventDefault();
  const q = norm($("q").value.trim());
  if (!q) return;
  const s = sitios.find((x) => norm(siteLabel(x)) === q) || sitios.find((x) => norm(siteLabel(x)).includes(q));
  if (!s) { $("q").setCustomValidity("No está en parcelas.json"); $("q").reportValidity(); setTimeout(() => $("q").setCustomValidity(""), 2000); return; }
  map.setView([s.lat, s.lon], 12);
  choosePoint(s.lat, s.lon, s.nombre);
});

// ------------------------------------------------------------------ panel y pestañas
function showTab(which) {
  for (const t of ["punto", "lista"]) {
    $(`tab-${t}`).setAttribute("aria-selected", String(t === which));
    $(`view-${t}`).hidden = t !== which;
  }
}
$("tab-punto").addEventListener("click", () => showTab("punto"));
$("tab-lista").addEventListener("click", () => { showTab("lista"); refreshJobs(); });

const SIZES = ["min", "half", "full"];
function setPanel(size) {
  $("panel").dataset.size = size;
  $("handle").setAttribute("aria-expanded", String(size === "full"));
  setTimeout(() => map.invalidateSize(), 300);
}
$("handle").addEventListener("click", () => {
  const cur = SIZES.indexOf($("panel").dataset.size);
  setPanel(SIZES[(cur + 1) % SIZES.length]);
});
// Deslizar el asa hacia arriba o abajo cambia el tamaño del panel.
let dragY = null;
$("handle").addEventListener("touchstart", (e) => { dragY = e.touches[0].clientY; }, { passive: true });
$("handle").addEventListener("touchend", (e) => {
  if (dragY === null) return;
  const dy = e.changedTouches[0].clientY - dragY;
  dragY = null;
  if (Math.abs(dy) < 25) return;
  const cur = SIZES.indexOf($("panel").dataset.size);
  setPanel(SIZES[Math.max(0, Math.min(2, cur + (dy < 0 ? 1 : -1)))]);
  e.preventDefault();
});

loadSitios();
refreshJobs();
