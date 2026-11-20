// Test doubles for node --test: a direct-style trace generator (same search
// order as queens.lam) and a fake fetch that speaks the service's JSON-RPC.

export function referenceTrace(size) {
  const events = [];
  const attacks = (column, row, board) =>
    board.some((c, r) => c === column || Math.abs(c - column) === row - r);
  const search = (row, board) => {
    if (row === size) { events.push({ event: "solution", board: [...board] }); return; }
    for (let column = 0; column < size; column++) {
      events.push({ event: "try", column, row, board: [...board] });
      if (attacks(column, row, board)) {
        events.push({ event: "reject", column, row, board: [...board] });
        continue;
      }
      const child = [...board, column];
      events.push({ event: "place", column, row, board: [...child] });
      search(row + 1, child);
      events.push({ event: "backtrack", column, row, board: [...board] });
    }
  };
  search(0, []);
  events.push({ event: "done" });
  return events;
}

const response = (body, status = 200) => ({
  ok: status >= 200 && status < 300,
  status,
  json: async () => body,
});

// A fake server. `calls` records every request; `failNext` can inject failures.
export class FakeServer {
  constructor() {
    this.streams = new Map();
    this.calls = [];
    this.counter = 0;
    this.failure = null; // null | "network" | "http" | { code, message }
    this.gate = null;    // a promise every request waits on (see hold())
    this.fetch = this.fetch.bind(this);
  }

  // Hold all requests until the returned release() is called.
  hold() {
    let release;
    this.gate = new Promise((resolve) => { release = resolve; });
    return () => { this.gate = null; release(); };
  }

  async fetch(url, init) {
    const request = JSON.parse(init.body);
    this.calls.push({ url, init, request });
    if (this.gate) await this.gate;
    if (this.failure === "network") throw new TypeError("Failed to fetch");
    if (this.failure === "http") return response({}, 502);
    const reply = (result) => response({ jsonrpc: "2.0", id: request.id, result });
    const error = (code, message, data) => response({ jsonrpc: "2.0", id: request.id, error: { code, message, data } });
    if (this.failure) return error(this.failure.code, this.failure.message);
    const p = request.params ?? {};
    switch (request.method) {
      case "queens.open": {
        const id = `stream-${++this.counter}`;
        this.streams.set(id, { events: referenceTrace(p.size), pos: 0 });
        return reply({ stream_id: id, size: p.size });
      }
      case "queens.next": {
        const s = this.streams.get(p.stream_id);
        if (!s) return error(-32020, "Unknown stream", { stream_id: p.stream_id });
        const events = s.events.slice(s.pos, s.pos + p.limit);
        s.pos += events.length;
        return reply({ events, done: s.pos >= s.events.length });
      }
      case "queens.close":
        if (!this.streams.delete(p.stream_id)) return error(-32020, "Unknown stream", { stream_id: p.stream_id });
        return reply({ closed: true });
      default:
        return error(-32601, "Method not found");
    }
  }

  callsTo(method) {
    return this.calls.filter((c) => c.request.method === method);
  }

  // Events the client has pulled from the server so far.
  eventsServed() {
    return this.callsTo("queens.next").length && [...this.streams.values()].reduce((n, s) => n + s.pos, 0);
  }
}

// Manual timer: schedule() records callbacks; fire() runs the pending one.
export class FakeTimers {
  constructor() { this.pending = new Map(); this.nextHandle = 1; this.delays = []; }
  schedule = (fn, ms) => { const h = this.nextHandle++; this.pending.set(h, fn); this.delays.push(ms); return h; };
  cancel = (h) => { this.pending.delete(h); };
  get count() { return this.pending.size; }
  async fire() {
    const [h, fn] = this.pending.entries().next().value;
    this.pending.delete(h);
    await fn();
  }
}

// Let queued promise callbacks (background refills) run.
export const flush = () => new Promise((resolve) => setImmediate(resolve));
