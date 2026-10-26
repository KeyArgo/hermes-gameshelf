"""English checkers. 8 by 8, a1 at the bottom left. White plays x from rows 1 to 3 and moves first."""

from __future__ import annotations

import re
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import kit  # noqa: E402

ID = "checkers"
TITLE = "Checkers"
MARKS = ("x", "o")
EXAMPLE = "move c3 d4"
MAX_PLIES = 400
HELP = [
    "Move diagonally forward. A capture is required when one exists, and a jump chain is one move: move c3 e5 c7.",
    "A man that reaches the far row is crowned (X or O) and can move backward. Crowning ends the move.",
    "80 moves with no capture and no crowning is a draw.",
]

_SIZE = 8
_COLS = "abcdefgh"
_QUIET = 80
_DEPTH = 4
_NODES = 20000

Move = tuple[str, ...]


def create(root: Path, settings: dict | None = None):
    del settings
    return kit.Table(Path(root), kit.rules(globals()))


def fresh() -> dict:
    board = [["." for _ in range(_SIZE)] for _ in range(_SIZE)]
    for row in range(_SIZE):
        for col in range(_SIZE):
            if (row + col) % 2:
                continue
            if row <= 2:
                board[row][col] = "x"
            elif row >= 5:
                board[row][col] = "o"
    return {"board": board, "quiet": 0}


def _mark(side: str) -> str:
    return "x" if side == "white" else "o"


def _name(row: int, col: int) -> str:
    return f"{_COLS[col]}{row + 1}"


def _square(text: str) -> tuple[int, int] | None:
    if len(text) != 2 or text[0] not in _COLS or not text[1].isdigit():
        return None
    row = int(text[1]) - 1
    if not 0 <= row < _SIZE:
        return None
    return row, _COLS.index(text[0])


def parse(words: list[str]) -> Move | None:
    pieces = [item for item in re.split(r"[\s\-x:]+", " ".join(words).lower()) if item]
    if len(pieces) < 2 or any(_square(item) is None for item in pieces):
        return None
    return tuple(pieces)


def show(move: Move) -> str:
    return "-".join(move)


def _directions(piece: str) -> tuple[tuple[int, int], ...]:
    if piece in "XO":
        return ((1, -1), (1, 1), (-1, -1), (-1, 1))
    return ((1, -1), (1, 1)) if piece == "x" else ((-1, -1), (-1, 1))


def _far_row(piece: str) -> int:
    return _SIZE - 1 if piece == "x" else 0


def _inside(row: int, col: int) -> bool:
    return 0 <= row < _SIZE and 0 <= col < _SIZE


def _jumps(board, row: int, col: int, piece: str, taken: frozenset) -> list[list[tuple[int, int]]]:
    enemy = "o" if piece.lower() == "x" else "x"
    paths: list[list[tuple[int, int]]] = []
    for dr, dc in _directions(piece):
        mid_r, mid_c = row + dr, col + dc
        land_r, land_c = row + 2 * dr, col + 2 * dc
        if not _inside(land_r, land_c):
            continue
        if board[mid_r][mid_c].lower() != enemy or (mid_r, mid_c) in taken or board[land_r][land_c] != ".":
            continue
        if piece in "xo" and land_r == _far_row(piece):
            paths.append([(land_r, land_c)])
            continue
        more = _jumps(board, land_r, land_c, piece, taken | {(mid_r, mid_c)})
        if more:
            paths.extend([(land_r, land_c), *tail] for tail in more)
        else:
            paths.append([(land_r, land_c)])
    return paths


def _moves(board, side: str) -> list[Move]:
    mark = _mark(side)
    captures: list[Move] = []
    steps: list[Move] = []
    for row in range(_SIZE):
        for col in range(_SIZE):
            piece = board[row][col]
            if piece.lower() != mark:
                continue
            board[row][col] = "."
            for path in _jumps(board, row, col, piece, frozenset()):
                captures.append((_name(row, col), *(_name(r, c) for r, c in path)))
            board[row][col] = piece
            for dr, dc in _directions(piece):
                r, c = row + dr, col + dc
                if _inside(r, c) and board[r][c] == ".":
                    steps.append((_name(row, col), _name(r, c)))
    return captures or steps


