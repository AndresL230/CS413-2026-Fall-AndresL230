def test_lam_value_is_formatted_as_lam_without_internals(rpc):
    source = "let f : sint -> sint = lam (x: sint) => x in f end"
    result = rpc.ok("lambda.interpret", {"source": source})
    assert result == {"type": "sint -> sint", "value": "<lam>"}


def test_fix_value_is_formatted_as_fix_without_internals(rpc):
    source = "let g : sint -> sint = fix g(n: sint): sint => n in g end"
    result = rpc.ok("lambda.interpret", {"source": source})
    assert result == {"type": "sint -> sint", "value": "<fix>"}


def test_function_values_contain_no_closure_or_env_internals(rpc):
    for source in (
        "let k : sint = 5 in lam (x: sint) => x + k end",
        "let f : sint -> sint = fix f(n: sint): sint => n in f end",
    ):
        result = rpc.ok("lambda.interpret", {"source": source})
        for word in ("env", "closure", "D0V", "0x", "object", "{", "k"):
            assert word.lower() not in result["value"].lower()
        assert result["value"] in ("<lam>", "<fix>")
