# Testing

Run everything from `assigns/08/`:

```sh
MySolution/.venv/bin/python -m pytest MySolution -v      # solver, laziness, service, HTTP e2e
node --test MySolution/tests/js/                          # browser client: transport + player
```

**Observed results** (Python 3.14.8, pytest 9.2.0, Node 26.12.1, 2026-11-19):

| Suite | Result |
| --- | --- |
| pytest | **146 passed in 34.04 s** |
| node --test | **33 passed (0 failed) in 0.15 s** |

Most of the pytest time goes to the full 8×8 trace: once in-process, via the
shared `trace8` fixture, in about 11 s, and once over a real socket in the
end-to-end test, in about 13 s.

Every solver test runs the LAMBDA3 program in `queens/queens.lam` through
the supplied interpreter. The only test doubles are:

- the fake clock (expiry),
- an exploding stream (internal error),
- the fake `fetch` and fake timers in the client tests.

## Requirement → tests

Test files are under `MySolution/tests/`.

| # | Requirement | Tests | Result |
| --- | --- | --- | --- |
| 1 | Safety checks: same row, both diagonals, safe placement | `test_safety.py`: `test_same_column_adjacent_row_conflicts`, `test_same_column_distant_row_conflicts`, `test_diagonal_up_left_conflicts`, `test_diagonal_up_right_conflicts`, `test_non_adjacent_diagonal_conflicts`, `test_empty_board_is_safe`, `test_safe_placements` (3 cases), `test_conflict_stops_at_first_collision`, `test_safe_walks_whole_board_once`, `test_check_safe_type_is_cps` | pass |
| 2 | CPS success and failure paths, resumption at the next candidate | `test_cps.py`: `test_success_continuation_receives_first_board_and_can_stop`, `test_success_continuation_resumes_search_through_failure_continuation`, `test_failure_continuation_when_every_column_is_rejected`, `test_search_at_full_board_calls_success_with_its_failure_continuation`, `test_dead_end_backtracks_and_resumes_at_next_candidate`, `test_row_exhaustion_backtracks_parent_then_next_parent_column`, `test_resumption_rule_over_full_8x8_trace` | pass |
| 3 | All 8×8 solutions, count 92, deterministic order, no duplicates | `test_solutions.py`: `test_8x8_has_exactly_92_solutions`, `test_8x8_solutions_are_distinct_valid_8_tuples`, `test_8x8_solutions_in_depth_first_lexicographic_order`, `test_small_sizes_match_brute_force` (4×4 to 7×7), `test_trace_is_deterministic`, `test_open_rejects_sizes_outside_4_to_10` | pass |
| 4 | Each event kind with correct board snapshot and coordinates | `test_events.py`: `test_8x8_opening_events`, `test_every_kind_occurs_with_expected_totals`, `test_done_exactly_once_and_last`, `test_full_trace_matches_direct_style_model`, `test_board_snapshots_and_coordinates_replay` | pass |
| 5 | Laziness: open does no search, one force leaves its tail unforced, a bounded prefix leaves later work unforced | `test_laziness.py`: `test_open_performs_no_search`, `test_forcing_one_cell_does_not_force_its_tail`, `test_bounded_prefix_leaves_later_work_unforced`, `test_first_10x10_solution_needs_a_small_fraction_of_the_trace`, `test_forced_cells_are_memoized`, `test_each_cell_does_bounded_work`, `test_full_8x8_trace_at_default_recursion_limit`; service level: `test_rpc_lifecycle.py::test_open_through_service_runs_no_search`, `test_table_holds_only_the_next_unforced_tail` | pass |
| 6 | Exhaustion, repeated `next`, close, unknown id, cleanup, expiry | `test_rpc_lifecycle.py`: `test_exhaustion_then_next_again_stays_done`, `test_done_can_be_the_only_event_in_a_response`, `test_close_live_stream_then_it_is_unknown`, `test_close_exhausted_marker`, `test_close_twice_is_unknown`, `test_unknown_id_on_next_and_close`, `test_expiry_after_ttl_of_inactivity`, `test_expired_entries_are_swept_on_access`, `test_cap_of_256_streams`, `test_cap_counts_exhausted_markers_and_frees_on_expiry`, `test_invalid_open_allocates_nothing`, `test_solver_failure_is_internal_error_and_discards_stream`, `test_open_returns_fresh_uuid_ids` | pass |
| 7 | JSON-RPC ids, malformed envelopes, unknown methods, invalid params, notifications, application errors | `test_rpc_protocol.py`: `test_request_ids_preserved_with_type` (7 id kinds), `test_body_not_json_is_parse_error`, `test_malformed_envelopes_are_invalid_request` (17 cases), `test_unknown_methods`, `test_open_bad_size` (12 cases), `test_open_size_float_spelled_in_json`, `test_next_bad_limit` (9 cases), `test_bad_stream_id_type`, `test_unknown_parameter_keys`, `test_missing_required_parameters`, `test_positional_params_rejected`, `test_well_formed_unknown_id_is_application_error_not_param_error`, `test_notifications_get_204_and_empty_body`, `test_notification_still_runs_the_method`, `test_notification_next_advances_stream`, `test_health`, `test_non_json_content_type_is_415`, `test_get_rpc_is_405`, `test_oversized_body_is_413`, `test_index_page_served`; batches in `test_rpc_limits_batch.py`: `test_batch_hits_one_stream_in_order`, `test_batch_mixes_results_errors_and_notifications`, `test_batch_of_only_notifications_is_204` | pass |
| 8 | `queens.next` respects limits 1 and 32, never more than requested | `test_rpc_limits_batch.py`: `test_limit_1_returns_exactly_one_event`, `test_limit_32_returns_exactly_32_while_available`, `test_limit_defaults_to_1`, `test_limits_never_exceeded_through_exhaustion`, `test_concurrent_next_calls_partition_the_trace` | pass |
| 9 | HTTP flow from open through all 92 solutions to completion | `test_rpc_e2e.py::test_http_8x8_open_through_92_solutions_to_done`: real socket, limit 32, 1,050 `next` calls, 33,589 events identical to the in-process trace, `next` after done, then close | pass (13.4 s) |
| 10 | Browser controls: start/reset, step, play/pause, next solution, RPC failure handling | Automated, `tests/js/player.test.js` (25 tests) and `tests/js/rpc.test.js` (8 tests); see the list below. Manual checklist further down. | pass |

