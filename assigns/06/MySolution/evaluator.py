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
# Source path: not implemented yet (milestone 1).
#
# This module must not import the compiler.
# Requires Python 3.12 or later.
########################################################################
########################################################################
from dataclasses import dataclass, fields

from source import D0E000
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
    trace is a list, each target contraction is appended to it.
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
        raise NotImplementedError("source evaluation is not implemented yet")
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
            contractum = substitute(held.body, held.param, value)
            if tracing:
                trace.append(TraceStep(steps, frame_path,
                                       App(held, value), contractum))
            current, path = contractum, frame_path
            break
