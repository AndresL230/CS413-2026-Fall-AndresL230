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


# ---- Service fixtures ---------------------------------------------------------

from queens.transport import create_app  # noqa: E402
from rpchelpers import FakeClock, Rpc  # noqa: E402


@pytest.fixture
def clock():
    return FakeClock()


@pytest.fixture
def make_app(clock):
    def factory(overrides=None, open_stream=None):
        app = create_app(overrides, clock=clock, open_stream=open_stream)
        app.testing = True
        return app

    return factory


@pytest.fixture
def app(make_app):
    return make_app()


@pytest.fixture
def table(app):
    return app.extensions["streams"]


@pytest.fixture
def rpc(app):
    return Rpc(app.test_client())


@pytest.fixture
def error_log(caplog):
    import logging
    with caplog.at_level(logging.ERROR, logger="queens"):
        yield caplog
