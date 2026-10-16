import unittest

from lambda_workbench import lambda1 as L
from lambda_workbench.reader import CONSTRUCTOR_NAMES, ReaderError, read_expression


class ReadValidExpressions(unittest.TestCase):
    def test_reads_nested_constructors(self):
        self.assertEqual(
            read_expression('D0Eop2("+", D0Eint(20), D0Eint(22))'),
            L.D0Eop2("+", L.D0Eint(20), L.D0Eint(22)))

    def test_reads_every_constructor(self):
        samples = {
            "D0Eint": ("D0Eint(7)", L.D0Eint(7)),
            "D0Ebtf": ("D0Ebtf(True)", L.D0Ebtf(True)),
            "D0Eop1": ('D0Eop1("+1", D0Eint(1))', L.D0Eop1("+1", L.D0Eint(1))),
            "D0Eop2": ('D0Eop2("*", D0Eint(2), D0Eint(3))', L.D0Eop2("*", L.D0Eint(2), L.D0Eint(3))),
            "D0Evar": ('D0Evar("x")', L.D0Evar("x")),
            "D0Elam": ('D0Elam("x", D0Evar("x"))', L.D0Elam("x", L.D0Evar("x"))),
            "D0Efix": ('D0Efix("f", "x", D0Evar("x"))', L.D0Efix("f", "x", L.D0Evar("x"))),
            "D0Eapp": ('D0Eapp(D0Evar("f"), D0Eint(1))', L.D0Eapp(L.D0Evar("f"), L.D0Eint(1))),
            "D0Eif0": ("D0Eif0(D0Ebtf(True), D0Eint(1), D0Eint(2))",
                       L.D0Eif0(L.D0Ebtf(True), L.D0Eint(1), L.D0Eint(2))),
            "D0Elet": ('D0Elet("x", D0Eint(1), D0Evar("x"))', L.D0Elet("x", L.D0Eint(1), L.D0Evar("x"))),
            "D0Epair": ("D0Epair(D0Eint(1), D0Eint(2))", L.D0Epair(L.D0Eint(1), L.D0Eint(2))),
            "D0Epfst": ("D0Epfst(D0Epair(D0Eint(1), D0Eint(2)))",
                        L.D0Epfst(L.D0Epair(L.D0Eint(1), L.D0Eint(2)))),
            "D0Epsnd": ("D0Epsnd(D0Epair(D0Eint(1), D0Eint(2)))",
                        L.D0Epsnd(L.D0Epair(L.D0Eint(1), L.D0Eint(2)))),
        }
        self.assertEqual(set(samples), set(CONSTRUCTOR_NAMES))
        for name, (text, expected) in samples.items():
            with self.subTest(constructor=name):
                self.assertEqual(read_expression(text), expected)

    def test_accepts_comments_and_multiline_layout(self):
        text = """
        # add two numbers
        D0Eop2(
            "+",          # the operator
            D0Eint(20),
            D0Eint(22),
        )
        """
        self.assertEqual(read_expression(text.replace("\n        ", "\n")),
                         L.D0Eop2("+", L.D0Eint(20), L.D0Eint(22)))

    def test_accepts_negative_integers_and_keyword_arguments(self):
        self.assertEqual(read_expression("D0Eint(-5)"), L.D0Eint(-5))
        self.assertEqual(read_expression('D0Eop1(name="-1", arg1=D0Eint(arg1=3))'),
                         L.D0Eop1("-1", L.D0Eint(3)))


class RejectInvalidText(unittest.TestCase):
    def assertRejected(self, text, fragment):
        with self.assertRaises(ReaderError) as caught:
            read_expression(text)
        self.assertIn(fragment, str(caught.exception))

    def test_rejects_syntax_errors_with_a_position(self):
        with self.assertRaises(ReaderError) as caught:
            read_expression("D0Eint(1")
        self.assertEqual(caught.exception.line, 1)

    def test_rejects_statements_and_scripts(self):
        self.assertRejected("import os", "not a constructor expression")
        self.assertRejected("x = D0Eint(1)", "not a constructor expression")
        self.assertRejected("D0Eint(1)\nD0Eint(2)", "not a constructor expression")

    def test_rejects_calls_that_are_not_constructors(self):
        self.assertRejected('__import__("os").system("true")', "not a LAMBDA expression constructor")
        self.assertRejected('print("hi")', "not a LAMBDA expression constructor")
        self.assertRejected("D0Vint(1)", "not a LAMBDA expression constructor")
        self.assertRejected('D0Eapp(eval("1"), D0Eint(1))', "not a LAMBDA expression constructor")

    def test_rejects_bare_literals_and_names(self):
        self.assertRejected("42", "expected a constructor")
        self.assertRejected("D0Eint", "expected a constructor")

    def test_rejects_wrong_argument_counts(self):
        self.assertRejected("D0Eint()", "missing arg1")
        self.assertRejected("D0Eint(1, 2)", "takes 1 argument(s), found 2")
        self.assertRejected('D0Eop2("+", D0Eint(1))', "missing arg2")

    def test_rejects_wrong_argument_types(self):
        self.assertRejected('D0Eint("1")', "must be an integer")
        self.assertRejected("D0Eint(True)", "must be an integer")
        self.assertRejected("D0Eint(1.5)", "must be an integer")
        self.assertRejected("D0Eint(1 + 2)", "must be an integer")
        self.assertRejected("D0Ebtf(1)", "must be True or False")
        self.assertRejected("D0Evar(x)", "must be a string")
        self.assertRejected('D0Elam("x", "x")', "expected a constructor")
        self.assertRejected("D0Eop1(D0Eint(1), D0Eint(1))", "must be a string")

    def test_rejects_unpacking_and_bad_keywords(self):
        self.assertRejected("D0Eint(*[1])", "unpacking")
        self.assertRejected("D0Eint(**{})", "unpacking")
        self.assertRejected("D0Eint(value=1)", "no argument named 'value'")
        self.assertRejected("D0Eint(1, arg1=2)", "given twice")

    def test_reports_the_position_of_a_nested_problem(self):
        with self.assertRaises(ReaderError) as caught:
            read_expression('D0Eop2("+",\n  D0Eint(1),\n  oops)')
        self.assertEqual((caught.exception.line, caught.exception.column), (3, 3))

    def test_rejects_very_deep_nesting_without_crashing(self):
        depth = 5000
        with self.assertRaises(ReaderError):
            read_expression("D0Epfst(" * depth + "D0Eint(1)" + ")" * depth)


if __name__ == "__main__":
    unittest.main()
