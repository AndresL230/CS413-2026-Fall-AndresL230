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
<!-- TODO (Andres): in your own words, a few sentences on:
     - why pairs let the int8 board and the solution list be built in LAMBDA0
     - why search needs a raised recursion limit (no tail calls)
     - why the tuple-argument version was slower (a pair is re-evaluated
       every time a parameter is read from it) -->
