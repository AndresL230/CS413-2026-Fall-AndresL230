"""Tests for compiler.py: every constructor and operator checked against
a hardcoded answer and the source evaluator, plus ACC-06 to ACC-10.

Run from assigns/06:
    python3 -B -m unittest discover -s MySolution/tests -t MySolution -v
"""
from __future__ import annotations

import copy
import re
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

import church
import evaluator
from compiler import compile_expr, CompileError
from examples import DEMOS
from evaluator import evaluate, Completed, Exhausted
from observers import NAT, BOOL, PairKind, Decoded, execute_and_observe
from source import D0Eint, D0Ebtf, D0Efix, D0Eop1, D0Eop2, d0exp_fvset
from target import Var, Lam, App, free_vars, is_pure, pretty
from examples import (
    V, N, B, TRUE_, FALSE_, op, app, lam, if_, let, pair, fst, snd, not_,
    LOOP, FACT, FIB,
)
from pipeline import to_python

MYSOLUTION = Path(__file__).resolve().parents[1]
EXEC, OBS = 200_000, 200_000
T, F = TRUE_, FALSE_


def run_compiled(expr, kind, exec_budget=EXEC, obs_budget=OBS):
    return execute_and_observe(compile_expr(expr), kind, exec_budget, obs_budget)


def comparison_cases():
    table = {"<": lambda m, n: m < n, "<=": lambda m, n: m <= n,
             ">": lambda m, n: m > n, ">=": lambda m, n: m >= n,
             "==": lambda m, n: m == n, "!=": lambda m, n: m != n}
    for name, fn in table.items():
        for m, n in [(2, 3), (3, 3), (3, 2)]:
            yield (f"{m} {name} {n}", op(name, N(m), N(n)), BOOL, fn(m, n))


def boolean_cases():
    for p in (True, False):
        yield (f"not {p}", not_(B(p)), BOOL, not p)
        for q in (True, False):
            yield (f"{p} and {q}", op("and", B(p), B(q)), BOOL, p and q)
            yield (f"{p} or {q}", op("or", B(p), B(q)), BOOL, p or q)


# (label, source, expected kind, hardcoded expected answer)
AGREEMENT_CASES = [
    ("zero", N(0), NAT, 0),
    ("literal", N(5), NAT, 5),
    ("true", T, BOOL, True),
    ("false", F, BOOL, False),
    ("identity application", app(lam("x", V("x")), N(3)), NAT, 3),
    ("curried application", app(lam("x", "y", op("-", V("x"), V("y"))), N(5), N(2)), NAT, 3),
    ("2 + 3 * 4", op("+", N(2), op("*", N(3), N(4))), NAT, 14),
    ("0 + 0", op("+", N(0), N(0)), NAT, 0),
    ("3 * 0", op("*", N(3), N(0)), NAT, 0),
    ("5 - 2", op("-", N(5), N(2)), NAT, 3),
    ("2 - 5 (truncated)", op("-", N(2), N(5)), NAT, 0),
    ("4 - 4", op("-", N(4), N(4)), NAT, 0),
    ("predecessor of zero: 0 - 1", op("-", N(0), N(1)), NAT, 0),
    *comparison_cases(),
    *boolean_cases(),
    ("if true", if_(T, N(1), N(2)), NAT, 1),
    ("if false", if_(F, N(1), N(2)), NAT, 2),
    ("if 2 <= 3 then 7 else 9", if_(op("<=", N(2), N(3)), N(7), N(9)), NAT, 7),
    ("let", let("x", N(3), app(lam("y", op("+", V("x"), V("y"))), N(4))), NAT, 7),
    ("nested lets", let("x", N(1), let("y", op("+", V("x"), N(1)),
                                       let("x", N(5), op("+", V("x"), V("y"))))), NAT, 7),
    ("let initializer scope", let("x", N(1), let("x", op("+", V("x"), N(1)), V("x"))), NAT, 2),
    ("nested lambdas shadow", app(lam("x", "x", V("x")), N(1), N(2)), NAT, 2),
    ("higher order", app(lam("f", app(V("f"), N(3))), lam("x", op("+", V("x"), N(1)))), NAT, 4),
    ("pair", pair(N(2), T), PairKind(NAT, BOOL), (2, True)),
    ("nested pair", pair(pair(N(2), T), N(3)), PairKind(PairKind(NAT, BOOL), NAT), ((2, True), 3)),
    ("fst", fst(pair(N(2), T)), NAT, 2),
    ("snd", snd(pair(N(2), T)), BOOL, True),
    ("factorial 3", app(FACT, N(3)), NAT, 6),
    ("coincident fix (fix f(f). f) 3", app(D0Efix("f", "f", V("f")), N(3)), NAT, 3),
    ("fix with Z-like names", app(D0Efix("g", "v", if_(op("==", V("v"), N(0)), N(0),
                                                        app(V("g"), op("-", V("v"), N(1))))), N(2)),
     NAT, 0),
    ("encoding-named source vars",
     let("s", N(2), let("z", N(3), app(lam("t", "f", op("+", V("t"), V("f"))), V("s"), V("z")))),
     NAT, 5),
    ("thunk name hazard: u in then-branch", let("u", N(1), if_(T, V("u"), N(0))), NAT, 1),
    ("thunk name hazard: v in else-branch", let("v", N(4), if_(F, N(0), V("v"))), NAT, 4),
    ("thunk name hazard: and/or", let("u", T, let("v", F, op("or", op("and", V("u"), V("v")),
                                                           V("u")))), BOOL, True),
]


