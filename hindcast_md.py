"""Write hindcast.md from out/<zone>.json (field hindcast.years). Never edit hindcast.md by hand.

    python hindcast_md.py           # after engine.py
"""
import json
import os

import config

HERE = os.path.dirname(os.path.abspath(__file__))
CROPS = ["maize", "bean", "sorghum"]
CROP_ES = {"maize": "Maíz", "bean": "Frijol", "sorghum": "Sorgo"}


def _f(x, fmt="{:.2f}"):
    return "—" if x is None else fmt.format(x)


def _crop(c):
    return "—" if not c else f"{c['wrsi']:.1f} {c['class']}"


def render_zone(d: dict) -> str:
    z, h, v, inp = d["zone"], d["hindcast"], d["validation"], d["inputs"]
    rows = h["years"]
    out = [f"## {z['key']} — {z['name']} ({z['lat']}, {z['lon']})", ""]
    out.append(f"Lluvia: {100 * inp['share_days_imerg']:.0f} % de los días desde IMERG; "
               f"el resto desde NASA POWER PRECTOTCORR. Suelo {inp['texture_class']}, WHC {inp['whc_mm']} mm. "
               f"Corrección de temperatura: {_f(inp['temp_correction_c'], '{} °C') if inp['temp_correction_c'] is not None else 'ninguna (null)'}.")
    for w in d.get("warnings", []):
        out.append(f"\n> Advertencia: {w}")
    out += ["", "| Año | Canícula | Elegida (LOO) | Score elegida | Score A | "
            + " | ".join(f"WRSI {CROP_ES[c]}" for c in CROPS)
            + " | Maíz primera (WRSI, rango) | Documentado | D6 | Fuente |",
            "|---|---|---|---|---|" + "---|" * len(CROPS) + "---|---|---|---|"]
    notes = []
    for r in rows:
        pm = r["primera_maize"]
        prim = "—" if not pm else f"{pm['wrsi']:.1f} (#{pm['rank_driest']})"
        ref = "—"
        if r["source"]:
            notes.append(r["source"])
            ref = f"[{len(notes)}]"
        out.append(f"| {r['year']} | {r['canicula_class'] or '—'} | {r['strategy'] or '—'} | "
                   f"{_f(r['score_strategy'])} | {_f(r['score_current'])} | "
                   + " | ".join(_crop(r["crops"].get(c)) for c in CROPS)
                   + f" | {prim} | {'sí' if r['documented'] else 'no'} | {r['result'] or '—'} | {ref} |")
    doc = [r for r in rows if r["documented"]]
    hits = [r["year"] for r in doc if r["result"] == "hit"]
    out += ["", f"D6: {len(hits)} hit de {len(doc)} años documentados "
            f"(hit = WRSI de maíz de primera entre los {h['worst_third_size']} peores del registro). "
            f"Hits: {hits or 'ninguno'}; fallos: {[r['year'] for r in doc if r['result'] == 'fallo'] or 'ninguno'}."]
    if v.get("n_years"):
        out.append(f"\nMedia ({v['n_years']} años): Tempo {v['mean_score_tempo']} · práctica A {v['mean_score_current']} · "
                   f"misma estrategia siempre {v['mean_score_same_every_year']} · mejor posible "
                   f"{v['mean_score_best_possible']} · Tempo mejor en {v['years_tempo_better']}, peor en "
                   f"{v['years_tempo_worse']} · elecciones {v['picks']}")
    if notes:
        out += ["", "Fuentes (D6):", ""] + [f"{i}. {n}" for i, n in enumerate(notes, 1)]
    return "\n".join(out) + "\n"


def render(zones: dict) -> str:
    head = ["# Hindcast 2001-2025 (leave-one-out)", "",
            "Generado por `hindcast_md.py` desde `out/<zona>.json` (`hindcast.years`). No editar a mano.", "",
            "Clase WRSI: good >= 80, partial 60-80, failure < 60. Score: 1 bueno, 0.5 parcial, 0 fallo.", "", ""]
    return "\n".join(head) + "\n".join(render_zone(d) for d in zones.values())


def load_zones() -> dict:
    zones = {}
    for z in config.ZONES:
        p = os.path.join(HERE, "out", f"{z.key}.json")
        if os.path.exists(p):
            with open(p) as f:
                zones[z.key] = json.load(f)
    return zones


def main() -> None:
    zones = load_zones()
    if not zones:
        raise SystemExit("No out/*.json found. Run engine.py first.")
    with open(os.path.join(HERE, "hindcast.md"), "w") as f:
        f.write(render(zones))
    print(f"hindcast.md written with zones: {', '.join(zones)}")


if __name__ == "__main__":
    main()
