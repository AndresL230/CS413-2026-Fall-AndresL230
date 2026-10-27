# Design (draft)

This file is filled in as milestones land. The decisions below are fixed
and must survive into the final write-up.

## Decisions carried forward

- **Pair observation budgets.** Evaluating a pair-valued program to a value
  uses the *execution* budget. Applying the Church projections and decoding
  each component uses the *observation* budget. Both counts are reported
  separately.
- **Source `and`/`or` compile only through thunks.** `C[e1 and e2]` and
  `C[e1 or e2]` use the delayed-branch form
  `(C[e1] (lam u. ...) (lam v. ...)) I`. They must **never** compile to the
  strict library combinators `AND C[e1] C[e2]` / `OR C[e1] C[e2]`. Under
  call-by-value those evaluate both operands, which breaks short-circuiting.
  The strict combinators are only for use inside the library (for example
  `EQ`), where the operands are already values.
- **Coincident `fix` in the source half of the evaluator.** Applying
  `fix f(x). body` to `v` substitutes `f := fixval` and then `x := v` when
  `f != x`. When `f == x`, the parameter shadows the function name, so the
  evaluator substitutes **only** `x := v`. It must not first put the fix
  value into the parameter slot. A test checks that `(fix f(f). f) 3`
  returns `3` on the source side.
- **Target execution is restricted to closed terms.** `evaluate` rejects an
  open target term with `EvalError` before taking any step. Substitution
  and compilation still support open terms.
