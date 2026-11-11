# Testing — LAMBDA3 JSON-RPC Service

Two suites are run from `assigns/07/`:

| Suite | Command | Needs running server? | Result |
| --- | --- | --- | --- |
| Ours: HTTP-level, Flask test client (`MySolution/tests/`) | `MySolution/.venv/bin/python -m pytest MySolution/tests -v` | no | **159 passed** |
| Instructor black-box (`TEST/test_rpc_api.py`) | `python3 -m unittest discover -s TEST -v` | yes: `MySolution/.venv/bin/python MySolution/server.py` | **15 tests, OK** |

Environment: Python 3.14.8, Flask 3.1.3, Werkzeug 3.1.9, pytest 9.2.0
(Linux).

## How the tests are built

- **Real HTTP requests.** Every test goes through the Flask test client and
  sends real HTTP POSTs to `/rpc`.
- **HTTP and envelope.** The `Rpc` helper in `tests/conftest.py` asserts the
  HTTP status, then `check_envelope` asserts:
  - `jsonrpc == "2.0"`;
  - the exact `id`, with the same JSON type as the request's;
  - exactly one of `result`/`error`;
  - no extra members;
  - for errors, an integer `code` and a string `message`.
- **No leaks.** `assert_no_leak` runs on **every error response**. It fails
  if the body contains `Traceback`, `File "`, `.py`, `/home`, the LAMBDA3
  directory path, `0x` object addresses, `Error:`, `Exception`, or
  `object at`.
- **Real LAMBDA3 for successes.** Successful typecheck, interpret, and
  compile tests call the real LAMBDA3. The compile tests also check that the
  returned code is byte-for-byte the output of
  `d0exp_compile` / `d0exp_compile_js`.
- **Test doubles in two places only.**
  - `ExplodingService` in `test_injected_failures.py` injects unexpected
    backend exceptions.
  - The spy service in `test_dispatch_boundary.py` checks dispatch
    boundaries.
- **Timeout uses the real interpreter.** The deadline is lowered to 1 s
  through `create_app` overrides, and the program is the real `fib(30)`.
- **Worker failure uses the real worker.** `WORKER_STACK_BYTES=1` makes
  `threading.stack_size` fail inside the spawned child process.

## Required behaviors → tests

All tests listed below **passed** in the run recorded at the end of this file.

