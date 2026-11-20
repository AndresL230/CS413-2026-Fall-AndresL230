// Playback state for the N-Queens client. No DOM and no fetch: the RPC
// client and the timer functions are injected, so node --test can drive it.
//
// Phases: idle -> busy (opening) -> ready -> playing <-> paused -> done
//         any -> error;  reset() -> idle from anywhere.

export const MIN_SIZE = 4;
export const MAX_SIZE = 10;
export const LOW_WATER = 4;     // refill when this many events or fewer are buffered
export const STEP_BATCH = 16;   // events per queens.next during step/play
export const FF_BATCH = 32;     // events per queens.next during "next solution"
export const LOG_LIMIT = 200;   // event log entries kept
export const UNKNOWN_STREAM = -32020;

// ---- Pure helpers ---------------------------------------------------------------

// The queen that attacks (column, row) on a row-order board, nearest row first.
export function attackerOf(column, row, board) {
  for (let r = row - 1; r >= 0; r--) {
    const c = board[r];
    if (c === column || Math.abs(c - column) === row - r) return { row: r, column: c };
  }
  return null;
}

export function describe(event) {
  const at = `row ${event.row}, col ${event.column}`;
  switch (event.event) {
    case "try": return `try ${at}`;
    case "place": return `place ${at}`;
    case "reject": {
      const a = attackerOf(event.column, event.row, event.board);
      return `reject ${at}` + (a ? ` (attacked by row ${a.row}, col ${a.column})` : "");
    }
    case "backtrack": return `backtrack ${at}`;
    case "solution": return `solution [${event.board.join(", ")}]`;
    case "done": return "done: no more solutions";
    default: return `unknown event ${String(event.event)}`;
  }
}

export function initialState(size) {
  return {
    size,
    board: [],
    event: null,
    attacker: null,
    counts: { events: 0, try: 0, place: 0, reject: 0, backtrack: 0, solution: 0 },
    log: [],
    finished: false,
  };
}

// Pure: returns a new state with one event applied.
export function applyEvent(state, event) {
  const counts = { ...state.counts, events: state.counts.events + 1 };
  if (event.event in counts && event.event !== "events") counts[event.event] += 1;
  const log = state.log.concat([{ n: counts.events, kind: event.event, text: describe(event) }]);
  if (log.length > LOG_LIMIT) log.splice(0, log.length - LOG_LIMIT);
  return {
    ...state,
    board: event.event === "done" ? [] : event.board.slice(),
    event,
    attacker: event.event === "reject" ? attackerOf(event.column, event.row, event.board) : null,
    counts,
    log,
    finished: event.event === "done",
  };
}

// size x size grid of CSS class names for the renderer.
export function boardView(state) {
  const n = state.size;
  const grid = Array.from({ length: n }, () => Array(n).fill(""));
  state.board.forEach((c, r) => { grid[r][c] = "queen"; });
  const e = state.event;
  if (!e) return grid;
  if (e.event === "try") grid[e.row][e.column] = "try";
  else if (e.event === "place") grid[e.row][e.column] = "queen placed";
  else if (e.event === "reject") {
    grid[e.row][e.column] = "reject";
    if (state.attacker) grid[state.attacker.row][state.attacker.column] = "queen attacker";
  } else if (e.event === "backtrack") grid[e.row][e.column] = "backtrack";
  else if (e.event === "solution") state.board.forEach((c, r) => { grid[r][c] = "queen solution"; });
  return grid;
}

export function controlsFor(phase) {
  const active = phase === "ready" || phase === "paused" || phase === "playing";
  return {
    start: phase !== "busy",
    step: phase === "ready" || phase === "paused",
    play: active,
    playLabel: phase === "playing" ? "Pause" : "Play",
    next: active,
    reset: phase !== "idle",
    restart: phase === "done",
    size: phase !== "busy",
  };
}

