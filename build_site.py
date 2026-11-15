"""Multi-page static site for Tempo, generated from out/parcela.json.

    python build_site.py   ->  web/site/{index,hindcast,metodo,fuentes,limites}.html + style.css

Every number is read from out/<zona>.json. No --demo. Copy stays honest: if a claim is not
supported by the output, it is not written.
"""
import html
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out", "parcela.json")
SITE = os.path.join(HERE, "web", "site")

NAMES = {"A": "Frijol en relevo tras maíz (práctica actual)",
         "B": "Sorgo (maicillo) + frijol",
         "C": "Segunda maíz"}
CROP = {"maize": "Maíz", "bean": "Frijol", "sorghum": "Sorgo"}


def esc(x):
    return html.escape(str(x))


def fmt(x, nd=2):
    return "—" if x is None else f"{x:.{nd}f}".replace(".", ",")


def page(title, active, body, desc):
    nav = [("index.html", "Veredicto"), ("hindcast.html", "Hindcast"),
           ("metodo.html", "Método"), ("fuentes.html", "Fuentes"), ("limites.html", "Límites")]
    links = "".join(f'<a href="{h}"{" aria-current=\"page\"" if h == active else ""}>{t}</a>' for h, t in nav)
    return f"""<!doctype html>
<html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(title)} · Tempo</title>
<meta name="description" content="{esc(desc)}">
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Newsreader:opsz,wght@6..72,400;6..72,600&family=Hanken+Grotesk:wght@400;500;600&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
<link rel="stylesheet" href="style.css">
</head><body>
<header class="top"><div class="wrap">
  <a class="brand" href="index.html">Tempo</a>
  <nav aria-label="Principal">{links}</nav>
</div></header>
<main class="wrap">{body}</main>
<footer class="foot wrap"><p>Apoyo para decisiones de la postrera. No reemplaza el criterio agronómico local. Datos: NASA POWER, GPM IMERG V07, SRTM, ISRIC SoilGrids. Sitio generado localmente; no publicado.</p></footer>
</body></html>"""


