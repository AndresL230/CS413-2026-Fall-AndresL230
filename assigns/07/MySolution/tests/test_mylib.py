import pytest

from lambda_rpc import config

LIB = config.LAMBDA3_DIR / "mylib"

CASES = [
    ("list.lam", "list_map(list_range(1, 6), lam (x: sint) => x * x)", "List[sint]", "[1, 4, 9, 16, 25]"),
    ("optn.lam", "optn_get_default(optn_map(optn_cons(20), lam (x: sint) => x + 1), 0)", "sint", "21"),
    ("strm.lam", "strm_to_list(strm_take(strm_range(0, 100), 5))", "List[sint]", "[0, 1, 2, 3, 4]"),
    (
        "a1sz.lam",
        "a1sz_quicksort(a1sz_make_nfun(5, lam (i: sint) => 5 - i), lam (p: (sint, sint)) => p.0 <= p.1)",
        "A1sz[sint]",
        "[1, 2, 3, 4, 5]",
    ),
]


def wrap(filename, body):
    return "let\n" + (LIB / filename).read_text() + "\nin\n" + body + "\nend"


@pytest.mark.parametrize("filename, body, type_, value", CASES, ids=[c[0] for c in CASES])
def test_mylib_demo_typechecks(rpc, filename, body, type_, value):
    assert rpc.ok("lambda.typecheck", {"source": wrap(filename, body)}) == {"type": type_}


@pytest.mark.parametrize("filename, body, type_, value", CASES, ids=[c[0] for c in CASES])
def test_mylib_demo_interprets(rpc, filename, body, type_, value):
    result = rpc.ok("lambda.interpret", {"source": wrap(filename, body)}, filename)
    assert result == {"type": type_, "value": value}


@pytest.mark.parametrize("filename, body, type_, value", CASES, ids=[c[0] for c in CASES])
def test_mylib_demo_compiles_to_both_targets(rpc, filename, body, type_, value):
    for target in ("python", "javascript"):
        result = rpc.ok("lambda.compile", {"source": wrap(filename, body), "target": target})
        assert result["target"] == target and result["code"].strip()
