from __future__ import annotations

########################################################################
########################################################################
# The end-to-end pipeline for one demonstration:
#
#   1. compile the source AST to a pure term (no evaluation);
#   2. execute the term on the shared evaluator under EXEC_BUDGET;
#   3. if it completed, observe the value with the expected kind under
#      OBS_BUDGET;
#   4. for terminating demos only, evaluate the source AST on the same
#      shared evaluator's source path to get the source-side answer.
#
# A demo expected to exhaust its budget never runs the source side,
# because source evaluation is unbounded.
#
# Budgets: the most expensive terminating demos measured 1,794
# execution steps (fib 5) and 218 observation steps (fact 4). The
# budgets below give roughly 11x and 23x headroom. The test suite
# checks that every terminating demo stays under a fifth of each.
# Requires Python 3.12 or later.
########################################################################
########################################################################
from dataclasses import dataclass

from compiler import compile_expr
from evaluator import evaluate, Completed, Exhausted, Outcome
from examples import Demo, EXHAUSTED
from observers import Decoded, ObsOutcome, execute_and_observe
from source import D0Eint, D0Ebtf, D0Epair, d0exp
from target import Term

EXEC_BUDGET = 20_000
OBS_BUDGET = 5_000


@dataclass(frozen=True)
class DemoReport:
    demo: Demo
    target: Term
    exec_budget: int
    obs_budget: int
    execution: Outcome
    observation: ObsOutcome | None   # None when execution did not complete
    source_ran: bool
    source_answer: object | None     # None when the source side did not run

    @property
    def passed(self) -> bool:
        if self.demo.expected is EXHAUSTED:
            return isinstance(self.execution, Exhausted)
        return (isinstance(self.execution, Completed)
                and isinstance(self.observation, Decoded)
                and same_answer(self.observation.value, self.demo.expected)
                and same_answer(self.source_answer, self.demo.expected))


def run_demo(demo: Demo, exec_budget: int = EXEC_BUDGET,
             obs_budget: int = OBS_BUDGET) -> DemoReport:
    target = compile_expr(demo.source)
    report = execute_and_observe(target, demo.kind, exec_budget, obs_budget)
    source_ran = demo.expected is not EXHAUSTED
    source_answer = None
    if source_ran:
        result = evaluate(demo.source)
        source_answer = to_python(result.value)
    return DemoReport(demo, target, exec_budget, obs_budget, report.execution,
                      report.observation, source_ran, source_answer)


def to_python(value: d0exp) -> object:
    """Convert a source value (D0Eint/D0Ebtf/D0Epair) to int/bool/tuple."""
    match value:
        case D0Ebtf(b):
            return b
        case D0Eint(n):
            return n
        case D0Epair(first, second):
            return (to_python(first), to_python(second))
    raise TypeError(f"not a data value: {value!r}")


def same_answer(left: object, right: object) -> bool:
    """Equality that does not confuse bool with int (True == 1 in Python)."""
    if isinstance(left, tuple) and isinstance(right, tuple):
        return (len(left) == len(right)
                and all(same_answer(a, b) for a, b in zip(left, right)))
    return type(left) is type(right) and left == right
