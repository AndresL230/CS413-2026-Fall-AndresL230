from __future__ import annotations

########################################################################
########################################################################
# Source-language support shared by the compiler and the evaluator:
#
#   * the supplied AST from ../../05/lambda1_vp.py, imported and never
#     copied or modified (run with python3 -B so no __pycache__ is
#     written next to it);
#   * the source-language contract: identifiers, natural literals, and
#     the supported operators, with validation of a whole tree;
#   * printing and capture-avoiding substitution for source ASTs.
#
# PrettyPrintVisitor, AllNamesVisitor, RenameVisitor, and
# SubstitutionVisitor are copied from Andres Lopez's Assignment 5
# solution (../../05/MySolution/lambda1_visitors.py) with only import
# changes; FreshNames is shared with target.py.
# Requires Python 3.12 or later.
########################################################################
########################################################################
import re
import sys
from pathlib import Path

_ASSIGN05_DIR = str(Path(__file__).resolve().parents[2] / "05")
if _ASSIGN05_DIR not in sys.path:
    sys.path.insert(0, _ASSIGN05_DIR)

from lambda1_vp import (  # noqa: E402,F401
    D0ExpVisitor, D0E000, d0exp, dvar, d0exp_fvset,
    D0Eint, D0Ebtf, D0Eop1, D0Eop2, D0Evar, D0Elam, D0Efix,
    D0Eapp, D0Eif0, D0Elet, D0Epair, D0Epfst, D0Epsnd,
)
from target import FreshNames  # noqa: E402

########################################################################
# Language contract
########################################################################

IDENTIFIER = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
OP1_NAMES = frozenset({"not"})
ARITH_OPS = frozenset({"+", "-", "*"})
COMPARE_OPS = frozenset({"<", "<=", ">", ">=", "==", "!="})
BOOL_OPS = frozenset({"and", "or"})
OP2_NAMES = ARITH_OPS | COMPARE_OPS | BOOL_OPS


class UnsupportedSource(ValueError):
    """A literal, operator, or name outside the source language."""


def check_name(name: object, dexp: d0exp) -> None:
    if not isinstance(name, str) or not IDENTIFIER.fullmatch(name):
        raise UnsupportedSource(
            f"invalid identifier {name!r} in {d0exp_pretty(dexp)}")


def check_int(n: object) -> None:
    if type(n) is not int:
        raise UnsupportedSource(
            f"natural literal must be an int, got {n!r} ({type(n).__name__})")
    if n < 0:
        raise UnsupportedSource(
            f"negative literal {n} is outside the source language")


def check_bool(b: object) -> None:
    if type(b) is not bool:
        raise UnsupportedSource(f"boolean literal must be a bool, got {b!r}")


def check_op1(dexp: D0Eop1) -> None:
    if dexp.name not in OP1_NAMES:
        raise UnsupportedSource(
            f"unsupported unary operator {dexp.name!r} in {d0exp_pretty(dexp)}")


def check_op2(dexp: D0Eop2) -> None:
    if dexp.name not in OP2_NAMES:
        raise UnsupportedSource(
            f"unsupported binary operator {dexp.name!r} in {d0exp_pretty(dexp)}")


class ValidateVisitor(D0ExpVisitor[None]):
    """Check every node, including unselected branches and unapplied
    function bodies, without evaluating anything."""

    def visit_int(self, dexp: D0Eint) -> None:
        check_int(dexp.arg1)

    def visit_btf(self, dexp: D0Ebtf) -> None:
        check_bool(dexp.arg1)

    def visit_var(self, dexp: D0Evar) -> None:
        check_name(dexp.arg1, dexp)

    def visit_op1(self, dexp: D0Eop1) -> None:
        check_op1(dexp)
        dexp.arg1.accept(self)

    def visit_op2(self, dexp: D0Eop2) -> None:
        check_op2(dexp)
        dexp.arg1.accept(self)
        dexp.arg2.accept(self)

    def visit_lam(self, dexp: D0Elam) -> None:
        check_name(dexp.arg1, dexp)
        dexp.arg2.accept(self)

    def visit_fix(self, dexp: D0Efix) -> None:
        check_name(dexp.arg1, dexp)
        check_name(dexp.arg2, dexp)
        dexp.arg3.accept(self)

    def visit_app(self, dexp: D0Eapp) -> None:
        dexp.arg1.accept(self)
        dexp.arg2.accept(self)

    def visit_if0(self, dexp: D0Eif0) -> None:
        dexp.arg1.accept(self)
        dexp.arg2.accept(self)
        dexp.arg3.accept(self)

    def visit_let(self, dexp: D0Elet) -> None:
        check_name(dexp.arg1, dexp)
        dexp.arg2.accept(self)
        dexp.arg3.accept(self)

    def visit_pair(self, dexp: D0Epair) -> None:
        dexp.arg1.accept(self)
        dexp.arg2.accept(self)

    def visit_pfst(self, dexp: D0Epfst) -> None:
        dexp.arg1.accept(self)

    def visit_psnd(self, dexp: D0Epsnd) -> None:
        dexp.arg1.accept(self)


