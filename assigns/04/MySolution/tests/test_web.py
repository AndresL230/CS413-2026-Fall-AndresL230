"""The whole application through its HTTP routes, with the real backend."""
import io
import unittest
from pathlib import Path

from lambda_workbench.backend import LambdaBackend
from lambda_workbench.controller import WorkbenchController
from lambda_workbench.examples import load_canned_examples
from lambda_workbench.model import Workbench
from lambda_workbench.web import create_app

EXAMPLES = Path(__file__).resolve().parent.parent / "examples"
STATIC = Path(__file__).resolve().parent.parent / "static"


class WebTestCase(unittest.TestCase):
    timeout_seconds = 5.0

    def setUp(self):
        controller = WorkbenchController(
            Workbench(), LambdaBackend(self.timeout_seconds), load_canned_examples())
        self.client = create_app(controller).test_client()

    def post(self, path, editor_text=None):
        payload = {} if editor_text is None else {"editorText": editor_text}
        return self.client.post(path, json=payload)

    def apply(self, text):
        response = self.post("/api/source/apply", text)
        self.assertEqual(response.status_code, 200, response.json)
        return response.json["state"]

    def run_action(self, operation):
        response = self.post(f"/api/actions/{operation}")
        self.assertEqual(response.status_code, 200, response.json)
        return response.json["state"]["results"][0]

    def upload(self, name, data):
        return self.client.post(
            "/api/source/upload", data={"file": (io.BytesIO(data), name)},
            content_type="multipart/form-data")


class Page(WebTestCase):
    def test_page_and_assets_are_served(self):
        with self.client.get("/") as page:
            self.assertEqual(page.status_code, 200)
            self.assertIn(b'<label for="source-menu">Load source</label>', page.data)
            self.assertEqual(page.headers["Content-Security-Policy"], "default-src 'self'")
        with self.client.get("/static/app.js") as script:
            self.assertEqual(script.status_code, 200)

    def test_initial_state_lists_buttons_in_the_required_order(self):
        state = self.client.get("/api/state").json["state"]
        self.assertEqual([action["label"] for action in state["actions"]],
                         ["Lint", "Interpret", "Type-check", "Compile", "Execute"])
        self.assertTrue(all(not action["enabled"] for action in state["actions"]))
        self.assertEqual([example["label"] for example in state["examples"]],
                         ["Factorial (canned)", "Fibonacci (canned)"])
        self.assertIsNone(state["source"])

    def test_the_browser_view_never_builds_markup_from_text(self):
        script = (STATIC / "app.js").read_text(encoding="utf-8")
        for unsafe in ["innerHTML", "outerHTML", "insertAdjacentHTML", "document.write"]:
            self.assertNotIn(unsafe, script)


class SourceAndActions(WebTestCase):
    def test_canned_examples_interpret_to_their_values(self):
        for key, expected in [("factorial", "D0Vint(arg1=120)"), ("fibonacci", "D0Vint(arg1=55)")]:
            with self.subTest(example=key):
                loaded = self.post(f"/api/source/example/{key}").json
                self.assertEqual(loaded["status"], "ok")
                result = self.run_action("interpret")
                self.assertEqual((result["outcomeLabel"], result["text"]), ("Success", expected))
                self.assertEqual(result["revision"], loaded["state"]["source"]["revision"])

    def test_open_expression_fails_lint_then_passes_after_editing(self):
        self.apply('D0Evar("x")')
        result = self.run_action("lint")
        self.assertEqual((result["outcomeLabel"], result["text"], result["revision"]),
                         ("Lint error", "Undeclared variable(s): x", 1))
        state = self.apply('D0Elam("x", D0Evar("x"))')
        self.assertEqual((state["source"]["revision"], state["results"]), (2, []))
        result = self.run_action("lint")
        self.assertEqual((result["outcomeLabel"], result["text"], result["revision"]),
                         ("Success", "No free variables found.", 2))

    def test_lint_passes_but_interpret_fails_at_run_time(self):
        self.apply((EXAMPLES / "division-by-zero.lambda").read_text(encoding="utf-8"))
        self.assertEqual(self.run_action("lint")["outcomeLabel"], "Success")
        result = self.run_action("interpret")
        self.assertEqual((result["outcomeLabel"], result["text"]),
                         ("Runtime error", "Runtime error: division by zero"))

    def test_malformed_input_is_an_input_error(self):
        self.apply("D0Eint(")
        result = self.run_action("interpret")
        self.assertEqual(result["outcomeLabel"], "Input error")

    def test_placeholders_and_disabled_execute(self):
        self.apply("D0Eint(1)")
        typecheck = self.run_action("typecheck")
        self.assertEqual((typecheck["outcomeLabel"], typecheck["text"]),
                         ("Not implemented", "Type checking is not yet implemented."))
        compiled = self.run_action("compile")
        self.assertEqual(compiled["outcomeLabel"], "Not implemented")
        state = self.client.get("/api/state").json["state"]
        execute = state["actions"][-1]
        self.assertEqual((execute["id"], execute["enabled"]), ("execute", False))
        self.assertIn("Compilation is not yet implemented", execute["reason"])
        self.assertFalse(state["hasArtifact"])
        refused = self.post("/api/actions/execute")
        self.assertEqual(refused.status_code, 409)

    def test_html_like_text_round_trips_unchanged(self):
        text = (EXAMPLES / "html-like.lambda").read_text(encoding="utf-8")
        state = self.apply(text)
        self.assertEqual(state["source"]["text"], text)
        result = self.run_action("lint")
        self.assertEqual(result["text"],
                         "Undeclared variable(s): <b>bold</b><script>alert(1)</script>")

    def test_unapplied_edits_block_actions_and_replacement(self):
        self.apply("D0Eint(1)")
        self.assertEqual(self.post("/api/actions/lint", "D0Eint(2)").status_code, 409)
        self.assertEqual(self.post("/api/source/example/factorial", "D0Eint(2)").status_code, 409)
        discarded = self.post("/api/source/discard").json["state"]
        self.assertEqual(discarded["editor"]["text"], "D0Eint(1)")
        self.assertEqual(self.post("/api/source/example/factorial").status_code, 200)


