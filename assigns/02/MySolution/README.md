# Assignment 2: pairs in LAMBDA0 and eight queens as a lambda-term

Requires Python 3.12+ (tested with Python 3.14).

## Files

| File | Contents |
| --- | --- |
| `lambda0.py` | Starter interpreter extended with `T0Mpair`, `T0Mpfst`, `T0Mpsnd`. |
| `TEST/test01_lambda0.py` | Starter tests, copied, run against this `lambda0.py`. |
| `TEST/test02_lambda0.py` | Tests for pairs and projections. |
| `queens.dats` | The ATS2 eight-queens program translated (from Assignment 1). |
| `queens_lambda0.py` | The translation as one closed `t0erm` plus a driver. |
| `TEST/test03_queens.py` | Tests for the translation. |
| `TEST/queens_ats_expected.out` | Output of the compiled ATS program (Assignment 1). |

## Running

```sh
cd MySolution/TEST && make                      # all tests (about 2 minutes)
make TEST=test02_lambda0.py                     # one file
cd .. && python3 queens_lambda0.py              # print all 92 solutions
python3 queens_lambda0.py 6                     # a smaller board
```

## Part 1: pairs and projections

`t0erm_size`, `t0erm_fvset` and `t0erm_subst0` recurse into both parts of a
pair and into a projection's operand. The new constructors bind no variables.
In `t0erm_cbv_evaluate0`, a pair evaluates its left part, then its right part.
`fst` and `snd` evaluate the operand fully, so both parts are always evaluated,
and they raise `TypeError` when the operand is not a pair. No other part of the
interpreter changed.

`test02_lambda0.py` covers the spec's examples plus the following:

- substitution under `lam` and `fix`, including shadowing
- nested pairs, and pairs that hold different kinds of values
- functions that take or return pairs
- recursion over pairs
- projection of a value that is not a pair
- left-to-right evaluation
- evaluation of the part a projection throws away

As a check that these tests really exercise the new code, I ran them against
the unmodified starter file. 26 of the 27 fail; only the import-path test
passes.

## Part 2: translating `queens.dats`

`search` and the safety checks run inside `t0erm_cbv_evaluate0`. Python only
builds the AST, then decodes and prints the value that comes back.

| ATS2 | LAMBDA0 |
| --- | --- |
| `int8` board `(x0, ..., x7)` | nested pairs `(x0, (x1, ... (x7, 0)))` |
| `board_get(bd, i)` | `T0Mfix` that walks down `i` steps with `snd`, then takes `fst` |
| `board_set(bd, i, j)` | `T0Mfix` that rebuilds the pairs up to position `i` |
| `abs` | `lam x. if x < 0 then -x else x` |
| `a andalso b` | `if a then b else false` (still short-circuits) |
| `safety_test1`, `safety_test2`, `search` | curried functions made with `T0Mlam`/`T0Mfix` |
| `let val x = e in b` | `(lam x. b) e` |
| `nsol` | accumulator `(count, solutions)`; `solutions` is a list of pairs, newest first |
| `#define N 8` | an outer `let N = 8`, so the tests can also use smaller boards |

All the definitions are chained together with `let` into one closed term.
Every definition is closed once the names before it have been substituted in.
This matches the interpreter's assumption that it only ever substitutes closed
terms. `queens_lambda0.evaluate` asserts that the term has no free variables
before it runs.

No new primitives were needed, because the starter already has `<`, `>`, `<=`,
`>=`, `==` and `!=` returning `T0Mbtf`.

### Comparison with the ATS program

- The count is 92, the same as the ATS program's `assertloc (nsol = 92)`.
- All 92 boards are valid: no two queens share a row, column or diagonal.
- They are the same 92 boards, in the same order, as the output of the
  compiled ATS program (`TEST/queens_ats_expected.out`).
- Smaller boards give the known counts: N = 4 gives 2, N = 5 gives 10,
  N = 6 gives 4.
- The tests also run `abs`, `board_get`, `board_set`, `safety_test1` and
  `safety_test2` inside the interpreter.

### Changes for call-by-value, and limitations

- **No printing.** The ATS program prints each solution when it finds it. A
  lambda-term can only return a value, so the term collects the solutions and
  Python prints them afterwards in the same layout as `print_board`.
- **Inlined lets.** The `test` and `bd1` lets in `search` are inlined. Each
  value is still computed at most once on any path, and `board_set` still runs
  only after the safety test passes, as in ATS.
- **Recursion depth.** The interpreter has no tail calls, so each of the
  17,685 `search` calls adds Python stack frames. The driver raises the
  recursion limit to 1,000,000. With Python's default limit of 1,000, the
  search fails with `RecursionError`.
- **Speed.** N = 8 takes about 100 seconds. Profiling shows about 88% of the
  time goes to `t0erm_subst0`, because every function call copies the whole
  function body, including the helper functions copied into it.
- **Tuple arguments made it slower.** I tried passing the arguments as one
  tuple, like ATS does. It was about 5 times slower (548 seconds for N = 8).
  This interpreter evaluates a pair by evaluating both parts again, so every
  parameter read went back through the whole argument tuple, including the
  list of solutions. I went back to curried arguments.

## AI assistance

I wrote this with Claude Code, and checked it as follows:

- Read every diff against the starter file.
- Ran the new tests against the unmodified starter to confirm they fail
  without the new code.
- Compared the translation's results with the compiled ATS program's actual
  output, not just the count of 92.
- Measured the performance ideas (profiling, the tuple-argument experiment)
  instead of assuming they would help. The tuple-argument version was rejected
  because the measurement showed it was slower.
