// DOM rendering only: turns a Player snapshot into the page. No state, no RPC.

import { boardView, controlsFor, statusText } from "./player.js";

const GLYPH = { queen: "♛", try: "♛", reject: "♛", backtrack: "♛" };

export function createRenderer(doc) {
  const $ = (id) => doc.getElementById(id);
  const el = {
    board: $("board"), status: $("status"), error: $("error"), doneBanner: $("done-banner"),
    doneText: $("done-text"), log: $("log"), solutions: $("count-solutions"),
    events: $("count-events"), requests: $("count-requests"),
    start: $("btn-start"), step: $("btn-step"), play: $("btn-play"), next: $("btn-next"),
    reset: $("btn-reset"), restart: $("btn-restart"), size: $("size"),
  };
  let cells = [];
  let boardSize = 0;
  let lastLogN = -1;

  function buildBoard(n) {
    el.board.replaceChildren();
    el.board.style.setProperty("--n", n);
    cells = [];
    for (let r = 0; r < n; r++) {
      const row = [];
      for (let c = 0; c < n; c++) {
        const cell = doc.createElement("div");
        cell.className = "cell";
        cell.dataset.shade = (r + c) % 2 ? "dark" : "light";
        cell.setAttribute("role", "gridcell");
        el.board.appendChild(cell);
        row.push(cell);
      }
      cells.push(row);
    }
    boardSize = n;
  }

  function renderBoard(state) {
    if (state.size !== boardSize) buildBoard(state.size);
    const grid = boardView(state);
    for (let r = 0; r < boardSize; r++) {
      for (let c = 0; c < boardSize; c++) {
        const classes = grid[r][c];
        const cell = cells[r][c];
        const next = classes ? `cell ${classes}` : "cell";
        if (cell.className !== next) {
          cell.className = next;
          // restart the CSS animation for the newly changed cell
          void cell.offsetWidth;
        }
        const kind = classes.split(" ")[0];
        cell.textContent = GLYPH[kind] ?? "";
        cell.setAttribute("aria-label", `row ${r}, column ${c}${classes ? ", " + classes : ""}`);
      }
    }
    el.board.classList.toggle("is-solution", state.event?.event === "solution");
    el.board.classList.toggle("is-done", state.finished);
  }

  function renderLog(state) {
    const newest = state.log.length ? state.log[state.log.length - 1].n : 0;
    if (newest === lastLogN) return;
    lastLogN = newest;
    const items = state.log.slice().reverse().map((entry) => {
      const li = doc.createElement("li");
      li.className = `log-${entry.kind}`;
      li.textContent = `#${entry.n} ${entry.text}`;
      return li;
    });
    el.log.replaceChildren(...items);
  }

  function render(snap) {
    const { phase, state } = snap;
    renderBoard(state);
    renderLog(state);
    el.status.textContent = statusText(snap);
    el.status.dataset.phase = phase;
    el.status.dataset.event = state.event?.event ?? "";
    el.solutions.textContent = String(state.counts.solution);
    el.events.textContent = String(state.counts.events);
    el.requests.textContent = String(snap.requests);
    el.error.hidden = !snap.error;
    el.error.textContent = snap.error ?? "";
    el.doneBanner.hidden = phase !== "done";
    el.doneText.textContent = `Search complete: no more solutions. Found ${state.counts.solution} in ${state.counts.events} events.`;

    const ctl = controlsFor(phase);
    el.start.disabled = !ctl.start;
    el.step.disabled = !ctl.step;
    el.play.disabled = !ctl.play;
    el.play.textContent = ctl.playLabel;
    el.play.setAttribute("aria-pressed", String(phase === "playing"));
    el.next.disabled = !ctl.next;
    el.reset.disabled = !ctl.reset;
    el.restart.disabled = !ctl.restart;
    el.size.disabled = !ctl.size;
  }

  return { render };
}