| # | Required behavior (Assign07 §3) | Tests (`MySolution/tests/…`) | Observed |
| --- | --- | --- | --- |
| 1 | `service.health` returns status and API version and keeps the request id | `test_health.py::test_health_returns_status_and_version`, `::test_health_preserves_request_id_and_type[health-1 / 17 / 0 / -3 / 1.5 / None]`, `::test_health_absent_params_is_accepted`, `::test_health_rejects_unknown_params` | `{"status":"ok","version":"1.0"}`; string, integer, float and null ids all echoed with the same type |
| 2 | Type-checking valid programs returns the formatted type | `test_typecheck.py::test_typecheck_valid_program_returns_formatted_type[arithmetic / factorial_function / tuple / list]`, `::test_typecheck_accepts_source_of_exactly_max_size` | `sint`, `sint -> sint`, `(sint, bool)`, `List[sint]`; a 32,768-char source is accepted |
| 3 | Interpretation: arithmetic, factorial, tuple, collection; type and value | `test_interpret.py::test_interpret_returns_type_and_formatted_value[arithmetic / factorial / tuple / list / print_returns_unit]`, `::test_interpret_large_integer_result_formats_without_error`, `::test_interpret_long_integer_literal_parses` | `42`, `720`, `(1, true)`, `[1, 2]`, `()` of type `unit`; integers over 4,300 digits format correctly |
| 4 | Python and JavaScript compilation return nonempty code and the right target | `test_compile.py::test_compile_returns_target_and_code_identical_to_lambda3[python / javascript × arith / fact / tuple]`, `::test_compile_python_and_javascript_differ`, `::test_compile_type_error_is_reported_before_codegen` | `target` echoed; `code` identical to LAMBDA3's output; an ill-typed source gets `-32011` with no code generated |
| 5 | Syntax and type errors have distinct documented codes | `test_lambda_errors.py::test_syntax_error_single_line_has_position_and_snippet`, `::test_syntax_error_multi_line_reports_the_right_line`, `::test_syntax_error_snippet_is_truncated_to_200_chars`, `::test_type_error_has_detail`, `::test_syntax_and_type_error_codes_are_distinct` | `-32010` with `{line:1, column:4, snippet:"if then"}` (and line 3 for the multi-line case); `-32011` with `detail` |
| 6 | Malformed JSON, invalid envelopes, unknown methods, absent/wrongly typed params, blank source, oversized source | `test_protocol.py` (all 23 tests: parse errors incl. non-UTF-8, NaN and deeply nested JSON; 12 invalid-envelope variants; unknown method; case-sensitive names; array/absent/null params); `test_params.py` (all 37 tests: wrong-type/blank/missing source, unknown key, bad/missing target, code points vs bytes); `test_runtime_and_limits.py::test_oversized_source_rejected_with_limit_and_actual`, `::test_deeply_nested_source_is_invalid_params_not_internal[typecheck / interpret / compile]`, `::test_long_operator_chain_is_nesting_error`; `test_transport.py` (all 18 tests: 415, 405 + `Allow`, 413, 404, 204, charset accepted) | `-32700` / `-32600` with `id: null`; `-32601` keeps the id; `-32602` with the documented `data`; oversized → `limit: 32768, actual: 32769`; deep nesting → `-32602` "source nesting too deep" (never `-32603`); transport errors use HTTP status codes with plain-text bodies |
| 7 | A function result is formatted without leaking closure internals | `test_function_values.py::test_lam_value_is_formatted_as_lam_without_internals`, `::test_fix_value_is_formatted_as_fix_without_internals`, `::test_function_values_contain_no_closure_or_env_internals` | `<lam>` and `<fix>`; no environment or object reprs |
| 8 | Injected backend failure or timeout returns the documented error, keeps the id, no traceback | `test_injected_failures.py::test_unexpected_failure_is_internal_error_without_data_or_leak`, `::test_unexpected_failure_traceback_is_logged_server_side`, `::test_unexpected_failure_in_compile_is_internal_error`, `::test_injected_failure_in_batch_does_not_break_other_members`; `test_worker_failures.py::test_worker_setup_failure_logs_traceback_but_hides_it`; `test_runtime_and_limits.py::test_slow_program_times_out_with_configured_seconds`, `::test_timeout_leaves_server_usable`, `::test_division_by_zero_is_runtime_error`, `::test_head_of_empty_list_is_invalid_operation`, `::test_unbounded_recursion_is_recursion_depth_exceeded_not_timeout` | `-32603` with exactly `{"code":-32603,"message":"Internal error"}` and id kept, while the traceback shows up only in the server log (`caplog`); real `fib(30)` → `-32012` `{seconds: 1}` and the server stays usable; `-32013` kinds `division_by_zero`, `invalid_operation`, `recursion_depth_exceeded` |
| 9 | LAMBDA3 type-checking rejects an unbound variable | `test_lambda_errors.py::test_unbound_variable_rejected_by_typecheck`, `::test_unbound_variable_rejected_by_interpret_without_running`, `::test_unbound_variable_rejected_by_compile` | `-32011` `"unbound variable 'x'"` from all three methods |
| 10 | Batches keep ids and omit notifications; invalid members get `id: null`; notification-only batch → empty body; empty batch → one Invalid Request; single notification → no body + documented status | `test_batch.py` (all 9 tests), `test_transport.py::test_notification_is_204_with_empty_body` | Responses matched by id (mixed string/number ids); notifications omitted, even failing ones; invalid members → `-32600` `id: null`; notification-only → `204` empty; `[]` → a single `-32600` object; single notification → `204` empty |

