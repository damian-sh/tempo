"""Servidor local: validación de rango, id y caché por punto, cola, estados y persistencia."""
import json
import os
import sys
import threading
import time
import urllib.error
import urllib.request

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import server  # noqa: E402

PARCELA = (13.796406, -89.801031)


def fake_result(estado="listo", faltantes=()):
    return {"estado": estado, "mensaje": f"prueba {estado}", "faltantes": list(faltantes),
            "veredicto": {"claro": False, "titulo": "Ninguna opción es claramente mejor", "anio": 2026},
            "resultado": {"resumen": {"anio": 2026}, "analisis": {}}}


class Recorder:
    """Procesador falso: registra llamadas y puede bloquearse para observar 'procesando'."""

    def __init__(self, out=None, gate=None):
        self.calls, self.out, self.gate = [], out or fake_result(), gate
        self.running = threading.Event()

    def __call__(self, rec, store, progress):
        self.calls.append(rec["id"])
        progress("paso de prueba", 0.5)
        self.running.set()
        if self.gate:
            assert self.gate.wait(5)
        return self.out


@pytest.fixture
def store(tmp_path):
    return server.JobStore(str(tmp_path / "jobs"))


def wait_for(cond, timeout=5.0):
    t0 = time.time()
    while time.time() - t0 < timeout:
        if cond():
            return True
        time.sleep(0.02)
    return False


# ---------------------------------------------------------------- validación e id
@pytest.mark.parametrize("body", [
    {"lat": 11.9, "lon": -89.0}, {"lat": 15.1, "lon": -89.0}, {"lat": 13.5, "lon": -90.6},
    {"lat": 13.5, "lon": -86.9}, {"lat": 13.48371, "lon": -86.582623},  # Somoto: fuera
    {"lat": "x", "lon": -89}, {"lon": -89}, [], {"lat": float("nan"), "lon": -89},
])
def test_validate_rejects_out_of_range_or_bad(body):
    point, err = server.validate_point(body)
    assert point is None and err


@pytest.mark.parametrize("lat,lon", [(12, -90.5), (15, -87), PARCELA, (13.30, -87.19)])
def test_validate_accepts_range_edges(lat, lon):
    point, err = server.validate_point({"lat": lat, "lon": lon, "nombre": "  Mi parcela  "})
    assert err is None and point["nombre"] == "Mi parcela"


def test_job_id_rounds_to_6_decimals():
    a = server.job_id(*PARCELA)
    assert a == server.job_id(13.7964061, -89.8010312)
    assert a != server.job_id(13.796407, -89.801031)
    assert len(a) == 16 and int(a, 16) >= 0


# ---------------------------------------------------------------- cola y estados
def test_queue_states_and_cache_per_point(store):
    gate = threading.Event()
    proc = Recorder(gate=gate)
    q = server.JobQueue(store, proc).start()
    try:
        rec, cached = q.submit({"lat": PARCELA[0], "lon": PARCELA[1], "nombre": "P"})
        assert not cached and rec["estado"] == "en_cola"
        assert proc.running.wait(5)
        assert store.get(rec["id"])["estado"] == "procesando"
        assert store.get(rec["id"])["mensaje"] == "paso de prueba"
        # Mismo punto mientras procesa: no se encola dos veces.
        again, cached = q.submit({"lat": PARCELA[0], "lon": PARCELA[1]})
        assert again["id"] == rec["id"] and not cached
        gate.set()
        assert wait_for(lambda: store.get(rec["id"])["estado"] == "listo")
        assert os.path.exists(store.result_path(rec["id"]))
        # Ya analizado: se devuelve desde caché, sin llamar al procesador otra vez.
        hit, cached = q.submit({"lat": PARCELA[0] + 1e-8, "lon": PARCELA[1]})
        assert cached and hit["estado"] == "listo"
        time.sleep(0.1)
        assert proc.calls == [rec["id"]]
    finally:
        q.stop()


