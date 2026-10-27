from __future__ import annotations

########################################################################
########################################################################
# Bounded observers that decode target values as naturals, booleans,
# and pairs. Every observation applies the value to pure, closed target
# terms and runs the result on the shared call-by-value evaluator. No
# reduction happens under lambdas, and Python never does arithmetic on
# the encoded data. It only inspects the final shape and counts nodes.
#
# Contexts and output shapes:
#
#   natural   v STEP BASE, where
#               STEP = lam tail. lam c. lam z. c tail
#               BASE = lam c. lam z. z
#             Call-by-value forces each tail to a value before STEP gets
#             it, so NUM(k) yields a k-node spine:
#               lam c. lam z. c (lam c. lam z. c (... BASE))
#             Nodes are matched up to alpha-renaming and counted.
#
#   boolean   v MARK_TRUE MARK_FALSE, where the markers are
#               MARK_TRUE  = lam a. lam b. lam c. a
#               MARK_FALSE = lam a. lam b. lam c. b
#             The result must be alpha-equivalent to one of them. Three
#             binders make a misread numeral (e.g. NUM(1), which yields
#             MARK_TRUE MARK_FALSE) produce neither marker.
#
#   pair      (FST v) and (SND v), each evaluated and then observed
#             recursively with the component's expected kind.
#
# Budgets: execute_and_observe runs the program under the execution
# budget. Every observation step after that (contexts, projections,
# nested components) comes from one shared observation budget, and the
# two counts are reported separately. A decoded pair also reports each
# component's share of the observation steps.
# Requires Python 3.12 or later.
########################################################################
########################################################################
from dataclasses import dataclass
from enum import Enum

from church import FST, SND
from evaluator import evaluate, Completed, Outcome
from target import Term, Var, Lam, App, alpha_eq, pretty


class Base(Enum):
    NAT = "nat"
    BOOL = "bool"

    def __str__(self) -> str:
        return self.value


NAT, BOOL = Base.NAT, Base.BOOL


@dataclass(frozen=True)
class PairKind:
    first: Kind
    second: Kind

    def __str__(self) -> str:
        return f"({self.first}, {self.second})"


type Kind = Base | PairKind

########################################################################
# Outcomes
########################################################################

@dataclass(frozen=True)
class Decoded:
    """value is an int, a bool, or a (nested) tuple for pairs. For a
    pair, parts holds each component's own Decoded, whose steps cover
    that component's projection and decoding; they sum to steps."""
    value: object
    steps: int
    parts: tuple[Decoded, Decoded] | None = None


@dataclass(frozen=True)
class Malformed:
    reason: str
    steps: int


@dataclass(frozen=True)
class ObsExhausted:
    """The observation budget ran out; this is not a decoded result."""
    steps: int


type ObsOutcome = Decoded | Malformed | ObsExhausted


@dataclass(frozen=True)
class Observation:
    """Execution outcome plus the observation outcome (None if execution
    did not complete), each with its own step count."""
    execution: Outcome
    observation: ObsOutcome | None

########################################################################
# Observation contexts
########################################################################

STEP = Lam("tail", Lam("c", Lam("z", App(Var("c"), Var("tail")))))
BASE = Lam("c", Lam("z", Var("z")))
MARK_TRUE = Lam("a", Lam("b", Lam("c", Var("a"))))
MARK_FALSE = Lam("a", Lam("b", Lam("c", Var("b"))))

########################################################################
# Observers
########################################################################

def observe(value: Term, kind: Kind, budget: int) -> ObsOutcome:
    """Decode a target value with the expected kind, using at most
    budget beta-value steps in total."""
    _require_value(value)
    match kind:
        case Base.NAT:
            return observe_nat(value, budget)
        case Base.BOOL:
            return observe_bool(value, budget)
        case PairKind(first_kind, second_kind):
            return _observe_pair(value, first_kind, second_kind, budget)
    raise TypeError(f"unknown kind: {kind!r}")


def observe_nat(value: Term, budget: int) -> ObsOutcome:
    _require_value(value)
    result = evaluate(App(App(value, STEP), BASE), budget)
    if not isinstance(result, Completed):
        return ObsExhausted(result.steps)
    count = _count_spine(result.value)
    if count is None:
        return Malformed("natural observation did not produce a STEP/BASE "
                         f"spine: {_short(result.value)}", result.steps)
    return Decoded(count, result.steps)


def observe_bool(value: Term, budget: int) -> ObsOutcome:
    _require_value(value)
    result = evaluate(App(App(value, MARK_TRUE), MARK_FALSE), budget)
    if not isinstance(result, Completed):
        return ObsExhausted(result.steps)
    if alpha_eq(result.value, MARK_TRUE):
        return Decoded(True, result.steps)
    if alpha_eq(result.value, MARK_FALSE):
        return Decoded(False, result.steps)
    return Malformed("boolean observation selected neither marker: "
                     f"{_short(result.value)}", result.steps)


def execute_and_observe(term: Term, kind: Kind, exec_budget: int,
                        obs_budget: int) -> Observation:
    """Run a closed term to a value under exec_budget, then observe it
    under obs_budget. For a pair this is OBS-02: evaluate the pair,
    then project and decode each component."""
    execution = evaluate(term, exec_budget)
    if not isinstance(execution, Completed):
        return Observation(execution, None)
    return Observation(execution, observe(execution.value, kind, obs_budget))


def _observe_pair(value: Term, first_kind: Kind, second_kind: Kind,
                  budget: int) -> ObsOutcome:
    parts: list[Decoded] = []
    used = 0
    for projection, kind in ((FST, first_kind), (SND, second_kind)):
        projected = evaluate(App(projection, value), budget - used)
        if not isinstance(projected, Completed):
            return ObsExhausted(used + projected.steps)
        component = observe(projected.value, kind,
                            budget - used - projected.steps)
        part_steps = projected.steps + component.steps
        used += part_steps
        match component:
            case Decoded(component_value, _, component_parts):
                parts.append(Decoded(component_value, part_steps,
                                     component_parts))
            case Malformed(reason, _):
                return Malformed(f"pair component: {reason}", used)
            case ObsExhausted():
                return ObsExhausted(used)
    return Decoded(tuple(part.value for part in parts), used, tuple(parts))

########################################################################
# Shape inspection
########################################################################

def _count_spine(term: Term) -> int | None:
    """Count STEP nodes down to BASE, up to alpha-renaming, or return None.

    BASE node: lam c. lam z. z
    STEP node: lam c. lam z. c tail   with c != z (so c is the outer binder)
    """
    count = 0
    while True:
        match term:
            case Lam(_, Lam(inner, Var(name))) if name == inner:
                return count
            case Lam(outer, Lam(inner, App(Var(head), tail))) \
                    if head == outer and outer != inner:
                count += 1
                term = tail
            case _:
                return None


def _require_value(value: Term) -> None:
    if not isinstance(value, Lam):
        raise ValueError(f"observers take a value (a lambda), got {pretty(value)}")


def _short(term: Term, limit: int = 80) -> str:
    text = pretty(term)
    return text if len(text) <= limit else text[:limit - 3] + "..."
