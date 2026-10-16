# AI Transcript

## AI tools used

- **Claude Code** (Anthropic's terminal coding assistant, model Claude Opus
  5.5), run in this repository. It read the assignment files, wrote code
  and documentation in `MySolution/`, and ran commands to test them.

## Important prompts and what the AI produced

1. **"Tell me a brief summary of this assign and what I should read before
   I start."**
   It summarized `Assign05.md`, pointed out that the stated due date
   (October 13) had already passed, and suggested a reading order: the spec,
   then the expression classes, `D0ExpVisitor`, `FreeVariableVisitor` and
   `EvaluateVisitor` in `lambda1_vp.py`, then the supplied tests.

2. **Build the visitors.** I asked for a summary of how the visitor pattern
   is set up in `lambda1_vp.py`, then for `PrettyPrintVisitor` and
   `d0exp_pretty`, a capture-avoiding `SubstitutionVisitor` and
   `d0exp_substitute` with alpha-renaming in its own visitor, and any helper
   visitors. Everything had to dispatch through `accept()`, nothing could be
   evaluated or mutated, the fresh-name scheme had to be deterministic
   (`y_1`, `y_2`, ...), and the supplied files could not be changed.
   It produced `lambda1_visitors.py` and `examples.py`. Suggestions and
   decisions it made:
   - A `fix` whose function name equals its parameter (`fix f(f)`) is renamed
     to one shared fresh name, so the parameter still shadows the name.
   - Unchanged subtrees are reused instead of copied. The spec allows this.
   - A binder is renamed only when the target is free in its body and the
     bound name is free in the replacement.

3. **Write the two test suites.** I asked for a `unittest` suite and a
   separate pytest suite that is not a wrapper around the first, covering
   every item in the assignment's Testing section plus the free-variable
   property.
   It produced `shared_cases.py` (data only), `test_unittest.py` and
   `test_pytest.py`. It also suggested:
   - Semantic-agreement tests: evaluating `e` with `x` bound gives the same
     result as evaluating `e[x := r]`.
   - Testing for no evaluation by replacing the evaluator with a function
     that fails, then printing and substituting into expressions that would
     crash or never finish if evaluated.

4. **Clean up, then write the docs.** It removed the `.venv` and
   `__pycache__` folders and wrote `.gitignore`, `README.md` (including the
   design explanation) and this file's outline.

## How the output was reviewed and tested

### Checks run during the session

- `examples.py`: every example from the assignment's table, plus 7 edge
  cases, matched its expected output. Each check also confirmed that the
  inputs were unchanged and that repeated calls gave the same result.
- Both suites passed: 26 `unittest` tests and 212 pytest cases.
- **Planted bugs:** in a scratch copy, six bugs were introduced into
  `lambda1_visitors.py` one at a time. Both suites failed on every one:
  - turning off renaming
  - not substituting into a `let` initializer when the body shadows the
    target
  - renaming that ignores shadowing
  - not recording generated names
  - fresh names that avoid only free variables
  - treating `fix f(f)` as two distinct names
- A search confirmed there are no `isinstance` or `type()` checks in
  `lambda1_visitors.py`.

### My own review

I ran both suites myself from assigns/05 after installing pytest, and ran
examples.py. I worked out (lam y. (x + y))[x := y] and the fix example from
the table on paper before comparing them to the output, and checked that
fix f(f) still lets the parameter shadow the function name, matching
EvaluateVisitor. I read through RenameVisitor and SubstitutionVisitor to
confirm renaming stops at inner binders and that let always substitutes
into the initializer.

My first prompt was very detailed about the substitution rules. I cut it
down and left the details to the assignment spec, since Claude Code had
read it. I kept the fix f(f) decision and the reuse of unchanged subtrees
after checking that both are allowed by the spec. I didn't reject any of
the generated code.

Adding a new operation was easy because it was just a new visitor class,
but adding a new expression type would mean updating every visitor.
Capture avoidance also needs every name in the expression, not just the
free variables, or fresh names can collide with existing bound names.
