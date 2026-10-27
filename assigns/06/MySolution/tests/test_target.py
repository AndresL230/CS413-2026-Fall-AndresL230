"""Tests for target.py: printer, free variables, renaming, substitution,
alpha-equivalence, and purity checks on the three-form target AST.

Run from assigns/06:
    python3 -B -m unittest discover -s MySolution/tests -t MySolution -v
"""
from __future__ import annotations

import copy
import unittest

from target import (
    Var, Lam, App, FreshNames,
    pretty, free_vars, all_names, rename, substitute, alpha_eq, is_pure,
)

x, y, z, f, a = Var("x"), Var("y"), Var("z"), Var("f"), Var("a")


def app(*terms):
    """Left-nested application: app(f, a, b) == ((f a) b)."""
    result = terms[0]
    for t in terms[1:]:
        result = App(result, t)
    return result


class PrinterTests(unittest.TestCase):
    """ACC-13: exact recursive formats from TGT-02."""

    def test_variable(self):
        self.assertEqual(pretty(Var("x")), "x")

    def test_abstraction(self):
        self.assertEqual(pretty(Lam("x", Var("x"))), "(lam x. x)")

    def test_application(self):
        self.assertEqual(pretty(App(f, a)), "(f a)")

    def test_nested(self):
        term = App(Lam("x", App(x, x)), Lam("y", Lam("z", app(y, z, x))))
        self.assertEqual(pretty(term),
                         "((lam x. (x x)) (lam y. (lam z. ((y z) x))))")

    def test_applications_nest_left_as_built(self):
        self.assertEqual(pretty(app(f, a, z)), "((f a) z)")
        self.assertEqual(pretty(App(f, App(a, z))), "(f (a z))")


class FreeVariableTests(unittest.TestCase):
    def test_var(self):
        self.assertEqual(free_vars(x), {"x"})

    def test_lam_binds_param(self):
        self.assertEqual(free_vars(Lam("x", App(x, y))), {"y"})

    def test_app_unions(self):
        self.assertEqual(free_vars(App(x, Lam("y", App(y, z)))), {"x", "z"})

    def test_inner_shadowing(self):
        # lam x. (lam x. x) x  -- both occurrences are bound
        self.assertEqual(free_vars(Lam("x", App(Lam("x", x), x))), set())

    def test_all_names_includes_binders(self):
        self.assertEqual(all_names(Lam("x", App(y, Lam("z", z)))),
                         {"x", "y", "z"})


class FreshNameTests(unittest.TestCase):
    def test_first_unused_suffix(self):
        names = FreshNames(frozenset({"y", "y_1"}))
        self.assertEqual(names.fresh("y"), "y_2")
        self.assertEqual(names.fresh("y"), "y_3")


class RenameTests(unittest.TestCase):
    def test_renames_free_occurrences_only(self):
        term = App(x, Lam("x", x))
        self.assertEqual(rename(term, "x", "w"), App(Var("w"), Lam("x", x)))


class SubstitutionTests(unittest.TestCase):
    def test_acc01_capture_avoided(self):
        # (lam y. x)[x := y]  ~  lam fresh. y, with y still free
        result = substitute(Lam("y", x), "x", y)
        self.assertIsInstance(result, Lam)
        self.assertNotEqual(result.param, "y")
        self.assertEqual(result.body, y)
        self.assertTrue(alpha_eq(result, Lam("w", y)))
        self.assertEqual(free_vars(result), {"y"})
        # Documented policy: first unused of y_1, y_2, ...
        self.assertEqual(pretty(result), "(lam y_1. y)")

    def test_binder_shadows_target(self):
        term = Lam("x", App(x, y))
        self.assertIs(substitute(term, "x", z), term)

    def test_target_not_free_no_rename(self):
        term = Lam("y", y)
        self.assertIs(substitute(term, "x", y), term)

    def test_replacement_with_several_free_vars(self):
        # (lam y. lam z. x (y z))[x := (y z)]
        term = Lam("y", Lam("z", App(x, App(y, z))))
        result = substitute(term, "x", App(y, z))
        self.assertEqual(pretty(result),
                         "(lam y_1. (lam z_1. ((y z) (y_1 z_1))))")
        self.assertEqual(free_vars(result), {"y", "z"})
        self.assertTrue(alpha_eq(
            result, Lam("p", Lam("q", App(App(y, z), App(Var("p"), Var("q")))))))

    def test_fresh_name_skips_existing(self):
        term = Lam("y", Lam("y_1", app(x, y, Var("y_1"))))
        result = substitute(term, "x", y)
        self.assertEqual(pretty(result), "(lam y_2. (lam y_1. ((y y_2) y_1)))")

    def test_rename_respects_nested_shadowing(self):
        term = Lam("y", App(App(x, y), Lam("y", y)))
        self.assertEqual(pretty(substitute(term, "x", y)),
                         "(lam y_1. ((y y_1) (lam y. y)))")

    def test_replacement_mentions_target(self):
        self.assertEqual(substitute(x, "x", App(x, x)), App(x, x))

    def test_distributes_over_application(self):
        self.assertEqual(substitute(app(x, y, x), "x", z), app(z, y, z))

    def test_closed_replacement_never_renames(self):
        ident = Lam("y", y)
        term = Lam("y", App(x, y))
        self.assertEqual(substitute(term, "x", ident), Lam("y", App(ident, y)))

    def test_deterministic(self):
        term = Lam("y", Lam("z", App(x, App(y, z))))
        self.assertEqual(substitute(term, "x", App(y, z)),
                         substitute(term, "x", App(y, z)))

    def test_inputs_not_mutated(self):
        term = Lam("y", Lam("z", App(x, App(y, z))))
        repl = App(y, z)
        term_before, repl_before = copy.deepcopy(term), copy.deepcopy(repl)
        substitute(term, "x", repl)
        self.assertEqual(term, term_before)
        self.assertEqual(repl, repl_before)


class AlphaEquivalenceTests(unittest.TestCase):
    def test_renamed_binders(self):
        self.assertTrue(alpha_eq(Lam("x", Lam("y", x)), Lam("a", Lam("b", a))))

    def test_different_binding_structure(self):
        self.assertFalse(alpha_eq(Lam("x", Lam("y", x)), Lam("x", Lam("y", y))))

    def test_shadowed_binder(self):
        # lam x. lam y. x  vs  lam y. lam y. y : second refers to inner binder
        self.assertFalse(alpha_eq(Lam("x", Lam("y", x)), Lam("y", Lam("y", y))))

    def test_free_names_must_match(self):
        self.assertTrue(alpha_eq(Lam("x", y), Lam("w", y)))
        self.assertFalse(alpha_eq(Lam("x", y), Lam("x", z)))

    def test_free_vs_bound(self):
        self.assertFalse(alpha_eq(Lam("x", y), Lam("y", y)))

    def test_shape_mismatch(self):
        self.assertFalse(alpha_eq(App(x, y), Lam("x", y)))


class PurityTests(unittest.TestCase):
    def test_pure(self):
        self.assertTrue(is_pure(App(Lam("x", x), Lam("y", App(y, z)))))

    def test_foreign_node(self):
        self.assertFalse(is_pure(App(Lam("x", x), 3)))
        self.assertFalse(is_pure(Lam("x", "not a term")))


if __name__ == "__main__":
    unittest.main()
