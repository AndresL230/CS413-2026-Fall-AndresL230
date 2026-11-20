"""Required test 2: CPS success and failure paths, run in LAMBDA3 with custom
continuations, including resumption at the next candidate."""

from lamhelpers import kinds_until_end, lam_list
from queens import solver

L = solver.L
TRY, PLACE, REJECT, BACKTRACK, SOLUTION, DONE = range(6)
FOUND, EXHAUSTED = 100, 300

# on_solution that records the board and STOPS (never calls resume).
STOP_AT_FIRST = f"lam (p: (List[sint], unit -> Strm[{solver.EVENT_TYPE}])) => queens_emit(({FOUND}, 0, 0, p.0), queens_strm_nil)"
# on_solution that records the board and RESUMES through the failure continuation.
RESUME = f"lam (p: (List[sint], unit -> Strm[{solver.EVENT_TYPE}])) => queens_emit(({FOUND}, 0, 0, p.0), p.1)"
EXHAUST = f"lam (u: unit) => queens_emit(({EXHAUSTED}, 0, 0, list_nil()), queens_strm_nil)"


def search(size, on_solution, on_exhausted=EXHAUST, row=0, board=()):
    body = f"queens_search({size}, {row}, {lam_list(board)}, {on_solution}, {on_exhausted})"
    return kinds_until_end(solver.evaluate(body))


def test_success_continuation_receives_first_board_and_can_stop():
    events = search(4, STOP_AT_FIRST)
    assert events[-1] == (FOUND, 0, 0, [1, 3, 0, 2])
    assert [e[0] for e in events].count(FOUND) == 1
    assert EXHAUSTED not in [e[0] for e in events]  # failure path never ran


def test_success_continuation_resumes_search_through_failure_continuation():
    events = search(4, RESUME)
    found = [e[3] for e in events if e[0] == FOUND]
    assert found == [[1, 3, 0, 2], [2, 0, 3, 1]]
    assert events[-1][0] == EXHAUSTED  # root failure continuation runs exactly once, last
    assert [e[0] for e in events].count(EXHAUSTED) == 1
    # Resuming after a solution backtracks the last queen first.
    first = next(i for i, e in enumerate(events) if e[0] == FOUND)
    assert events[first + 1] == (BACKTRACK, 2, 3, [1, 3, 0])


def test_failure_continuation_when_every_column_is_rejected():
    # Row 2 of 4x4 with queens at (0,0) and (1,2): every column conflicts.
    events = search(4, STOP_AT_FIRST, row=2, board=[0, 2])
    assert events == [
        (TRY, 0, 2, [0, 2]), (REJECT, 0, 2, [0, 2]),
        (TRY, 1, 2, [0, 2]), (REJECT, 1, 2, [0, 2]),
        (TRY, 2, 2, [0, 2]), (REJECT, 2, 2, [0, 2]),
        (TRY, 3, 2, [0, 2]), (REJECT, 3, 2, [0, 2]),
        (EXHAUSTED, 0, 0, []),
    ]


def test_search_at_full_board_calls_success_with_its_failure_continuation():
    # row == size: on_solution(board, on_exhausted) immediately.
    events = search(4, RESUME, row=4, board=[1, 3, 0, 2])
    assert events == [(FOUND, 0, 0, [1, 3, 0, 2]), (EXHAUSTED, 0, 0, [])]


def test_dead_end_backtracks_and_resumes_at_next_candidate():
    # 4x4 opening: (0,0) placed, row 1 tries 0,1 (reject), 2 placed, row 2 all
    # rejected -> backtrack (2,1) -> try (3,1) next.
    events = search(4, STOP_AT_FIRST)
    i = events.index((BACKTRACK, 2, 1, [0]))
    assert events[i - 1] == (REJECT, 3, 2, [0, 2])
    assert events[i + 1] == (TRY, 3, 1, [0])


def test_row_exhaustion_backtracks_parent_then_next_parent_column():
    # After every row-1 column under (0,0) fails, the parent (0,0) is
    # backtracked and row 0 resumes at column 1.
    events = search(4, STOP_AT_FIRST)
    i = events.index((BACKTRACK, 0, 0, []))
    assert events[i + 1] == (TRY, 1, 0, [])


def test_resumption_rule_over_full_8x8_trace(trace8):
    # After backtrack(c, r, board): try(c + 1, r, board) if c + 1 < size,
    # otherwise the parent's backtrack (or done after row 0).
    events = trace8.events
    for i, e in enumerate(events):
        if e["event"] != "backtrack":
            continue
        nxt = events[i + 1]
        c, r, board = e["column"], e["row"], e["board"]
        if c + 1 < 8:
            assert nxt == {"event": "try", "column": c + 1, "row": r, "board": board}
        elif r == 0:
            assert nxt == {"event": "done"}
        else:
            assert nxt["event"] == "backtrack" and nxt["row"] == r - 1
            assert nxt["column"] == board[-1] and nxt["board"] == board[:-1]
