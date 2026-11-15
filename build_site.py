"""Multi-page bilingual static site for Tempo, generated from out/parcela.json.

    python build_site.py   ->  web/site/{index,hindcast,metodo,fuentes,limites}.html (ES)
                               web/site/{index,hindcast,metodo,fuentes,limites}-en.html (EN)

Every number is read from out/<zona>.json. Copy stays honest: the headline only claims an
advantage when every condition in verdict() holds; otherwise it says no option is clearly better.
Spanish and English pages are built from the same function, string pairs side by side, so they
always carry the same content.
"""
import html
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out", "parcela.json")
SITE = os.path.join(HERE, "web", "site")

# Reading threshold for the gap between the top two final scores. It is a SUPUESTO (not a
# measured noise level): below it the site never names a winner.
READ_MARGIN = 0.05

NAMES = {"es": {"A": "Frijol en relevo tras maíz (práctica actual)", "B": "Sorgo (maicillo) + frijol",
                "C": "Segunda maíz"},
         "en": {"A": "Relay bean after maize (current practice)", "B": "Sorghum (maicillo) + bean",
                "C": "Second maize"}}
CLASS = {"es": {"good": "bueno", "partial": "parcial", "failure": "fallo",
                "short": "corta", "normal": "normal", "long": "larga"},
         "en": {"good": "good", "partial": "partial", "failure": "failure",
                "short": "short", "normal": "normal", "long": "long"}}
RESULT = {"es": {"hit": "acierto", "fallo": "fallo", "no_evaluable": "no evaluable"},
          "en": {"hit": "hit", "fallo": "miss", "no_evaluable": "not evaluable"}}
RUNS = {"es": {"whc_60": "Capacidad de agua 60 mm", "whc_90": "Capacidad de agua 90 mm",
               "whc_130": "Capacidad de agua 130 mm", "no_bean_excess_rule": "Sin la regla de 150 mm del frijol"},
        "en": {"whc_60": "Water capacity 60 mm", "whc_90": "Water capacity 90 mm",
               "whc_130": "Water capacity 130 mm", "no_bean_excess_rule": "Without the 150 mm bean rule"}}
WEIGHTS = {"es": {"food": "Comida", "income": "Ingreso", "soil": "Suelo", "water": "Agua", "labor": "Mano de obra"},
           "en": {"food": "Food", "income": "Income", "soil": "Soil", "water": "Water", "labor": "Labor"}}
PAGES = [("index", "Veredicto", "Verdict"), ("hindcast", "Hindcast", "Hindcast"),
         ("metodo", "Método", "Method"), ("fuentes", "Fuentes", "Sources"), ("limites", "Límites", "Limits")]


def esc(x):
    return html.escape(str(x))


def fname(key, lang):
    return f"{key}.html" if lang == "es" else f"{key}-en.html"


def num(x, lang, nd=2):
    if x is None:
        return "—"
    s = f"{x:.{nd}f}"
    return s.replace(".", ",") if lang == "es" else s


def page(lang, key, title, desc, body):
    t = (lambda es, en: es if lang == "es" else en)
    other = "en" if lang == "es" else "es"
    links = "".join(
        f'<a href="{fname(k, lang)}"{" aria-current=\"page\"" if k == key else ""}>{es if lang == "es" else en}</a>'
        for k, es, en in PAGES)
    switch = (f'<a class="lang" href="{fname(key, other)}" hreflang="{other}" lang="{other}">'
              f'{"English" if other == "en" else "Español"}</a>')
    alt = "".join(f'<link rel="alternate" hreflang="{l}" href="{fname(key, l)}">' for l in ("es", "en"))
    return f"""<!doctype html>
<html lang="{lang}"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(title)} · Tempo</title>
<meta name="description" content="{esc(desc)}">
{alt}
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Newsreader:opsz,wght@6..72,400;6..72,600&family=Hanken+Grotesk:wght@400;500;600&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
<link rel="stylesheet" href="style.css">
</head><body>
<a class="skip" href="#main">{t("Saltar al contenido", "Skip to content")}</a>
<header class="top"><div class="wrap">
  <a class="brand" href="{fname('index', lang)}">Tempo</a>
  <nav aria-label="{t('Principal', 'Main')}">{links}</nav>
  <div class="langs" role="group" aria-label="{t('Idioma', 'Language')}"><span class="lang lang--on">{"ES" if lang == "es" else "EN"}</span>{switch}</div>
</div></header>
<main id="main" class="wrap" tabindex="-1">{body}</main>
<footer class="foot wrap"><p>{t(
        "Apoyo para decisiones de la postrera. No reemplaza el criterio agronómico local. Datos: NASA POWER, GPM IMERG V07, SRTM, ISRIC SoilGrids. Sitio generado localmente; no publicado.",
        "Decision support for the postrera season. It does not replace local agronomic judgement. Data: NASA POWER, GPM IMERG V07, SRTM, ISRIC SoilGrids. Site built locally; not published.")}</p></footer>
</body></html>"""


