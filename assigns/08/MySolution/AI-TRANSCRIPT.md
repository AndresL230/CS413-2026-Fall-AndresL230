# AI Transcript: Assign08

AI was used throughout this assignment, in one Claude Code session that I
directed in steps. This file lists the tools, the prompts, the decisions I
made, what the AI got wrong along the way, and how the work was checked.

## Tools

| Tool | Used for |
| --- | --- |
| Claude Code (Opus 5.5) | Reading the spec, Assign07, and `lambda3.py`; probing the interpreter; writing DESIGN.md, the LAMBDA3 solver, the Python bridge, the service, the browser client, all tests, and the docs; running tests and mutation checks; git |
| Claude in Chrome (driven by Claude Code) | Running the manual checklist for the browser controls against the real server |

No other AI tools were used. The supplied `LAMBDA3/lambda3.py` was not
modified.

## Prompt 1: orientation

**Prompt (summary):** Get oriented in the repo before writing code. Read
the README, docs, and git log/status, then report what the project is, how
to run it and its tests, and what looks broken. Then propose a plan and
wait for "go".

**What came back:**

- The repo layout and the per-assignment LAMBDA3 copies.
- `make check` in `LAMBDA3/mytest` passes, and `make test` in
  `LAMBDA3/mylib/TEST` fails because the Makefile breaks on the spaces in
  my path. That is not a code bug.
- Assign08's `MySolution/` was empty, and Assign06 had uncommitted docs.
- My template still read `[TASK]`, which it flagged instead of guessing.

**Correction:** I asked whether it had written anything. It checked
instead of answering from memory, and found that `make check` had created
`LAMBDA3/__pycache__/`. It was removed later.

## Prompt 2: research questions before the design

**Prompt (summary):** Read Assign08.md and the Assign07 service fully, plus
`lambda3.py`, `eight_queens_stream.lam`, and `lazy_stream.lam`. Explain:

- how `lazy_make`/`lazy_eval` work and how to force a stream cell from
  Python,
- how to call a LAMBDA closure with an argument,
- whether LAMBDA3 has strings,
- whether `print` works inside a thunk,
- what makes CPS painful.

Then list the ambiguities in the spec. No code yet.

**What came back:** answers checked with a throwaway probe script, not from
memory.

- Laziness is a memoizing `D0Vlazy`. Cells are forced through the
  interpreter's own `lazy_eval`. Closures are applied with `_d0val_apply`.
- There are no strings or sum types, so events are int-coded tuples.
- `print` does work inside a thunk.
- There are no tail calls, and the limit is about 150–300 nested LAMBDA
  calls at recursion limit 1000. But a lazy stream unwinds the stack at
  every cell: a probe consumed 100,000 cells at the default limit.

It also listed 12 open questions.

**My decisions** (these became DESIGN.md):

1. Drop the solver state on `done` and keep a marker until close or expiry.
2. `close` on an unknown or already-closed id returns `-32020`.
3. Treat "same row" as same column, plus both diagonals and a safe case,
   and document why.
4. Keep the spec's continuation signatures; the client works out the
   attacking queen.
5. Prove laziness by counting interpreter applications and checking
   `.evaluated` on real tails. No trace flag in the solver.
6. 10-minute TTL, an injectable clock, a cap of 256, codes
   `-32020`/`-32021`.
7. Serve the static files from Flask at `GET /`.
8. Keep batches, processed sequentially.
9. Copy and trim Assign07 so 08 stands alone.
10. Next solution fast-forwards in batches of 32; add a size selector.
11. `node --test` for the client, plus a manual checklist.
12. Minimal and solid, no extras.

## Prompt 3: DESIGN.md, solver, bridge, solver tests

**Prompt (summary):** Write DESIGN.md, then the solver `.lam`, the Python
bridge, and solver tests for required tests 1–5. Keep the rule that no
continuation chain runs without emitting an event, and add a full 8×8
trace test at the default recursion limit. Report the continuation
signatures, the 8×8 event count, the timing, and the test output, then
commit and push.

