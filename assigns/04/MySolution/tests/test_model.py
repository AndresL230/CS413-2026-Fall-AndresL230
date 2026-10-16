"""The model on its own: no browser, no web server, no backend."""
import unittest

from lambda_workbench.contract import Artifact, Operation, Outcome, ToolOutput
from lambda_workbench.model import (
    MANUAL_INPUT_NAME, MAX_RESULTS, MAX_SOURCE_BYTES, BusyError, ModelError,
    OperationUnavailable, SourceRejected, UnappliedEdits, Workbench, decode_upload)

OK = ToolOutput(Outcome.SUCCESS, "fine")


class SourceEntry(unittest.TestCase):
    def setUp(self):
        self.model = Workbench()

    def test_starts_with_no_source_and_a_blank_manual_editor(self):
        snapshot = self.model.snapshot()
        self.assertIsNone(snapshot.source)
        self.assertEqual((snapshot.editor_name, snapshot.editor_text), (MANUAL_INPUT_NAME, ""))
        self.assertFalse(snapshot.has_unapplied_edits)

    def test_manual_input_without_an_upload_becomes_revision_one(self):
        self.model.edit("D0Eint(1)")
        self.assertTrue(self.model.snapshot().has_unapplied_edits)
        applied = self.model.apply_edits()
        self.assertEqual((applied.name, applied.text, applied.revision),
                         (MANUAL_INPUT_NAME, "D0Eint(1)", 1))
        self.assertFalse(self.model.snapshot().has_unapplied_edits)

    def test_each_accepted_change_is_a_new_revision(self):
        self.assertEqual(self.model.load("a.lambda", "D0Eint(1)").revision, 1)
        self.assertEqual(self.model.load("Factorial (canned)", "D0Eint(2)").revision, 2)
        self.model.edit("D0Eint(3)")
        applied = self.model.apply_edits()
        self.assertEqual((applied.name, applied.revision), ("Factorial (canned)", 3))

    def test_applying_without_changes_is_refused_and_keeps_the_revision(self):
        self.model.load("a.lambda", "D0Eint(1)")
        with self.assertRaises(ModelError):
            self.model.apply_edits()
        self.assertEqual(self.model.snapshot().source.revision, 1)

    def test_discard_restores_the_applied_source(self):
        self.model.load("a.lambda", "D0Eint(1)")
        self.model.edit("D0Eint(999)")
        self.model.discard_edits()
        snapshot = self.model.snapshot()
        self.assertEqual(snapshot.editor_text, "D0Eint(1)")
        self.assertFalse(snapshot.has_unapplied_edits)
        self.assertEqual(snapshot.source.revision, 1)

    def test_source_replacement_is_blocked_by_unapplied_edits(self):
        self.model.load("a.lambda", "D0Eint(1)")
        self.model.edit("D0Eint(2)")
        with self.assertRaises(UnappliedEdits):
            self.model.load("b.lambda", "D0Eint(3)")
        with self.assertRaises(UnappliedEdits):
            self.model.open_manual_input()
        snapshot = self.model.snapshot()
        self.assertEqual((snapshot.source.name, snapshot.editor_text), ("a.lambda", "D0Eint(2)"))

    def test_manual_input_keeps_the_applied_source_until_apply(self):
        self.model.load("a.lambda", "D0Eint(1)")
        self.model.open_manual_input()
        snapshot = self.model.snapshot()
        self.assertEqual((snapshot.editor_name, snapshot.editor_text), (MANUAL_INPUT_NAME, ""))
        self.assertEqual(snapshot.source.text, "D0Eint(1)")
        # The editor no longer shows the applied source, so tools are blocked.
        with self.assertRaises(OperationUnavailable):
            self.model.begin(Operation.LINT)
        self.model.discard_edits()
        self.assertEqual(self.model.snapshot().editor_text, "D0Eint(1)")
        self.model.begin(Operation.LINT)


