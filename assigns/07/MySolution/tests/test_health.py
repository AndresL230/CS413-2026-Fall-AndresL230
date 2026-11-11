import pytest


def test_health_returns_status_and_version(rpc):
    assert rpc.ok("service.health", {}, "health-1") == {"status": "ok", "version": "1.0"}


@pytest.mark.parametrize("request_id", ["health-1", 17, 0, -3, 1.5, None])
def test_health_preserves_request_id_and_type(rpc, request_id):
    body = rpc.call("service.health", {}, request_id)
    assert body["result"] == {"status": "ok", "version": "1.0"}


def test_health_absent_params_is_accepted(rpc):
    assert rpc.ok("service.health", None, 2) == {"status": "ok", "version": "1.0"}


def test_health_rejects_unknown_params(rpc):
    err = rpc.err("service.health", {"x": 1}, -32602)
    assert err["data"] == {"param": "x", "reason": "unknown parameter"}
