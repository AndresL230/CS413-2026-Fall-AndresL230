"""Required test 9: HTTP client flow over a real socket, from open through all
92 solution events to done, with limit 32."""

import json
import threading
import urllib.request

import pytest
from werkzeug.serving import make_server

from queens.transport import create_app
from reference import brute_force_solutions


@pytest.fixture
def live_url():
    app = create_app()
    server = make_server("127.0.0.1", 0, app, threaded=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        thread.join()


def post(url, method, params, request_id):
    payload = {"jsonrpc": "2.0", "id": request_id, "method": method, "params": params}
    req = urllib.request.Request(
        url + "/rpc", data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=30) as resp:
        assert resp.status == 200
        assert resp.headers.get_content_type() == "application/json"
        body = json.loads(resp.read())
    assert body["id"] == request_id and "result" in body, body
    return body["result"]


def test_http_8x8_open_through_92_solutions_to_done(live_url, trace8):
    assert post(live_url, "service.health", {}, 0) == {"status": "ok", "version": "1.0"}
    opened = post(live_url, "queens.open", {"size": 8}, 1)
    assert opened["size"] == 8
    stream_id = opened["stream_id"]

    events, calls, request_id = [], 0, 2
    while True:
        result = post(live_url, "queens.next", {"stream_id": stream_id, "limit": 32}, request_id)
        request_id += 1
        calls += 1
        assert 1 <= len(result["events"]) <= 32
        events.extend(result["events"])
        if result["done"]:
            break
        assert {"event": "done"} not in result["events"]

    solutions = [e["board"] for e in events if e["event"] == "solution"]
    assert len(solutions) == 92 and solutions == brute_force_solutions(8)
    assert events[-1] == {"event": "done"} and events.count({"event": "done"}) == 1
    assert events == trace8.events          # identical to the in-process trace
    assert calls == -(-33589 // 32)          # ceil(33,589 / 32) = 1,050 requests

    assert post(live_url, "queens.next", {"stream_id": stream_id, "limit": 32}, request_id) == {
        "events": [], "done": True}
    assert post(live_url, "queens.close", {"stream_id": stream_id}, request_id + 1) == {"closed": True}
