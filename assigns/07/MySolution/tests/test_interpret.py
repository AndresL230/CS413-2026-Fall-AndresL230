import pytest

FACT6 = "let fact : sint -> sint =\n  fix fact(n: sint): sint =>\n    if n <= 1 then 1 else n * fact(n - 1)\nin fact(6) end"


@pytest.mark.parametrize(
    "source, type_, value",
    [
        ("20 + 22", "sint", "42"),
        (FACT6, "sint", "720"),
        ("(1, true)", "(sint, bool)", "(1, true)"),
        ("list_cons(1, list_cons(2, list_nil()))", "List[sint]", "[1, 2]"),
        ("print(41 + 1)", "unit", "()"),
    ],
    ids=["arithmetic", "factorial", "tuple", "list", "print_returns_unit"],
)
def test_interpret_returns_type_and_formatted_value(rpc, source, type_, value):
    assert rpc.ok("lambda.interpret", {"source": source}, "i") == {"type": type_, "value": value}


def test_interpret_large_integer_result_formats_without_error(rpc):
    source = (
        "let fact : sint -> sint =\n  fix fact(n: sint): sint =>\n"
        "    if n <= 1 then 1 else n * fact(n - 1)\nin fact(2000) end"
    )
    result = rpc.ok("lambda.interpret", {"source": source})
    import math

    assert result["type"] == "sint"
    assert result["value"] == str(math.factorial(2000))
    assert len(result["value"]) > 4300


def test_interpret_long_integer_literal_parses(rpc):
    literal = "9" * 5000
    result = rpc.ok("lambda.interpret", {"source": literal})
    assert result == {"type": "sint", "value": literal}
