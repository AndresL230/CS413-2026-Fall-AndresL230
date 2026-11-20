# Assign08 Design: Animated N-Queens with CPS and Lazy Streams

This document was written before the implementation. It fixes the solver's
state, its continuation conventions, the lazy event stream, the JSON-RPC
contract, the stream lifecycle, and the browser client's responsibilities.

## 1. Overview and layout

The N-Queens search is written in LAMBDA3 (`queens/queens.lam`) in
continuation-passing style (CPS). It produces its trace of search events as
a lazy stream (`Strm[Event]`). A Python bridge (`queens/solver.py`) loads and
type-checks the LAMBDA3 program once. It opens a stream for a board size,
forces one cell at a time, and decodes each event into a JSON-ready dict. A
Flask service exposes the stream through JSON-RPC at `POST /rpc`. A static
browser client, served at `GET /`, requests events in small batches and
animates them.

```
MySolution/
  queens/
    queens.lam        LAMBDA3 solver: safety check, board extension, events, CPS search
    lambda3_loader.py import path for ../LAMBDA3 (never cwd-based, no bytecode)
    solver.py         bridge: load + type-check, open, force one cell, decode events
    errors.py         error codes + RpcError            (copied from Assign07, trimmed)
    jsonrpc.py        envelope validation, ids, batches, notifications (Assign07)
    streams.py        stream table: ids, locks, TTL, cap, exhausted markers
    methods.py        method registry + parameter validation
    transport.py      Flask: POST /rpc, GET / and /static/*
  static/             index.html, app.css, rpc.js, player.js, render.js, main.js
  server.py           python3 server.py -> http://127.0.0.1:8000/
  tests/              pytest (solver, stream, service) + node --test (client)
```

The Assign07 modules are copied and trimmed so that this directory stands on
its own. The `lambda.*` methods and the subprocess worker are removed,
because this service must not accept LAMBDA source text, and stream state
consists of live interpreter closures that cannot cross a process boundary.

## 2. Solver state and the partial-board invariant

The search runs one row at a time, from row 0 to row `size - 1`, and tries
columns from left to right (0 to `size - 1`).

**Board.** Inside LAMBDA3, a partial board is a `List[sint]` of queen
columns with the **newest row first**. The board `[c_{k-1}, ..., c_1, c_0]`
means the queen in row `i` is in column `c_i`, and rows `0..k-1` are filled.
The row being searched is always `k = length(board)`, so the row number never
has to be stored in the board. Newest-first order makes the safety check a
plain walk down the list: the head is the row directly above the candidate
(distance 1), the next element is two rows above it, and so on.

On the JSON side, a board is an array in **row order** (`board[i]` is the
column of row `i`). The bridge reverses the list when it decodes an event.

**Invariant.** For every partial board `b` that the search holds:

1. `0 <= c < size` for each element `c` of `b`, and `length(b) <= size`.
2. No two queens in `b` attack each other. Each row holds exactly one queen
   by construction, and no two queens share a column or a diagonal: for rows
   `i != j`, `c_i != c_j` and `|c_i - c_j| != |i - j|`.
3. `b` grows only through `queens_place(column, b)`, which is called only
   after `queens_check_safe` has called its `on_safe` continuation for
   `column` against `b`.

A board of length `size` is therefore a complete solution. Because each
column of each row is tried exactly once along each path, and paths are
distinguished by their first differing row, no solution is produced twice.