def validate(dexp: d0exp) -> None:
    """Raise UnsupportedSource for the first unsupported node found."""
    dexp.accept(ValidateVisitor())

########################################################################
# Printing (from Assignment 5)
########################################################################

class PrettyPrintVisitor(D0ExpVisitor[str]):
    """Render an expression on one line in the assignment's exact format."""

    def visit_int(self, dexp: D0Eint) -> str:
        return str(dexp.arg1)

    def visit_btf(self, dexp: D0Ebtf) -> str:
        return "true" if dexp.arg1 else "false"

    def visit_var(self, dexp: D0Evar) -> str:
        return dexp.arg1

    def visit_op1(self, dexp: D0Eop1) -> str:
        return f"({dexp.name} {dexp.arg1.accept(self)})"

    def visit_op2(self, dexp: D0Eop2) -> str:
        return f"({dexp.arg1.accept(self)} {dexp.name} {dexp.arg2.accept(self)})"

    def visit_lam(self, dexp: D0Elam) -> str:
        return f"(lam {dexp.arg1}. {dexp.arg2.accept(self)})"

    def visit_fix(self, dexp: D0Efix) -> str:
        return f"(fix {dexp.arg1}({dexp.arg2}). {dexp.arg3.accept(self)})"

    def visit_app(self, dexp: D0Eapp) -> str:
        return f"({dexp.arg1.accept(self)} {dexp.arg2.accept(self)})"

    def visit_if0(self, dexp: D0Eif0) -> str:
        return (f"(if {dexp.arg1.accept(self)} then {dexp.arg2.accept(self)}"
                f" else {dexp.arg3.accept(self)})")

    def visit_let(self, dexp: D0Elet) -> str:
        return (f"(let {dexp.arg1} = {dexp.arg2.accept(self)}"
                f" in {dexp.arg3.accept(self)})")

    def visit_pair(self, dexp: D0Epair) -> str:
        return f"(pair {dexp.arg1.accept(self)} {dexp.arg2.accept(self)})"

    def visit_pfst(self, dexp: D0Epfst) -> str:
        return f"(fst {dexp.arg1.accept(self)})"

    def visit_psnd(self, dexp: D0Epsnd) -> str:
        return f"(snd {dexp.arg1.accept(self)})"


def d0exp_pretty(dexp: d0exp) -> str:
    """Return the single-line printed form of an expression."""
    return dexp.accept(PrettyPrintVisitor())

########################################################################
# All names and alpha-renaming (from Assignment 5)
########################################################################

