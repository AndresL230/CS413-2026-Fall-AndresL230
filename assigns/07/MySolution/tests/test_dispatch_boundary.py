from lambda_rpc.service import LambdaService


class SpyService:
    def __init__(self):
        self.calls = []

    def health(self):
        self.calls.append(("health",))
        return {"status": "ok", "version": "spy"}

    def typecheck(self, source):
        self.calls.append(("typecheck", source))
        return {"type": "SPY"}

    def interpret(self, source):
        self.calls.append(("interpret", source))
        return {"type": "SPY", "value": "SPY"}

    def compile(self, source, target):
        self.calls.append(("compile", source, target))
        return {"target": target, "code": "SPY"}


def test_dispatcher_passes_validated_params_to_service(rpc_for):
    spy = SpyService()
    rpc = rpc_for(service=spy)
    assert rpc.ok("lambda.typecheck", {"source": "a b"}) == {"type": "SPY"}
    assert rpc.ok("lambda.interpret", {"source": "  x "}) == {"type": "SPY", "value": "SPY"}
    assert rpc.ok("lambda.compile", {"source": "q", "target": "javascript"}) == {
        "target": "javascript",
        "code": "SPY",
    }
    assert rpc.ok("service.health", {}) == {"status": "ok", "version": "spy"}
    assert spy.calls == [
        ("typecheck", "a b"),
        ("interpret", "  x "),
        ("compile", "q", "javascript"),
        ("health",),
    ]


def test_notification_invokes_method_once_but_returns_nothing(rpc_for):
    spy = SpyService()
    rpc = rpc_for(service=spy)
    resp = rpc.post({"jsonrpc": "2.0", "method": "lambda.typecheck", "params": {"source": "1"}})
    assert resp.status_code == 204 and resp.get_data() == b""
    assert spy.calls == [("typecheck", "1")]


def test_invalid_requests_never_reach_the_service(rpc_for):
    spy = SpyService()
    rpc = rpc_for(service=spy)
    rpc.raw_error({"jsonrpc": "1.0", "method": "lambda.typecheck", "params": {"source": "1"}}, -32600)
    rpc.err("lambda.typecheck", {"source": " "}, -32602)
    rpc.err("lambda.compile", {"source": "1", "target": "c"}, -32602)
    rpc.err("lambda.typecheck", ["1"], -32602)
    rpc.err("nope", {}, -32601)
    rpc.post_json(raw=b"{")
    assert spy.calls == []


def test_max_source_override_is_honored_by_validation(rpc_for):
    spy = SpyService()
    rpc = rpc_for({"MAX_SOURCE_CHARS": 10}, service=spy)
    err = rpc.err("lambda.typecheck", {"source": "x" * 11}, -32602)
    assert err["data"]["limit"] == 10 and err["data"]["actual"] == 11
    assert spy.calls == []


def test_dispatcher_is_independent_of_lambda3():
    import lambda_rpc.jsonrpc as j

    assert "lambda3" not in open(j.__file__).read()
    from lambda_rpc.jsonrpc import Dispatcher

    d = Dispatcher({"echo": lambda params: params})
    assert d.handle_payload({"jsonrpc": "2.0", "method": "echo", "params": {"a": 1}, "id": 1}) == {
        "jsonrpc": "2.0",
        "id": 1,
        "result": {"a": 1},
    }
