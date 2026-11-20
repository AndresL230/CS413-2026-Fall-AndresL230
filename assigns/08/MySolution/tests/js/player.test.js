// node --test: the playback state module (static/player.js) with a fake
// server and fake timers. Covers incremental fetching, the controls'
// behavior, done vs solution, reset/close, and visible RPC failures.

import { test } from "node:test";
import assert from "node:assert/strict";

import {
  FF_BATCH, LOG_LIMIT, LOW_WATER, STEP_BATCH, Player, applyEvent, attackerOf,
  boardView, controlsFor, describe, initialState, statusText,
} from "../../static/player.js";
import { RpcClient } from "../../static/rpc.js";
import { FakeServer, FakeTimers, flush, referenceTrace } from "./fakes.js";

function setup(size = 8) {
  const server = new FakeServer();
  const timers = new FakeTimers();
  const snaps = [];
  const player = new Player({
    rpc: new RpcClient({ fetch: server.fetch }),
    onChange: (s) => snaps.push(s),
    schedule: timers.schedule, cancel: timers.cancel, size,
  });
  return { server, timers, snaps, player };
}

const nextLimits = (server) => server.callsTo("queens.next").map((c) => c.request.params.limit);

// ---- Pure helpers ----------------------------------------------------------------

test("attackerOf finds same-column and both diagonals, nearest row first", () => {
  assert.deepEqual(attackerOf(0, 1, [0]), { row: 0, column: 0 });           // same column
  assert.deepEqual(attackerOf(1, 1, [0]), { row: 0, column: 0 });           // diagonal
  assert.deepEqual(attackerOf(1, 1, [2]), { row: 0, column: 2 });           // other diagonal
  assert.deepEqual(attackerOf(2, 2, [2, 3]), { row: 1, column: 3 });        // nearest row wins
  assert.deepEqual(attackerOf(2, 2, [0, 5]), { row: 0, column: 0 });        // two rows up
  assert.equal(attackerOf(2, 1, [0]), null);                                // safe
});

test("applyEvent is pure and tracks board, counts, attacker, and done", () => {
  const s0 = initialState(4);
  const reject = { event: "reject", column: 1, row: 1, board: [0] };
  const s1 = applyEvent(s0, reject);
  assert.deepEqual(s0, initialState(4));
  assert.deepEqual(s1.board, [0]);
  assert.deepEqual(s1.attacker, { row: 0, column: 0 });
  assert.equal(s1.counts.reject, 1);
  assert.equal(s1.counts.events, 1);
  const s2 = applyEvent(s1, { event: "done" });
  assert.equal(s2.finished, true);
  assert.deepEqual(s2.board, []);
});

test("boardView gives each event kind a distinct look", () => {
  const at = (ev, prev = initialState(4)) => boardView(applyEvent(prev, ev));
  assert.equal(at({ event: "try", column: 1, row: 1, board: [3] })[1][1], "try");
  assert.equal(at({ event: "place", column: 1, row: 1, board: [3, 1] })[1][1], "queen placed");
  const rejected = at({ event: "reject", column: 0, row: 1, board: [0] });
  assert.equal(rejected[1][0], "reject");
  assert.equal(rejected[0][0], "queen attacker");                     // the conflicting queen
  assert.equal(at({ event: "backtrack", column: 1, row: 1, board: [3] })[1][1], "backtrack");
  const solved = at({ event: "solution", board: [1, 3, 0, 2] });
  assert.deepEqual([solved[0][1], solved[1][3], solved[2][0], solved[3][2]], Array(4).fill("queen solution"));
});

test("describe names the attacker for rejects", () => {
  assert.equal(describe({ event: "reject", column: 1, row: 1, board: [0] }),
    "reject row 1, col 1 (attacked by row 0, col 0)");
});