Additional tests outside the ten items:

- `test_mylib.py`: all four `LAMBDA3/mylib` files, sent as
  `let <file> in <expr> end`, type-check, interpret, and compile to both
  targets. For example, `list.lam` gives `[1, 4, 9, 16, 25]`.
- `test_dispatch_boundary.py`: five tests using a spy service:
  - validated params reach the service unchanged;
  - a notification invokes its method exactly once and returns nothing;
  - invalid requests never reach the service;
  - a source-size override is honored;
  - the dispatcher module does not depend on LAMBDA3.

## Architecture

```
  HTTP client (curl, TEST/test_rpc_api.py, Flask test client)
        │  POST /rpc   Content-Type: application/json
        ▼
┌──────────────────────────────────────────────────────────┐
│ transport.py — Flask                                     │
│  415 wrong media type · 405 non-POST · 413 > 1 MiB · 404 │
│  200 + JSON-RPC body  ·  204 when nothing to answer      │
└───────────────┬──────────────────────────────────────────┘
                │ raw bytes
                ▼
┌──────────────────────────────────────────────────────────┐
│ jsonrpc.py — envelope + dispatcher (no LAMBDA3 imports)  │
│  decode (-32700) · validate envelope (-32600, id null)   │
│  batches · notifications · id preservation               │
│  unexpected exception → log traceback, return -32603     │
└───────────────┬──────────────────────────────────────────┘
                │ method name + params object
                ▼
┌──────────────────────────────────────────────────────────┐
│ methods.py — registry + param validation (-32601/-32602) │
└───────────────┬──────────────────────────────────────────┘
                ▼
┌──────────────────────────────────────────────────────────┐
│ service.py — LAMBDA3 adapter                             │
│  LambdaSyntaxError → -32010 · TypeCheckError → -32011    │
│  RecursionError in parse/check/compile → -32602          │
└──────┬──────────────────────────────────────┬────────────┘
       │ typecheck / compile                  │ interpret
       │ (in the service process)             ▼
       │                ┌──────────────────────────────────┐
       │                │ worker.py — spawned process      │
       │                │  5 s deadline, kill → -32012     │
       │                │  100k recursion, 512 MiB stack   │
       │                │  runtime exceptions → -32013     │
       │                └───────────────┬──────────────────┘
       ▼                                ▼
┌──────────────────────────────────────────────────────────┐
│ LAMBDA3/lambda3.py (provided, unmodified)                │
│  d0exp_parse_and_typecheck · format_type · d0exp_evaluate│
│  d0val_format · d0exp_compile · d0exp_compile_js         │
└──────────────────────────────────────────────────────────┘
```

Each layer depends only on the one below it. The transport knows nothing
about JSON-RPC methods, and the dispatcher knows nothing about LAMBDA3
(`test_dispatcher_is_independent_of_lambda3` checks this). Only `service.py`
and `worker.py` import `lambda3`.

## Observed output

### Our suite (pytest)

The `[ nn%]` progress column was removed. Everything else is verbatim.

