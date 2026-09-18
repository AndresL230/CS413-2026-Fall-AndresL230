#!/usr/bin/env python3
#
# Copyright (C) 2011 Hongwei Xi, ATS Trustful Software, Inc.
#
# Permission is hereby granted, free of charge, to any person
# obtaining a copy of this software and associated documentation
# files (the "Software"), to deal in the Software without
# restriction, including without limitation the rights to use,
# copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the
# Software is furnished to do so, subject to the following
# conditions:
#
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES
# OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
# NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT
# HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
# WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
# FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR
# OTHER DEALINGS IN THE SOFTWARE.
#
"""
queens.py -- Python 3 translation of queens.dats (ATS2).

Example: Eight Queens Puzzle

Original author: Hongwei Xi (January, 2011)
Ported to ATS2 by Hongwei Xi (March 24, 2013)

The board (ATS type ``int8``) is a tuple of 8 ints: ``bd[r]`` is the
column of the queen in row ``r``. Boards are immutable, as in the
original. ``board_set`` returns a new tuple.

The ATS functions ``print_dots``, ``safety_test2``, and ``search`` are
tail-recursive, and the ATS compiler turns them into loops. ``search``
makes far more nested calls than Python's default recursion limit
allows, so these functions are written as loops here. They take the
same parameters and go through the same sequence of states.
"""

import signal
import sys

N = 8  # HX: this should not be changed!


def assertloc(cond):
    """ATS's assertloc: if cond is false, print where the check is and exit with code 1.

    Like ATS, it prints only the location, with no newline. Unlike an assert
    statement, it is not removed by `python -O`.
    """
    if not cond:
        caller = sys._getframe(1)
        sys.stdout.flush()
        sys.stderr.write(f"{caller.f_code.co_filename}: line {caller.f_lineno}")
        sys.exit(1)


def print_dots(i):
    """Print ". " i times (nothing if i <= 0)."""
    while i > 0:
        sys.stdout.write(". ")
        i = i - 1


def print_row(i):
    """Print one board row with the queen in column i."""
    print_dots(i)
    sys.stdout.write("Q ")
    print_dots(N - i - 1)
    sys.stdout.write("\n")


def print_board(bd):
    """Print all 8 rows of the board, then an empty line."""
    print_row(bd[0])
    print_row(bd[1])
    print_row(bd[2])
    print_row(bd[3])
    print_row(bd[4])
    print_row(bd[5])
    print_row(bd[6])
    print_row(bd[7])
    # print_newline () in ATS prints '\n' and flushes stdout.
    sys.stdout.write("\n")
    sys.stdout.flush()


def board_get(bd, i):
    """Return bd[i] for 0 <= i <= 7, or 0 for any other i."""
    if 0 <= i < N:
        return bd[i]
    return 0


def board_set(bd, i, j):
    """Return a new board with position i set to j.

    If i is not in 0..7, return bd unchanged.
    """
    if 0 <= i < N:
        x = list(bd)
        x[i] = j
        return tuple(x)
    return bd


def safety_test1(i0, j0, i, j):
    """Return True if queens at (i0, j0) and (i, j) do not attack.

    They must be in different columns and not on the same diagonal.
    """
    return j0 != j and abs(i0 - i) != abs(j0 - j)


def safety_test2(i0, j0, bd, i):
    """Return True if a queen at (i0, j0) is safe from rows i down to 0."""
    while i >= 0:
        if safety_test1(i0, j0, i, board_get(bd, i)):
            i = i - 1
        else:
            return False
    return True


def search(bd, i, j, nsol):
    """Backtracking search for every solution.

    Each solution is printed when found. Returns the total number of
    solutions found (nsol plus the number found by this search).
    """
    while True:
        if j < N:
            test = safety_test2(i, j, bd, i - 1)
            if test:
                bd1 = board_set(bd, i, j)
                if i + 1 == N:
                    sys.stdout.write("Solution #" + str(nsol + 1) + ":\n\n")
                    print_board(bd1)
                    # search (bd, i, j+1, nsol+1)
                    bd, i, j, nsol = bd, i, j + 1, nsol + 1
                else:
                    # search (bd1, i+1, 0, nsol): place the next queen
                    bd, i, j, nsol = bd1, i + 1, 0, nsol
            else:
                # search (bd, i, j+1, nsol)
                bd, i, j, nsol = bd, i, j + 1, nsol
        else:
            if i > 0:
                # search (bd, i-1, board_get (bd, i-1) + 1, nsol)
                bd, i, j, nsol = bd, i - 1, board_get(bd, i - 1) + 1, nsol
            else:
                return nsol


def main0():
    """Do what main0 does in queens.dats."""
    print_board((0, 1, 2, 3, 4, 5, 6, 7))

    nsol = search((0, 0, 0, 0, 0, 0, 0, 0), 0, 0, 0)

    assertloc(nsol == 92)


if __name__ == "__main__":
    # Like the compiled ATS program, stop quietly when the reader of the output
    # goes away (e.g. `| head`), instead of printing a BrokenPipeError traceback.
    # Done here, not at import, so importing this file changes no signal handling.
    if hasattr(signal, "SIGPIPE"):
        signal.signal(signal.SIGPIPE, signal.SIG_DFL)
    main0()
