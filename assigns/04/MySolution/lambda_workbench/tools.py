"""The real Lint and Interpret tools, as plain functions over source text.

These run inside the worker process started by `backend.LambdaBackend`, so
they are unbounded here; the time and memory bounds are applied around them.
"""
from . import lambda1
from .contract import Outcome, ToolOutput
from .reader import ReaderError, read_expression

# Longest value text returned to the application.
MAX_OUTPUT_CHARS = 20_000


def lint_source(source: str) -> ToolOutput:
    """Report the undeclared variables of `source` without evaluating it."""
    try:
        dexp = read_expression(source)
    except ReaderError as exc:
        return ToolOutput(Outcome.INPUT_ERROR, f"Input error: {exc}")
    free = lambda1.d0exp_fvset(dexp)
    if free:
        names = ", ".join(sorted(free))
        return ToolOutput(Outcome.LANGUAGE_ERROR, f"Undeclared variable(s): {names}")
    return ToolOutput(Outcome.SUCCESS, "No free variables found.")


def interpret_source(source: str) -> ToolOutput:
    """Evaluate `source` in the empty environment and report its value."""
    try:
        dexp = read_expression(source)
    except ReaderError as exc:
        return ToolOutput(Outcome.INPUT_ERROR, f"Input error: {exc}")
    try:
        value = lambda1.d0exp_evaluate(dexp, lambda1.ENVnil())
    except RecursionError:
        return _runtime_error("recursion is too deep (the program may not terminate)")
    except MemoryError:
        return _runtime_error("the program ran out of memory")
    except ZeroDivisionError:
        return _runtime_error("division by zero")
    except Exception as exc:
        return _runtime_error(f"{type(exc).__name__}: {exc}")
    if contains_error_value(value):
        return _runtime_error(
            f"evaluation produced the error value D0V000() in {_show(value)}; "
            "this usually means an undeclared variable was used")
    return ToolOutput(Outcome.SUCCESS, _show(value))


def contains_error_value(value: lambda1.d0val) -> bool:
    """True if `value` is the error sentinel D0V000() or a pair holding one."""
    pending = [value]
    while pending:
        current = pending.pop()
        if type(current) is lambda1.D0V000:
            return True
        if isinstance(current, lambda1.D0Vpair):
            pending += [current.arg1, current.arg2]
    return False


def _runtime_error(message: str) -> ToolOutput:
    return ToolOutput(Outcome.LANGUAGE_ERROR, f"Runtime error: {message}")


def _show(value: lambda1.d0val) -> str:
    try:
        text = repr(value)
    except (ValueError, RecursionError):
        # Python refuses to print integers beyond its digit limit.
        return f"<{type(value).__name__} too large to display>"
    if len(text) > MAX_OUTPUT_CHARS:
        text = text[:MAX_OUTPUT_CHARS] + f"\n... (truncated, {len(text)} characters in total)"
    return text
