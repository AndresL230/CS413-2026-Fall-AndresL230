import pytest

FIB30 = "let fib : sint -> sint = fix fib(n: sint): sint => if n < 2 then n else fib(n - 1) + fib(n - 2) in fib(30) end"
LOOP = "let f : sint -> sint = fix f(n: sint): sint => f(n + 1) in f(0) end"


def test_division_by_zero_is_runtime_error(rpc):
    err = rpc.err("lambda.interpret", {"source": "1 / 0"}, -32013, "div")
    assert err["message"] == "LAMBDA runtime error: division by zero"
    assert err["data"] == {"kind": "division_by_zero", "detail": "division by zero"}


def test_head_of_empty_list_is_invalid_operation(rpc):
    source = "let xs : List[sint] = list_nil() in list_head(xs) end"
    err = rpc.err("lambda.interpret", {"source": source}, -32013, "head")
    assert err["data"] == {
        "kind": "invalid_operation",
        "detail": "list_head: nonempty list expected",
    }


def test_unbounded_recursion_is_recursion_depth_exceeded_not_timeout(rpc):
    err = rpc.err("lambda.interpret", {"source": LOOP}, -32013, "loop")
    assert err["data"] == {
        "kind": "recursion_depth_exceeded",
        "detail": "recursion depth limit exceeded",
    }


def test_slow_program_times_out_with_configured_seconds(rpc_for):
    client = rpc_for({"INTERPRET_DEADLINE_SECONDS": 1.0})
    err = client.err("lambda.interpret", {"source": FIB30}, -32012, "slow")
    assert err["message"] == "Interpretation timed out"
    assert err["data"] == {"seconds": 1}


def test_timeout_leaves_server_usable(rpc_for):
    client = rpc_for({"INTERPRET_DEADLINE_SECONDS": 1.0})
    client.err("lambda.interpret", {"source": FIB30}, -32012, "slow")
    assert client.ok("lambda.interpret", {"source": "6 * 7"}, "after") == {
        "type": "sint",
        "value": "42",
    }


def test_oversized_source_rejected_with_limit_and_actual(rpc):
    err = rpc.err("lambda.typecheck", {"source": "1" * 32769}, -32602, "big")
    assert err["data"] == {
        "param": "source",
        "reason": "source exceeds maximum size",
        "limit": 32768,
        "actual": 32769,
    }


@pytest.mark.parametrize("method", ["lambda.typecheck", "lambda.interpret", "lambda.compile"])
def test_deeply_nested_source_is_invalid_params_not_internal(rpc, method):
    source = "(" * 1000 + "1" + ")" * 1000
    params = {"source": source}
    if method == "lambda.compile":
        params["target"] = "python"
    err = rpc.err(method, params, -32602, "deep")
    assert err["data"] == {"param": "source", "reason": "source nesting too deep"}


def test_long_operator_chain_is_nesting_error(rpc):
    source = "1" + " + 1" * 3000
    err = rpc.err("lambda.typecheck", {"source": source}, -32602)
    assert err["data"]["reason"] == "source nesting too deep"
