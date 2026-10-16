"""Free-variable analysis and the real Lint and Interpret tools, in process."""
import unittest
from pathlib import Path

from lambda_workbench import lambda1 as L
from lambda_workbench.contract import Outcome
from lambda_workbench.tools import contains_error_value, interpret_source, lint_source

EXAMPLES = Path(__file__).resolve().parent.parent / "examples"

X, Y, F = L.D0Evar("x"), L.D0Evar("y"), L.D0Evar("f")
ONE = L.D0Eint(1)


def example(name: str) -> str:
    return (EXAMPLES / name).read_text(encoding="utf-8")


def factorial(n: int) -> str:
    return example("factorial.lambda").replace("D0Eint(5))", f"D0Eint({n}))")


def fibonacci(n: int) -> str:
    return example("fibonacci.lambda").replace("D0Eint(10))", f"D0Eint({n}))")


class FreeVariables(unittest.TestCase):
    def assertFree(self, dexp, expected):
        result = L.d0exp_fvset(dexp)
        self.assertIsInstance(result, frozenset)
        self.assertEqual(result, frozenset(expected))

    def test_literals_have_no_free_variables(self):
        self.assertFree(L.D0Eint(3), [])
        self.assertFree(L.D0Ebtf(False), [])

    def test_variable_is_free(self):
        self.assertFree(X, ["x"])

    def test_operators_collect_from_every_operand(self):
        self.assertFree(L.D0Eop1("+1", X), ["x"])
        self.assertFree(L.D0Eop2("+", X, Y), ["x", "y"])

    def test_application_and_pairs_collect_from_both_parts(self):
        self.assertFree(L.D0Eapp(F, X), ["f", "x"])
        self.assertFree(L.D0Epair(X, Y), ["x", "y"])
        self.assertFree(L.D0Epfst(X), ["x"])
        self.assertFree(L.D0Epsnd(Y), ["y"])

    def test_conditional_collects_from_test_and_both_branches(self):
        self.assertFree(L.D0Eif0(X, Y, L.D0Evar("z")), ["x", "y", "z"])

    def test_lambda_binds_its_parameter(self):
        self.assertFree(L.D0Elam("x", L.D0Eop2("+", X, Y)), ["y"])

    def test_fix_binds_its_name_and_parameter(self):
        self.assertFree(L.D0Efix("f", "x", L.D0Eapp(F, L.D0Eop2("+", X, Y))), ["y"])

    def test_let_binds_only_in_its_body(self):
        self.assertFree(L.D0Elet("x", ONE, X), [])
        # The initializer is outside the scope of the name being bound.
        self.assertFree(L.D0Elet("x", X, X), ["x"])
        self.assertFree(L.D0Elet("x", Y, ONE), ["y"])

    def test_duplicate_occurrences_are_reported_once(self):
        self.assertFree(L.D0Eop2("+", X, L.D0Eop2("*", X, X)), ["x"])

    def test_nested_bindings_and_shadowing(self):
        inner = L.D0Elam("y", L.D0Eop2("+", X, L.D0Eop2("+", Y, L.D0Evar("z"))))
        self.assertFree(L.D0Elam("x", inner), ["z"])
        # x is bound inside the lambda but free in the argument.
        self.assertFree(L.D0Eapp(L.D0Elam("x", X), X), ["x"])

    def test_unused_binding_is_not_reported(self):
        self.assertFree(L.D0Elam("unused", ONE), [])


