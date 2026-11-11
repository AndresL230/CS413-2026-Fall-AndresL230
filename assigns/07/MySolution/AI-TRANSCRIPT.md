# AI Transcript — Assign07

AI was used throughout this assignment. This file records which tools were
used, for what, what they got wrong, and how I checked their output.

## Tools

| Tool | Used for |
| --- | --- |
| Claude (chat) | Reading `LAMBDA3/lambda3.py` with me, probing it, and drafting the prompts I gave to Claude Code |
| Claude Code (Opus 5.5) | Writing `RPC.md`, running LAMBDA3 to produce every example, coordinating subagents, re-running checks, git |
| Claude Code subagent (Sonnet) | Writing `schema/jsonrpc.schema.json` and a validation script for it |

## Part 1 — Understanding LAMBDA3 and writing the contract

### Exploring LAMBDA3 (Claude chat)

I used Claude in a chat to read `lambda3.py` and to run small probes
against it before designing anything:

- Successful programs: factorial, a tuple, a list, and function values
  (formatted as `<lam>` / `<fix>`).
- Error behavior: a syntax error (`LambdaSyntaxError`, with line, column,
  and line text), a type error (`TypeCheckError`, message only), `1 / 0`,
  and `list_head` of an empty list.
- How deep recursion can go before Python's limit is hit, and how long
  `fib(n)` takes, to choose an interpretation deadline.

From this I made the design decisions myself: Flask, a 32,768-character
source cap, a 1 MiB body cap, a 5 s deadline in a killable worker process,
error codes `-32010`..`-32013`, the error `data` shapes, and the HTTP status
rules. Claude in the chat then helped me write those decisions into prompts
for Claude Code.

### Writing the contract (Claude Code)

Main prompt (summarized): *"Only write `RPC.md` and the JSON Schema, no
server code yet. RPC.md needs everything in task 1. For the example
requests/responses, actually run lambda3 to get the outputs, don't type them
from memory. Include a runtime error and a timeout example."*

- Claude Code ran LAMBDA3 on every example source and copied the real
  outputs (types, values, error messages, line/column) into `RPC.md` §7.
  The compile examples are the only shortened ones, and that is marked in
  the document.
- A Sonnet subagent wrote `schema/jsonrpc.schema.json`. It also wrote a
  script that validates every JSON example in `RPC.md` against the schema.
  Valid examples must pass; invalid requests and bad params must fail. Claude
  Code re-ran that script itself instead of trusting the subagent's report:
  0 failures.
- The subagent pointed out one inconsistency in `RPC.md`: the request table
  said `params` must be an object, but the validation steps accept an array
  and reject it later with `-32602`. I fixed the table wording.

### Corrections found by running the code

Each of these came from actually running LAMBDA3. Each one changed my
notes or the contract.

1. **`basics0.py` location.** My notes said it lived in `LAMBDA3/mylib/`. It
   is in `LAMBDA3/`, next to `lambda3.py`. Only `LAMBDA3/` needs to be on
   `sys.path`.
2. **The parser and type-checker are recursive too.** At Python's default
   recursion limit they raise `RecursionError` at about 300 nested
   parentheses, or a chain of about 1,000 `+` (around 4 KB, far under the
   source cap). That happens in the server process, not the worker. The
   contract now maps it to `-32602` "source nesting too deep" instead of an
   internal error.
3. **Python's integer-digit limit.** Python refuses to convert integers with
   more than 4,300 digits to or from strings. `fact(5000)` evaluated fine
   and then crashed in `d0val_format`, and a 5,000-digit literal crashed the
   parser. The contract now calls `sys.set_int_max_str_digits(0)` in both
   processes, and formatting happens inside the worker so it counts against
   the deadline.
4. **Recursion limit vs deadline.** A worker recursion limit of 1,000,000
   made infinite recursion run for 15.6 s, so it would show up as a timeout.
   100,000 (with a 512 MiB thread stack) makes it fail with `RecursionError`
   in about 1.3 s, so it is reported as a runtime error. 100,000 was chosen.
5. **Small fixes in the examples.** The interpreter's `IndexError` message is
   `a1sz_getat: index out of range`, not the compiled runtime's message. My
   first `a1sz` library demo expression was badly typed. All four `mylib`
   files were then checked with the `let <file> in <expr> end` wrapping.

### How I reviewed it

- Claude Code checked `RPC.md` against the Task 1 checklist in
  `Assign07.md`.
- I reviewed the error-code table and the batch examples it showed me.
- The schema was accepted only after Claude Code re-ran the checker
  itself.

## Part 2 — Server, tests, and docs

### Prompt

Main prompt (summarized):

> Mylib: no auto loading and no new method. Tests and demos send a library
> file as `let <file contents> in <expr> end`; check every file works that
> way. Make sure `RecursionError` in the parent maps to the `-32602` nesting
> error, never a 500. Then build the server in separate files (transport,
> envelope/dispatcher, LAMBDA3 adapter, interpret worker), with no
> exec/eval, unexpected errors logged server-side, and pinned requirements.
> Write pytest tests for all 10 items of task 3. Successful paths must call
> real LAMBDA3; doubles are only for injected failures and dispatch
> boundaries. The timeout test uses a lowered deadline and real `fib(30)`.
> Write README and TESTING, run both suites, and fix anything failing.

I had also asked Claude Code to use Sonnet for writing code.

### Who did what

- **Claude Code (Opus 5.5)**
  - Checked that all four `mylib` files type-check and evaluate when wrapped
    in `let … in … end`. Each is 2.3–5.6 K characters, under the cap, and
    parses at the server's default recursion limit. It added a section about
    this to `RPC.md`.
  - Added `.gitignore`, then committed and pushed `RPC.md` and the schema.
- **Sonnet subagent #1**
  - Wrote all of `lambda_rpc/`, `server.py`, `requirements.txt`, and the
    pytest suite from a detailed brief that pointed at `RPC.md` as the
    contract.
  - Reported 158 passing tests and 15/15 instructor tests.
- **Claude Code review.** It read every server module itself and found one
  real defect: unexpected **worker** failures were turned into `-32603`
  without being logged. The dispatcher only logs exceptions that are not
  `RpcError`, and the worker returned a bare `("internal",)` with the
  traceback thrown away. The assignment requires server-side logging.
- **Sonnet subagent #2**
  - Fixed `worker.py`: the child now sends the traceback back to the parent,
    the parent logs it, and a child that dies without a result is logged
    with its exit code.
  - Added `tests/test_worker_failures.py`. It uses the real worker,
    configured so that `threading.stack_size(1)` fails inside the child, and
    asserts the client gets a bare `-32603` while the traceback shows up in
    the server log.
- **Claude Code verification.** It did not rely on the subagents' reports.
  It re-ran everything itself:
  - pytest: 159 passed;
  - started the real server and ran the instructor suite: 15/15 OK;
  - ran every curl example in `README.md` against the live server and
    pasted the real responses;
  - grepped for `exec`/`eval`/`compile(`: none.

  It wrote `README.md` and `TESTING.md` itself. The test outputs in
  `TESTING.md` were pasted from the saved run logs, not retyped. When the
  first draft of the requirement mapping had wrong per-file test counts,
  they were corrected from the actual output.

### Things considered and left as they are

- **Huge integer ids.** With `sys.set_int_max_str_digits(0)` in the server
  process, a 1 MiB all-digit JSON `id` is accepted. Measured: about 0.6 s to
  parse and 0.4 s to echo. The 1 MiB body cap bounds this, so the contract
  was not changed.
- **Untested path.** The "worker died without sending a result" path is
  logged but has no test of its own. The setup-failure test covers the
  logging route.