```
============================= test session starts ==============================
platform linux -- Python 3.14.8, pytest-9.2.0, pluggy-1.7.0 -- /home/andresl/Desktop/Courses/Fall 2026/CS 413/CS413-2026-Fall/assigns/07/MySolution/.venv/bin/python
rootdir: /home/andresl/Desktop/Courses/Fall 2026/CS 413/CS413-2026-Fall/assigns/07/MySolution
configfile: pytest.ini
collecting ... collected 159 items

MySolution/tests/test_batch.py::test_batch_matches_by_id_with_mixed_id_types_and_omits_notification PASSED
MySolution/tests/test_batch.py::test_batch_invalid_members_get_null_id_alongside_valid_results PASSED
MySolution/tests/test_batch.py::test_notification_only_batch_is_204_empty_body PASSED
MySolution/tests/test_batch.py::test_empty_batch_is_single_invalid_request_object PASSED
MySolution/tests/test_batch.py::test_single_notification_is_204_empty_body PASSED
MySolution/tests/test_batch.py::test_failing_notification_produces_no_response PASSED
MySolution/tests/test_batch.py::test_failing_notifications_in_batch_are_omitted_but_calls_answered PASSED
MySolution/tests/test_batch.py::test_invalid_notification_still_gets_invalid_request PASSED
MySolution/tests/test_batch.py::test_batch_with_unknown_method_and_bad_params_keeps_ids PASSED
MySolution/tests/test_compile.py::test_compile_returns_target_and_code_identical_to_lambda3[python-arith] PASSED
MySolution/tests/test_compile.py::test_compile_returns_target_and_code_identical_to_lambda3[python-fact] PASSED
MySolution/tests/test_compile.py::test_compile_returns_target_and_code_identical_to_lambda3[python-tuple] PASSED
MySolution/tests/test_compile.py::test_compile_returns_target_and_code_identical_to_lambda3[javascript-arith] PASSED
MySolution/tests/test_compile.py::test_compile_returns_target_and_code_identical_to_lambda3[javascript-fact] PASSED
MySolution/tests/test_compile.py::test_compile_returns_target_and_code_identical_to_lambda3[javascript-tuple] PASSED
MySolution/tests/test_compile.py::test_compile_python_and_javascript_differ PASSED
MySolution/tests/test_compile.py::test_compile_type_error_is_reported_before_codegen PASSED
MySolution/tests/test_dispatch_boundary.py::test_dispatcher_passes_validated_params_to_service PASSED
MySolution/tests/test_dispatch_boundary.py::test_notification_invokes_method_once_but_returns_nothing PASSED
MySolution/tests/test_dispatch_boundary.py::test_invalid_requests_never_reach_the_service PASSED
MySolution/tests/test_dispatch_boundary.py::test_max_source_override_is_honored_by_validation PASSED
MySolution/tests/test_dispatch_boundary.py::test_dispatcher_is_independent_of_lambda3 PASSED
MySolution/tests/test_function_values.py::test_lam_value_is_formatted_as_lam_without_internals PASSED
MySolution/tests/test_function_values.py::test_fix_value_is_formatted_as_fix_without_internals PASSED
MySolution/tests/test_function_values.py::test_function_values_contain_no_closure_or_env_internals PASSED
MySolution/tests/test_health.py::test_health_returns_status_and_version PASSED
MySolution/tests/test_health.py::test_health_preserves_request_id_and_type[health-1] PASSED
MySolution/tests/test_health.py::test_health_preserves_request_id_and_type[17] PASSED
MySolution/tests/test_health.py::test_health_preserves_request_id_and_type[0] PASSED
MySolution/tests/test_health.py::test_health_preserves_request_id_and_type[-3] PASSED
MySolution/tests/test_health.py::test_health_preserves_request_id_and_type[1.5] PASSED
MySolution/tests/test_health.py::test_health_preserves_request_id_and_type[None] PASSED
MySolution/tests/test_health.py::test_health_absent_params_is_accepted PASSED
MySolution/tests/test_health.py::test_health_rejects_unknown_params PASSED
MySolution/tests/test_injected_failures.py::test_unexpected_failure_is_internal_error_without_data_or_leak PASSED
MySolution/tests/test_injected_failures.py::test_unexpected_failure_traceback_is_logged_server_side PASSED
MySolution/tests/test_injected_failures.py::test_unexpected_failure_in_compile_is_internal_error PASSED
MySolution/tests/test_injected_failures.py::test_injected_failure_in_batch_does_not_break_other_members PASSED
MySolution/tests/test_interpret.py::test_interpret_returns_type_and_formatted_value[arithmetic] PASSED
MySolution/tests/test_interpret.py::test_interpret_returns_type_and_formatted_value[factorial] PASSED
MySolution/tests/test_interpret.py::test_interpret_returns_type_and_formatted_value[tuple] PASSED
MySolution/tests/test_interpret.py::test_interpret_returns_type_and_formatted_value[list] PASSED
MySolution/tests/test_interpret.py::test_interpret_returns_type_and_formatted_value[print_returns_unit] PASSED
MySolution/tests/test_interpret.py::test_interpret_large_integer_result_formats_without_error PASSED
MySolution/tests/test_interpret.py::test_interpret_long_integer_literal_parses PASSED
MySolution/tests/test_lambda_errors.py::test_syntax_error_single_line_has_position_and_snippet PASSED
MySolution/tests/test_lambda_errors.py::test_syntax_error_multi_line_reports_the_right_line PASSED
MySolution/tests/test_lambda_errors.py::test_syntax_error_snippet_is_truncated_to_200_chars PASSED
MySolution/tests/test_lambda_errors.py::test_type_error_has_detail PASSED
MySolution/tests/test_lambda_errors.py::test_syntax_and_type_error_codes_are_distinct PASSED
MySolution/tests/test_lambda_errors.py::test_unbound_variable_rejected_by_typecheck PASSED
MySolution/tests/test_lambda_errors.py::test_unbound_variable_rejected_by_interpret_without_running PASSED
MySolution/tests/test_lambda_errors.py::test_unbound_variable_rejected_by_compile PASSED
MySolution/tests/test_mylib.py::test_mylib_demo_typechecks[list.lam] PASSED
MySolution/tests/test_mylib.py::test_mylib_demo_typechecks[optn.lam] PASSED
MySolution/tests/test_mylib.py::test_mylib_demo_typechecks[strm.lam] PASSED
MySolution/tests/test_mylib.py::test_mylib_demo_typechecks[a1sz.lam] PASSED
MySolution/tests/test_mylib.py::test_mylib_demo_interprets[list.lam] PASSED
MySolution/tests/test_mylib.py::test_mylib_demo_interprets[optn.lam] PASSED
MySolution/tests/test_mylib.py::test_mylib_demo_interprets[strm.lam] PASSED
MySolution/tests/test_mylib.py::test_mylib_demo_interprets[a1sz.lam] PASSED
MySolution/tests/test_mylib.py::test_mylib_demo_compiles_to_both_targets[list.lam] PASSED
MySolution/tests/test_mylib.py::test_mylib_demo_compiles_to_both_targets[optn.lam] PASSED
MySolution/tests/test_mylib.py::test_mylib_demo_compiles_to_both_targets[strm.lam] PASSED
MySolution/tests/test_mylib.py::test_mylib_demo_compiles_to_both_targets[a1sz.lam] PASSED
MySolution/tests/test_params.py::test_source_wrong_type_or_blank_is_invalid_params[int-lambda.typecheck] PASSED
MySolution/tests/test_params.py::test_source_wrong_type_or_blank_is_invalid_params[int-lambda.interpret] PASSED
MySolution/tests/test_params.py::test_source_wrong_type_or_blank_is_invalid_params[int-lambda.compile] PASSED
MySolution/tests/test_params.py::test_source_wrong_type_or_blank_is_invalid_params[null-lambda.typecheck] PASSED
MySolution/tests/test_params.py::test_source_wrong_type_or_blank_is_invalid_params[null-lambda.interpret] PASSED
MySolution/tests/test_params.py::test_source_wrong_type_or_blank_is_invalid_params[null-lambda.compile] PASSED
MySolution/tests/test_params.py::test_source_wrong_type_or_blank_is_invalid_params[bool-lambda.typecheck] PASSED
MySolution/tests/test_params.py::test_source_wrong_type_or_blank_is_invalid_params[bool-lambda.interpret] PASSED
MySolution/tests/test_params.py::test_source_wrong_type_or_blank_is_invalid_params[bool-lambda.compile] PASSED
MySolution/tests/test_params.py::test_source_wrong_type_or_blank_is_invalid_params[array-lambda.typecheck] PASSED
MySolution/tests/test_params.py::test_source_wrong_type_or_blank_is_invalid_params[array-lambda.interpret] PASSED
MySolution/tests/test_params.py::test_source_wrong_type_or_blank_is_invalid_params[array-lambda.compile] PASSED
MySolution/tests/test_params.py::test_source_wrong_type_or_blank_is_invalid_params[object-lambda.typecheck] PASSED
MySolution/tests/test_params.py::test_source_wrong_type_or_blank_is_invalid_params[object-lambda.interpret] PASSED
MySolution/tests/test_params.py::test_source_wrong_type_or_blank_is_invalid_params[object-lambda.compile] PASSED
MySolution/tests/test_params.py::test_source_wrong_type_or_blank_is_invalid_params[empty-lambda.typecheck] PASSED
MySolution/tests/test_params.py::test_source_wrong_type_or_blank_is_invalid_params[empty-lambda.interpret] PASSED
MySolution/tests/test_params.py::test_source_wrong_type_or_blank_is_invalid_params[empty-lambda.compile] PASSED
MySolution/tests/test_params.py::test_source_wrong_type_or_blank_is_invalid_params[spaces-lambda.typecheck] PASSED
MySolution/tests/test_params.py::test_source_wrong_type_or_blank_is_invalid_params[spaces-lambda.interpret] PASSED
MySolution/tests/test_params.py::test_source_wrong_type_or_blank_is_invalid_params[spaces-lambda.compile] PASSED
MySolution/tests/test_params.py::test_source_wrong_type_or_blank_is_invalid_params[whitespace-lambda.typecheck] PASSED
MySolution/tests/test_params.py::test_source_wrong_type_or_blank_is_invalid_params[whitespace-lambda.interpret] PASSED
MySolution/tests/test_params.py::test_source_wrong_type_or_blank_is_invalid_params[whitespace-lambda.compile] PASSED
MySolution/tests/test_params.py::test_missing_source_is_invalid_params[lambda.typecheck] PASSED
MySolution/tests/test_params.py::test_missing_source_is_invalid_params[lambda.interpret] PASSED
MySolution/tests/test_params.py::test_missing_source_is_invalid_params[lambda.compile] PASSED
MySolution/tests/test_params.py::test_unknown_param_key_is_rejected PASSED
MySolution/tests/test_params.py::test_typecheck_rejects_target_param PASSED
MySolution/tests/test_params.py::test_bad_target_is_invalid_params[ruby] PASSED
MySolution/tests/test_params.py::test_bad_target_is_invalid_params[Python] PASSED
MySolution/tests/test_params.py::test_bad_target_is_invalid_params[] PASSED
MySolution/tests/test_params.py::test_bad_target_is_invalid_params[None] PASSED
MySolution/tests/test_params.py::test_bad_target_is_invalid_params[3] PASSED
MySolution/tests/test_params.py::test_bad_target_is_invalid_params[target5] PASSED
MySolution/tests/test_params.py::test_missing_target_is_invalid_params PASSED
MySolution/tests/test_params.py::test_oversized_source_counts_code_points_not_bytes PASSED
MySolution/tests/test_protocol.py::test_malformed_json_is_parse_error_with_null_id PASSED
MySolution/tests/test_protocol.py::test_non_utf8_body_is_parse_error PASSED
MySolution/tests/test_protocol.py::test_deeply_nested_json_is_parse_error_not_500 PASSED
MySolution/tests/test_protocol.py::test_nan_constant_is_parse_error PASSED
MySolution/tests/test_protocol.py::test_invalid_envelope_gets_invalid_request_with_null_id[wrong_version_with_id] PASSED
MySolution/tests/test_protocol.py::test_invalid_envelope_gets_invalid_request_with_null_id[missing_jsonrpc] PASSED
MySolution/tests/test_protocol.py::test_invalid_envelope_gets_invalid_request_with_null_id[method_not_string] PASSED
MySolution/tests/test_protocol.py::test_invalid_envelope_gets_invalid_request_with_null_id[method_missing] PASSED
MySolution/tests/test_protocol.py::test_invalid_envelope_gets_invalid_request_with_null_id[boolean_id] PASSED
MySolution/tests/test_protocol.py::test_invalid_envelope_gets_invalid_request_with_null_id[array_id] PASSED
MySolution/tests/test_protocol.py::test_invalid_envelope_gets_invalid_request_with_null_id[params_string] PASSED
MySolution/tests/test_protocol.py::test_invalid_envelope_gets_invalid_request_with_null_id[params_number] PASSED
MySolution/tests/test_protocol.py::test_invalid_envelope_gets_invalid_request_with_null_id[extra_member] PASSED
MySolution/tests/test_protocol.py::test_invalid_envelope_gets_invalid_request_with_null_id[string_request] PASSED
MySolution/tests/test_protocol.py::test_invalid_envelope_gets_invalid_request_with_null_id[number_request] PASSED
MySolution/tests/test_protocol.py::test_invalid_envelope_gets_invalid_request_with_null_id[null_request] PASSED
MySolution/tests/test_protocol.py::test_unknown_method_preserves_id_and_reports_method PASSED
MySolution/tests/test_protocol.py::test_unknown_method_name_is_truncated_to_128_chars PASSED
MySolution/tests/test_protocol.py::test_method_names_are_case_sensitive PASSED
MySolution/tests/test_protocol.py::test_array_params_rejected_with_invalid_params_and_id_kept PASSED
MySolution/tests/test_protocol.py::test_absent_params_on_interpret_is_missing_source PASSED
MySolution/tests/test_protocol.py::test_null_params_is_invalid_request PASSED
MySolution/tests/test_protocol.py::test_validation_precedes_method_lookup_for_bad_envelope PASSED
MySolution/tests/test_runtime_and_limits.py::test_division_by_zero_is_runtime_error PASSED
MySolution/tests/test_runtime_and_limits.py::test_head_of_empty_list_is_invalid_operation PASSED
MySolution/tests/test_runtime_and_limits.py::test_unbounded_recursion_is_recursion_depth_exceeded_not_timeout PASSED
MySolution/tests/test_runtime_and_limits.py::test_slow_program_times_out_with_configured_seconds PASSED
MySolution/tests/test_runtime_and_limits.py::test_timeout_leaves_server_usable PASSED
MySolution/tests/test_runtime_and_limits.py::test_oversized_source_rejected_with_limit_and_actual PASSED
MySolution/tests/test_runtime_and_limits.py::test_deeply_nested_source_is_invalid_params_not_internal[lambda.typecheck] PASSED
MySolution/tests/test_runtime_and_limits.py::test_deeply_nested_source_is_invalid_params_not_internal[lambda.interpret] PASSED
MySolution/tests/test_runtime_and_limits.py::test_deeply_nested_source_is_invalid_params_not_internal[lambda.compile] PASSED
MySolution/tests/test_runtime_and_limits.py::test_long_operator_chain_is_nesting_error PASSED
MySolution/tests/test_transport.py::test_rpc_success_is_http_200_application_json PASSED
MySolution/tests/test_transport.py::test_content_type_with_charset_is_accepted PASSED
MySolution/tests/test_transport.py::test_wrong_content_type_is_415_plain_text[text/plain] PASSED
MySolution/tests/test_transport.py::test_wrong_content_type_is_415_plain_text[application/x-www-form-urlencoded] PASSED
MySolution/tests/test_transport.py::test_wrong_content_type_is_415_plain_text[application/jsonp] PASSED
MySolution/tests/test_transport.py::test_missing_content_type_is_415 PASSED
MySolution/tests/test_transport.py::test_other_methods_are_405_with_allow_post[get] PASSED
MySolution/tests/test_transport.py::test_other_methods_are_405_with_allow_post[put] PASSED
MySolution/tests/test_transport.py::test_other_methods_are_405_with_allow_post[delete] PASSED
MySolution/tests/test_transport.py::test_other_methods_are_405_with_allow_post[patch] PASSED
MySolution/tests/test_transport.py::test_body_over_1_mib_is_413_plain_text PASSED
MySolution/tests/test_transport.py::test_body_of_exactly_1_mib_reaches_the_dispatcher PASSED
MySolution/tests/test_transport.py::test_other_paths_are_404_plain_text[/] PASSED
MySolution/tests/test_transport.py::test_other_paths_are_404_plain_text[/rpc/] PASSED
MySolution/tests/test_transport.py::test_other_paths_are_404_plain_text[/health] PASSED
MySolution/tests/test_transport.py::test_other_paths_are_404_plain_text[/rpc/extra] PASSED
MySolution/tests/test_transport.py::test_other_paths_are_404_plain_text[/lambda/typecheck] PASSED
MySolution/tests/test_transport.py::test_notification_is_204_with_empty_body PASSED
MySolution/tests/test_typecheck.py::test_typecheck_valid_program_returns_formatted_type[arithmetic] PASSED
MySolution/tests/test_typecheck.py::test_typecheck_valid_program_returns_formatted_type[factorial_function] PASSED
MySolution/tests/test_typecheck.py::test_typecheck_valid_program_returns_formatted_type[tuple] PASSED
MySolution/tests/test_typecheck.py::test_typecheck_valid_program_returns_formatted_type[list] PASSED
MySolution/tests/test_typecheck.py::test_typecheck_accepts_source_of_exactly_max_size PASSED
MySolution/tests/test_worker_failures.py::test_worker_setup_failure_logs_traceback_but_hides_it PASSED

============================= 159 passed in 8.23s ==============================
```

