"""Required test 8 (limits 1 and 32, never more than requested), batches
hitting one stream in order, and per-request atomicity."""

import threading
from collections import Counter

from queens import solver


def test_limit_1_returns_exactly_one_event(rpc):
    stream_id = rpc.open(8)
    expected = solver.open_stream(8)
    for _ in range(50):
        result = rpc.next(stream_id, 1)
        assert result["events"] == [expected.next()] and result["done"] is False


def test_limit_defaults_to_1(rpc):
    stream_id = rpc.open(8)
    assert len(rpc.ok("queens.next", {"stream_id": stream_id})["events"]) == 1


def test_limit_32_returns_exactly_32_while_available(rpc):
    stream_id = rpc.open(8)
    for _ in range(10):
        assert len(rpc.next(stream_id, 32)["events"]) == 32


def test_limits_never_exceeded_through_exhaustion(rpc):
    # 4x4 has 139 events: 4 full batches of 32, then the last 11 with done.
    stream_id = rpc.open(4)
    events, responses = rpc.drain(stream_id, 32)
    assert [len(r["events"]) for r in responses] == [32, 32, 32, 32, 11]
    for limit in (1, 7, 32):
        sid = rpc.open(5)
        evs, resps = rpc.drain(sid, limit)
        assert all(len(r["events"]) <= limit for r in resps)
        assert evs == list(solver.iter_events(5))


def test_batch_hits_one_stream_in_order(rpc):
    stream_id = rpc.open(8)
    batch = [rpc.request("queens.next", {"stream_id": stream_id, "limit": 3}, request_id=i)
             for i in range(4)]
    status, body = rpc.post_json(batch)
    assert status == 200
    assert [r["id"] for r in body] == [0, 1, 2, 3]
    events = [e for r in body for e in r["result"]["events"]]
    assert events == [e for _, e in zip(range(12), solver.iter_events(8))]


def test_batch_mixes_results_errors_and_notifications(rpc):
    stream_id = rpc.open(8)
    batch = [
        rpc.request("queens.next", {"stream_id": stream_id, "limit": 2}, request_id="a"),
        rpc.notification("queens.next", {"stream_id": stream_id, "limit": 2}),
        rpc.request("queens.next", {"stream_id": stream_id, "limit": 33}, request_id="b"),
        rpc.request("queens.next", {"stream_id": stream_id, "limit": 2}, request_id="c"),
        {"jsonrpc": "2.0"},
    ]
    status, body = rpc.post_json(batch)
    assert status == 200
    assert [r["id"] for r in body] == ["a", "b", "c", None]
    trace = [e for _, e in zip(range(6), solver.iter_events(8))]
    assert body[0]["result"]["events"] == trace[0:2]
    assert body[1]["error"]["code"] == -32602
    assert body[2]["result"]["events"] == trace[4:6]  # the notification consumed 2..3
    assert body[3]["error"]["code"] == -32600


def test_batch_of_only_notifications_is_204(rpc):
    resp = rpc.post([rpc.notification("service.health"), rpc.notification("service.health")])
    assert resp.status_code == 204 and resp.get_data() == b""


def test_concurrent_next_calls_partition_the_trace(rpc, app):
    # Each next holds the entry's lock, so concurrent slices are disjoint
    # and together cover the whole trace exactly once.
    stream_id = rpc.open(5)
    seen = []
    lock = threading.Lock()

    def worker():
        from rpchelpers import Rpc
        client = Rpc(app.test_client())
        while True:
            result = client.next(stream_id, 5)
            with lock:
                seen.extend(result["events"])
            if result["done"]:
                return

    threads = [threading.Thread(target=worker) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    expected = list(solver.iter_events(5))
    assert len(seen) == len(expected)
    assert Counter(map(str, seen)) == Counter(map(str, expected))
