// View, browser side: draw the state the server describes and forward user
// actions to the controller. There is no language logic here: which actions
// are available, and why not, comes from the model through /api/state.
"use strict";

const $ = (id) => document.getElementById(id);
const workbench = $("workbench");
const sourceMenu = $("source-menu");
const loadButton = $("load-button");
const fileInput = $("file-input");
const sourceInfo = $("source-info");
const editor = $("editor");
const editorInfo = $("editor-info");
const applyButton = $("apply-button");
const discardButton = $("discard-button");
const actions = $("actions");
const actionsNote = $("actions-note");
const statusLine = $("status");
const results = $("results");
const resultsEmpty = $("results-empty");

const UNAPPLIED = "Apply or discard the changes in the editor first.";
const POLL_MILLISECONDS = 700;

let state = null;      // Last state received from the server.
let working = null;    // Label of the request in flight from this page, if any.
let pollTimer = null;

// The editor differs from the text it started from. The model makes the same
// comparison on every request; this copy only keeps the controls current
// between requests, while the user is typing.
const hasUnappliedEdits = () => state !== null && editor.value !== state.editor.base;

function setStatus(text) {
  statusLine.textContent = text;
}

function render() {
  if (state === null) return;
  const busy = working ?? (state.busy ? `${state.busy.label} is running` : null);
  const dirty = hasUnappliedEdits();
  const source = state.source;

  workbench.setAttribute("aria-busy", busy ? "true" : "false");
  sourceInfo.textContent = source
    ? `Applied source: ${source.name}, revision ${source.revision}`
    : "Applied source: none yet";
  const showsApplied = source !== null && state.editor.base === source.text;
  editorInfo.textContent = dirty
    ? `Editing ${state.editor.name}: unapplied changes. Tools use the applied source.`
    : showsApplied
      ? `Editing ${state.editor.name}: no unapplied changes.`
      : "Type a program, then choose Apply changes.";

  editor.readOnly = busy !== null;
  sourceMenu.disabled = loadButton.disabled = busy !== null || dirty;
  applyButton.disabled = busy !== null || !dirty;
  discardButton.disabled = busy !== null || !(dirty || (source !== null && !showsApplied));

  // Group the buttons by the reason they are disabled, so each reason is
  // stated once and names the buttons it applies to.
  const reasons = new Map();
  for (const action of state.actions) {
    const button = actionButton(action);
    const reason = busy ? `${busy}.` : dirty ? UNAPPLIED : action.reason;
    button.disabled = reason !== null;
    if (reason !== null) reasons.set(reason, [...(reasons.get(reason) ?? []), action.label]);
  }
  actionsNote.textContent = [...reasons]
    .map(([reason, labels]) => labels.length === state.actions.length
      ? `All actions are disabled: ${reason}`
      : `${labels.join(", ")} ${labels.length === 1 ? "is" : "are"} disabled: ${reason}`)
    .join(" ");

  resultsEmpty.textContent = state.results.length
    ? ""
    : source
      ? `No results yet for revision ${source.revision}.`
      : "No results yet.";
  results.replaceChildren(...state.results.map(resultItem));
}

function actionButton(action) {
  let button = $(`action-${action.id}`);
  if (button === null) {
    button = document.createElement("button");
    button.type = "button";
    button.id = `action-${action.id}`;
    button.textContent = action.label;
    button.setAttribute("aria-describedby", `about-${action.id}`);
    button.addEventListener("click", () => runAction(action));
    const about = document.createElement("p");
    about.id = `about-${action.id}`;
    about.textContent = action.description;
    const item = document.createElement("li");
    item.append(button, about);
    actions.append(item);
  }
  return button;
}