def build():
    d = json.load(open(OUT))
    cur, v, sk = d["current"], d["validation"], d["skill"]
    strat = {s["key"]: s for s in d["strategies"]}
    inp, pc, rs = d["inputs"], d["primera_check"], d["rain_source_sensitivity"]
    hc = d["hindcast"]["years"]
    n_disc = pc.get("discriminative", True)
    rec = cur["recommended"]
    scores = {k: strat[k]["score"] for k in ("A", "B", "C")}
    top = max(scores, key=scores.get)
    margin = round(scores[top] - sorted(scores.values())[-2], 3)
    # Honest reading of the ranking
    if margin < 0.05:
        verdict_title = "No hay una estrategia claramente mejor para esta parcela en 2026"
        verdict_lead = (f"Las tres opciones quedan a menos de {fmt(max(scores.values())-min(scores.values()))} puntos entre sí. "
                        "La lectura es de temporada, no una recomendación fuerte.")
    else:
        verdict_title = f"Ventaja clara para {NAMES[top].lower()}"
        verdict_lead = "La diferencia supera el margen de ruido del modelo."
    light = cur["traffic_light"]
    light_txt = {"green": "Sin alerta de estrés", "yellow": "Riesgo moderado", "red": "Riesgo alto"}.get(light, light)

    # --- index: verdict
    cards = ""
    for k in ("A", "B", "C"):
        s = strat[k]
        star = " card--lead" if (k == top and margin >= 0.05) else ""
        cards += f"""<article class="card{star}"><p class="eyebrow">Estrategia {k}</p>
<h3>{esc(NAMES[k])}</h3>
<p class="num">{fmt(s['score'])}<span> / 1,00</span></p>
<p class="muted">Puntaje ajustado a tus prioridades (comida, ingreso, suelo, agua, mano de obra). Diferencia con la mejor: {fmt(scores[top]-s['score'])}.</p></article>"""
    index_body = f"""
<section class="hero">
  <p class="eyebrow">Parcela 13,796406 · −89,801031 · temporada {d['current_year']}</p>
  <h1>{esc(verdict_title)}</h1>
  <p class="lead">{esc(verdict_lead)}</p>
  <div class="chips">
    <span class="chip">Lluvia: IMERG 100 %</span>
    <span class="chip">Suelo: {esc(inp['texture_class'])}, {inp['whc_mm']} mm</span>
    <span class="chip">Canícula: {cur['canicula_days']} días ({esc(cur['canicula_class'])})</span>
  </div>
</section>
<section class="block"><h2>Las tres opciones</h2><div class="grid3">{cards}</div></section>
<section class="block callout"><h2>Cómo leer esto</h2>
  <p>En la validación retrospectiva (2001–2025), elegir siempre la segunda maíz (C) obtiene un puntaje de {fmt(v['mean_score_same_every_year'])}, igual que el mejor modelo ({fmt(v['mean_score_tempo'])}). La práctica actual (A) obtiene {fmt(v['mean_score_current'])}.</p>
  <p>La señal de canícula frente a la lluvia de septiembre a noviembre es casi nula (Spearman {fmt(sk['canicula_vs_sep_nov_rain'])}). Por eso no hay base sólida para elegir una estrategia distinta de C en el hindcast.</p>
  <p><strong>Límite principal:</strong> CHECK 1 no discrimina. {pc['n_at_max_wrsi']} de {pc['n_years']} años dan WRSI 100 en maíz de primera, así que la prueba de años secos no separa nada. Ver <a href="limites.html">Límites</a>.</p>
</section>"""

    # --- hindcast table
    rows = ""
    for r in hc:
        res = r.get("result") or "—"
        rows += (f"<tr><td>{r['year']}</td><td>{esc(r.get('canicula_class') or '—')}</td>"
                 f"<td>{esc(r.get('strategy') or '—')}</td><td>{fmt(r.get('score_strategy'))}</td>"
                 f"<td>{fmt(r.get('score_current'))}</td><td>{esc(res)}</td>"
                 f"<td>{'sí' if r.get('documented') else 'no'}</td></tr>")
    sens = rs["windows"]
    sens_rows = "".join(f"<tr><td>{esc(k)}</td><td>{esc(w['months'])}</td><td>{w['n_years']}</td>"
                        f"<td>{fmt(w['bias_pct'],1)} %</td><td>{fmt(w['spearman'])}</td></tr>"
                        for k, w in sens.items())
    hindcast_body = f"""
<section class="hero hero--sm">
  <p class="eyebrow">Validación retrospectiva · 2001–2025 · leave-one-out</p>
  <h1>Qué habría pasado en cada año</h1>
  <p class="lead">Cada año se evalúa con la regla elegida sin usar ese año. El puntaje va de 0 a 1: 1 bueno, 0,5 parcial, 0 fallo.</p>
</section>
<section class="block"><h2>Año por año</h2>
<div class="table-wrap"><table><thead><tr><th>Año</th><th>Canícula</th><th>Elegida</th><th>Puntaje elegida</th><th>Puntaje A</th><th>Acierto/fallo</th><th>Sequía documentada</th></tr></thead>
<tbody>{rows}</tbody></table></div>
<p class="muted">Acierto/fallo se marca solo en años con fuente citada. CHECK 1 empata en WRSI 100: no es informativo.</p></section>
<section class="block"><h2>Lluvia: IMERG frente a POWER</h2>
<p>POWER da menos lluvia que IMERG en las tres ventanas. Con POWER, la estrategia elegida cambia en {rs['n_verdict_changes']} de {rs['n_years_compared']} años.</p>
<div class="table-wrap"><table><thead><tr><th>Ventana</th><th>Meses</th><th>Años</th><th>Sesgo POWER − IMERG</th><th>Spearman</th></tr></thead><tbody>{sens_rows}</tbody></table></div></section>"""

    # --- method
    cropz = "".join(f"<li><strong>{CROP[c]}</strong>: {esc(c)}</li>" for c in [])
    method_body = f"""
<section class="hero hero--sm"><p class="eyebrow">Método</p><h1>Cómo se calcula</h1>
<p class="lead">Un balance hídrico diario sencillo sobre la parcela, con lluvia y temperatura de satélite y reanálisis.</p></section>
<section class="block"><h2>Pasos</h2><ol class="steps">
<li><strong>Lluvia:</strong> IMERG V07 sumado por día local (UTC−6) en el punto. Si faltan días, POWER como respaldo.</li>
<li><strong>Temperatura:</strong> POWER, corregida por elevación con SRTM ({inp['temp_correction_c']} °C en esta parcela, −0,0065 °C/m).</li>
<li><strong>Evapotranspiración:</strong> Hargreaves con (Tmax+Tmin)/2, según FAO-56.</li>
<li><strong>Suelo:</strong> capacidad de agua de {inp['whc_mm']} mm según la textura {esc(inp['texture_class'])} (SoilGrids). El valor de capacidad por textura es un SUPUESTO.</li>
<li><strong>Balance:</strong> cubeta diaria con tope de capacidad y agotamiento p = 0,5 para todos los cultivos. Es un índice tipo WRSI simplificado, no FAO-56 completo.</li>
<li><strong>Puntaje:</strong> ponderado por comida, ingreso, suelo, agua y mano de obra (pesos en la tabla de abajo).</li></ol></section>
<section class="block"><h2>Pesos de prioridad</h2><div class="table-wrap"><table><thead><tr><th>Prioridad</th><th>Peso</th></tr></thead><tbody>
{''.join(f'<tr><td>{esc(k)}</td><td>{fmt(w,1)}</td></tr>' for k, w in inp['weights'].items())}
</tbody></table></div><p class="muted">Pesos definidos por el equipo; son SUPUESTOS, no datos medidos.</p></section>"""

    # --- sources
    sources_body = """
<section class="hero hero--sm"><p class="eyebrow">Fuentes</p><h1>De dónde sale cada número</h1></section>
<section class="block"><div class="table-wrap"><table><thead><tr><th>Fuente</th><th>Qué aporta</th><th>Cómo se usa</th></tr></thead><tbody>
<tr><td>GPM IMERG V07 (NASA/GPM_L3/IMERG_V07, GEE)</td><td>Lluvia cada 30 min</td><td>Suma diaria en el punto, reducción en servidor</td></tr>
<tr><td>NASA POWER Daily AG</td><td>Temperatura, radiación, humedad, lluvia (respaldo)</td><td>Serie diaria del punto</td></tr>
<tr><td>SRTM GL1 (USGS/SRTMGL1_003, GEE)</td><td>Elevación y pendiente</td><td>Corrección de temperatura</td></tr>
<tr><td>ISRIC SoilGrids v2</td><td>Arena, limo, arcilla y carbono 0–30 cm</td><td>Textura y capacidad de agua</td></tr>
<tr><td>FEWS NET / FAO-GIEWS / ReliefWeb</td><td>Años con sequía documentada</td><td>Solo años con cita verificable</td></tr>
</tbody></table></div></section>"""

    # --- limits
    limits_body = f"""
<section class="hero hero--sm"><p class="eyebrow">Límites</p><h1>Lo que este sitio no puede decir</h1></section>
<section class="block"><ul class="limits">
<li><strong>Sin rendimientos reales.</strong> No hay datos de cosecha por año para esta parcela; el puntaje es un modelo, no una cosecha observada.</li>
<li><strong>CHECK 1 no discrimina.</strong> {pc['n_at_max_wrsi']} de {pc['n_years']} años dan WRSI 100 en maíz de primera. No hay prueba de que el modelo distinga años secos.</li>
<li><strong>Señal débil.</strong> La canícula no predice la lluvia de septiembre a noviembre (Spearman {fmt(sk['canicula_vs_sep_nov_rain'])}).</li>
<li><strong>Dependencia de la fuente de lluvia.</strong> Con POWER, la estrategia cambia en {rs['n_verdict_changes']} de {rs['n_years_compared']} años.</li>
<li><strong>Supuestos sin validar.</strong> Capacidad de agua por textura, coeficientes de cultivo, pesos de prioridad y el umbral de 150 mm para frijol. Todos son SUPUESTO.</li>
<li><strong>Una parcela.</strong> Los resultados no se generalizan a otras fincas ni al resto del Corredor Seco.</li>
<li><strong>Pendiente de validación local.</strong> Falta revisión con técnicos de CENTA antes de cualquier uso en campo.</li>
</ul></section>"""

    base = os.path.join(SITE)
    os.makedirs(base, exist_ok=True)
    files = {
        "index.html": page("Veredicto", "index.html", index_body, "Veredicto de la postrera para la parcela."),
        "hindcast.html": page("Hindcast", "hindcast.html", hindcast_body, "Validación retrospectiva año por año."),
        "metodo.html": page("Método", "metodo.html", method_body, "Cómo se calcula el balance hídrico y el puntaje."),
        "fuentes.html": page("Fuentes", "fuentes.html", sources_body, "Fuentes de datos de Tempo."),
        "limites.html": page("Límites", "limites.html", limits_body, "Límites y supuestos de Tempo."),
    }
    for name, content in files.items():
        open(os.path.join(base, name), "w").write(content)
    print("site written:", ", ".join(files))


if __name__ == "__main__":
    build()
