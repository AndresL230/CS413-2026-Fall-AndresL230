"""Required test 7: JSON-RPC ids, malformed envelopes, unknown methods,
invalid params, notifications, application errors, and HTTP framing."""

import json

import pytest

from queens.errors import (INVALID_PARAMS, INVALID_REQUEST, METHOD_NOT_FOUND,
                           PARSE_ERROR, UNKNOWN_STREAM)
from rpchelpers import check_envelope


def test_health(rpc):
    assert rpc.ok("service.health", {}) == {"status": "ok", "version": "1.0"}
    assert rpc.ok("service.health") == {"status": "ok", "version": "1.0"}  # params omitted


@pytest.mark.parametrize("request_id", [7, "abc", "", 0, -3, 2.5, None])
def test_request_ids_preserved_with_type(rpc, request_id):
    body = rpc.call("service.health", {}, request_id)
    assert "result" in body
    body = rpc.call("queens.open", {"size": 99}, request_id)  # errors too
    assert body["error"]["code"] == INVALID_PARAMS


# ---- Malformed envelopes ---------------------------------------------------------

def test_body_not_json_is_parse_error(rpc):
    rpc.raw_error(raw=b'{"jsonrpc": "2.0", "method": ', code=PARSE_ERROR)
    rpc.raw_error(raw=b"\xff\xfe", code=PARSE_ERROR)
    rpc.raw_error(raw=b'{"jsonrpc": "2.0", "method": "service.health", "id": NaN}', code=PARSE_ERROR)


@pytest.mark.parametrize("payload", [
    5, "text", None, True,
    {"method": "service.health", "id": 1},                          # no jsonrpc
    {"jsonrpc": "1.0", "method": "service.health", "id": 1},
    {"jsonrpc": 2.0, "method": "service.health", "id": 1},
    {"jsonrpc": "2.0", "id": 1},                                     # no method
    {"jsonrpc": "2.0", "method": 5, "id": 1},
    {"jsonrpc": "2.0", "method": "service.health", "id": True},
    {"jsonrpc": "2.0", "method": "service.health", "id": {"a": 1}},
    {"jsonrpc": "2.0", "method": "service.health", "id": [1]},
    {"jsonrpc": "2.0", "method": "service.health", "params": "x", "id": 1},
    {"jsonrpc": "2.0", "method": "service.health", "params": None, "id": 1},
    {"jsonrpc": "2.0", "method": "service.health", "id": 1, "extra": 0},
    [],                                                              # empty batch
])
def test_malformed_envelopes_are_invalid_request(rpc, payload):
    rpc.raw_error(payload, code=INVALID_REQUEST)


# ---- Methods ----------------------------------------------------------------------

@pytest.mark.parametrize("method", ["queens.solve", "lambda.interpret", "QUEENS.OPEN", "", "x" * 500])
def test_unknown_methods(rpc, method):
    err = rpc.err(method, {}, METHOD_NOT_FOUND)
    assert err["data"] == {"method": method[:128]}


# ---- Parameters ---------------------------------------------------------------------

@pytest.mark.parametrize("size", [True, False, 8.0, 8.5, "8", None, [8], {"n": 8}, 3, 11, 0, -8])
def test_open_bad_size(rpc, size):
    err = rpc.err("queens.open", {"size": size}, INVALID_PARAMS)
    assert err["data"]["param"] == "size"


def test_open_size_bounds_accepted(rpc):
    for size in range(4, 11):
        assert rpc.ok("queens.open", {"size": size})["size"] == size


def test_open_size_float_spelled_in_json(rpc):
    # 8.0 / 8e0 in the JSON text decode to float and are rejected.
    for text in ("8.0", "8e0"):
        raw = ('{"jsonrpc": "2.0", "id": 1, "method": "queens.open", "params": {"size": %s}}' % text).encode()
        status, body = rpc.post_json(raw=raw)
        check_envelope(body, 1)
        assert body["error"]["code"] == INVALID_PARAMS


@pytest.mark.parametrize("limit", [True, False, 0, 33, -1, 1.0, 32.0, "1", None])
def test_next_bad_limit(rpc, limit):
    stream_id = rpc.open(8)
    err = rpc.err("queens.next", {"stream_id": stream_id, "limit": limit}, INVALID_PARAMS)
    assert err["data"]["param"] == "limit"
    assert rpc.next(stream_id, 1)["events"][0]["event"] == "try"  # nothing was forced


@pytest.mark.parametrize("stream_id", [5, None, True, "", "x" * 65, ["id"]])
def test_bad_stream_id_type(rpc, stream_id):
    for method in ("queens.next", "queens.close"):
        err = rpc.err(method, {"stream_id": stream_id}, INVALID_PARAMS)
        assert err["data"]["param"] == "stream_id"


@pytest.mark.parametrize("method,params", [
    ("service.health", {"verbose": True}),
    ("queens.open", {"size": 8, "seed": 1}),
    ("queens.next", {"stream_id": "a", "limit": 1, "offset": 0}),
    ("queens.close", {"stream_id": "a", "force": True}),
])
def test_unknown_parameter_keys(rpc, method, params):
    err = rpc.err(method, params, INVALID_PARAMS)
    assert err["data"]["reason"] == "unknown parameter"


@pytest.mark.parametrize("method,missing", [
    ("queens.open", "size"), ("queens.next", "stream_id"), ("queens.close", "stream_id")])
def test_missing_required_parameters(rpc, method, missing):
    err = rpc.err(method, {}, INVALID_PARAMS)
    assert err["data"] == {"param": missing, "reason": "missing required parameter"}


def test_positional_params_rejected(rpc):
    rpc.err("queens.open", [8], INVALID_PARAMS)


def test_well_formed_unknown_id_is_application_error_not_param_error(rpc):
    err = rpc.err("queens.next", {"stream_id": "not-a-uuid"}, UNKNOWN_STREAM)
    assert err["data"] == {"stream_id": "not-a-uuid"}


# ---- Notifications -----------------------------------------------------------------

def test_notifications_get_204_and_empty_body(rpc, table):
    for note in (rpc.notification("service.health", {}),
                 rpc.notification("queens.open", {"size": 3}),       # invalid params
                 rpc.notification("no.such.method")):
        resp = rpc.post(note)
        assert resp.status_code == 204 and resp.get_data() == b""
    assert len(table) == 0


def test_notification_still_runs_the_method(rpc, table):
    resp = rpc.post(rpc.notification("queens.open", {"size": 8}))
    assert resp.status_code == 204
    assert len(table) == 1


def test_notification_next_advances_stream(rpc):
    stream_id = rpc.open(8)
    resp = rpc.post(rpc.notification("queens.next", {"stream_id": stream_id, "limit": 2}))
    assert resp.status_code == 204
    assert rpc.next(stream_id, 1)["events"] == [
        {"event": "try", "column": 0, "row": 1, "board": [0]}]  # the 3rd event


# ---- HTTP framing -------------------------------------------------------------------

def test_non_json_content_type_is_415(rpc):
    resp = rpc.post(rpc.request("service.health"), content_type="text/plain")
    assert resp.status_code == 415


def test_get_rpc_is_405(rpc):
    resp = rpc.client.get("/rpc")
    assert resp.status_code == 405 and "POST" in resp.headers["Allow"]


def test_oversized_body_is_413(rpc):
    big = json.dumps(rpc.request("service.health", {"pad": "x" * 70_000})).encode()
    assert rpc.post(raw=big).status_code == 413


def test_index_page_served(rpc):
    resp = rpc.client.get("/")
    assert resp.status_code == 200 and b"N-Queens" in resp.get_data()