export function statusText(snap) {
  const { phase, state } = snap;
  const n = state.size;
  switch (phase) {
    case "idle": return `Choose a board size and press Start.`;
    case "busy": return snap.busy === "forward" ? "Fast-forwarding to the next solution..." : "Opening search...";
    case "error": return "Stopped by an error.";
    case "done":
      return `Search complete: ${state.counts.solution} solutions in ${state.counts.events} events. Press Restart to search again.`;
    default: {
      const mode = phase === "playing" ? "Playing" : phase === "ready" ? "Ready" : "Paused";
      if (state.event?.event === "solution") return `${mode}: solution #${state.counts.solution} found on ${n}x${n}.`;
      if (!state.event) return `${mode}: ${n}x${n} search opened. Step or Play to begin.`;
      return `${mode}: ${describe(state.event)}.`;
    }
  }
}

export function errorMessage(err) {
  if (err?.kind === "network") return "Network error: cannot reach the server. Check that server.py is running, then press Start.";
  if (err?.kind === "rpc" && err.code === UNKNOWN_STREAM) {
    return "This search expired or was closed on the server (error -32020). Press Start to begin again.";
  }
  if (err?.kind === "rpc") return `Server error ${err.code}: ${err.message}.`;
  if (err?.kind === "http") return `Server returned ${err.message}.`;
  if (err?.kind === "protocol") return `Unexpected response from the server: ${err.message}.`;
  return `Unexpected error: ${err?.message ?? err}.`;
}

// ---- Player ----------------------------------------------------------------------

export class Player {
  constructor({ rpc, onChange = () => {}, schedule = (fn, ms) => setTimeout(fn, ms),
                cancel = (handle) => clearTimeout(handle), intervalMs = 250, size = 8 }) {
    this.rpc = rpc;
    this.onChange = onChange;
    this.schedule = schedule;
    this.cancel = cancel;
    this.intervalMs = intervalMs;
    this.phase = "idle";
    this.busy = null;          // "opening" | "forward" while phase is busy
    this.state = initialState(size);
    this.error = null;
    this.streamId = null;
    this.buffer = [];
    this.streamDone = false;
    this.fetching = null;
    this.timer = null;
    this.gen = 0;              // bumped by start/reset; stale async work checks it
    this.queue = Promise.resolve();
    this.requests = 0;         // queens.next calls made (for tests and the UI)
  }

  snapshot() {
    return { phase: this.phase, busy: this.busy, state: this.state, error: this.error,
             buffered: this.buffer.length, requests: this.requests };
  }

  _emit() { this.onChange(this.snapshot()); }

  // Run operations one at a time, in call order.
  _serial(fn) {
    const run = this.queue.then(fn, fn);
    this.queue = run.catch(() => {});
    return run;
  }

  _stopTimer() {
    if (this.timer !== null) { this.cancel(this.timer); this.timer = null; }
  }

  _clearStream() {
    this.streamId = null;
    this.buffer = [];
    this.streamDone = false;
    this.fetching = null;
  }

  _fail(err, gen) {
    if (gen !== this.gen || this.phase === "error") return;
    this._stopTimer();
    this.phase = "error";
    this.error = errorMessage(err);
    this._emit();
  }

  _closeQuietly(id) {
    if (id) this.rpc.close(id).catch(() => {});
  }

  // Start one queens.next unless one is already in flight.
  _refill(limit, gen) {
    if (!this.fetching) {
      this.requests += 1;
      const p = this.rpc.next(this.streamId, limit)
        .then((result) => {
          if (gen !== this.gen) return;
          if (result.events.length === 0 && !result.done) {
            throw Object.assign(new Error("empty batch from an unfinished stream"), { kind: "protocol" });
          }
          this.buffer.push(...result.events);
          if (result.done) this.streamDone = true;
        })
        .finally(() => { if (this.fetching === p) this.fetching = null; });
      this.fetching = p;
    }
    return this.fetching;
  }

  // Next buffered event; waits for a refill only when the buffer is empty,
  // and prefetches in the background once it runs low.
  async _take(limit, gen) {
    while (this.buffer.length === 0) {
      if (this.streamDone) return null;
      await this._refill(limit, gen);
      if (gen !== this.gen) return null;
    }
    const event = this.buffer.shift();
    if (this.buffer.length <= LOW_WATER && !this.streamDone && !this.fetching) {
      this._refill(limit, gen).catch((err) => this._fail(err, gen));
    }
    return event;
  }