class AgreementTests(unittest.TestCase):
    """Every constructor and operator: hardcoded answer == source
    evaluator == observed compiled result."""

    def test_source_and_target_agree_with_expected(self):
        for label, expr, kind, expected in AGREEMENT_CASES:
            with self.subTest(label):
                source_result = evaluate(expr)
                self.assertIsInstance(source_result, Completed)
                self.assertEqual(to_python(source_result.value), expected)
                report = run_compiled(expr, kind)
                self.assertIsInstance(report.execution, Completed, report)
                self.assertIsInstance(report.observation, Decoded, report)
                self.assertEqual(report.observation.value, expected)

    def test_recursive_programs(self):
        # ACC-07: factorial and Fibonacci agree with the demo table.
        for label, expr, expected in [("fact 4", app(FACT, N(4)), 24),
                                      ("fib 5", app(FIB, N(5)), 5)]:
            with self.subTest(label):
                self.assertEqual(to_python(evaluate(expr).value), expected)
                self.assertEqual(run_compiled(expr, NAT).observation.value, expected)


class TranslationShapeTests(unittest.TestCase):
    """The required rules, checked structurally."""

    def test_var_lam_app(self):
        self.assertEqual(compile_expr(V("x")), Var("x"))
        self.assertEqual(compile_expr(lam("x", V("y"))), Lam("x", Var("y")))
        self.assertEqual(compile_expr(app(V("f"), V("a"))), App(Var("f"), Var("a")))

    def test_let(self):
        self.assertEqual(compile_expr(let("x", V("a"), V("x"))),
                         App(Lam("x", Var("x")), Var("a")))

    def test_if(self):
        self.assertEqual(compile_expr(if_(V("c"), V("a"), V("b"))),
                         App(App(App(Var("c"), Lam("u", Var("a"))),
                                 Lam("v", Var("b"))), church.I))

    def test_and_or_use_thunks_not_strict_combinators(self):
        a, b = Var("a"), Var("b")
        self.assertEqual(compile_expr(op("and", V("a"), V("b"))),
                         App(App(App(a, Lam("u", b)), Lam("v", church.FALSE)), church.I))
        self.assertEqual(compile_expr(op("or", V("a"), V("b"))),
                         App(App(App(a, Lam("u", church.TRUE)), Lam("v", b)), church.I))

    def test_fix(self):
        self.assertEqual(compile_expr(D0Efix("f", "x", V("f"))),
                         App(church.Z, Lam("f", Lam("x", Var("f")))))

    def test_strict_operators(self):
        self.assertEqual(compile_expr(op("+", V("a"), V("b"))),
                         App(App(church.ADD, Var("a")), Var("b")))
        self.assertEqual(compile_expr(not_(V("a"))), App(church.NOT, Var("a")))
        self.assertEqual(compile_expr(pair(V("a"), V("b"))),
                         App(App(church.PAIR, Var("a")), Var("b")))
        self.assertEqual(compile_expr(fst(V("p"))), App(church.FST, Var("p")))
        self.assertEqual(compile_expr(snd(V("p"))), App(church.SND, Var("p")))
        self.assertEqual(compile_expr(N(2)), church.num(2))
        self.assertEqual(compile_expr(T), church.TRUE)
        self.assertEqual(compile_expr(F), church.FALSE)


