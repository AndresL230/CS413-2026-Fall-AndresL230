import pytest

from lambda_rpc import config

lambda3 = config.load_lambda3()

FACT = "let fact : sint -> sint =\n  fix fact(n: sint): sint =>\n    if n <= 1 then 1 else n * fact(n - 1)\nin fact(5) end"


@pytest.mark.parametrize("source", ["1 + 2", FACT, "(1, true)"], ids=["arith", "fact", "tuple"])
@pytest.mark.parametrize("target", ["python", "javascript"])
def test_compile_returns_target_and_code_identical_to_lambda3(rpc, source, target):
    result = rpc.ok("lambda.compile", {"source": source, "target": target}, target)
    assert set(result) == {"target", "code"}
    assert result["target"] == target
    assert isinstance(result["code"], str) and result["code"].strip()
    expr, _ = lambda3.d0exp_parse_and_typecheck(source)
    expected = (
        lambda3.d0exp_compile(expr) if target == "python" else lambda3.d0exp_compile_js(expr)
    )
    assert result["code"] == expected


def test_compile_python_and_javascript_differ(rpc):
    py = rpc.ok("lambda.compile", {"source": "1 + 2", "target": "python"})["code"]
    js = rpc.ok("lambda.compile", {"source": "1 + 2", "target": "javascript"})["code"]
    assert py != js
    assert "def _lambda_main" in py and "function _lambda_main" in js


def test_compile_type_error_is_reported_before_codegen(rpc):
    rpc.err("lambda.compile", {"source": "1 + true", "target": "python"}, -32011)
