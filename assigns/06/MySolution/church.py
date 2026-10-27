from __future__ import annotations

########################################################################
########################################################################
# Church-encoding library: closed, pure target terms.
#
#   TRUE   = lam t. lam f. t
#   FALSE  = lam t. lam f. f
#   NUM(n) = lam s. lam z. s (s ... (s z))        (n applications)
#   PAIR   = lam a. lam b. lam p. p a b
#   Z      = lam g. (lam x. g (lam v. x x v)) (lam x. g (lam v. x x v))
#
# These names are Python builder names, not target primitives: each is
# a complete closed Term, and a combinator that uses another contains a
# copy of it. Because every combinator is closed, its binders scope only
# over its own body and cannot capture names in the terms it is applied
# to.
#
# AND and OR here are strict: under call-by-value both operands are
# evaluated before the call. They are for use inside the library (EQ).
# The compiler must translate source `and`/`or` with delayed thunks
# instead, never as AND C[e1] C[e2] (see DESIGN.md).
#
# Encodings follow the standard presentations in Pierce, "Types and
# Programming Languages" (2002), section 5.2.
# Requires Python 3.12 or later.
########################################################################
########################################################################
from target import Term, Var, Lam, App


def _lam(*parts: str | Term) -> Term:
    """_lam("a", "b", body) == lam a. lam b. body."""
    *params, body = parts
    for param in reversed(params):
        body = Lam(param, body)
    return body


def _app(*terms: Term) -> Term:
    """_app(f, a, b) == ((f a) b)."""
    result = terms[0]
    for term in terms[1:]:
        result = App(result, term)
    return result


a, b, f, g, m, n, p, q, s, t, v, w, x, z = map(Var, "abfgmnpqstvwxz")

########################################################################
# Booleans, identity, and numerals
########################################################################

TRUE = _lam("t", "f", t)
FALSE = _lam("t", "f", f)
I = _lam("w", w)


def num(k: int) -> Term:
    """NUM(k) for a natural number k. Builds a literal only; no target
    arithmetic is performed here."""
    if type(k) is not int:
        raise TypeError(f"numeral must be an int, got {k!r}")
    if k < 0:
        raise ValueError(f"numeral must be nonnegative, got {k}")
    body: Term = z
    for _ in range(k):
        body = App(s, body)
    return _lam("s", "z", body)


ZERO = num(0)

########################################################################
# Pairs
########################################################################

PAIR = _lam("a", "b", "p", _app(p, a, b))
FST = _lam("p", App(p, TRUE))
SND = _lam("p", App(p, FALSE))

########################################################################
# Arithmetic
########################################################################

SUCC = _lam("n", "s", "z", App(s, _app(n, s, z)))
ISZERO = _lam("n", _app(n, _lam("w", FALSE), TRUE))

# Predecessor by pair shifting: starting from (0, 0), apply
#   SHIFT (a, b) = (b, b + 1)
# n times to get (n - 1, n) when n > 0, or (0, 0) when n = 0; then take
# the first component. Every argument is already a value, so this is
# safe under call-by-value, and PRED 0 = 0.
SHIFT = _lam("p", _app(PAIR, App(SND, p), App(SUCC, App(SND, p))))
PRED = _lam("n", App(FST, _app(n, SHIFT, _app(PAIR, ZERO, ZERO))))

ADD = _lam("m", "n", "s", "z", _app(m, s, _app(n, s, z)))
SUB = _lam("m", "n", _app(n, PRED, m))        # truncated: m - n >= 0
MUL = _lam("m", "n", "s", App(m, App(n, s)))

########################################################################
# Boolean operations (strict; library use only, see header)
########################################################################

NOT = _lam("p", _app(p, FALSE, TRUE))
AND = _lam("p", "q", _app(p, q, FALSE))
OR = _lam("p", "q", _app(p, TRUE, q))

########################################################################
# Comparisons
########################################################################

LEQ = _lam("m", "n", App(ISZERO, _app(SUB, m, n)))  # m <= n iff m - n = 0
GEQ = _lam("m", "n", _app(LEQ, n, m))
LT = _lam("m", "n", App(NOT, _app(LEQ, n, m)))       # m < n iff not n <= m
GT = _lam("m", "n", App(NOT, _app(LEQ, m, n)))
EQ = _lam("m", "n", _app(AND, _app(LEQ, m, n), _app(LEQ, n, m)))
NEQ = _lam("m", "n", App(NOT, _app(EQ, m, n)))

########################################################################
# Call-by-value fixed point
########################################################################

_Z_HALF = _lam("x", App(g, _lam("v", _app(x, x, v))))
Z = _lam("g", App(_Z_HALF, _Z_HALF))

COMBINATORS: dict[str, Term] = {
    "TRUE": TRUE, "FALSE": FALSE, "I": I, "ZERO": ZERO,
    "PAIR": PAIR, "FST": FST, "SND": SND,
    "SUCC": SUCC, "ISZERO": ISZERO, "SHIFT": SHIFT, "PRED": PRED,
    "ADD": ADD, "SUB": SUB, "MUL": MUL,
    "NOT": NOT, "AND": AND, "OR": OR,
    "LEQ": LEQ, "GEQ": GEQ, "LT": LT, "GT": GT, "EQ": EQ, "NEQ": NEQ,
    "Z": Z,
}
