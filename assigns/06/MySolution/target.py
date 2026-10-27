from __future__ import annotations

########################################################################
########################################################################
# The pure lambda-calculus target language:
#
#     Term ::= Var(name) | Lam(name, Term) | App(Term, Term)
#
# Printing, free variables, renaming, capture-avoiding substitution,
# alpha-equivalence, and a purity check. Nodes are frozen and no
# operation mutates its input; unchanged subtrees are shared.
#
# FreshNames, rename, and substitute adapt Andres Lopez's Assignment 5
# solution (../../05/MySolution/lambda1_visitors.py) from the source AST
# to this three-form AST, with the same fresh-name policy.
# Requires Python 3.12 or later.
########################################################################
########################################################################
from dataclasses import dataclass


@dataclass(frozen=True)
class Var:
    name: str


@dataclass(frozen=True)
class Lam:
    param: str
    body: Term


@dataclass(frozen=True)
class App:
    fn: Term
    arg: Term


type Term = Var | Lam | App
TERM_TYPES = (Var, Lam, App)

########################################################################
# Printing and name analysis
########################################################################

def pretty(term: Term) -> str:
    """Render x, (lam x. body), and (fn arg), recursively."""
    match term:
        case Var(name):
            return name
        case Lam(param, body):
            return f"(lam {param}. {pretty(body)})"
        case App(fn, arg):
            return f"({pretty(fn)} {pretty(arg)})"


def free_vars(term: Term) -> frozenset[str]:
    """Return the names occurring free in term."""
    match term:
        case Var(name):
            return frozenset({name})
        case Lam(param, body):
            return free_vars(body) - {param}
        case App(fn, arg):
            return free_vars(fn) | free_vars(arg)


def all_names(term: Term) -> frozenset[str]:
    """Return every variable occurrence and binder name, free or bound."""
    match term:
        case Var(name):
            return frozenset({name})
        case Lam(param, body):
            return all_names(body) | {param}
        case App(fn, arg):
            return all_names(fn) | all_names(arg)


def is_pure(term: object) -> bool:
    """True when every node is Var, Lam, or App with string names."""
    pending = [term]
    while pending:
        match pending.pop():
            case Var(name) if isinstance(name, str):
                pass
            case Lam(param, body) if isinstance(param, str):
                pending.append(body)
            case App(fn, arg):
                pending.append(arg)
                pending.append(fn)
            case _:
                return False
    return True

########################################################################
# Fresh names and alpha-renaming
########################################################################

class FreshNames:
    """Deterministic fresh-name supply for one substitution call.

    fresh(base) returns base_1, base_2, ... -- the first candidate not yet
    used. Generated names are recorded, so later requests skip them.
    """

    def __init__(self, used: frozenset[str]) -> None:
        self.used = set(used)

    def fresh(self, base: str) -> str:
        k = 1
        while f"{base}_{k}" in self.used:
            k += 1
        name = f"{base}_{k}"
        self.used.add(name)
        return name


def rename(term: Term, old: str, new: str) -> Term:
    """Rename the free occurrences of old to new, respecting shadowing.

    The caller guarantees new is fresh, so no binder in term captures it.
    """
    match term:
        case Var(name):
            return Var(new) if name == old else term
        case Lam(param, body):
            if param == old:
                return term
            new_body = rename(body, old, new)
            return term if new_body is body else Lam(param, new_body)
        case App(fn, arg):
            new_fn, new_arg = rename(fn, old, new), rename(arg, old, new)
            if new_fn is fn and new_arg is arg:
                return term
            return App(new_fn, new_arg)

########################################################################
# Capture-avoiding substitution
########################################################################

class _Substitution:
    """State for one call: target, replacement, and a lazy name supply.

    A binder is renamed only when it is free in the replacement and the
    target is free in its body. A closed replacement therefore never
    renames, and the supply (a scan of every name in the term and the
    replacement) is built only on the first renaming. It sees the same
    names whenever it is built, so results stay deterministic.
    """

    def __init__(self, term: Term, target: str, replacement: Term) -> None:
        self.term = term
        self.target = target
        self.replacement = replacement
        self.replacement_fv = free_vars(replacement)
        self.names: FreshNames | None = None

    def fresh(self, base: str) -> str:
        if self.names is None:
            self.names = FreshNames(all_names(self.term)
                                    | all_names(self.replacement)
                                    | {self.target})
        return self.names.fresh(base)

    def apply(self, term: Term) -> Term:
        match term:
            case Var(name):
                return self.replacement if name == self.target else term
            case Lam(param, body):
                if param == self.target:
                    return term
                if param in self.replacement_fv and self.target in free_vars(body):
                    new = self.fresh(param)
                    return Lam(new, self.apply(rename(body, param, new)))
                new_body = self.apply(body)
                return term if new_body is body else Lam(param, new_body)
            case App(fn, arg):
                new_fn, new_arg = self.apply(fn), self.apply(arg)
                if new_fn is fn and new_arg is arg:
                    return term
                return App(new_fn, new_arg)


def substitute(term: Term, target: str, replacement: Term) -> Term:
    """Return term[target := replacement], avoiding variable capture.

    Works on open terms. Fresh names avoid every name in term and
    replacement, the target, and names generated earlier in this call.
    """
    return _Substitution(term, target, replacement).apply(term)

########################################################################
# Alpha-equivalence
########################################################################

def alpha_eq(left: Term, right: Term) -> bool:
    """True when the terms differ only in the names of bound variables."""
    return _alpha_eq(left, right, {}, {}, 0)


def _alpha_eq(left: Term, right: Term,
              lenv: dict[str, int], renv: dict[str, int], depth: int) -> bool:
    # Each environment maps a bound name to the depth of its binder.
    match left, right:
        case Var(lname), Var(rname):
            lbind, rbind = lenv.get(lname), renv.get(rname)
            if lbind is None and rbind is None:
                return lname == rname
            return lbind == rbind
        case Lam(lparam, lbody), Lam(rparam, rbody):
            return _alpha_eq(lbody, rbody, {**lenv, lparam: depth},
                             {**renv, rparam: depth}, depth + 1)
        case App(lfn, larg), App(rfn, rarg):
            return (_alpha_eq(lfn, rfn, lenv, renv, depth)
                    and _alpha_eq(larg, rarg, lenv, renv, depth))
        case _:
            return False