### Client tests (node --test)

All of these run against the fake server and fake timers in
`tests/js/fakes.js`, which play back a JS copy of the same search.

`player.test.js` covers:

- **Board and log helpers:**
  - `attackerOf finds same-column and both diagonals, nearest row first`
  - `applyEvent is pure and tracks board, counts, attacker, and done`
  - `boardView gives each event kind a distinct look`
  - `describe names the attacker for rejects`
  - `the event log is capped`
- **Done versus solution:** `controls and status distinguish done from a solution`
- **Incremental fetching:**
  - `start opens a stream without fetching any events`
  - `step applies events in order and only fetches small batches when low`
  - `no refill while the buffer is above the low-water mark`
- **Play/pause:**
  - `play advances on the timer, pause stops it, speed sets the interval`
  - `playing to the end reaches done, stops the timer, and closes the stream`
- **Next solution:**
  - `next solution fast-forwards in batches of 32 and draws once`
  - `next solution twice gives the second solution`
  - `next solution that runs into done shows done, not a solution`
  - `next solution pauses playback first`
- **Reset, restart and leaving the page:**
  - `reset closes the stream and clears the board`
  - `reset during a fast-forward stops it`
  - `restart after done opens a fresh stream and resets the counters`
  - `start while a stream is open closes the old one`
  - `closeOnUnload closes the open stream with a keepalive notification`
- **Failures:**
  - `network failure during step shows an error and stops playback`
  - `expired stream (-32020) shows a restart hint`
  - `failure on open is shown`
  - `failure during a fast-forward is shown`
  - `a failed close on reset is reported`

`rpc.test.js` covers:

- `call sends a JSON-RPC 2.0 POST with increasing ids`
- `next returns the event batch`
- `JSON-RPC errors become RpcFailure(kind rpc) with code and data`
- `network failure becomes RpcFailure(kind network)`
- `HTTP error status becomes RpcFailure(kind http)`
- `non-JSON or mismatched responses are protocol failures`
- `next rejects a batch larger than the requested limit`
- `closeOnUnload sends a keepalive notification and never throws`

