from __future__ import annotations

########################################################################
########################################################################
# The shared evaluator: one entry point, evaluate(), for source ASTs
# and target terms, both using left-to-right call-by-value.
#
# Target path: weak call-by-value over Var/Lam/App only. Values are
# lambdas; (lam x. body) v --> body[x := v] is one beta-value step.
# It runs on an explicit stack (no Python recursion per redex), counts
# steps against a budget, and applies no source-language operations.
#
# Source path: the same left-to-right call-by-value rules over source
# ASTs, by substitution. Values are D0Eint, D0Ebtf, D0Epair of values,
# D0Elam, and D0Efix. Source-only constructors use the source rules:
# truncated subtraction, short-circuit and/or, and only the selected
# branch of a conditional. It is unbounded (budget must be None) and
# counts application and let contractions as steps.
#
# Both paths share one contraction rule, _contract, for target lambdas,
# source lambdas, and source fix values.
#
# This module must not import the compiler or the Church library.
# Requires Python 3.12 or later.
########################################################################
########################################################################
from dataclasses import dataclass, fields

import source
from source import (
    D0ExpVisitor, D0E000, d0exp,
    D0Eint, D0Ebtf, D0Eop1, D0Eop2, D0Evar, D0Elam, D0Efix,
    D0Eapp, D0Eif0, D0Elet, D0Epair, D0Epfst, D0Epsnd,
    UnsupportedSource, d0exp_pretty, d0exp_substitute,
)
from target import Term, TERM_TYPES, Lam, App, free_vars, is_pure, \
    pretty, substitute


class EvalError(Exception):
    """Input the evaluator rejects: open target terms, mixed or non-syntax
    trees, and (later) source-language runtime errors."""


@dataclass(frozen=True)
class Completed:
    """Evaluation reached a value after `steps` beta-value steps."""
    value: object
    steps: int


@dataclass(frozen=True)
class Exhausted:
    """Another step was needed but all `steps` of the budget were spent.
    This is not a proof of nontermination."""
    steps: int


type Outcome = Completed | Exhausted


@dataclass(frozen=True)
class TraceStep:
    """One contraction: its step number, the redex's position in the
    current term ("fn"/"arg" from the root), the redex, and its result."""
    step: int
    path: tuple[str, ...]
    redex: App
    contractum: Term


def evaluate(expr: object, budget: int | None = None, *,
             trace: list[TraceStep] | None = None) -> Outcome:
    """Evaluate a source AST or a closed target term.

    A target term needs a nonnegative int budget of beta-value steps. When
    trace is a list, each target contraction is appended to it. A source
    AST is evaluated without a budget; source runtime errors (unbound
    names, type errors, Python recursion exhaustion on divergence) and
    unsupported input anywhere in the tree raise EvalError.
    """
    if isinstance(expr, TERM_TYPES):
        if not is_pure(expr):
            raise EvalError("target term contains a non-target node")
        _check_budget(budget)
        open_names = free_vars(expr)
        if open_names:
            raise EvalError("target execution requires a closed term; "
                            f"free variables: {sorted(open_names)}")
        return _run_target(expr, budget, trace)
    if isinstance(expr, D0E000):
        _check_pure_source(expr)
        if budget is not None:
            raise TypeError("source evaluation is unbounded; budget must be None")
        try:
            source.validate(expr)
        except UnsupportedSource as err:
            raise EvalError(str(err)) from err
        return _run_source(expr)
    raise EvalError(f"not a source AST or target term: {expr!r}")


def _check_budget(budget: object) -> None:
    if type(budget) is not int:
        raise TypeError(f"budget must be an int, got {budget!r}")
    if budget < 0:
        raise ValueError(f"budget must be nonnegative, got {budget}")


def _check_pure_source(expr: D0E000) -> None:
    """Reject a source tree with any non-source node inside it."""
    pending: list[object] = [expr]
    while pending:
        node = pending.pop()
        if not isinstance(node, D0E000):
            raise EvalError(f"source AST contains a non-source node: {node!r}")
        for field in fields(node):
            child = getattr(node, field.name)
            if not isinstance(child, (str, int)):  # names, literals, bools
                pending.append(child)

########################################################################
# Target path
########################################################################
#
# The stack holds two kinds of frame, each tagged with the position of
# its application in the current term:
#   ("arg", app, path)      the function is being evaluated; next, app.arg
#   ("apply", fnval, path)  the argument is being evaluated; then contract
#
# Paths are built only when tracing.

def _run_target(term: Term, budget: int,
                trace: list[TraceStep] | None) -> Outcome:
    tracing = trace is not None
    steps = 0
    stack: list[tuple[str, Term, tuple[str, ...] | None]] = []
    current, path = term, (() if tracing else None)
    while True:
        # Descend through applications to the leftmost function position.
        while isinstance(current, App):
            stack.append(("arg", current, path))
            current = current.fn
            path = path + ("fn",) if tracing else None
        if not isinstance(current, Lam):
            # Unreachable for closed terms, which are checked on entry.
            raise EvalError(f"stuck on free variable: {pretty(current)}")
        value = current
        # Return the value to the nearest frame that needs one.
        while True:
            if not stack:
                return Completed(value, steps)
            kind, held, frame_path = stack.pop()
            if kind == "arg":
                stack.append(("apply", value, frame_path))
                current = held.arg
                path = frame_path + ("arg",) if tracing else None
                break
            if steps == budget:
                return Exhausted(steps)
            steps += 1
            contractum = _contract(held, value)
            if tracing:
                trace.append(TraceStep(steps, frame_path,
                                       App(held, value), contractum))
            current, path = contractum, frame_path
            break