**Same-row checks.** One column per row means two queens can never share a
row, so a same-row conflict cannot be represented. The spec's "same row"
safety test is applied here to the axis that can actually conflict:
**same column**, plus both diagonals, plus a safe placement. (The reference
`eight_queens_stream.lam` searches by column, so its "same row" check is
this design's same-column check.)

## 3. Events inside LAMBDA3

LAMBDA3 has no strings, records, or sum types, and every element of a
stream must have the same type. An event is therefore a 4-tuple:

```
Event = (sint, sint, sint, List[sint])      # (kind, column, row, board)
```

| kind | event | column, row | board (newest first) |
| ---: | --- | --- | --- |
| 0 | `try` | candidate | current partial board (without the candidate) |
| 1 | `place` | candidate | updated board (with the candidate) |
| 2 | `reject` | candidate | current partial board |
| 3 | `backtrack` | queen being removed | restored board (without that queen) |
| 4 | `solution` | `-1, -1` (unused) | complete board |
| 5 | `done` | `-1, -1` (unused) | `[]` (unused) |

Events are built by pure constructor functions (`queens_ev_try`,
`queens_ev_place`, `queens_ev_reject`, `queens_ev_backtrack`,
`queens_ev_solution`, `queens_ev_done`). The search itself never builds a
tuple directly.

## 4. CPS conventions

Writing `S` for `Strm[Event]` (that is, `Lazy[Stcn[Event]]`):

| Continuation | Type | Role |
| --- | --- | --- |
| `on_solution` (success) | `(List[sint], unit -> S) -> S` | receives a complete board and the failure continuation that resumes search after it |
| `on_exhausted` (failure) | `unit -> S` | the current branch has no more candidates; resume the enclosing search point |
| `on_safe` | `unit -> S` | the candidate passed every check |
| `on_conflict` | `unit -> S` | the candidate collides with an earlier queen |

Every function in the search returns `S`, which is the CPS answer type.
None of them returns a board or a Boolean to direct-style code. Each
function hands control to its next step in tail position: it either calls a
continuation, makes a recursive call, or calls `queens_emit`.

Functions (LAMBDA3 has no mutual recursion, so multiple arguments are
passed as one tuple):

```
queens_check_safe : (column, distance, board, on_safe, on_conflict) -> S
queens_try_column : (size, row, column, board, on_solution, on_exhausted) -> S
queens_search     : (size, row, board, on_solution, on_exhausted) -> S
queens_emit       : (Event, unit -> S) -> S
queens_stream     : sint -> S            # the entry point the bridge calls
```

Pseudocode, which matches the LAMBDA3 code one-to-one:

```text
check_safe(column, d, board, on_safe, on_conflict):
  if board is empty: on_safe()
  else if head(board) == column            : on_conflict()   # same column
  else if head(board) == column - d        : on_conflict()   # diagonal, up-left
  else if head(board) == column + d        : on_conflict()   # diagonal, up-right
  else check_safe(column, d + 1, tail(board), on_safe, on_conflict)

try_column(size, row, column, board, on_solution, on_exhausted):
  next_candidate = λ(). try_column(size, row, column + 1, board, on_solution, on_exhausted)
  if column == size: on_exhausted()
  else emit(try(column, row, board), λ().
         check_safe(column, 1, board,
           λ(). let next_board = place(column, board)
                    resume = λ(). emit(backtrack(column, row, board), next_candidate)
                emit(place(column, row, next_board), λ().
                  search(size, row + 1, next_board, on_solution, resume)),   # inlined, see below
           λ(). emit(reject(column, row, board), next_candidate)))

search(size, row, board, on_solution, on_exhausted):
  if row == size: on_solution(board, on_exhausted)
  else try_column(size, row, 0, board, on_solution, on_exhausted)

on_solution(board, resume) = emit(solution(board), resume)
root_exhausted()           = emit(done, λ(). empty_stream)
stream(size)               = lazy(λ(). force(search(size, 0, [], on_solution, root_exhausted)))
```

**Search order.** `next_candidate` closes over the current row, column,
board, and the *enclosing* continuations. That closure is the encoding of
"try the next column in this row, and when this row runs out, go back to
whoever called it." `resume`, the failure continuation passed into the
child row, first records the `backtrack` of the queen at `(column, row)` and
then runs `next_candidate`. At the root, `on_exhausted` is
`root_exhausted`, so after the last column of row 0 the stream emits `done`
exactly once. The result is a depth-first, left-to-right traversal.
Solutions appear in ascending lexicographic order of their row-order boards.

**Mutual recursion.** In LAMBDA3, `let` declarations only see earlier
declarations, so `try_column` cannot call a separately declared `search`.
`try_column` therefore inlines `search(row + 1, ...)` as
`if row + 1 == size then on_solution(next_board, resume) else try_column(size, row + 1, 0, next_board, on_solution, resume)`.
`queens_search` is declared after it and is used for the root call (and
directly by tests).

**Reject data.** Following the spec, the conflict continuation has type
`unit -> S` and does not report which queen it collided with. The browser
works out the attacking queen from the `reject` event's board snapshot so
it can highlight it.

## 5. From CPS to a lazy stream: what forcing does

```
queens_emit(event, k) =
  lazy(λ(). stcn_cons(event, lazy(λ(). force(k()))))
```

`emit` returns a stream whose head cell is already known. Its tail is a
suspension that calls the continuation `k` only when the consumer forces
the tail. So:

- **Opening** (`queens_stream(size)`) builds a single unforced lazy. No
  safety check, placement, or event is computed.
- **Forcing the first cell** runs `search(size, 0, [], ...)` far enough to
  reach the first `emit`, which yields `try(0, 0, [])` and an unforced tail.
- **Forcing any later tail** runs exactly one continuation step: at most one
  `check_safe` walk (no more than `size` calls), one placement, and the
  continuations up to the next `emit`. Then it stops and returns the next cell.
  Nothing past that event is computed.
- `lazy_eval` memoizes, so forcing the same cell twice does no extra work.

**Rule: no continuation chain runs without emitting.** Every path out of
every continuation reaches `queens_emit` after a bounded number of calls
(the `check_safe` walk is the only loop, and it is bounded by the board
length). Checking each path:

- `try` → `check_safe` → `place` or `reject`.
- `place` → `search(row + 1)`, which is either `solution` or a `try` in the
  next row.
- `reject` → the next column's `try`, or `on_exhausted`.
- `on_exhausted` → `backtrack` or `done`.
- `solution` → `resume`, which is `backtrack`.

LAMBDA3's interpreter is a recursive Python tree-walker with no tail-call
optimization, and each LAMBDA call costs several Python frames. The rule is
what keeps the Python stack bounded: each force returns to the consumer's
loop, and that loop, not the call stack, drives the search. Tests verify
this by consuming the entire 8×8 trace at Python's default recursion limit
of 1000, and by bounding the number of LAMBDA function applications per
forced cell.

## 6. Python bridge (`queens/solver.py`)

- `declarations()` parses `queens.lam` with `d0cls_parse` and type-checks
  it with `d0cls_typecheck`. It also asserts that `queens_stream` has type
  `sint -> Lazy[Stcn[(sint, sint, sint, List[sint])]]`. The declarations
  are then evaluated once and the `queens_stream` closure is cached. Both
  steps are cached and run on first use (the service will call them at app
  start), so a broken `.lam` fails fast.
- `open_stream(size)` validates `4 <= size <= 10` and applies the closure to
  `D0Vint(size)`, using the interpreter's own function application. It
  returns an `EventStream` holding the unforced lazy.
- `EventStream.next()` forces the current lazy through the interpreter's own
  `lazy_eval` (by evaluating `lazy_eval(s)` with `s` bound to the lazy). It
  decodes the head into a dict, replaces the current lazy with the tail, and
  returns the dict. It returns `None` once the stream is empty. It never
  forces past the cell it returns.
- `decode_event(value)` turns the LAMBDA tuple into JSON-ready data (§7),
  reversing the board into row order. No interpreter object is ever
  returned to callers.
- `evaluate(body_source)` (used by tests) type-checks and evaluates a
  LAMBDA expression with the solver's declarations in scope. This lets
  tests call `queens_check_safe` and `queens_try_column` with their own
  continuations.

The bridge knows nothing about HTTP or JSON-RPC.

## 7. Event schema (JSON)

```json
{"event": "try",       "column": 2, "row": 1, "board": [0]}
{"event": "place",     "column": 2, "row": 1, "board": [0, 2]}
{"event": "reject",    "column": 0, "row": 1, "board": [0]}
{"event": "backtrack", "column": 2, "row": 1, "board": [0]}
{"event": "solution",  "board": [0, 4, 7, 5, 2, 6, 1, 3]}
{"event": "done"}
```

`row` and `column` are zero-based. `board` is in row order. In `try` and
`reject`, `board` is the board before the candidate (so `row ==
board.length`). In `place`, it already includes the candidate. In
`backtrack`, it is the board with the removed queen at `(column, row)`
taken off. `done` carries no other fields and is always the final event,
exactly once.

## 8. JSON-RPC methods

All requests are `POST /rpc` with `Content-Type: application/json`, using
JSON-RPC 2.0. A successful call and a JSON-RPC error both return HTTP 200.
A valid notification (no `id`) returns HTTP 204 with an empty body. Request
ids (string, number, or null) are echoed with their type preserved. Unknown
parameter keys are rejected with `-32602`.

### `service.health`

```json
→ {"jsonrpc": "2.0", "id": 1, "method": "service.health", "params": {}}
← {"jsonrpc": "2.0", "id": 1, "result": {"status": "ok", "version": "1.0"}}
```

### `queens.open`: `{"size": int}`, where `size` is an integer from 4 to 10 (booleans are rejected)

```json
→ {"jsonrpc": "2.0", "id": 2, "method": "queens.open", "params": {"size": 8}}
← {"jsonrpc": "2.0", "id": 2, "result": {"stream_id": "5f0c3f5e-4f7b-4c8e-9d61-2a7c1f3b9e10", "size": 8}}
```

Returns without forcing the first event.

### `queens.next`: `{"stream_id": string, "limit": int}`, where `limit` is an integer from 1 to 32 and defaults to 1

```json
→ {"jsonrpc": "2.0", "id": 3, "method": "queens.next",
   "params": {"stream_id": "5f0c3f5e-...", "limit": 4}}
← {"jsonrpc": "2.0", "id": 3, "result": {"events": [
     {"event": "try",    "column": 0, "row": 0, "board": []},
     {"event": "place",  "column": 0, "row": 0, "board": [0]},
     {"event": "try",    "column": 0, "row": 1, "board": [0]},
     {"event": "reject", "column": 0, "row": 1, "board": [0]}],
   "done": false}}
```

Forces at most `limit` cells. If it reaches `done`, it stops there and sets
`"done": true`. A later `next` on the same id returns
`{"events": [], "done": true}`.

### `queens.close`: `{"stream_id": string}`

```json
→ {"jsonrpc": "2.0", "id": 4, "method": "queens.close", "params": {"stream_id": "5f0c3f5e-..."}}
← {"jsonrpc": "2.0", "id": 4, "result": {"closed": true}}
```

### Errors

| Code | Message | When | `data` |
| --- | --- | --- | --- |
| `-32700` | Parse error | body is not JSON | — |
| `-32600` | Invalid Request | bad envelope (`jsonrpc`, `method`, `id`, `params` shape, extra keys, empty batch) | `{"reason"}` |
| `-32601` | Method not found | method not in the fixed registry | `{"method"}` (truncated to 128 characters) |
| `-32602` | Invalid params | missing, unknown, or ill-typed parameter, or value out of range | `{"param", "reason"}` |
| `-32603` | Internal error | unexpected failure (logged on the server, never returned) | — |
| `-32020` | Unknown stream | id never issued, closed, or expired | `{"stream_id"}` (truncated) |
| `-32021` | Too many streams | 256 live streams already open | `{"limit": 256}` |

`-32020` and `-32021` are application codes in the server-error range.
Responses never contain tracebacks, file paths, or interpreter values.
`stream_id` must be a string of 1 to 64 characters; anything else is
`-32602`. A well-formed id that is not in the table is `-32020`. Request
bodies over 64 KiB get HTTP 413.

### Batches

A batch array is processed **sequentially, in order**, against the same
stream table. So `[open, ...]` cannot reference an id it has not yet
received, but `[next(id), next(id)]` returns two consecutive slices of the
same stream. Notifications in a batch produce no response entry. If every
member is a notification, the HTTP status is 204.

## 9. Stream lifetime, cleanup, limits

The stream table maps a `uuid4` string to an entry. Each entry holds a
`threading.Lock`, the current `EventStream` (or `None` once exhausted), and
a `last_used` timestamp from an injectable clock (`time.monotonic` by
default).

- **Atomicity.** `next` holds the entry's lock for the whole request, so
  two concurrent `next` calls on one stream get disjoint, consecutive
  slices. A separate table lock guards only dictionary operations.
- **Exhaustion.** When `next` reaches `done`, the `EventStream` (and every
  interpreter closure it references) is dropped, and the entry becomes a
  tiny **exhausted marker**. Repeated `next` returns `[]`, `done: true`.
  `close` removes the marker.
- **Close.** `close` on a live stream or a marker removes it and returns
  `{"closed": true}`. `close` on an unknown id returns `-32020`, and so
  does a second `close`.
- **Expiry.** An entry (live or marker) not used for **600 seconds**
  (10 minutes) expires. Expired entries are swept at the start of every
  stream method. After that the id returns `-32020`.
- **Cap.** At most **256 live** streams (entries that still hold an
  `EventStream`) exist at once. Exhausted markers do not count toward the
  cap: they hold no solver state and disappear on close or expiry. `open`
  sweeps expired entries first, then fails with `-32021` if 256 live
  streams remain. `open` validates `size` before allocating anything.
- **Failure inside the solver.** If forcing raises (which should not
  happen), the entry is removed, the error is logged, and the client gets
  `-32603`.
- All state is process-local. A server restart invalidates every id.

## 10. Browser client

Plain HTML, CSS, and ES modules served by Flask from `static/`, with no
external resources. Responsibilities are separated so each can be tested:

- `rpc.js`, **transport**: `RpcClient` with `open`, `next`, `close`. It
  takes an injectable `fetch`, throws `RpcFailure` on network, HTTP, or
  JSON-RPC errors, and holds no UI state.
- `player.js`, **playback state**: an event buffer that is refilled only
  when 4 or fewer events remain, 16 at a time for step/play and 32 at a
  time for next solution, and never the whole trace. It provides `step`,
  `play`, `pause`, `nextSolution`, and `reset`, plus counters (events,
  solutions, fetches). It is driven by a timer the tests can inject, and it
  holds pure helpers (`applyEvent`, `boardView`, `attackerOf`,
  `controlsFor`, `statusText`).
- `render.js`, **rendering**: DOM updates only. It turns the player's
  snapshot into board cells, status, counters, log, and button states. The
  attacking queen for `reject` comes from `attackerOf`, which checks the
  board snapshot for the same column or diagonal, nearest row first.
- `main.js`: wiring for the controls, the size selector (4–10, default 8),
  the speed slider, the status line, the event log, and the error banner.

**Controls.**

- **Start** opens a stream for the selected size.
- **Step** draws one event.
- **Play/Pause** animates at the chosen speed.
- **Next solution** fetches batches of 32 and fast-forwards, updating the
  counters and log without drawing intermediate boards, then draws the
  solution board.
- **Reset** closes the stream and clears the board. After `done`, the
  status shows "Search complete", which is styled differently from a
  solution, and Start restarts the search.
- RPC or network failures show an error banner and stop playback.

**Visual states.** These are distinct cell styles: `try` (outlined
candidate), `place` (queen), `reject` (red candidate plus a highlighted
attacker), `backtrack` (fading queen), and `solution` (whole board
highlighted).

## 11. Architecture diagram

```
 ┌───────────────────────────── Browser ─────────────────────────────┐
 │ main.js (controls) ─► player.js (queue, ≤32/fetch) ─► render.js   │
 │                              │                                    │
 │                         rpc.js (fetch)                            │
 └──────────────────────────────┼────────────────────────────────────┘
                                │ POST /rpc  (JSON-RPC 2.0)
                                ▼              GET / , /static/* ◄── static/
 ┌──────────────────────── Flask (transport.py) ─────────────────────┐
 │  jsonrpc.Dispatcher: envelope, ids, batch, notifications          │
 │        │                                                          │
 │        ▼                                                          │
 │  methods.py: validate params ──► streams.StreamTable              │
 │                                   { uuid → lock, EventStream,     │
 │                                     last_used }  TTL 600s, ≤256 live│
 └───────────────────────────────────────┼───────────────────────────┘
                                         │ next(): force one cell
                                         ▼
 ┌──────────────────── solver.py (Python bridge) ────────────────────┐
 │  load+typecheck queens.lam once; open(size); force; decode        │
 └───────────────────────────────────────┼───────────────────────────┘
                                         ▼
 ┌────────────────────── LAMBDA3 interpreter ────────────────────────┐
 │  queens.lam: check_safe ─ try_column ─ search  (CPS)              │
 │  lazy stream:  [ev₀ | lazy] → [ev₁ | lazy] → … (forced on demand) │
 └───────────────────────────────────────────────────────────────────┘
```

## 12. Testing strategy

- **Solver (through LAMBDA3):**
  - Safety checks: same column, both diagonals, a non-adjacent diagonal,
    and safe placements.
  - CPS success and failure paths, run with custom continuations written
    in LAMBDA3, including resumption at the next candidate.
  - All 92 solutions for 8×8, in lexicographic order, with no duplicates,
    matching a brute-force Python reference; the same check for sizes 4 to 7.
  - A full-trace comparison against a direct-style Python model of the
    same search, plus per-event board and coordinate checks.
- **Laziness:**
  - A counter wraps the interpreter's function application
    (`lambda3._d0val_apply`) and counts calls by function name
    (`check`, `try_column`, and so on).
  - Opening performs zero applications of search functions, and the lazy
    is unevaluated.
  - Forcing one cell leaves `cell.tail.evaluated == False`.
  - A bounded prefix leaves the next tail unforced, and forcing it
    increases the counter.
  - Each forced cell uses at most `size + 10` applications (measured
    worst case: `size + 7`).
  - The full 8×8 trace runs at recursion limit 1000.
- **Service** (later): Flask test client for every RPC rule in §8 and §9,
  plus an end-to-end run through all 92 solutions to `done`.
- **Client** (later): `node --test` for `rpc.js`, `player.js`, and the pure
  parts of `render.js`, plus a manual checklist for the controls.