## Manual checklist for the controls (requirement 10)

Start the server with `MySolution/.venv/bin/python MySolution/server.py`
and open http://127.0.0.1:8000/. The "Observed" column is from a run on
2026-11-19 in Chrome, driven by browser automation: real clicks for
Start, Step, Play, and Next solution; JavaScript-dispatched events for the
size select, speed slider, and repeated clicks. The server log was checked
for the close calls.

| # | Action | Expected | Observed |
| --- | --- | --- | --- |
| 1 | Load the page | 8×8 board, size 8 selected, only Start enabled, status "Choose a board size and press Start." | as expected |
| 2 | Start | status "Ready: 8x8 search opened"; Step/Play/Next/Reset enabled; RPC fetches still 0 | as expected |
| 3 | Step ×4 | try (0,0) dashed blue → place (0,0) → try (1,0) → reject (1,0) red with ✕, attacking queen (0,0) ringed red; log shows "reject row 1, col 0 (attacked by row 0, col 0)"; 1 fetch for 4 events | as expected |
| 4 | Next solution | jumps to `[0, 4, 7, 5, 2, 6, 1, 3]`, board glows gold, status "solution #1 found", solutions = 1, 1,858 events from 59 fetches (32 per fetch) | as expected |
| 5 | Play, speed 40 | Play turns into Pause, Step is disabled, events advance ~36/s; backtracks fade amber | as expected |
| 6 | Pause | the event count stops changing | as expected (2,198 → 2,198 after 0.8 s) |
| 7 | Change size to 4×4 | resets: 4×4 board, counters 0, status back to idle; old stream closed | board, counters, and status as expected; the close itself is covered by `reset closes the stream and clears the board` (the server log does not show which method each 200 was) |
| 8 | Start, Next solution ×3 | solutions [1,3,0,2], [2,0,3,1], then **done**: grey board, dark banner "Search complete: no more solutions. Found 2 in 139 events." with Restart; Step/Play/Next disabled; 5 fetches total | as expected |
| 9 | Restart | banner gone, fresh stream; a Step gives try (0,0), counters restarted | as expected |
| 10 | Stop the server, keep stepping | red banner "Network error: cannot reach the server. Check that server.py is running, then press Start."; status "Stopped by an error."; Step/Play/Next disabled, Start enabled | as expected (after 11 buffered steps) |
| 11 | Restart the server, press Start | error cleared, new search works | as expected |
| 12 | Navigate away from the page | server log shows a `POST /rpc` answered 204 (the keepalive `queens.close` notification) | as expected |
| 13 | Narrow window (phone width) | board above the log, controls wrap, no horizontal scroll | layout uses a single column under 760 px; not checked on a real phone |

Issues found during this manual pass, all fixed before the run above:

- Start relabelled itself "Start over" and grew wider, which shifted Step
  under the cursor. The label is now fixed, and Play/Pause has a minimum
  width.
- The "RPC fetches" counter carried over from the previous search. It is
  now reset on Start and Reset, and a test was added.
- The status read "Ready" after stepping. It now reads "Paused".

## Checking that the tests can fail

Each mutant was run in a scratch copy, not committed:

| Mutant | Caught by |
| --- | --- |
| drop the second diagonal check in `queens.lam` | `test_diagonal_up_right_conflicts` |
| make `queens_emit` call its continuation eagerly | `test_forcing_one_cell_does_not_force_its_tail` (`check` count) |
| remove the bool check from integer params | `test_next_bad_limit[True]` |
| disable the expiry sweep | 3 expiry tests |
| check the stream cap after calling the solver | `test_cap_of_256_streams` (application count) |

## Measured solver numbers

| Size | Events | Solutions | Full-trace time |
| --- | ---: | ---: | ---: |
| 4 | 139 | 2 | 0.03 s |
| 5 | 504 | 10 | 0.12 s |
| 6 | 1,945 | 4 | 0.49 s |
| 7 | 7,760 | 40 | 2.1 s |
| 8 | 33,589 | 92 | 9.7 s |
| 9 | 153,502 | 352 | 50 s |
| 10 | 732,563 | 724 | 261 s |

Sizes 9 and 10 are too slow for the suite; their counts were measured once
and match the known values. The worst case per forced cell is `size + 7`
LAMBDA applications.
