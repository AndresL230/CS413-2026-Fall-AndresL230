import logging

from lambda_rpc.service import LambdaService


class ExplodingService(LambdaService):
    """Real service, except typecheck/interpret/compile raise on demand."""

    def __init__(self):
        super().__init__()

    def typecheck(self, source):
        if source == "boom":
            raise RuntimeError("secret /home/x/path")
        return super().typecheck(source)

    def interpret(self, source):
        raise RuntimeError("secret /home/x/path")

    def compile(self, source, target):
        raise KeyError("/home/x/secret.py")


def test_unexpected_failure_is_internal_error_without_data_or_leak(rpc_for, error_log):
    rpc = rpc_for(service=ExplodingService())
    resp = rpc.post(rpc.request("lambda.interpret", {"source": "1"}, "boom-id"))
    text = resp.get_data(as_text=True)
    assert resp.status_code == 200
    body = resp.get_json()
    assert body == {
        "jsonrpc": "2.0",
        "id": "boom-id",
        "error": {"code": -32603, "message": "Internal error"},
    }
    for leak in ("secret", "/home", "Traceback", "RuntimeError", ".py"):
        assert leak not in text


def test_unexpected_failure_traceback_is_logged_server_side(rpc_for, error_log):
    rpc = rpc_for(service=ExplodingService())
    rpc.err("lambda.interpret", {"source": "1"}, -32603, 5)
    assert "Traceback" in error_log.text
    assert "RuntimeError: secret /home/x/path" in error_log.text
    assert any(r.levelno == logging.ERROR and r.exc_info for r in error_log.records)


def test_unexpected_failure_in_compile_is_internal_error(rpc_for, error_log):
    rpc = rpc_for(service=ExplodingService())
    err = rpc.err("lambda.compile", {"source": "1", "target": "python"}, -32603, "c")
    assert "data" not in err


def test_injected_failure_in_batch_does_not_break_other_members(rpc_for, error_log):
    rpc = rpc_for(service=ExplodingService())
    notification = {"jsonrpc": "2.0", "method": "lambda.typecheck", "params": {"source": "boom"}}
    payload = [
        rpc.request("lambda.typecheck", {"source": "boom"}, "bad"),
        rpc.request("lambda.typecheck", {"source": "1 + 2"}, "good"),
        rpc.request("service.health", {}, 3),
        notification,  # failing notification: no response
    ]
    status, body = rpc.post_json(payload)
    assert status == 200 and len(body) == 3
    by_id = {r["id"]: r for r in body}
    assert by_id["bad"]["error"] == {"code": -32603, "message": "Internal error"}
    assert by_id["good"]["result"] == {"type": "sint"}
    assert by_id[3]["result"] == {"status": "ok", "version": "1.0"}
