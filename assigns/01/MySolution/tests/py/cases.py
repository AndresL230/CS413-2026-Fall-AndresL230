"""My Python side of the function-by-function test.

This is the twin of tests/ats/cases.dats. Same inputs, same printing, so the
two outputs can be compared byte for byte (tests/test_regression.py does the
comparing, against tests/expected/cases.out). TESTING.md says what each case
checks and why.

Each case prints:
    ### <id> <call>
    <whatever the function printed>
    => <return value>

I build the header out of the real arguments, so it can't end up describing a
different call than the one I make. I also call the function on its own line
before printing anything about the result, because ATS and Python don't run
the arguments of a print in the same order.

If a function hands back the wrong type I print "<not a ...: value>", so a
wrong type can't quietly look correct.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "translation"))

import queens  # noqa: E402


# How I print each kind of return value, to match what the ATS side prints.
def show_int(v):
    return str(v) if type(v) is int else f"<not an int: {v!r}>"


def show_bool(v):
    if type(v) is not bool:
        return f"<not a bool: {v!r}>"
    return "true" if v else "false"


def show_unit(v):
    return "()" if v is None else f"<not None: {v!r}>"


def show_board(v):
    if type(v) is not tuple or len(v) != 8 or any(type(x) is not int for x in v):
        return f"<not a board of 8 ints: {v!r}>"
    return "(" + ", ".join(str(x) for x in v) + ")"


# print_dots never ends its line, so this runner does.
def case_print_dots(cid, i):
    print(f"### {cid} print_dots({i})")
    r = queens.print_dots(i)
    print()
    print(f"=> {show_unit(r)}")


def case_print_row(cid, i):
    print(f"### {cid} print_row({i})")
    r = queens.print_row(i)
    print(f"=> {show_unit(r)}")


def case_print_board(cid, bd):
    print(f"### {cid} print_board({show_board(bd)})")
    r = queens.print_board(bd)
    print(f"=> {show_unit(r)}")


def case_board_get(cid, bd, i):
    print(f"### {cid} board_get({show_board(bd)}, {i})")
    r = queens.board_get(bd, i)
    print(f"=> {show_int(r)}")


def case_board_set(cid, bd, i, j):
    print(f"### {cid} board_set({show_board(bd)}, {i}, {j})")
    r = queens.board_set(bd, i, j)
    print(f"=> {show_board(r)}")


def case_safety_test1(cid, i0, j0, i, j):
    print(f"### {cid} safety_test1({i0}, {j0}, {i}, {j})")
    r = queens.safety_test1(i0, j0, i, j)
    print(f"=> {show_bool(r)}")


def case_safety_test2(cid, i0, j0, bd, i):
    print(f"### {cid} safety_test2({i0}, {j0}, {show_board(bd)}, {i})")
    r = queens.safety_test2(i0, j0, bd, i)
    print(f"=> {show_bool(r)}")


def case_search(cid, bd, i, j, nsol):
    print(f"### {cid} search({show_board(bd)}, {i}, {j}, {nsol})")
    r = queens.search(bd, i, j, nsol)
    print(f"=> {show_int(r)}")


def main():
    sol1 = (0, 4, 7, 5, 2, 6, 1, 3)  # Solution #1
    zeros = (0, 0, 0, 0, 0, 0, 0, 0)

    # printing
    case_print_dots("P1", 0)
    case_print_dots("P2", 3)
    case_print_dots("P3", -3)
    case_print_row("P4", 0)
    case_print_row("P5", 7)
    case_print_board("P6", sol1)

    # reading and writing a board, including rows that don't exist
    for i in range(8):
        case_board_get(f"G1.{i}", sol1, i)
    case_board_get("G2", sol1, 8)
    case_board_get("G3", sol1, -1)

    case_board_set("S1", sol1, 3, 6)
    case_board_set("S2", sol1, 7, 0)
    case_board_set("S3", sol1, 8, 5)
    case_board_set("S4", sol1, -1, 5)

    # are two queens safe from each other, and is a queen safe from the rows above
    case_safety_test1("T1", 0, 0, 1, 2)
    case_safety_test1("T2", 0, 3, 5, 3)
    case_safety_test1("T3", 2, 2, 5, 5)
    case_safety_test1("T4", 5, 1, 2, 4)
    case_safety_test1("T5", 3, 3, 3, 3)
    case_safety_test2("T6", 7, 3, sol1, 6)
    case_safety_test2("T7", 3, 4, sol1, 2)
    case_safety_test2("T8", 0, 5, zeros, -1)

    # the search itself; R5 counts the solutions from each starting column
    case_search("R2", zeros, 0, 8, 0)
    case_search("R3", zeros, 0, 7, 10)
    case_search("R4", zeros, 1, 0, 0)
    for c in range(8):
        case_search(f"R5.{c}", zeros, 0, c, 0)


if __name__ == "__main__":
    main()
