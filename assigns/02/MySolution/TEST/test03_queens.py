"""Tests for the eight-queens LAMBDA0 translation.

Run with: python3 TEST/test03_queens.py   (N = 8 takes about 100 seconds)
"""

import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import lambda0
from lambda0 import T0Mint, T0Mbtf, T0Mpair
from queens_lambda0 import (
    V, I, call, with_program, evaluate, decode_board, solve,
)

KNOWN_COUNTS = {4: 2, 5: 10, 6: 4, 7: 40, 8: 92}


def is_valid(board):
    n = len(board)
    return (len(set(board)) == n and all(0 <= q < n for q in board) and
            all(abs(board[a] - board[b]) != b - a
                for a in range(n) for b in range(a + 1, n)))


def board_term(board):
    t = T0Mint(0)
    for q in reversed(board):
        t = T0Mpair(T0Mint(q), t)
    return t


def ats_solutions():
    """Boards printed by the compiled ATS program (Assignment 1 output)."""
    text = (Path(__file__).parent / "queens_ats_expected.out").read_text()
    boards = []
    for block in text.split("Solution #")[1:]:
        rows = [r for r in block.splitlines() if "Q" in r][:8]
        boards.append(tuple(r.split().index("Q") for r in rows))
    return boards


class TestImports(unittest.TestCase):
    def test_uses_mysolution_interpreter(self):
        here = Path(__file__).resolve().parents[1]
        self.assertEqual(Path(lambda0.__file__).resolve(), here / "lambda0.py")


class TestHelpers(unittest.TestCase):
    """The helper functions, run inside the interpreter."""

    def run_term(self, body):
        return evaluate(with_program(body))

    def test_abs(self):
        for x in (-3, 0, 5):
            self.assertEqual(self.run_term(call("abs", I(x))), T0Mint(abs(x)))

    def test_board_get_set(self):
        bd = board_term((3, 1, 4, 1, 5, 2, 6, 0))
        self.assertEqual(self.run_term(call("board_get", bd, I(4))), T0Mint(5))
        new = self.run_term(call("board_set", bd, I(2), I(7)))
        self.assertEqual(decode_board(new, 8), (3, 1, 7, 1, 5, 2, 6, 0))

    def test_safety_test1(self):
        cases = [((3, 3, 0, 3), False),   # same column
                 ((3, 3, 1, 1), False),   # diagonal
                 ((3, 3, 1, 5), False),   # anti-diagonal
                 ((3, 3, 1, 4), True)]
        for args, expected in cases:
            with self.subTest(args=args):
                term = call("safety_test1", *map(I, args))
                self.assertEqual(self.run_term(term), T0Mbtf(expected))

    def test_safety_test2(self):
        bd = board_term((0, 4, 7, 0, 0, 0, 0, 0))  # rows 0..2 placed
        # Row 3: column 5 is safe, column 6 is diagonal to (2, 7), column 4 shares a column.
        for j, expected in [(5, True), (6, False), (4, False)]:
            with self.subTest(j=j):
                term = call("safety_test2", I(3), I(j), bd, I(2))
                self.assertEqual(self.run_term(term), T0Mbtf(expected))


class TestSmallBoards(unittest.TestCase):
    def test_counts_and_validity(self):
        for n in (4, 5, 6):
            with self.subTest(n=n):
                count, sols = solve(n)
                self.assertEqual(count, KNOWN_COUNTS[n])
                self.assertEqual(len(sols), count)
                self.assertEqual(len(set(sols)), count)
                self.assertTrue(all(len(b) == n and is_valid(b) for b in sols))


class TestEightQueens(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.count, cls.sols = solve(8)

    def test_count_matches_ats(self):
        self.assertEqual(self.count, 92)  # assertloc (nsol = 92) in queens.dats

    def test_all_boards_valid(self):
        self.assertEqual(len(set(self.sols)), 92)
        for b in self.sols:
            self.assertTrue(is_valid(b), b)

    def test_same_solutions_in_same_order_as_ats(self):
        self.assertEqual(self.sols, ats_solutions())


if __name__ == "__main__":
    unittest.main()
