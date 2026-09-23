"""Tests for pairs and projections in LAMBDA0.

Run with: python3 TEST/test02_lambda0.py   (or: cd TEST && make)
Requires Python 3.12 or later, like lambda0.py.
"""

import sys
import unittest
from pathlib import Path

# Import MySolution/lambda0.py, not the starter file one level up.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import lambda0
from lambda0 import (
    T0Mint, T0Mbtf, T0Mstr, T0Mvar, T0Mlam, T0Mfix, T0Mapp, T0Mif0, T0Mop1, T0Mop2,
    T0Mpair, T0Mpfst, T0Mpsnd,
    t0erm_size, t0erm_fvset, t0erm_subst0, t0erm_cbv_evaluate0,
)

DIV_BY_ZERO = T0Mop2("/", T0Mint(1), T0Mint(0))
BAD_NEGATION = T0Mop1("-", T0Mstr("bad"))  # raises TypeError when evaluated

# swap = lambda p. (snd p, fst p)
SWAP = T0Mlam("p", T0Mpair(T0Mpsnd(T0Mvar("p")), T0Mpfst(T0Mvar("p"))))


class TestImportsSolution(unittest.TestCase):
    def test_imports_mysolution_copy(self):
        here = Path(__file__).resolve().parents[1]
        self.assertEqual(Path(lambda0.__file__).resolve(), here / "lambda0.py")


class TestSize(unittest.TestCase):
    def test_spec_example(self):
        self.assertEqual(t0erm_size(T0Mpair(T0Mint(1), T0Mint(2))), 3)

    def test_projections(self):
        pair = T0Mpair(T0Mint(1), T0Mint(2))
        self.assertEqual(t0erm_size(T0Mpfst(pair)), 4)
        self.assertEqual(t0erm_size(T0Mpsnd(pair)), 4)
        self.assertEqual(t0erm_size(T0Mpfst(T0Mvar("x"))), 2)

    def test_nested(self):
        # ((1, x), snd y) -> pair + pair + 1 + x + snd + y = 6
        term = T0Mpair(T0Mpair(T0Mint(1), T0Mvar("x")), T0Mpsnd(T0Mvar("y")))
        self.assertEqual(t0erm_size(term), 6)

    def test_inside_other_constructs(self):
        # lambda p. fst p + snd p -> lam + op2 + fst + p + snd + p = 6
        term = T0Mlam("p", T0Mop2("+", T0Mpfst(T0Mvar("p")), T0Mpsnd(T0Mvar("p"))))
        self.assertEqual(t0erm_size(term), 6)
        self.assertEqual(t0erm_size(SWAP), 6)


class TestFvset(unittest.TestCase):
    def test_spec_example(self):
        term = T0Mpfst(T0Mpair(T0Mvar("x"), T0Mvar("y")))
        self.assertEqual(t0erm_fvset(term), frozenset({"x", "y"}))

    def test_closed_pair(self):
        self.assertEqual(t0erm_fvset(T0Mpair(T0Mint(1), T0Mstr("s"))), frozenset())

    def test_projection_operand(self):
        self.assertEqual(t0erm_fvset(T0Mpsnd(T0Mvar("z"))), frozenset({"z"}))

    def test_nested(self):
        term = T0Mpair(T0Mpair(T0Mvar("a"), T0Mpfst(T0Mvar("b"))), T0Mpsnd(T0Mvar("a")))
        self.assertEqual(t0erm_fvset(term), frozenset({"a", "b"}))

    def test_binders_still_bind(self):
        self.assertEqual(t0erm_fvset(SWAP), frozenset())
        term = T0Mlam("x", T0Mpair(T0Mvar("x"), T0Mvar("y")))
        self.assertEqual(t0erm_fvset(term), frozenset({"y"}))
        term = T0Mfix("f", "x", T0Mpair(T0Mapp(T0Mvar("f"), T0Mvar("x")), T0Mvar("g")))
        self.assertEqual(t0erm_fvset(term), frozenset({"g"}))