class Uploads(WebTestCase):
    def test_upload_becomes_the_applied_source(self):
        response = self.upload("prog.lambda", b'D0Eop2("+", D0Eint(20), D0Eint(22))')
        self.assertEqual(response.status_code, 200)
        source = response.json["state"]["source"]
        self.assertEqual((source["name"], source["revision"]), ("prog.lambda", 1))
        self.assertEqual(self.run_action("interpret")["text"], "D0Vint(arg1=42)")

    def test_upload_is_accepted_while_a_multiline_source_is_in_the_editor(self):
        # Browsers send form fields with CRLF line endings.
        self.apply("D0Eint(\n1)\n")
        response = self.client.post(
            "/api/source/upload", content_type="multipart/form-data",
            data={"file": (io.BytesIO(b"D0Eint(\r\n2)\r\n"), "two.lambda"),
                  "editorText": "D0Eint(\r\n1)\r\n"})
        self.assertEqual(response.status_code, 200, response.json)
        state = response.json["state"]
        self.assertEqual((state["source"]["text"], state["editor"]["hasUnappliedEdits"]),
                         ("D0Eint(\n2)\n", False))

    def test_rejected_uploads_keep_the_previous_source(self):
        self.apply("D0Eint(1)")
        for name, data in [("empty.lambda", b""), ("binary.lambda", b"\xff\xfe\x00"),
                           ("big.lambda", b"#" * 70_000), ("huge.lambda", b"#" * 2_000_000)]:
            with self.subTest(file=name):
                response = self.upload(name, data)
                self.assertEqual(response.status_code, 422)
                self.assertEqual(response.json["status"], "rejected")
                source = response.json["state"]["source"]
                self.assertEqual((source["text"], source["revision"]), ("D0Eint(1)", 1))

    def test_cross_origin_posts_are_refused(self):
        response = self.client.post("/api/source/apply", json={"editorText": "D0Eint(1)"},
                                    headers={"Origin": "http://evil.example"})
        self.assertEqual(response.status_code, 403)
        self.assertIsNone(self.client.get("/api/state").json["state"]["source"])


class Timeout(WebTestCase):
    timeout_seconds = 0.5

    def test_timeout_restores_controls_and_allows_retry(self):
        slow = (EXAMPLES / "slow-fibonacci.lambda").read_text(encoding="utf-8")
        self.apply(slow)
        result = self.run_action("interpret")
        self.assertEqual(result["outcomeLabel"], "Timed out")
        state = self.client.get("/api/state").json["state"]
        self.assertIsNone(state["busy"])
        self.assertEqual(state["source"]["text"], slow)
        self.assertTrue(state["actions"][1]["enabled"])
        # Retry with a program that finishes.
        self.apply(slow.replace("D0Eint(40))", "D0Eint(10))"))
        self.assertEqual(self.run_action("interpret")["text"], "D0Vint(arg1=55)")


if __name__ == "__main__":
    unittest.main()
