"""Tests for the target half of evaluator.py: weak left-to-right
call-by-value, beta-value step counting and budgets, determinism,
input preservation, and rejection of open or mixed inputs.

Run from assigns/06:
    python3 -B -m unittest discover -s MySolution/tests -t MySolution -v
"""
from __future__ import annotations

import copy
import unittest

from target import Var, Lam, App, pretty
from evaluator import evaluate, Completed, Exhausted, EvalError, TraceStep
from source import D0Eint, D0Evar, D0Elam, D0Eapp

x, y = Var("x"), Var("y")
I = Lam("x", x)
OMEGA_HALF = Lam("x", App(x, x))
OMEGA = App(OMEGA_HALF, OMEGA_HALF)


class ValueTests(unittest.TestCase):
    def test_acc02_no_reduction_under_lambda(self):
        term = Lam("x", App(Lam("y", y), x))
        self.assertEqual(evaluate(term, 10), Completed(term, 0))

    def test_value_completes_with_budget_zero(self):
        # ACC-03, first case
        self.assertEqual(evaluate(I, 0), Completed(I, 0))


class BudgetTests(unittest.TestCase):
    """ACC-03 boundaries, RED-03/RED-04."""

    def test_redex_with_budget_zero_exhausts(self):
        self.assertEqual(evaluate(App(I, I), 0), Exhausted(0))

    def test_value_on_last_permitted_step_completes(self):
        self.assertEqual(evaluate(App(I, I), 1), Completed(I, 1))

    def test_omega_exhausts_at_budget(self):
        for budget in (0, 1, 7, 100):
            with self.subTest(budget=budget):
                self.assertEqual(evaluate(OMEGA, budget), Exhausted(budget))

    def test_budget_must_be_nonnegative_int(self):
        with self.assertRaises(ValueError):
            evaluate(I, -1)
        for bad in (None, 1.5, True):
            with self.subTest(budget=bad):
                with self.assertRaises(TypeError):
                    evaluate(I, bad)


class OrderTests(unittest.TestCase):
    """ACC-02 trace and left-to-right call-by-value (RED-02)."""

    def test_acc02_trace_left_right_outer(self):
        trace: list[TraceStep] = []
        result = evaluate(App(App(I, I), App(I, I)), 10, trace=trace)
        self.assertEqual(result, Completed(I, 3))
        self.assertEqual([step.path for step in trace],
                         [("fn",), ("arg",), ()])
        self.assertEqual([step.step for step in trace], [1, 2, 3])
        for step in trace:
            self.assertEqual(step.redex, App(I, I))
            self.assertEqual(step.contractum, I)

    def test_function_evaluated_before_argument(self):
        # (I I) OMEGA: one step on the function, then the argument diverges.
        trace: list[TraceStep] = []
        result = evaluate(App(App(I, I), OMEGA), 5, trace=trace)
        self.assertEqual(result, Exhausted(5))
        self.assertEqual(trace[0].path, ("fn",))
        self.assertTrue(all(s.path == ("arg",) for s in trace[1:]))

    def test_argument_evaluated_before_substitution(self):
        # (lam x. lam y. y) OMEGA diverges under call-by-value even though
        # the argument is unused.
        self.assertEqual(evaluate(App(Lam("x", Lam("y", y)), OMEGA), 20),
                         Exhausted(20))

    def test_contractum_keeps_unevaluated_redex_under_lambda(self):
        # (lam x. lam y. (x y)) I  -->  lam y. (I y), not further reduced.
        result = evaluate(App(Lam("x", Lam("y", App(x, y))), I), 10)
        self.assertEqual(result, Completed(Lam("y", App(I, y)), 1))

    def test_k_combinator(self):
        k = Lam("a", Lam("b", Var("a")))
        k_i = Lam("z", Var("z"))
        result = evaluate(App(App(k, k_i), OMEGA_HALF), 10)
        self.assertEqual(result, Completed(k_i, 2))


class DeterminismTests(unittest.TestCase):
    """ACC-04 and RED-05."""

    TERMS = [
        App(App(I, I), App(I, I)),
        App(App(Lam("x", Lam("y", App(y, x))), I), I),
        OMEGA,
    ]

    def test_repeat_gives_same_outcome(self):
        for term in self.TERMS:
            with self.subTest(term=pretty(term)):
                t1, t2 = [], []
                self.assertEqual(evaluate(term, 25, trace=t1),
                                 evaluate(term, 25, trace=t2))
                self.assertEqual(t1, t2)

    def test_input_not_mutated(self):
        for term in self.TERMS:
            with self.subTest(term=pretty(term)):
                before = copy.deepcopy(term)
                evaluate(term, 25)
                self.assertEqual(term, before)


class RejectionTests(unittest.TestCase):
    def test_open_terms_rejected_before_running(self):
        for term in (x, App(I, y), App(App(I, I), Lam("z", y))):
            with self.subTest(term=pretty(term)):
                trace: list[TraceStep] = []
                with self.assertRaisesRegex(EvalError, "free variable"):
                    evaluate(term, 10, trace=trace)
                self.assertEqual(trace, [])

    def test_source_node_inside_target(self):
        with self.assertRaises(EvalError):
            evaluate(App(I, D0Eint(1)), 10)
        with self.assertRaises(EvalError):
            evaluate(Lam("x", D0Evar("x")), 10)

    def test_target_node_inside_source(self):
        with self.assertRaises(EvalError):
            evaluate(D0Eapp(D0Elam("x", D0Evar("x")), I))

    def test_non_syntax(self):
        with self.assertRaises(EvalError):
            evaluate(42, 10)

    def test_source_half_not_yet_implemented(self):
        # Milestone 1 placeholder; replaced when the source half lands.
        with self.assertRaises(NotImplementedError):
            evaluate(D0Eapp(D0Elam("x", D0Evar("x")), D0Eint(1)))


if __name__ == "__main__":
    unittest.main()
