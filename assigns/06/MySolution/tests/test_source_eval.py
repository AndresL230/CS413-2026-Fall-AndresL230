"""Tests for the source half of the shared evaluator: substitution-based
left-to-right call-by-value with the source-language rules.

Run from assigns/06:
    python3 -B -m unittest discover -s MySolution/tests -t MySolution -v
"""
from __future__ import annotations

import copy
import unittest

from evaluator import evaluate, Completed, EvalError
from source import D0Eint, D0Ebtf, D0Efix, D0Elam, D0Eop1, D0Eop2
from examples import (
    V, N, B, TRUE_, FALSE_, op, app, lam, if_, let, pair, fst, snd, not_,
    LOOP, FACT, FIB,
)
from pipeline import to_python


def value(expr):
    result = evaluate(expr)
    assert isinstance(result, Completed), result
    return to_python(result.value)


class SourceRuleTests(unittest.TestCase):
    def test_literals(self):
        self.assertEqual(value(N(0)), 0)
        self.assertEqual(value(N(7)), 7)
        self.assertIs(value(TRUE_), True)
        self.assertIs(value(FALSE_), False)

    def test_truncated_subtraction(self):
        self.assertEqual(value(op("-", N(2), N(5))), 0)
        self.assertEqual(value(op("-", N(5), N(2))), 3)
        self.assertEqual(value(op("-", N(0), N(1))), 0)

    def test_application_and_let(self):
        self.assertEqual(value(app(lam("x", op("+", V("x"), N(1))), N(4))), 5)
        self.assertEqual(value(let("x", N(3), app(lam("y", op("+", V("x"), V("y"))), N(4)))), 7)

    def test_let_initializer_scope(self):
        # let x = 1 in let x = x + 1 in x  ==>  2
        self.assertEqual(value(let("x", N(1), let("x", op("+", V("x"), N(1)), V("x")))), 2)

    def test_closures_are_lexical(self):
        # let y = 1 in let f = lam x. x + y in let y = 10 in f 0  ==>  1
        prog = let("y", N(1), let("f", lam("x", op("+", V("x"), V("y"))),
                                   let("y", N(10), app(V("f"), N(0)))))
        self.assertEqual(value(prog), 1)

    def test_pairs(self):
        self.assertEqual(value(pair(N(1), pair(TRUE_, N(2)))), (1, (True, 2)))
        self.assertEqual(value(fst(pair(N(2), TRUE_))), 2)
        self.assertIs(value(snd(pair(N(2), TRUE_))), True)

    def test_coincident_fix_binders(self):
        # (fix f(f). f) 3  ==>  3: only the parameter is substituted.
        self.assertEqual(value(app(D0Efix("f", "f", V("f")), N(3))), 3)

    def test_distinct_fix_binders(self):
        self.assertEqual(value(app(FACT, N(4))), 24)
        self.assertEqual(value(app(FIB, N(5))), 5)

    def test_fix_value_is_not_unfolded(self):
        result = evaluate(FACT)
        self.assertEqual(result, Completed(FACT, 0))

    def test_short_circuit_and_unselected_branches(self):
        self.assertIs(value(op("and", FALSE_, LOOP)), False)
        self.assertIs(value(op("or", TRUE_, LOOP)), True)
        self.assertEqual(value(if_(TRUE_, N(1), LOOP)), 1)
        self.assertEqual(value(if_(FALSE_, LOOP, N(2))), 2)

    def test_steps_counted(self):
        # one application, one let
        self.assertEqual(evaluate(let("x", N(1), app(lam("y", V("y")), V("x")))),
                         Completed(N(1), 2))


class SourceErrorTests(unittest.TestCase):
    def test_unbound_variable(self):
        with self.assertRaisesRegex(EvalError, "unbound"):
            evaluate(V("x"))

    def test_type_errors(self):
        for expr in (if_(N(1), N(2), N(3)), op("+", TRUE_, N(1)),
                     app(N(1), N(2)), fst(N(1)), not_(N(0)),
                     op("and", N(1), TRUE_)):
            with self.subTest(expr=expr):
                with self.assertRaises(EvalError):
                    evaluate(expr)

    def test_unsupported_input_rejected_even_when_unused(self):
        for expr in (N(-1), if_(TRUE_, N(1), op("/", N(1), N(0))),
                     lam("x", D0Eop1("-1", V("x"))), D0Eint(True)):
            with self.subTest(expr=expr):
                with self.assertRaises(EvalError):
                    evaluate(expr)

    def test_budget_not_accepted_for_source(self):
        with self.assertRaises(TypeError):
            evaluate(N(1), 10)

    def test_divergence_reported_as_error(self):
        with self.assertRaisesRegex(EvalError, "recursion"):
            evaluate(LOOP)


class SourceInputTests(unittest.TestCase):
    def test_input_not_mutated(self):
        prog = app(FACT, N(3))
        before = copy.deepcopy(prog)
        evaluate(prog)
        self.assertEqual(prog, before)


if __name__ == "__main__":
    unittest.main()
