"""Exporta una instantánea de demo de los análisis guardados a web/app/demo/.

La instantánea permite abrir la app sin servidor ni caché (por ejemplo, una página estática para el
jurado). Se versiona a propósito; es la única excepción a la regla de no subir JSON de caché
(tests/test_rules.py). Regenerar después de `python server.py --reanalizar`:

    python export_demo.py               # análisis + sitios
    python export_demo.py --sitios      # solo demo/sitios.json (no toca los análisis)
"""
from __future__ import annotations

import json
import os

import server

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "web", "app", "demo")


def export_sitios() -> None:
    """demo/sitios.json: los sitios de parcelas.json para el buscador (igual que GET /api/sitios)."""
    with open(os.path.join(OUT, "sitios.json"), "w", encoding="utf-8") as f:
        json.dump({"sitios": server.sites_public()}, f, ensure_ascii=False, indent=1)


def main() -> None:
    store = server.JobStore()
    os.makedirs(OUT, exist_ok=True)
    for f in os.listdir(OUT):
        if f.endswith(".json"):
            os.remove(os.path.join(OUT, f))
    jobs = []
    for rec in sorted(store.all(), key=lambda r: r.get("creado", "")):
        if rec.get("estado") not in server.TERMINADOS:
            continue
        path = store.result_path(rec["id"])
        if not os.path.exists(path):
            continue
        with open(path, encoding="utf-8") as f:
            result = json.load(f)
        pub = server.public(rec)
        with open(os.path.join(OUT, f"{rec['id']}.json"), "w", encoding="utf-8") as f:
            json.dump({"job": pub, "result": result}, f, ensure_ascii=False, separators=(",", ":"))
        jobs.append(pub)
    with open(os.path.join(OUT, "jobs.json"), "w", encoding="utf-8") as f:
        json.dump({"jobs": jobs, "exportado_utc": server._now()}, f, ensure_ascii=False, indent=1)
    export_sitios()
    print(f"{len(jobs)} análisis exportados a {OUT}")


if __name__ == "__main__":
    import sys
    if "--sitios" in sys.argv:
        os.makedirs(OUT, exist_ok=True)
        export_sitios()
    else:
        main()
