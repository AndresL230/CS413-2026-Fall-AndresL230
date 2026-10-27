from __future__ import annotations

########################################################################
########################################################################
# Compositional compiler from extended LAMBDA source ASTs to pure
# lambda terms, written as a D0ExpVisitor. Each visit method combines
# the translations of the node's children. Nothing is evaluated, and
# this module never imports the evaluator.
#
#   C[x]                  = x
#   C[lam x. e]           = lam x. C[e]
#   C[e1 e2]              = C[e1] C[e2]
#   C[let x = e1 in e2]   = (lam x. C[e2]) C[e1]
#   C[if c then t else f] = (C[c] (lam u. C[t]) (lam v. C[f])) I
#   C[e1 and e2]          = (C[e1] (lam u. C[e2]) (lam v. FALSE)) I
#   C[e1 or e2]           = (C[e1] (lam u. TRUE) (lam v. C[e2])) I
#   C[fix f(x). e]        = Z (lam f. lam x. C[e])
#   C[n]                  = NUM(n)            C[true/false] = TRUE/FALSE
#   C[e1 op e2]           = OP C[e1] C[e2]    for + - * < <= > >= == !=
#   C[not e]              = NOT C[e]
#   C[pair e1 e2]         = PAIR C[e1] C[e2]
#   C[fst e] = FST C[e]   C[snd e] = SND C[e]
#
# Library terms are closed and appear only as whole subterms, so their
# binders never surround translated code. The only compiler-introduced
# binders around translated code are the thunk parameters u and v. Each
# is the first of base, base_1, base_2, ... that is not among all the
# names (free or bound) of the term it wraps. So the thunk binds nothing
# its body mentions, and FV(C[e]) = FV(e).
#
# Source `and`/`or` must never compile to the strict church.AND/OR:
# call-by-value would evaluate both operands.
# Requires Python 3.12 or later.
########################################################################
########################################################################
import church
from source import (
    D0ExpVisitor, D0E000, d0exp,
    D0Eint, D0Ebtf, D0Eop1, D0Eop2, D0Evar, D0Elam, D0Efix,
    D0Eapp, D0Eif0, D0Elet, D0Epair, D0Epfst, D0Epsnd,
    UnsupportedSource, BOOL_OPS,
    check_name, check_int, check_bool, check_op1, check_op2,
)
from target import Term, Var, Lam, App, all_names


class CompileError(Exception):
    """The source AST contains an unsupported literal, operator, or name."""


STRICT_OP2: dict[str, Term] = {
    "+": church.ADD, "-": church.SUB, "*": church.MUL,
    "<": church.LT, "<=": church.LEQ, ">": church.GT, ">=": church.GEQ,
    "==": church.EQ, "!=": church.NEQ,
}


def fresh_for(base: str, term: Term) -> str:
    """First of base, base_1, base_2, ... not among term's names."""
    names = all_names(term)
    if base not in names:
        return base
    k = 1
    while f"{base}_{k}" in names:
        k += 1
    return f"{base}_{k}"


def _thunk(base: str, body: Term) -> Term:
    return Lam(fresh_for(base, body), body)


def _select(cond: Term, if_true: Term, if_false: Term) -> Term:
    """(cond (lam u. if_true) (lam v. if_false)) I: force only the
    branch the Church boolean selects."""
    return App(App(App(cond, _thunk("u", if_true)), _thunk("v", if_false)),
               church.I)


class CompileVisitor(D0ExpVisitor[Term]):
    """Translate one source node by combining its children's translations."""

    def visit_int(self, dexp: D0Eint) -> Term:
        check_int(dexp.arg1)
        return church.num(dexp.arg1)

    def visit_btf(self, dexp: D0Ebtf) -> Term:
        check_bool(dexp.arg1)
        return church.TRUE if dexp.arg1 else church.FALSE

    def visit_var(self, dexp: D0Evar) -> Term:
        check_name(dexp.arg1, dexp)
        return Var(dexp.arg1)

    def visit_lam(self, dexp: D0Elam) -> Term:
        check_name(dexp.arg1, dexp)
        return Lam(dexp.arg1, dexp.arg2.accept(self))

    def visit_app(self, dexp: D0Eapp) -> Term:
        return App(dexp.arg1.accept(self), dexp.arg2.accept(self))

    def visit_let(self, dexp: D0Elet) -> Term:
        check_name(dexp.arg1, dexp)
        init = dexp.arg2.accept(self)
        return App(Lam(dexp.arg1, dexp.arg3.accept(self)), init)

    def visit_if0(self, dexp: D0Eif0) -> Term:
        return _select(dexp.arg1.accept(self), dexp.arg2.accept(self),
                       dexp.arg3.accept(self))

    def visit_fix(self, dexp: D0Efix) -> Term:
        # When the names coincide, lam f. lam f. C[e] already lets the
        # parameter shadow the function name.
        check_name(dexp.arg1, dexp)
        check_name(dexp.arg2, dexp)
        return App(church.Z,
                   Lam(dexp.arg1, Lam(dexp.arg2, dexp.arg3.accept(self))))

    def visit_op1(self, dexp: D0Eop1) -> Term:
        check_op1(dexp)
        return App(church.NOT, dexp.arg1.accept(self))

    def visit_op2(self, dexp: D0Eop2) -> Term:
        check_op2(dexp)
        left, right = dexp.arg1.accept(self), dexp.arg2.accept(self)
        if dexp.name in BOOL_OPS:
            if dexp.name == "and":
                return _select(left, right, church.FALSE)
            return _select(left, church.TRUE, right)
        return App(App(STRICT_OP2[dexp.name], left), right)

    def visit_pair(self, dexp: D0Epair) -> Term:
        return App(App(church.PAIR, dexp.arg1.accept(self)),
                   dexp.arg2.accept(self))

    def visit_pfst(self, dexp: D0Epfst) -> Term:
        return App(church.FST, dexp.arg1.accept(self))

    def visit_psnd(self, dexp: D0Epsnd) -> Term:
        return App(church.SND, dexp.arg1.accept(self))


def compile_expr(dexp: d0exp) -> Term:
    """Compile a source AST (open or closed) to a pure target term.

    Raises CompileError for unsupported input anywhere in the tree,
    including unselected branches and unapplied function bodies.
    """
    if not isinstance(dexp, D0E000):
        raise CompileError(f"not a source AST: {dexp!r}")
    try:
        return dexp.accept(CompileVisitor())
    except UnsupportedSource as err:
        raise CompileError(str(err)) from err
