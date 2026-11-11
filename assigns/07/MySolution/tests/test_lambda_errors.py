def test_syntax_error_single_line_has_position_and_snippet(rpc):
    err = rpc.err("lambda.typecheck", {"source": "if then"}, -32010, "syntax")
    assert err["message"] == "LAMBDA syntax error: Expected an expression"
    assert err["data"] == {"line": 1, "column": 4, "snippet": "if then"}


def test_syntax_error_multi_line_reports_the_right_line(rpc):
    err = rpc.err("lambda.interpret", {"source": "let x = 1 in\n  x +\nend"}, -32010, "s2")
    assert err["data"] == {"line": 3, "column": 1, "snippet": "end"}


def test_syntax_error_snippet_is_truncated_to_200_chars(rpc):
    source = "1 + " + "1 " * 300 + "+ )"
    err = rpc.err("lambda.typecheck", {"source": source}, -32010)
    assert len(err["data"]["snippet"]) <= 200


def test_type_error_has_detail(rpc):
    err = rpc.err("lambda.typecheck", {"source": "1 + true"}, -32011, "type")
    assert err["message"] == "LAMBDA type error: +: expected bool, got sint"
    assert err["data"] == {"detail": "+: expected bool, got sint"}


def test_syntax_and_type_error_codes_are_distinct(rpc):
    syntax = rpc.err("lambda.typecheck", {"source": "if then"}, -32010)
    typ = rpc.err("lambda.typecheck", {"source": "1 + true"}, -32011)
    assert syntax["code"] != typ["code"]


def test_unbound_variable_rejected_by_typecheck(rpc):
    err = rpc.err("lambda.typecheck", {"source": "x + 1"}, -32011, "u1")
    assert err["data"]["detail"] == "unbound variable 'x'"
    assert err["message"] == "LAMBDA type error: unbound variable 'x'"


def test_unbound_variable_rejected_by_interpret_without_running(rpc):
    err = rpc.err("lambda.interpret", {"source": "x + 1"}, -32011, "u2")
    assert err["data"] == {"detail": "unbound variable 'x'"}


def test_unbound_variable_rejected_by_compile(rpc):
    rpc.err("lambda.compile", {"source": "x + 1", "target": "javascript"}, -32011)
