"""The controller with a substituted backend. No view code is involved."""
import threading
import unittest

from lambda_workbench.contract import Artifact, Operation, Outcome, ToolOutput
from lambda_workbench.controller import Status, WorkbenchController
from lambda_workbench.examples import load_canned_examples
from lambda_workbench.model import Workbench


class RecordingBackend:
    """Test backend: records every call and returns a canned output."""

    def __init__(self):
        self.calls = []
        self.outputs = {}

    def _call(self, operation, argument):
        self.calls.append((operation, argument))
        output = self.outputs.get(operation, ToolOutput(Outcome.SUCCESS, f"{operation} ok"))
        if isinstance(output, Exception):
            raise output
        return output

    def lint(self, source): return self._call("lint", source)
    def interpret(self, source): return self._call("interpret", source)
    def typecheck(self, source): return self._call("typecheck", source)
    def compile(self, source): return self._call("compile", source)
    def execute(self, artifact): return self._call("execute", artifact)


class BlockingBackend(RecordingBackend):
    """Test backend whose interpret waits until the test releases it."""

    def __init__(self):
        super().__init__()
        self.started = threading.Event()
        self.release = threading.Event()

    def interpret(self, source):
        self.started.set()
        if not self.release.wait(timeout=10):
            raise RuntimeError("the test never released the backend")
        return super().interpret(source)


def make(backend):
    return WorkbenchController(Workbench(), backend, load_canned_examples())


class Dispatch(unittest.TestCase):
    def setUp(self):
        self.backend = RecordingBackend()
        self.controller = make(self.backend)
        self.controller.apply("D0Eint(1)")

    def test_each_source_action_calls_exactly_its_backend_operation(self):
        for name in ["lint", "interpret", "typecheck", "compile"]:
            with self.subTest(operation=name):
                self.backend.calls.clear()
                reply = self.controller.run(name)
                self.assertEqual(reply.status, Status.OK)
                self.assertEqual(self.backend.calls, [(name, "D0Eint(1)")])
                newest = reply.snapshot.results[0]
                self.assertEqual((newest.operation.value, newest.revision, newest.text),
                                 (name, 1, f"{name} ok"))

    def test_unknown_operation_reaches_no_backend(self):
        self.assertEqual(self.controller.run("format").status, Status.UNKNOWN)
        self.assertEqual(self.backend.calls, [])

    def test_execute_is_refused_and_never_reaches_the_backend(self):
        reply = self.controller.run("execute")
        self.assertEqual(reply.status, Status.CONFLICT)
        self.assertIn("no generated code exists", reply.message)
        self.assertEqual(self.backend.calls, [])
        self.assertEqual(reply.snapshot.results, ())

    def test_placeholder_results_are_not_successes(self):
        self.backend.outputs["typecheck"] = ToolOutput(Outcome.NOT_IMPLEMENTED, "no type checker")
        self.backend.outputs["compile"] = ToolOutput(Outcome.NOT_IMPLEMENTED, "no compiler")
        for name in ["typecheck", "compile"]:
            newest = self.controller.run(name).snapshot.results[0]
            self.assertEqual(newest.outcome, Outcome.NOT_IMPLEMENTED)
        self.assertEqual(self.controller.run("execute").status, Status.CONFLICT)

    def test_execute_receives_the_stored_artifact_without_recompiling(self):
        self.backend.outputs["compile"] = ToolOutput(
            Outcome.SUCCESS, "compiled", Artifact(0, "python", "print(1)"))
        self.controller.run("compile")
        self.backend.calls.clear()
        reply = self.controller.run("execute")
        self.assertEqual(reply.status, Status.OK)
        self.assertEqual(self.backend.calls, [("execute", Artifact(1, "python", "print(1)"))])

    def test_actions_run_on_the_applied_source_not_on_unapplied_edits(self):
        reply = self.controller.run("lint", editor_text="D0Eint(2)")
        self.assertEqual(reply.status, Status.CONFLICT)
        self.assertEqual(self.backend.calls, [])
        self.assertEqual(reply.snapshot.editor_text, "D0Eint(2)")
        self.assertEqual(reply.snapshot.source.text, "D0Eint(1)")


