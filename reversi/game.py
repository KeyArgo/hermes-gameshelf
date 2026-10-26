"""Reversi. 8 by 8, a1 at the top left. White plays X and moves first. A side with no move passes."""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import kit  # noqa: E402

ID = "reversi"
TITLE = "Reversi"
MARKS = ("X", "O")
EXAMPLE = "move d3"
MAX_PLIES = 130
HELP = [
    "Place a disc so it traps a line of the other color. Those discs flip.",
    "If you have no move, you pass. Most discs at the end wins.",
]

_SIZE = 8
_COLS = "abcdefgh"
_DIRECTIONS = ((-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1))
_WEIGHTS = (
    (100, -20, 10, 5, 5, 10, -20, 100),
    (-20, -50, -2, -2, -2, -2, -50, -20),
    (10, -2, 1, 1, 1, 1, -2, 10),
    (5, -2, 1, 0, 0, 1, -2, 5),
    (5, -2, 1, 0, 0, 1, -2, 5),
    (10, -2, 1, 1, 1, 1, -2, 10),
    (-20, -50, -2, -2, -2, -2, -50, -20),
    (100, -20, 10, 5, 5, 10, -20, 100),
)


def create(root: Path, settings: dict | None = None):
    del settings
    return kit.Table(Path(root), kit.rules(globals()))


def fresh() -> dict:
    board = [["." for _ in range(_SIZE)] for _ in range(_SIZE)]
    board[3][3] = "O"
    board[4][4] = "O"
    board[3][4] = "X"
    board[4][3] = "X"
    return {"board": board}


def _mark(side: str) -> str:
    return MARKS[0] if side == "white" else MARKS[1]


def _square(text: str) -> tuple[int, int] | None:
    text = text.strip().lower()
    if len(text) != 2 or text[0] not in _COLS or not text[1].isdigit():
        return None
    row = int(text[1]) - 1
    if not 0 <= row < _SIZE:
        return None
    return row, _COLS.index(text[0])


def parse(words: list[str]) -> str | None:
    if not words or _square(words[0]) is None:
        return None
    return words[0].strip().lower()


def show(move: str) -> str:
    return move


def _flips(board: list[list[str]], row: int, col: int, mark: str) -> list[tuple[int, int]]:
    if board[row][col] != ".":
        return []
    other = "O" if mark == "X" else "X"
    found: list[tuple[int, int]] = []
    for dr, dc in _DIRECTIONS:
        line: list[tuple[int, int]] = []
        r, c = row + dr, col + dc
        while 0 <= r < _SIZE and 0 <= c < _SIZE and board[r][c] == other:
            line.append((r, c))
            r += dr
            c += dc
        if line and 0 <= r < _SIZE and 0 <= c < _SIZE and board[r][c] == mark:
            found.extend(line)
    return found


def _moves(board: list[list[str]], mark: str) -> list[str]:
    return [
        f"{_COLS[col]}{row + 1}"
        for row in range(_SIZE)
        for col in range(_SIZE)
        if _flips(board, row, col, mark)
    ]


def legal(state: dict) -> list[str]:
    return _moves(state["board"], _mark(state["turn"]))


def _count(board: list[list[str]]) -> tuple[int, int]:
    flat = [cell for row in board for cell in row]
    return flat.count("X"), flat.count("O")


def play(state: dict, move: str) -> str:
    board = state["board"]
    side = state["turn"]
    other = "black" if side == "white" else "white"
    row, col = _square(move)
    mark = _mark(side)
    for r, c in _flips(board, row, col, mark):
        board[r][c] = mark
    board[row][col] = mark
    if _moves(board, _mark(other)):
        state["turn"] = other
        return ""
    if _moves(board, mark):
        return f"{other.capitalize()} has no move and passes."
    white, black = _count(board)
    if white == black:
        state["status"] = "draw"
        state["winner"] = ""
    else:
        state["status"] = "win"
        state["winner"] = "white" if white > black else "black"
    return f"Final {white} to {black}."


def _copy(state: dict) -> dict:
    return {"board": [row[:] for row in state["board"]], "turn": state["turn"], "status": "active", "winner": ""}


def _value(state: dict, me: str) -> float:
    board = state["board"]
    mine = _mark(me)
    theirs = "O" if mine == "X" else "X"
    if state["status"] != "active":
        white, black = _count(board)
        diff = (white - black) if me == "white" else (black - white)
        return diff * 10000
    score = 0
    for row in range(_SIZE):
        for col in range(_SIZE):
            if board[row][col] == mine:
                score += _WEIGHTS[row][col]
            elif board[row][col] == theirs:
                score -= _WEIGHTS[row][col]
    score += 5 * (len(_moves(board, mine)) - len(_moves(board, theirs)))
    return score


def bot(state: dict) -> str:
    me = state["turn"]
    choices = legal(state)
    best_move, best_score = choices[0], float("-inf")
    for move in choices:
        child = _copy(state)
        play(child, move)
        if child["status"] != "active" or child["turn"] == me:
            score = _value(child, me)
        else:
            replies = legal(child)
            score = float("inf")
            for reply in replies:
                grandchild = _copy(child)
                play(grandchild, reply)
                score = min(score, _value(grandchild, me))
        if score > best_score:
            best_move, best_score = move, score
    return best_move


def draw(state: dict) -> list[str]:
    board = state["board"]
    lines = ["  " + " ".join(_COLS)]
    lines += [f"{row + 1} " + " ".join(board[row]) for row in range(_SIZE)]
    white, black = _count(board)
    lines.append(f"Discs: X {white}  O {black}")
    return lines
