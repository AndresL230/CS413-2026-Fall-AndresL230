# Testing: LAMBDA workbench

## Running the automated tests

```sh
.venv/bin/python -m unittest discover -s tests -t .
```

There are 109 tests in seven files. They use only the standard library
`unittest` module and Flask's test client. The whole run takes about two
seconds; one test deliberately waits half a second for a timeout.

| File | Needs | What it covers |
| --- | --- | --- |
| `tests/test_reader.py` | nothing | The restricted constructor reader. |
| `tests/test_tools.py` | nothing | `d0exp_fvset`, Lint and Interpret, called in process. |
| `tests/test_backend.py` | worker process | `LambdaBackend`: real tools through the worker, time bound, placeholders. |
| `tests/test_model.py` | nothing | The model alone. No browser, web server or backend. |
| `tests/test_controller.py` | test backend | The controller with `RecordingBackend` and `BlockingBackend` substituted. No view code. |
| `tests/test_web.py` | Flask test client | The HTTP routes with the real backend. |
| `tests/test_architecture.py` | nothing | Import rules between components. |

## Coverage of the required test areas

| Area in the assignment | Tests |
| --- | --- |
| 1. Free variables: every constructor, duplicates, nested bindings, recursive functions, let initializer scope, `frozenset` result | `test_tools.FreeVariables` (every assertion also checks the type is `frozenset`) |
| 2. Lint success, Lint error listing names, Lint does not evaluate | `test_tools.Lint`, `test_backend.RealTools.test_lint_runs_through_the_worker` |
| 3. Interpretation of arithmetic, factorial and Fibonacci with base cases; malformed input; runtime failures | `test_tools.Interpret`, `test_backend.RealTools`, `test_web.SourceAndActions` |
| 4. Manual input, source replacement, editing, rejection without losing the applied source | `test_model.SourceEntry`, `test_model.Rejection`, `test_controller.SourceChanges`, `test_web.Uploads` |
| 5. Backend dispatch; placeholders are not successes; Execute unavailable | `test_controller.Dispatch`, `test_backend.Placeholders`, `test_model.ExecuteAndArtifacts`, `test_web.SourceAndActions.test_placeholders_and_disabled_execute` |
| 6. Busy state, backend failure or timeout, retry | `test_model.Operations.test_everything_is_blocked_while_busy_and_restored_afterwards`, `test_controller.FailureAndBusy`, `test_backend.TimeBound`, `test_web.Timeout` |

The model test requirement is met by all of `test_model.py`. The controller
test requirement is met by all of `test_controller.py`, which constructs
`WorkbenchController` with a test backend and imports no view module.

## Traceability to F1–F10

"Browser" refers to the numbered steps in the smoke test below.

| ID | Automated | Browser |
| --- | --- | --- |
| F1 | `test_controller.SourceChanges` (examples, upload name), `test_web.Uploads`, `test_web.Page.test_initial_state_lists_buttons_in_the_required_order` | 2, 3, 4, 11 |
| F2 | `test_model.SourceEntry`, `test_controller.Dispatch.test_actions_run_on_the_applied_source_not_on_unapplied_edits`, `test_web.SourceAndActions.test_unapplied_edits_block_actions_and_replacement` | 4, 5, 9 |
| F3 | `test_model.Rejection`, `test_controller.SourceChanges.test_rejected_uploads_keep_the_applied_source`, `test_web.Uploads.test_rejected_uploads_keep_the_previous_source` | 9, 11 |
| F4 | `test_web.Page.test_initial_state_lists_buttons_in_the_required_order`, `test_model.Operations.test_source_operations_need_an_applied_source`, `test_model.ExecuteAndArtifacts` | 1, 7 |
| F5 | `test_tools.Lint`, `test_web.SourceAndActions.test_open_expression_fails_lint_then_passes_after_editing` | 4, 5 |
| F6 | `test_tools.Interpret`, `test_web.SourceAndActions.test_malformed_input_is_an_input_error`, `test_lint_passes_but_interpret_fails_at_run_time` | 2, 3, 6 |
| F7 | `test_backend.Placeholders`, `test_web.SourceAndActions.test_placeholders_and_disabled_execute` | 7 |
| F8 | `test_model.SourceEntry.test_each_accepted_change_is_a_new_revision`, `test_model.Operations.test_a_new_revision_clears_results`, `test_model.ExecuteAndArtifacts.test_source_change_and_failed_recompile_invalidate_the_artifact` | 2–5, 9 |
| F9 | `test_model.Operations.test_result_records_operation_revision_and_outcome`, `test_web.SourceAndActions.test_html_like_text_round_trips_unchanged`, `test_web.Page.test_the_browser_view_never_builds_markup_from_text` | 8, 12 |
| F10 | `test_controller.FailureAndBusy`, `test_web.Timeout` | 10 |

## Browser smoke test

- **Date:** 2026-10-07
- **Browser:** Chrome 154 on Linux x86_64
- **Server:** `python app.py`, Python 3.13.13, Flask 3.1.3, default 5 second timeout
- **Method:** steps 1–11 were driven by a script run in the page that clicks
  the real buttons, sets the editor text and fires its `input` event, then
  reads back what the page displays. Step 12 used real keyboard input only.
  This was run by the AI assistant through a browser automation tool; see
  `AI-TRANSCRIPT.md`.