**Who did what:**

- Claude wrote `queens/queens.lam`:
  - Pure event constructors and `queens_place`.
  - The CPS `queens_check_safe`.
  - `queens_try_column`, which inlines `search(row + 1)` because LAMBDA3
    has no mutual recursion.
  - `queens_emit`, which suspends the continuation in the tail.
  - `queens_stream`.

  It type-checked on the first try.
- It also wrote the bridge `queens/solver.py`, an independent
  direct-style Python model (`tests/reference.py`) to compare traces
  against, and an application counter that wraps
  `lambda3._d0val_apply`.
- **Mistakes caught by running the tests:**
  - One "safe" test case, `(3, [1, 4, 0, 2])`, was actually a diagonal
    conflict. It was replaced with a case taken from a 5×5 solution.
  - A guessed threshold ("first 10×10 solution within 2,000 events")
    failed at 2,042. Instead of loosening the guess, the number was
    checked against the Python model and asserted exactly.
- **Mutation checks:** removing a diagonal check, and making `emit` eager,
  each made a specific test fail.
- **Results reported:**
  - 33,589 events for 8×8, taking about 9.7 s.
  - Counts for 4–10 match the known solution numbers.
  - The worst case per cell is `size + 7` applications.
  - 47 tests passed.

## Prompt 4: RPC service

**Prompt (summary):** Remove the stray `__pycache__` and make `.gitignore`
cover caches anywhere in 08. Then copy and trim the service from 07. My
specific requirements:

- `next` swaps the stored stream for its tail while holding the lock.
- `true` and `8.0` are rejected for both `size` and `limit`.
- Validate everything before creating a stream, and check the cap before
  touching the solver.
- `-32020` data includes the `stream_id`.
- Expired streams are swept on access, using the fake clock.
- The recursion limit is not changed.

Write tests for required tests 6–9, including the HTTP end-to-end run
with limit 32, and a test that `queens.open` makes zero interpreter calls.
Update the README.

**Who did what:**

- Claude copied `jsonrpc.py` unchanged apart from the logger name. It
  trimmed `errors.py`, wrote the new `streams.py`, `methods.py`, and
  `transport.py`, and wrote 99 service tests. The end-to-end test uses a
  real socket rather than Flask's test client.
- **Flagged instead of guessed:** `queens.open` makes exactly one
  interpreter call, `queens_stream(size)`, which only builds an unforced
  lazy value. The test asserts zero search calls and one call in total.
  I accepted this, because the spec only says opening must not force the
  first event.
- **Mutation checks:** no bool check, no expiry sweep, and checking the
  cap after the solver call. All three were caught.
- **Problems along the way, all harmless:**
  - `pkill -f` matched the calling shell twice.
  - A log `grep` missed werkzeug's ANSI-colored lines.

  These were noticed and handled. Servers were afterwards stopped by a
  saved PID.

## Prompt 5: browser client and docs

**Prompt (summary):** Build the client in plain HTML/CSS/JS:

- size selector (default 8), Start, Step, Play/Pause, Next solution,
  Reset, speed slider, event log, solutions count, status line;
- a distinct look for each event, with the attacker highlighted on
  reject;
- incremental fetching with a small buffer;
- Next solution fast-forwards in batches of 32;
- `done` clearly different from a solution, with a Restart button;
- visible errors;
- close the stream on Reset and on leaving the page;
- transport, a pure player, and a DOM renderer as separate modules, with
  node tests using a fake fetch.

Then TESTING.md, this file, and README updates.

**Who did what:**

- Claude wrote:
  - `static/rpc.js`: transport with an injectable `fetch` and typed
    failures.
  - `static/player.js`: serialized operations, a generation counter so
    `reset` cancels in-flight work, a buffer refilled at 4 left (16 per
    fetch, 32 when fast-forwarding), and pure helpers for the board,
    controls, and status.
  - `static/render.js` and `static/main.js`.
  - 33 node tests against a fake server and fake timers.