class Lint(unittest.TestCase):
    def test_closed_program_passes(self):
        output = lint_source(example("factorial.lambda"))
        self.assertEqual(output.outcome, Outcome.SUCCESS)
        self.assertEqual(output.text, "No free variables found.")

    def test_open_program_lists_names_in_sorted_order(self):
        output = lint_source('D0Epair(D0Evar("zeta"), D0Epair(D0Evar("alpha"), D0Evar("zeta")))')
        self.assertEqual(output.outcome, Outcome.LANGUAGE_ERROR)
        self.assertEqual(output.text, "Undeclared variable(s): alpha, zeta")

    def test_does_not_evaluate(self):
        # Closed, but dividing by zero would fail if it were run.
        output = lint_source(example("division-by-zero.lambda"))
        self.assertEqual(output.outcome, Outcome.SUCCESS)

    def test_malformed_input_is_an_input_error(self):
        output = lint_source(example("malformed.lambda"))
        self.assertEqual(output.outcome, Outcome.INPUT_ERROR)
        self.assertTrue(output.text.startswith("Input error: line 2"))


class Interpret(unittest.TestCase):
    def assertValue(self, source, expected):
        output = interpret_source(source)
        self.assertEqual((output.outcome, output.text), (Outcome.SUCCESS, expected))

    def assertRuntimeError(self, source, fragment):
        output = interpret_source(source)
        self.assertEqual(output.outcome, Outcome.LANGUAGE_ERROR)
        self.assertTrue(output.text.startswith("Runtime error: "), output.text)
        self.assertIn(fragment, output.text)

    def test_arithmetic(self):
        self.assertValue(example("arithmetic.lambda"), "D0Vint(arg1=42)")
        self.assertValue('D0Eop2("-", D0Eop2("*", D0Eint(6), D0Eint(7)), D0Eop1("+1", D0Eint(-1)))',
                         "D0Vint(arg1=42)")
        self.assertValue('D0Eop2("<", D0Eint(1), D0Eint(2))', "D0Vbtf(arg1=True)")

    def test_factorial_with_base_cases(self):
        for n, expected in [(0, 1), (1, 1), (5, 120), (10, 3628800)]:
            with self.subTest(n=n):
                self.assertValue(factorial(n), f"D0Vint(arg1={expected})")

    def test_fibonacci_with_base_cases(self):
        for n, expected in [(0, 0), (1, 1), (2, 1), (10, 55)]:
            with self.subTest(n=n):
                self.assertValue(fibonacci(n), f"D0Vint(arg1={expected})")

    def test_pairs_and_let(self):
        self.assertValue('D0Elet("p", D0Epair(D0Eint(1), D0Ebtf(False)), D0Epsnd(D0Evar("p")))',
                         "D0Vbtf(arg1=False)")

    def test_malformed_input_is_an_input_error_not_a_runtime_error(self):
        output = interpret_source("D0Eint(")
        self.assertEqual(output.outcome, Outcome.INPUT_ERROR)
        self.assertTrue(output.text.startswith("Input error: "))

    def test_division_by_zero_is_a_runtime_error(self):
        self.assertRuntimeError(example("division-by-zero.lambda"), "division by zero")

    def test_wrong_operand_type_is_a_runtime_error(self):
        self.assertRuntimeError('D0Eop2("+", D0Eint(1), D0Ebtf(True))', "TypeError")
        self.assertRuntimeError("D0Eapp(D0Eint(1), D0Eint(2))", "TypeError")

    def test_error_value_returned_directly_is_a_runtime_error(self):
        self.assertRuntimeError('D0Evar("x")', "D0V000()")

    def test_error_value_inside_a_pair_is_a_runtime_error(self):
        self.assertRuntimeError('D0Epair(D0Eint(1), D0Epair(D0Evar("x"), D0Eint(2)))', "D0V000()")

    def test_unbounded_recursion_is_a_runtime_error(self):
        loop = 'D0Eapp(D0Efix("f", "x", D0Eapp(D0Evar("f"), D0Evar("x"))), D0Eint(0))'
        self.assertRuntimeError(loop, "recursion is too deep")

    def test_contains_error_value(self):
        self.assertTrue(contains_error_value(L.D0V000()))
        self.assertTrue(contains_error_value(L.D0Vpair(L.D0Vint(1), L.D0V000())))
        self.assertFalse(contains_error_value(L.D0Vpair(L.D0Vint(1), L.D0Vbtf(True))))


if __name__ == "__main__":
    unittest.main()