def test_one_job_at_a_time_in_order(store):
    active, peak, order = [0], [0], []
    lock = threading.Lock()

    def proc(rec, st, progress):
        with lock:
            active[0] += 1
            peak[0] = max(peak[0], active[0])
        order.append(rec["id"])
        time.sleep(0.05)
        with lock:
            active[0] -= 1
        return fake_result()

    q = server.JobQueue(store, proc).start()
    try:
        ids = [q.submit({"lat": 13.0 + i / 10, "lon": -89.0})[0]["id"] for i in range(3)]
        assert store.get(ids[2])["estado"] == "en_cola"
        assert wait_for(lambda: all(store.get(i)["estado"] == "listo" for i in ids))
        assert peak[0] == 1 and order == ids
    finally:
        q.stop()


def test_parcial_keeps_faltantes_and_error_is_retried(store):
    q = server.JobQueue(store, Recorder(out=fake_result("parcial", ["IMERG (lluvia satelital): sin dato"])))
    rec, _ = q.submit({"lat": 13.5, "lon": -88.5})
    done = q.run_one(rec["id"])
    assert done["estado"] == "parcial" and done["faltantes"] == ["IMERG (lluvia satelital): sin dato"]

    def boom(rec, st, progress):
        raise RuntimeError("sin red")
    q2 = server.JobQueue(store, boom)
    rec, _ = q2.submit({"lat": 13.6, "lon": -88.5})
    done = q2.run_one(rec["id"])
    assert done["estado"] == "error" and "sin red" in done["mensaje"]
    assert not os.path.exists(store.result_path(rec["id"]))
    again, cached = q2.submit({"lat": 13.6, "lon": -88.5})  # error: se vuelve a encolar
    assert not cached and again["estado"] == "en_cola" and again["intentos"] == 2


def test_queue_survives_restart(store, tmp_path):
    q = server.JobQueue(store, Recorder())  # sin worker: queda en cola en disco
    a, _ = q.submit({"lat": 13.1, "lon": -89.1})
    b, _ = q.submit({"lat": 13.2, "lon": -89.2})
    store.update(b["id"], estado="procesando")  # se cortó a mitad
    proc = Recorder()
    store2 = server.JobStore(store.root)
    q2 = server.JobQueue(store2, proc).start()
    try:
        assert wait_for(lambda: all(store2.get(i)["estado"] == "listo" for i in (a["id"], b["id"])))
        assert sorted(proc.calls) == sorted([a["id"], b["id"]])
    finally:
        q2.stop()
    with open(store.path(a["id"])) as f:
        assert json.load(f)["estado"] == "listo"


# ---------------------------------------------------------------- worker real sin red
class FakeFetch:
    POWER_PARAMS = ["T2M"]

    def __init__(self, power_fails=False):
        self.power_fails = power_fails

    def _end_date(self):
        return "2026-11-13"

    def fetch_power(self, lat, lon, start, end):
        if self.power_fails:
            raise RuntimeError("POWER caído")
        import pandas as pd
        df = pd.DataFrame({"PRECTOTCORR": [1.0, 2.0]}, index=pd.to_datetime(["2001-01-01", "2001-01-02"]))
        df.index.name = "date"
        return df, 600.0

    def power_precip_json(self, power):
        return {"values": [1.0, 2.0]}

    def fetch_soilgrids(self, lat, lon):
        raise RuntimeError("SoilGrids caído")

    def texture_class(self, c, s):
        return None


class FakeEngine:
    DEFAULT_WEIGHTS = {}

    def __init__(self):
        self.zones = []

    def build_zone(self, zone, weights, seeds, rain_source):
        self.zones.append(zone)
        return {"zone": zone.__dict__}

    def clean_json(self, x):
        return x


