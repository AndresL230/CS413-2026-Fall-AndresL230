"""Tests for the demonstration pipeline (DEM-01, DEM-02): every mandatory
demo matches its expected answer under the shared demo budgets.

Run from assigns/06:
    python3 -B -m unittest discover -s MySolution/tests -t MySolution -v
"""
from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import pipeline
from compiler import compile_expr
from evaluator import Completed, Exhausted
from examples import DEMOS, EXHAUSTED
from observers import Decoded
from pipeline import EXEC_BUDGET, OBS_BUDGET, run_demo, same_answer
from target import pretty

MYSOLUTION = Path(__file__).resolve().parents[1]


def _forbid(*args, **kwargs):
    raise AssertionError("source evaluation ran on a divergent demo")


class DemoTableTests(unittest.TestCase):
    def test_all_fourteen_demos_present(self):
        self.assertEqual([d.id for d in DEMOS],
                         [f"DEMO-{k:02d}" for k in range(1, 15)])

    def test_every_demo_matches_expected(self):
        for demo in DEMOS:
            with self.subTest(demo.id, notation=demo.notation):
                report = run_demo(demo)
                self.assertTrue(report.passed, report)
                if demo.expected is EXHAUSTED:
                    self.assertEqual(report.execution, Exhausted(EXEC_BUDGET))
                    self.assertIsNone(report.observation)
                else:
                    self.assertIsInstance(report.execution, Completed)
                    self.assertIsInstance(report.observation, Decoded)
                    self.assertTrue(same_answer(report.observation.value, demo.expected))
                    self.assertTrue(same_answer(report.source_answer, demo.expected))

    def test_divergent_demos_never_run_source_side(self):
        with mock.patch.object(pipeline, "evaluate", _forbid):
            for demo in DEMOS:
                if demo.expected is EXHAUSTED:
                    with self.subTest(demo.id):
                        report = run_demo(demo)
                        self.assertFalse(report.source_ran)
                        self.assertTrue(report.passed)

    def test_budgets_have_headroom(self):
        # Terminating demos use at most a fifth of each budget.
        for demo in DEMOS:
            if demo.expected is not EXHAUSTED:
                with self.subTest(demo.id):
                    report = run_demo(demo)
                    self.assertLessEqual(report.execution.steps * 5, EXEC_BUDGET)
                    self.assertLessEqual(report.observation.steps * 5, OBS_BUDGET)


class AnswerComparisonTests(unittest.TestCase):
    def test_bool_and_int_are_not_confused(self):
        self.assertFalse(same_answer(True, 1))
        self.assertFalse(same_answer(0, False))
        self.assertTrue(same_answer((2, True), (2, True)))
        self.assertFalse(same_answer((2, 1), (2, True)))


class DemoCommandTests(unittest.TestCase):
    def test_command_runs_and_saves_terms(self):
        with tempfile.TemporaryDirectory() as out:
            result = subprocess.run(
                [sys.executable, "-B", str(MYSOLUTION / "demo.py"), "--out-dir", out],
                capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn(f"execution budget:   {EXEC_BUDGET:,}", result.stdout)
            self.assertIn(f"observation budget: {OBS_BUDGET:,}", result.stdout)
            self.assertIn("budget exhausted", result.stdout)
            self.assertNotIn("diverge", result.stdout.lower())
            self.assertIn("14 of 14 demos match", result.stdout)
            for demo in DEMOS:
                saved = Path(out) / f"{demo.id}.txt"
                self.assertTrue(saved.exists(), saved)
                last_line = saved.read_text().rstrip("\n").splitlines()[-1]
                self.assertEqual(last_line, pretty(compile_expr(demo.source)))


if __name__ == "__main__":
    unittest.main()
