def req(method, params, **kw):
    return {"jsonrpc": "2.0", "method": method, "params": params, **kw}


def test_batch_matches_by_id_with_mixed_id_types_and_omits_notification(rpc):
    payload = [
        req("lambda.interpret", {"source": "6 * 7"}, id="answer"),
        req("lambda.typecheck", {"source": "1 + true"}, id=7),
        req("service.health", {}),
        req("service.health", {}, id=2.5),
    ]
    status, body = rpc.post_json(payload)
    assert status == 200 and isinstance(body, list) and len(body) == 3
    by_id = {r["id"]: r for r in body}
    assert by_id["answer"]["result"] == {"type": "sint", "value": "42"}
    assert by_id[7]["error"]["code"] == -32011
    assert by_id[2.5]["result"] == {"status": "ok", "version": "1.0"}
    for r in body:
        assert r["jsonrpc"] == "2.0" and ("result" in r) != ("error" in r)


def test_batch_invalid_members_get_null_id_alongside_valid_results(rpc):
    payload = [
        req("service.health", {}, id="ok"),
        "not-a-request-object",
        {"jsonrpc": "2.0", "method": 42, "id": 9},
        [req("service.health", {}, id="nested")],
        {"jsonrpc": "1.0", "method": "service.health", "id": 3},
    ]
    status, body = rpc.post_json(payload)
    assert status == 200 and len(body) == 5
    assert body[0] == {"jsonrpc": "2.0", "id": "ok", "result": {"status": "ok", "version": "1.0"}}
    for r in body[1:]:
        assert r["id"] is None
        assert r["error"]["code"] == -32600 and r["error"]["message"] == "Invalid Request"
    assert [r["error"]["data"]["reason"] for r in body[1:]] == [
        "request must be an object",
        "method must be a string",
        "request must be an object",
        'jsonrpc must be "2.0"',
    ]
    assert all(r["id"] != 9 for r in body)


def test_notification_only_batch_is_204_empty_body(rpc):
    payload = [req("service.health", {}), req("lambda.typecheck", {"source": "1 + 2"})]
    resp = rpc.post(payload)
    assert resp.status_code == 204 and resp.get_data() == b""


def test_empty_batch_is_single_invalid_request_object(rpc):
    status, body = rpc.post_json([])
    assert status == 200
    assert isinstance(body, dict)
    assert body == {
        "jsonrpc": "2.0",
        "id": None,
        "error": {"code": -32600, "message": "Invalid Request", "data": {"reason": "empty batch"}},
    }


def test_single_notification_is_204_empty_body(rpc):
    resp = rpc.post(req("lambda.interpret", {"source": "1 + 1"}))
    assert resp.status_code == 204 and resp.get_data() == b""


def test_failing_notification_produces_no_response(rpc):
    for bad in (
        req("lambda.typecheck", {"source": "1 + true"}),
        req("lambda.typecheck", {"source": "  "}),
        req("no.such.method", {}),
        req("lambda.typecheck", ["x"]),
    ):
        resp = rpc.post(bad)
        assert resp.status_code == 204 and resp.get_data() == b""


def test_failing_notifications_in_batch_are_omitted_but_calls_answered(rpc):
    payload = [
        req("lambda.typecheck", {"source": "1 + true"}),
        req("service.health", {}, id="h"),
    ]
    status, body = rpc.post_json(payload)
    assert status == 200 and [r["id"] for r in body] == ["h"]


def test_invalid_notification_still_gets_invalid_request(rpc):
    status, body = rpc.post_json([{"jsonrpc": "1.0", "method": "service.health"}])
    assert status == 200
    assert body[0]["id"] is None and body[0]["error"]["code"] == -32600


def test_batch_with_unknown_method_and_bad_params_keeps_ids(rpc):
    payload = [req("nope", {}, id="a"), req("lambda.interpret", {}, id="b")]
    status, body = rpc.post_json(payload)
    got = {r["id"]: r["error"]["code"] for r in body}
    assert got == {"a": -32601, "b": -32602}
