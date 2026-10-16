"""Example inputs and expected results shared by both test suites.

This module holds data only; test_unittest.py and test_pytest.py each
contain their own test logic and run independently.

Expected names follow the documented fresh-name policy: a conflicting
binder b becomes b_1, b_2, ... (the first candidate not already used).
"""
from __future__ import annotations

from lambda1_visitors import (
    D0Eint, D0Ebtf, D0Eop1, D0Eop2, D0Evar, D0Elam, D0Efix,
    D0Eapp, D0Eif0, D0Elet, D0Epair, D0Epfst, D0Epsnd,
)

V, I, B = D0Evar, D0Eint, D0Ebtf


def add(a, b):
    return D0Eop2("+", a, b)

########################################################################
# Pretty printing: (label, expression, expected string)
########################################################################

PRETTY_CONSTRUCTOR_CASES = [
    ("int", I(42), "42"),
    ("int zero", I(0), "0"),
    ("int negative", I(-7), "-7"),
    ("int large", I(123456789012345678901234567890),
     "123456789012345678901234567890"),
    ("int large negative", I(-10**30), "-1000000000000000000000000000000"),
    ("btf true", B(True), "true"),
    ("btf false", B(False), "false"),
    ("var", V("x_1"), "x_1"),
    ("op1 +1", D0Eop1("+1", V("x")), "(+1 x)"),
    ("op1 -1 negative", D0Eop1("-1", I(-3)), "(-1 -3)"),
    ("op2", D0Eop2("<=", I(1), V("y")), "(1 <= y)"),
    ("lam", D0Elam("x", V("x")), "(lam x. x)"),
    ("fix", D0Efix("f", "n", D0Eapp(V("f"), V("n"))), "(fix f(n). (f n))"),
    ("app", D0Eapp(V("f"), I(2)), "(f 2)"),
    ("if0", D0Eif0(B(True), I(1), I(2)), "(if true then 1 else 2)"),
    ("let", D0Elet("x", I(1), add(V("x"), V("x"))), "(let x = 1 in (x + x))"),
    ("pair", D0Epair(I(1), B(False)), "(pair 1 false)"),
    ("fst", D0Epfst(V("p")), "(fst p)"),
    ("snd", D0Epsnd(D0Epair(I(1), I(2))), "(snd (pair 1 2))"),
]

PRETTY_NESTED_CASES = [
    ("assignment example",
     D0Eapp(D0Elam("x", add(V("x"), I(1))), I(4)),
     "((lam x. (x + 1)) 4)"),
    ("factorial",
     D0Efix("fact", "n",
            D0Eif0(D0Eop2("<=", V("n"), I(0)),
                   I(1),
                   D0Eop2("*", V("n"),
                          D0Eapp(V("fact"), D0Eop2("-", V("n"), I(1)))))),
     "(fix fact(n). (if (n <= 0) then 1 else (n * (fact (n - 1)))))"),
    ("let with pair projections",
     D0Elet("p", D0Epair(I(-1), D0Elam("z", D0Eop1("-1", V("z")))),
            D0Eapp(D0Epsnd(V("p")), D0Epfst(V("p")))),
     "(let p = (pair -1 (lam z. (-1 z))) in ((snd p) (fst p)))"),
    ("division by zero", D0Eop2("/", I(1), I(0)), "(1 / 0)"),
]

########################################################################
# Substitution through every constructor:
# (label, expression, target, replacement, expected AST)
########################################################################

SEVEN = I(7)

SUBST_CONSTRUCTOR_CASES = [
    ("int", I(5), "x", SEVEN, I(5)),
    ("btf", B(True), "x", SEVEN, B(True)),
    ("var matching", V("x"), "x", SEVEN, I(7)),
    ("var nonmatching", V("y"), "x", SEVEN, V("y")),
    ("op1", D0Eop1("+1", V("x")), "x", SEVEN, D0Eop1("+1", I(7))),
    ("op2", D0Eop2("-", V("x"), V("y")), "x", SEVEN,
     D0Eop2("-", I(7), V("y"))),
    ("lam", D0Elam("y", add(V("x"), V("y"))), "x", SEVEN,
     D0Elam("y", add(I(7), V("y")))),
    ("fix", D0Efix("f", "n", add(V("x"), D0Eapp(V("f"), V("n")))), "x", SEVEN,
     D0Efix("f", "n", add(I(7), D0Eapp(V("f"), V("n"))))),
    ("app", D0Eapp(V("x"), V("x")), "x", SEVEN, D0Eapp(I(7), I(7))),
    ("if0", D0Eif0(V("x"), V("x"), V("z")), "x", SEVEN,
     D0Eif0(I(7), I(7), V("z"))),
    ("let", D0Elet("y", V("x"), add(V("x"), V("y"))), "x", SEVEN,
     D0Elet("y", I(7), add(I(7), V("y")))),
    ("pair", D0Epair(V("x"), V("y")), "x", SEVEN, D0Epair(I(7), V("y"))),
    ("fst", D0Epfst(V("x")), "x", SEVEN, D0Epfst(I(7))),
    ("snd", D0Epsnd(D0Epair(V("x"), V("x"))), "x", SEVEN,
     D0Epsnd(D0Epair(I(7), I(7)))),
    ("replacement contains target (no recursive substitution)",
     D0Eop2("*", V("x"), V("x")), "x", add(V("x"), I(1)),
     D0Eop2("*", add(V("x"), I(1)), add(V("x"), I(1)))),
    ("replacement contains target under a binder",
     D0Elam("y", D0Eapp(V("x"), V("y"))), "x", D0Eapp(V("x"), V("x")),
     D0Elam("y", D0Eapp(D0Eapp(V("x"), V("x")), V("y")))),
]

