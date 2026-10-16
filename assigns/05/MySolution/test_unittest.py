"""unittest suite for pretty printing and capture-avoiding substitution.

Run from assigns/05:
    python3 -m unittest discover -s MySolution -p 'test_unittest.py' -v
"""
from __future__ import annotations

import copy
import unittest
from unittest import mock

# lambda1_visitors puts the assignment directory on sys.path, so it is
# imported before lambda1_vp.
from lambda1_visitors import (
    d0exp_pretty, d0exp_substitute, d0exp_allnames, d0exp_rename,
    FreshNames, PrettyPrintVisitor, SubstitutionVisitor,
)
import lambda1_vp
from lambda1_vp import (
    d0exp_fvset, d0exp_evaluate, ENVnil, ENVcns, D0Vint,
    D0Elam, D0Elet, D0Efix, D0Epair, D0Eop2,
)
from shared_cases import (
    V, I, add,
    PRETTY_CONSTRUCTOR_CASES, PRETTY_NESTED_CASES, SUBST_CONSTRUCTOR_CASES,
    SHADOWING_CASES, CAPTURE_CASES, RENAMING_CASES, LET_INIT_BODY_CASES,
    ALL_SCOPE_CASES, FV_TARGET_FREE_CASES, FV_TARGET_NOT_FREE_CASES,
    SEMANTIC_CASES, NO_EVAL_CASES,
)


def _forbid(*args, **kwargs):
    raise AssertionError("evaluation was attempted")


class PrettyPrintTests(unittest.TestCase):
    def test_every_constructor(self):
        for label, e, expected in PRETTY_CONSTRUCTOR_CASES:
            with self.subTest(label):
                self.assertEqual(d0exp_pretty(e), expected)

    def test_nested_expressions(self):
        for label, e, expected in PRETTY_NESTED_CASES:
            with self.subTest(label):
                self.assertEqual(d0exp_pretty(e), expected)

    def test_single_line_without_surrounding_whitespace(self):
        for label, e, _ in PRETTY_CONSTRUCTOR_CASES + PRETTY_NESTED_CASES:
            with self.subTest(label):
                s = d0exp_pretty(e)
                self.assertEqual(s, s.strip())
                self.assertNotIn("\n", s)

    def test_visitor_dispatches_through_accept(self):
        e = add(V("a"), I(2))
        self.assertEqual(e.accept(PrettyPrintVisitor()), "(a + 2)")


class SubstitutionConstructorTests(unittest.TestCase):
    def test_every_constructor_structurally(self):
        for label, e, x, r, expected in SUBST_CONSTRUCTOR_CASES:
            with self.subTest(label):
                self.assertEqual(d0exp_substitute(e, x, r), expected)

    def test_matching_variable_returns_replacement(self):
        r = add(V("x"), I(1))
        self.assertIs(d0exp_substitute(V("x"), "x", r), r)

    def test_nonmatching_variable_is_unchanged(self):
        self.assertEqual(d0exp_substitute(V("y"), "x", I(3)), V("y"))

    def test_operator_and_constructor_preserved(self):
        result = d0exp_substitute(D0Eop2("<", V("x"), V("x")),
                                  "x", I(1))
        self.assertIs(type(result), D0Eop2)
        self.assertEqual(result.name, "<")


class ScopeTests(unittest.TestCase):
    def check(self, cases):
        for label, e, x, r, expected in cases:
            with self.subTest(label):
                self.assertEqual(d0exp_pretty(d0exp_substitute(e, x, r)),
                                 expected)

    def test_shadowing(self):
        self.check(SHADOWING_CASES)

    def test_shadowed_target_returns_equal_expression(self):
        for label, e, x, r, _ in SHADOWING_CASES:
            if x in d0exp_fvset(e):
                continue
            with self.subTest(label):
                self.assertEqual(d0exp_substitute(e, x, r), e)

    def test_capture_avoidance(self):
        self.check(CAPTURE_CASES)

    def test_formerly_free_name_is_not_captured(self):
        result = d0exp_substitute(D0Elam("y", add(V("x"), V("y"))), "x", V("y"))
        self.assertNotEqual(d0exp_pretty(result), "(lam y. (y + y))")
        self.assertIn("y", d0exp_fvset(result))

    def test_nested_shadowing_and_fresh_names(self):
        self.check(RENAMING_CASES)

    def test_let_initializer_versus_body(self):
        self.check(LET_INIT_BODY_CASES)