// Source and tool output are placed with textContent, never as markup.
function resultItem(result) {
  const item = document.createElement("li");
  item.className = `result ${result.outcome}`;
  const heading = document.createElement("h3");
  const outcome = document.createElement("span");
  outcome.className = "outcome";
  outcome.textContent = result.outcomeLabel;
  heading.append(`${result.operationLabel} · revision ${result.revision} · `, outcome);
  const output = document.createElement("pre");
  output.textContent = result.text;
  item.append(heading, output);
  return item;
}

function fillExamples() {
  for (const example of state.examples) {
    const option = document.createElement("option");
    option.value = `example:${example.key}`;
    option.textContent = example.label;
    sourceMenu.append(option);
  }
}

// Send one request to the controller and draw the state that comes back.
async function send(label, path, body, describe) {
  const focused = document.activeElement;
  working = label;
  setStatus(`Working: ${label}…`);
  render();
  try {
    const response = await fetch(path, { method: "POST", ...body });
    const reply = await response.json();
    state = reply.state;
    if (reply.status === "ok") {
      editor.value = state.editor.text;
      setStatus(describe ? describe(state) : reply.message);
    } else if (reply.status === "rejected") {
      setStatus(`Rejected: ${reply.message} The applied source is unchanged.`);
    } else {
      setStatus(`Not done: ${reply.message}`);
    }
  } catch (error) {
    setStatus("Could not reach the server. The editor text is kept; try again.");
  } finally {
    working = null;
    render();
    restoreFocus(focused);
    watchWhileBusy();
  }
}

// Controls are disabled while a request runs, which drops keyboard focus.
// Put it back on the control that was used, or on the editor if that control
// is no longer available.
function restoreFocus(previous) {
  if (document.activeElement !== document.body && document.activeElement !== null) return;
  const target = previous instanceof HTMLElement && !previous.disabled && previous !== document.body
    ? previous : editor;
  target.focus();
}

const jsonBody = () => ({
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ editorText: editor.value }),
});

function runAction(action) {
  send(`${action.label} is running`, `/api/actions/${action.id}`, jsonBody(), (next) => {
    const result = next.results[0];
    return `${result.operationLabel} finished for revision ${result.revision}: ${result.outcomeLabel}.`;
  });
}

function loadSelected() {
  const choice = sourceMenu.value;
  if (choice === "file") {
    fileInput.click();
  } else if (choice === "manual") {
    send("opening manual input", "/api/source/manual", jsonBody()).then(() => editor.focus());
  } else {
    const key = choice.slice("example:".length);
    send("loading the example", `/api/source/example/${encodeURIComponent(key)}`, jsonBody());
  }
}

function uploadChosenFile() {
  const file = fileInput.files[0];
  fileInput.value = "";
  if (!file) return;
  const form = new FormData();
  form.append("file", file);
  form.append("editorText", editor.value);
  send(`uploading ${file.name}`, "/api/source/upload", { body: form });
}

// Another page may have started an operation; follow it until it finishes.
function watchWhileBusy() {
  clearTimeout(pollTimer);
  if (state === null || state.busy === null || working !== null) return;
  pollTimer = setTimeout(async () => {
    try {
      const reply = await (await fetch("/api/state")).json();
      if (working === null) {
        state = reply.state;
        render();
      }
    } catch (error) {
      setStatus("Could not reach the server.");
    }
    watchWhileBusy();
  }, POLL_MILLISECONDS);
}

async function start() {
  try {
    const reply = await (await fetch("/api/state")).json();
    state = reply.state;
    editor.value = state.editor.text;
    fillExamples();
    setStatus("Ready.");
    render();
    watchWhileBusy();
  } catch (error) {
    setStatus("Could not reach the server. Reload the page to try again.");
  }
}

loadButton.addEventListener("click", loadSelected);
fileInput.addEventListener("change", uploadChosenFile);
editor.addEventListener("input", render);
applyButton.addEventListener("click", () =>
  send("applying changes", "/api/source/apply", jsonBody()));
discardButton.addEventListener("click", () =>
  send("discarding changes", "/api/source/discard", { method: "POST" }));

start();