def legal(state: dict) -> list[Move]:
    return _moves(state["board"], state["turn"])


def play(state: dict, move: Move) -> str:
    board = state["board"]
    side = state["turn"]
    other = "black" if side == "white" else "white"
    spots = [_square(item) for item in move]
    row, col = spots[0]
    piece = board[row][col]
    board[row][col] = "."
    captured = 0
    for (r1, c1), (r2, c2) in zip(spots, spots[1:]):
        if abs(r2 - r1) == 2:
            board[(r1 + r2) // 2][(c1 + c2) // 2] = "."
            captured += 1
    end_r, end_c = spots[-1]
    notes = []
    crowned = piece in "xo" and end_r == _far_row(piece)
    if crowned:
        piece = piece.upper()
        notes.append("Crowned.")
    board[end_r][end_c] = piece
    if captured:
        notes.insert(0, f"Took {captured}.")
    state["quiet"] = 0 if captured or crowned else int(state.get("quiet") or 0) + 1
    if not _moves(board, other):
        state["status"] = "win"
        state["winner"] = side
        notes.append(f"{other.capitalize()} has no move.")
    elif state["quiet"] >= _QUIET:
        state["status"] = "draw"
        state["winner"] = ""
        notes.append(f"{_QUIET} moves with no capture or crowning.")
    else:
        state["turn"] = other
    return " ".join(notes)


def _copy(state: dict) -> dict:
    return {
        "board": [row[:] for row in state["board"]],
        "turn": state["turn"],
        "status": "active",
        "winner": "",
        "quiet": state.get("quiet", 0),
    }


def _value(state: dict, me: str) -> float:
    if state["status"] == "win":
        return 10000 if state["winner"] == me else -10000
    if state["status"] != "active":
        return 0
    mine = _mark(me)
    score = 0.0
    for row in range(_SIZE):
        for col in range(_SIZE):
            piece = state["board"][row][col]
            if piece == ".":
                continue
            worth = 5 if piece in "XO" else 3 + 0.1 * (row if piece == "x" else _SIZE - 1 - row)
            score += worth if piece.lower() == mine else -worth
    return score


def _search(state: dict, me: str, depth: int, alpha: float, beta: float, budget: list[int]) -> float:
    budget[0] -= 1
    if depth == 0 or state["status"] != "active" or budget[0] <= 0:
        return _value(state, me)
    maximizing = state["turn"] == me
    best = float("-inf") if maximizing else float("inf")
    for move in legal(state):
        child = _copy(state)
        play(child, move)
        score = _search(child, me, depth - 1, alpha, beta, budget)
        if maximizing:
            best = max(best, score)
            alpha = max(alpha, score)
        else:
            best = min(best, score)
            beta = min(beta, score)
        if beta <= alpha:
            break
    return best


def bot(state: dict) -> Move:
    me = state["turn"]
    choices = legal(state)
    if len(choices) == 1:
        return choices[0]
    share = max(1, _NODES // len(choices))
    best_move, best_score = choices[0], float("-inf")
    for move in choices:
        child = _copy(state)
        play(child, move)
        score = _search(child, me, _DEPTH - 1, float("-inf"), float("inf"), [share])
        if score > best_score:
            best_move, best_score = move, score
    return best_move


def draw(state: dict) -> list[str]:
    board = state["board"]
    lines = ["  " + " ".join(_COLS)]
    for row in range(_SIZE - 1, -1, -1):
        cells = [board[row][col] if (row + col) % 2 == 0 else " " for col in range(_SIZE)]
        lines.append(f"{row + 1} " + " ".join(cells))
    return lines
