"""Shared fixtures for solver and laziness tests."""

import sys
from collections import Counter
from types import SimpleNamespace

import pytest

from queens import solver

L = solver.L
DEFAULT_RECURSION_LIMIT = 1000


@pytest.fixture(scope="session")
def trace8():
    """The complete 8x8 trace, consumed one cell at a time at Python's
    default recursion limit (1000). Generated once (about 10 s) and shared."""
    previous = sys.getrecursionlimit()
    sys.setrecursionlimit(DEFAULT_RECURSION_LIMIT)
    try:
        events = list(solver.iter_events(8))
    finally:
        sys.setrecursionlimit(previous)
    return SimpleNamespace(events=events, recursion_limit=DEFAULT_RECURSION_LIMIT)


class ApplyCounter:
    """Counts every LAMBDA function application made by the interpreter.

    Wraps lambda3._d0val_apply, which the interpreter calls (as a module
    global) for every application, including the thunk call inside lazy_eval.
    Named recursive functions are counted by their fix name: 'check' is
    queens_check_safe and 'try_column' is queens_try_column.
    """

    def __init__(self, monkeypatch):
        self.counts = Counter()
        original = L._d0val_apply

        def counting(dfun, darg):
            name = dfun.arg2.arg1 if isinstance(dfun, L.D0Vfix) else "lam"
            self.counts[name] += 1
            self.counts["total"] += 1
            return original(dfun, darg)

        monkeypatch.setattr(L, "_d0val_apply", counting)

    def __getitem__(self, name):
        return self.counts[name]

    def snapshot(self):
        return Counter(self.counts)


@pytest.fixture
def applies(monkeypatch):
    solver.declarations()
    solver._entry_closure()  # warm the caches before counting
    return ApplyCounter(monkeypatch)
