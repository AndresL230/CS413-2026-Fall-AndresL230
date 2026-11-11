# LAMBDA3 JSON-RPC Service (Assign07)

This is a JSON-RPC 2.0 service that makes the provided LAMBDA3 type-checker,
interpreter, and Python/JavaScript compilers available over HTTP at a single
endpoint, `POST /rpc`. The full contract (methods, error codes, limits,
examples) is in [`RPC.md`](RPC.md). The JSON Schema for the envelopes is in
[`schema/jsonrpc.schema.json`](schema/jsonrpc.schema.json).

> **Generated code is returned, never run.** `lambda.compile` returns the
> Python or JavaScript source produced by `d0exp_compile` / `d0exp_compile_js`
> as a string, unchanged. The service does not execute it, and nothing in the
> service uses `exec` or `eval`. The only method that runs a program is
> `lambda.interpret`, which uses the LAMBDA3 interpreter in a separate worker
> process with a 5-second hard deadline.

## Versions

| Component | Version |
| --- | --- |
| Python | 3.12 or later required (developed and tested on 3.14.8) |
| Flask | 3.1.3 |
| Werkzeug | 3.1.9 |
| pytest | 9.2.0 |

All dependencies are pinned in [`requirements.txt`](requirements.txt). The
instructor's black-box suite in `../TEST/` needs only the standard library.

## Layout

```
MySolution/
  server.py                 startup script (binds 127.0.0.1:8000)
  lambda_rpc/
    transport.py            Flask: POST /rpc, 415 / 405 / 413 / 404, 200 vs 204
    jsonrpc.py              JSON-RPC envelope validation, ids, batches, notifications, dispatch
    methods.py              method registry + parameter validation
    service.py              LAMBDA3 adapter: maps LAMBDA3 calls and exceptions to RPC results/errors
    worker.py               interpretation in a killable spawned process (deadline, recursion limit)
    errors.py, config.py    error codes; limits and the LAMBDA3 import path
  tests/                    pytest suite (Flask test client)
  RPC.md, schema/           contract and JSON Schema
  TESTING.md                requirement -> test mapping, observed results, architecture
```

`lambda3.py` is imported from `../LAMBDA3/`. The path is computed from the
location of `lambda_rpc/config.py`, so commands work from any working
directory.

## Setup

All commands below are run from `assigns/07/`:

```sh
python3 -m venv MySolution/.venv
MySolution/.venv/bin/pip install -r MySolution/requirements.txt
```

## Tests

Our HTTP-level suite (Flask test client, real LAMBDA3, no server needed):

```sh
MySolution/.venv/bin/python -m pytest MySolution/tests -v
```

The instructor's black-box suite needs the server to be running (see the
next section). In a second terminal:

```sh
python3 -m unittest discover -s TEST -v
```

Observed results for both are recorded in [`TESTING.md`](TESTING.md).

## Starting the service

```sh
MySolution/.venv/bin/python MySolution/server.py
```

The endpoint is **`http://127.0.0.1:8000/rpc`**. It accepts only `POST` with
`Content-Type: application/json`. The server uses Flask's development server,
bound to localhost only. It is meant for local development and tests, not
public deployment. Stop it with Ctrl-C.

## Usage (curl)

Every response below was captured from the running service.

### `service.health`

```sh
curl -s -X POST http://127.0.0.1:8000/rpc -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","method":"service.health","params":{},"id":1}'
```
```json
{"jsonrpc": "2.0", "id": 1, "result": {"status": "ok", "version": "1.0"}}
```

### `lambda.typecheck`

```sh
curl -s -X POST http://127.0.0.1:8000/rpc -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","method":"lambda.typecheck","params":{"source":"(1, true)"},"id":2}'
```
```json
{"jsonrpc": "2.0", "id": 2, "result": {"type": "(sint, bool)"}}
```

### `lambda.interpret`: factorial

```sh
curl -s -X POST http://127.0.0.1:8000/rpc -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","method":"lambda.interpret","params":{"source":"let fact : sint -> sint = fix fact(n: sint): sint => if n <= 1 then 1 else n * fact(n - 1) in fact(6) end"},"id":"fact"}'
```
```json
{"jsonrpc": "2.0", "id": "fact", "result": {"type": "sint", "value": "720"}}
```

### Unbound variable (type error, `-32011`)

LAMBDA3's type-checker rejects unbound variables, so the program is never
run:

```sh
curl -s -X POST http://127.0.0.1:8000/rpc -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","method":"lambda.interpret","params":{"source":"x + 1"},"id":"unbound"}'
```
```json
{"jsonrpc": "2.0", "id": "unbound", "error": {"code": -32011, "message": "LAMBDA type error: unbound variable 'x'", "data": {"detail": "unbound variable 'x'"}}}
```

### Syntax error (`-32010`)

