"""Tests for observers.py (ACC-11, ACC-12, OBS-01, OBS-02): bounded pure
observation contexts, malformed outputs, and separate execution and
observation budgets.

Run from assigns/06:
    python3 -B -m unittest discover -s MySolution/tests -t MySolution -v
"""
from __future__ import annotations

import copy
import unittest

from church import TRUE, FALSE, num, PAIR, SUCC, ADD, MUL, NOT, AND
from evaluator import evaluate, Completed, Exhausted
from observers import (
    NAT, BOOL, PairKind, Decoded, Malformed, ObsExhausted,
    observe, observe_nat, observe_bool, execute_and_observe,
    STEP, BASE, MARK_TRUE, MARK_FALSE,
)
from target import Var, Lam, App, free_vars, is_pure, alpha_eq

OMEGA_HALF = Lam("x", App(Var("x"), Var("x")))
OMEGA = App(OMEGA_HALF, OMEGA_HALF)


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


def value_of(term, budget=10_000):
    result = evaluate(term, budget)
    assert isinstance(result, Completed), result
    return result.value


class ContextTests(unittest.TestCase):
    def test_contexts_closed_and_pure(self):
        for term in (STEP, BASE, MARK_TRUE, MARK_FALSE):
            self.assertTrue(is_pure(term))
            self.assertEqual(free_vars(term), frozenset())

    def test_markers_distinct(self):
        self.assertFalse(alpha_eq(MARK_TRUE, MARK_FALSE))


class NaturalObserverTests(unittest.TestCase):
    def test_literals(self):
        for n in (0, 1, 4):
            with self.subTest(n=n):
                result = observe_nat(num(n), 1_000)
                self.assertIsInstance(result, Decoded)
                self.assertEqual(result.value, n)

    def test_alpha_renamed_literal(self):
        a, b = Var("a"), Var("b")
        self.assertEqual(observe_nat(lam("a", "b", App(a, App(a, b))), 100).value, 2)
        # Binders named like the context's own binders.
        c, z = Var("c"), Var("z")
        self.assertEqual(observe_nat(lam("c", "z", App(c, z)), 100).value, 1)

    def test_computed_value_with_redexes_under_lambdas(self):
        v = value_of(App(SUCC, num(2)))
        # The value is not a normalized numeral: its body still has a redex.
        self.assertFalse(alpha_eq(v, num(3)))
        self.assertEqual(observe_nat(v, 1_000).value, 3)
        self.assertEqual(observe_nat(value_of(app(MUL, num(2), num(3))), 1_000).value, 6)
        self.assertEqual(observe_nat(value_of(app(ADD, num(0), num(0))), 1_000).value, 0)

    def test_reports_observation_steps(self):
        # num(2) STEP BASE: 2 to apply, then 2 STEP applications.
        self.assertEqual(observe_nat(num(2), 100), Decoded(2, 4))

    def test_malformed(self):
        s = Var("s")
        for label, v in [
            ("boolean true", TRUE),
            ("tail not a spine node", lam("s", "z", App(s, Lam("q", Var("q"))))),
            ("three lambdas", lam("s", "z", "w", Var("w"))),
        ]:
            with self.subTest(label):
                self.assertIsInstance(observe_nat(v, 1_000), Malformed)

    def test_budget_exhaustion(self):
        self.assertEqual(observe_nat(num(3), 0), ObsExhausted(0))
        self.assertEqual(observe_nat(num(3), 2), ObsExhausted(2))
        diverging = lam("s", "z", OMEGA)
        self.assertEqual(observe_nat(diverging, 50), ObsExhausted(50))

    def test_rejects_non_value(self):
        with self.assertRaises(ValueError):
            observe_nat(App(SUCC, num(1)), 100)


class BooleanObserverTests(unittest.TestCase):
    def test_literals(self):
        self.assertEqual(observe_bool(TRUE, 100), Decoded(True, 2))
        self.assertEqual(observe_bool(FALSE, 100), Decoded(False, 2))

    def test_alpha_renamed(self):
        self.assertIs(observe_bool(lam("p", "q", Var("q")), 100).value, False)

    def test_computed(self):
        self.assertIs(observe_bool(value_of(App(NOT, FALSE)), 100).value, True)
        self.assertIs(observe_bool(value_of(app(AND, TRUE, FALSE)), 100).value, False)

    def test_church_zero_under_both_kinds(self):
        self.assertEqual(observe_bool(num(0), 100).value, False)
        self.assertEqual(observe_nat(num(0), 100).value, 0)

    def test_malformed(self):
        for label, v in [("numeral one", num(1)), ("numeral two", num(2)),
                         ("identity", Lam("x", Var("x")))]:
            with self.subTest(label):
                self.assertIsInstance(observe_bool(v, 100), Malformed)

    def test_budget_exhaustion(self):
        self.assertEqual(observe_bool(TRUE, 1), ObsExhausted(1))
        self.assertEqual(observe_bool(lam("t", "f", OMEGA), 30), ObsExhausted(30))


class PairObserverTests(unittest.TestCase):
    def test_acc12_nested_pair(self):
        term = app(PAIR, app(PAIR, num(2), TRUE), num(3))
        kind = PairKind(PairKind(NAT, BOOL), NAT)
        report = execute_and_observe(term, kind, 1_000, 1_000)
        self.assertIsInstance(report.execution, Completed)
        self.assertEqual(report.observation.value, ((2, True), 3))

    def test_wrong_component_kind_is_malformed(self):
        v = value_of(app(PAIR, TRUE, num(2)))
        self.assertIsInstance(observe(v, PairKind(NAT, NAT), 1_000), Malformed)

    def test_projections_use_observation_budget(self):
        report = execute_and_observe(app(PAIR, num(2), TRUE),
                                     PairKind(NAT, BOOL), 1_000, 3)
        self.assertIsInstance(report.execution, Completed)
        self.assertEqual(report.observation, ObsExhausted(3))

    def test_diverging_component_exhausts_execution(self):
        for term in (app(PAIR, OMEGA, TRUE), app(PAIR, num(2), OMEGA)):
            with self.subTest():
                report = execute_and_observe(term, PairKind(NAT, BOOL), 100, 1_000)
                self.assertEqual(report.execution, Exhausted(100))
                self.assertIsNone(report.observation)


class ExecuteAndObserveTests(unittest.TestCase):
    def test_counts_reported_separately(self):
        report = execute_and_observe(App(SUCC, num(1)), NAT, 100, 100)
        self.assertEqual(report.execution.steps, 1)
        self.assertEqual(report.observation.value, 2)
        self.assertGreater(report.observation.steps, 0)

    def test_execution_exhaustion_skips_observation(self):
        report = execute_and_observe(OMEGA, NAT, 40, 100)
        self.assertEqual(report.execution, Exhausted(40))
        self.assertIsNone(report.observation)

    def test_input_not_mutated_and_deterministic(self):
        term = app(PAIR, app(ADD, num(1), num(2)), TRUE)
        before = copy.deepcopy(term)
        kind = PairKind(NAT, BOOL)
        first = execute_and_observe(term, kind, 1_000, 1_000)
        self.assertEqual(first, execute_and_observe(term, kind, 1_000, 1_000))
        self.assertEqual(term, before)


if __name__ == "__main__":
    unittest.main()
