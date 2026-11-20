"""Bridge between Python and the LAMBDA3 solver in queens.lam.

Loads and type-checks the solver once, opens event streams for a board size,
forces one stream cell at a time through the interpreter's own lazy_eval, and
decodes events into JSON-ready dicts. Knows nothing about HTTP or JSON-RPC.
"""

from functools import lru_cache
from pathlib import Path

from .lambda3_loader import load_lambda3

L = load_lambda3()

SOURCE_PATH = Path(__file__).resolve().parent / "queens.lam"
MIN_SIZE = 4
MAX_SIZE = 10
EVENT_TYPE = "(sint, sint, sint, List[sint])"
ENTRY_TYPE = f"sint -> Lazy[Stcn[{EVENT_TYPE}]]"
KINDS = ("try", "place", "reject", "backtrack", "solution", "done")
_BOARD_EVENTS = frozenset(("try", "place", "reject", "backtrack"))


class SolverError(Exception):
    """The solver program is malformed or produced an unexpected value."""


@lru_cache(maxsize=1)
def declarations():
    """Parse and type-check queens.lam once; return its declaration list."""
    decls = L.d0cls_parse(SOURCE_PATH.read_text())
    L.d0cls_typecheck(decls)
    entry = L.d0exp_typecheck(L.D0Elets(decls, L.D0Evar("queens_stream")))
    if L.format_type(entry) != ENTRY_TYPE:
        raise SolverError(f"queens_stream has type {L.format_type(entry)}")
    return decls


@lru_cache(maxsize=1)
def _entry_closure():
    """Evaluate the declarations once and keep the queens_stream closure."""
    return L.d0exp_evaluate(L.D0Elets(declarations(), L.D0Evar("queens_stream")))


def evaluate(body_source):
    """Type-check and evaluate a LAMBDA expression with the solver in scope.

    Used by tests to call queens_check_safe / queens_try_column with their
    own continuations. Returns the raw interpreter value.
    """
    expr = L.D0Elets(declarations(), L.d0exp_parse(body_source))
    L.d0exp_typecheck(expr)
    return L.d0exp_evaluate(expr)


def force(lazy):
    """Force a lazy value using the interpreter's lazy_eval (memoizing)."""
    env = L.ENVcns("s", lazy, L.ENVnil())
    return L.d0exp_evaluate(L.D0Eop1("lazy_eval", L.D0Evar("s")), env)


def _int(value):
    if not isinstance(value, L.D0Vint):
        raise SolverError("integer expected in event")
    return value.arg1


def _board(value):
    """Decode a newest-first List[sint] into a row-order Python list."""
    if not isinstance(value, L.D0Vlist):
        raise SolverError("list expected in event")
    columns = []
    items = value.arg1
    while isinstance(items, L.fnlist_cons):
        columns.append(_int(items.arg1))
        items = items.arg2
    columns.reverse()
    return columns


def decode_event(value):
    """Turn an Event tuple (kind, column, row, board) into a JSON-ready dict."""
    if not isinstance(value, L.D0Vtupl) or len(value.arg1) != 4:
        raise SolverError("event tuple expected")
    kind_code, column, row, board = value.arg1
    code = _int(kind_code)
    if not 0 <= code < len(KINDS):
        raise SolverError("unknown event kind")
    kind = KINDS[code]
    if kind in _BOARD_EVENTS:
        return {"event": kind, "column": _int(column), "row": _int(row),
                "board": _board(board)}
    if kind == "solution":
        return {"event": kind, "board": _board(board)}
    return {"event": kind}


def check_size(size):
    if isinstance(size, bool) or not isinstance(size, int) or not MIN_SIZE <= size <= MAX_SIZE:
        raise ValueError(f"size must be an integer from {MIN_SIZE} to {MAX_SIZE}")


class EventStream:
    """The unconsumed rest of one search trace. Not thread-safe by itself."""

    def __init__(self, lazy):
        self._lazy = lazy  # current Strm[Event]; None once the empty cell is seen

    def next(self):
        """Force exactly one cell; return its event dict, or None at the end."""
        if self._lazy is None:
            return None
        cell = force(self._lazy)
        if not isinstance(cell, L.D0Vstcn):
            raise SolverError("stream cell expected")
        if not cell.is_cons:
            self._lazy = None
            return None
        event = decode_event(cell.head)
        self._lazy = cell.tail
        return event


def open_stream(size):
    """Start a fresh search; builds one unforced lazy and does no search work."""
    check_size(size)
    return EventStream(L._d0val_apply(_entry_closure(), L.D0Vint(size)))


def iter_events(size):
    """Yield every event of the size x size trace, one forced cell at a time."""
    stream = open_stream(size)
    while (event := stream.next()) is not None:
        yield event
