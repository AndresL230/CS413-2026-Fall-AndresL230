"""Required test 4: each event kind, with correct coordinates and board
snapshots, over the full 8x8 trace produced by LAMBDA3."""

from collections import Counter

from queens import solver
from reference import attacks, reference_trace

BOARD_EVENT_KEYS = {"event", "column", "row", "board"}


def test_8x8_opening_events():
    stream = solver.open_stream(8)
    first = [stream.next() for _ in range(8)]
    assert first == [
        {"event": "try", "column": 0, "row": 0, "board": []},
        {"event": "place", "column": 0, "row": 0, "board": [0]},
        {"event": "try", "column": 0, "row": 1, "board": [0]},
        {"event": "reject", "column": 0, "row": 1, "board": [0]},
        {"event": "try", "column": 1, "row": 1, "board": [0]},
        {"event": "reject", "column": 1, "row": 1, "board": [0]},
        {"event": "try", "column": 2, "row": 1, "board": [0]},
        {"event": "place", "column": 2, "row": 1, "board": [0, 2]},
    ]


def test_every_kind_occurs_with_expected_totals(trace8):
    counts = Counter(e["event"] for e in trace8.events)
    assert counts == {"try": 15720, "reject": 13664, "place": 2056,
                      "backtrack": 2056, "solution": 92, "done": 1}
    assert len(trace8.events) == 33589


def test_done_exactly_once_and_last(trace8):
    assert trace8.events[-1] == {"event": "done"}
    assert sum(e["event"] == "done" for e in trace8.events) == 1


def test_full_trace_matches_direct_style_model(trace8):
    assert trace8.events == reference_trace(8)


def test_board_snapshots_and_coordinates_replay(trace8):
    """Replay the trace against a Python board, checking each event's data."""
    board = []
    pending = None  # the (column, row) of the most recent try
    for e in trace8.events:
        kind = e["event"]
        if kind in ("try", "place", "reject", "backtrack"):
            assert set(e) == BOARD_EVENT_KEYS
            assert 0 <= e["column"] < 8 and 0 <= e["row"] < 8
        if kind == "try":
            assert e["board"] == board and e["row"] == len(board)
            pending = (e["column"], e["row"])
        elif kind == "reject":
            assert (e["column"], e["row"]) == pending and e["board"] == board
            assert attacks(e["column"], e["row"], board)
        elif kind == "place":
            assert (e["column"], e["row"]) == pending
            assert not attacks(e["column"], e["row"], board)
            board = board + [e["column"]]
            assert e["board"] == board
        elif kind == "backtrack":
            assert board and board[-1] == e["column"] and len(board) - 1 == e["row"]
            board = board[:-1]
            assert e["board"] == board
        elif kind == "solution":
            assert set(e) == {"event", "board"} and e["board"] == board and len(board) == 8
        else:
            assert e == {"event": "done"} and board == []
