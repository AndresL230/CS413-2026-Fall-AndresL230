# LAMBDA3 JSON-RPC Service — RPC Contract

Version `1.0`. This document is the contract for the service in this
directory. It was written before the dispatcher. Every example result below
comes from running the provided `LAMBDA3/lambda3.py` on the shown source. It
was not typed by hand. The formal envelope definitions are in
[`schema/jsonrpc.schema.json`](schema/jsonrpc.schema.json) (JSON Schema,
draft 2020-12).

## 1. Scope

The service exposes the provided LAMBDA3 parser, type-checker, interpreter,
and Python/JavaScript compilers to local clients over HTTP. It does not
implement any of them itself.

It is a local development and test service. Accounts, persistence, public
deployment, and lazy-stream delivery across calls (Assign08) are out of scope.
The service **never executes generated Python or JavaScript**. `lambda.compile`
returns generated source code as text and nothing else. Only `lambda.interpret`
runs a program, using the LAMBDA3 interpreter in a separate, killable process.

## 2. Transport contract

There is exactly one endpoint:

```
POST http://127.0.0.1:8000/rpc
Content-Type: application/json
```

Operations are **not** separate resource URLs. The method name inside the
JSON body selects the operation.

| Situation | HTTP status | Body |
| --- | --- | --- |
| Body produced one JSON-RPC response object or a response array. This includes parse errors, invalid requests, unknown methods, invalid params, and every LAMBDA error. | `200 OK` | JSON-RPC response (object or array), `Content-Type: application/json` |
| Single valid notification, or a batch with only valid notifications | `204 No Content` | empty |
| `Content-Type` is not `application/json` (parameters such as `; charset=utf-8` are allowed) | `415 Unsupported Media Type` | short plain-text message, not JSON-RPC |
| Request body larger than 1 MiB (1,048,576 bytes) | `413 Content Too Large` | short plain-text message, not JSON-RPC |
| Any method other than `POST` on `/rpc` | `405 Method Not Allowed`, with `Allow: POST` | short plain-text message, not JSON-RPC |
| Any other path | `404 Not Found` | short plain-text message, not JSON-RPC |

### HTTP status vs RPC outcome

HTTP reports whether the **transport** worked: whether the server accepted
and processed the HTTP message. It does not report whether the call succeeded.

- A non-2xx status means the request never reached the JSON-RPC dispatcher.
  The body is not a JSON-RPC response, so a client must not look for
  `result`/`error` in it.
- `200` means the dispatcher produced at least one JSON-RPC response. The
  outcome of each call is in that response's `result` or `error` member.
  A LAMBDA type error, an unknown method, and even malformed JSON
  (`-32700`) are all `200`. The HTTP exchange worked, and the RPC call failed.
- `204` means the dispatcher ran but there was nothing to answer (only
  notifications).

A client therefore checks the HTTP status first, then the JSON-RPC `error`
member.

## 3. JSON-RPC envelope

