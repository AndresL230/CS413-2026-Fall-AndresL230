"""Required test 6: exhaustion, next after exhaustion, close, unknown ids,
cleanup, expiry (fake clock), and the stream cap."""

import uuid

from queens import solver
from queens.errors import TOO_MANY_STREAMS, UNKNOWN_STREAM

L = solver.L


def test_open_returns_fresh_uuid_ids(rpc):
    first = rpc.ok("queens.open", {"size": 8})
    second = rpc.ok("queens.open", {"size": 8})
    assert first["size"] == 8
    assert uuid.UUID(first["stream_id"]).version == 4
    assert first["stream_id"] != second["stream_id"]


def test_open_through_service_runs_no_search(rpc, applies, table):
    # The only interpreter application is queens_stream(size) itself, which
    # just builds one unforced lazy; no search function runs.
    stream_id = rpc.open(10)
    assert applies["check"] == 0 and applies["try_column"] == 0
    assert applies["total"] == 1
    assert not table.entry_stream(stream_id)._lazy.evaluated


def test_table_holds_only_the_next_unforced_tail(rpc, table):
    stream_id = rpc.open(8)
    rpc.next(stream_id, 5)
    stored = table.entry_stream(stream_id)._lazy
    assert isinstance(stored, L.D0Vlazy) and not stored.evaluated
    assert rpc.next(stream_id, 1)["events"] == [
        {"event": "reject", "column": 1, "row": 1, "board": [0]}]  # the 6th event


def test_exhaustion_then_next_again_stays_done(rpc, table):
    stream_id = rpc.open(4)
    events, responses = rpc.drain(stream_id, 32)
    assert events == list(solver.iter_events(4))
    assert events[-1] == {"event": "done"}
    assert [r["done"] for r in responses] == [False] * (len(responses) - 1) + [True]
    assert table.entry_stream(stream_id) is None  # solver state released
    for _ in range(2):
        assert rpc.next(stream_id, 32) == {"events": [], "done": True}


def test_done_can_be_the_only_event_in_a_response(rpc):
    stream_id = rpc.open(4)
    for _ in range(138):  # the 4x4 trace has 139 events
        assert rpc.next(stream_id, 1)["done"] is False
    assert rpc.next(stream_id, 1) == {"events": [{"event": "done"}], "done": True}


def test_close_live_stream_then_it_is_unknown(rpc, table):
    stream_id = rpc.open(8)
    assert rpc.ok("queens.close", {"stream_id": stream_id}) == {"closed": True}
    assert len(table) == 0
    err = rpc.err("queens.next", {"stream_id": stream_id}, UNKNOWN_STREAM)
    assert err["data"] == {"stream_id": stream_id}


def test_close_exhausted_marker(rpc, table):
    stream_id = rpc.open(4)
    rpc.drain(stream_id)
    assert rpc.ok("queens.close", {"stream_id": stream_id}) == {"closed": True}
    assert len(table) == 0
    rpc.err("queens.next", {"stream_id": stream_id}, UNKNOWN_STREAM)


def test_close_twice_is_unknown(rpc):
    stream_id = rpc.open(8)
    rpc.ok("queens.close", {"stream_id": stream_id})
    err = rpc.err("queens.close", {"stream_id": stream_id}, UNKNOWN_STREAM)
    assert err == {"code": UNKNOWN_STREAM, "message": "Unknown stream",
                   "data": {"stream_id": stream_id}}


def test_unknown_id_on_next_and_close(rpc):
    fake = str(uuid.uuid4())
    for method in ("queens.next", "queens.close"):
        err = rpc.err(method, {"stream_id": fake}, UNKNOWN_STREAM)
        assert err["data"] == {"stream_id": fake}


def test_expiry_after_ttl_of_inactivity(rpc, clock):
    stream_id = rpc.open(8)
    clock.advance(599)
    rpc.next(stream_id)          # still alive; this use refreshes it
    clock.advance(599)
    rpc.next(stream_id)
    clock.advance(600)           # 600 s idle: expired
    err = rpc.err("queens.next", {"stream_id": stream_id}, UNKNOWN_STREAM)
    assert err["data"] == {"stream_id": stream_id}
    rpc.err("queens.close", {"stream_id": stream_id}, UNKNOWN_STREAM)


def test_expired_entries_are_swept_on_access(rpc, clock, table):
    old = [rpc.open(8) for _ in range(3)]
    exhausted = rpc.open(4)
    rpc.drain(exhausted)         # exhausted markers expire too
    clock.advance(600)
    assert len(table) == 4       # nothing is swept until the next access
    fresh = rpc.open(8)
    assert len(table) == 1
    for stream_id in old + [exhausted]:
        rpc.err("queens.next", {"stream_id": stream_id}, UNKNOWN_STREAM)
    rpc.next(fresh)


def test_cap_of_256_streams(rpc, table, applies):
    ids = [rpc.open(8) for _ in range(256)]
    assert len(table) == 256
    before = applies["total"]
    err = rpc.err("queens.open", {"size": 8}, TOO_MANY_STREAMS)
    assert err == {"code": TOO_MANY_STREAMS, "message": "Too many streams",
                   "data": {"limit": 256}}
    assert applies["total"] == before  # cap checked before touching the solver
    assert len(table) == 256
    rpc.ok("queens.close", {"stream_id": ids[0]})
    rpc.open(8)                  # a freed slot can be reused


def test_cap_counts_exhausted_markers_and_frees_on_expiry(make_app, clock):
    from rpchelpers import Rpc
    rpc = Rpc(make_app({"MAX_STREAMS": 2}).test_client())
    rpc.drain(rpc.open(4))
    rpc.open(8)
    rpc.err("queens.open", {"size": 8}, TOO_MANY_STREAMS)
    clock.advance(600)
    rpc.open(8)                  # sweeping expired entries frees the slots


def test_invalid_open_allocates_nothing(rpc, table, applies):
    for params in ({"size": 3}, {"size": True}, {}, {"size": 8, "extra": 1}):
        rpc.err("queens.open", params, -32602)
    assert len(table) == 0
    assert applies["total"] == 0


def test_solver_failure_is_internal_error_and_discards_stream(make_app, error_log):
    class Exploding:
        def next(self):
            raise RuntimeError("boom at /home/secret.py")

    from rpchelpers import Rpc
    app = make_app(open_stream=lambda size: Exploding())
    rpc = Rpc(app.test_client())
    stream_id = rpc.open(8)
    err = rpc.err("queens.next", {"stream_id": stream_id}, -32603)
    assert "data" not in err
    assert len(app.extensions["streams"]) == 0
    rpc.err("queens.next", {"stream_id": stream_id}, UNKNOWN_STREAM)
    assert "boom" in error_log.text  # logged server-side only
