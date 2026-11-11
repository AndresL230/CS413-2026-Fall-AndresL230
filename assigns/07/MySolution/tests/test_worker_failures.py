"""Unexpected worker failures: generic client error, traceback only in the server log."""

from conftest import assert_no_leak


def test_worker_setup_failure_logs_traceback_but_hides_it(rpc_for, error_log):
    # stack_size(1) raises ValueError inside the real spawned child.
    rpc = rpc_for({"WORKER_STACK_BYTES": 1})

    status, body = rpc.post_json(rpc.request("lambda.interpret", {"source": "1 + 2"}, "wf"))
    assert status == 200
    assert body == {
        "jsonrpc": "2.0",
        "id": "wf",
        "error": {"code": -32603, "message": "Internal error"},
    }
    assert_no_leak(body)

    messages = [r.getMessage() for r in error_log.records if r.name == "lambda_rpc"]
    assert any(
        "worker failed" in m and "Traceback" in m and "ValueError" in m for m in messages
    ), messages

    health = rpc.ok("service.health")
    assert health["status"] == "ok"