class ScopeAndNamingTests(unittest.TestCase):
    """ACC-06 and the scope parts of ACC-07."""

    OPEN_CASES = [
        let("x", V("x"), V("x")),
        lam("x", lam("x", V("x"))),
        lam("x", app(lam("x", V("x")), V("x"))),
        op("+", V("s"), V("z")),
        if_(V("t"), V("f"), V("x")),
        app(V("f"), V("x")),
        if_(op("<", V("s"), N(1)), V("u"), V("v")),
        op("and", V("t"), op("or", V("f"), V("u_1"))),
        D0Efix("f", "x", app(V("f"), V("x"), V("s"), V("z"))),
        D0Efix("f", "f", app(V("f"), V("g"))),
        D0Efix("g", "v", app(V("g"), V("x"), V("v"))),
        let("t", V("t"), D0Efix("f", "x", if_(V("t"), V("f"), V("x")))),
        pair(fst(V("p")), snd(V("q"))),
    ]

    def test_free_variables_preserved(self):
        for expr in self.OPEN_CASES:
            with self.subTest(expr=expr):
                target = compile_expr(expr)
                self.assertEqual(free_vars(target), d0exp_fvset(expr))
                self.assertTrue(is_pure(target))

    def test_let_x_equals_x(self):
        target = compile_expr(let("x", V("x"), V("x")))
        self.assertEqual(target, App(Lam("x", Var("x")), Var("x")))
        self.assertEqual(free_vars(target), {"x"})

    def test_thunk_names_skip_names_in_branch(self):
        # if c then (u u_1) else v: then-thunk avoids u, u_1; else-thunk avoids v.
        target = compile_expr(if_(V("c"), app(V("u"), V("u_1")), V("v")))
        expected = App(App(App(Var("c"), Lam("u_2", App(Var("u"), Var("u_1")))),
                           Lam("v_1", Var("v"))), church.I)
        self.assertEqual(target, expected)
        self.assertEqual(free_vars(target), {"c", "u", "u_1", "v"})

    def test_thunk_names_also_avoid_bound_and_library_names(self):
        # Z binds v internally, so an else-branch containing fix skips v.
        target = compile_expr(if_(V("c"), V("a"), D0Efix("f", "x", V("x"))))
        self.assertEqual(target.fn.arg.param, "v_1")
        # Names outside the thunked branch do not matter.
        target = compile_expr(app(lam("u", if_(V("u"), N(1), N(2))), T))
        self.assertEqual(target.fn.body.fn.fn.arg.param, "u")

    def test_naming_is_deterministic(self):
        for expr in self.OPEN_CASES:
            with self.subTest(expr=expr):
                self.assertEqual(compile_expr(expr), compile_expr(expr))

    def test_input_not_mutated(self):
        for expr in self.OPEN_CASES + [app(FACT, N(4)), LOOP]:
            before = copy.deepcopy(expr)
            compile_expr(expr)
            self.assertEqual(expr, before)


SKIPPED_DIVERGENCE_CASES = [
    ("false and LOOP", op("and", F, LOOP), BOOL, False),
    ("true or LOOP", op("or", T, LOOP), BOOL, True),
    ("if true then 1 else LOOP", if_(T, N(1), LOOP), NAT, 1),
    ("if false then LOOP else 2", if_(F, LOOP, N(2)), NAT, 2),
]

FORCED_DIVERGENCE_CASES = [
    ("LOOP", LOOP, NAT),
    ("(lam x. 0) LOOP", app(lam("x", N(0)), LOOP), NAT),
    ("let x = LOOP in 2", let("x", LOOP, N(2)), NAT),
    ("fst (pair 2 LOOP)", fst(pair(N(2), LOOP)), NAT),
    ("snd (pair LOOP true)", snd(pair(LOOP, T)), BOOL),
    ("pair LOOP 1", pair(LOOP, N(1)), PairKind(NAT, NAT)),
    ("pair 1 LOOP", pair(N(1), LOOP), PairKind(NAT, NAT)),
    ("if true then LOOP else 1", if_(T, LOOP, N(1)), NAT),
    ("if false then 1 else LOOP", if_(F, N(1), LOOP), NAT),
    ("true and LOOP", op("and", T, LOOP), BOOL),
    ("false or LOOP", op("or", F, LOOP), BOOL),
    ("LOOP + 1", op("+", LOOP, N(1)), NAT),
    ("1 + LOOP", op("+", N(1), LOOP), NAT),
]


