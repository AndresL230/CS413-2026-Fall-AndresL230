from __future__ import annotations

########################################################################
########################################################################
# Source programs built directly as ASTs (no parser): small builders,
# the shared programs LOOP, FACT, and FIB, and the 14 mandatory
# demonstrations (REQUIREMENTS.md section 7.1). Data only.
# Requires Python 3.12 or later.
########################################################################
########################################################################
from dataclasses import dataclass

from observers import NAT, BOOL, Kind
from source import (
    d0exp, D0Eint, D0Ebtf, D0Eop1, D0Eop2, D0Evar, D0Elam, D0Efix,
    D0Eapp, D0Eif0, D0Elet, D0Epair, D0Epfst, D0Epsnd,
)

########################################################################
# Builders
########################################################################

V, N, B = D0Evar, D0Eint, D0Ebtf
TRUE_, FALSE_ = B(True), B(False)


def op(name: str, left: d0exp, right: d0exp) -> d0exp:
    return D0Eop2(name, left, right)


def app(fn: d0exp, *args: d0exp) -> d0exp:
    """app(f, a, b) == ((f a) b)."""
    for arg in args:
        fn = D0Eapp(fn, arg)
    return fn


def lam(*parts: str | d0exp) -> d0exp:
    """lam("x", "y", body) == lam x. lam y. body."""
    *params, body = parts
    for param in reversed(params):
        body = D0Elam(param, body)
    return body


def if_(cond: d0exp, then: d0exp, else_: d0exp) -> d0exp:
    return D0Eif0(cond, then, else_)


def let(name: str, init: d0exp, body: d0exp) -> d0exp:
    return D0Elet(name, init, body)


def pair(first: d0exp, second: d0exp) -> d0exp:
    return D0Epair(first, second)


def fst(e: d0exp) -> d0exp:
    return D0Epfst(e)


def snd(e: d0exp) -> d0exp:
    return D0Epsnd(e)


def not_(e: d0exp) -> d0exp:
    return D0Eop1("not", e)

########################################################################
# Shared programs
########################################################################

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

########################################################################
# Demonstrations
########################################################################

class _Exhausted:
    """Expected outcome of a demo that must run out of execution budget."""

    def __repr__(self) -> str:
        return "EXHAUSTED"


EXHAUSTED = _Exhausted()


@dataclass(frozen=True)
class Demo:
    id: str
    notation: str           # explanatory notation from the assignment
    source: d0exp
    kind: Kind              # expected result kind for decoding
    expected: object        # int, bool, tuple, or EXHAUSTED


DEMOS: list[Demo] = [
    Demo("DEMO-01", "2 + 3 * 4",
         op("+", N(2), op("*", N(3), N(4))), NAT, 14),
    Demo("DEMO-02", "2 - 5",
         op("-", N(2), N(5)), NAT, 0),
    Demo("DEMO-03", "if 2 <= 3 then 7 else 9",
         if_(op("<=", N(2), N(3)), N(7), N(9)), NAT, 7),
    Demo("DEMO-04", "let x = 3 in (lam y. x + y) 4",
         let("x", N(3), app(lam("y", op("+", V("x"), V("y"))), N(4))), NAT, 7),
    Demo("DEMO-05", "fst (pair 2 true)",
         fst(pair(N(2), TRUE_)), NAT, 2),
    Demo("DEMO-06", "snd (pair 2 true)",
         snd(pair(N(2), TRUE_)), BOOL, True),
    Demo("DEMO-07", "(lam f. f 3) (lam x. x + 1)",
         app(lam("f", app(V("f"), N(3))), lam("x", op("+", V("x"), N(1)))), NAT, 4),
    Demo("DEMO-08", "if true then 1 else LOOP",
         if_(TRUE_, N(1), LOOP), NAT, 1),
    Demo("DEMO-09", "(lam x. 0) LOOP",
         app(lam("x", N(0)), LOOP), NAT, EXHAUSTED),
    Demo("DEMO-10", "fact 4",
         app(FACT, N(4)), NAT, 24),
    Demo("DEMO-11", "fib 5",
         app(FIB, N(5)), NAT, 5),
    Demo("DEMO-12", "LOOP",
         LOOP, NAT, EXHAUSTED),
    Demo("DEMO-13", "true and false",
         op("and", TRUE_, FALSE_), BOOL, False),
    Demo("DEMO-14", "false or true",
         op("or", FALSE_, TRUE_), BOOL, True),
]
