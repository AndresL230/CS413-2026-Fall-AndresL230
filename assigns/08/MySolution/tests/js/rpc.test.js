// node --test: the JSON-RPC transport (static/rpc.js) against a fake fetch.

import { test } from "node:test";
import assert from "node:assert/strict";

import { RpcClient, RpcFailure } from "../../static/rpc.js";
import { FakeServer } from "./fakes.js";

const fixed = (body, status = 200) => async () => ({ ok: status < 300, status, json: async () => body });

test("call sends a JSON-RPC 2.0 POST with increasing ids", async () => {
  const server = new FakeServer();
  const rpc = new RpcClient({ fetch: server.fetch });
  const id = await rpc.open(8);
  await rpc.next(id, 3);
  const [first, second] = server.calls;
  assert.equal(first.url, "/rpc");
  assert.equal(first.init.method, "POST");
  assert.equal(first.init.headers["Content-Type"], "application/json");
  assert.deepEqual(first.request, { jsonrpc: "2.0", id: 1, method: "queens.open", params: { size: 8 } });
  assert.deepEqual(second.request.params, { stream_id: id, limit: 3 });
  assert.equal(second.request.id, 2);
});

test("next returns the event batch", async () => {
  const rpc = new RpcClient({ fetch: new FakeServer().fetch });
  const id = await rpc.open(4);
  const result = await rpc.next(id, 2);
  assert.deepEqual(result, {
    events: [{ event: "try", column: 0, row: 0, board: [] }, { event: "place", column: 0, row: 0, board: [0] }],
    done: false,
  });
});

test("JSON-RPC errors become RpcFailure(kind rpc) with code and data", async () => {
  const rpc = new RpcClient({ fetch: new FakeServer().fetch });
  await assert.rejects(rpc.next("nope", 1), (err) => {
    assert.ok(err instanceof RpcFailure);
    assert.equal(err.kind, "rpc");
    assert.equal(err.code, -32020);
    assert.deepEqual(err.data, { stream_id: "nope" });
    return true;
  });
});

test("network failure becomes RpcFailure(kind network)", async () => {
  const rpc = new RpcClient({ fetch: async () => { throw new TypeError("Failed to fetch"); } });
  await assert.rejects(rpc.call("service.health"), { name: "RpcFailure", kind: "network" });
});

test("HTTP error status becomes RpcFailure(kind http)", async () => {
  const rpc = new RpcClient({ fetch: fixed({}, 502) });
  await assert.rejects(rpc.call("service.health"), { kind: "http", status: 502 });
});

test("non-JSON or mismatched responses are protocol failures", async () => {
  const notJson = new RpcClient({ fetch: async () => ({ ok: true, status: 200, json: async () => { throw new SyntaxError("x"); } }) });
  await assert.rejects(notJson.call("service.health"), { kind: "protocol" });
  const wrongId = new RpcClient({ fetch: fixed({ jsonrpc: "2.0", id: 99, result: {} }) });
  await assert.rejects(wrongId.call("service.health"), { kind: "protocol" });
  const noResult = new RpcClient({ fetch: fixed({ jsonrpc: "2.0", id: 1 }) });
  await assert.rejects(noResult.call("service.health"), { kind: "protocol" });
});

test("next rejects a batch larger than the requested limit", async () => {
  const events = Array.from({ length: 5 }, () => ({ event: "try", column: 0, row: 0, board: [] }));
  const rpc = new RpcClient({ fetch: fixed({ jsonrpc: "2.0", id: 1, result: { events, done: false } }) });
  await assert.rejects(rpc.next("s", 4), { kind: "protocol" });
});

test("closeOnUnload sends a keepalive notification and never throws", async () => {
  const server = new FakeServer();
  const rpc = new RpcClient({ fetch: server.fetch });
  const id = await rpc.open(8);
  rpc.closeOnUnload(id);
  await new Promise((r) => setImmediate(r));
  const close = server.callsTo("queens.close")[0];
  assert.equal(close.init.keepalive, true);
  assert.equal("id" in close.request, false);
  assert.deepEqual(close.request.params, { stream_id: id });
  assert.equal(server.streams.size, 0);
  const broken = new RpcClient({ fetch: () => { throw new Error("gone"); } });
  assert.doesNotThrow(() => broken.closeOnUnload("x"));
  const rejecting = new RpcClient({ fetch: async () => { throw new Error("gone"); } });
  assert.doesNotThrow(() => rejecting.closeOnUnload("x"));
});
