# Assignment #1 — AI-Assisted Code Translation

The eight-queens program from the ATS book, translated into Python 3 with an AI assistant, plus
the tests I used to check the translation against the original.

## The program

It solves the eight-queens puzzle: put 8 queens on a chessboard so that none of them can attack
another. It prints a demo board first, then every solution there is, which comes to 92, and
finishes by checking that it really found 92. It takes no input, so both versions print the same
1,021 lines every time.

A board is 8 numbers, one per row, saying which column that row's queen is in. `search` tries
each column of a row in turn, moves on to the next row when a square is safe, and backs up to the
previous row when it runs out of columns.

The original is `original/queens.dats`, taken unchanged from the ATS book
(INT2PROGINATS, `CODE/CHAP_FUNCTION/queens.dats`):
<https://ats-lang.github.io/FROZEN000/DOCUMENT/INT2PROGINATS/CODE/CHAP_FUNCTION/queens.dats>

## What's here

| File | What it is |
|---|---|
| `original/queens.dats` | The original ATS2 program, exactly as downloaded. Never edited. |
| `translation/queens.py` | The Python 3 translation. |
| `tests/` | The test programs and the saved output of the original. |
| `TESTING.md` | What is tested, what each case checks, and the results. |
| `AI-TRANSCRIPT.md` | The AI used, the prompts, what it found, and the corrections. |
| `Makefile` | Commands for building and running both programs. |

## Running it

From this directory:

```
make test             # compare the translation with the original's saved output (needs only python3)
make run-translation  # run the Python version
make run-original     # compile and run the ATS version (needs ATS2)
make expected         # regenerate the saved ATS output (needs ATS2)
```

`make test` runs four tests: the whole program's output, 43 cases run function by function on both
versions, the failed-count check, and the closed output pipe. All of them pass. The output of the
ATS side is saved in `tests/expected/`, so ATS2 is only needed to regenerate it. See `TESTING.md`.

## If you want to run the ATS side

Only `make run-original` and `make expected` need ATS2; the tests don't. I used ATS2-Postiats
0.4.2, built from source without root into `~/.local/opt/ATS2-Postiats-gmp-0.4.2`, which is where
the Makefile looks by default. To point it somewhere else:

```
make run-original PATSHOME=/path/to/ATS2-Postiats-gmp-0.4.2
```

Two things I ran into while installing it. The checksum in the AUR package didn't match what
SourceForge serves, and the file I downloaded matched SourceForge's own published MD5, which is
newer. And ATS2's own C code doesn't build under GCC 16 until you add `-std=gnu17 -fpermissive`,
which I did with a temporary `gcc` wrapper. Compiling the queens programs themselves needs no
such flags.

## AI Reflection

I used Claude Code (Claude Opus 5) to translate an eight-queens program from ATS into Python 3.

**What the AI did well.** It understood the original program quickly and explained what each part
of it did. The most useful thing was how fast it turned what I wanted into something real. I told
it I wanted to be sure the Python version behaved like the original, and it wrote the test cases
and generated all the expected output for me. Doing that by hand would have taken me a long time,
and it was accurate: the translation matched the original's output exactly, down to the last space.

**Weaknesses.** The AI didn't know how I wanted to approach the assignment. It kept giving me
options and waiting on me to choose, so the direction had to come from me, and I had to be clear
about what I wanted and give it ideas before it produced anything useful. It also got two things
wrong in the translation that only showed up after testing: it invented an error message that the
original never prints, and it crashed with a traceback when the output was piped into another
command, instead of stopping quietly the way the original does.

**What I had to understand myself.** I still had to understand the program: how the board is
stored, what the search does, and exactly what the original prints, including the trailing space
at the end of every row. Without that, "the tests pass" wouldn't have meant anything, and I
couldn't have judged the choices the AI put in front of me.

**Could it have been trusted without testing?** No. You don't really know what the AI produced,
because you didn't write it line by line. It passed every test we had on its first run and was
still wrong in two places, and those only turned up because we read the code and then wrote tests
aimed at them.

**How AI changed my work.** It made the whole thing easier and quicker. I spent my time on the big
picture — how to approach the problem and how to show the translation was right — instead of
writing every line myself.