class SourceChanges(unittest.TestCase):
    def setUp(self):
        self.backend = RecordingBackend()
        self.controller = make(self.backend)

    def test_actions_need_an_applied_source(self):
        reply = self.controller.run("lint")
        self.assertEqual((reply.status, reply.message), (Status.CONFLICT, "Apply a source first."))
        self.assertEqual(self.backend.calls, [])

    def test_canned_examples_load_as_new_revisions(self):
        first = self.controller.load_example("factorial")
        second = self.controller.load_example("fibonacci")
        self.assertEqual((first.snapshot.source.name, first.snapshot.source.revision),
                         ("Factorial (canned)", 1))
        self.assertEqual((second.snapshot.source.name, second.snapshot.source.revision),
                         ("Fibonacci (canned)", 2))
        self.assertEqual(self.controller.load_example("missing").status, Status.UNKNOWN)

    def test_replacing_the_source_clears_results(self):
        self.controller.load_example("factorial")
        self.controller.run("lint")
        reply = self.controller.load_example("fibonacci")
        self.assertEqual(reply.snapshot.results, ())

    def test_upload_uses_the_file_name_without_its_path(self):
        reply = self.controller.upload("C:\\work\\prog.lambda", b"D0Eint(1)")
        self.assertEqual((reply.status, reply.snapshot.source.name), (Status.OK, "prog.lambda"))

    def test_rejected_uploads_keep_the_applied_source(self):
        self.controller.load_example("factorial")
        for data in [b"", b"   \n", b"\xff\xfe\x00", b"#" * 70_000]:
            with self.subTest(data=data[:8]):
                reply = self.controller.upload("bad.lambda", data)
                self.assertEqual(reply.status, Status.REJECTED)
                self.assertEqual(reply.snapshot.source.name, "Factorial (canned)")
                self.assertEqual(reply.snapshot.source.revision, 1)

    def test_rejected_edit_stays_in_the_editor(self):
        self.controller.load_example("factorial")
        reply = self.controller.apply("   ")
        self.assertEqual(reply.status, Status.REJECTED)
        self.assertEqual(reply.snapshot.editor_text, "   ")
        self.assertEqual(reply.snapshot.source.revision, 1)
        corrected = self.controller.apply("D0Eint(7)")
        self.assertEqual((corrected.status, corrected.snapshot.source.revision), (Status.OK, 2))

    def test_unapplied_edits_block_replacement_until_discarded(self):
        self.controller.load_example("factorial")
        blocked = self.controller.load_example("fibonacci", editor_text="D0Eint(0)")
        self.assertEqual(blocked.status, Status.CONFLICT)
        self.assertEqual(blocked.snapshot.source.name, "Factorial (canned)")
        self.assertEqual(self.controller.manual_input(editor_text="D0Eint(0)").status, Status.CONFLICT)
        self.controller.discard()
        self.assertEqual(self.controller.load_example("fibonacci").status, Status.OK)


class FailureAndBusy(unittest.TestCase):
    def test_backend_exception_becomes_a_failure_result_and_retry_succeeds(self):
        backend = RecordingBackend()
        controller = make(backend)
        controller.apply("D0Eint(1)")
        backend.outputs["interpret"] = RuntimeError("worker crashed")
        failed = controller.run("interpret").snapshot
        self.assertEqual(failed.results[0].outcome, Outcome.BACKEND_FAILURE)
        self.assertIn("worker crashed", failed.results[0].text)
        self.assertIsNone(failed.busy)
        self.assertEqual(failed.source.text, "D0Eint(1)")

        del backend.outputs["interpret"]
        retried = controller.run("interpret").snapshot
        self.assertEqual(retried.results[0].outcome, Outcome.SUCCESS)
        self.assertEqual(len(retried.results), 2)

    def test_backend_returning_the_wrong_type_is_a_failure(self):
        backend = RecordingBackend()
        controller = make(backend)
        controller.apply("D0Eint(1)")
        backend.outputs["lint"] = "not a ToolOutput"
        snapshot = controller.run("lint").snapshot
        self.assertEqual(snapshot.results[0].outcome, Outcome.BACKEND_FAILURE)
        self.assertIsNone(snapshot.busy)

    def test_timeout_is_recorded_and_retry_succeeds(self):
        backend = RecordingBackend()
        controller = make(backend)
        controller.apply("D0Eint(1)")
        backend.outputs["interpret"] = ToolOutput(Outcome.TIMEOUT, "Stopped after 5 seconds")
        timed_out = controller.run("interpret").snapshot
        self.assertEqual(timed_out.results[0].outcome, Outcome.TIMEOUT)
        self.assertIsNone(timed_out.busy)
        del backend.outputs["interpret"]
        self.assertEqual(controller.run("interpret").snapshot.results[0].outcome, Outcome.SUCCESS)

    def test_requests_made_while_busy_are_refused_then_allowed(self):
        backend = BlockingBackend()
        controller = make(backend)
        controller.apply("D0Eint(1)")
        replies = []
        worker = threading.Thread(target=lambda: replies.append(controller.run("interpret")))
        worker.start()
        try:
            self.assertTrue(backend.started.wait(timeout=10))
            self.assertIs(controller.current().snapshot.busy, Operation.INTERPRET)
            for attempt in [lambda: controller.run("lint"),
                            lambda: controller.apply("D0Eint(2)"),
                            lambda: controller.load_example("factorial"),
                            controller.manual_input,
                            controller.discard]:
                reply = attempt()
                self.assertEqual(reply.status, Status.CONFLICT)
                self.assertTrue(reply.message.startswith("Busy: "), reply.message)
        finally:
            backend.release.set()
            worker.join(timeout=10)
        self.assertEqual(replies[0].status, Status.OK)
        after = controller.current().snapshot
        self.assertIsNone(after.busy)
        self.assertEqual(after.source.text, "D0Eint(1)")
        self.assertEqual(backend.calls, [("interpret", "D0Eint(1)")])
        self.assertEqual(controller.run("lint").status, Status.OK)


if __name__ == "__main__":
    unittest.main()
