"""Run the assignment's examples (plus edge cases) and show actual vs expected.

Usage, from assigns/05:  python3 MySolution/examples.py
"""
from __future__ import annotations

import copy

from lambda1_visitors import (
    d0exp_pretty, d0exp_substitute,
    D0Eint, D0Evar, D0Elam, D0Efix, D0Eapp, D0Elet, D0Eop2, D0Epair,
)

V, I = D0Evar, D0Eint


def add(a, b):
    return D0Eop2("+", a, b)


PRETTY = [
    ("Task 1 example",
     D0Eapp(D0Elam("x", add(V("x"), I(1))), I(4)),
     "((lam x. (x + 1)) 4)"),
    ("division by zero is not evaluated",
     D0Eop2("/", I(1), I(0)),
     "(1 / 0)"),
]

# (label, expression, target, replacement, expected printed result)
SUBST = [
    ("table 1", add(V("x"), V("z")), "x", I(3),
     "(3 + z)"),
    ("table 2: lam shadows x", D0Elam("x", add(V("x"), V("y"))), "x", I(3),
     "(lam x. (x + y))"),
    ("table 3: lam capture", D0Elam("y", add(V("x"), V("y"))), "x", V("y"),
     "(lam y_1. (y + y_1))"),
    ("table 4: let init vs body", D0Elet("x", V("x"), add(V("x"), V("y"))), "x", I(3),
     "(let x = 3 in (x + y))"),
    ("table 5: let capture", D0Elet("y", V("x"), add(V("x"), V("y"))), "x", V("y"),
     "(let y_1 = y in (y + y_1))"),
    ("table 6: fix name capture",
     D0Efix("f", "n", add(V("x"), D0Eapp(V("f"), V("n")))), "x", V("f"),
     "(fix f_1(n). (f + (f_1 n)))"),
    ("table 7: replacement has target", V("x"), "x", add(V("x"), I(1)),
     "(x + 1)"),
    # Extra edge cases (expected values follow the y_1, y_2, ... policy).
    ("both fix binders conflict",
     D0Efix("f", "n", add(add(V("x"), V("n")), D0Eapp(V("f"), V("n")))),
     "x", add(V("f"), V("n")),
     "(fix f_1(n_1). (((f + n) + n_1) + (f_1 n_1)))"),
    ("fix f(f): param shadows name", D0Efix("f", "f", add(V("x"), V("f"))),
     "x", V("f"),
     "(fix f_1(f_1). (f + f_1))"),
    ("fix shadows target", D0Efix("x", "n", V("x")), "x", I(3),
     "(fix x(n). x)"),
    ("fresh name skips existing y_1",
     D0Elam("y", D0Elam("y_1", add(add(V("x"), V("y")), V("y_1")))),
     "x", V("y"),
     "(lam y_2. (lam y_1. ((y + y_2) + y_1)))"),
    ("fresh name skips earlier generated",
     D0Epair(D0Elam("y", add(V("x"), V("y"))), D0Elam("y", add(V("x"), V("y")))),
     "x", V("y"),
     "(pair (lam y_1. (y + y_1)) (lam y_2. (y + y_2)))"),
    ("rename respects nested shadowing",
     D0Elam("y", D0Eapp(D0Eapp(V("x"), V("y")), D0Elam("y", V("y")))),
     "x", V("y"),
     "(lam y_1. ((y y_1) (lam y. y)))"),
    ("no rename when target not free", D0Elam("y", V("y")), "x", V("y"),
     "(lam y. y)"),
]


def main() -> int:
    failures = 0

    def report(label, actual, expected):
        nonlocal failures
        ok = actual == expected
        failures += not ok
        print(f"[{'PASS' if ok else 'FAIL'}] {label}")
        print(f"    actual:   {actual}")
        print(f"    expected: {expected}")

    print("== Pretty printing ==")
    for label, e, expected in PRETTY:
        report(label, d0exp_pretty(e), expected)

    print("\n== Substitution ==")
    for label, e, x, r, expected in SUBST:
        e_before, r_before = copy.deepcopy(e), copy.deepcopy(r)
        first = d0exp_pretty(d0exp_substitute(e, x, r))
        second = d0exp_pretty(d0exp_substitute(e, x, r))
        print(f"    input: {d0exp_pretty(e)}  [{x} := {d0exp_pretty(r)}]")
        report(label, first, expected)
        if e != e_before or r != r_before:
            failures += 1
            print("    FAIL: an input AST was mutated")
        if first != second:
            failures += 1
            print("    FAIL: repeated calls disagree")

    print(f"\n{failures} failure(s)")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