def test_worker_marks_missing_sources_without_inventing(store, monkeypatch):
    monkeypatch.setattr(server, "registered_cache", lambda lat, lon: None)
    monkeypatch.setattr(server, "summarize", lambda out, f: {"anio": 2026, "veredicto": {"claro": False, "titulo": "t"}})
    eng = FakeEngine()
    rec = {"id": server.job_id(13.5, -88.5), "lat": 13.5, "lon": -88.5}
    out = server.process_point(rec, store, lambda *a: None, fetch_mod=FakeFetch(),
                               gee=lambda: (False, "TEMPO_GEE_PROJECT no está definido"), engine_mod=eng)
    assert out["estado"] == "parcial"
    joined = " ".join(out["faltantes"])
    assert "IMERG" in joined and "SRTM" in joined and "SoilGrids" in joined
    d = store.data_dir(rec["id"])
    assert not os.path.exists(os.path.join(d, "imerg.csv"))
    with open(os.path.join(d, "terrain.json")) as f:
        assert json.load(f)["elevation_m"] is None
    assert eng.zones[0].key == os.path.relpath(d, server.config.CACHE_DIR)


def test_worker_error_when_power_fails(store, monkeypatch):
    monkeypatch.setattr(server, "registered_cache", lambda lat, lon: None)
    eng = FakeEngine()
    rec = {"id": server.job_id(13.4, -88.4), "lat": 13.4, "lon": -88.4}
    out = server.process_point(rec, store, lambda *a: None, fetch_mod=FakeFetch(power_fails=True),
                               gee=lambda: (False, "sin GEE"), engine_mod=eng)
    assert out["estado"] == "error" and "POWER" in out["mensaje"] and not eng.zones


# ---------------------------------------------------------------- HTTP
@pytest.fixture
def http(store):
    httpd, st, q = server.make_server("127.0.0.1", 0, store=store, processor=Recorder())
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    base = f"http://127.0.0.1:{httpd.server_address[1]}"
    yield base, st
    httpd.shutdown()
    httpd.server_close()
    q.stop()


def call(base, path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(base + path, data=data, headers={"Content-Type": "application/json"},
                                 method="POST" if data is not None else "GET")
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


def test_http_flow(http):
    base, st = http
    code, body = call(base, "/api/jobs", {"lat": 16.0, "lon": -89.0})
    assert code == 400 and "fuera" in body["error"]
    code, body = call(base, "/api/jobs", {"lat": PARCELA[0], "lon": PARCELA[1]})
    assert code == 202 and body["cache"] is False and body["estado"] in ("en_cola", "procesando", "listo")
    jid = body["id"]
    assert wait_for(lambda: call(base, f"/api/jobs/{jid}")[1]["estado"] == "listo")
    code, res = call(base, f"/api/jobs/{jid}/result")
    assert code == 200 and res["resumen"]["anio"] == 2026
    code, body = call(base, "/api/jobs", {"lat": PARCELA[0], "lon": PARCELA[1]})
    assert code == 200 and body["cache"] is True and body["estado"] == "listo"
    code, lst = call(base, "/api/jobs")
    assert [j["id"] for j in lst["jobs"]] == [jid] and "resultado" not in lst["jobs"][0]
    assert call(base, "/api/jobs/0123456789abcdef")[0] == 404
    assert call(base, "/api/jobs/../../etc")[0] == 404


def test_http_result_not_ready(store):
    q = server.JobQueue(store, Recorder())
    rec, _ = q.submit({"lat": 13.0, "lon": -89.0})
    httpd, _, q2 = server.make_server("127.0.0.1", 0, store=store, processor=Recorder(), start_worker=False)
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    try:
        base = f"http://127.0.0.1:{httpd.server_address[1]}"
        code, body = call(base, f"/api/jobs/{rec['id']}/result")
        assert code == 409 and body["estado"] == "en_cola"
        code, body = call(base, f"/api/jobs/{rec['id']}")
        assert body["posicion"] == 1
    finally:
        httpd.shutdown()
        httpd.server_close()