class AllNamesVisitor(D0ExpVisitor[frozenset[dvar]]):
    """Collect every variable occurrence and binder name, free or bound."""

    def visit_int(self, dexp: D0Eint) -> frozenset[dvar]:
        return frozenset()

    def visit_btf(self, dexp: D0Ebtf) -> frozenset[dvar]:
        return frozenset()

    def visit_var(self, dexp: D0Evar) -> frozenset[dvar]:
        return frozenset({dexp.arg1})

    def visit_op1(self, dexp: D0Eop1) -> frozenset[dvar]:
        return dexp.arg1.accept(self)

    def visit_op2(self, dexp: D0Eop2) -> frozenset[dvar]:
        return dexp.arg1.accept(self) | dexp.arg2.accept(self)

    def visit_lam(self, dexp: D0Elam) -> frozenset[dvar]:
        return dexp.arg2.accept(self) | {dexp.arg1}

    def visit_fix(self, dexp: D0Efix) -> frozenset[dvar]:
        return dexp.arg3.accept(self) | {dexp.arg1, dexp.arg2}

    def visit_app(self, dexp: D0Eapp) -> frozenset[dvar]:
        return dexp.arg1.accept(self) | dexp.arg2.accept(self)

    def visit_if0(self, dexp: D0Eif0) -> frozenset[dvar]:
        return (dexp.arg1.accept(self) | dexp.arg2.accept(self)
                | dexp.arg3.accept(self))

    def visit_let(self, dexp: D0Elet) -> frozenset[dvar]:
        return (dexp.arg2.accept(self) | dexp.arg3.accept(self)
                | {dexp.arg1})

    def visit_pair(self, dexp: D0Epair) -> frozenset[dvar]:
        return dexp.arg1.accept(self) | dexp.arg2.accept(self)

    def visit_pfst(self, dexp: D0Epfst) -> frozenset[dvar]:
        return dexp.arg1.accept(self)

    def visit_psnd(self, dexp: D0Epsnd) -> frozenset[dvar]:
        return dexp.arg1.accept(self)


def d0exp_allnames(dexp: d0exp) -> frozenset[dvar]:
    """Return every name that appears anywhere in an expression."""
    return dexp.accept(AllNamesVisitor())


class RenameVisitor(D0ExpVisitor[d0exp]):
    """Rename the free occurrences of old to new, respecting shadowing.

    Stops below any binder that rebinds old. The caller guarantees new is
    fresh, so no binder inside the expression can capture it.
    """

    def __init__(self, old: dvar, new: dvar) -> None:
        self.old = old
        self.new = new

    def visit_int(self, dexp: D0Eint) -> d0exp:
        return dexp

    def visit_btf(self, dexp: D0Ebtf) -> d0exp:
        return dexp

    def visit_var(self, dexp: D0Evar) -> d0exp:
        return D0Evar(self.new) if dexp.arg1 == self.old else dexp

    def visit_op1(self, dexp: D0Eop1) -> d0exp:
        return D0Eop1(dexp.name, dexp.arg1.accept(self))

    def visit_op2(self, dexp: D0Eop2) -> d0exp:
        return D0Eop2(dexp.name, dexp.arg1.accept(self), dexp.arg2.accept(self))

    def visit_lam(self, dexp: D0Elam) -> d0exp:
        if dexp.arg1 == self.old:
            return dexp
        return D0Elam(dexp.arg1, dexp.arg2.accept(self))

    def visit_fix(self, dexp: D0Efix) -> d0exp:
        if self.old in (dexp.arg1, dexp.arg2):
            return dexp
        return D0Efix(dexp.arg1, dexp.arg2, dexp.arg3.accept(self))

    def visit_app(self, dexp: D0Eapp) -> d0exp:
        return D0Eapp(dexp.arg1.accept(self), dexp.arg2.accept(self))

    def visit_if0(self, dexp: D0Eif0) -> d0exp:
        return D0Eif0(dexp.arg1.accept(self), dexp.arg2.accept(self),
                      dexp.arg3.accept(self))

    def visit_let(self, dexp: D0Elet) -> d0exp:
        # The initializer is outside the let's scope, so always rename it.
        init = dexp.arg2.accept(self)
        if dexp.arg1 == self.old:
            return D0Elet(dexp.arg1, init, dexp.arg3)
        return D0Elet(dexp.arg1, init, dexp.arg3.accept(self))

    def visit_pair(self, dexp: D0Epair) -> d0exp:
        return D0Epair(dexp.arg1.accept(self), dexp.arg2.accept(self))

    def visit_pfst(self, dexp: D0Epfst) -> d0exp:
        return D0Epfst(dexp.arg1.accept(self))

    def visit_psnd(self, dexp: D0Epsnd) -> d0exp:
        return D0Epsnd(dexp.arg1.accept(self))


def d0exp_rename(dexp: d0exp, old: dvar, new: dvar) -> d0exp:
    """Rename free occurrences of old to the fresh name new."""
    return dexp.accept(RenameVisitor(old, new))

########################################################################
# Capture-avoiding substitution (from Assignment 5)
########################################################################

