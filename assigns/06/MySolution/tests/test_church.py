"""Tests for church.py (ACC-05): every encoding run independently through
the shared evaluator and decoded with the observers.

Run from assigns/06:
    python3 -B -m unittest discover -s MySolution/tests -t MySolution -v
"""
from __future__ import annotations

import unittest

import church
from church import (
    TRUE, FALSE, num, I, PAIR, FST, SND, Z,
    SUCC, PRED, ISZERO, ADD, SUB, MUL,
    LT, LEQ, GT, GEQ, EQ, NEQ, NOT, AND, OR,
)
from evaluator import evaluate, Completed, Exhausted
from observers import NAT, BOOL, PairKind, Decoded, execute_and_observe
from target import Var, Lam, App, free_vars, is_pure

EXEC, OBS = 20_000, 20_000


def app(*terms):
    result = terms[0]
    for t in terms[1:]:
        result = App(result, t)
    return result


def lam(*parts):
    *params, body = parts
    for p in reversed(params):
        body = Lam(p, body)
    return body


def run(term, kind):
    """Execute then observe; return the decoded Python value."""
    report = execute_and_observe(term, kind, EXEC, OBS)
    assert isinstance(report.execution, Completed), report
    assert isinstance(report.observation, Decoded), report
    return report.observation.value


class LiteralTests(unittest.TestCase):
    def test_numerals(self):
        for n in range(6):
            with self.subTest(n=n):
                self.assertEqual(run(num(n), NAT), n)

    def test_numeral_shape(self):
        s, z = Var("s"), Var("z")
        self.assertEqual(num(0), lam("s", "z", z))
        self.assertEqual(num(2), lam("s", "z", App(s, App(s, z))))

    def test_numeral_rejects_bad_input(self):
        with self.assertRaises(ValueError):
            num(-1)
        for bad in (True, 2.0, "3"):
            with self.subTest(bad=bad):
                with self.assertRaises(TypeError):
                    num(bad)

    def test_booleans(self):
        self.assertIs(run(TRUE, BOOL), True)
        self.assertIs(run(FALSE, BOOL), False)

    def test_zero_and_false_share_a_representation(self):
        self.assertEqual(run(num(0), BOOL), False)
        self.assertEqual(run(FALSE, NAT), 0)


class ArithmeticTests(unittest.TestCase):
    def check(self, op, cases):
        for args, expected in cases:
            with self.subTest(op=op, args=args):
                term = app(op, *(num(n) for n in args))
                self.assertEqual(run(term, NAT), expected)

    def test_succ(self):
        self.check(SUCC, [((0,), 1), ((3,), 4)])

    def test_pred(self):
        self.check(PRED, [((0,), 0), ((1,), 0), ((5,), 4)])

    def test_add(self):
        self.check(ADD, [((0, 0), 0), ((2, 3), 5), ((0, 4), 4), ((4, 0), 4)])

    def test_truncated_sub(self):
        self.check(SUB, [((5, 2), 3), ((2, 5), 0), ((3, 3), 0),
                         ((4, 0), 4), ((0, 0), 0)])

    def test_mul(self):
        self.check(MUL, [((0, 3), 0), ((3, 0), 0), ((1, 5), 5), ((3, 4), 12)])

    def test_iszero(self):
        for n, expected in [(0, True), (1, False), (3, False)]:
            with self.subTest(n=n):
                self.assertIs(run(App(ISZERO, num(n)), BOOL), expected)


class ComparisonTests(unittest.TestCase):
    PAIRS = [(2, 3), (3, 3), (3, 2), (0, 0), (0, 1), (1, 0)]
    OPS = [
        ("<", LT, lambda m, n: m < n),
        ("<=", LEQ, lambda m, n: m <= n),
        (">", GT, lambda m, n: m > n),
        (">=", GEQ, lambda m, n: m >= n),
        ("==", EQ, lambda m, n: m == n),
        ("!=", NEQ, lambda m, n: m != n),
    ]

    def test_every_comparison(self):
        for name, op, expect in self.OPS:
            outcomes = set()
            for m, n in self.PAIRS:
                with self.subTest(op=name, m=m, n=n):
                    result = run(app(op, num(m), num(n)), BOOL)
                    self.assertIs(result, expect(m, n))
                    outcomes.add(result)
            self.assertEqual(outcomes, {True, False},
                             f"{name} must be tested with both outcomes")


class BooleanTests(unittest.TestCase):
    def test_not(self):
        self.assertIs(run(App(NOT, TRUE), BOOL), False)
        self.assertIs(run(App(NOT, FALSE), BOOL), True)

    def test_and_or_truth_tables(self):
        enc = {True: TRUE, False: FALSE}
        for p in (True, False):
            for q in (True, False):
                with self.subTest(p=p, q=q):
                    self.assertIs(run(app(AND, enc[p], enc[q]), BOOL), p and q)
                    self.assertIs(run(app(OR, enc[p], enc[q]), BOOL), p or q)


class PairTests(unittest.TestCase):
    def test_projections(self):
        pair = app(PAIR, num(2), TRUE)
        self.assertEqual(run(App(FST, pair), NAT), 2)
        self.assertIs(run(App(SND, pair), BOOL), True)

    def test_pair_observed_directly(self):
        self.assertEqual(run(app(PAIR, num(2), TRUE), PairKind(NAT, BOOL)),
                         (2, True))


class FixedPointTests(unittest.TestCase):
    def test_z_of_function_is_a_value_quickly(self):
        # Z F stops at a lambda instead of unfolding forever.
        result = evaluate(App(Z, lam("f", "x", Var("x"))), 10)
        self.assertIsInstance(result, Completed)
        self.assertIsInstance(result.value, Lam)

    def test_y_unfolds_forever_under_cbv(self):
        # Ordinary Y, for contrast: never reaches a value.
        g, x = Var("g"), Var("x")
        half = Lam("x", App(g, App(x, x)))
        y = Lam("g", App(half, half))
        self.assertEqual(evaluate(App(y, lam("f", "x", x)), 200),
                         Exhausted(200))

    def test_recursive_sum(self):
        # sum n = if n == 0 then 0 else n + sum (n - 1), with thunked branches
        f, n = Var("f"), Var("n")
        body = app(App(ISZERO, n),
                   Lam("u", num(0)),
                   Lam("u", app(ADD, n, App(f, App(PRED, n)))),
                   I)
        summer = App(Z, lam("f", "n", body))
        self.assertEqual(run(App(summer, num(4)), NAT), 10)


class LibraryShapeTests(unittest.TestCase):
    def test_every_combinator_closed_and_pure(self):
        self.assertTrue(church.COMBINATORS)
        for name, term in church.COMBINATORS.items():
            with self.subTest(name=name):
                self.assertTrue(is_pure(term))
                self.assertEqual(free_vars(term), frozenset())

    def test_numerals_closed_and_pure(self):
        for n in (0, 1, 7):
            self.assertTrue(is_pure(num(n)))
            self.assertEqual(free_vars(num(n)), frozenset())


if __name__ == "__main__":
    unittest.main()