The service implements [JSON-RPC 2.0](https://www.jsonrpc.org/specification).

### Request object

| Member | Required | Rule |
| --- | --- | --- |
| `jsonrpc` | yes | exactly the string `"2.0"` |
| `method` | yes | string; method names are case-sensitive |
| `params` | no | if present, a JSON object; omitted `params` is treated as `{}`. An array (by-position params) passes envelope validation but is rejected by every method with `-32602`; any other type is `-32600`. |
| `id` | no | string, number, or `null`; if the member is absent, the request is a *notification* |

No other top-level members are allowed. Booleans are not valid IDs. Clients
should use strings or integers. `null` is allowed but discouraged, because it
cannot be told apart from the `id: null` used on Invalid Request errors.

### Response object

Every response has `"jsonrpc": "2.0"` and an `id`. It has **exactly one** of:

- `result`: the method's result (shapes in §4), or
- `error`: `{ "code": <integer>, "message": <string>, "data": <optional structured value> }`

A response never contains both `result` and `error`.

### Request IDs

- For a well-formed call, the response `id` is the request's `id`, copied
  unchanged (same JSON type and value). This also applies when the call fails
  with `-32601`, `-32602`, `-32603`, or any LAMBDA error.
- **Any request that fails envelope validation (`-32600`) is answered with
  `id: null`, even if it carried a usable `id`.** For example,
  `{"jsonrpc": "1.0", "method": "service.health", "id": 1}` gets
  `"id": null`. The service does not trust any member of an envelope it has
  rejected.
- A parse error (`-32700`) always has `id: null`, because no request could be
  read.
- The server does not check that IDs in a batch are unique. A client that
  reuses IDs in one batch cannot tell those responses apart.

### Notifications

A request without an `id` member is a notification. The server validates
and executes it like a call but **never returns a response for it**, whether
it succeeded or failed. A notification that fails envelope validation was
never a valid notification, so it **does** get a `-32600` response with
`id: null`. Notifications run synchronously; the `204` is sent only after
they finish.

### Validation order (per request object)

1. The value is a JSON object, otherwise `-32600`.
2. `jsonrpc` is exactly `"2.0"`, otherwise `-32600`.
3. `method` is present and is a string, otherwise `-32600`.
4. `id`, if present, is a string, number, or `null`, otherwise `-32600`.
5. `params`, if present, is an object or an array, otherwise `-32600`.
6. No members other than `jsonrpc`, `method`, `params`, `id`, otherwise `-32600`.
7. `method` names a known method, otherwise `-32601`.
8. `params` is an object, not an array, otherwise `-32602`.
9. Method-specific parameter rules (§4), otherwise `-32602`.
10. Run the method. LAMBDA errors are `-32010` to `-32013`; unexpected
    failures are `-32603`.

Steps 1–6 produce `id: null`. Steps 7–10 keep the request's `id`.

### Batches

- A batch is a JSON array of request objects. Members are processed in
  order, one at a time.
- The response is an array with one entry for every call and every invalid
  member. Valid notifications get no entry. **Clients must match responses
  by `id`, not by position.**
- An invalid member (not an object, wrong `jsonrpc`, and so on) gets a
  `-32600` response with `id: null`. The other members are still processed.
- If every member is a valid notification, the response is `204` with an
  empty body.
- An empty batch `[]` is itself an invalid request. The response is **one**
  `-32600` response object with `id: null`, not an array.
- An array nested inside a batch is an invalid member (`-32600`). Batches do
  not nest.

## 4. Methods

| RPC method | `params` | `result` | Behavior |
| --- | --- | --- | --- |
| `service.health` | `{}` | `{ "status": "ok", "version": "1.0" }` | Liveness and API version. Never calls LAMBDA3. |
| `lambda.typecheck` | `{ "source": string }` | `{ "type": string }` | Parse + type-check. |
| `lambda.interpret` | `{ "source": string }` | `{ "type": string, "value": string }` | Parse + type-check, then evaluate under the deadline. |
| `lambda.compile` | `{ "source": string, "target": "python" \| "javascript" }` | `{ "target": string, "code": string }` | Parse + type-check, then generate code. Code is returned, not run. |

### Parameter rules (all `-32602` when violated)

- `params` must be an object. A by-position array is rejected.
- Unknown parameter keys are rejected (`service.health` accepts only `{}`).
- `source` is required, must be a string, must contain at least one
  non-whitespace character, and must be at most **32,768 characters**
  (Unicode code points).
- `target` (compile only) is required and must be exactly `"python"` or
  `"javascript"`.

### `service.health`

Returns the fixed object `{"status": "ok", "version": "1.0"}`. `version` is
the version of this API contract.

### `lambda.typecheck`

Calls `d0exp_parse_and_typecheck(source)` and returns
`format_type(type)`. Types use LAMBDA3's own notation: `sint`, `bool`,
`unit`, `(sint, bool)`, `sint -> sint`, `List[sint]`, and so on. A type that
is not fully determined is printed with LAMBDA3's type variables (for example
`?t1`).

### `lambda.interpret`

1. The service process calls `d0exp_parse_and_typecheck(source)`. Syntax and
   type errors are therefore returned at once, without starting a worker.
2. A **fresh worker process** parses the source again and runs
   `d0exp_evaluate`. Inside the worker, evaluation runs in a thread with a
   512 MiB stack and a Python recursion limit of 100,000.