class Rejection(unittest.TestCase):
    def setUp(self):
        self.model = Workbench()
        self.model.load("a.lambda", "D0Eint(1)")

    def assertAppliedSourceUnchanged(self):
        source = self.model.snapshot().source
        self.assertEqual((source.name, source.text, source.revision), ("a.lambda", "D0Eint(1)", 1))

    def test_rejects_empty_and_whitespace_only_edits_but_keeps_them(self):
        for text in ["", "   \n\t  "]:
            with self.subTest(text=text):
                self.model.edit(text)
                with self.assertRaises(SourceRejected):
                    self.model.apply_edits()
                self.assertAppliedSourceUnchanged()
                # The rejected edit is still in the editor for correction.
                self.assertEqual(self.model.snapshot().editor_text, text)

    def test_rejects_oversized_edit_and_accepts_the_largest_allowed(self):
        self.model.edit("#" * (MAX_SOURCE_BYTES + 1))
        with self.assertRaises(SourceRejected) as caught:
            self.model.apply_edits()
        self.assertIn(str(MAX_SOURCE_BYTES), str(caught.exception))
        self.assertAppliedSourceUnchanged()
        self.model.edit("#" * MAX_SOURCE_BYTES)
        self.assertEqual(self.model.apply_edits().revision, 2)

    def test_size_is_measured_in_utf8_bytes(self):
        self.model.edit("é" * (MAX_SOURCE_BYTES // 2 + 1))
        with self.assertRaises(SourceRejected):
            self.model.apply_edits()

    def test_rejects_empty_load(self):
        with self.assertRaises(SourceRejected):
            self.model.load("empty.lambda", "  \n")
        self.assertAppliedSourceUnchanged()

    def test_decode_upload_rejects_invalid_utf8_and_oversized_files(self):
        with self.assertRaises(SourceRejected) as caught:
            decode_upload(b"D0Eint(1) \xff\xfe")
        self.assertIn("UTF-8", str(caught.exception))
        with self.assertRaises(SourceRejected):
            decode_upload(b"#" * (MAX_SOURCE_BYTES + 1))
        self.assertEqual(decode_upload("﻿D0Evar('é')".encode("utf-8")), "D0Evar('é')")

    def test_line_endings_are_normalized_so_the_editor_matches_the_source(self):
        applied = self.model.load("windows.lambda", "D0Eint(\r\n1)\r# old mac\r\n")
        self.assertEqual(applied.text, "D0Eint(\n1)\n# old mac\n")
        # A browser form field reports the same text with CRLF line endings.
        self.model.edit("D0Eint(\r\n1)\r\n# old mac\r\n")
        self.assertFalse(self.model.snapshot().has_unapplied_edits)

    def test_a_rejection_keeps_results_and_revision(self):
        self.model.finish(self.model.begin(Operation.LINT), OK)
        self.model.edit(" ")
        with self.assertRaises(SourceRejected):
            self.model.apply_edits()
        self.assertEqual(len(self.model.snapshot().results), 1)


class Operations(unittest.TestCase):
    def setUp(self):
        self.model = Workbench()

    def test_source_operations_need_an_applied_source(self):
        for operation in Operation:
            with self.subTest(operation=operation):
                with self.assertRaises(OperationUnavailable):
                    self.model.begin(operation)
        self.assertIsNone(self.model.snapshot().busy)

    def test_operations_are_blocked_by_unapplied_edits(self):
        self.model.load("a.lambda", "D0Eint(1)")
        self.model.edit("D0Eint(2)")
        with self.assertRaises(UnappliedEdits):
            self.model.begin(Operation.INTERPRET)

    def test_result_records_operation_revision_and_outcome(self):
        self.model.load("a.lambda", "D0Eint(1)")
        self.model.load("b.lambda", "D0Eint(2)")
        ticket = self.model.begin(Operation.INTERPRET)
        self.assertEqual((ticket.revision, ticket.source), (2, "D0Eint(2)"))
        result = self.model.finish(ticket, ToolOutput(Outcome.SUCCESS, "D0Vint(arg1=2)"))
        self.assertEqual((result.operation, result.revision, result.outcome, result.text),
                         (Operation.INTERPRET, 2, Outcome.SUCCESS, "D0Vint(arg1=2)"))
        self.assertEqual(self.model.snapshot().results, (result,))

    def test_results_are_newest_first_and_capped(self):
        self.model.load("a.lambda", "D0Eint(1)")
        for number in range(MAX_RESULTS + 5):
            self.model.finish(self.model.begin(Operation.LINT),
                              ToolOutput(Outcome.SUCCESS, str(number)))
        results = self.model.snapshot().results
        self.assertEqual(len(results), MAX_RESULTS)
        self.assertEqual(results[0].text, str(MAX_RESULTS + 4))

    def test_a_new_revision_clears_results(self):
        self.model.load("a.lambda", "D0Eint(1)")
        self.model.finish(self.model.begin(Operation.LINT), OK)
        self.model.edit("D0Eint(2)")
        self.model.apply_edits()
        self.assertEqual(self.model.snapshot().results, ())

    def test_everything_is_blocked_while_busy_and_restored_afterwards(self):
        self.model.load("a.lambda", "D0Eint(1)")
        ticket = self.model.begin(Operation.INTERPRET)
        self.assertIs(self.model.snapshot().busy, Operation.INTERPRET)
        for attempt in [lambda: self.model.begin(Operation.LINT),
                        lambda: self.model.edit("D0Eint(2)"),
                        lambda: self.model.load("b.lambda", "D0Eint(2)"),
                        self.model.open_manual_input,
                        self.model.apply_edits,
                        self.model.discard_edits]:
            with self.assertRaises(BusyError):
                attempt()
        self.assertTrue(all(self.model.snapshot().blocked.values()))
        self.model.finish(ticket, OK)
        snapshot = self.model.snapshot()
        self.assertIsNone(snapshot.busy)
        self.assertIsNone(snapshot.blocked[Operation.LINT])
        self.assertEqual(snapshot.source.text, "D0Eint(1)")

    def test_finish_rejects_a_ticket_that_is_not_in_progress(self):
        self.model.load("a.lambda", "D0Eint(1)")
        ticket = self.model.begin(Operation.LINT)
        self.model.finish(ticket, OK)
        with self.assertRaises(ModelError):
            self.model.finish(ticket, OK)


class ExecuteAndArtifacts(unittest.TestCase):
    def setUp(self):
        self.model = Workbench()
        self.model.load("a.lambda", "D0Eint(1)")

    def compile_with(self, output):
        return self.model.finish(self.model.begin(Operation.COMPILE), output)

    def test_execute_is_unavailable_without_an_artifact(self):
        snapshot = self.model.snapshot()
        self.assertIn("Compilation is not yet implemented", snapshot.blocked[Operation.EXECUTE])
        self.assertIsNone(snapshot.blocked[Operation.COMPILE])
        with self.assertRaises(OperationUnavailable):
            self.model.begin(Operation.EXECUTE)

    def test_placeholder_compile_does_not_enable_execute(self):
        self.compile_with(ToolOutput(Outcome.NOT_IMPLEMENTED, "not yet"))
        self.assertIsNone(self.model.snapshot().artifact)
        with self.assertRaises(OperationUnavailable):
            self.model.begin(Operation.EXECUTE)

    def test_only_compile_can_produce_an_artifact(self):
        artifact = Artifact(0, "python", "print(1)")
        self.model.finish(self.model.begin(Operation.LINT),
                          ToolOutput(Outcome.SUCCESS, "fine", artifact))
        self.assertIsNone(self.model.snapshot().artifact)

    def test_successful_compile_stores_an_artifact_for_its_revision(self):
        self.compile_with(ToolOutput(Outcome.SUCCESS, "compiled", Artifact(0, "python", "print(1)")))
        self.assertEqual(self.model.snapshot().artifact, Artifact(1, "python", "print(1)"))
        ticket = self.model.begin(Operation.EXECUTE)
        self.assertEqual(ticket.artifact.code, "print(1)")

    def test_source_change_and_failed_recompile_invalidate_the_artifact(self):
        compiled = ToolOutput(Outcome.SUCCESS, "compiled", Artifact(0, "python", "print(1)"))
        self.compile_with(compiled)
        self.compile_with(ToolOutput(Outcome.LANGUAGE_ERROR, "type error"))
        self.assertIsNone(self.model.snapshot().artifact)
        self.compile_with(compiled)
        self.model.edit("D0Eint(2)")
        self.model.apply_edits()
        self.assertIsNone(self.model.snapshot().artifact)


if __name__ == "__main__":
    unittest.main()