def table(caption, head, rows, cls=""):
    """Accessible table. Cells carry data-label so narrow screens can stack rows without scrolling."""
    th = "".join(f'<th scope="col">{esc(h)}</th>' for h in head)
    body = "".join("<tr>" + "".join(f'<td data-label="{esc(h)}">{c}</td>' for h, c in zip(head, r)) + "</tr>"
                   for r in rows)
    return (f'<div class="table-wrap"><table class="{cls}"><caption>{esc(caption)}</caption>'
            f"<thead><tr>{th}</tr></thead><tbody>{body}</tbody></table></div>")


def verdict(d):
    """Conditions for naming a winner, as (key, passed). All must pass."""
    cur, pc = d["current"], d["primera_check"]
    sens, rs = d.get("sensitivity", {}), d["rain_source_sensitivity"]
    margin = cur.get("margin_over_second")
    return [
        ("margin", margin is not None and margin >= READ_MARGIN),
        ("params", sens.get("max_pick_changes", 1) == 0),
        ("rain", bool(rs.get("available")) and rs.get("n_verdict_changes", 1) == 0),
        ("check1", bool(pc.get("discriminative"))),
    ]


def build_lang(d, lang):
    t = (lambda es, en: es if lang == "es" else en)
    n = (lambda x, nd=2: num(x, lang, nd))
    yes = (lambda b: t("sí", "yes") if b else "no")
    N, C, R = NAMES[lang], CLASS[lang], RESULT[lang]
    cur, v, sk = d["current"], d["validation"], d["skill"]
    strat = {s["key"]: s for s in d["strategies"]}
    inp, pc, rs = d["inputs"], d["primera_check"], d["rain_source_sensitivity"]
    sens = d["sensitivity"]
    runs = sens["runs"]
    hc = d["hindcast"]["years"]
    year = d["current_year"]
    rec = cur["recommended"]
    margin = cur.get("margin_over_second")
    conds = verdict(d)
    n_ok = sum(ok for _, ok in conds)
    clear = n_ok == len(conds)
    nb, w60 = runs["no_bean_excess_rule"], runs["whc_60"]
    w60_disc = w60["check1"]["discriminative"]

    # ------------------------------------------------------------ index
    if clear:
        h1 = t(f"Para {year}, el modelo favorece: {N[rec].lower()}", f"For {year}, the model favours: {N[rec].lower()}")
        lead = t(f"Ventaja de {n(margin, 3)} puntos sobre la segunda opción, y la elección no cambia con otros supuestos ni con otra fuente de lluvia.",
                 f"A {n(margin, 3)} point lead over the second option, and the choice does not change under other assumptions or another rain source.")
    else:
        h1 = t(f"Ninguna opción es claramente mejor para esta parcela en {year}",
               f"No option is clearly better for this plot in {year}")
        lead = t(f"El puntaje más alto es para {N[rec].lower()}, con {n(margin, 3)} puntos sobre la segunda opción, y el resultado depende de supuestos sin validar. Léalo como una descripción de la temporada, no como una recomendación.",
                 f"The highest score goes to {N[rec].lower()}, {n(margin, 3)} points above the second option, and the result depends on unvalidated assumptions. Read it as a description of the season, not as a recommendation.")

    cond_txt = {
        "margin": (t("Margen entre las dos mejores opciones", "Gap between the top two options"),
                   t(f"{n(margin, 3)} puntos; el umbral de lectura es {n(READ_MARGIN)} (un SUPUESTO, no una medida del error).",
                     f"{n(margin, 3)} points; the reading threshold is {n(READ_MARGIN)} (an ASSUMPTION, not a measured error).")),
        "params": (t("Estable ante otros supuestos", "Stable under other assumptions"),
                   t(f"Sin la regla de 150 mm del frijol, la elección cambia en {nb['n_pick_changes']} de {nb['n_years_compared']} años; con 60 mm de capacidad de agua, en {w60['n_pick_changes']}.",
                     f"Without the 150 mm bean rule, the pick changes in {nb['n_pick_changes']} of {nb['n_years_compared']} years; with 60 mm water capacity, in {w60['n_pick_changes']}.")),
        "rain": (t("Estable con otra fuente de lluvia", "Stable with another rain source"),
                 t(f"Con NASA POWER en lugar de IMERG, la elección cambia en {rs.get('n_verdict_changes')} de {rs.get('n_years_compared')} años.",
                   f"With NASA POWER instead of IMERG, the pick changes in {rs.get('n_verdict_changes')} of {rs.get('n_years_compared')} years.")),
        "check1": (t("El modelo reconoce las sequías documentadas", "The model recognises documented droughts"),
                   t(f"No evaluable: {pc['n_at_max_wrsi']} de {pc['n_years']} años empatan en WRSI 100 en maíz de primera." if not pc["discriminative"]
                     else f"{len(pc['documented_in_worst_third'])} de {len(pc['documented'])} años documentados entre los peores.",
                     f"Not evaluable: {pc['n_at_max_wrsi']} of {pc['n_years']} years tie at WRSI 100 for primera maize." if not pc["discriminative"]
                     else f"{len(pc['documented_in_worst_third'])} of {len(pc['documented'])} documented years among the worst.")),
    }
    cond_items = "".join(
        f'<li class="cond cond--{"ok" if ok else "no"}"><span class="cond-mark">{t("Cumple", "Met") if ok else t("No cumple", "Not met")}</span>'
        f'<strong>{esc(cond_txt[k][0])}</strong> <span>{esc(cond_txt[k][1])}</span></li>'
        for k, ok in conds)

    best = max(s["score"] for s in strat.values() if s["score"] is not None)
    cards = ""
    for k in ("A", "B", "C"):
        s, st = strat[k], strat[k]["analog_stats"]
        cards += f"""<article class="card{' card--lead' if (clear and k == rec) else ''}">
<p class="eyebrow">{t('Estrategia', 'Strategy')} {k}</p>
<h3>{esc(N[k])}</h3>
<p class="num">{n(s['score'], 3)}<span> / {n(1.0)}</span></p>
<dl class="facts">
<div><dt>{t('Diferencia con el puntaje más alto', 'Gap to the highest score')}</dt><dd>{n(best - s['score'], 3)}</dd></div>
<div><dt>{t(f'Clima: media en {st["n_years"]} años parecidos', f'Climate: mean in {st["n_years"]} similar years')}</dt><dd>{n(st['mean_score'])}</dd></div>
<div><dt>{t('Años con fallo entre ellos', 'Failure years among them')}</dt><dd>{int(round(100 * (st['failure_rate'] or 0)))} %</dd></div>
</dl></article>"""

    index_body = f"""
<section class="hero">
  <p class="eyebrow">{t('Parcela', 'Plot')} {n(d['zone']['lat'], 6)} · {n(d['zone']['lon'], 6)} · {t('temporada', 'season')} {year}</p>
  <h1>{esc(h1)}</h1>
  <p class="lead">{esc(lead)}</p>
  <ul class="chips" aria-label="{t('Datos de la parcela', 'Plot data')}">
    <li class="chip">{t('Lluvia', 'Rain')}: IMERG {round(100 * inp['share_days_imerg'])} %</li>
    <li class="chip">{t('Suelo', 'Soil')}: {esc(inp['texture_class'])}, {inp['whc_mm']} mm</li>
    <li class="chip">{t('Canícula', 'Mid-summer drought')}: {cur['canicula_days']} {t('días', 'days')} ({esc(C.get(cur['canicula_class'], cur['canicula_class']))})</li>
    <li class="chip">{t('Pendiente', 'Slope')}: {n(inp['slope_pct'], 1)} %</li>
  </ul>
</section>
<section class="block" aria-labelledby="how"><h2 id="how">{t('Cómo leer el veredicto', 'How to read the verdict')}</h2>
  <p>{t(f'Tempo solo nombra una opción mejor cuando se cumplen las cuatro condiciones. Hoy se cumplen {n_ok} de 4.',
         f'Tempo only names a better option when all four conditions hold. Today {n_ok} of 4 hold.')}</p>
  <ul class="conds">{cond_items}</ul>
  <p class="muted">{t('Puntaje de 0 a 1: 60 % viene del clima (cómo le fue a cada opción en años con una canícula parecida) y 40 % de las prioridades del hogar (comida, ingreso, suelo, agua, mano de obra). No es un rendimiento.',
                      'Score from 0 to 1: 60 % comes from climate (how each option did in years with a similar mid-summer drought) and 40 % from household priorities (food, income, soil, water, labor). It is not a yield.')}</p>
</section>
<section class="block" aria-labelledby="opts"><h2 id="opts">{t('Las tres opciones', 'The three options')}</h2><div class="grid3">{cards}</div></section>
<section class="block" aria-labelledby="past"><h2 id="past">{t('Qué dice el pasado', 'What the past says')}</h2>
  <p>{t(f'En {v["n_years"]} años (2001–2025, cada año evaluado sin usarlo), la regla de Tempo obtiene {n(v["mean_score_tempo"])} y la práctica actual {n(v["mean_score_current"])}: margen medio de {n(v["mean_margin_vs_current"])}. Tempo es mejor en {v["years_tempo_better"]} años y peor en {v["years_tempo_worse"]} (prueba de signos p = {n(v["sign_test_p"], 4)}).',
         f'Over {v["n_years"]} years (2001–2025, each year evaluated without using it), the Tempo rule scores {n(v["mean_score_tempo"])} and current practice {n(v["mean_score_current"])}: mean margin {n(v["mean_margin_vs_current"])}. Tempo is better in {v["years_tempo_better"]} years and worse in {v["years_tempo_worse"]} (sign test p = {n(v["sign_test_p"], 4)}).')}</p>
  <p>{t(f'Sembrar siempre la misma estrategia obtiene {n(v["mean_score_same_every_year"])} (margen de Tempo frente a eso: {n(v["mean_margin_vs_same_every_year"])}). Sin la regla de 150 mm del frijol, el margen frente a la práctica actual pasa a {n(nb["mean_margin_vs_current"])} y la elección cambia en {nb["n_pick_changes"]} de {nb["n_years_compared"]} años.',
         f'Planting the same strategy every year scores {n(v["mean_score_same_every_year"])} (Tempo margin over that: {n(v["mean_margin_vs_same_every_year"])}). Without the 150 mm bean rule, the margin over current practice becomes {n(nb["mean_margin_vs_current"])} and the pick changes in {nb["n_pick_changes"]} of {nb["n_years_compared"]} years.')}</p>
  <p><a href="{fname('hindcast', lang)}">{t('Ver el hindcast año por año y la sensibilidad', 'See the year-by-year hindcast and sensitivity')}</a> · <a href="{fname('limites', lang)}">{t('Ver los límites', 'See the limits')}</a></p>
</section>"""

    # ------------------------------------------------------------ hindcast
    rows = [[str(r["year"]), esc(C.get(r.get("canicula_class"), "—")), esc(r.get("strategy") or "—"),
             n(r.get("score_strategy")), n(r.get("score_current")),
             esc(R.get(r.get("result"), "—")), yes(r.get("documented"))] for r in hc]
    sens_rows = []
    for k, r in runs.items():
        yrs = ", ".join(str(c["year"]) for c in r["pick_changes"]) or "—"
        if r["n_pick_changes"] and r["n_pick_changes"] == r["n_years_compared"]:
            yrs = t("todos", "all")
        sens_rows.append([esc(RUNS[lang][k]), f"{r['n_pick_changes']} / {r['n_years_compared']}", esc(yrs),
                          n(r["mean_score_tempo"]), n(r["mean_score_current"]), n(r["mean_margin_vs_current"]),
                          yes(r["check1"]["discriminative"])])
    rain_rows = [[esc(k), esc(w["months"]), str(w["n_years"]), f"{n(w['bias_pct'], 1)} %", n(w["spearman"])]
                 for k, w in rs.get("windows", {}).items()]
    check1_note = (t(f"Acierto/fallo se marca solo en años con sequía documentada con fuente citada. Aquí es «no evaluable»: {pc['n_at_max_wrsi']} de {pc['n_years']} años empatan en WRSI 100 en maíz de primera y un empate no cuenta como acierto.",
                     f"Hit/miss is only marked for years with a cited, documented drought. Here it is “not evaluable”: {pc['n_at_max_wrsi']} of {pc['n_years']} years tie at WRSI 100 for primera maize, and a tie does not count as a hit.")
                   if not pc["discriminative"] else
                   t("Acierto/fallo se marca solo en años con sequía documentada con fuente citada. Los empates toman el rango más alto.",
                     "Hit/miss is only marked for years with a cited, documented drought. Ties take the highest rank."))
    nb_txt = (t(f'Sin la regla de 150 mm, la práctica actual obtiene {n(nb["mean_score_current"])} y Tempo {n(nb["mean_score_tempo"])}: la ventaja depende de un umbral que es un SUPUESTO.',
                f'Without the 150 mm rule, current practice scores {n(nb["mean_score_current"])} and Tempo {n(nb["mean_score_tempo"])}: the advantage depends on a threshold that is an ASSUMPTION.'))
    w60_txt = (t(f' Con 60 mm de capacidad de agua, CHECK 1 {"sí" if w60_disc else "tampoco"} discrimina y la elección cambia en {w60["n_pick_changes"]} años.',
                 f' With 60 mm water capacity, CHECK 1 {"does" if w60_disc else "still does not"} discriminate and the pick changes in {w60["n_pick_changes"]} years.'))
    hindcast_body = f"""
<section class="hero hero--sm">
  <p class="eyebrow">{t('Validación retrospectiva · 2001–2025 · dejando un año fuera', 'Retrospective validation · 2001–2025 · leave-one-out')}</p>
  <h1>{t('Qué habría pasado en cada año', 'What would have happened each year')}</h1>
  <p class="lead">{t(f'Cada año se evalúa con la regla elegida sin usar ese año. {year} no entra en la validación. El puntaje va de 0 a 1: 1 bueno, 0,5 parcial, 0 fallo.',
                     f'Each year is evaluated with the chosen rule without using that year. {year} is not part of the validation. Score from 0 to 1: 1 good, 0.5 partial, 0 failure.')}</p>
</section>
<section class="block" aria-labelledby="yby"><h2 id="yby">{t('Año por año', 'Year by year')}</h2>
{table(t('Elección de Tempo frente a la práctica actual (A), por año', 'Tempo pick versus current practice (A), by year'),
       [t('Año', 'Year'), t('Canícula', 'Mid-summer drought'), t('Elegida', 'Pick'), t('Puntaje elegida', 'Pick score'),
        t('Puntaje A', 'A score'), t('Acierto/fallo', 'Hit/miss'), t('Sequía documentada', 'Documented drought')], rows, "stack")}
<p class="muted">{esc(check1_note)}</p></section>
<section class="block" aria-labelledby="sens"><h2 id="sens">{t('Sensibilidad a los supuestos', 'Sensitivity to assumptions')}</h2>
<p>{t(f'Se repite el hindcast cambiando un supuesto a la vez. Base: capacidad de agua {sens["baseline"]["whc_mm"]} mm y regla de {sens["baseline"]["bean_excess_rain_late_mm"]} mm de lluvia al final del ciclo del frijol. Los valores por defecto no se cambian.',
       f'The hindcast is re-run changing one assumption at a time. Baseline: water capacity {sens["baseline"]["whc_mm"]} mm and the {sens["baseline"]["bean_excess_rain_late_mm"]} mm late-season rain rule for beans. Defaults are not changed.')}</p>
{table(t('Años en que cambia la elección frente a la base', 'Years in which the pick changes versus the baseline'),
       [t('Variante', 'Variant'), t('Años que cambian', 'Years that change'), t('Cuáles', 'Which'), 'Tempo',
        t('Práctica A', 'Practice A'), t('Margen', 'Margin'), t('CHECK 1 discrimina', 'CHECK 1 discriminates')], sens_rows, "stack")}
<p>{esc(nb_txt + w60_txt)}</p>
</section>
<section class="block" aria-labelledby="rain"><h2 id="rain">{t('Lluvia: IMERG frente a NASA POWER', 'Rain: IMERG versus NASA POWER')}</h2>
<p>{t(f'Con NASA POWER en lugar de IMERG, la estrategia elegida cambia en {rs.get("n_verdict_changes")} de {rs.get("n_years_compared")} años.',
       f'With NASA POWER instead of IMERG, the chosen strategy changes in {rs.get("n_verdict_changes")} of {rs.get("n_years_compared")} years.')}</p>
{table(t('Diferencia de lluvia por ventana (POWER − IMERG)', 'Rain difference by window (POWER − IMERG)'),
       [t('Ventana', 'Window'), t('Meses', 'Months'), t('Años', 'Years'), t('Sesgo POWER − IMERG', 'Bias POWER − IMERG'), 'Spearman'],
       rain_rows, "stack")}</section>"""

    # ------------------------------------------------------------ method
    weight_rows = [[esc(WEIGHTS[lang].get(k, k)), n(w, 1)] for k, w in inp["weights"].items()]
    steps = [
        (t("Lluvia", "Rain"), t("IMERG V07 sumado por día local (UTC−6) en el punto. Si faltan días, NASA POWER como respaldo.",
                                "IMERG V07 summed per local day (UTC−6) at the point. NASA POWER fills missing days.")),
        (t("Temperatura", "Temperature"), t(f"NASA POWER, corregida por elevación con SRTM ({n(inp['temp_correction_c'])} °C en esta parcela, −0,0065 °C/m).",
                                            f"NASA POWER, corrected for elevation with SRTM ({n(inp['temp_correction_c'])} °C at this plot, −0.0065 °C/m).")),
        (t("Evapotranspiración", "Evapotranspiration"), t("Hargreaves con (Tmax+Tmin)/2, según FAO-56 ec. 52.",
                                                          "Hargreaves with (Tmax+Tmin)/2, FAO-56 eq. 52.")),
        (t("Suelo", "Soil"), t(f"capacidad de agua de {inp['whc_mm']} mm según la textura {inp['texture_class']} (SoilGrids). El valor por textura es un SUPUESTO.",
                               f"water capacity of {inp['whc_mm']} mm from the {inp['texture_class']} texture (SoilGrids). The value per texture is an ASSUMPTION.")),
        (t("Balance", "Balance"), t("cubeta diaria con tope de capacidad; el estrés empieza bajo la mitad de la capacidad. Índice tipo WRSI simplificado, no FAO-56 completo. Clases: ≥ 80 bueno, 60–80 parcial, < 60 fallo; baja una clase si hay estrés en floración o, en frijol, más de 150 mm de lluvia al final del ciclo.",
                                    "daily bucket capped at capacity; stress starts below half of capacity. Simplified WRSI-type index, not full FAO-56. Classes: ≥ 80 good, 60–80 partial, < 60 failure; one class down for stress at flowering or, for beans, more than 150 mm of rain at the end of the cycle.")),
        (t("Años parecidos", "Similar years"), t("los años se agrupan en tercios por la duración de la canícula; para cada año se usan los otros años del mismo tercio. Nunca el año evaluado ni la temporada actual.",
                                                 "years are grouped into thirds by mid-summer drought length; each year uses the other years in the same third. Never the year being evaluated nor the current season.")),
        (t("Empates", "Ties"), t("si dos opciones empatan en el clima, se mantiene la práctica actual. En la prueba de sequías, los años empatados toman el rango más alto, y si la mayoría empata la prueba se marca «no evaluable».",
                                 "if two options tie on climate, current practice is kept. In the drought check, tied years take the highest rank, and if most years tie the check is marked “not evaluable”.")),
        (t("Puntaje final", "Final score"), t(f"60 % clima y 40 % prioridades. Con pendiente sobre 15 % (aquí {n(inp['slope_pct'], 1)} %), el peso del suelo se multiplica por 1,5.",
                                              f"60 % climate and 40 % priorities. With slope above 15 % (here {n(inp['slope_pct'], 1)} %), the soil weight is multiplied by 1.5.")),
        (t("Margen y prueba de signos", "Margin and sign test"), t("el margen es la diferencia media de puntaje frente a la práctica actual. La prueba de signos cuenta años mejores y peores e ignora empates; no corrige por supuestos compartidos entre años.",
                                                                  "the margin is the mean score difference against current practice. The sign test counts better and worse years and ignores ties; it does not account for assumptions shared across years.")),
    ]
    method_body = f"""
<section class="hero hero--sm"><p class="eyebrow">{t('Método', 'Method')}</p><h1>{t('Cómo se calcula', 'How it is calculated')}</h1>
<p class="lead">{t('Un balance hídrico diario sencillo sobre la parcela, con lluvia de satélite y temperatura de reanálisis.',
                   'A simple daily water balance for the plot, with satellite rain and reanalysis temperature.')}</p></section>
<section class="block" aria-labelledby="steps"><h2 id="steps">{t('Pasos', 'Steps')}</h2><ol class="steps">
{''.join(f'<li><strong>{esc(a)}:</strong> {esc(b)}</li>' for a, b in steps)}
</ol></section>
<section class="block" aria-labelledby="w"><h2 id="w">{t('Pesos de prioridad', 'Priority weights')}</h2>
{table(t('Pesos usados en el puntaje final', 'Weights used in the final score'), [t('Prioridad', 'Priority'), t('Peso', 'Weight')], weight_rows)}
<p class="muted">{t('Pesos definidos por el equipo; son SUPUESTOS, no datos medidos.', 'Weights set by the team; they are ASSUMPTIONS, not measured data.')}</p></section>"""

    # ------------------------------------------------------------ sources
    src_rows = [
        ["GPM IMERG V07 (NASA/GPM_L3/IMERG_V07, GEE)", t("Lluvia cada 30 min", "Rain every 30 min"),
         t("Suma diaria en el punto, reducción en servidor", "Daily total at the point, reduced server-side")],
        ["NASA POWER Daily AG", t("Temperatura, radiación, humedad, lluvia (respaldo)", "Temperature, radiation, humidity, rain (backup)"),
         t("Serie diaria del punto", "Daily series at the point")],
        ["SRTM GL1 (USGS/SRTMGL1_003, GEE)", t("Elevación y pendiente", "Elevation and slope"),
         t("Corrección de temperatura y peso del suelo", "Temperature correction and soil weight")],
        ["ISRIC SoilGrids v2", t("Arena, limo, arcilla y carbono 0–30 cm", "Sand, silt, clay and carbon 0–30 cm"),
         t("Textura y capacidad de agua", "Texture and water capacity")],
        ["FAO-56 (Allen et al., 1998)", t("Coeficientes de cultivo y etapas", "Crop coefficients and stages"),
         t("Valores por defecto, sin validar localmente", "Defaults, not validated locally")],
        ["FEWS NET / FAO-GIEWS / ReliefWeb", t("Años con sequía documentada", "Years with documented drought"),
         t("Solo años con cita verificable", "Only years with a verifiable citation")],
    ]
    sources_body = f"""
<section class="hero hero--sm"><p class="eyebrow">{t('Fuentes', 'Sources')}</p><h1>{t('De dónde sale cada número', 'Where each number comes from')}</h1></section>
<section class="block">{table(t('Fuentes de datos', 'Data sources'), [t('Fuente', 'Source'), t('Qué aporta', 'What it provides'), t('Cómo se usa', 'How it is used')], [[esc(c) for c in r] for r in src_rows], "stack")}</section>"""

    # ------------------------------------------------------------ limits
    limits = [
        (t("Sin rendimientos reales.", "No real yields."),
         t("No hay datos de cosecha por año para esta parcela; el puntaje es un modelo, no una cosecha observada.",
           "There are no yearly harvest data for this plot; the score is a model, not an observed harvest.")),
        (t("La ventaja depende de un supuesto.", "The advantage depends on an assumption."),
         t(f"Sin la regla de 150 mm del frijol, el margen frente a la práctica actual es {n(nb['mean_margin_vs_current'])} y la elección cambia en {nb['n_pick_changes']} de {nb['n_years_compared']} años.",
           f"Without the 150 mm bean rule, the margin over current practice is {n(nb['mean_margin_vs_current'])} and the pick changes in {nb['n_pick_changes']} of {nb['n_years_compared']} years.")),
        (t(f"Margen de {year}.", f"{year} margin."),
         t(f"La opción con más puntaje en {year} supera a la segunda por {n(margin, 3)} puntos; el umbral de lectura es {n(READ_MARGIN)}.",
           f"The top option in {year} leads the second by {n(margin, 3)} points; the reading threshold is {n(READ_MARGIN)}.")),
        (t("CHECK 1 no evaluable." if not pc["discriminative"] else "CHECK 1 evaluable.",
           "CHECK 1 not evaluable." if not pc["discriminative"] else "CHECK 1 evaluable."),
         t(f"{pc['n_at_max_wrsi']} de {pc['n_years']} años dan WRSI 100 en maíz de primera. Con 60 mm de capacidad de agua, CHECK 1 {'sí' if w60_disc else 'tampoco'} discrimina.",
           f"{pc['n_at_max_wrsi']} of {pc['n_years']} years give WRSI 100 for primera maize. With 60 mm water capacity, CHECK 1 {'does' if w60_disc else 'still does not'} discriminate.")),
        (t("Señal débil.", "Weak signal."),
         t(f"La canícula no predice la lluvia de septiembre a noviembre (Spearman {n(sk['canicula_vs_sep_nov_rain'])}, {sk['n_years']} años).",
           f"The mid-summer drought does not predict September–November rain (Spearman {n(sk['canicula_vs_sep_nov_rain'])}, {sk['n_years']} years).")),
        (t("Dependencia de la fuente de lluvia.", "Dependence on the rain source."),
         t(f"Con NASA POWER, la estrategia cambia en {rs.get('n_verdict_changes')} de {rs.get('n_years_compared')} años.",
           f"With NASA POWER, the strategy changes in {rs.get('n_verdict_changes')} of {rs.get('n_years_compared')} years.")),
        (t("Sin semáforo de riesgo.", "No risk light."),
         t("Se quitó: no hay rendimientos ni una prueba de sequías que respalde un umbral de riesgo.",
           "It was removed: there are no yields and no drought check that would support a risk threshold.")),
        (t("Supuestos sin validar.", "Unvalidated assumptions."),
         t("Capacidad de agua por textura, coeficientes de cultivo, proporciones 0,6/0,4, pesos de prioridad, umbral de 150 mm y umbral de lectura. Todos son SUPUESTO.",
           "Water capacity per texture, crop coefficients, 0.6/0.4 land shares, priority weights, the 150 mm threshold and the reading threshold. All are ASSUMPTIONS.")),
        (t("Una parcela.", "One plot."),
         t("Los resultados no se generalizan a otras fincas ni al resto del Corredor Seco.",
           "Results do not generalise to other farms or the rest of the Dry Corridor.")),
        (t("Pendiente de validación local.", "Local validation pending."),
         t("Falta revisión con técnicos de CENTA antes de cualquier uso en campo.",
           "Review with CENTA technicians is needed before any field use.")),
    ]
    limits_body = f"""
<section class="hero hero--sm"><p class="eyebrow">{t('Límites', 'Limits')}</p><h1>{t('Lo que este sitio no puede decir', 'What this site cannot say')}</h1></section>
<section class="block"><ul class="limits">{''.join(f'<li><strong>{esc(a)}</strong> {esc(b)}</li>' for a, b in limits)}</ul></section>"""

    return {
        fname("index", lang): page(lang, "index", t("Veredicto", "Verdict"),
                                   t("Veredicto de la postrera para la parcela.", "Postrera verdict for the plot."), index_body),
        fname("hindcast", lang): page(lang, "hindcast", "Hindcast",
                                      t("Validación retrospectiva año por año y sensibilidad.", "Year-by-year retrospective validation and sensitivity."), hindcast_body),
        fname("metodo", lang): page(lang, "metodo", t("Método", "Method"),
                                    t("Cómo se calcula el balance hídrico y el puntaje.", "How the water balance and the score are calculated."), method_body),
        fname("fuentes", lang): page(lang, "fuentes", t("Fuentes", "Sources"),
                                     t("Fuentes de datos de Tempo.", "Tempo data sources."), sources_body),
        fname("limites", lang): page(lang, "limites", t("Límites", "Limits"),
                                     t("Límites y supuestos de Tempo.", "Tempo limits and assumptions."), limits_body),
    }


def build():
    with open(OUT, encoding="utf-8") as f:
        d = json.load(f)
    os.makedirs(SITE, exist_ok=True)
    files = {**build_lang(d, "es"), **build_lang(d, "en")}
    for name, content in files.items():
        with open(os.path.join(SITE, name), "w", encoding="utf-8") as f:
            f.write(content)
    print("site written:", ", ".join(files))


if __name__ == "__main__":
    build()
