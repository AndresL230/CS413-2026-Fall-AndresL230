# Testing

The Python translation (`translation/queens.py`) is tested against the ATS original
(`original/queens.dats`) by comparing what the two programs **print**, byte for byte. Printed
output is the only thing the two languages share, so it is what gets compared.

There are four tests:

1. **Whole program.** `translation/queens.py` must print exactly what the compiled original prints:
   the demo board, then all 92 solutions (1,021 lines).
2. **Function by function.** An ATS test program (`tests/ats/cases.dats`) calls the original's
   own functions with a table of inputs and prints one block per case. A Python test program
   (`tests/py/cases.py`) calls the translation's functions with the same inputs and must print the
   same bytes. This covers normal, boundary and unusual inputs that the fixed-input program never
   uses by itself.
3. **Failed count check.** `main0` ends with `assertloc(nsol = 92)`, which never fails in a normal
   run. The test makes `search` report one fewer solution. The program must still print the full
   normal output, then write only the location of the check to stderr, and exit with code 1.
4. **Closed output pipe.** If nobody reads the output (for example after `| head` has quit), the
   program must be stopped by the SIGPIPE signal without printing an error.

Tests 3 and 4 were added after reviewing the AI's translation, which had both behaviors wrong.
They check paths the ATS original can't reach without being edited, so its behavior on them was
checked by hand (see [Checks done by hand](#checks-done-by-hand-on-the-ats-side)).

## How to run

From `MySolution/`:

| Command | Needs | What it does |
|---|---|---|
| `make test` | `python3` | Runs all four tests (`python3 -m unittest discover -s tests -v`). |
| `make expected` | ATS2 | Rebuilds the saved ATS output in `tests/expected/`. |
| `make run-original` | ATS2 | Compiles and runs the original. |
| `make run-translation` | `python3` | Runs the translation. |
| `make clean` | | Deletes `build/`. |

The ATS output is saved in `tests/expected/` and committed, so `make test` needs only
`python3`. `make expected` only has to be run again if the ATS side changes. The Makefile
looks for ATS2 in `$PATSHOME`, which defaults to `~/.local/opt/ATS2-Postiats-gmp-0.4.2`.

**Environment used:** Linux (CachyOS), GCC 16.2.1, Python 3.14.7, ATS2-Postiats 0.4.2
built from source. ATS2's own C code needed `-std=gnu17 -fpermissive` to build under GCC 16,
but the programs here compile with the plain system `gcc`.

## Layout

```
MySolution/
├── original/queens.dats        the ATS original, never edited
├── translation/queens.py       the Python translation
├── tests/
│   ├── ats/cases.dats          ATS test program: the original's functions on each case
│   ├── py/cases.py             Python test program: the same cases on the translation
│   ├── expected/queens.out     saved output of the original
│   ├── expected/cases.out      saved output of tests/ats/cases.dats
│   └── test_regression.py      the four unittest tests
├── build/                      compiled files (ignored by git)
├── Makefile
└── TESTING.md
```

**Using the original's functions without editing it.** `make expected` writes a copy of
`original/queens.dats` without `main0` to `build/queens_lib.dats` (using `sed`, then checks
that `main0` is gone). `cases.dats` includes that copy. ATS resolves `#include` paths from the
directory the compiler runs in, not from the including file, so both programs are compiled
from inside `build/`.

**How the Python side imports the translation.** `cases.py` imports `translation/queens.py`
as the module `queens`. This requires the translation to keep the original's function names
and arguments, and to run its main program only under `if __name__ == "__main__":`.

## Output format of the case programs

```
### G2 board_get((0, 4, 7, 5, 2, 6, 1, 3), 8)
=> 0
### P2 print_dots(3)
. . . 
=> ()
```

- Each case starts with `### <id> <call>`. The call is built from the real arguments, in Python
  syntax (`-1`, not ATS's `~1`).
- Next comes whatever the function printed, then `=> <return value>`.
- Return values: `true`/`false` for booleans, `()` for no value (ATS `void`, Python `None`),
  and `(a, b, c, d, e, f, g, h)` for a board.
- `print_dots` never ends its line, so its runner adds a newline after it. P1 and P3 therefore
  show an empty line, meaning "printed nothing".
- The function is called in its own statement *before* anything about its result is printed.
  This matters because ATS's `println!("label", f(x))` prints `label` before `f` runs, while
  Python's `print("label", f(x))` runs `f` first. With the call on its own line, both languages
  produce the same order.
- The Python side checks return **types** too. It expects `int`, `bool`, `None`, and a **tuple**
  of 8 ints for a board, because the ATS board type `int8` is an immutable tuple. Anything else
  prints as `<not a ...: value>`, so it can never match by accident.

## Test cases

`sol1 = (0, 4, 7, 5, 2, 6, 1, 3)` is Solution #1. `zeros = (0, 0, 0, 0, 0, 0, 0, 0)`.
Every expected value below comes from running the real ATS functions (`tests/expected/cases.out`).

| ID | Call | ATS result | Type | What it checks |
|---|---|---|---|---|
| P1 | `print_dots(0)` | prints nothing | boundary | zero dots |
| P2 | `print_dots(3)` | `. . . ` | normal | each dot is `". "`, trailing space included |
| P3 | `print_dots(-3)` | prints nothing | unusual | negative count is treated like 0 (`if i > 0`) |
| P4 | `print_row(0)` | `Q . . . . . . . ` | boundary | queen in the first column |
| P5 | `print_row(7)` | `. . . . . . . Q ` | boundary | queen in the last column, trailing space after `Q` |
| P6 | `print_board(sol1)` | 8 rows, then a blank line | normal | full board layout |
| G1.0–G1.7 | `board_get(sol1, i)`, i = 0…7 | `0 4 7 5 2 6 1 3` | normal | every position is read correctly |
| G2 | `board_get(sol1, 8)` | `0` | boundary | row past the end gives `0` (the book's version gives `-1`) |
| G3 | `board_get(sol1, -1)` | `0` | boundary | negative row gives `0`, not Python's `bd[-1]` = last item |
| S1 | `board_set(sol1, 3, 6)` | `(0, 4, 7, 6, 2, 6, 1, 3)` | normal | changes only position 3 |
| S2 | `board_set(sol1, 7, 0)` | `(0, 4, 7, 5, 2, 6, 1, 0)` | boundary | last position |
| S3 | `board_set(sol1, 8, 5)` | `sol1` unchanged | boundary | row past the end is ignored |
| S4 | `board_set(sol1, -1, 5)` | `sol1` unchanged | boundary | negative row is ignored, not Python's `bd[-1]` |
| T1 | `safety_test1(0, 0, 1, 2)` | `true` | normal | a knight's move apart is safe |
| T2 | `safety_test1(0, 3, 5, 3)` | `false` | normal | same column |
| T3 | `safety_test1(2, 2, 5, 5)` | `false` | normal | same diagonal |
| T4 | `safety_test1(5, 1, 2, 4)` | `false` | unusual | other diagonal with rows in reverse order (needs `abs`) |
| T5 | `safety_test1(3, 3, 3, 3)` | `false` | unusual | a queen against its own square |
| T6 | `safety_test2(7, 3, sol1, 6)` | `true` | normal | the last queen of a real solution is safe against all rows above |
| T7 | `safety_test2(3, 4, sol1, 2)` | `false` | normal | clashes with row 1 (same column) |
| T8 | `safety_test2(0, 5, zeros, -1)` | `true` | boundary | no earlier rows to check |
| R1 | *(the whole program)* | 92 solutions | normal | the full search from `main0`, checked by test 1 |
| R2 | `search(zeros, 0, 8, 0)` | `0` | boundary | column already past the end in row 0: stops at once |
| R3 | `search(zeros, 0, 7, 10)` | `14` | unusual | the count starts at 10: labels run `Solution #11`…`#14` |
| R4 | `search(zeros, 1, 0, 0)` | `92` | unusual | starting in row 1, it backs up into row 0 and finishes the whole board |
| R5.0–R5.7 | `search(zeros, 0, c, 0)`, c = 0…7 | `92 88 80 64 46 28 12 4` | own design | see below |

**R5, the case of our own design.** `search(zeros, 0, c, 0)` counts the solutions whose
first queen is in column `c` **or further right**. Subtracting neighbouring results gives the
number of solutions for each column of the first queen:

| First-queen column | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | Total |
|---|---|---|---|---|---|---|---|---|---|
| `search(zeros, 0, c, 0)` | 92 | 88 | 80 | 64 | 46 | 28 | 12 | 4 | |
| Solutions in column `c` | 4 | 8 | 16 | 18 | 18 | 16 | 8 | 4 | 92 |

The counts add up to 92 and read the same from both ends, as the board's left-right mirror
symmetry requires. So this case checks that the search is *correct*, not only that the two
versions agree.

**Size:** the search cases print 510 solutions, so `cases.out` is 5,702 lines. Every one of
those boards also re-tests the printing functions.

## Behaviors a translation could get wrong

These came up while designing the tests, and each one is covered by a case:

- **Trailing spaces.** Every board row ends in a space (`"Q . . . . . . . "`), because each
  square prints as `"Q "` or `". "`. A translation using `" ".join(...)` looks the same on
  screen but fails the byte comparison (P2, P4–P6, every solution).
- **Out-of-range rows.** `board_get` returns `0` and `board_set` returns the board unchanged.
  A translation using Python indexing would treat `-1` as the last position, or raise
  `IndexError` for `8` (G2, G3, S3, S4).
- **`search` backs up past where it started.** When a row runs out of columns, `search` moves
  back to the previous row, even below the row it was called with (R4).
- **Recursion depth.** `search` and `safety_test2` call themselves as their last step, and
  ATS compiles such calls into loops. Python doesn't, and by default it stops after about 1,000
  nested calls. A direct translation of `search` will crash with `RecursionError` on the full
  run (R1, R4, R5).
- **Board type.** The ATS board is an immutable tuple, so `board_set` returns a new board and
  never changes its input. A Python tuple behaves the same way. With a list, `board_set` could
  change the caller's board, so the tests require a tuple (S1–S4).

These two were found while reviewing the AI's translation (tests 3 and 4):

- **The failed-check message.** ATS's `assertloc` prints only the location of the check (file,
  line and character offsets, with no newline) and exits with code 1. It does not print a
  message like `assertion failed`. Python's `assert` would print a traceback instead, and
  `python -O` removes it entirely.
- **A closed output pipe.** A compiled C program is stopped by SIGPIPE (shell exit code 141)
  and prints nothing. Python ignores SIGPIPE by default, so it raises `BrokenPipeError`, prints a
  traceback, and exits with code 120.

## Checks done by hand on the ATS side

Tests 3 and 4 have no saved ATS output to compare with, because the original can't take those
paths without being edited. So what the original does was checked once, by hand:

| Check | ATS original | Python, AI's draft | Python, reviewed |
|---|---|---|---|
| Count check fails (ATS: a `build/` copy with `nsol = 93`; Python: `search` patched to return one fewer) | stdout same as the normal run; stderr is only `…/queens_bad.dats: 4650(line=187, offs=18) -- 4671(line=187, offs=39)`, no newline; exit 1 | stdout same; stderr `exit(ATS): [assertloc] failed: queens.py: nsol = 92` plus a newline, a message ATS never prints; exit 1 | stdout same; stderr `…/translation/queens.py: line 167`, no newline; exit 1 |
| Output pipe closed before the program starts | stopped by SIGPIPE, stderr empty | exit 120, 730 bytes of `BrokenPipeError` traceback on stderr | stopped by SIGPIPE, stderr empty |
| `… \| head -2` in a shell | exit 141, no message | traceback, exit 120 | exit 141, no message |

The ATS message is printed by `atspre_assert_errmsg_bool` in ATS2's
`prelude/CATS/basics.cats` (`fprintf(stderr, "%s", msg); exit(1);`). The Python version can't be
byte-identical here, because it names a different file and Python has no character offsets, so
test 3 checks the shape of the message: one line naming `queens.py` and a line number.

## Review of the AI translation

The AI's first draft (`translation/queens.py` in commit `ff3be27`, "Add initial AI-generated translation")
passed tests 1 and 2 on its first run. It was then reviewed against the assignment's checklist:

| Checklist item | Finding |
|---|---|
| Incorrect syntax | None. |
| Incorrect interpretation | The failed-count message was made up (see above). Everything else matches the original, including the trailing spaces, `0` for out-of-range rows, and `search` backing up past its starting row. |
| Data types and language semantics | Boards are tuples, as in ATS. `search`, `safety_test2` and `print_dots` were correctly rewritten as loops: the full search makes over 15,000 tail calls, and a literal recursive version was run and does crash with `RecursionError`. Python ignoring SIGPIPE was missed (see above). ATS `int` is a 32-bit C integer and Python's is unbounded; this program's numbers stay between -1 and 92, so it makes no difference. |
| Missing functions | None: all eight functions, `N`, and `main0` with its count check are there. |
| Library usage | Only `sys` (the review added `signal`). Output goes through `sys.stdout.write`, and `print_board` flushes like ATS's `print_newline`. |
| Poor or complicated code | Kept as is: `print_board` calls `print_row` eight times like the original, and `search` updates all four of its variables in one assignment per branch, even where some stay the same. Each assignment matches one recursive call in the original, and doing the update in one step matters when backing up (`j` must be read from the old row `i`). |

Also checked: the output is identical when the file is run directly (`./translation/queens.py`),
from another directory, and under `python -O`.

## How failures are reported

- **Translation missing:** both tests fail with `translation not found: translation/queens.py
  does not exist`. They are not skipped.
- **A program crashes:** the test shows its exit code, the last case it had started, and the
  end of its error output (for example the `RecursionError`).
- **A program hangs:** it is stopped after 60 seconds and the test fails.
- **Whole-program output differs:** the report gives the first line that differs and a diff
  with each line shown by `repr()`, so `'. . . \n'` and `'. . .\n'` look different.
- **Case output differs:** the output is split at the `###` headers. The report lists the IDs
  of the cases that differ, are missing, or were not expected (including anything printed
  before the first case, e.g. by a main program that runs on import), then shows a diff of the
  first differing case.
- **`make expected` fails:** if `patscc` is not found, it says where it looked. If an ATS
  program exits with an error, its partial output file is deleted and the files in
  `tests/expected/` are left unchanged.

**Checking the test harness itself.** Before any translation existed, the harness was run
against deliberately broken stand-ins (in a scratch directory, not committed):

| Stand-in | Result |
|---|---|
| Output identical to `queens.out` | test 1 passes |
| Hand-written helper functions, no `search` | `cases.py` output for P1–T8 (28 cases) is byte-identical to the ATS output, so the Python test program formats cases exactly like `cases.dats` |
| Functions whose `search` recurses without end | test 2 fails: exit code 1, `last case started: ### R2 ...`, `RecursionError` |
| Program that sleeps (time limit lowered to 1 s) | fails: `did not finish within 1 seconds` |
| `queens.out` with trailing spaces removed | fails at line 1, diff shows `'Q . . . . . . . \n'` against `'Q . . . . . . .\n'` |
| `queens.out` cut after 500 lines | fails at line 501 (expected 1021 lines, got 500) |
| `cases.out` with P2's trailing space lost, G3 removed, R4 changed, text before the first case | `differing cases: P2, R4`, `missing cases: G3`, `unexpected output: (output before the first case)` |
| `cases.out` with two cases swapped | `every case matches, but they come out in a different order` |
| `make expected PATSHOME=/nope` | `error: patscc not found at /nope/bin/patscc` |
| `cases.dats` with a failing `assertloc` added | `make` stops, deletes `build/cases.out`, and `tests/expected/` is unchanged |

`make expected` also reproduced the original's output from session 1 exactly (SHA-256
`a1941fc45db2e56714d733bc3ab14999952dbf98b80b4ad7dc83b1e96c654359`).

## Results

| Date | Code tested | `make test` | Notes |
|---|---|---|---|
| 2026-09-17 | `895b4ce`: test harness only, no translation yet | 2 failed | both: `translation not found`, as expected |
| 2026-09-18 | `ff3be27`: AI's first draft, unedited | 2 passed | tests 1 and 2, on the first run |
| 2026-09-18 | `ff3be27` plus tests 3 and 4 | 2 passed, 2 failed | test 3: `exit(ATS): [assertloc] failed: ...` is not ATS's message. Test 4: exit 120 with a `BrokenPipeError` traceback, not SIGPIPE |
| 2026-09-18 | `3147b52`: reviewed translation (`assertloc` helper, default SIGPIPE handling) | 4 passed | |