3. The parent waits at most **5 seconds** (wall-clock, including worker
   start-up). If the deadline passes, the worker is terminated and the call
   fails with `-32012`.
4. The value is formatted with `d0val_format` **inside the worker**, so
   formatting also counts against the deadline. Only the formatted string
   comes back to the parent. The result is
   `{"type": format_type(type), "value": d0val_format(value)}`.

Integers are unbounded in LAMBDA3, but Python by default refuses to convert
integers longer than 4,300 digits to or from strings. Without a change,
`fact(5000)` would evaluate and then fail in `d0val_format`, and a long
integer literal would fail in the parser. Both the service process and the
worker therefore call `sys.set_int_max_str_digits(0)`. Literal parsing is
bounded by the source-size cap (a 32,000-digit literal parses in about 7 ms).
Formatting a computed value is bounded by the interpretation deadline.

Values are always returned as their `d0val_format` strings, never as JSON
structures. Function values come back as `<lam>` or `<fix>`. Closures and
environments are never serialized.

`print(e)` in a LAMBDA program writes to the worker's standard output and
evaluates to `()` of type `unit`. That printed output is **not** captured or
returned in this version.

### `lambda.compile`

Parse + type-check (step 1 above), then `d0exp_compile(expr)` for
`"python"` or `d0exp_compile_js(expr)` for `"javascript"`. The generated
string is returned **unchanged** (including LAMBDA3's runtime helper
prelude, about 4.9 KB even for `1 + 2`). The service never runs it.

### Using the standard library (`LAMBDA3/mylib/`)

The service does not load library files automatically, and there is no
library method. A client uses a library by reading the `.lam` file itself
and sending its declarations as the binding part of a `let`:

```text
let
<contents of mylib/list.lam>
in
list_map(list_range(1, 6), lam (x: sint) => x * x)
end
```

The source then goes through the same `lambda.typecheck` /
`lambda.interpret` / `lambda.compile` path as any other source. The source
cap counts the library text too. All four files were checked with
`d0exp_parse_and_typecheck` this way, and all fit under the cap and parse at
the service's default recursion limit:

| File | Wrapped size (chars) | Example body | Result |
| --- | --- | --- | --- |
| `list.lam` | 3,545 + body | `list_map(list_range(1, 6), lam (x: sint) => x * x)` | `List[sint]`, `[1, 4, 9, 16, 25]` |
| `optn.lam` | 2,318 + body | `optn_get_default(optn_map(optn_cons(20), lam (x: sint) => x + 1), 0)` | `sint`, `21` |
| `strm.lam` | 4,883 + body | `strm_to_list(strm_take(strm_range(0, 100), 5))` | `List[sint]`, `[0, 1, 2, 3, 4]` |
| `a1sz.lam` | 5,590 + body | `a1sz_quicksort(a1sz_make_nfun(5, lam (i: sint) => 5 - i), lam (p: (sint, sint)) => p.0 <= p.1)` | `A1sz[sint]`, `[1, 2, 3, 4, 5]` |

## 5. Errors

### Error code table

| Code | `message` | When | `data` |
| --- | --- | --- | --- |
| `-32700` | `Parse error` | Body is not valid JSON (or not valid UTF-8) | none |
| `-32600` | `Invalid Request` | Envelope fails §3 steps 1–6; empty batch; invalid batch member | `{ "reason": string }` |
| `-32601` | `Method not found` | Unknown method name | `{ "method": string }` (name truncated to 128 chars) |
| `-32602` | `Invalid params` | `params` is an array; unknown key; `source` missing / not a string / blank / too large / too deeply nested; bad `target` | `{ "param"?: string, "reason": string }` plus `limit` and `actual` for oversized source |
| `-32603` | `Internal error` | Unexpected server failure, including a worker that crashes without a result | none |
| `-32010` | `LAMBDA syntax error: <parser message>` | `LambdaSyntaxError` from the parser | `{ "line": int, "column": int, "snippet": string }` |
| `-32011` | `LAMBDA type error: <checker message>` | `TypeCheckError` from the type-checker (includes unbound variables) | `{ "detail": string }` |
| `-32012` | `Interpretation timed out` | Interpretation did not finish within the deadline | `{ "seconds": 5 }` |
| `-32013` | `LAMBDA runtime error: <detail>` | A well-typed program failed while running | `{ "kind": string, "detail": string }` |

