"""Prueba de punta a punta de Tempo (web/app) en Firefox real con Playwright.

    python server.py --port 8830 &
    uv run --no-project --with playwright python -m playwright install firefox
    uv run --no-project --with playwright python tests/e2e/e2e_web.py http://127.0.0.1:8830 ["lat, lon"]

El segundo argumento opcional lanza un análisis nuevo real (necesita Earth Engine y red).
"""
import os
import re
import sys
import tempfile
import time

from playwright.sync_api import sync_playwright, expect

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8830"
NEW_POINT = sys.argv[2] if len(sys.argv) > 2 else None   # "lat, lon" para un análisis nuevo real
OUT = os.environ.get("TEMPO_E2E_OUT", tempfile.gettempdir())  # capturas de la prueba
results, errors = [], []


def check(name, fn):
    t = time.time()
    try:
        fn()
        results.append(("OK", name, round(time.time() - t, 1), ""))
    except Exception as e:  # noqa: BLE001
        results.append(("FALLA", name, round(time.time() - t, 1), str(e).splitlines()[0][:220]))


with sync_playwright() as p:
    b = p.firefox.launch()
    ctx = b.new_context(viewport={"width": 1440, "height": 900}, locale="es-ES")
    page = ctx.new_page()
    page.on("console", lambda m: errors.append(f"console.{m.type}: {m.text}") if m.type == "error" else None)
    page.on("pageerror", lambda e: errors.append(f"pageerror: {e}"))
    expect.set_options(timeout=20000)

    def t01():
        page.goto(f"{BASE}/app/")
        expect(page.locator("#intro")).to_be_visible()
        expect(page.locator("#intro h1")).to_contain_text("postrera")
        assert page.locator("link[rel=icon]").get_attribute("href") == "icon.svg"
    check("01 carga inicial: intro visible, ícono", t01)

    def t02():
        page.click("#btn-intro-demo")
        expect(page.locator("#result .verdict h1")).to_be_visible()
        expect(page.locator("#result .conf-badge")).to_be_visible()
        expect(page.locator("#result .data-line").first).to_contain_text("Datos de lluvia hasta")
        expect(page.locator("#result table.basis tbody tr")).to_have_count(6)
        assert "job=c994b1f9c85a940e" in page.url, page.url
    check("02 ejemplo: recomendación, confianza, fecha de datos, 6 escenarios, URL", t02)

    def t03():
        expect(page.locator("#result .season li")).to_have_count(3)
        expect(page.locator("#result .season")).to_contain_text("Ciclo terminado")
    check("03 bloque 'Así va la postrera 2026'", t03)

    def t04():
        page.go_back()
        expect(page.locator("#intro")).to_be_visible()
        assert "job=" not in page.url, page.url
        page.go_forward()
        expect(page.locator("#result .verdict h1")).to_be_visible()
    check("04 botón atrás y adelante del navegador", t04)

    def t05():
        page.click(".chip-btn[data-site=nacaome]")
        expect(page.locator("#result .place")).to_contain_text("Nacaome")
        expect(page.locator("#result .conf-badge")).to_contain_text("media")
        expect(page.locator("#result .planted-note")).to_contain_text("planificar la siembra 2027")
        expect(page.locator("#result .rain-unc")).to_contain_text("IMERG")
        expect(page.locator("#result .val")).to_contain_text("sin la regla")
        assert "CHECK 1" not in page.locator("#result").inner_text()
        page.locator("#panel").screenshot(path="/tmp/claude-1000/-home-damian-Proyectos-tempo/fcf678ef-b378-4ffb-8e04-074f11385536/scratchpad/e2e-nacaome-panel.png")
        assert "job=63e1cac4e49c6a6c" in page.url
    check("05 chip Nacaome: confianza media, aviso 2027, incertidumbre, prueba histórica, sin jerga", t05)

    def t06():
        box = page.locator("#map").bounding_box()
        page.mouse.click(box["x"] + 300, box["y"] + 450)
        expect(page.locator(".confirm-pop")).to_be_visible()
        expect(page.locator("#result")).to_be_visible()     # el resultado sigue ahí
        page.click(".confirm-pop button.primary")
        expect(page.locator("#pick")).to_be_visible()
    check("06 toque en mapa con resultado abierto pide confirmación", t06)

    def t07():
        page.click("#pick [data-cancel-pick]")
        expect(page.locator("#intro")).to_be_visible()
        page.fill("#coords-in", "10, -80")
        page.click("#coords-form button[type=submit]")
        expect(page.locator("#pick-error")).to_be_visible()
        assert page.locator("#go").is_disabled()
        page.click("#pick [data-cancel-pick]")
        page.fill("#coords-in", "hola")
        page.click("#coords-form button[type=submit]")
        expect(page.locator("#coords-error")).to_be_visible()
    check("07 coordenadas fuera de zona e inválidas", t07)

    def t08():
        page.fill("#coords-in", "13.5306, -87.4870")
        page.click("#coords-form button[type=submit]")
        expect(page.locator("#pick")).to_be_visible()
        page.click("#go")
        expect(page.locator("#result .verdict h1")).to_be_visible()
        expect(page.locator("#result")).to_contain_text("Ya estaba analizado")
    check("08 coordenadas de un punto ya analizado: resultado al instante", t08)

    def t09():
        page.click("#result [data-share]")
        expect(page.locator(".toast")).to_be_visible()
    check("09 Compartir muestra aviso", t09)

    def t10():
        page.click("#tab-lista")
        expect(page.locator("#jobs li.job")).to_have_count(page.locator("#jobs li.job").count())
        n = page.locator("#jobs li.job").count()
        assert n >= 9, n
        page.locator("#jobs .job-check").nth(0).check()
        page.locator("#jobs .job-check").nth(1).check()
        expect(page.locator("#compare-bar")).to_be_visible()
        page.click("#btn-compare")
        expect(page.locator(".compare-table thead th")).to_have_count(3)
        expect(page.locator(".compare-table")).to_contain_text("Confianza")
    check("10 guardados (>=9) y comparación de 2", t10)

    def t11():
        page.click("#btn-lang")
        expect(page.locator("#tab-lista")).to_contain_text("Saved")
        page.click("#tab-punto")
        expect(page.locator("#result .verdict-kind")).to_contain_text("to plan 2027")
        expect(page.locator("#result .conf-badge")).to_contain_text("confidence")
        page.click("#btn-lang")
        expect(page.locator("#tab-lista")).to_contain_text("Guardados")
    check("11 idioma inglés y vuelta", t11)

    def t12():
        page.click("#btn-metodo")
        expect(page.locator("#modal-metodo")).to_be_visible()
        expect(page.locator("#modal-body")).to_contain_text("prueba de honestidad")
        page.keyboard.press("Escape")
        expect(page.locator("#modal-metodo")).to_be_hidden()
    check("12 modal 'Cómo funciona' abre y cierra con Escape", t12)

    def t13():
        page.click("#result [data-home]")
        page.fill("#q", "Santa Rosa de Lima")
        page.press("#q", "Enter")
        expect(page.locator("#pick")).to_be_visible()
    check("13 buscador de lugares registrados", t13)

    def t14():
        page.goto(f"{BASE}/app/?job=noexiste000000")
        expect(page.locator(".toast")).to_be_visible()
        expect(page.locator("#intro")).to_be_visible()
    check("14 enlace a un análisis inexistente vuelve al inicio con aviso", t14)

    def t15():
        m = b.new_context(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True)
        mp = m.new_page()
        mp.on("pageerror", lambda e: errors.append(f"mobile pageerror: {e}"))
        mp.goto(f"{BASE}/app/?job=44c5015f05bd7873")
        expect(mp.locator("#result .verdict h1")).to_be_visible()
        assert mp.locator("#panel").get_attribute("data-size") == "full"
        sw = mp.evaluate("document.documentElement.scrollWidth")
        assert sw <= 390, f"scroll horizontal: {sw}px"
        expect(mp.locator("#result .result-actions")).to_be_visible()
        mp.screenshot(path=f"{OUT}/e2e-mobile.png")
        m.close()
    check("15 móvil: resultado a pantalla completa, sin scroll horizontal", t15)

    if NEW_POINT:
        def t16():
            page.goto(f"{BASE}/app/")
            page.fill("#coords-in", NEW_POINT)
            page.click("#coords-form button[type=submit]")
            page.fill("#pick-name", "Prueba E2E")
            page.click("#go")
            expect(page.locator("#progress")).to_be_visible()
            expect(page.locator("#result .verdict h1")).to_be_visible(timeout=900_000)
            expect(page.locator("#result .conf-badge")).to_be_visible()
            page.screenshot(path=f"{OUT}/e2e-new.png", full_page=True)
        check(f"16 análisis NUEVO real de punta a punta ({NEW_POINT})", t16)

    b.close()

for r in results:
    print(f"{r[0]:6} {r[2]:>6}s  {r[1]}" + (f"\n         -> {r[3]}" if r[3] else ""))
print(f"\n{sum(r[0] == 'OK' for r in results)}/{len(results)} OK")
print("Errores de consola/página:", len(errors))
for e in errors[:15]:
    print("  ", e[:200])