class TestSubst(unittest.TestCase):
    def test_both_pair_components(self):
        term = T0Mpair(T0Mvar("x"), T0Mpair(T0Mint(0), T0Mvar("x")))
        expected = T0Mpair(T0Mint(7), T0Mpair(T0Mint(0), T0Mint(7)))
        self.assertEqual(t0erm_subst0(term, "x", T0Mint(7)), expected)

    def test_projection_operands(self):
        pair = T0Mpair(T0Mint(1), T0Mint(2))
        self.assertEqual(t0erm_subst0(T0Mpfst(T0Mvar("p")), "p", pair), T0Mpfst(pair))
        self.assertEqual(t0erm_subst0(T0Mpsnd(T0Mvar("p")), "p", pair), T0Mpsnd(pair))

    def test_other_variables_untouched(self):
        term = T0Mpair(T0Mvar("x"), T0Mvar("y"))
        self.assertEqual(t0erm_subst0(term, "x", T0Mint(1)), T0Mpair(T0Mint(1), T0Mvar("y")))

    def test_under_lambda(self):
        # Free x is replaced under a binder for a different variable.
        term = T0Mlam("y", T0Mpair(T0Mvar("x"), T0Mpfst(T0Mvar("y"))))
        expected = T0Mlam("y", T0Mpair(T0Mint(3), T0Mpfst(T0Mvar("y"))))
        self.assertEqual(t0erm_subst0(term, "x", T0Mint(3)), expected)

    def test_shadowed_by_lambda(self):
        term = T0Mlam("x", T0Mpair(T0Mvar("x"), T0Mpsnd(T0Mvar("x"))))
        self.assertEqual(t0erm_subst0(term, "x", T0Mint(3)), term)

    def test_under_fix(self):
        term = T0Mfix("f", "n", T0Mpair(T0Mvar("n"), T0Mpsnd(T0Mvar("k"))))
        tsub = T0Mpair(T0Mint(1), T0Mint(2))
        expected = T0Mfix("f", "n", T0Mpair(T0Mvar("n"), T0Mpsnd(tsub)))
        self.assertEqual(t0erm_subst0(term, "k", tsub), expected)

    def test_shadowed_by_fix(self):
        term = T0Mfix("f", "n", T0Mpair(T0Mvar("f"), T0Mvar("n")))
        self.assertEqual(t0erm_subst0(term, "f", T0Mint(0)), term)
        self.assertEqual(t0erm_subst0(term, "n", T0Mint(0)), term)