`-32010` to `-32013` are application codes in the JSON-RPC server-error range
(`-32000` to `-32099`). A LAMBDA syntax error is **not** a JSON-RPC parse
error. `-32700` means the HTTP body was not JSON.

#### Field details

- **`-32010`**: `line` and `column` are 1-based and come from the
  `LambdaSyntaxError` (`lineno`, `offset`). `snippet` is the source line
  containing the error, cut to 200 characters if it is longer.
- **`-32011`**: `detail` is the `TypeCheckError` message, unchanged. LAMBDA3
  has no separate lint step. An unbound variable is a type error here, for
  example `unbound variable 'x'`.
- **`-32012`**: a timeout means only that evaluation did not finish within
  the deadline. **It does not prove the program diverges.** For example,
  `fib(30)` terminates but is too slow for this interpreter.
- **`-32013`**: `kind` is a stable, language-level label. `detail` is the
  interpreter's message:

  | Python exception in the worker | `kind` | Example `detail` |
  | --- | --- | --- |
  | `ZeroDivisionError` | `division_by_zero` | `division by zero` |
  | `ValueError` | `invalid_operation` | `list_head: nonempty list expected` |
  | `IndexError` | `index_out_of_range` | `a1sz_getat: index out of range` |
  | `RecursionError` | `recursion_depth_exceeded` | `recursion depth limit exceeded` |

  Any other exception in the worker (for example the interpreter's internal
  `TypeError` or a `MemoryError`) is unexpected for a well-typed program and
  is reported as `-32603`.

### Information handling

- No response ever contains a Python traceback, exception class name, file
  system path, or the repr of an internal object. Unexpected failures are
  logged on the server with their traceback, and the client gets only
  `{"code": -32603, "message": "Internal error"}`.
- Strings echoed back to the client are limited to the client's own input:
  the method name, at most 128 characters; the source snippet, at most 200
  characters; and LAMBDA3's own diagnostic messages.
- `-32602` reasons are fixed strings chosen by the service, for example
  `"source must be a nonempty string"`.

## 6. Limits

