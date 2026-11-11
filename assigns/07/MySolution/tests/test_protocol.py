import pytest


def test_malformed_json_is_parse_error_with_null_id(rpc):
    status, body = rpc.post_json(raw=b'{"jsonrpc":')
    assert status == 200
    assert body == {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "Parse error"}}


def test_non_utf8_body_is_parse_error(rpc):
    status, body = rpc.post_json(raw=b'{"jsonrpc": "2.0", "method": "\xff\xfe"}')
    assert status == 200
    assert body["id"] is None and body["error"]["code"] == -32700
    assert "data" not in body["error"]


def test_deeply_nested_json_is_parse_error_not_500(rpc):
    status, body = rpc.post_json(raw=b"[" * 100000 + b"]" * 100000)
    assert status == 200
    assert body["error"]["code"] == -32700


def test_nan_constant_is_parse_error(rpc):
    status, body = rpc.post_json(raw=b'{"jsonrpc":"2.0","method":"service.health","id":NaN}')
    assert status == 200 and body["error"]["code"] == -32700


@pytest.mark.parametrize(
    "payload, reason",
    [
        ({"jsonrpc": "1.0", "method": "service.health", "id": 1}, 'jsonrpc must be "2.0"'),
        ({"method": "service.health", "id": 1}, 'jsonrpc must be "2.0"'),
        ({"jsonrpc": "2.0", "method": 42, "id": 9}, "method must be a string"),
        ({"jsonrpc": "2.0", "id": 9}, "method must be a string"),
        ({"jsonrpc": "2.0", "method": "service.health", "id": True}, "id must be a string, number, or null"),
        ({"jsonrpc": "2.0", "method": "service.health", "id": [1]}, "id must be a string, number, or null"),
        ({"jsonrpc": "2.0", "method": "service.health", "params": "x", "id": 1}, "params must be an object"),
        ({"jsonrpc": "2.0", "method": "service.health", "params": 5, "id": 1}, "params must be an object"),
        ({"jsonrpc": "2.0", "method": "service.health", "id": 1, "extra": 1}, "unexpected member in request"),
        ("just a string", "request must be an object"),
        (42, "request must be an object"),
        (None, "request must be an object"),
    ],
    ids=[
        "wrong_version_with_id", "missing_jsonrpc", "method_not_string", "method_missing",
        "boolean_id", "array_id", "params_string", "params_number", "extra_member",
        "string_request", "number_request", "null_request",
    ],
)
def test_invalid_envelope_gets_invalid_request_with_null_id(rpc, payload, reason):
    err = rpc.raw_error(payload, -32600)
    assert err["message"] == "Invalid Request"
    assert err["data"] == {"reason": reason}


def test_unknown_method_preserves_id_and_reports_method(rpc):
    err = rpc.err("does.not.exist", {}, -32601, "unknown")
    assert err == {"code": -32601, "message": "Method not found", "data": {"method": "does.not.exist"}}


def test_unknown_method_name_is_truncated_to_128_chars(rpc):
    err = rpc.err("m" * 500, {}, -32601)
    assert err["data"]["method"] == "m" * 128


def test_method_names_are_case_sensitive(rpc):
    rpc.err("Service.Health", {}, -32601)


def test_array_params_rejected_with_invalid_params_and_id_kept(rpc):
    err = rpc.err("lambda.typecheck", ["1 + 2"], -32602, "pos")
    assert err["data"] == {"reason": "params must be an object"}


def test_absent_params_on_interpret_is_missing_source(rpc):
    err = rpc.err("lambda.interpret", None, -32602, "np")
    assert err["data"] == {"param": "source", "reason": "missing required parameter"}


def test_null_params_is_invalid_request(rpc):
    err = rpc.raw_error(
        {"jsonrpc": "2.0", "method": "lambda.interpret", "params": None, "id": 1}, -32600
    )
    assert err["data"]["reason"] == "params must be an object"


def test_validation_precedes_method_lookup_for_bad_envelope(rpc):
    err = rpc.raw_error({"jsonrpc": "2.0", "method": "nope", "id": 1, "x": 2}, -32600)
    assert err["data"]["reason"] == "unexpected member in request"
