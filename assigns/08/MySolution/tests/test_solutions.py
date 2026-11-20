"""Required test 3: all 8x8 solutions, exact count, deterministic order,
no duplicates. Sizes 9 and 10 are too slow for the suite (about 50 s and
260 s for a full trace); their counts are recorded in TESTING.md."""

import pytest

from queens import solver
from reference import brute_force_solutions, is_solution


def solutions_of(events):
    return [e["board"] for e in events if e["event"] == "solution"]


def test_8x8_has_exactly_92_solutions(trace8):
    assert len(solutions_of(trace8.events)) == 92


def test_8x8_solutions_are_distinct_valid_8_tuples(trace8):
    boards = solutions_of(trace8.events)
    assert len({tuple(b) for b in boards}) == 92
    for board in boards:
        assert len(board) == 8 and all(0 <= c < 8 for c in board)
        assert is_solution(board)


def test_8x8_solutions_in_depth_first_lexicographic_order(trace8):
    boards = solutions_of(trace8.events)
    assert boards == sorted(boards)
    assert boards == brute_force_solutions(8)
    assert boards[0] == [0, 4, 7, 5, 2, 6, 1, 3]
    assert boards[-1] == [7, 3, 0, 2, 5, 1, 6, 4]


@pytest.mark.parametrize("size,count", [(4, 2), (5, 10), (6, 4), (7, 40)])
def test_small_sizes_match_brute_force(size, count):
    boards = solutions_of(solver.iter_events(size))
    assert len(boards) == count
    assert boards == brute_force_solutions(size)


def test_trace_is_deterministic():
    assert list(solver.iter_events(6)) == list(solver.iter_events(6))


@pytest.mark.parametrize("size", [3, 11, 0, -1, True, 8.0, "8", None])
def test_open_rejects_sizes_outside_4_to_10(size):
    with pytest.raises(ValueError):
        solver.open_stream(size)