########################################################################
# Scope-sensitive cases: (label, expression, target, replacement,
# expected pretty-printed result)
########################################################################

SHADOWING_CASES = [
    ("lam binds target", D0Elam("x", add(V("x"), V("y"))), "x", I(3),
     "(lam x. (x + y))"),
    ("fix function name binds target", D0Efix("x", "n", D0Eapp(V("x"), V("n"))),
     "x", I(3), "(fix x(n). (x n))"),
    ("fix parameter binds target", D0Efix("f", "x", D0Eapp(V("f"), V("x"))),
     "x", I(3), "(fix f(x). (f x))"),
    ("fix f(f) binds target", D0Efix("f", "f", add(V("f"), I(1))),
     "f", I(3), "(fix f(f). (f + 1))"),
    ("fix f(f) with other target", D0Efix("f", "f", add(V("x"), V("f"))),
     "x", I(3), "(fix f(f). (3 + f))"),
    ("let body binds target", D0Elet("x", I(1), V("x")), "x", I(3),
     "(let x = 1 in x)"),
    ("shadowing only in one branch", D0Epair(V("x"), D0Elam("x", V("x"))),
     "x", I(3), "(pair 3 (lam x. x))"),
    ("no renaming when target is shadowed below",
     D0Elam("y", D0Elam("x", add(V("x"), V("y")))), "x", V("y"),
     "(lam y. (lam x. (x + y)))"),
]

CAPTURE_CASES = [
    ("lam", D0Elam("y", add(V("x"), V("y"))), "x", V("y"),
     "(lam y_1. (y + y_1))"),
    ("let", D0Elet("y", V("x"), add(V("x"), V("y"))), "x", V("y"),
     "(let y_1 = y in (y + y_1))"),
    ("fix function name",
     D0Efix("f", "n", add(V("x"), D0Eapp(V("f"), V("n")))), "x", V("f"),
     "(fix f_1(n). (f + (f_1 n)))"),
    ("fix parameter",
     D0Efix("f", "n", add(V("x"), D0Eapp(V("f"), V("n")))), "x", V("n"),
     "(fix f(n_1). (n + (f n_1)))"),
    ("fix both distinct binders",
     D0Efix("f", "n", add(V("x"), D0Eapp(V("f"), V("n")))),
     "x", add(V("f"), V("n")),
     "(fix f_1(n_1). ((f + n) + (f_1 n_1)))"),
    ("fix f(f): parameter shadows name",
     D0Efix("f", "f", add(V("x"), V("f"))), "x", V("f"),
     "(fix f_1(f_1). (f + f_1))"),
]

RENAMING_CASES = [
    ("rename stops at inner lam",
     D0Elam("y", D0Eapp(D0Eapp(V("x"), V("y")), D0Elam("y", V("y")))),
     "x", V("y"),
     "(lam y_1. ((y y_1) (lam y. y)))"),
    ("rename enters let initializer but not shadowed body",
     D0Elam("y", add(add(V("x"), V("y")), D0Elet("y", V("y"), V("y")))),
     "x", V("y"),
     "(lam y_1. ((y + y_1) + (let y = y_1 in y)))"),
    ("rename stops at inner fix",
     D0Elam("f", D0Eapp(D0Eapp(V("x"), V("f")),
                        D0Efix("f", "n", D0Eapp(V("f"), V("n"))))),
     "x", V("f"),
     "(lam f_1. ((f f_1) (fix f(n). (f n))))"),
    ("nested conflicting binders each renamed",
     D0Elam("y", D0Elam("y", add(V("x"), V("y")))), "x", V("y"),
     "(lam y_1. (lam y_2. (y + y_2)))"),
    ("fresh name avoids existing bound y_1",
     D0Elam("y", D0Elam("y_1", add(add(V("x"), V("y")), V("y_1")))),
     "x", V("y"),
     "(lam y_2. (lam y_1. ((y + y_2) + y_1)))"),
    ("fresh name avoids free y_1 in expression",
     D0Elam("y", add(add(V("x"), V("y")), V("y_1"))), "x", V("y"),
     "(lam y_2. ((y + y_2) + y_1))"),
    ("fresh name avoids y_1 in replacement",
     D0Elam("y", add(V("x"), V("y"))), "x", add(V("y"), V("y_1")),
     "(lam y_2. ((y + y_1) + y_2))"),
    ("fresh name avoids the target",
     D0Elam("y", add(V("y_1"), V("y"))), "y_1", V("y"),
     "(lam y_2. (y + y_2))"),
    ("fresh name avoids names generated earlier",
     D0Epair(D0Elam("y", add(V("x"), V("y"))),
             D0Elam("y", add(V("x"), V("y")))),
     "x", V("y"),
     "(pair (lam y_1. (y + y_1)) (lam y_2. (y + y_2)))"),
]