test("controls and status distinguish done from a solution", () => {
  const done = controlsFor("done");
  assert.equal(done.restart, true);
  assert.equal(done.step || done.play || done.next, false);
  assert.equal(controlsFor("paused").restart, false);
  const solution = applyEvent(initialState(4), { event: "solution", board: [1, 3, 0, 2] });
  assert.match(statusText({ phase: "paused", state: solution }), /solution #1/);
  const finished = applyEvent(solution, { event: "done" });
  assert.match(statusText({ phase: "done", state: finished }), /Search complete/);
  assert.doesNotMatch(statusText({ phase: "done", state: finished }), /solution #/);
});

// ---- Incremental fetching ------------------------------------------------------------

test("start opens a stream without fetching any events", async () => {
  const { server, player } = setup();
  await player.start(8);
  assert.equal(player.phase, "ready");
  assert.deepEqual(server.callsTo("queens.open")[0].request.params, { size: 8 });
  assert.equal(server.callsTo("queens.next").length, 0);
});

test("step applies events in order and only fetches small batches when low", async () => {
  const { server, player } = setup();
  const trace = referenceTrace(8);
  await player.start(8);
  for (let i = 0; i < 40; i++) {
    const ev = await player.step();
    assert.deepEqual(ev, trace[i]);
    await flush();
    assert.ok(player.buffer.length <= LOW_WATER + STEP_BATCH);
  }
  assert.ok(nextLimits(server).every((l) => l === STEP_BATCH));
  const served = server.eventsServed();
  assert.ok(served <= 40 + LOW_WATER + STEP_BATCH, `pulled ${served} events for 40 steps`);
  assert.ok(served < trace.length / 100);  // nowhere near the whole trace
});

test("no refill while the buffer is above the low-water mark", async () => {
  const { server, player } = setup();
  await player.start(8);
  await player.step();            // first fetch: 16 events, 15 left
  await flush();
  const before = server.callsTo("queens.next").length;
  for (let i = 0; i < STEP_BATCH - 1 - LOW_WATER - 1; i++) await player.step();
  await flush();
  assert.equal(server.callsTo("queens.next").length, before);
  assert.equal(before, 1);
});

// ---- Play / pause / speed ---------------------------------------------------------------

test("play advances on the timer, pause stops it, speed sets the interval", async () => {
  const { server, timers, player } = setup();
  await player.start(8);
  player.setSpeed(20);
  player.play();
  assert.equal(player.phase, "playing");
  assert.equal(timers.count, 1);
  assert.equal(timers.delays.at(-1), 50);
  await timers.fire();
  await timers.fire();
  assert.equal(player.state.counts.events, 2);
  player.pause();
  assert.equal(player.phase, "paused");
  assert.equal(timers.count, 0);
  const pulled = server.eventsServed();
  await flush();
  assert.equal(player.state.counts.events, 2);
  player.togglePlay();
  assert.equal(player.phase, "playing");
  assert.ok(server.eventsServed() >= pulled);
});

test("playing to the end reaches done, stops the timer, and closes the stream", async () => {
  const { server, timers, player } = setup(4);
  await player.start(4);
  player.setSpeed(60);
  player.play();
  while (timers.count) await timers.fire();
  assert.equal(player.phase, "done");
  assert.equal(player.state.counts.solution, 2);
  assert.equal(player.state.counts.events, referenceTrace(4).length);
  await flush();
  assert.equal(server.callsTo("queens.close").length, 1);
  assert.equal(server.streams.size, 0);
  assert.equal(await player.step(), null);   // nothing more to do after done
});

// ---- Next solution ------------------------------------------------------------------------

test("next solution fast-forwards in batches of 32 and draws once", async () => {
  const { server, snaps, player } = setup();
  await player.start(8);
  const before = snaps.length;
  const ev = await player.nextSolution();
  assert.deepEqual(ev, { event: "solution", board: [0, 4, 7, 5, 2, 6, 1, 3] });
  assert.equal(player.state.counts.solution, 1);
  assert.equal(player.phase, "paused");
  assert.ok(nextLimits(server).every((l) => l === FF_BATCH));
  // one "busy" snapshot plus one final snapshot: intermediate steps not drawn
  assert.deepEqual(snaps.slice(before).map((s) => s.phase), ["busy", "paused"]);
  assert.equal(snaps.at(-1).state.event.event, "solution");
  const firstIndex = referenceTrace(8).findIndex((e) => e.event === "solution");
  assert.equal(player.state.counts.events, firstIndex + 1);
  assert.ok(server.eventsServed() <= firstIndex + 1 + FF_BATCH + LOW_WATER + FF_BATCH);
});

test("next solution twice gives the second solution", async () => {
  const { player } = setup(4);
  await player.start(4);
  await player.nextSolution();
  const second = await player.nextSolution();
  assert.deepEqual(second.board, [2, 0, 3, 1]);
  assert.equal(player.state.counts.solution, 2);
});

test("next solution that runs into done shows done, not a solution", async () => {
  const { snaps, player } = setup(4);
  await player.start(4);
  await player.nextSolution();
  await player.nextSolution();
  const last = await player.nextSolution();       // no third 4x4 solution
  assert.deepEqual(last, { event: "done" });
  assert.equal(player.phase, "done");
  assert.equal(player.state.counts.solution, 2);
  assert.equal(snaps.at(-1).phase, "done");
  assert.match(statusText(snaps.at(-1)), /Search complete/);
});

test("next solution pauses playback first", async () => {
  const { timers, player } = setup();
  await player.start(8);
  player.play();
  await player.nextSolution();
  assert.equal(timers.count, 0);
  assert.equal(player.phase, "paused");
});

// ---- Reset, restart, leaving the page --------------------------------------------------------

test("reset closes the stream and clears the board", async () => {
  const { server, player } = setup();
  await player.start(8);
  await player.step();
  const id = server.callsTo("queens.open").length && [...server.streams.keys()][0];
  await player.reset();
  assert.equal(player.phase, "idle");
  assert.deepEqual(player.state, initialState(8));
  assert.deepEqual(server.callsTo("queens.close").map((c) => c.request.params.stream_id), [id]);
  assert.equal(server.streams.size, 0);
});

test("reset during a fast-forward stops it", async () => {
  const { server, player } = setup();
  await player.start(8);
  await player.nextSolution();               // advance a little first
  const release = server.hold();
  const ff = player.nextSolution();
  await flush();
  assert.equal(player.phase, "busy");        // mid fast-forward, a fetch in flight
  assert.equal(server.callsTo("queens.next").at(-1).request.params.limit, FF_BATCH);
  const resetting = player.reset();
  release();
  await resetting;
  assert.equal(await ff, null);
  await flush();
  assert.equal(player.phase, "idle");
  assert.equal(player.state.counts.events, 0); // the late batch was discarded
  assert.equal(player.buffer.length, 0);
});

test("restart after done opens a fresh stream and resets the counters", async () => {
  const { server, player } = setup(4);
  await player.start(4);
  while (player.phase !== "done") await player.nextSolution();
  assert.ok(player.requests > 0);
  await player.start(4);
  assert.equal(player.phase, "ready");
  assert.equal(player.requests, 0);
  assert.equal(player.state.counts.events, 0);
  assert.equal(server.callsTo("queens.open").length, 2);
  assert.deepEqual(await player.step(), referenceTrace(4)[0]);
});

test("start while a stream is open closes the old one", async () => {
  const { server, player } = setup();
  await player.start(8);
  await player.start(6);
  await flush();
  assert.equal(server.callsTo("queens.close").length, 1);
  assert.equal(server.streams.size, 1);
  assert.equal(player.state.size, 6);
});

test("closeOnUnload closes the open stream with a keepalive notification", async () => {
  const { server, player } = setup();
  await player.start(8);
  player.closeOnUnload();
  await flush();
  const close = server.callsTo("queens.close")[0];
  assert.equal(close.init.keepalive, true);
  assert.equal(server.streams.size, 0);
});

// ---- Visible failures ------------------------------------------------------------------------

test("network failure during step shows an error and stops playback", async () => {
  const { server, timers, snaps, player } = setup();
  await player.start(8);
  player.play();
  server.failure = "network";
  await timers.fire();
  assert.equal(player.phase, "error");
  assert.match(player.error, /Network error/);
  assert.equal(timers.count, 0);
  assert.equal(snaps.at(-1).phase, "error");
  assert.deepEqual(controlsFor("error").step, false);
});

test("expired stream (-32020) shows a restart hint", async () => {
  const { server, player } = setup();
  await player.start(8);
  server.streams.clear();                  // the server forgot the stream
  await player.step();
  assert.equal(player.phase, "error");
  assert.match(player.error, /-32020/);
  assert.match(player.error, /Start/);
});

test("failure on open is shown", async () => {
  const { server, player } = setup();
  server.failure = "http";
  await player.start(8);
  assert.equal(player.phase, "error");
  assert.match(player.error, /502/);
});

test("failure during a fast-forward is shown", async () => {
  const { server, player } = setup();
  await player.start(8);
  server.failure = { code: -32603, message: "Internal error" };
  assert.equal(await player.nextSolution(), null);
  assert.equal(player.phase, "error");
  assert.match(player.error, /-32603/);
});

test("a failed close on reset is reported", async () => {
  const { server, player } = setup();
  await player.start(8);
  server.failure = "network";
  await player.reset();
  assert.equal(player.phase, "idle");
  assert.match(player.error, /Network error/);
});

test("the event log is capped", async () => {
  let state = initialState(8);
  for (const ev of referenceTrace(6).slice(0, LOG_LIMIT + 50)) state = applyEvent(state, ev);
  assert.equal(state.log.length, LOG_LIMIT);
  assert.equal(state.log.at(-1).n, LOG_LIMIT + 50);
});