### Instructor suite (unittest, against the running server)

The server was started with `MySolution/.venv/bin/python MySolution/server.py`
from `assigns/07/`. Verbatim:

```
test_batch_matches_by_id_and_omits_notification (test_rpc_api.JsonRpcContractTests.test_batch_matches_by_id_and_omits_notification) ... ok
test_compile_python_and_javascript (test_rpc_api.JsonRpcContractTests.test_compile_python_and_javascript) ... ok
test_health (test_rpc_api.JsonRpcContractTests.test_health) ... ok
test_interpret_arithmetic (test_rpc_api.JsonRpcContractTests.test_interpret_arithmetic) ... ok
test_interpret_function_formats_closure (test_rpc_api.JsonRpcContractTests.test_interpret_function_formats_closure) ... ok
test_interpret_list (test_rpc_api.JsonRpcContractTests.test_interpret_list) ... ok
test_interpret_tuple (test_rpc_api.JsonRpcContractTests.test_interpret_tuple) ... ok
test_invalid_params_and_unknown_method (test_rpc_api.JsonRpcContractTests.test_invalid_params_and_unknown_method) ... ok
test_invalid_request_and_empty_batch (test_rpc_api.JsonRpcContractTests.test_invalid_request_and_empty_batch) ... ok
test_language_syntax_and_type_errors_are_distinct (test_rpc_api.JsonRpcContractTests.test_language_syntax_and_type_errors_are_distinct) ... ok
test_malformed_batch_member_gets_null_id_error (test_rpc_api.JsonRpcContractTests.test_malformed_batch_member_gets_null_id_error) ... ok
test_malformed_json_returns_parse_error (test_rpc_api.JsonRpcContractTests.test_malformed_json_returns_parse_error) ... ok
test_notification_has_no_response (test_rpc_api.JsonRpcContractTests.test_notification_has_no_response) ... ok
test_notification_only_batch_has_no_response (test_rpc_api.JsonRpcContractTests.test_notification_only_batch_has_no_response) ... ok
test_typecheck_arithmetic (test_rpc_api.JsonRpcContractTests.test_typecheck_arithmetic) ... ok

----------------------------------------------------------------------
Ran 15 tests in 0.928s

OK
```
