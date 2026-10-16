"""The real backend adapter, including its worker process and time bound."""
import unittest
from pathlib import Path

from lambda_workbench.backend import LambdaBackend
from lambda_workbench.contract import Artifact, Outcome

EXAMPLES = Path(__file__).resolve().parent.parent / "examples"


def example(name: str) -> str:
    return (EXAMPLES / name).read_text(encoding="utf-8")


class RealTools(unittest.TestCase):
    def setUp(self):
        self.backend = LambdaBackend()

    def test_lint_runs_through_the_worker(self):
        self.assertEqual(self.backend.lint(example("factorial.lambda")).outcome, Outcome.SUCCESS)
        output = self.backend.lint(example("undeclared-variable.lambda"))
        self.assertEqual((output.outcome, output.text),
                         (Outcome.LANGUAGE_ERROR, "Undeclared variable(s): x"))

    def test_interpret_runs_through_the_worker(self):
        output = self.backend.interpret(example("factorial.lambda"))
        self.assertEqual((output.outcome, output.text), (Outcome.SUCCESS, "D0Vint(arg1=120)"))
        output = self.backend.interpret(example("fibonacci.lambda"))
        self.assertEqual((output.outcome, output.text), (Outcome.SUCCESS, "D0Vint(arg1=55)"))

    def test_interpret_handles_recursion_deeper_than_pythons_default(self):
        source = example("factorial.lambda").replace("D0Eint(5))", "D0Eint(400))")
        self.assertEqual(self.backend.interpret(source).outcome, Outcome.SUCCESS)

    def test_non_ascii_source_survives_the_round_trip(self):
        output = self.backend.lint('D0Evar("变量")')
        self.assertEqual(output.text, "Undeclared variable(s): 变量")


class TimeBound(unittest.TestCase):
    def test_slow_program_times_out_and_the_backend_stays_usable(self):
        backend = LambdaBackend(timeout_seconds=0.5)
        output = backend.interpret(example("slow-fibonacci.lambda"))
        self.assertEqual(output.outcome, Outcome.TIMEOUT)
        self.assertIn("0.5 seconds", output.text)
        # Lint does not evaluate, so the same program lints within the bound.
        self.assertEqual(backend.lint(example("slow-fibonacci.lambda")).outcome, Outcome.SUCCESS)


class Placeholders(unittest.TestCase):
    def setUp(self):
        self.backend = LambdaBackend()

    def test_typecheck_and_compile_are_not_implemented(self):
        typecheck = self.backend.typecheck("D0Eint(1)")
        compiled = self.backend.compile("D0Eint(1)")
        self.assertEqual(typecheck.outcome, Outcome.NOT_IMPLEMENTED)
        self.assertEqual(typecheck.text, "Type checking is not yet implemented.")
        self.assertEqual(compiled.outcome, Outcome.NOT_IMPLEMENTED)
        self.assertIn("Compilation is not yet implemented", compiled.text)
        self.assertIsNone(compiled.artifact)

    def test_execute_does_not_fall_back_to_interpretation(self):
        self.assertEqual(self.backend.execute(None).outcome, Outcome.NOT_IMPLEMENTED)
        artifact = Artifact(revision=1, language="python", code="print(42)")
        self.assertEqual(self.backend.execute(artifact).outcome, Outcome.NOT_IMPLEMENTED)


if __name__ == "__main__":
    unittest.main()
