"""Eight queens (queens.dats) translated into a LAMBDA0 term.

Run with: python3 queens_lambda0.py [N]      (N defaults to 8)

The ATS2 source is queens.dats in this directory. Every ATS function used
by the search becomes a closed LAMBDA0 function, and the search itself
runs inside t0erm_cbv_evaluate0. The Python code below only builds ASTs
and decodes/prints the value the interpreter returns.

Representations
---------------
* int8 board     : nested pairs  (q0, (q1, ... (q_{N-1}, 0)))
                   (the final 0 is a terminator that is never read)
* multi-argument : curried; f(a, b, c) becomes ((f a) b) c
* let x = e in b : (lam x. b) e for the top-level definitions; the
                   [test] and [bd1] lets in [search] are inlined instead
* abs, andalso   : T0Mif0 expressions (andalso keeps its short-circuit)
* nsol           : accumulator pair (count, solutions) where solutions is
                   a list built from pairs, (board, rest), ended by 0,
                   newest solution first. ATS prints each solution as it is
                   found; a LAMBDA0 term cannot print, so it collects them.
* N              : bound by an outer let so smaller boards can be tested;
                   the driver uses N = 8, as in the ATS program.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lambda0 import (
    T0Mint, T0Mbtf, T0Mvar, T0Mlam, T0Mfix, T0Mapp, T0Mif0, T0Mop1, T0Mop2,
    T0Mpair, T0Mpfst, T0Mpsnd, t0erm_fvset, t0erm_cbv_evaluate0,
)

# The search nests one interpreter call per ATS [search] call (no tail calls).
RECURSION_LIMIT = 1_000_000

########################################################################
# AST-building shorthands (construction only; no evaluation happens here)

def V(x): return T0Mvar(x)
def I(n): return T0Mint(n)

def app(f, *args):
    for a in args:
        f = T0Mapp(f, a)
    return f

def lam(params, body):
    for x in reversed(params):
        body = T0Mlam(x, body)
    return body

def fix(f, params, body):
    # A curried recursive function: fix f(p0). lam p1. ... body
    return T0Mfix(f, params[0], lam(params[1:], body))

def call(f, *args): return app(V(f), *args)

def let(x, e, body): return T0Mapp(T0Mlam(x, body), e)
def if_(c, t, e): return T0Mif0(c, t, e)
def op(o, a, b): return T0Mop2(o, a, b)

TRUE, FALSE = T0Mbtf(True), T0Mbtf(False)

########################################################################
# Translated functions. Each is closed except for the names bound
# earlier in [with_program], which are substituted before it is used.

# abs(x) = if x < 0 then -x else x
ABS = T0Mlam("x", if_(op("<", V("x"), I(0)), T0Mop1("-", V("x")), V("x")))

# board_get(bd, i): walk i steps down the nested pairs.
BOARD_GET = fix("board_get", ["bd", "i"],
    if_(op("==", V("i"), I(0)),
        T0Mpfst(V("bd")),
        call("board_get", T0Mpsnd(V("bd")), op("-", V("i"), I(1)))))

# board_set(bd, i, j): rebuild the board with position i replaced by j.
BOARD_SET = fix("board_set", ["bd", "i", "j"],
    if_(op("==", V("i"), I(0)),
        T0Mpair(V("j"), T0Mpsnd(V("bd"))),
        T0Mpair(T0Mpfst(V("bd")),
                call("board_set", T0Mpsnd(V("bd")), op("-", V("i"), I(1)), V("j")))))

# The initial board (0, 0, ..., 0) of length n (main0 writes it literally).
MAKE_BOARD = T0Mfix("make_board", "n",
    if_(op("<=", V("n"), I(0)),
        I(0),
        T0Mpair(I(0), app(V("make_board"), op("-", V("n"), I(1))))))

# safety_test1(i0, j0, i, j) = j0 <> j andalso abs(i0-i) <> abs(j0-j)
SAFETY_TEST1 = lam(["i0", "j0", "i", "j"],
    if_(op("!=", V("j0"), V("j")),
        op("!=", app(V("abs"), op("-", V("i0"), V("i"))),
                 app(V("abs"), op("-", V("j0"), V("j")))),
        FALSE))

# safety_test2(i0, j0, bd, i): queen (i0, j0) is safe w.r.t. rows i, i-1, ..., 0
SAFETY_TEST2 = fix("safety_test2", ["i0", "j0", "bd", "i"],
    if_(op(">=", V("i"), I(0)),
        if_(call("safety_test1", V("i0"), V("j0"), V("i"),
                 call("board_get", V("bd"), V("i"))),
            call("safety_test2", V("i0"), V("j0"), V("bd"), op("-", V("i"), I(1))),
            FALSE),
        TRUE))

# search(bd, i, j, acc) where acc = (nsol, solutions); see queens.dats.
# ATS binds [test] and [bd1] with lets; they are inlined here so that each
# step does not substitute through the body (and the solution list) again.
# Each is still evaluated at most once on any path, as in ATS.
BD1 = call("board_set", V("bd"), V("i"), V("j"))
SEARCH = fix("search", ["bd", "i", "j", "acc"],
    if_(op("<", V("j"), V("N")),
        if_(call("safety_test2", V("i"), V("j"), V("bd"), op("-", V("i"), I(1))),
            if_(op("==", op("+", V("i"), I(1)), V("N")),
                # Solution found: record bd1 (ATS prints it here).
                call("search", V("bd"), V("i"), op("+", V("j"), I(1)),
                     T0Mpair(op("+", T0Mpfst(V("acc")), I(1)),
                             T0Mpair(BD1, T0Mpsnd(V("acc"))))),
                # Positioning the next piece.
                call("search", BD1, op("+", V("i"), I(1)), I(0), V("acc"))),
            call("search", V("bd"), V("i"), op("+", V("j"), I(1)), V("acc"))),
        if_(op(">", V("i"), I(0)),
            call("search", V("bd"), op("-", V("i"), I(1)),
                 op("+", call("board_get", V("bd"), op("-", V("i"), I(1))), I(1)),
                 V("acc")),
            V("acc"))))

# Definitions in dependency order; each may use the names before it.
PROGRAM = [
    ("abs", ABS),
    ("board_get", BOARD_GET),
    ("board_set", BOARD_SET),
    ("make_board", MAKE_BOARD),
    ("safety_test1", SAFETY_TEST1),
    ("safety_test2", SAFETY_TEST2),
    ("search", SEARCH),
]

def with_program(body, n=8):
    """Wrap [body] in lets binding N and every translated function.

    The result is a single closed term (provided body only uses those names).
    """
    for name, defn in reversed(PROGRAM):
        body = let(name, defn, body)
    return let("N", I(n), body)

def queens_term(n=8):
    """main0: search((0, ..., 0), 0, 0, (0, nil)), as one closed term."""
    return with_program(
        call("search", app(V("make_board"), V("N")), I(0), I(0),
             T0Mpair(I(0), I(0))),
        n)

########################################################################
# Decoding and display (Python side; no searching)

def evaluate(term):
    assert t0erm_fvset(term) == frozenset(), "term must be closed"
    sys.setrecursionlimit(max(sys.getrecursionlimit(), RECURSION_LIMIT))
    return t0erm_cbv_evaluate0(term)

def decode_board(value, n):
    board = []
    for _ in range(n):
        board.append(value.arg1.arg1)
        value = value.arg2
    return tuple(board)

def decode_result(value, n):
    """(count, solutions) -> (int, list of boards in discovery order)."""
    count = value.arg1.arg1
    sols, rest = [], value.arg2
    while isinstance(rest, T0Mpair):
        sols.append(decode_board(rest.arg1, n))
        rest = rest.arg2
    sols.reverse()
    return count, sols

def solve(n=8):
    return decode_result(evaluate(queens_term(n)), n)

def board_to_text(board):
    # Same layout as print_board in queens.dats.
    n = len(board)
    return "".join(". " * q + "Q " + ". " * (n - q - 1) + "\n" for q in board) + "\n"

def main(argv):
    n = int(argv[1]) if len(argv) > 1 else 8
    count, sols = solve(n)
    for k, board in enumerate(sols, 1):
        print(f"Solution #{k}:\n")
        print(board_to_text(board), end="")
    print(f"Total: {count} solutions for N = {n}")

if __name__ == "__main__":
    main(sys.argv)
