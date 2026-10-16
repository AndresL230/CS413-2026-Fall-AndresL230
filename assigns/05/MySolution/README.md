# Assignment 5: Pretty Printing and Capture-Avoiding Substitution

Author: Andres Lopez

Two new operations on the supplied LAMBDA AST (`../lambda1_vp.py`), both
written as visitors that dispatch through `accept`. The supplied interpreter
is imported, not copied or modified.

## Files

| File | Contents |
| --- | --- |
| `lambda1_visitors.py` | `PrettyPrintVisitor`, `SubstitutionVisitor`, helper visitors (`AllNamesVisitor`, `RenameVisitor`), `FreshNames`, and the entry points `d0exp_pretty`, `d0exp_substitute` |
| `test_unittest.py` | `unittest` suite (`unittest.TestCase` classes) |
| `test_pytest.py` | `pytest` suite (plain test functions and `assert`) |
| `shared_cases.py` | Example inputs and expected results used by both suites (data only) |
| `examples.py` | Runs the assignment's examples and prints actual vs. expected |

## Requirements and setup

- Python 3.12 or later (tested with Python 3.14.7).
- The `unittest` suite and `examples.py` need only the standard library.
- The `pytest` suite needs pytest. Install it into a virtual environment
  inside `MySolution/` (ignored by `MySolution/.gitignore`), from `assigns/05`:

```sh
python3 -m venv MySolution/.venv
MySolution/.venv/bin/python -m pip install pytest
```

## Running

Run every command from the assignment directory, `assigns/05`. The `-B` flag
stops Python from writing a `__pycache__/` next to the supplied
`lambda1_vp.py`, and `-p no:cacheprovider` stops pytest from writing a
`.pytest_cache/` there.

```sh
# unittest suite
python3 -B -m unittest discover -s MySolution -p 'test_unittest.py' -v

# pytest suite
MySolution/.venv/bin/python -B -m pytest MySolution/test_pytest.py -v -p no:cacheprovider

# assignment examples, actual vs. expected
python3 -B MySolution/examples.py
```

If pytest is already installed for `python3`, the pytest suite can also be
run without the virtual environment:

```sh
python3 -B -m pytest MySolution/test_pytest.py -v -p no:cacheprovider
```

Each command exits with a nonzero status if anything fails.

## Examples

Run this snippet from inside `MySolution/`, where Python can find
`lambda1_visitors` (which in turn finds `../lambda1_vp.py`):

```python
from lambda1_visitors import d0exp_pretty, d0exp_substitute
from lambda1_vp import D0Eapp, D0Elam, D0Eop2, D0Evar, D0Eint

e = D0Eapp(D0Elam("x", D0Eop2("+", D0Evar("x"), D0Eint(1))), D0Eint(4))
d0exp_pretty(e)                                   # '((lam x. (x + 1)) 4)'

lam = D0Elam("y", D0Eop2("+", D0Evar("x"), D0Evar("y")))
d0exp_pretty(d0exp_substitute(lam, "x", D0Evar("y")))
                                                  # '(lam y_1. (y + y_1))'
```

These are results from `examples.py`. The first seven rows are the
assignment's examples; the last three are extra edge cases:

| Expression | Substitution | Result |
| --- | --- | --- |
| `(x + z)` | `x := 3` | `(3 + z)` |
| `(lam x. (x + y))` | `x := 3` | `(lam x. (x + y))` |
| `(lam y. (x + y))` | `x := y` | `(lam y_1. (y + y_1))` |
| `(let x = x in (x + y))` | `x := 3` | `(let x = 3 in (x + y))` |
| `(let y = x in (x + y))` | `x := y` | `(let y_1 = y in (y + y_1))` |
| `(fix f(n). (x + (f n)))` | `x := f` | `(fix f_1(n). (f + (f_1 n)))` |
| `x` | `x := (x + 1)` | `(x + 1)` |
| `(fix f(n). ((x + n) + (f n)))` | `x := (f + n)` | `(fix f_1(n_1). (((f + n) + n_1) + (f_1 n_1)))` |
| `(fix f(f). (x + f))` | `x := f` | `(fix f_1(f_1). (f + f_1))` |
| `(lam y. (lam y_1. ((x + y) + y_1)))` | `x := y` | `(lam y_2. (lam y_1. ((y + y_2) + y_1)))` |

