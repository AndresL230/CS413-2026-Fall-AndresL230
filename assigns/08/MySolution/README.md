# Animated N-Queens Search (Assign08)

The program searches for N-Queens solutions in LAMBDA3, using
continuation-passing style (CPS). The search trace is a lazy stream of
events. A JSON-RPC 2.0 service (`POST /rpc`) delivers the events in small
batches to a browser client, which animates them.

The design is in [`DESIGN.md`](DESIGN.md), which covers continuation
conventions, the event schema, stream lifetime, and the architecture
diagram.

> **Status:** the solver, the bridge, and the RPC service are done. The
> browser client at `GET /` is a placeholder for now.

## Versions

| Component | Version |
| --- | --- |
| Python | 3.12 or later required (developed and tested on 3.14.8) |
| Flask | 3.1.3 |
| Werkzeug | 3.1.9 |
| pytest | 9.2.0 |

All dependencies are pinned in [`requirements.txt`](requirements.txt). The
supplied interpreter is imported from `../LAMBDA3/lambda3.py`, unmodified.
The import path is computed from the location of
`queens/lambda3_loader.py`, so commands work from any working directory.

## Layout

```
MySolution/
  server.py            startup script (binds 127.0.0.1:8000)
  queens/
    queens.lam         LAMBDA3 solver: safety check, board extension, events, CPS search
    solver.py          bridge: load + type-check, open, force one cell, decode events
    streams.py         stream table: uuid ids, per-stream locks, TTL, cap, exhausted markers
    methods.py         method registry + parameter validation
    jsonrpc.py         envelope validation, ids, batches, notifications (from Assign07)
    transport.py       Flask: POST /rpc, GET /, /static/*
    errors.py, config.py, lambda3_loader.py
  static/              browser client (placeholder index.html for now)
  tests/               pytest suite
```

## Setup

Run all commands from `assigns/08/`:

```sh
python3 -m venv MySolution/.venv
MySolution/.venv/bin/pip install -r MySolution/requirements.txt
```

## Tests

```sh
MySolution/.venv/bin/python -m pytest MySolution -v
```

The whole suite takes about 35 seconds. Most of that is spent consuming
the full 8×8 trace (33,589 events) twice: once in-process, shared by the
solver tests, and once over a real HTTP socket in the end-to-end test.

To run one part:

```sh
MySolution/.venv/bin/python -m pytest MySolution/tests/test_laziness.py -v    # laziness only
MySolution/.venv/bin/python -m pytest MySolution -v -k "rpc"                  # service only
```

## Starting the service

```sh
MySolution/.venv/bin/python MySolution/server.py
```

The page is at http://127.0.0.1:8000/, and the RPC endpoint is
`POST http://127.0.0.1:8000/rpc`. Stop the server with Ctrl-C.

## RPC examples (curl)

```sh
rpc() { curl -s -X POST http://127.0.0.1:8000/rpc -H 'Content-Type: application/json' -d "$1"; echo; }

rpc '{"jsonrpc":"2.0","id":1,"method":"service.health","params":{}}'
# {"jsonrpc": "2.0", "id": 1, "result": {"status": "ok", "version": "1.0"}}

rpc '{"jsonrpc":"2.0","id":2,"method":"queens.open","params":{"size":8}}'
# {"jsonrpc": "2.0", "id": 2, "result": {"stream_id": "4c9b81d9-...", "size": 8}}

rpc '{"jsonrpc":"2.0","id":3,"method":"queens.next","params":{"stream_id":"4c9b81d9-...","limit":4}}'
# {"jsonrpc": "2.0", "id": 3, "result": {"events": [
#   {"event": "try", "column": 0, "row": 0, "board": []},
#   {"event": "place", "column": 0, "row": 0, "board": [0]},
#   {"event": "try", "column": 0, "row": 1, "board": [0]},
#   {"event": "reject", "column": 0, "row": 1, "board": [0]}], "done": false}}

rpc '{"jsonrpc":"2.0","id":4,"method":"queens.close","params":{"stream_id":"4c9b81d9-..."}}'
# {"jsonrpc": "2.0", "id": 4, "result": {"closed": true}}

rpc '{"jsonrpc":"2.0","id":5,"method":"queens.next","params":{"stream_id":"4c9b81d9-..."}}'
# {"jsonrpc": "2.0", "id": 5, "error": {"code": -32020, "message": "Unknown stream",
#   "data": {"stream_id": "4c9b81d9-..."}}}

curl -s -o /dev/null -w '%{http_code}\n' -X POST http://127.0.0.1:8000/rpc \
  -H 'Content-Type: application/json' -d '{"jsonrpc":"2.0","method":"service.health"}'
# 204   (notification: no body)
```

