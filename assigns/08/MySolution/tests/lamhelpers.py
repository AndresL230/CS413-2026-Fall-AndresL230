"""Helpers for building LAMBDA test snippets and reading raw streams."""

from queens import solver


def lam_list(board):
    """LAMBDA source for a row-order board as a newest-first List[sint]."""
    source = "list_nil()"
    for column in board:
        source = f"list_cons({column}, {source})"
    return source


def kinds_until_end(strm, limit=10_000):
    """Force a raw Strm and return its raw event tuples as Python tuples.
    Marker events from test continuations use kinds >= 100."""
    out = []
    while len(out) < limit:
        cell = solver.force(strm)
        if not cell.is_cons:
            return out
        kind, column, row, board = cell.head.arg1
        out.append((kind.arg1, column.arg1, row.arg1, solver._board(board)))
        strm = cell.tail
    raise AssertionError("stream did not end")
