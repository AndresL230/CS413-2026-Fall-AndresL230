"""Required test 1: the CPS safety check, run in LAMBDA3.

Boards are row-order here. Same-row conflicts cannot be represented (one
column per row), so the 'same row' case is the same-column check; see
DESIGN.md section 2.
"""

import pytest

from lamhelpers import kinds_until_end, lam_list
from queens import solver

L = solver.L
SAFE, CONFLICT = 100, 200


def run_check(column, board):
    """Call queens_check_safe with marker continuations; return 'safe' or 'conflict'."""
    marker = lambda kind: f"lam (u: unit) => queens_emit(({kind}, 0, 0, list_nil()), queens_strm_nil)"
    body = (f"queens_check_safe({column}, 1, {lam_list(board)}, "
            f"{marker(SAFE)}, {marker(CONFLICT)})")
    events = kinds_until_end(solver.evaluate(body))
    assert len(events) == 1, events  # exactly one continuation ran
    return {SAFE: "safe", CONFLICT: "conflict"}[events[0][0]]


def test_empty_board_is_safe():
    assert run_check(3, []) == "safe"


def test_same_column_adjacent_row_conflicts():
    assert run_check(3, [3]) == "conflict"


def test_same_column_distant_row_conflicts():
    # queens at (row0, col3), (row1, col0); candidate row 2 col 3
    assert run_check(3, [3, 0]) == "conflict"


def test_diagonal_up_left_conflicts():
    # queen at (row0, col1); candidate (row1, col2): previous == column - distance
    assert run_check(2, [1]) == "conflict"


def test_diagonal_up_right_conflicts():
    # queen at (row0, col2); candidate (row1, col1): previous == column + distance
    assert run_check(1, [2]) == "conflict"


def test_non_adjacent_diagonal_conflicts():
    # queen at (row0, col0), (row1, col5); candidate (row2, col2) hits row 0 at distance 2
    assert run_check(2, [0, 5]) == "conflict"


@pytest.mark.parametrize("column,board", [
    (2, [0]),           # knight's move away
    (4, [0, 2]),        # clear of both queens
    (4, [1, 3, 0, 2]),  # completes the 5x5 solution [1, 3, 0, 2, 4]
])
def test_safe_placements(column, board):
    assert run_check(column, board) == "safe"


def test_conflict_stops_at_first_collision(applies):
    # Conflict with the newest queen: exactly one check call, no further walk.
    run_check(4, [0, 2, 5, 4])
    assert applies["check"] == 1


def test_safe_walks_whole_board_once(applies):
    # Four queens, none conflicting with column 2 in row 4: 4 checks + empty-board call.
    run_check(2, [0, 4, 7, 5])
    assert applies["check"] == 5


def test_check_safe_type_is_cps():
    # It returns the stream answer type, never a bool for direct-style code.
    expr = L.D0Elets(solver.declarations(), L.D0Evar("queens_check_safe"))
    strm = f"Lazy[Stcn[{solver.EVENT_TYPE}]]"
    assert L.format_type(L.d0exp_typecheck(expr)) == (
        f"(sint, sint, List[sint], unit -> {strm}, unit -> {strm}) -> {strm}")
