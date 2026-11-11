import pytest

NONEMPTY = {"param": "source", "reason": "source must be a nonempty string"}


@pytest.mark.parametrize("method", ["lambda.typecheck", "lambda.interpret", "lambda.compile"])
@pytest.mark.parametrize(
    "source", [12, None, True, ["1"], {"a": 1}, "", "   ", "\n\t "],
    ids=["int", "null", "bool", "array", "object", "empty", "spaces", "whitespace"],
)
def test_source_wrong_type_or_blank_is_invalid_params(rpc, method, source):
    params = {"source": source}
    if method == "lambda.compile":
        params["target"] = "python"
    err = rpc.err(method, params, -32602, "bad")
    assert err["message"] == "Invalid params"
    assert err["data"] == NONEMPTY


@pytest.mark.parametrize("method", ["lambda.typecheck", "lambda.interpret", "lambda.compile"])
def test_missing_source_is_invalid_params(rpc, method):
    params = {"target": "python"} if method == "lambda.compile" else {}
    err = rpc.err(method, params, -32602)
    assert err["data"] == {"param": "source", "reason": "missing required parameter"}


def test_unknown_param_key_is_rejected(rpc):
    err = rpc.err("lambda.interpret", {"source": "1", "extra": 1}, -32602, "x")
    assert err["data"] == {"param": "extra", "reason": "unknown parameter"}


def test_typecheck_rejects_target_param(rpc):
    err = rpc.err("lambda.typecheck", {"source": "1", "target": "python"}, -32602)
    assert err["data"] == {"param": "target", "reason": "unknown parameter"}


@pytest.mark.parametrize("target", ["ruby", "Python", "", None, 3, ["python"]])
def test_bad_target_is_invalid_params(rpc, target):
    err = rpc.err("lambda.compile", {"source": "1 + 2", "target": target}, -32602, "t")
    assert err["data"] == {"param": "target", "reason": 'target must be "python" or "javascript"'}


def test_missing_target_is_invalid_params(rpc):
    err = rpc.err("lambda.compile", {"source": "1 + 2"}, -32602)
    assert err["data"] == {"param": "target", "reason": "missing required parameter"}


def test_oversized_source_counts_code_points_not_bytes(rpc):
    ok = rpc.ok("lambda.typecheck", {"source": "1 # " + "é" * 100 + " " * 100})
    assert ok == {"type": "sint"}
    err = rpc.err("lambda.typecheck", {"source": "é" * 32769}, -32602)
    assert err["data"]["actual"] == 32769 and err["data"]["limit"] == 32768
