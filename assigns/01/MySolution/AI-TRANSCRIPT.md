# AI Transcript — Assignment #1

## AI system used

- **Tool:** Claude Code (Anthropic's CLI coding agent), running locally in this repository.
- **Model:** Claude Opus 5 (`claude-opus-5`).
- **Process aid:** the Claude Code "brainstorming" skill (the AI proposes options, the user
  approves each design section before anything is built).

---

## Session 1 — 2026-09-17: source program, toolchain, test design

### Prompts (verbatim)

**Initial prompt**

> so did you read the readme, clone that in here the source program and explain to me what it
> is and does, keep one directory for the original source program and create another one for
> ours to keep them seperated

**Follow-up: testing strategy**

> yes, add it and help me figure out a testing framework that this may or may not have and to
> see if we can somehow use or create a testing framework to ensure no regression between this
> version of the code and the one that will be translated into python

**Answer to the AI's question on how to install ATS2**

> Build locally, no sudo (Recommended)

**Choosing the test approach**

> lets go with option B, the whole-program output plus the per-function comparison

**Design approvals**

> yes this looks right   *(Section 1: layout and workflow)*

> yeah   *(Section 2: test cases and output format)*

### What the AI did and found

1. **Got the complete source, not just the book's code excerpts.** The book section shows
   the code in pieces; it links to the full file `CODE/CHAP_FUNCTION/queens.dats` (193 lines),
   which also has `main0`. That file was saved unmodified as `original/queens.dats`.
   - Difference noticed: `board_get` falls back to `~1` (−1) in the book, but `0` in the file.
   - `main0` prints a demo board `(0,1,2,3,4,5,6,7)`, runs `search`, then `assertloc(nsol = 92)`.

2. **Testing framework research.** ATS2 has no unit-testing framework; its own tests are
   plain programs using `assert`/`assertloc` (the original already does `assertloc(nsol = 92)`).
   Python has `unittest` in the standard library; `pytest` is not installed. The only thing the
   two languages share is stdout, so the regression check has to compare printed output.

3. **ATS2 was not installed, so the AI built it locally**, the way the user asked (no root).
   Two snags, both written up in `README.md`: a checksum that didn't match the download, and a
   build failure under GCC 16. **AI mistake:** its install script did not stop when the checksum
   failed and unpacked the archive anyway. The AI flagged that and verified the file separately
   before building.

4. **Ran the original.** `patscc -DATS_MEMALLOC_LIBC -o queens queens.dats && ./queens`:
   exit 0, 1021 lines, 92 solutions, first solution matches the book. Every board row ends in a
   **trailing space** (`"Q . . . . . . . "`), which later turned out to be the detail a Python
   translation is most likely to lose.

5. **Options proposed, user chose.** (A) whole-program output comparison only, (B) whole-program
   output plus a per-function comparison against an ATS test program, (C) Python-only brute-force
   check. The user chose **B**, and every later decision was built on that choice.

6. **Throwaway probes found behaviors a translation could get wrong:**
   - A test program can `#include` a copy of `queens.dats` with `main0` removed, so the original
     file never has to be edited.
   - `search` does **not** stay inside a partly filled board: `search(zeros, 1, 0, 0)` returns
     **92**, because it backs up into row 0 and keeps going.
   - `println!("label", f(x))` in ATS prints `label` *before* `f` runs; Python's
     `print("label", f(x))` runs `f` first. The test programs must call functions on their own line.
   - AI mistake in its probe code: `print (if b then "true" else "false")` doesn't compile
     (ATS can't tell which `print` is meant); fixed with `print_string`.
   - Anticipated translation risk: `search` is tail-recursive, which ATS compiles into a loop.
     Python doesn't do that and stops after 1,000 nested calls by default, so a literal
     translation will likely crash with `RecursionError`.

### Manual changes made after reviewing AI output

None yet (no translation exists yet).

---

## Session 2 — 2026-09-17: building the test harness

### Prompts (verbatim)

**Starting the implementation**

> continue on this on the implementation part now

### What the AI did and found

1. **Picked up the approved design from session 1.** Sections 1 and 2 had been approved.
   Section 3 (failure reports and recording results) had been presented but not explicitly
   approved; the AI took "continue on the implementation part" as the go-ahead and built it as
   presented.

2. **Dropped a test idea from session 1, with a reason.** Session 1 suggested a case checking
   that `board_set` doesn't change its input board. In Python that can only happen if the board
   is a list: a tuple can't be changed. So instead the Python test program requires every board
   the translation returns to be a **tuple of 8 ints**, like the ATS `int8` tuple, and prints
   `<not a board ...>` for anything else.

3. **A probe found how ATS resolves `#include`.** The path is resolved from the directory the
   compiler runs in, not from the including file, and `patscc` writes its generated C file into
   that same directory. The first probe failed with `the file [../../build/queens_lib.dats] is
   not available for inclusion`. So the Makefile compiles both ATS programs from inside `build/`.

4. **Built the harness** the user had approved (see `TESTING.md`): `Makefile`,
   `tests/ats/cases.dats`, `tests/py/cases.py`, `tests/test_regression.py`, and the saved ATS
   output in `tests/expected/`. Each case's `###` header is generated from the real arguments in both
   languages, so a header can't disagree with the call it describes.

5. **Checked the ATS output against the approved table.** Every value matched, and
   `queens.out` has the same SHA-256 as in session 1. **Correction of the AI's own estimate:**
   session 1 said `cases.out` would print 418 solutions (about 4,600 lines). It prints **510**
   (5,702 lines); the estimate had left out R4's 92 solutions.

6. **Tested the harness itself** against deliberately broken stand-ins in a scratch directory
   (table in `TESTING.md`). This found a **bug in the AI's own report code**: the whole-program
   diff was cut to a window before diffing, so its `@@` line numbers counted from the window
   instead of the file (`@@ -1,43` for a difference at line 501). Fixed by diffing the whole
   output and cutting the printed diff instead (`@@ -498,...`).

7. **`make test` fails, as it should.** There's no translation yet, so both tests fail with
   `translation not found: translation/queens.py does not exist`.

### Manual changes made after reviewing AI output

None yet (no translation exists yet).

---

## Session 2, continued — 2026-09-18: translation, review and fixes

### Prompts (verbatim)

**Checking the test programs**

> we have both the python and ats test cses that are both running?

**Starting the translation**

> right yeah lets build the translation now mimicing the overall function and purpose of
> everything in the original program and testing with our test suite as you go through

**The translation prompt.** By this point the AI in this session knew the traps it had built tests
for (trailing spaces, the recursion limit, out-of-range rows), so a translation written by it
wouldn't show what an AI gets wrong on its own. It gave the job to a **fresh subagent** (Claude
Opus 5, no memory of this session). That subagent was told not to open any files, so it never saw
`tests/` or `TESTING.md`. It received this message, followed by the complete `queens.dats`:

> Do not read, write, or run any files or commands. Everything you need is in this message. Reply
> with the complete Python file in one \`\`\`python code block and nothing else after it.
>
> Request from the user:
>
> "Translate the ATS2 program below (queens.dats, an eight-queens solver) into Python 3, mimicking
> the overall function and purpose of everything in the original program. Preserve the behavior of
> the original program as closely as possible, including exactly what it prints. Keep the same
> function names and parameters (print_dots, print_row, print_board, board_get, board_set,
> safety_test1, safety_test2, search), and put what main0 does under
> `if __name__ == "__main__":` so the file can be imported without running it. The file will be
> saved as translation/queens.py."
>
> The original program, queens.dats: *(the full 193-line file)*

The function names and the `__main__` guard were added to the user's wording because the test programs
import the translation and call its functions.

### What the AI did and found

1. **Answer to "are both running?": not yet.** The ATS test program ran and matched its saved
   output. The Python one couldn't run, because it imports `translation/queens.py`, which didn't
   exist yet. As a partial check, it was run in a scratch directory against hand-written helper
   functions (no `search`). Its output for the 28 cases P1–T8 was byte-identical to the ATS output.

2. **The first draft passed tests 1 and 2 on its first run** and was saved unedited. It got right
   everything the test design had worried about: trailing spaces, `0` for out-of-range rows,
   tuples as boards, and `search` backing up past its starting row. It also rewrote the three
   tail-recursive functions as loops, explaining that Python has no tail-call elimination. The
   reviewing AI checked that claim: the full search makes over 15,000 tail calls, and a literal
   recursive version crashes with `RecursionError`.

3. **The review looked for behavior the tests didn't cover, and found two differences:**
   - **A made-up error message.** For the `assertloc(nsol = 92)` check, the draft printed
     `exit(ATS): [assertloc] failed: queens.py: nsol = 92`. ATS never prints that. Running a copy of
     the original with the check changed to 93, and reading ATS2's C runtime, showed that
     `assertloc` prints only the source location, with no newline, and exits with code 1.
   - **Closed output pipe.** With `| head -2`, the ATS program stops quietly (SIGPIPE, exit 141).
     The draft printed a `BrokenPipeError` traceback and exited with code 120, because Python
     ignores SIGPIPE by default.

4. **Tests first, then fixes**, following the user's instruction to test with the suite while
   building. The AI added tests 3 and 4 to `tests/test_regression.py`, ran them
   on the unedited draft, and both failed for the reasons above. Only then was the translation
   changed. **AI mistake caught before it mattered:** the first version of test 3 matched the
   file path with `\S*`, which would have rejected this repository's path because it contains
   spaces (`Fall 2026/CS 413`). It was fixed before the corrected translation was tested.

5. **Kept as is, with reasons** (details in `TESTING.md`, "Review of the AI translation"): the
   eight explicit `print_row` calls, and `search` updating all four variables in one assignment
   per branch. The one-step update is what keeps the backing-up step correct.

### Corrections made after reviewing the AI output

These came out of the direction the user set for this step: make the translation mimic everything
the original does, and test it against the suite while building it. Working to that instruction,
the AI reported each difference it found and then made the change; the user decided what the
translation had to match and did not hand-edit code.

1. Added an `assertloc(cond)` helper that works like ATS's: it prints the caller's file and line
   with no newline, exits with code 1, and isn't removed by `python -O`. `main0` now ends with
   `assertloc(nsol == 92)`, like the original.
2. In the `__main__` block only, restored default SIGPIPE handling, so the program stops quietly
   like the ATS one when its output is closed. Importing the file doesn't change signal handling.
3. Made `translation/queens.py` executable, since the AI's draft starts with `#!/usr/bin/env python3`.

After these, `make test` passes all 4 tests.
