# Closure-based LAMBDA interpreter

`lambda0.py` adapts the term constructors and call-by-value semantics from
`../lecture-09-15/lambda0.py`. It requires Python 3.12 or later.

Run the examples and tests:

```sh
python3 -m unittest discover -s TEST -v
```

`t0erm_cbv_evaluate0(term)` evaluates a closed term in an empty environment.
Literal values retain their `T0Mint`, `T0Mbtf`, and `T0Mstr` representations.
Functions evaluate to `T0Vclos(code, env)` and pairs to `T0Vpair(first, second)`.
`T0Env` is an immutable linked list of name/value bindings; `None` is empty.

A lambda captures its definition environment. Application evaluates the function
and argument, then evaluates the body in the captured environment extended with
the parameter binding. A recursive closure additionally binds its own name to
itself at application time. The parameter shadows the recursive name when both
names coincide, as in the original substitution evaluator.

There is no substitution or AST copying during evaluation. Evaluation proceeds
left to right, including both pair components; a conditional evaluates only its
selected branch. Unbound variables raise `NameError`; invalid operand kinds raise
`TypeError`. Integer division and modulo use Python semantics.

This version also implements the existing pair/projection constructors and fixes
the original `>=` branch, which accidentally performed `<=`.