```sh
curl -s -X POST http://127.0.0.1:8000/rpc -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","method":"lambda.typecheck","params":{"source":"if then"},"id":"syntax"}'
```
```json
{"jsonrpc": "2.0", "id": "syntax", "error": {"code": -32010, "message": "LAMBDA syntax error: Expected an expression", "data": {"line": 1, "column": 4, "snippet": "if then"}}}
```

### `lambda.compile`

The generated code is about 4.9 KB even for `1 + 2`, because LAMBDA3 includes
its runtime helpers. This example uses `jq` to print the target, the code
length, and the end of the code:

```sh
curl -s -X POST http://127.0.0.1:8000/rpc -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","method":"lambda.compile","params":{"source":"1 + 2","target":"python"},"id":"py"}' \
  | jq -r '.result.target, (.result.code | length), (.result.code | split("\n") | .[-9:] | join("\n"))'
```
```text
python
4872

def _lambda_main():
    _v1 = 1
    _v2 = 2
    _v3 = (_v1 + _v2)
    return _v3

_lambda_result = _lambda_main()
```

For JavaScript, use `"target":"javascript"` instead. The same summary gives
`{"id":"js","target":"javascript","code_chars":4996}`. Drop the `jq` filter to
see the full JSON response.

### Using the standard library (`LAMBDA3/mylib/`)

The service does not load libraries itself. The client sends a library file's
declarations as the binding part of a `let`. Here `jq` builds the request
from `list.lam`:

```sh
jq -n --rawfile lib LAMBDA3/mylib/list.lam \
  '{jsonrpc: "2.0", method: "lambda.interpret", id: "mylib",
    params: {source: ("let\n" + $lib + "\nin\nlist_map(list_range(1, 6), lam (x: sint) => x * x)\nend")}}' \
  | curl -s -X POST http://127.0.0.1:8000/rpc -H 'Content-Type: application/json' --data-binary @-
```
```json
{"jsonrpc": "2.0", "id": "mylib", "result": {"type": "List[sint]", "value": "[1, 4, 9, 16, 25]"}}
```

All four library files (`list`, `optn`, `strm`, `a1sz`) work this way and fit
under the 32,768-character source limit. See `RPC.md` §4.

### Runtime error, batch, notification, timeout

```sh
# well-typed but fails while running -> -32013
curl -s -X POST http://127.0.0.1:8000/rpc -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","method":"lambda.interpret","params":{"source":"1 / 0"},"id":"div"}'
```
```json
{"jsonrpc": "2.0", "id": "div", "error": {"code": -32013, "message": "LAMBDA runtime error: division by zero", "data": {"kind": "division_by_zero", "detail": "division by zero"}}}
```

```sh
# batch: one call + one notification -> one response (match by id)
curl -s -X POST http://127.0.0.1:8000/rpc -H 'Content-Type: application/json' \
  -d '[{"jsonrpc":"2.0","method":"lambda.interpret","params":{"source":"6 * 7"},"id":"answer"},
       {"jsonrpc":"2.0","method":"service.health","params":{}}]'
```
```json
[{"jsonrpc": "2.0", "id": "answer", "result": {"type": "sint", "value": "42"}}]
```

```sh
# a single notification gets no body and HTTP 204
curl -s -o /dev/null -w '%{http_code}\n' -X POST http://127.0.0.1:8000/rpc \
  -H 'Content-Type: application/json' -d '{"jsonrpc":"2.0","method":"service.health","params":{}}'
```
```text
204
```

```sh
# fib(30) terminates, but not within the 5 s deadline -> -32012
curl -s -X POST http://127.0.0.1:8000/rpc -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","method":"lambda.interpret","params":{"source":"let fib : sint -> sint = fix fib(n: sint): sint => if n < 2 then n else fib(n - 1) + fib(n - 2) in fib(30) end"},"id":"slow"}'
```
```json
{"jsonrpc": "2.0", "id": "slow", "error": {"code": -32012, "message": "Interpretation timed out", "data": {"seconds": 5}}}
```

A wrong content type is a transport failure, not an RPC error:
`curl -s -w '%{http_code}\n' -X POST http://127.0.0.1:8000/rpc -H 'Content-Type: text/plain' -d hello`
prints `Unsupported Media Type: use application/json` and `415`.

## Limits

These are summarized here. The details are in `RPC.md` §6.

| Limit | Value |
| --- | --- |
| HTTP body | 1 MiB (HTTP 413 beyond) |
| `source` length | 32,768 characters (`-32602` with `limit`/`actual`) |
| Source nesting | about 300 nested parentheses / about 1,000 chained operators (`-32602` "source nesting too deep") |
| Interpretation time | 5 s wall-clock per call, worker killed (`-32012`; a timeout does not prove non-termination) |
| Interpreter recursion | Python limit 100,000 in a 512 MiB worker thread (`-32013` `recursion_depth_exceeded`) |

Output from `print` inside a LAMBDA program goes to the worker's standard
output and is not returned to the client.