class HelperVisitorTests(unittest.TestCase):
    def test_allnames_includes_binders_and_bound_names(self):
        e = D0Elet("y", V("x"),
                   D0Elam("z", D0Efix("f", "n", V("w"))))
        self.assertEqual(d0exp_allnames(e), {"y", "x", "z", "f", "n", "w"})

    def test_fresh_names_skip_used_and_generated(self):
        names = FreshNames(frozenset({"y", "y_1"}))
        self.assertEqual(names.fresh("y"), "y_2")
        self.assertEqual(names.fresh("y"), "y_3")

    def test_rename_respects_shadowing(self):
        e = D0Epair(V("y"), D0Elam("y", V("y")))
        self.assertEqual(d0exp_pretty(d0exp_rename(e, "y", "q")),
                         "(pair q (lam y. y))")

    def test_rename_enters_let_initializer_only(self):
        e = D0Elet("y", V("y"), V("y"))
        self.assertEqual(d0exp_pretty(d0exp_rename(e, "y", "q")),
                         "(let y = q in y)")


class FreeVariablePropertyTests(unittest.TestCase):
    def test_target_free(self):
        for label, e, x, r in FV_TARGET_FREE_CASES:
            with self.subTest(label):
                self.assertIn(x, d0exp_fvset(e))
                result = d0exp_substitute(e, x, r)
                self.assertEqual(d0exp_fvset(result),
                                 (d0exp_fvset(e) - {x}) | d0exp_fvset(r))

    def test_target_not_free(self):
        for label, e, x, r in FV_TARGET_NOT_FREE_CASES:
            with self.subTest(label):
                self.assertNotIn(x, d0exp_fvset(e))
                result = d0exp_substitute(e, x, r)
                self.assertEqual(d0exp_fvset(result), d0exp_fvset(e))
                self.assertEqual(result, e)


class SemanticAgreementTests(unittest.TestCase):
    def test_substitution_matches_binding_in_environment(self):
        for label, e, x, r, bindings, expected in SEMANTIC_CASES:
            with self.subTest(label):
                env = ENVnil()
                for name, value in bindings.items():
                    env = ENVcns(name, D0Vint(value), env)
                env_x = ENVcns(x, d0exp_evaluate(r, env), env)
                self.assertEqual(d0exp_evaluate(e, env_x), D0Vint(expected))
                result = d0exp_substitute(e, x, r)
                self.assertEqual(d0exp_evaluate(result, env), D0Vint(expected))


class SafetyTests(unittest.TestCase):
    def all_subst_inputs(self):
        for label, e, x, r, _ in SUBST_CONSTRUCTOR_CASES + ALL_SCOPE_CASES:
            yield label, e, x, r

    def test_inputs_not_mutated(self):
        for label, e, x, r in self.all_subst_inputs():
            with self.subTest(label):
                e_before, r_before = copy.deepcopy(e), copy.deepcopy(r)
                d0exp_pretty(e)
                d0exp_substitute(e, x, r)
                self.assertEqual(e, e_before)
                self.assertEqual(r, r_before)

    def test_deterministic_across_calls(self):
        for label, e, x, r in self.all_subst_inputs():
            with self.subTest(label):
                first = d0exp_substitute(e, x, r)
                d0exp_substitute(D0Elam("y", add(V("x"), V("y"))), "x", V("y"))
                second = d0exp_substitute(e, x, r)
                self.assertEqual(first, second)
                self.assertEqual(d0exp_pretty(first), d0exp_pretty(second))

    def test_fresh_supply_is_per_call(self):
        e, x, r = D0Elam("y", add(V("x"), V("y"))), "x", V("y")
        names = FreshNames(frozenset({"x", "y"}))
        e.accept(SubstitutionVisitor(x, r, names))
        self.assertEqual(d0exp_pretty(d0exp_substitute(e, x, r)),
                         "(lam y_1. (y + y_1))")

    def test_no_evaluation(self):
        with mock.patch.object(lambda1_vp.EvaluateVisitor, "__init__", _forbid), \
             mock.patch.object(lambda1_vp, "d0exp_evaluate", _forbid):
            for label, e in NO_EVAL_CASES:
                with self.subTest(label):
                    self.assertIsInstance(d0exp_pretty(e), str)
                    result = d0exp_substitute(e, "x", I(0))
                    self.assertNotIn("x", d0exp_fvset(result))

    def test_division_by_zero_prints(self):
        self.assertEqual(d0exp_pretty(D0Eop2("/", I(1), I(0))),
                         "(1 / 0)")


if __name__ == "__main__":
    unittest.main()
