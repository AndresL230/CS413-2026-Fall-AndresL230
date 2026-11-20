// JSON-RPC 2.0 transport for the N-Queens service. No UI state.
// `fetch` is injectable so node --test can use a fake.

export class RpcFailure extends Error {
  // kind: "network" | "http" | "protocol" | "rpc"
  constructor(kind, message, { code = null, data = null, status = null } = {}) {
    super(message);
    this.name = "RpcFailure";
    this.kind = kind;
    this.code = code;
    this.data = data;
    this.status = status;
  }
}

export class RpcClient {
  constructor({ fetch = globalThis.fetch?.bind(globalThis), url = "/rpc" } = {}) {
    this.fetch = fetch;
    this.url = url;
    this.nextId = 0;
  }

  async call(method, params = {}) {
    const id = ++this.nextId;
    let response;
    try {
      response = await this.fetch(this.url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ jsonrpc: "2.0", id, method, params }),
      });
    } catch {
      throw new RpcFailure("network", "Cannot reach the server");
    }
    if (!response.ok) {
      throw new RpcFailure("http", `HTTP ${response.status}`, { status: response.status });
    }
    let body;
    try {
      body = await response.json();
    } catch {
      throw new RpcFailure("protocol", "Response is not JSON");
    }
    if (!body || typeof body !== "object" || body.jsonrpc !== "2.0" || body.id !== id) {
      throw new RpcFailure("protocol", "Malformed JSON-RPC response");
    }
    if (body.error) {
      const { code = null, message = "RPC error", data = null } = body.error;
      throw new RpcFailure("rpc", message, { code, data });
    }
    if (!("result" in body)) throw new RpcFailure("protocol", "Response has no result");
    return body.result;
  }

  async open(size) {
    const result = await this.call("queens.open", { size });
    if (typeof result?.stream_id !== "string") throw new RpcFailure("protocol", "open: no stream_id");
    return result.stream_id;
  }

  async next(streamId, limit) {
    const result = await this.call("queens.next", { stream_id: streamId, limit });
    if (!Array.isArray(result?.events) || typeof result.done !== "boolean" || result.events.length > limit) {
      throw new RpcFailure("protocol", "next: malformed event batch");
    }
    return result;
  }

  async close(streamId) {
    return this.call("queens.close", { stream_id: streamId });
  }

  // Best-effort close while the page is being unloaded: a notification
  // (no id, so the server answers 204) sent with keepalive. Never throws.
  closeOnUnload(streamId) {
    try {
      const p = this.fetch(this.url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ jsonrpc: "2.0", method: "queens.close", params: { stream_id: streamId } }),
        keepalive: true,
      });
      p?.catch?.(() => {});
    } catch {
      // ignore: the server expires the stream after 10 minutes anyway
    }
  }
}
