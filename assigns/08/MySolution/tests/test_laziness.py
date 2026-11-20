"""Required test 5: the stream is genuinely lazy.

Evidence is observable, not a formatted '<lazy>': the `applies` fixture
counts every LAMBDA function application the interpreter makes, and the
tests inspect the `evaluated` flag on the interpreter's own lazy objects.
"""

from queens import solver

L = solver.L
SEARCH_FUNCTIONS = ("check", "try_column")


def search_work(applies):
    return sum(applies[name] for name in SEARCH_FUNCTIONS)


def test_open_performs_no_search(applies):
    stream = solver.open_stream(10)
    assert search_work(applies) == 0
    assert applies["total"] == 1  # only the call queens_stream(10) itself
    assert isinstance(stream._lazy, L.D0Vlazy) and not stream._lazy.evaluated


def test_forcing_one_cell_does_not_force_its_tail(applies):
    stream = solver.open_stream(8)
    cell = solver.force(stream._lazy)
    assert solver.decode_event(cell.head) == {"event": "try", "column": 0, "row": 0, "board": []}
    assert applies["check"] == 0  # the first try needs no safety check yet
    assert isinstance(cell.tail, L.D0Vlazy) and not cell.tail.evaluated


def test_bounded_prefix_leaves_later_work_unforced(applies):
    stream = solver.open_stream(10)
    prefix = [stream.next() for _ in range(100)]
    assert all(e is not None for e in prefix)
    before = applies.snapshot()
    assert not stream._lazy.evaluated  # the 101st cell is still suspended
    assert applies.snapshot() == before  # nothing runs between requests
    stream.next()
    assert applies["total"] > before["total"]  # the work lives in the tail


def test_first_10x10_solution_needs_a_small_fraction_of_the_trace(applies):
    # The full 10x10 trace has 732,563 events (per tests/reference.py); the
    # first solution is event index 2,042, and reaching it forces only that
    # prefix: no cell after it is evaluated.
    stream = solver.open_stream(10)
    taken = 0
    while (event := stream.next())["event"] != "solution":
        taken += 1
    assert event["board"] == [0, 2, 5, 7, 9, 4, 8, 1, 3, 6]
    assert taken == 2_042
    assert not stream._lazy.evaluated
    # ~2k cells forced, each bounded (see test_each_cell_does_bounded_work):
    # far below what the 732k-event trace would need.
    assert applies["total"] < 2_043 * 20


def test_forced_cells_are_memoized(applies):
    stream = solver.open_stream(8)
    lazy = stream._lazy
    first = solver.force(lazy)
    before = applies.snapshot()
    assert solver.force(lazy) is first
    assert applies.snapshot() == before


def test_each_cell_does_bounded_work(applies):
    # No continuation chain runs without emitting: forcing one cell costs at
    # most one safety walk (<= size checks) plus a constant number of calls.
    for size in (6, 10):
        stream = solver.open_stream(size)
        worst = 0
        for _ in range(3_000):
            before = applies["total"]
            if stream.next() is None:
                break
            worst = max(worst, applies["total"] - before)
        assert worst <= size + 10, (size, worst)


def test_full_8x8_trace_at_default_recursion_limit(trace8):
    # The trace8 fixture consumes all 33,589 cells with sys.setrecursionlimit(1000).
    assert trace8.recursion_limit == 1000
    assert trace8.events[-1] == {"event": "done"}
