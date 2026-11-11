import json

import pytest

HEALTH = {"jsonrpc": "2.0", "method": "service.health", "params": {}, "id": 1}


def assert_plain_non_rpc(resp):
    body = resp.get_data(as_text=True)
    assert resp.mimetype == "text/plain"
    assert body.strip()
    with pytest.raises(ValueError):
        json.loads(body)
    assert "jsonrpc" not in body
    from conftest import assert_no_leak

    assert_no_leak(body)


def test_rpc_success_is_http_200_application_json(rpc):
    resp = rpc.post(HEALTH)
    assert resp.status_code == 200
    assert resp.mimetype == "application/json"


def test_content_type_with_charset_is_accepted(rpc):
    resp = rpc.post(HEALTH, content_type="application/json; charset=utf-8")
    assert resp.status_code == 200


@pytest.mark.parametrize("ctype", ["text/plain", "application/x-www-form-urlencoded", "application/jsonp"])
def test_wrong_content_type_is_415_plain_text(rpc, ctype):
    resp = rpc.post(HEALTH, content_type=ctype)
    assert resp.status_code == 415
    assert_plain_non_rpc(resp)


def test_missing_content_type_is_415(client):
    resp = client.post("/rpc", data=json.dumps(HEALTH))
    assert resp.status_code == 415
    assert_plain_non_rpc(resp)


@pytest.mark.parametrize("verb", ["get", "put", "delete", "patch"])
def test_other_methods_are_405_with_allow_post(client, verb):
    resp = getattr(client, verb)("/rpc")
    assert resp.status_code == 405
    assert resp.headers["Allow"] == "POST"
    assert_plain_non_rpc(resp)


def test_body_over_1_mib_is_413_plain_text(rpc):
    big = b" " * (1048576 + 1)
    resp = rpc.post(raw=big)
    assert resp.status_code == 413
    assert_plain_non_rpc(resp)


def test_body_of_exactly_1_mib_reaches_the_dispatcher(rpc):
    raw = json.dumps(HEALTH).encode().ljust(1048576)
    status, body = rpc.post_json(raw=raw)
    assert status == 200 and body["result"]["status"] == "ok"


@pytest.mark.parametrize("path", ["/", "/rpc/", "/health", "/rpc/extra", "/lambda/typecheck"])
def test_other_paths_are_404_plain_text(client, path):
    resp = client.post(path, json=HEALTH)
    assert resp.status_code == 404
    assert_plain_non_rpc(resp)


def test_notification_is_204_with_empty_body(rpc):
    resp = rpc.post({"jsonrpc": "2.0", "method": "service.health", "params": {}})
    assert resp.status_code == 204
    assert resp.get_data() == b""