## Methods

| Method | Params | Result |
| --- | --- | --- |
| `service.health` | `{}` | `{"status": "ok", "version": "1.0"}` |
| `queens.open` | `{"size": 4..10}` | `{"stream_id": uuid, "size": n}`, with no event forced |
| `queens.next` | `{"stream_id": str, "limit": 1..32}` (`limit` defaults to 1) | `{"events": [...], "done": bool}` |
| `queens.close` | `{"stream_id": str}` | `{"closed": true}` |

Integer parameters must be JSON integers. `true`/`false`, `8.0`, and `"8"`
are rejected with `-32602`, and so are unknown parameter keys. Event
objects are described in DESIGN.md §7.

## Error codes

| Code | Message | When | `data` |
| --- | --- | --- | --- |
| `-32700` | Parse error | body is not valid JSON (including `NaN`/`Infinity`) | none |
| `-32600` | Invalid Request | bad envelope: `jsonrpc` is not `"2.0"`, `method` is not a string, `id` is not a string/number/null, `params` is not an object/array, there are extra members, or the batch is empty | `{"reason"}` |
| `-32601` | Method not found | method is not one of the four above | `{"method"}` (first 128 characters) |
| `-32602` | Invalid params | a parameter is missing, unknown, of the wrong type, or out of range; positional params are rejected | `{"param", "reason"}` |
| `-32603` | Internal error | unexpected failure; logged on the server, and the stream is discarded | none |
| `-32020` | Unknown stream | the stream id was never issued, was closed, or expired | `{"stream_id"}` |
| `-32021` | Too many streams | 256 streams (live or exhausted) are already open | `{"limit": 256}` |

HTTP status codes:

- A call or a JSON-RPC error returns 200.
- A notification, or a batch made only of notifications, returns 204 with
  no body.
- A non-JSON `Content-Type` returns 415.
- `GET /rpc` returns 405.
- A body over 64 KiB returns 413.

## Limits and lifecycle

- **Events per `queens.next`:** 1 to 32. The response that contains
  `done` has `"done": true`, and every later `next` returns
  `{"events": [], "done": true}`.
- **After `done`:** the solver state is dropped, and an exhausted marker
  remains until `queens.close` or expiry.
- **Inactivity lifetime:** 600 seconds (10 minutes) per stream id, for live
  streams and exhausted markers alike. Expired ids are removed whenever any
  stream method runs, and then return `-32020`.
- **Open streams:** at most 256. Exhausted markers count toward this.
- **Batches** run sequentially in array order against the same stream
  table, so two `next` calls on one id return consecutive slices.
- **Process-local state:** restarting the server invalidates every stream
  id.

## Limitations

- The tree-walking interpreter manages about 3,500 events per second. A
  full 8×8 trace takes about 10 s; 9×9 takes about 50 s and 10×10 about
  260 s. The browser only fetches small batches, so playback is not
  affected.
- The service accepts no LAMBDA source text. It exposes only the fixed
  solver.
- There is no authentication or persistent storage, and the server is meant
  for local use only.
