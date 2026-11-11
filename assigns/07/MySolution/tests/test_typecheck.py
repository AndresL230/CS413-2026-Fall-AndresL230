import pytest

FACT = "let fact : sint -> sint =\n  fix fact(n: sint): sint =>\n    if n <= 1 then 1 else n * fact(n - 1)\nin fact end"


@pytest.mark.parametrize(
    "source, expected",
    [
        ("1 + 2", "sint"),
        (FACT, "sint -> sint"),
        ("(1, true)", "(sint, bool)"),
        ("list_cons(1, list_cons(2, list_nil()))", "List[sint]"),
    ],
    ids=["arithmetic", "factorial_function", "tuple", "list"],
)
def test_typecheck_valid_program_returns_formatted_type(rpc, source, expected):
    assert rpc.ok("lambda.typecheck", {"source": source}, "tc") == {"type": expected}


def test_typecheck_accepts_source_of_exactly_max_size(rpc):
    source = "1" + " " * 32767
    assert len(source) == 32768
    assert rpc.ok("lambda.typecheck", {"source": source}) == {"type": "sint"}
