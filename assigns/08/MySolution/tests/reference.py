"""Independent direct-style Python model of the same search, used as an oracle.

Boards here are row-order lists, matching the JSON encoding.
"""

from itertools import permutations


def attacks(column, row, board):
    """True if a queen at (column, row) conflicts with any queen on board."""
    return any(c == column or abs(c - column) == row - r for r, c in enumerate(board))


def is_solution(board):
    return all(not attacks(c, r, board[:r]) for r, c in enumerate(board))


def reference_trace(size):
    events = []

    def search(row, board):
        if row == size:
            events.append({"event": "solution", "board": list(board)})
            return
        for column in range(size):
            events.append({"event": "try", "column": column, "row": row, "board": list(board)})
            if attacks(column, row, board):
                events.append({"event": "reject", "column": column, "row": row, "board": list(board)})
                continue
            child = board + [column]
            events.append({"event": "place", "column": column, "row": row, "board": list(child)})
            search(row + 1, child)
            events.append({"event": "backtrack", "column": column, "row": row, "board": list(board)})

    search(0, [])
    events.append({"event": "done"})
    return events


def brute_force_solutions(size):
    """All solutions in lexicographic order, by filtering permutations."""
    return [list(p) for p in permutations(range(size)) if is_solution(list(p))]
