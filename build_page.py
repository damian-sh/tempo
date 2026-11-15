"""Build the static page: inline every out/<zone>.json into web/template.html.

    python build_page.py            # -> web/index.html

The page then works offline and from any static host (GitHub Pages, a USB stick).
"""
import argparse
import glob
import json
import os

import config

HERE = os.path.dirname(os.path.abspath(__file__))


def main() -> None:
    # --demo was removed: it set a flag the template never read (no banner was shown).
    argparse.ArgumentParser(description=__doc__.splitlines()[0]).parse_args()
    zones = {}
    order = [z.key for z in config.ZONES]
    files = sorted(glob.glob(os.path.join(HERE, "out", "*.json")),
                   key=lambda p: order.index(os.path.basename(p)[:-5]) if os.path.basename(p)[:-5] in order else 99)
    for path in files:
        with open(path) as f:
            zones[os.path.basename(path)[:-5]] = json.load(f)
    if not zones:
        raise SystemExit("No out/*.json found. Run engine.py first.")

    data = json.dumps({"zones": zones}, separators=(",", ":"), allow_nan=False)
    data = data.replace("</", "<\\/")  # never close the <script> early
    with open(os.path.join(HERE, "web", "template.html")) as f:
        html = f.read()
    html = html.replace("/*TEMPO_DATA*/null", data)
    with open(os.path.join(HERE, "web", "index.html"), "w") as f:
        f.write(html)
    print(f"web/index.html written with zones: {', '.join(zones)}")


if __name__ == "__main__":
    main()
