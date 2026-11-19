import json
import threading
import time
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

import pytest

from matlab_practice import engine, server
from conftest import reference

pytestmark = pytest.mark.skipif(not engine.find_octave().found, reason="Octave not installed")
PID = "ex-01-mylininterp"


@pytest.fixture
def base(work):
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}"
    httpd.shutdown()


def get(url):
    with urllib.request.urlopen(url, timeout=60) as r:
        return r.status, r.headers.get("Content-Type"), r.read()


def post(url, data):
    req = urllib.request.Request(url, json.dumps(data).encode(), {"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read())


def test_static_and_status(base):
    status, ctype, body = get(base + "/")
    assert status == 200 and "text/html" in ctype and b"<html" in body.lower()
    st = json.loads(get(base + "/api/status")[2])
    assert st["octave"]["found"] and st["claude"]["found"]


def test_path_traversal_blocked(base):
    for bad in ["/../pyproject.toml", "/%2e%2e/pyproject.toml", "/vendor/../../README.md"]:
        try:
            status = get(base + bad)[0]
        except urllib.error.HTTPError as e:
            status = e.code
        assert status == 404, bad


def test_problem_list_and_detail(base):
    items = json.loads(get(base + "/api/problems")[2])
    assert {p["id"] for p in items} >= {PID, "ex-02-basel-terms", "ex-03-sin-cos-plot"}
    d = json.loads(get(base + f"/api/problems/{PID}")[2])
    assert d["file"] == "myLinInterp.m" and d["scratch"] and "interp1" in d["statement_md"]
    assert d["hint_threshold"] == 5


def test_check_endpoint(base):
    r = post(base + f"/api/problems/{PID}/check", {"code": "x = 1;\nx += 1;\n"})
    assert r["issues"] and r["issues"][0]["line"] == 2


def test_submit_and_poll(base):
    sub = post(base + f"/api/problems/{PID}/submit", {"code": reference(PID), "scratch": "Y = 1"})
    assert sub["tests_verdict"] == "accepted" and sub["verdict"] in ("pending", "accepted")
    for _ in range(60):
        full = json.loads(get(base + f"/api/problems/{PID}/submissions/{sub['id']}")[2])
        if full["review"]["status"] != "pending":
            break
        time.sleep(0.5)
    assert full["verdict"] == "accepted" and full["code"] == reference(PID)
    d = json.loads(get(base + f"/api/problems/{PID}")[2])
    assert d["code"] == reference(PID) and d["submissions"][0]["id"] == sub["id"]


def test_bad_requests(base):
    for url, data in [(f"/api/problems/{PID}/submit", {}), ("/api/problems/nope/submit", {"code": ""})]:
        with pytest.raises(urllib.error.HTTPError) as e:
            post(base + url, data)
        assert e.value.code in (400, 404)