| Limit | Value | Enforcement | Outcome when exceeded |
| --- | --- | --- | --- |
| HTTP body size | 1 MiB (1,048,576 bytes) | Flask `MAX_CONTENT_LENGTH`, before JSON parsing | HTTP `413`, no JSON-RPC body |
| `source` length | 32,768 characters | Service parameter validation, before parsing | `-32602`, `data: {"param": "source", "reason": "source exceeds maximum size", "limit": 32768, "actual": <n>}` |
| Source nesting depth | about 300 nested parentheses, or a chain of about 1,000 binary operators (the parser and checker are recursive and run at Python's default recursion limit in the service process) | `RecursionError` caught around parse / type-check / compile | `-32602`, `data: {"param": "source", "reason": "source nesting too deep"}` |
| Interpretation wall-clock time | 5 seconds per `lambda.interpret` call, including worker start-up | Worker process terminated by the parent at the deadline | `-32012`, `data: {"seconds": 5}` |
| Interpreter recursion depth | Python recursion limit 100,000 in a 512 MiB worker thread (measured: recursion 5,000 calls deep succeeds in 0.4 s; 50,000 deep exceeds the limit; unbounded recursion fails in about 1.3 s) | `RecursionError` inside the worker | `-32013`, `kind: "recursion_depth_exceeded"` |
| Integer digits | unlimited (`sys.set_int_max_str_digits(0)` in service and worker) | bounded by the source cap for literals and by the deadline for computed values | — |
| Batch length | no separate limit; bounded by the 1 MiB body size | — | — |

The 5-second deadline is below the 10-second client timeout used by the
course's black-box test suite. Each batch member that calls
`lambda.interpret` gets its own 5-second deadline, so a long batch can take
longer than any single deadline.

## 7. Examples

All examples are HTTP `POST /rpc` with `Content-Type: application/json`.
Unless marked otherwise, the HTTP status is `200`. Results come from running
LAMBDA3 on the shown source.

### 7.1 Health

```json
{"jsonrpc": "2.0", "method": "service.health", "params": {}, "id": "health-1"}
```

```json
{"jsonrpc": "2.0", "id": "health-1", "result": {"status": "ok", "version": "1.0"}}
```

### 7.2 Successful type-checking

```json
{"jsonrpc": "2.0", "method": "lambda.typecheck", "params": {"source": "let fact : sint -> sint =\n  fix fact(n: sint): sint =>\n    if n <= 1 then 1 else n * fact(n - 1)\nin fact end"}, "id": 2}
```

```json
{"jsonrpc": "2.0", "id": 2, "result": {"type": "sint -> sint"}}
```

### 7.3 Successful interpretation

Factorial:

```json
{"jsonrpc": "2.0", "method": "lambda.interpret", "params": {"source": "let fact : sint -> sint =\n  fix fact(n: sint): sint =>\n    if n <= 1 then 1 else n * fact(n - 1)\nin fact(6) end"}, "id": 3}
```

```json
{"jsonrpc": "2.0", "id": 3, "result": {"type": "sint", "value": "720"}}
```

Tuple, list, and function values:

| `source` | `result` |
| --- | --- |
| `20 + 22` | `{"type": "sint", "value": "42"}` |
| `(1, true)` | `{"type": "(sint, bool)", "value": "(1, true)"}` |
| `list_cons(1, list_cons(2, list_nil()))` | `{"type": "List[sint]", "value": "[1, 2]"}` |
| `let f : sint -> sint = lam (x: sint) => x in f end` | `{"type": "sint -> sint", "value": "<lam>"}` |
| `print(41 + 1)` | `{"type": "unit", "value": "()"}` (the `42` printed by the program is not returned) |

### 7.4 Compilation

```json
{"jsonrpc": "2.0", "method": "lambda.compile", "params": {"source": "1 + 2", "target": "python"}, "id": "py"}
```

The real `code` string is 4,872 characters. **Only here** is the middle
replaced by `…` to keep the document readable. The real string starts and
ends exactly as shown.

```json
{"jsonrpc": "2.0", "id": "py", "result": {"target": "python", "code": "# The emitted program uses Python values for integers, booleans, lists and\n# tuples. … \n\ndef _lambda_main():\n    _v1 = 1\n    _v2 = 2\n    _v3 = (_v1 + _v2)\n    return _v3\n\n_lambda_result = _lambda_main()\n"}}
```

JavaScript (real `code` is 4,996 characters, shortened the same way):

```json
{"jsonrpc": "2.0", "method": "lambda.compile", "params": {"source": "1 + 2", "target": "javascript"}, "id": "js"}
```

```json
{"jsonrpc": "2.0", "id": "js", "result": {"target": "javascript", "code": "const _lambda_some_tag = Symbol(\"some\");\nconst _lambda_tuple_tag = Symbol(\"tuple\");\n… \nfunction _lambda_main() {\n  let _v1 = 1;\n  let _v2 = 2;\n  let _v3 = (_v1 + _v2);\n  return _v3;\n}\nconst _lambda_result = _lambda_main();\n"}}
```

### 7.5 LAMBDA syntax error (`-32010`)

```json
{"jsonrpc": "2.0", "method": "lambda.typecheck", "params": {"source": "if then"}, "id": "syntax"}
```

```json
{"jsonrpc": "2.0", "id": "syntax", "error": {"code": -32010, "message": "LAMBDA syntax error: Expected an expression", "data": {"line": 1, "column": 4, "snippet": "if then"}}}
```

A multi-line source reports the line of the error:

```json
{"jsonrpc": "2.0", "method": "lambda.interpret", "params": {"source": "let x = 1 in\n  x +\nend"}, "id": "syntax-2"}
```

```json
{"jsonrpc": "2.0", "id": "syntax-2", "error": {"code": -32010, "message": "LAMBDA syntax error: Expected an expression", "data": {"line": 3, "column": 1, "snippet": "end"}}}
```

### 7.6 LAMBDA type errors (`-32011`)

```json
{"jsonrpc": "2.0", "method": "lambda.typecheck", "params": {"source": "1 + true"}, "id": "type"}
```

```json
{"jsonrpc": "2.0", "id": "type", "error": {"code": -32011, "message": "LAMBDA type error: +: expected bool, got sint", "data": {"detail": "+: expected bool, got sint"}}}
```

Unbound variable (LAMBDA3's checker rejects it; there is no separate lint
step):

```json
{"jsonrpc": "2.0", "method": "lambda.interpret", "params": {"source": "x + 1"}, "id": "unbound"}
```

```json
{"jsonrpc": "2.0", "id": "unbound", "error": {"code": -32011, "message": "LAMBDA type error: unbound variable 'x'", "data": {"detail": "unbound variable 'x'"}}}
```

### 7.7 LAMBDA runtime errors (`-32013`)

Division by zero is well-typed (`sint`) but fails during evaluation:

```json
{"jsonrpc": "2.0", "method": "lambda.interpret", "params": {"source": "1 / 0"}, "id": "div"}
```

```json
{"jsonrpc": "2.0", "id": "div", "error": {"code": -32013, "message": "LAMBDA runtime error: division by zero", "data": {"kind": "division_by_zero", "detail": "division by zero"}}}
```

Head of an empty list:

```json
{"jsonrpc": "2.0", "method": "lambda.interpret", "params": {"source": "let xs : List[sint] = list_nil() in list_head(xs) end"}, "id": "head"}
```

```json
{"jsonrpc": "2.0", "id": "head", "error": {"code": -32013, "message": "LAMBDA runtime error: list_head: nonempty list expected", "data": {"kind": "invalid_operation", "detail": "list_head: nonempty list expected"}}}
```

Unbounded recursion reaches the recursion limit (in about 1.3 s) before the
deadline, so it is a runtime error, not a timeout:

```json
{"jsonrpc": "2.0", "method": "lambda.interpret", "params": {"source": "let f : sint -> sint = fix f(n: sint): sint => f(n + 1) in f(0) end"}, "id": "loop"}
```

```json
{"jsonrpc": "2.0", "id": "loop", "error": {"code": -32013, "message": "LAMBDA runtime error: recursion depth limit exceeded", "data": {"kind": "recursion_depth_exceeded", "detail": "recursion depth limit exceeded"}}}
```

### 7.8 Interpretation timeout (`-32012`)

`fib(30)` terminates, but this interpreter needs more than 7 s for it
(measured), so the 5 s deadline stops it:

```json
{"jsonrpc": "2.0", "method": "lambda.interpret", "params": {"source": "let fib : sint -> sint = fix fib(n: sint): sint => if n < 2 then n else fib(n - 1) + fib(n - 2) in fib(30) end"}, "id": "slow"}
```

```json
{"jsonrpc": "2.0", "id": "slow", "error": {"code": -32012, "message": "Interpretation timed out", "data": {"seconds": 5}}}
```

### 7.9 Protocol and parameter errors

Malformed JSON (body `{"jsonrpc":`):

```json
{"jsonrpc": "2.0", "id": null, "error": {"code": -32700, "message": "Parse error"}}
```

Wrong protocol version. The request had `id: 1`, but invalid requests are
answered with `id: null`:

```json
{"jsonrpc": "1.0", "method": "service.health", "id": 1}
```

```json
{"jsonrpc": "2.0", "id": null, "error": {"code": -32600, "message": "Invalid Request", "data": {"reason": "jsonrpc must be \"2.0\""}}}
```

Unknown method:

```json
{"jsonrpc": "2.0", "method": "does.not.exist", "params": {}, "id": "unknown"}
```

```json
{"jsonrpc": "2.0", "id": "unknown", "error": {"code": -32601, "message": "Method not found", "data": {"method": "does.not.exist"}}}
```

Invalid params (each shown with its response `error` member):

| `params` | `error` |
| --- | --- |
| `{"source": "   "}` | `{"code": -32602, "message": "Invalid params", "data": {"param": "source", "reason": "source must be a nonempty string"}}` |
| `{"source": 12}` | `{"code": -32602, "message": "Invalid params", "data": {"param": "source", "reason": "source must be a nonempty string"}}` |
| `{}` (interpret) | `{"code": -32602, "message": "Invalid params", "data": {"param": "source", "reason": "missing required parameter"}}` |
| `["1 + 2"]` | `{"code": -32602, "message": "Invalid params", "data": {"reason": "params must be an object"}}` |
| `{"source": "1", "extra": 1}` | `{"code": -32602, "message": "Invalid params", "data": {"param": "extra", "reason": "unknown parameter"}}` |
| `{"source": "1 + 2", "target": "ruby"}` (compile) | `{"code": -32602, "message": "Invalid params", "data": {"param": "target", "reason": "target must be \"python\" or \"javascript\""}}` |
| `{"source": "<40,000 characters>"}` | `{"code": -32602, "message": "Invalid params", "data": {"param": "source", "reason": "source exceeds maximum size", "limit": 32768, "actual": 40000}}` |
| `{"source": "(((…(1)…)))"}` (1,000 levels) | `{"code": -32602, "message": "Invalid params", "data": {"param": "source", "reason": "source nesting too deep"}}` |

### 7.10 Single notification

```json
{"jsonrpc": "2.0", "method": "service.health", "params": {}}
```

Response: HTTP **`204 No Content`**, empty body.

### 7.11 Batch with calls and a notification

```json
[
  {"jsonrpc": "2.0", "method": "lambda.interpret", "params": {"source": "6 * 7"}, "id": "answer"},
  {"jsonrpc": "2.0", "method": "lambda.typecheck", "params": {"source": "1 + true"}, "id": 7},
  {"jsonrpc": "2.0", "method": "service.health", "params": {}}
]
```

HTTP `200`. There are two entries, because the notification gets none.
Match them by `id`:

```json
[
  {"jsonrpc": "2.0", "id": "answer", "result": {"type": "sint", "value": "42"}},
  {"jsonrpc": "2.0", "id": 7, "error": {"code": -32011, "message": "LAMBDA type error: +: expected bool, got sint", "data": {"detail": "+: expected bool, got sint"}}}
]
```

### 7.12 Notification-only batch

```json
[
  {"jsonrpc": "2.0", "method": "service.health", "params": {}},
  {"jsonrpc": "2.0", "method": "lambda.typecheck", "params": {"source": "1 + 2"}}
]
```

Response: HTTP **`204 No Content`**, empty body.

### 7.13 Batch with invalid members

```json
[
  {"jsonrpc": "2.0", "method": "service.health", "params": {}, "id": "ok"},
  "not-a-request-object",
  {"jsonrpc": "2.0", "method": 42, "id": 9}
]
```

HTTP `200`. Both invalid members get `id: null`. The third member's `id: 9`
is not echoed back, because its envelope was rejected:

```json
[
  {"jsonrpc": "2.0", "id": "ok", "result": {"status": "ok", "version": "1.0"}},
  {"jsonrpc": "2.0", "id": null, "error": {"code": -32600, "message": "Invalid Request", "data": {"reason": "request must be an object"}}},
  {"jsonrpc": "2.0", "id": null, "error": {"code": -32600, "message": "Invalid Request", "data": {"reason": "method must be a string"}}}
]
```

### 7.14 Empty batch

```json
[]
```

HTTP `200`. The response is a single object, not an array:

```json
{"jsonrpc": "2.0", "id": null, "error": {"code": -32600, "message": "Invalid Request", "data": {"reason": "empty batch"}}}
```

## 8. JSON Schema

[`schema/jsonrpc.schema.json`](schema/jsonrpc.schema.json) (draft 2020-12)
defines both directions of the protocol under `$defs`:

- **Requests:** `request` (a call or notification, with method-specific
  `params` selected by `method`), `batchRequest`, and `requestPayload` (one
  request or a nonempty batch).
- **Responses:** `successResponse`, `errorResponse`, `response`,
  `batchResponse`, and `responsePayload`. Result shapes are in
  `healthResult`, `typecheckResult`, `interpretResult`, and `compileResult`.
  Error `data` shapes are tied to each error code.

The schema describes **valid** requests. Invalid requests are not described
by it. How the service answers them is defined in §3 and §5 above.