class CallByValueTests(unittest.TestCase):
    """ACC-08 and the delayed-branch requirements."""

    BUDGET = 3_000

    def test_skipped_divergence(self):
        for label, expr, kind, expected in SKIPPED_DIVERGENCE_CASES:
            with self.subTest(label):
                self.assertEqual(run_compiled(expr, kind).observation.value, expected)

    def test_forced_divergence_exhausts(self):
        for label, expr, kind in FORCED_DIVERGENCE_CASES:
            with self.subTest(label):
                report = run_compiled(expr, kind, self.BUDGET)
                self.assertEqual(report.execution, Exhausted(self.BUDGET))
                self.assertIsNone(report.observation)


class RejectionTests(unittest.TestCase):
    """ACC-09: unsupported input is rejected anywhere in the tree."""

    def test_rejections_identify_input(self):
        for label, expr, needle in [
            ("negative literal", N(-1), "-1"),
            ("division", op("/", N(4), N(2)), "'/'"),
            ("modulo", op("%", N(4), N(2)), "'%'"),
            ("unsupported unary", D0Eop1("-1", N(2)), "'-1'"),
            ("unsupported unary neg", D0Eop1("neg", N(2)), "'neg'"),
            ("bool as int", D0Eint(True), "True"),
            ("int as bool", D0Ebtf(1), "1"),
            ("unselected branch", if_(T, N(1), op("/", N(1), N(0))), "'/'"),
            ("unapplied lambda", lam("x", op("+", V("x"), N(-3))), "-3"),
            ("fix body", D0Efix("f", "x", D0Eop1("-1", V("x"))), "'-1'"),
            ("short-circuited operand", op("and", F, op("^", N(1), N(2))), "'^'"),
            ("invalid identifier", V("1x"), "'1x'"),
            ("invalid binder", lam("a-b", N(1)), "'a-b'"),
        ]:
            with self.subTest(label):
                with self.assertRaisesRegex(CompileError, re.escape(needle)) as caught:
                    compile_expr(expr)
                self.assertNotIsInstance(caught.exception, NotImplementedError)


def _forbid(*args, **kwargs):
    raise AssertionError("the compiler called the evaluator")


class IsolationTests(unittest.TestCase):
    """ACC-10: compilation never evaluates."""

    def test_compiles_without_evaluator(self):
        with mock.patch.object(evaluator, "evaluate", _forbid), \
                mock.patch.object(evaluator, "_run_target", _forbid), \
                mock.patch.object(evaluator, "_run_source", _forbid):
            for expr in (op("+", N(2), op("*", N(3), N(4))), LOOP, app(FIB, N(5))):
                before = copy.deepcopy(expr)
                target = compile_expr(expr)
                self.assertTrue(is_pure(target))
                self.assertEqual(free_vars(target), frozenset())
                self.assertEqual(expr, before)

    def _modules_loaded_by(self, module):
        code = f"import sys, {module}; print(sorted(sys.modules))"
        out = subprocess.run([sys.executable, "-B", "-c", code], cwd=MYSOLUTION,
                             capture_output=True, text=True, check=True).stdout
        return out

    def test_compiler_does_not_import_evaluator(self):
        self.assertNotIn("'evaluator'", self._modules_loaded_by("compiler"))

    def test_evaluator_does_not_import_compiler(self):
        loaded = self._modules_loaded_by("evaluator")
        self.assertNotIn("'compiler'", loaded)
        self.assertNotIn("'church'", loaded)


class PurityAcrossSuiteTests(unittest.TestCase):
    """CMP-03: every source AST the suite compiles yields only Var, Lam,
    and App nodes, with FV(C[e]) = FV(e) (so no library name is left
    unresolved)."""

    def all_sources(self):
        yield from ((label, expr) for label, expr, _, _ in AGREEMENT_CASES)
        yield from ((label, expr) for label, expr, _, _ in SKIPPED_DIVERGENCE_CASES)
        yield from ((label, expr) for label, expr, _ in FORCED_DIVERGENCE_CASES)
        yield from ((f"open case {k}", expr)
                    for k, expr in enumerate(ScopeAndNamingTests.OPEN_CASES))
        yield from ((demo.id, demo.source) for demo in DEMOS)
        yield from (("fact", FACT), ("fib", FIB), ("LOOP", LOOP))

    def test_every_compiled_output_is_pure(self):
        count = 0
        for label, expr in self.all_sources():
            with self.subTest(label):
                target = compile_expr(expr)
                self.assertTrue(is_pure(target))
                self.assertEqual(free_vars(target), d0exp_fvset(expr))
                count += 1
        self.assertGreater(count, 100)


if __name__ == "__main__":
    unittest.main()