- **A weak test, strengthened:** "reset during a fast-forward" originally
  reset before the fast-forward had started. The fake server got a
  request gate, so the test now resets while a `next` is actually in
  flight.
- **Bugs found by actually running the page in Chrome**, each fixed and
  re-checked:
  - The Start button relabelled itself "Start over" and grew wider, which
    shifted Step under the cursor. The first automated clicks hit
    "Start over" four times.
  - The fetch counter carried over between searches (85 for a 139-event
    4×4 run). It is now reset, with a test.
  - The status read "Ready" after stepping. It now reads "Paused".
- **Investigated before claiming it worked:** leaving the page seemed not
  to send `queens.close`. Testing the keepalive fetch and the `pagehide`
  path separately showed both work; the server-log filter had been
  hiding colored 204 lines. TESTING.md was also corrected so it does not
  claim that the close on size-change was seen in the server log. That
  close is covered by a node test instead.

## Prompt 6: cap change, UI cleanup, final check

**Prompt (summary):** Exhausted markers should not count toward the
256-stream cap, only live streams; fix it and add a test. Then clean up the
UI:

- one system-ui font in 2–3 sizes;
- a neutral background with one accent color and muted event colors;
- a spacing grid, with the controls in one row;
- square cells with thin borders and big centered queens;
- a fixed-height monospace log;
- same-size buttons, with disabled ones clearly disabled.

Finally, clone fresh into a temp dir and run the README setup and tests
there, check that nothing is tracked that shouldn't be, commit and push,
and start the server from my repo.

**Who did what:**

- Claude wrote the cap test first, at the real limit (255 live streams
  plus one exhausted marker, then one more open must succeed and the
  257th live one must fail). It confirmed the test failed against the old
  code, then counted only live entries in `StreamTable.open`. It also
  updated README, DESIGN, and TESTING.
  - Trade-off noted in DESIGN: markers are now bounded only by expiry and
    close, not by the cap. They hold no solver state.
- The CSS was rewritten around tokens:
  - font sizes 12/14/20 px (plus queen glyphs sized to the cell);
  - an 8 px spacing scale and one accent color (`#3b5b8c`);
  - muted event colors and 112 px × 36 px buttons;
  - disabled buttons grey and dashed;
  - the board drawn as a 1 px-gap grid.

  The markup was tidied; every element id stayed the same, so the tests
  and `render.js` did not change.
- **Checked in Chrome:** two layout problems were found and fixed:
  - The speed control wrapped onto a second row.
  - "Next solution" wrapped inside a narrower button.

  After the fixes, the controls sit on one row, all five buttons measure
  the same, and the computed font sizes are exactly 20/14/12 px.

## How the work was reviewed

- **Checkpoints:** I approved each step before it started (orientation,
  then research, then design and solver, then service, then client). I
  answered the design questions myself, and I checked the reported
  numbers (92 solutions, 33,589 events, the counts for sizes 4–10)
  against what I expected.
- **Tests that exercise the real thing:**
  - The solver tests run `queens.lam` through the supplied interpreter,
    and the 8×8 trace is compared event by event with an independent
    direct-style model.
  - The HTTP test drives a real server socket through all 1,050 `next`
    calls.
  - Laziness is shown with an application counter and the interpreter's
    own `evaluated` flags, not by looking at `<lazy>` output.
- **Mutation checks** confirmed that the key tests fail when the code is
  wrong (see TESTING.md).
- **The browser client** was run against the live server, following the
  manual checklist in TESTING.md, and three UI bugs were found and fixed
  that way.
- **Commands** in README and TESTING were run from `assigns/08/` exactly
  as written.

Final results: pytest 147 passed, `node --test` 33 passed.
