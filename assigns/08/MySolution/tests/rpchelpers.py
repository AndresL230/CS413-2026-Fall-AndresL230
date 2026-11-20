"""JSON-RPC test helpers (adapted from Assign07's conftest)."""

import json

from queens.lambda3_loader import LAMBDA3_DIR

LEAK_MARKERS = ("Traceback", 'File "', ".py", "/home", "0x", str(LAMBDA3_DIR),
                "Error:", "Exception", "D0V", "<lam", "<fix", "<lazy", "object at")


def assert_no_leak(value):
    """No traceback, path, or interpreter/closure repr anywhere in value."""
    text = value if isinstance(value, str) else json.dumps(value)
    for marker in LEAK_MARKERS:
        assert marker not in text, f"leaked {marker!r} in {text[:300]!r}"


def check_envelope(body, request_id):
    """Assert one JSON-RPC response envelope with the given id; return it."""
    assert isinstance(body, dict)
    assert body["jsonrpc"] == "2.0"
    assert "id" in body
    assert body["id"] == request_id and type(body["id"]) is type(request_id)
    assert ("result" in body) != ("error" in body), "exactly one of result/error"
    assert set(body) <= {"jsonrpc", "id", "result", "error"}
    if "error" in body:
        error = body["error"]
        assert set(error) <= {"code", "message", "data"}
        assert isinstance(error["code"], int) and not isinstance(error["code"], bool)
        assert isinstance(error["message"], str)
    assert_no_leak(body)
    return body


class Rpc:
    def __init__(self, client):
        self.client = client

    def post(self, payload=None, raw=None, content_type="application/json"):
        data = raw if raw is not None else json.dumps(payload).encode("utf-8")
        return self.client.post("/rpc", data=data, content_type=content_type)

    def post_json(self, payload=None, raw=None, content_type="application/json"):
        """Return (status, decoded body or None)."""
        resp = self.post(payload, raw, content_type)
        body = resp.get_data()
        return resp.status_code, (json.loads(body) if body else None)

    @staticmethod
    def request(method, params=None, request_id=1):
        req = {"jsonrpc": "2.0", "method": method, "id": request_id}
        if params is not None:
            req["params"] = params
        return req

    @staticmethod
    def notification(method, params=None):
        req = {"jsonrpc": "2.0", "method": method}
        if params is not None:
            req["params"] = params
        return req

    def call(self, method, params=None, request_id=1):
        status, body = self.post_json(self.request(method, params, request_id))
        assert status == 200
        return check_envelope(body, request_id)

    def ok(self, method, params=None, request_id=1):
        body = self.call(method, params, request_id)
        assert "result" in body, body
        return body["result"]

    def err(self, method, params, code, request_id=1):
        body = self.call(method, params, request_id)
        assert "error" in body, body
        assert body["error"]["code"] == code, body
        return body["error"]

    def raw_error(self, payload=None, code=None, raw=None):
        """Post an arbitrary payload; expect one error object with id null."""
        status, body = self.post_json(payload, raw=raw)
        assert status == 200
        check_envelope(body, None)
        assert body["error"]["code"] == code, body
        return body["error"]

    # Convenience wrappers for the queens methods.
    def open(self, size=8):
        return self.ok("queens.open", {"size": size})["stream_id"]

    def next(self, stream_id, limit=1):
        return self.ok("queens.next", {"stream_id": stream_id, "limit": limit})

    def drain(self, stream_id, limit=32):
        """Call next until done; return (events, responses)."""
        events, responses = [], []
        while True:
            result = self.next(stream_id, limit)
            responses.append(result)
            events.extend(result["events"])
            if result["done"]:
                return events, responses


class FakeClock:
    """Injectable monotonic clock for expiry tests."""

    def __init__(self, start=1000.0):
        self.now = start

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds
