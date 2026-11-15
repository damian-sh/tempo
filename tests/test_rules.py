"""Repository rules: no forbidden data sources, no literal secrets, no cache JSON in git."""
import os
import re
import subprocess

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SELF = os.path.relpath(os.path.abspath(__file__), ROOT)

FORBIDDEN_SOURCES = re.compile(
    r"\b(GLDAS|GAEZ|SMAP|ERA5|Sentinel[-_ ]?2|Landsat|ECOSTRESS|GEDI)\b", re.IGNORECASE)
SOURCES_ALLOWED_IN = {"README.md", "DECISIONES.md", SELF}
SECRET_PREFIXES = ("cog_", "4/1A")
ALLOWED_JSON = {"crops.json", "parcelas.json"}  # parcelas.json es registro de sitios, no caché
DEMO_DIR = "web/app/demo/"  # instantánea de demo versionada a propósito (export_demo.py)
CACHE_DIRS = ("cache/", "out/")


def repo_files():
    out = subprocess.run(["git", "ls-files", "--cached", "--others", "--exclude-standard"],
                         cwd=ROOT, check=True, capture_output=True, text=True).stdout
    return [f for f in out.splitlines() if os.path.isfile(os.path.join(ROOT, f))]


def read(f):
    with open(os.path.join(ROOT, f), encoding="utf-8", errors="ignore") as fh:
        return fh.read()


def test_no_forbidden_sources():
    hits = [(f, m.group(0)) for f in repo_files() if f not in SOURCES_ALLOWED_IN
            for m in FORBIDDEN_SOURCES.finditer(read(f))]
    assert not hits, f"forbidden sources outside README/DECISIONES: {hits}"


def test_no_literal_secrets():
    hits = [(f, p) for f in repo_files() if f != SELF for p in SECRET_PREFIXES if p in read(f)]
    assert not hits, f"literal secret prefixes found: {hits}"


def test_no_cache_json_in_git():
    tracked = subprocess.run(["git", "ls-files"], cwd=ROOT, check=True,
                             capture_output=True, text=True).stdout.splitlines()
    bad = [f for f in tracked if f.startswith(CACHE_DIRS)
           or (f.endswith(".json") and f not in ALLOWED_JSON and not f.startswith(DEMO_DIR))]
    assert not bad, f"cache/output JSON tracked in git: {bad}"
