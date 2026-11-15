/* Tempo · parcelas. Reads data.json (build_parcels.py) and out/<id>.json. No build step. */
(function () {
  "use strict";

  var NAMES = {
    A: "Frijol en relevo tras maíz (práctica actual)",
    B: "Sorgo (maicillo) + frijol",
    C: "Segunda maíz"
  };
  var LIGHT = { green: "Sin alerta de estrés", yellow: "Riesgo moderado", red: "Riesgo alto" };
  var CANICULA = { short: "corta", normal: "normal", long: "larga" };
  var TEXTURE = { clayey: "arcillosa", loamy: "franca", sandy: "arenosa", "default": "sin dato (valor por defecto)" };
  var ESTADO = { completo: "Completo", parcial: "Parcial", pendiente: "Pendiente" };

  var state = { all: [], byId: {}, selected: null, compare: [], map: null, markers: {}, probe: null, outCache: {} };

  // ------------------------------------------------------------ helpers
  function $(id) { return document.getElementById(id); }
  function esc(x) {
    return String(x == null ? "" : x).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }
  function fmt(x, nd) {
    if (x == null || isNaN(x)) return "—";
    return Number(x).toFixed(nd == null ? 0 : nd).replace(".", ",").replace("-", "−");
  }
  function norm(s) {
    return String(s || "").normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();
  }
  function depto(s) { return s.departamento || "Sin verificar"; }
  function place(s) {
    return [s.municipio, s.departamento, s.pais].filter(Boolean).join(", ") || s.pais || "Ubicación sin verificar";
  }
  function km(a, b) { // haversine, km
    var R = 6371, r = Math.PI / 180;
    var dLat = (b.lat - a.lat) * r, dLon = (b.lon - a.lon) * r;
    var h = Math.sin(dLat / 2) * Math.sin(dLat / 2) +
      Math.cos(a.lat * r) * Math.cos(b.lat * r) * Math.sin(dLon / 2) * Math.sin(dLon / 2);
    return 2 * R * Math.asin(Math.sqrt(h));
  }

  // "13.7, -88.1" | "13.7 -88.1" | 13°47'47.06"N 89°48'03.71"W (also O = oeste)
  function parseCoords(q) {
    var s = q.trim();
    var dec = q.trim().match(/^\s*(-?\d{1,2}(?:\.\d+)?)\s*[,; ]\s*(-?\d{1,3}(?:\.\d+)?)\s*$/);
    if (dec) return check(parseFloat(dec[1]), parseFloat(dec[2]));
    var re = /(\d{1,3})\s*°\s*(?:(\d{1,2}(?:[.,]\d+)?)\s*['′])?\s*(?:(\d{1,2}(?:[.,]\d+)?)\s*(?:"|″|''))?\s*([NSEWO])/gi;
    var parts = [], m;
    while ((m = re.exec(s)) !== null) {
      var v = parseFloat(m[1]) + (m[2] ? parseFloat(m[2].replace(",", ".")) / 60 : 0) +
        (m[3] ? parseFloat(m[3].replace(",", ".")) / 3600 : 0);
      var h = m[4].toUpperCase();
      parts.push({ v: (h === "S" || h === "W" || h === "O") ? -v : v, axis: (h === "N" || h === "S") ? "lat" : "lon" });
    }
    if (parts.length === 2 && parts[0].axis !== parts[1].axis) {
      var lat = parts[0].axis === "lat" ? parts[0].v : parts[1].v;
      var lon = parts[0].axis === "lon" ? parts[0].v : parts[1].v;
      return check(lat, lon);
    }
    return null;
    function check(lat, lon) {
      return (Math.abs(lat) <= 90 && Math.abs(lon) <= 180) ? { lat: lat, lon: lon } : null;
    }
  }

  function notice(msg) {
    var n = $("aviso");
    if (!msg) { n.hidden = true; n.textContent = ""; return; }
    n.hidden = false; n.innerHTML = msg;
  }

  // ------------------------------------------------------------ data
  function load() {
    fetch("data.json", { cache: "no-store" })
      .then(function (r) { if (!r.ok) throw new Error("HTTP " + r.status); return r.json(); })
      .then(init)
      .catch(function (e) {
        $("lista-vacia").hidden = false;
        $("lista-vacia").innerHTML = "No se pudo leer <code>data.json</code> (" + esc(e.message) + "). " +
          "Genera el índice con <code>python build_parcels.py</code> y sirve el repositorio por HTTP: " +
          "<code>python -m http.server 8000</code>, luego abre <code>http://localhost:8000/web/parcelas/</code>.";
        $("cuenta").textContent = "(0)";
        initMap();
      });
  }

  function init(data) {
    var ready = (data.parcelas || []).map(function (p) { p._estado = p.datos; return p; });
    var pend = (data.pendientes || []).map(function (p) { p._estado = "pendiente"; return p; });
    state.all = ready.concat(pend);
    state.all.forEach(function (s) { state.byId[s.id] = s; });

    var deps = {};
    state.all.forEach(function (s) { deps[depto(s)] = (s.pais || ""); });
    var sel = $("f-depto");
    Object.keys(deps).sort(function (a, b) { return a.localeCompare(b, "es"); }).forEach(function (d) {
      var o = document.createElement("option");
      o.value = d; o.textContent = d + (deps[d] ? " (" + deps[d] + ")" : "");
      sel.appendChild(o);
    });

    initMap();
    renderList();
    readHash();
  }

  function filtered() {
    var d = $("f-depto").value, e = $("f-estado").value, q = $("q").value;
    var text = parseCoords(q) ? "" : norm(q.trim());
    return state.all.filter(function (s) {
      if (d && depto(s) !== d) return false;
      if (e && s._estado !== e) return false;
      if (text) {
        var hay = norm([s.id, s.nombre, s.municipio, s.departamento, s.pais].join(" "));
        if (hay.indexOf(text) < 0) return false;
      }
      return true;
    });
  }

  // ------------------------------------------------------------ list
  function renderList() {
    var list = filtered(), ul = $("sitios");
    ul.innerHTML = "";
    $("cuenta").textContent = "(" + list.length + " de " + state.all.length + ")";
    var empty = $("lista-vacia");
    if (!state.all.length) {
      empty.hidden = false;
      empty.textContent = "No hay sitios en parcelas.json. Agrega uno y corre build_parcels.py --run.";
    } else if (!list.length) {
      empty.hidden = false;
      empty.textContent = "Ningún sitio coincide con la búsqueda o los filtros. Prueba con otro nombre, quita filtros o escribe coordenadas.";
    } else {
      empty.hidden = true;
    }
    list.forEach(function (s) {
      var li = document.createElement("li");
      li.className = "site" + (state.selected === s.id ? " is-selected" : "");
      var v = s.veredicto;
      var tag = v ? (v.lectura_temporada ? '<span class="tag tag--season">Lectura de temporada</span>'
        : '<span class="tag tag--lead">' + esc(v.titulo) + "</span>") : "";
      var inCmp = state.compare.indexOf(s.id) >= 0;
      li.innerHTML =
        '<button type="button" class="site-main" data-id="' + esc(s.id) + '"' +
        (state.selected === s.id ? ' aria-current="true"' : "") + ">" +
        '<span class="site-name">' + esc(s.nombre) + "</span>" +
        '<span class="site-place">' + esc(place(s)) + "</span>" +
        '<span class="site-tags"><span class="tag tag--' + esc(s._estado) + '">' + esc(ESTADO[s._estado]) + "</span>" +
        (s.coordenada_supuesta ? '<span class="tag tag--warn">Coordenada SUPUESTO</span>' : "") + tag + "</span>" +
        "</button>" +
        (s._estado === "pendiente" ? "" :
          '<button type="button" class="cmp" data-cmp="' + esc(s.id) + '" aria-pressed="' + inCmp + '">' +
          (inCmp ? "Quitar" : "Comparar") + '<span class="sr"> ' + esc(s.nombre) + "</span></button>");
      ul.appendChild(li);
    });
    syncMarkers(list);
  }

  // ------------------------------------------------------------ map
  function initMap() {
    if (state.map) return;
    if (typeof L === "undefined") { $("mapa").hidden = true; $("mapa-vacio").hidden = false; return; }
    var map = L.map("mapa", { scrollWheelZoom: false }).setView([13.6, -88.2], 7);
    var tiles = L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 18, attribution: '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
    }).addTo(map);
    var failed = 0;
    tiles.on("tileerror", function () {
      failed += 1;
      if (failed === 4) notice("Algunos mosaicos del mapa no cargaron. Los puntos y la lista siguen disponibles.");
    });
    map.on("click", function (e) { nearestTo({ lat: e.latlng.lat, lon: e.latlng.lng }, "al punto del mapa"); });
    state.map = map;
  }

  function syncMarkers(list) {
    if (!state.map) return;
    var show = {};
    list.forEach(function (s) { show[s.id] = true; });
    state.all.forEach(function (s) {
      var m = state.markers[s.id];
      if (!m) {
        m = L.circleMarker([s.lat, s.lon], { radius: 8, weight: 2 });
        m.bindTooltip(s.nombre);
        m.on("click", function (ev) { L.DomEvent.stopPropagation(ev); select(s.id, true); });
        state.markers[s.id] = m;
      }
      var sel = state.selected === s.id;
      m.setStyle({
        color: sel ? "#0b3d91" : "#1d1d1b",
        fillColor: s._estado === "pendiente" ? "#ffffff" : (sel ? "#0b3d91" : "#1f6b3f"),
        fillOpacity: 0.9, radius: sel ? 11 : 8
      });
      if (show[s.id] && !state.map.hasLayer(m)) m.addTo(state.map);
      if (!show[s.id] && state.map.hasLayer(m)) state.map.removeLayer(m);
    });
  }

  // ------------------------------------------------------------ nearest
  function nearestTo(pt, label) {
    var cands = state.all.filter(function (s) { return s._estado !== "pendiente"; });
    if (!cands.length) { notice("No hay sitios con datos para buscar el más cercano."); return; }
    var ranked = cands.map(function (s) { return { s: s, d: km(pt, s) }; })
      .sort(function (a, b) { return a.d - b.d; });
    var best = ranked[0];
    var closerPending = state.all.filter(function (s) { return s._estado === "pendiente" && km(pt, s) < best.d; });
    var msg = "Sitio con datos más cercano " + esc(label) + " (" + fmt(pt.lat, 4) + ", " + fmt(pt.lon, 4) + "): <strong>" +
      esc(best.s.nombre) + "</strong>, a " + fmt(best.d, best.d < 10 ? 1 : 0) + " km.";
    if (ranked[1]) msg += " Siguiente: " + esc(ranked[1].s.nombre) + " (" + fmt(ranked[1].d, 0) + " km).";
    if (best.d > 25) msg += " Está lejos: sus datos no representan ese punto.";
    if (closerPending.length) msg += " Hay un sitio pendiente más cerca (" + esc(closerPending[0].nombre) + "), sin resultado todavía.";
    notice(msg);
    if (state.map) {
      if (state.probe) state.map.removeLayer(state.probe);
      state.probe = L.layerGroup([
        L.circleMarker([pt.lat, pt.lon], { radius: 6, color: "#8a1c1c", fillColor: "#8a1c1c", fillOpacity: 1 }),
        L.polyline([[pt.lat, pt.lon], [best.s.lat, best.s.lon]], { color: "#8a1c1c", dashArray: "4 6", weight: 2 })
      ]).addTo(state.map);
    }
    select(best.s.id, false);
  }

  // ------------------------------------------------------------ detail
  function select(id, focus) {
    var s = state.byId[id];
    if (!s) return;
    state.selected = id;
    writeHash();
    renderList();
    if (state.map) state.map.panTo([s.lat, s.lon]);
    var body = $("detalle-body");
    if (s._estado === "pendiente") {
      body.innerHTML = head(s) +
        '<p class="empty">Sin resultado todavía: ' + esc(s.motivo) + ". Corre <code>python build_parcels.py --run --ids " +
        esc(s.id) + "</code>.</p>" + coordSource(s);
      if (focus) $("detalle").focus();
      return;
    }
    body.innerHTML = head(s) + verdict(s) + '<p class="loading">Cargando out/' + esc(s.id) + ".json…</p>";
    getOut(s).then(function (d) {
      if (state.selected !== id) return;
      body.innerHTML = head(s) + verdict(s) + rain(s, d) + soil(s) + gaps(s) + links(s) + coordSource(s);
    }).catch(function (e) {
      if (state.selected !== id) return;
      body.innerHTML = head(s) + verdict(s) +
        '<p class="empty">No se pudo cargar <code>out/' + esc(s.id) + ".json</code> (" + esc(e.message) +
        "). El resumen de arriba viene de data.json; sirve el repositorio desde su raíz para ver el detalle.</p>" +
        soil(s) + gaps(s) + links(s) + coordSource(s);
    });
    if (focus) $("detalle").focus();
  }

  function getOut(s) {
    if (state.outCache[s.id]) return Promise.resolve(state.outCache[s.id]);
    return fetch(s.out, { cache: "no-store" }).then(function (r) {
      if (!r.ok) throw new Error("HTTP " + r.status);
      return r.json();
    }).then(function (d) { state.outCache[s.id] = d; return d; });
  }

  function head(s) {
    return '<div class="d-head"><h3>' + esc(s.nombre) + "</h3><p>" + esc(place(s)) + " · " +
      fmt(s.lat, 5) + ", " + fmt(s.lon, 5) + (s.anio ? " · temporada " + esc(s.anio) : "") + "</p></div>";
  }

  function verdict(s) {
    var v = s.veredicto;
    if (!v) return "";
    var html = '<div class="verdict' + (v.lectura_temporada ? " verdict--season" : "") + '">';
    if (v.lectura_temporada) html += '<p class="eyebrow">Lectura de temporada</p>';
    html += "<p class=\"v-title\">" + esc(v.titulo) + "</p>";
    if (v.razones && v.razones.length) html += "<ul>" + v.razones.map(function (r) { return "<li>" + esc(r) + "</li>"; }).join("") + "</ul>";
    if (s.faltantes && s.faltantes.length) html += '<p class="v-warn">Datos parciales: faltan ' + s.faltantes.length + " fuentes (ver abajo). Lee el veredicto con más cautela.</p>";
    html += "</div>";
    html += '<table class="scores"><caption>Puntaje por estrategia (1 = buena cosecha, 0 = fallo)</caption><tbody>';
    ["A", "B", "C"].forEach(function (k) {
      var sc = v.puntajes ? v.puntajes[k] : null;
      html += "<tr" + (k === v.mejor ? ' class="best"' : "") + '><th scope="row">' + k + " · " + esc(NAMES[k]) + "</th><td>" +
        fmt(sc, 2) + (k === v.mejor ? ' <span class="sr">(mayor puntaje)</span>' : "") + "</td></tr>";
    });
    html += "</tbody></table>";
    var val = s.validacion || {};
    html += '<p class="small">Semáforo de maíz: ' + esc(LIGHT[s.semaforo] || "sin dato") +
      ". Validación " + (val.anios ? val.anios + " años" : "sin años") + ": Tempo " + fmt(val.tempo, 2) +
      ", misma estrategia siempre " + fmt(val.misma_siempre, 2) + ", práctica actual " + fmt(val.practica_actual, 2) + "." +
      (s.check1_discriminante === false ? " CHECK 1 no discrimina años secos en este punto." : "") + "</p>";
    return html;
  }

  function rain(s, d) {
    var l = s.lluvia || {};
    var src = l.imerg_disponible ? fmt(l.dias_imerg_pct) + " % de los días desde IMERG" +
      (l.dias_imerg_pct < 100 ? "; el resto, NASA POWER." : ".")
      : "100 % NASA POWER (IMERG no descargada).";
    var years = (d.yearly || []).filter(function (y) { return y.year < d.current_year && y.rain_sep_nov_mm != null; });
    var chart = years.length ? sparkBars(years) : '<p class="empty">Sin años completos de lluvia Sep–Nov.</p>';
    return '<section class="block"><h4>Lluvia</h4><p class="small">' + src + "</p>" +
      '<dl class="kv">' +
      "<dt>Sep–Nov, mediana " + (l.anios ? l.anios[0] + "–" + l.anios[1] : "") + "</dt><dd>" + fmt(l.sep_nov_mediana_mm) + " mm</dd>" +
      "<dt>Sep–Nov " + esc(s.anio) + "</dt><dd>" + (l.sep_nov_actual_mm == null ? "temporada en curso o sin dato" : fmt(l.sep_nov_actual_mm) + " mm") + "</dd>" +
      "<dt>Jul–Ago " + esc(s.anio) + " (mediana)</dt><dd>" + fmt(l.jul_ago_actual_mm) + " mm (" + fmt(l.jul_ago_mediana_mm) + ")</dd>" +
      "<dt>Canícula " + esc(s.anio) + "</dt><dd>" + (l.canicula_dias == null ? "—" : l.canicula_dias + " días, " + esc(CANICULA[l.canicula_clase] || l.canicula_clase || "")) + "</dd>" +
      "<dt>Inicio de postrera</dt><dd>" + esc(l.inicio_postrera || "—") + "</dd>" +
      (l.cambios_por_fuente != null ? "<dt>Cambios IMERG vs POWER</dt><dd>" + l.cambios_por_fuente + " de " + l.anios_comparados + " años</dd>" : "") +
      "</dl>" + chart + "</section>";
  }

  function sparkBars(years) {
    var max = Math.max.apply(null, years.map(function (y) { return y.rain_sep_nov_mm; })) || 1;
    var w = 300, h = 80, bw = w / years.length;
    var bars = years.map(function (y, i) {
      var bh = Math.max(1, (y.rain_sep_nov_mm / max) * (h - 14));
      return '<rect x="' + (i * bw + 1).toFixed(1) + '" y="' + (h - bh).toFixed(1) + '" width="' + Math.max(1, bw - 2).toFixed(1) +
        '" height="' + bh.toFixed(1) + '"><title>' + y.year + ": " + fmt(y.rain_sep_nov_mm) + " mm</title></rect>";
    }).join("");
    var first = years[0].year, last = years[years.length - 1].year;
    return '<figure class="spark"><svg viewBox="0 0 ' + w + " " + h + '" role="img" aria-label="Lluvia Sep–Nov por año, ' +
      first + " a " + last + ", máximo " + fmt(max) + ' mm">' + bars + "</svg>" +
      "<figcaption>Lluvia Sep–Nov por año, " + first + "–" + last + " (máx. " + fmt(max) + " mm)</figcaption></figure>";
  }

  function soil(s) {
    var so = s.suelo || {}, t = s.terreno || {};
    var has = so.textura != null;
    return '<section class="block"><h4>Suelo y terreno</h4><dl class="kv">' +
      "<dt>Textura (SoilGrids 0–30 cm)</dt><dd>" + (has ? esc(TEXTURE[so.textura] || so.textura) : "sin dato" + (so.error ? " (error de la fuente)" : "")) + "</dd>" +
      (has ? "<dt>Arcilla · arena · limo</dt><dd>" + fmt(so.arcilla_pct, 1) + " · " + fmt(so.arena_pct, 1) + " · " + fmt(so.limo_pct, 1) + " %</dd>" +
        "<dt>Carbono orgánico</dt><dd>" + fmt(so.carbono_g_kg, 1) + " g/kg</dd>" : "") +
      "<dt>Agua disponible usada</dt><dd>" + fmt(so.whc_mm) + " mm (" + esc(TEXTURE[so.clase_usada] || so.clase_usada) + "; valor de tabla, SUPUESTO)</dd>" +
      "<dt>Elevación (SRTM)</dt><dd>" + (t.elevation_m == null ? "sin dato" : fmt(t.elevation_m) + " m") + "</dd>" +
      "<dt>Pendiente (SRTM)</dt><dd>" + (t.slope_pct == null ? "sin dato" : fmt(t.slope_pct, 1) + " %") + "</dd>" +
      "</dl></section>";
  }

  function gaps(s) {
    var f = s.faltantes || [], w = s.advertencias || [];
    if (!f.length && !w.length) return '<section class="block"><h4>Datos faltantes</h4><p class="small">Ninguno: POWER, IMERG, SRTM y SoilGrids presentes.</p></section>';
    return '<section class="block"><h4>Datos faltantes y advertencias</h4><ul class="small">' +
      f.map(function (x) { return "<li>" + esc(x) + "</li>"; }).join("") +
      w.map(function (x) { return "<li>Advertencia: " + esc(x) + "</li>"; }).join("") + "</ul></section>";
  }

  function links(s) {
    return '<p class="links">' +
      (s.detalle ? '<a href="' + esc(s.detalle) + '">Ver detalle completo (veredicto, hindcast, método)</a>'
        : '<span class="small">Sitio de detalle multipágina: solo existe para la parcela del usuario.</span>') +
      ' <a href="' + esc(s.out) + '">Datos crudos (out/' + esc(s.id) + ".json)</a></p>";
  }

  function coordSource(s) {
    return '<details class="src"><summary>Fuente de la coordenada' + (s.coordenada_supuesta ? " (SUPUESTO)" : "") + "</summary><p>" +
      esc(s.fuente_coordenadas) + "</p>" + (s.fuente_admin ? "<p>" + esc(s.fuente_admin) + "</p>" : "") + "</details>";
  }

  // ------------------------------------------------------------ compare
  function toggleCompare(id) {
    var i = state.compare.indexOf(id);
    if (i >= 0) state.compare.splice(i, 1);
    else {
      if (state.compare.length >= 2) state.compare.shift();
      state.compare.push(id);
    }
    writeHash();
    renderList();
    renderCompare();
  }

  function renderCompare() {
    var body = $("comparar-body");
    var sites = state.compare.map(function (id) { return state.byId[id]; }).filter(Boolean);
    if (sites.length < 2) {
      body.innerHTML = '<p class="empty">' + (sites.length === 1
        ? "Elegiste «" + esc(sites[0].nombre) + "». Marca «Comparar» en un segundo sitio."
        : "Marca «Comparar» en dos sitios de la lista para verlos lado a lado.") + "</p>";
      return;
    }
    var a = sites[0], b = sites[1];
    var rows = [
      ["Lugar", function (s) { return esc(place(s)); }],
      ["Distancia entre ambos", function () { return fmt(km(a, b), 0) + " km"; }],
      ["Veredicto", function (s) {
        return (s.veredicto.lectura_temporada ? '<span class="tag tag--season">Lectura de temporada</span><br>' : "") + esc(s.veredicto.titulo) +
          (s.faltantes.length ? '<br><span class="small">Datos parciales: más cautela.</span>' : "");
      }],
      ["Mayor puntaje", function (s) { return esc(s.veredicto.mejor) + " · " + esc(NAMES[s.veredicto.mejor] || "") + " (margen " + fmt(s.veredicto.margen, 3) + ")"; }],
      ["Puntajes A · B · C", function (s) { var p = s.veredicto.puntajes || {}; return fmt(p.A, 2) + " · " + fmt(p.B, 2) + " · " + fmt(p.C, 2); }],
      ["Semáforo de maíz", function (s) { return esc(LIGHT[s.semaforo] || "sin dato"); }],
      ["Validación: Tempo / misma siempre", function (s) { return fmt(s.validacion.tempo, 2) + " / " + fmt(s.validacion.misma_siempre, 2); }],
      ["Lluvia Sep–Nov (mediana)", function (s) { return fmt(s.lluvia.sep_nov_mediana_mm) + " mm"; }],
      ["Canícula " + (a.anio || ""), function (s) { return s.lluvia.canicula_dias == null ? "—" : s.lluvia.canicula_dias + " días"; }],
      ["Fuente de lluvia", function (s) { return s.lluvia.imerg_disponible ? fmt(s.lluvia.dias_imerg_pct) + " % IMERG" : "100 % POWER"; }],
      ["Suelo", function (s) { return s.suelo.textura ? esc(TEXTURE[s.suelo.textura]) + ", " + fmt(s.suelo.whc_mm) + " mm" : "sin dato (" + fmt(s.suelo.whc_mm) + " mm por defecto)"; }],
      ["Elevación · pendiente", function (s) { return (s.terreno.elevation_m == null ? "sin dato" : fmt(s.terreno.elevation_m) + " m") + " · " + (s.terreno.slope_pct == null ? "sin dato" : fmt(s.terreno.slope_pct, 1) + " %"); }],
      ["Datos", function (s) { return esc(ESTADO[s._estado]) + (s.faltantes.length ? " (faltan " + s.faltantes.length + ")" : ""); }],
      ["Coordenada", function (s) { return s.coordenada_supuesta ? "SUPUESTO" : "con fuente"; }]
    ];
    var html = '<div class="cmp-wrap"><table class="cmp-table"><thead><tr><th scope="col"><span class="sr">Dato</span></th>' +
      '<th scope="col">' + esc(a.nombre) + '</th><th scope="col">' + esc(b.nombre) + "</th></tr></thead><tbody>";
    rows.forEach(function (r) {
      if (r[0] === "Distancia entre ambos") {
        html += '<tr><th scope="row">' + r[0] + '</th><td colspan="2">' + r[1]() + "</td></tr>";
      } else {
        html += '<tr><th scope="row">' + esc(r[0]) + "</th><td>" + r[1](a) + "</td><td>" + r[1](b) + "</td></tr>";
      }
    });
    html += "</tbody></table></div>";
    if (a.anio !== b.anio) html += '<p class="small">Las temporadas difieren (' + esc(a.anio) + " y " + esc(b.anio) + ").</p>";
    html += '<p class="small">Cada puntaje se calcula con los años parecidos de su propio sitio; compáralos como lecturas, no como rendimientos.</p>';
    body.innerHTML = html;
  }

  // ------------------------------------------------------------ hash state (#s=id&c=a,b)
  function writeHash() {
    var parts = [];
    if (state.selected) parts.push("s=" + encodeURIComponent(state.selected));
    if (state.compare.length) parts.push("c=" + state.compare.map(encodeURIComponent).join(","));
    history.replaceState(null, "", parts.length ? "#" + parts.join("&") : location.pathname);
  }
  function readHash() {
    var h = location.hash.replace(/^#/, ""), sel = null;
    h.split("&").forEach(function (kv) {
      var p = kv.split("="), v = decodeURIComponent(p[1] || "");
      if (p[0] === "s" && state.byId[v]) sel = v;
      if (p[0] === "c") state.compare = v.split(",").filter(function (id) {
        return state.byId[id] && state.byId[id]._estado !== "pendiente";
      }).slice(0, 2);
    });
    renderCompare();
    renderList();
    if (sel) select(sel, false);
  }

  // ------------------------------------------------------------ events
  $("sitios").addEventListener("click", function (e) {
    var b = e.target.closest("button");
    if (!b) return;
    if (b.dataset.id) select(b.dataset.id, true);
    if (b.dataset.cmp) toggleCompare(b.dataset.cmp);
  });
  $("buscar").addEventListener("submit", function (e) {
    e.preventDefault();
    var q = $("q").value, pt = parseCoords(q);
    if (pt) { renderList(); nearestTo(pt, "a las coordenadas"); return; }
    var list = filtered();
    renderList();
    if (!q.trim()) { notice(""); return; }
    if (list.length === 1) { notice(""); select(list[0].id, true); }
    else if (!list.length) notice("Sin coincidencias para «" + esc(q) + "». Si es un lugar, escribe sus coordenadas para buscar el sitio más cercano.");
    else notice(list.length + " sitios coinciden con «" + esc(q) + "».");
  });
  $("q").addEventListener("input", function () { if (!parseCoords($("q").value)) renderList(); });
  $("f-depto").addEventListener("change", renderList);
  $("f-estado").addEventListener("change", renderList);
  window.addEventListener("hashchange", function () { if (state.all.length) readHash(); });

  load();
})();