## Fresh-name policy

A binder is renamed only when the target occurs free in its scope **and**
the bound name occurs free in the replacement. For a binder named `b`, the
new name is the first of `b_1`, `b_2`, `b_3`, ... that is not already used.
At the start of each call, "used" means every variable and binder name in
the expression and in the replacement, plus the target. Each generated name
is then added, so later renamings in the same call skip it. Each call starts
a new supply and visits children left to right (initializer before body), so
results are deterministic.

When a `fix` has the same function name and parameter (`fix f(f)`), both
binders get the same fresh name, so the parameter still shadows the function
name.

## Known limitations

- Each binder computes its body's free variables to decide whether
  substitution or renaming is needed, so substitution is quadratic on deeply
  nested expressions.
- The result may share unchanged subtrees with the input, and the
  replacement is inserted as the same object everywhere it appears. Nothing
  mutates a node, but a caller that mutates the result could affect them.
- Fresh names are built from the binder's own name, so renaming a binder
  already called `y_1` produces `y_1_1`.
- Inputs are not validated. Names are assumed to match
  `[A-Za-z_][A-Za-z0-9_]*`, and operator names are printed as given.
- Deep expressions can hit Python's recursion limit, as the supplied
  visitors can.

## Design

Each operation is a subclass of `D0ExpVisitor[R]`, where `R` is the result
type. `PrettyPrintVisitor` is a `D0ExpVisitor[str]`: each `visit_*` method
calls `accept` on the node's children and places their strings in that
form's fixed template. `SubstitutionVisitor` and `RenameVisitor` are
`D0ExpVisitor[d0exp]` and build new expression nodes. `AllNamesVisitor`
returns `frozenset[str]`, like the supplied `FreeVariableVisitor`, which is
reused through `d0exp_fvset`. One interface serves all of these because the
result type is a parameter: `accept` returns whatever its visitor's methods
return.

Substitution carries its context in the visitor's fields, the same way
`EvaluateVisitor` keeps its environment. The fields are the target name, the
replacement, the replacement's free variables (computed once), and a
`FreshNames` supply shared by the whole call. That supply is the only state
that changes. It is created anew by `d0exp_substitute` on each call, so
repeated calls give the same result. The visitor never changes a node: every
method returns the input node, the replacement, or a newly built node.

Scope is handled at the three binders. For `lam` and `fix`, if the target is
bound there, or does not occur free in the body, the node is returned as is.
That stops substitution where the target is shadowed and avoids needless
renaming. Otherwise, each binder whose name is free in the replacement is
renamed before the visitor goes into the body. For `let`, the initializer is
always substituted, because it lies outside the binding, and only the body
follows the binder rules. Renaming is its own visitor, `RenameVisitor`, not
a string replacement. It changes only the occurrences that a given binder
actually binds, and it stops at any inner `lam`, `fix` or `let` body that
rebinds the same name. Because the new name never appears anywhere in the
expression, no inner binder can capture it. For `fix f(f)`, the evaluator
binds the parameter after the function name, so every occurrence in the body
refers to the parameter. Renaming both binders to one fresh name keeps that
behavior.

The Visitor pattern makes adding operations cheap and adding constructors
expensive. These two operations needed no change to `lambda1_vp.py`: each is
one new class implementing every `visit_*` method, kept in a separate module. A
new expression form is the reverse. It needs a new node class, a new
abstract method on `D0ExpVisitor`, and an implementation in every existing
visitor (free variables, evaluation, printing, names, renaming and
substitution). Until all of those exist, the abstract base class keeps those
visitors from being created. This is one side of the expression problem: the
set of operations is open to extension while the set of expression forms is
fixed.
