# AI-assisted development log: Assignment 2

Tool: Claude Code (Claude Opus 5.5), in one session on 2026-09-22.
Below are my prompts, paraphrased, in order, with what the AI did and what
I decided. I made the decisions; the AI proposed options, ran commands and
wrote the drafts.

## 1. Setup and orientation
- **Me:** Fetch from the remote and give me a rundown of the assignment.
- **AI:** Fetched from both remotes. It found 4 new upstream commits and
  summarized the spec into Part A (pairs) and Part B (queens). It also
  flagged likely problems: Python's recursion limit, speed, and printing.
- **Me:** Merge upstream "for good practice" and start. The AI merged.

## 2. Part A: pairs and projections
- The AI copied `lambda0.py` and the starter tests into `MySolution/`. It
  added the pair and projection cases to `t0erm_size`, `t0erm_fvset`,
  `t0erm_subst0` and `t0erm_cbv_evaluate0`, and wrote `test02_lambda0.py`.
- **Check:** 57/57 tests pass. Against the unmodified starter, 26 of the 27
  new tests fail, which shows they really test the new code.

## 3. Understanding before Part B
- **Me:** Explain what the README must contain, so I know how to approach
  this. The AI listed the README requirements from the spec.
- **Me:** Show me the problems first, so I understand this well.
- **AI:** Measured instead of guessing. The ATS search makes 17,685 calls.
  With the default recursion limit, a 1,000-step loop fails, and raising
  the limit fixes it. It listed the encoding problems (no `let`, no `abs`,
  no `and`, the term must be closed, call-by-value) and gave me two
  decisions.
- **Me:** Chose the recommended design: return every solution rather than
  just a count, make N a parameter so smaller boards can be tested, and use
  curried arguments.

## 4. Part B: translation
- The AI wrote `queens_lambda0.py`: each ATS function as a closed term, all
  chained together with `let` into one closed program.
- First version: correct (92 solutions) but it took 104 seconds for N = 8.
  Profiling showed about 88% of the time was in `t0erm_subst0`.
- The AI tried passing arguments as one tuple. Every count was still
  correct, but it was about 5 times slower (548 seconds), because the
  interpreter re-evaluates a whole pair every time a parameter is read from
  it. It reverted to curried arguments and wrote the reason in the README.
- It was close to the deadline, so we stopped optimizing and finished the
  deliverables: `test03_queens.py`, the README, and a copy of the ATS source.

## 5. Verification
- The full suite passes: 66 tests in about 70 seconds.
- The translation's 92 boards are identical to the output of the compiled
  ATS program from Assignment 1, in the same order.
- **Me:** Asked for clear commit messages and for this log.