LET_INIT_BODY_CASES = [
    ("let-bound target: initializer substituted, body not",
     D0Elet("x", V("x"), add(V("x"), V("y"))), "x", I(3),
     "(let x = 3 in (x + y))"),
    ("let-bound target with compound initializer",
     D0Elet("x", add(V("x"), I(1)), V("x")), "x", I(5),
     "(let x = (5 + 1) in x)"),
    ("renaming changes body occurrences, not initializer",
     D0Elet("y", V("y"), add(V("x"), V("y"))), "x", V("y"),
     "(let y_1 = y in (y + y_1))"),
    ("no rename when target only in initializer",
     D0Elet("y", V("x"), V("y")), "x", V("y"),
     "(let y = y in y)"),
    ("rename when target in body",
     D0Elet("y", V("x"), V("x")), "x", V("y"),
     "(let y_1 = y in y)"),
]

ALL_SCOPE_CASES = (SHADOWING_CASES + CAPTURE_CASES + RENAMING_CASES
                   + LET_INIT_BODY_CASES)

########################################################################
# Free-variable property: (label, expression, target, replacement)
########################################################################

FV_TARGET_FREE_CASES = [
    ("lam capture", D0Elam("y", add(V("x"), V("y"))), "x", V("y")),
    ("let capture", D0Elet("y", V("x"), add(V("x"), V("y"))), "x", V("y")),
    ("fix both binders",
     D0Efix("f", "n", add(V("x"), D0Eapp(V("f"), V("n")))),
     "x", add(V("f"), V("n"))),
    ("fix f(f)", D0Efix("f", "f", add(V("x"), V("f"))), "x", V("f")),
    ("nested binders",
     D0Elam("y", D0Elam("y", add(V("x"), V("y")))), "x", V("y")),
    ("replacement contains target",
     D0Epair(V("x"), V("w")), "x", add(V("x"), V("z"))),
    ("closed replacement", D0Eapp(V("x"), V("q")), "x", D0Elam("a", V("a"))),
]

FV_TARGET_NOT_FREE_CASES = [
    ("literal", I(3), "x", V("y")),
    ("lam binds target", D0Elam("x", V("x")), "x", V("y")),
    ("target absent under conflicting binder", D0Elam("y", V("y")), "x", V("y")),
    ("let body binds target", D0Elet("x", V("z"), V("x")), "x", V("z")),
    ("fix binds target", D0Efix("x", "n", V("x")), "x", V("n")),
]

########################################################################
# Semantic agreement: evaluating e with x bound to r's value should
# match evaluating e[x := r]. (label, e, x, r, free-variable bindings,
# expected integer result). Evaluation happens only in the tests.
########################################################################

SEMANTIC_CASES = [
    ("lam capture", D0Eapp(D0Elam("y", add(V("x"), V("y"))), I(10)),
     "x", V("y"), {"y": 100}, 110),
    ("let capture", D0Elet("y", V("x"), add(V("x"), V("y"))),
     "x", V("y"), {"y": 5}, 10),
    ("fix function-name capture",
     D0Eapp(D0Efix("f", "n",
                   D0Eif0(D0Eop2("<=", V("n"), I(0)),
                          V("x"),
                          D0Eapp(V("f"), D0Eop2("-", V("n"), I(1))))),
            I(3)),
     "x", V("f"), {"f": 9}, 9),
    ("fix f(f)", D0Eapp(D0Efix("f", "f", add(V("x"), V("f"))), I(1)),
     "x", V("f"), {"f": 100}, 101),
]

########################################################################
# Expressions that would fail or diverge if evaluated: (label, expression)
########################################################################

NO_EVAL_CASES = [
    ("division by zero", D0Eop2("/", V("x"), I(0))),
    ("bool plus int", add(B(True), V("x"))),
    ("apply an integer", D0Eapp(I(3), V("x"))),
    ("project a non-pair", D0Epfst(V("x"))),
    ("non-bool condition", D0Eif0(I(7), V("x"), I(2))),
    ("unbound variable", add(V("nope"), V("x"))),
    ("divergent recursion",
     D0Eapp(D0Efix("f", "n", D0Eapp(V("f"), V("n"))), V("x"))),
]
