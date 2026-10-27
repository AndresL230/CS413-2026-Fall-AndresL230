"""Source-AST builders and shared programs for the test suites (data and
small helpers only; no test logic)."""
from __future__ import annotations

from source import (
    D0Eint, D0Ebtf, D0Eop1, D0Eop2, D0Evar, D0Elam, D0Efix,
    D0Eapp, D0Eif0, D0Elet, D0Epair, D0Epfst, D0Epsnd,
)

V, N, B = D0Evar, D0Eint, D0Ebtf
TRUE_, FALSE_ = B(True), B(False)


def op(name, left, right):
    return D0Eop2(name, left, right)


def app(fn, *args):
    for arg in args:
        fn = D0Eapp(fn, arg)
    return fn


def lam(*parts):
    *params, body = parts
    for p in reversed(params):
        body = D0Elam(p, body)
    return body


def if_(c, t, f):
    return D0Eif0(c, t, f)


def let(x, init, body):
    return D0Elet(x, init, body)


def pair(a, b):
    return D0Epair(a, b)


def fst(e):
    return D0Epfst(e)


def snd(e):
    return D0Epsnd(e)


def not_(e):
    return D0Eop1("not", e)


# LOOP = (fix loop(x). loop x) 0
LOOP = app(D0Efix("loop", "x", app(V("loop"), V("x"))), N(0))

# fix fact(n). if n == 0 then 1 else n * fact (n - 1)
FACT = D0Efix("fact", "n",
              if_(op("==", V("n"), N(0)),
                  N(1),
                  op("*", V("n"), app(V("fact"), op("-", V("n"), N(1))))))

# fix fib(n). if n <= 1 then n else fib (n - 1) + fib (n - 2)
FIB = D0Efix("fib", "n",
             if_(op("<=", V("n"), N(1)),
                 V("n"),
                 op("+", app(V("fib"), op("-", V("n"), N(1))),
                         app(V("fib"), op("-", V("n"), N(2))))))


def to_python(value):
    """Convert a source value (D0Eint/D0Ebtf/D0Epair) to int/bool/tuple."""
    match value:
        case D0Eint(n):
            return n
        case D0Ebtf(b):
            return b
        case D0Epair(a, b):
            return (to_python(a), to_python(b))
    raise TypeError(f"not a data value: {value!r}")
