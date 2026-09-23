# AI-assisted development log: Assignment 2

Tool: Claude Code (Claude Opus 5.5), 2026-09-22. These are my prompts while
working on the solution, in order. For each one: what I asked for, why, and
what came of it.

## 1. "Orient me on what it says on the README … so I know how to go about this"
Before any Part B code was written, I wanted to know what the finished
submission had to show: the ATS-to-LAMBDA0 mapping, the run commands, the
comparison with the original program, the call-by-value changes and
limitations, and how I checked the AI's work. I asked first so the plan
would be built around those requirements instead of patched afterwards.

## 2. "Help me understand this well … present to me the issues first"
I asked for the risks before any translation code existed, so I could make
the design decisions myself. What came back, measured rather than assumed:
- **Recursion depth.** The ATS search makes 17,685 calls. The interpreter
  has no tail calls, so Python's default recursion limit of 1,000 is not
  enough.
- **Substitution cost.** Every function call copies the function body.
- **Missing features.** LAMBDA0 has no `let`, `abs`, `andalso` or
  multi-argument functions, so each has to be encoded.
- **Closed terms.** The whole program has to be one term with no free
  variables.
- **Call-by-value.** Arguments are always evaluated first, so anything
  conditional has to go inside an `if` branch.
- **Two decisions for me:** what the term returns, and whether N is fixed.

## 3. "Let's go with that recommendation"
My design decisions:
- **Enumerate every solution** instead of only counting. The ATS program
  both counts and prints each solution, and the spec says to preserve that.
  Returning every board also lets every board be checked.
- **Make N a parameter**, so the smaller boards the spec asks about can be
  tested, while the driver still uses N = 8 like the original.
- **Curried arguments**, so the code reads like the ATS functions.

Result: 92 solutions, identical in order to the compiled ATS output.
Passing arguments as one tuple was tried for speed; it was 5 times slower,
so it was reverted with the measurements recorded in the README.

## 4. "Make sure we got all the comments … proper commit messages … fill out the transcript"
Before submitting, I asked for the code comments to be checked, for the work
to be split into one commit per part (Part A, Part B, documentation), and
for this log.

## My understanding

### Why pairs let us build the board and the solution list
Before this assignment, LAMBDA0 only had single values like numbers,
booleans, strings, and functions, so there was no way to keep several values
together. A pair holds two values, and putting pairs inside pairs gives you
any length: the board is `(q0, (q1, (q2, ...)))`, and the solution list is
`(board, rest_of_list)` ending in `0`. The only way to get values back out is
`fst` and `snd`, which is why `board_get` walks the board one step at a time.
To get queen 5 you take `snd` five times, then `fst`. I chose to keep every
solution in a list instead of just counting them, so the program does what
the ATS version does and every board can be checked.

### Why the search needed a higher recursion limit
In ATS, `search` calls itself as its very last action, and the compiler turns
that tail call into a plain loop, so the stack never grows. Our Python
interpreter can't do that. Evaluating a call means `t0erm_cbv_evaluate0` calls
itself again, so each of the 17,685 search steps stacks more Python calls on
top of the last one. Python stops at 1,000 by default and raises a
`RecursionError`, so the driver raises the limit to 1,000,000.

### Why the tuple-argument version was slower
We tried passing all four arguments as one tuple, like ATS does, thinking
each call would do less substitution. It backfired: 548 s instead of 104 s.
This interpreter re-evaluates every part of a pair each time the pair is
evaluated, even when the parts are already values. The tuple included `acc`,
so every time the function read any parameter, it re-walked the whole growing
solution list. We went back to curried arguments. The lesson for me was that
a change that looks faster on paper has to be measured, because the
interpreter's details decide what is actually fast.

### Looking back
If I did this again, I'd use the closure-based interpreter from the 09-22
lecture, since it doesn't copy the program on every call and would be much
faster.
