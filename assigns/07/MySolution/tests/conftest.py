"""Shared fixtures and helpers for the HTTP-level test suite."""

import json
import logging

import pytest

from lambda_rpc import config
from lambda_rpc.transport import create_app

LEAK_MARKERS = ("Traceback", 'File "', ".py", "/home", "0x", str(config.LAMBDA3_DIR))


def assert_no_leak(text):
    """No traceback, path, exception class repr, or object repr in `text`."""
    if not isinstance(text, str):
        text = json.dumps(text)
    for marker in LEAK_MARKERS:
        assert marker not in text, f"leaked {marker!r} in {text[:300]!r}"
    for name in ("Error:", "Exception", "<lambda3", "object at"):
        assert name not in text, f"leaked {name!r} in {text[:300]!r}"


def check_envelope(body, request_id):
    """Assert a single JSON-RPC response envelope; return it."""
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
        assert_no_leak(error)
    return body


class Rpc:
    def __init__(self, client):
        self.client = client

    def post(self, payload=None, raw=None, content_type="application/json"):
        data = raw if raw is not None else json.dumps(payload).encode("utf-8")
        resp = self.client.post("/rpc", data=data, content_type=content_type)
        return resp

    def post_json(self, payload=None, raw=None, content_type="application/json"):
        """Return (status, decoded body or None)."""
        resp = self.post(payload, raw, content_type)
        body = resp.get_data()
        return resp.status_code, (json.loads(body) if body else None)

    def request(self, method, params=None, request_id=1):
        req = {"jsonrpc": "2.0", "method": method, "id": request_id}
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

    def raw_error(self, payload, code, status=200):
        """Post an arbitrary payload; expect one error object with id null."""
        st, body = self.post_json(payload)
        assert st == status
        check_envelope(body, None)
        assert body["error"]["code"] == code
        return body["error"]


@pytest.fixture
def make_app():
    def factory(overrides=None, service=None):
        app = create_app(overrides, service=service)
        app.testing = True
        return app

    return factory


@pytest.fixture
def app(make_app):
    return make_app()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def rpc(client):
    return Rpc(client)


@pytest.fixture
def rpc_for(make_app):
    def factory(overrides=None, service=None):
        return Rpc(make_app(overrides, service).test_client())

    return factory


@pytest.fixture
def check():
    return check_envelope


@pytest.fixture
def no_leak():
    return assert_no_leak


@pytest.fixture
def error_log(caplog):
    with caplog.at_level(logging.ERROR, logger="lambda_rpc"):
        yield caplog
