"""Unexpected worker failures: generic client error, traceback only in the server log."""

import worker_doubles
from conftest import assert_no_leak
from lambda_rpc import worker


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


def test_worker_dying_without_result_is_logged_and_hidden(rpc, error_log, monkeypatch):
    # The spawned child pickles its target by reference, so a module-level double
    # (tests/worker_doubles.py) runs inside the child and exits without sending.
    monkeypatch.setattr(worker, "_child_main", worker_doubles.die_before_reporting)

    status, body = rpc.post_json(rpc.request("lambda.interpret", {"source": "1 + 2"}, "dead"))
    assert status == 200
    assert body == {
        "jsonrpc": "2.0",
        "id": "dead",
        "error": {"code": -32603, "message": "Internal error"},
    }
    assert_no_leak(body)

    messages = [r.getMessage() for r in error_log.records if r.name == "lambda_rpc"]
    assert any("exited without a result" in m and "exitcode=1" in m for m in messages), messages

    monkeypatch.undo()
    assert rpc.ok("lambda.interpret", {"source": "6 * 7"}) == {"type": "sint", "value": "42"}