class SubstitutionVisitor(D0ExpVisitor[d0exp]):
    """Compute e[target := replacement] without capturing free names.

    At a binder whose scope contains a free target, any bound name that is
    free in the replacement is alpha-renamed to a fresh name first. Unchanged
    subtrees (target shadowed, or not free) are reused rather than copied.
    """

    def __init__(self, target: dvar, replacement: d0exp,
                 names: FreshNames) -> None:
        self.target = target
        self.replacement = replacement
        self.names = names
        self.replacement_fv = d0exp_fvset(replacement)

    def _needs_work(self, body: d0exp) -> bool:
        return self.target in d0exp_fvset(body)

    def _avoid(self, name: dvar) -> dvar:
        return self.names.fresh(name) if name in self.replacement_fv else name

    def visit_int(self, dexp: D0Eint) -> d0exp:
        return dexp

    def visit_btf(self, dexp: D0Ebtf) -> d0exp:
        return dexp

    def visit_var(self, dexp: D0Evar) -> d0exp:
        return self.replacement if dexp.arg1 == self.target else dexp

    def visit_op1(self, dexp: D0Eop1) -> d0exp:
        return D0Eop1(dexp.name, dexp.arg1.accept(self))

    def visit_op2(self, dexp: D0Eop2) -> d0exp:
        return D0Eop2(dexp.name, dexp.arg1.accept(self), dexp.arg2.accept(self))

    def visit_lam(self, dexp: D0Elam) -> d0exp:
        name, body = dexp.arg1, dexp.arg2
        if name == self.target or not self._needs_work(body):
            return dexp
        new = self._avoid(name)
        if new != name:
            body = d0exp_rename(body, name, new)
        return D0Elam(new, body.accept(self))

    def visit_fix(self, dexp: D0Efix) -> d0exp:
        fname, param, body = dexp.arg1, dexp.arg2, dexp.arg3
        if self.target in (fname, param) or not self._needs_work(body):
            return dexp
        if fname == param:
            # The parameter shadows the function name, so every body
            # occurrence is the parameter; keep both binders identical.
            new = self._avoid(param)
            if new != param:
                body = d0exp_rename(body, param, new)
            return D0Efix(new, new, body.accept(self))
        new_f = self._avoid(fname)
        new_p = self._avoid(param)
        if new_f != fname:
            body = d0exp_rename(body, fname, new_f)
        if new_p != param:
            body = d0exp_rename(body, param, new_p)
        return D0Efix(new_f, new_p, body.accept(self))

    def visit_app(self, dexp: D0Eapp) -> d0exp:
        return D0Eapp(dexp.arg1.accept(self), dexp.arg2.accept(self))

    def visit_if0(self, dexp: D0Eif0) -> d0exp:
        return D0Eif0(dexp.arg1.accept(self), dexp.arg2.accept(self),
                      dexp.arg3.accept(self))

    def visit_let(self, dexp: D0Elet) -> d0exp:
        name, body = dexp.arg1, dexp.arg3
        # The initializer is outside the let's scope: always substitute.
        init = dexp.arg2.accept(self)
        if name == self.target or not self._needs_work(body):
            return D0Elet(name, init, body)
        new = self._avoid(name)
        if new != name:
            body = d0exp_rename(body, name, new)
        return D0Elet(new, init, body.accept(self))

    def visit_pair(self, dexp: D0Epair) -> d0exp:
        return D0Epair(dexp.arg1.accept(self), dexp.arg2.accept(self))

    def visit_pfst(self, dexp: D0Epfst) -> d0exp:
        return D0Epfst(dexp.arg1.accept(self))

    def visit_psnd(self, dexp: D0Epsnd) -> d0exp:
        return D0Epsnd(dexp.arg1.accept(self))


def d0exp_substitute(dexp: d0exp, variable: dvar, replacement: d0exp) -> d0exp:
    """Return dexp[variable := replacement], avoiding variable capture.

    Fresh names avoid every name in dexp and replacement, the target, and
    names generated earlier in this call (see FreshNames).
    """
    used = d0exp_allnames(dexp) | d0exp_allnames(replacement) | {variable}
    return dexp.accept(SubstitutionVisitor(variable, replacement, FreshNames(used)))
