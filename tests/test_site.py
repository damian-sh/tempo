"""Site: ES/EN parity and no winner in the headline unless every verdict condition holds."""
import os
import re
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import build_site  # noqa: E402
from test_checks import load  # noqa: E402


def test_es_en_same_pages_and_rows():
    d = load("parcela")
    es, en = build_site.build_lang(d, "es"), build_site.build_lang(d, "en")
    assert sorted(k.replace(".html", "") for k in es) == sorted(k.replace("-en.html", "") for k in en)
    for k in es:
        e = en[k.replace(".html", "-en.html")]
        for tag in ("<tr>", "<li", "<table", "<h2"):
            assert es[k].count(tag) == e.count(tag), (k, tag)
        assert 'lang="es"' in es[k] and '<html lang="en">' in e
        assert 'hreflang="en"' in es[k] and 'hreflang="es"' in e


def test_headline_neutral_without_all_conditions():
    d = load("parcela")
    clear = all(ok for _, ok in build_site.verdict(d))
    h1 = {lang: re.search(r"<h1>(.*?)</h1>", build_site.build_lang(d, lang)[build_site.fname("index", lang)]).group(1)
          for lang in ("es", "en")}
    if clear:
        pytest.skip("all verdict conditions hold for this output")
    assert h1["es"].startswith("Ninguna opción es claramente mejor")
    assert h1["en"].startswith("No option is clearly better")


def test_verdict_requires_margin():
    d = load("parcela")
    d = {**d, "current": {**d["current"], "margin_over_second": build_site.READ_MARGIN / 2}}
    assert dict(build_site.verdict(d))["margin"] is False
