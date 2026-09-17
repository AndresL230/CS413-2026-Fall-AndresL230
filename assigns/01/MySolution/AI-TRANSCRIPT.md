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

**Follow-up: commit and testing strategy**

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
   which also has `main0`. That file was saved unmodified as `original/queens.dats` and committed
   (`85a2bcd Add original source program`).
   - Difference noticed: `board_get` falls back to `~1` (−1) in the book, but `0` in the file.
   - `main0` prints a demo board `(0,1,2,3,4,5,6,7)`, runs `search`, then `assertloc(nsol = 92)`.

2. **Testing framework research.** ATS2 has no unit-testing framework; its own tests are
   plain programs using `assert`/`assertloc` (the original already does `assertloc(nsol = 92)`).
   Python has `unittest` in the standard library; `pytest` is not installed. The only thing the
   two languages share is stdout, so the regression check has to compare printed output.

3. **ATS2 was not installed, so the AI built it locally** (`~/.local/opt/ATS2-Postiats-gmp-0.4.2`):
   - The AUR checksum did **not** match the SourceForge download. The AI's script also did not
     stop on that failure and extracted the archive anyway, so the AI flagged this and checked the
     file before building: it matched SourceForge's published MD5
     (`930e9e11c05cde2f1041a3c58c6efb9d`, re-uploaded 2021-06-01), which is newer than the AUR
     checksum.
   - First build **failed** with GCC 16 (`implicit declaration of function` became an error).
     Fixed by building through a temporary `gcc` wrapper that adds `-std=gnu17 -fpermissive`.
   - `patsopt` and `patscc` built; the optional `myatscc` tool still fails (glibc's `bsearch`
     macro). It is not needed.

4. **Ran the original.** `patscc -DATS_MEMALLOC_LIBC -o queens queens.dats && ./queens`:
   exit 0, 1021 lines, 92 solutions, first solution matches the book.
   SHA-256 of the output: `a1941fc45db2e56714d733bc3ab14999952dbf98b80b4ad7dc83b1e96c654359`.
   Every board row ends in a **trailing space** (`"Q . . . . . . . "`).

5. **Options proposed:** (A) whole-program output comparison only, (B) whole-program output plus
   a per-function comparison against an ATS test program, (C) Python-only brute-force check.
   The user chose **B**.

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