########################################################################
# Shared contraction rule
########################################################################

def _contract(fn: object, arg: object) -> object:
    """Contract (fn arg) where both are values: substitute the argument
    for the parameter. A target lambda gets target substitution only."""
    match fn:
        case Lam(param, body):
            return substitute(body, param, arg)
        case D0Elam(param, body):
            return d0exp_substitute(body, param, arg)
        case D0Efix(fname, param, body):
            # The parameter shadows a coincident function name: then only
            # x := v applies. Otherwise f := fn first, then x := v. Both
            # values are closed in a closed program, so order is safe.
            if fname != param:
                body = d0exp_substitute(body, fname, fn)
            return d0exp_substitute(body, param, arg)
    raise EvalError(f"not a function value: {_show(fn)}")


def _show(value: object) -> str:
    if isinstance(value, TERM_TYPES):
        return pretty(value)
    if isinstance(value, D0E000):
        return d0exp_pretty(value)
    return repr(value)

########################################################################
# Source path
########################################################################

def _run_source(expr: d0exp) -> Outcome:
    visitor = _SourceEvaluator()
    try:
        value = expr.accept(visitor)
    except RecursionError:
        raise EvalError("source evaluation exceeded the Python recursion "
                        f"limit after {visitor.steps} steps (likely divergent)") \
            from None
    return Completed(value, visitor.steps)


class _SourceEvaluator(D0ExpVisitor[d0exp]):
    """Left-to-right call-by-value over source ASTs by substitution.
    Every visit returns a value expression."""

    def __init__(self) -> None:
        self.steps = 0

    def visit_int(self, dexp: D0Eint) -> d0exp:
        return dexp

    def visit_btf(self, dexp: D0Ebtf) -> d0exp:
        return dexp

    def visit_var(self, dexp: D0Evar) -> d0exp:
        # Bound names were substituted away, so any variable left is free.
        raise EvalError(f"unbound variable: {dexp.arg1}")

    def visit_lam(self, dexp: D0Elam) -> d0exp:
        return dexp

    def visit_fix(self, dexp: D0Efix) -> d0exp:
        return dexp

    def visit_app(self, dexp: D0Eapp) -> d0exp:
        fn = dexp.arg1.accept(self)
        arg = dexp.arg2.accept(self)
        if not isinstance(fn, (D0Elam, D0Efix)):
            raise EvalError(f"application of a non-function: {_show(fn)}")
        self.steps += 1
        return _contract(fn, arg).accept(self)

    def visit_let(self, dexp: D0Elet) -> d0exp:
        init = dexp.arg2.accept(self)
        self.steps += 1
        return d0exp_substitute(dexp.arg3, dexp.arg1, init).accept(self)

    def visit_if0(self, dexp: D0Eif0) -> d0exp:
        chosen = dexp.arg2 if self._bool(dexp.arg1) else dexp.arg3
        return chosen.accept(self)

    def visit_pair(self, dexp: D0Epair) -> d0exp:
        first = dexp.arg1.accept(self)
        second = dexp.arg2.accept(self)
        return D0Epair(first, second)

    def visit_pfst(self, dexp: D0Epfst) -> d0exp:
        return self._pair(dexp.arg1).arg1

    def visit_psnd(self, dexp: D0Epsnd) -> d0exp:
        return self._pair(dexp.arg1).arg2

    def visit_op1(self, dexp: D0Eop1) -> d0exp:
        return D0Ebtf(not self._bool(dexp.arg1))  # only "not" is valid

    def visit_op2(self, dexp: D0Eop2) -> d0exp:
        match dexp.name:
            case "and":
                return D0Ebtf(self._bool(dexp.arg1) and self._bool(dexp.arg2))
            case "or":
                return D0Ebtf(self._bool(dexp.arg1) or self._bool(dexp.arg2))
        left = self._nat(dexp.arg1)
        right = self._nat(dexp.arg2)
        match dexp.name:
            case "+":
                return D0Eint(left + right)
            case "-":
                return D0Eint(max(left - right, 0))
            case "*":
                return D0Eint(left * right)
            case "<":
                return D0Ebtf(left < right)
            case "<=":
                return D0Ebtf(left <= right)
            case ">":
                return D0Ebtf(left > right)
            case ">=":
                return D0Ebtf(left >= right)
            case "==":
                return D0Ebtf(left == right)
            case "!=":
                return D0Ebtf(left != right)
        raise EvalError(f"unsupported operator: {dexp.name!r}")

    # Operand helpers: evaluate, then check the source-language kind.

    def _nat(self, dexp: d0exp) -> int:
        value = dexp.accept(self)
        if not isinstance(value, D0Eint):
            raise EvalError(f"natural number expected: {_show(value)}")
        return value.arg1

    def _bool(self, dexp: d0exp) -> bool:
        value = dexp.accept(self)
        if not isinstance(value, D0Ebtf):
            raise EvalError(f"boolean expected: {_show(value)}")
        return value.arg1

    def _pair(self, dexp: d0exp) -> D0Epair:
        value = dexp.accept(self)
        if not isinstance(value, D0Epair):
            raise EvalError(f"pair expected: {_show(value)}")
        return value