  _finish() {
    this._stopTimer();
    this.phase = "done";
    const id = this.streamId;
    this._clearStream();
    this._closeQuietly(id); // release the server's exhausted marker
  }

  _canAdvance() {
    return this.streamId !== null && !this.state.finished && this.phase !== "error" && this.phase !== "idle";
  }

  start(size = this.state.size) {
    return this._serial(async () => {
      if (!Number.isInteger(size) || size < MIN_SIZE || size > MAX_SIZE) {
        throw new RangeError(`size must be an integer from ${MIN_SIZE} to ${MAX_SIZE}`);
      }
      this._stopTimer();
      const old = this.streamId;
      const gen = ++this.gen;
      this._clearStream();
      this._closeQuietly(old);
      this.requests = 0;
      this.state = initialState(size);
      this.error = null;
      this.phase = "busy";
      this.busy = "opening";
      this._emit();
      let id;
      try {
        id = await this.rpc.open(size);
      } catch (err) {
        this._fail(err, gen);
        return;
      }
      if (gen !== this.gen) { this._closeQuietly(id); return; }
      this.streamId = id;
      this.phase = "ready";
      this._emit();
    });
  }

  step() {
    return this._serial(async () => {
      if (!this._canAdvance()) return null;
      const gen = this.gen;
      let event;
      try {
        event = await this._take(STEP_BATCH, gen);
      } catch (err) {
        this._fail(err, gen);
        return null;
      }
      if (gen !== this.gen || !event) return null;
      this.state = applyEvent(this.state, event);
      if (this.state.finished) this._finish();
      else if (this.phase === "ready") this.phase = "paused";
      this._emit();
      return event;
    });
  }

  play() {
    if (this.phase !== "ready" && this.phase !== "paused") return;
    this.phase = "playing";
    this._emit();
    this._scheduleTick();
  }

  pause() {
    if (this.phase !== "playing") return;
    this._stopTimer();
    this.phase = "paused";
    this._emit();
  }

  togglePlay() {
    if (this.phase === "playing") this.pause();
    else this.play();
  }

  setSpeed(eventsPerSecond) {
    this.intervalMs = Math.max(1, Math.round(1000 / eventsPerSecond));
  }

  _scheduleTick() {
    this.timer = this.schedule(() => this._tick(), this.intervalMs);
  }

  async _tick() {
    this.timer = null;
    if (this.phase !== "playing") return;
    await this.step();
    if (this.phase === "playing") this._scheduleTick();
  }

  // Fast-forward in batches of FF_BATCH without drawing each step; emits
  // once when it reaches a solution (or done).
  nextSolution() {
    return this._serial(async () => {
      if (!this._canAdvance()) return null;
      this._stopTimer();
      const gen = this.gen;
      this.phase = "busy";
      this.busy = "forward";
      this._emit();
      let event = null;
      try {
        while ((event = await this._take(FF_BATCH, gen)) !== null) {
          if (gen !== this.gen) return null;
          this.state = applyEvent(this.state, event);
          if (event.event === "solution" || event.event === "done") break;
        }
      } catch (err) {
        this._fail(err, gen);
        return null;
      }
      if (gen !== this.gen) return null;
      if (this.state.finished) this._finish();
      else this.phase = "paused";
      this._emit();
      return event;
    });
  }

  // Not serialized: it must interrupt playback or a fast-forward in progress.
  async reset(size = this.state.size) {
    const id = this.streamId;
    this.gen += 1;
    this._stopTimer();
    this._clearStream();
    this.requests = 0;
    this.state = initialState(size);
    this.phase = "idle";
    this.error = null;
    this._emit();
    if (!id) return;
    try {
      await this.rpc.close(id);
    } catch (err) {
      if (err?.code !== UNKNOWN_STREAM) {
        this.error = errorMessage(err);
        this._emit();
      }
    }
  }

  // Called from pagehide: fire-and-forget close of the open stream.
  closeOnUnload() {
    if (this.streamId) {
      this.rpc.closeOnUnload(this.streamId);
      this.streamId = null;
    }
  }
}