| # | Step | Expected | Observed |
| --- | --- | --- | --- |
| 1 | Open the page. | No applied source. All five buttons disabled, in the order Lint, Interpret, Type-check, Compile, Execute. | As expected. Status "Ready." |
| 2 | Load **Factorial (canned)**, then Interpret. | Revision 1; value 120. | "Applied source: Factorial (canned), revision 1". Result "Interpret · revision 1 · Success", `D0Vint(arg1=120)`. Execute stayed disabled. |
| 3 | Load **Fibonacci (canned)**, then Interpret. | Revision 2, earlier result cleared; value 55. | Revision 2, results empty after loading, then `D0Vint(arg1=55)`. |
| 4 | Load **Manual input**, type `D0Evar("x")`. Apply. Lint. | Blank editor with focus. While typing: actions and Load disabled, Apply enabled. After Apply: new revision. Lint reports `x`. | Editor blank and focused. Note "All actions are disabled: Apply or discard the changes in the editor first." After Apply a new revision. "Lint · Lint error", "Undeclared variable(s): x". |
| 5 | Edit to `D0Elam("x", D0Evar("x"))`. Apply. Lint. | New revision, results cleared, Lint passes. | New revision, results cleared, "Lint · Success", "No free variables found." |
| 6 | Apply `D0Eop2("/", D0Eint(1), D0Eint(0))`. Lint, then Interpret. | Lint passes; Interpret reports a runtime error. | "Lint · Success", then "Interpret · Runtime error", "Runtime error: division by zero". |
| 7 | Type-check. Compile. Look at Execute. | Two "not implemented" results. Execute disabled with an explanation. | "Type checking is not yet implemented." and "Compilation is not yet implemented. No generated code was produced, so Execute stays unavailable." Execute disabled; note "Execute is disabled: Execute runs code generated by Compile. Compilation is not yet implemented, so no generated code exists." |
| 8 | Apply a source whose variable name is `<b>bold</b><img src=x onerror=alert(1)>`. Lint. | The name appears as literal text in the editor and the result. No markup is created and no script runs. | Result text showed the name literally. The result contained 0 child elements, no `img`, `b` or `i` elements existed in the results, and `alert` was not called. Line breaks preserved (`white-space: pre-wrap`). |
| 9 | Replace the editor text with spaces. Apply. Then Discard. | Rejected; applied source and results unchanged; the spaces stay in the editor. Discard restores the applied text. | "Rejected: The source is empty. The applied source is unchanged." Source line and result unchanged, editor still held the spaces. After Discard the editor matched the applied source and the actions were enabled. |
| 10 | Apply naive Fibonacci of 40. Interpret. While it runs, check the page and send a second request. Afterwards apply Fibonacci of 10 and Interpret. | Busy status; controls disabled; editor read-only; second request refused. After 5 seconds: "Timed out", controls restored, source kept. Retry succeeds. | Status "Working: Interpret is running…", `aria-busy="true"`, editor read-only, all buttons disabled, second request answered 409. After about 6 seconds: "Interpret · Timed out", "Stopped after 5 seconds without a result. The program may not terminate." Controls restored, source unchanged. Retry gave `D0Vint(arg1=55)`. |
| 11 | With a multiline source applied, upload: a file with invalid UTF-8; a 70,000 byte file; an empty file; then a valid file with Windows line endings. Interpret. | Three rejections with reasons, applied source unchanged. The valid file loads as a new revision with no unapplied edits. | "The file is not valid UTF-8 text.", "The source is 70000 bytes; the limit is 65536 bytes.", "The source is empty." each with the source unchanged. The valid file loaded as a new revision, the editor reported no unapplied changes, and Interpret gave `D0Vint(arg1=42)`. |
| 12 | Keyboard only: Tab to the menu, Down to Manual input, Tab, Enter. Type `D0Epair(D0Evar("<b>y</b>"), D0Eint(1))`. Tab, Enter (Apply). Tab, Enter (Lint). Tab, Enter (Interpret). | Every step works without a mouse and focus is never lost. | Worked. After Apply, focus returned to the editor; after Lint and Interpret it stayed on the button used. Lint: "Undeclared variable(s): `<b>y</b>`". Interpret: "Runtime error: evaluation produced the error value D0V000() in D0Vpair(...)". |

No errors appeared in the browser console.

### Defects found by the smoke test and fixed

1. **Upload refused after a multiline source (step 11).** Browsers send form
   fields with CRLF line endings, so the editor text sent with an upload did
   not match the applied source and the model reported unapplied edits. A file
   saved with Windows line endings would also have been shown as permanently
   edited. Fixed by normalizing line endings in the model. Regression tests:
   `test_model.Rejection.test_line_endings_are_normalized_so_the_editor_matches_the_source`
   and `test_web.Uploads.test_upload_is_accepted_while_a_multiline_source_is_in_the_editor`.
2. **Keyboard focus lost after Apply (step 12).** A button that becomes
   disabled drops focus to the page body. Fixed in `app.js` by restoring focus
   to the control that was used, or to the editor. This is checked only by
   step 12; there is no automated browser test.

### Not covered

- The operating system's file picker was not operated. Uploads in step 11 were
  placed on the page's file input by script, which exercises the same upload
  request.
- Only Chrome was used. Firefox and Safari were not tested.
- No screen reader was used. Labels, the live status region and text-only
  status were checked by inspection.
- The page was restyled after this smoke test (light theme, numbered sections,
  a description under each control). The controls, their ids and their
  behavior did not change. After the restyle only a short check was made:
  load Factorial, then Lint, Interpret and Compile, with the results as in
  steps 2 and 7. The twelve steps were not repeated in full.
- Steps 2–11 were run before the two fixes above and step 11 was repeated
  after them. Steps 2–10 were not repeated in the browser after the fixes; the
  automated suite was.
