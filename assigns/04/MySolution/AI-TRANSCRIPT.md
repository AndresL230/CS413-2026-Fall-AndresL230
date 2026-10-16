# AI transcript

## Tool

Claude Code (Anthropic's command-line coding agent) running the Claude Opus
5.5 model, in one session on 2026-10-06 and 2026-10-07, plus a later,
separate session in which I asked it to explain the code. The assistant read
and wrote files in this repository, ran shell commands, and operated a Chrome
tab through a browser automation extension.

The assistant wrote the application code, the tests and the first draft of
all four documents in this directory.

The instructor's reference solution in `public/Solution04/` was already in the
repository when this work began. The assistant listed that directory's file
names while summarizing the repository, but did not open or read any of its
files.

## Prompts

These are my prompts, in order, as typed.

1. "get in sync with main and start by giving me a rundown of the next assign
   that were working on"
2. "ok help me understand the building blocks for our task at hand, i have
   specs in assign 03 i believe"
3. "I see so we are following by the assignment 4 spec then?"
4. "very well lets continue then and start implementing the spec you
   suggested"
5. "spin up the server now"
6. "fix the ui it looks very disorganized make it white cleaner edges and put more
   descriptions of what everything does"

The next three prompts were in a separate session. They are reconstructed from
memory, not quoted.

7. I asked the assistant to walk me through what each part of
   the code does: the reader, the backend adapter, the model, the controller
   and the view.
8. Follow-up questions on the backend side:
   - What does the reader do, and why parse with `ast` instead of just running
     the code?
   - What is the backend adapter for, and why does it run in a separate worker
     process?
   - How does the timeout work, and what happens when a program runs forever?
9. Follow-up questions on the rest:
   - What is the difference between the model and the controller, and why does
     the controller call the backend?
   - What is a `Ticket`, and what do `begin` and `finish` do?
   - What are the six result outcomes?
   - How do the tests work, and how do I run them?
   - What is the Flask part doing, and how does the page talk to the server?

## What the assistant suggested and did

**Prompt 1.** It completed a merge of the course repository that was already
staged, then summarized `Assign04.md`: the five operations, requirements
F1–F10, the deliverables and the grading weights. It pointed out that
Assignment 5 had starter files but no handout.

**Prompt 2.** It read my Assignment 3 requirements document and
`lambda1.py`, and proposed six building blocks: the supplied interpreter, a
restricted reader, a backend adapter, the model, the controller and the view.
It listed interpreter behaviors the adapter would have to handle:

- An unbound variable returns the value `D0V000()` instead of raising.
- Runtime failures arrive as Python exceptions.
- `D0Eif0` requires a boolean test despite its name.
- A non-terminating program needs a separate process to be stoppable.

It also mapped my Assignment 3 requirements onto Assignment 4 and listed the
ones that were dropped (persistence, test collections, a Stop button).

**Prompt 3.** It confirmed that `Assign04.md` is the specification to build
against and that my Assignment 3 document is background.

**Prompt 4.** It implemented the application in this order: contract and
reader, Lint and Interpret tools, backend adapter with a worker process,
model, controller, view and HTTP routes, then tests and documents. Design
choices it made without asking me:

- Flask as the web framework, with the model held on the server.
- The controller, not the model, calls the backend. The model issues a
  `Ticket` in `begin` and records the output in `finish`.
- The reader uses Python's `ast` module to parse the text and accepts only
  whitelisted constructor calls. Nothing is evaluated.
- Each Lint or Interpret run starts a worker process so it can be stopped at
  a 5 second limit.
- Six result outcomes, with timeout kept separate from backend failure.
- A 64 KiB source limit.

**Prompt 5.** It started the server on `127.0.0.1:8413`.

**Prompt 6.** It restyled the page with a white theme, numbered cards and
rounded edges. It also added a how-to strip, a short description under each
action button, and definitions for the source menu, Apply and Discard. The
element ids and the behavior did not change, and the tests still pass.

**Prompts 7–9.** It explained the code and did not change it.

## How the output was tested

- **Automated tests.** The assistant wrote 109 `unittest` tests alongside the
  code and ran them after each stage. All pass.
- **Clean setup.** It copied the source files to an empty directory, ran the
  setup commands from `README.md` with plain `venv` and `pip`, and ran the
  tests there. All pass on Python 3.14.7.
- **Browser smoke test.** It started the server and ran the twelve steps in
  `TESTING.md` in Chrome 154. Steps 1–11 were driven by a script in the page;
  step 12 used keyboard input only.

The smoke test found two defects in the assistant's own code that the
automated tests had missed. Both were fixed:

1. An upload was refused as "unapplied edits" whenever a multiline source was
   in the editor, because browsers send form fields with CRLF line endings.
   The model now normalizes line endings. Two regression tests were added.
2. Keyboard focus was lost after pressing Apply changes, because the button
   becomes disabled. The page now restores focus.

It also corrected its own wording in two status messages after seeing them in
the browser.

## What was not verified

- The operating system's file picker, Firefox, Safari and screen readers were
  not tested.
- Steps 2–10 of the smoke test were not repeated in the browser after the two
  fixes. The automated tests were.
- The memory limit in the worker was not tested.

## My own review

I read through all of the code the assistant wrote. I also asked it to explain
what each part of the code does (prompts 7–9 above). I used those explanations
to check my understanding of the reader, the backend adapter and the
controller before accepting them.

I reviewed the design choices the assistant made without asking. I agree with
parsing with `ast` instead of running the text, because the input never gets
executed as Python. I also agree with running each tool in a worker process,
because that is the only way to stop a program that runs forever.

Still unverified: the worker's memory limit; the operating system's file
picker, Firefox, Safari and screen readers; and smoke-test steps 2–10, which
were not repeated in the browser after the two fixes or after the restyle.