class TestEvaluate(unittest.TestCase):
    def test_spec_example(self):
        term = T0Mpsnd(T0Mpair(T0Mint(1), T0Mop2("+", T0Mint(2), T0Mint(3))))
        self.assertEqual(t0erm_cbv_evaluate0(term), T0Mint(5))

    def test_components_are_evaluated(self):
        term = T0Mpair(T0Mop2("*", T0Mint(3), T0Mint(4)), T0Mop2("<", T0Mint(1), T0Mint(2)))
        value = t0erm_cbv_evaluate0(term)
        self.assertEqual(value, T0Mpair(T0Mint(12), T0Mbtf(True)))
        self.assertEqual(t0erm_cbv_evaluate0(T0Mpfst(term)), T0Mint(12))
        self.assertEqual(t0erm_cbv_evaluate0(T0Mpsnd(term)), T0Mbtf(True))

    def test_pair_of_values_is_value(self):
        value = T0Mpair(T0Mint(1), T0Mstr("a"))
        self.assertEqual(t0erm_cbv_evaluate0(value), value)

    def test_nested_pairs(self):
        inner = T0Mpair(T0Mop2("-", T0Mint(5), T0Mint(2)), T0Mint(4))
        term = T0Mpair(inner, T0Mpair(T0Mint(6), inner))
        self.assertEqual(t0erm_cbv_evaluate0(T0Mpfst(T0Mpfst(term))), T0Mint(3))
        self.assertEqual(t0erm_cbv_evaluate0(T0Mpsnd(T0Mpsnd(T0Mpsnd(term)))), T0Mint(4))
        self.assertEqual(
            t0erm_cbv_evaluate0(term),
            T0Mpair(T0Mpair(T0Mint(3), T0Mint(4)),
                    T0Mpair(T0Mint(6), T0Mpair(T0Mint(3), T0Mint(4)))))

    def test_mixed_value_kinds(self):
        fn = T0Mlam("x", T0Mop2("+", T0Mvar("x"), T0Mint(1)))
        term = T0Mpair(T0Mpair(T0Mbtf(False), T0Mstr("s")), fn)
        self.assertEqual(t0erm_cbv_evaluate0(term), term)
        # (snd term) 41 == 42: a function stored in a pair can be applied.
        self.assertEqual(t0erm_cbv_evaluate0(T0Mapp(T0Mpsnd(term), T0Mint(41))), T0Mint(42))
        cond = T0Mif0(T0Mpfst(T0Mpfst(term)), T0Mint(1), T0Mint(0))
        self.assertEqual(t0erm_cbv_evaluate0(cond), T0Mint(0))

    def test_function_accepting_pair(self):
        term = T0Mapp(SWAP, T0Mpair(T0Mint(1), T0Mop2("+", T0Mint(1), T0Mint(1))))
        self.assertEqual(t0erm_cbv_evaluate0(term), T0Mpair(T0Mint(2), T0Mint(1)))

    def test_function_returning_pair(self):
        # dup = lambda x. (x, x * x)
        dup = T0Mlam("x", T0Mpair(T0Mvar("x"), T0Mop2("*", T0Mvar("x"), T0Mvar("x"))))
        term = T0Mapp(dup, T0Mop2("+", T0Mint(2), T0Mint(3)))
        self.assertEqual(t0erm_cbv_evaluate0(term), T0Mpair(T0Mint(5), T0Mint(25)))

    def test_curried_function_building_pair(self):
        mk = T0Mlam("a", T0Mlam("b", T0Mpair(T0Mvar("a"), T0Mvar("b"))))
        term = T0Mpsnd(T0Mapp(T0Mapp(mk, T0Mint(1)), T0Mstr("two")))
        self.assertEqual(t0erm_cbv_evaluate0(term), T0Mstr("two"))

    def test_recursive_function_with_pairs(self):
        # fib2 n = if n <= 0 then (0, 1) else let p = fib2 (n-1) in (snd p, fst p + snd p)
        step = T0Mlam("p", T0Mpair(
            T0Mpsnd(T0Mvar("p")),
            T0Mop2("+", T0Mpfst(T0Mvar("p")), T0Mpsnd(T0Mvar("p")))))
        fib2 = T0Mfix("f", "n", T0Mif0(
            T0Mop2("<=", T0Mvar("n"), T0Mint(0)),
            T0Mpair(T0Mint(0), T0Mint(1)),
            T0Mapp(step, T0Mapp(T0Mvar("f"), T0Mop2("-", T0Mvar("n"), T0Mint(1))))))
        term = T0Mpfst(T0Mapp(fib2, T0Mint(10)))
        self.assertEqual(t0erm_cbv_evaluate0(term), T0Mint(55))

    def test_projection_of_non_pair(self):
        for operand in [T0Mint(1), T0Mbtf(True), T0Mstr("p"),
                        T0Mlam("x", T0Mvar("x")), T0Mop2("+", T0Mint(1), T0Mint(2))]:
            for proj in (T0Mpfst, T0Mpsnd):
                with self.subTest(proj=proj.__name__, operand=operand):
                    with self.assertRaises(TypeError):
                        t0erm_cbv_evaluate0(proj(operand))

    def test_left_component_evaluated_first(self):
        # Left raises ZeroDivisionError, right raises TypeError: left must win.
        with self.assertRaises(ZeroDivisionError):
            t0erm_cbv_evaluate0(T0Mpair(DIV_BY_ZERO, BAD_NEGATION))
        with self.assertRaises(TypeError):
            t0erm_cbv_evaluate0(T0Mpair(BAD_NEGATION, DIV_BY_ZERO))

    def test_unselected_component_is_evaluated(self):
        # Spec example: fst (1, 1/0) raises rather than returning 1.
        with self.assertRaises(ZeroDivisionError):
            t0erm_cbv_evaluate0(T0Mpfst(T0Mpair(T0Mint(1), DIV_BY_ZERO)))
        with self.assertRaises(ZeroDivisionError):
            t0erm_cbv_evaluate0(T0Mpsnd(T0Mpair(DIV_BY_ZERO, T0Mint(1))))

    def test_error_inside_pair_argument(self):
        # The argument pair is evaluated before substitution (call-by-value).
        term = T0Mapp(T0Mlam("p", T0Mint(0)), T0Mpair(T0Mint(1), DIV_BY_ZERO))
        with self.assertRaises(ZeroDivisionError):
            t0erm_cbv_evaluate0(term)


if __name__ == "__main__":
    unittest.main()
