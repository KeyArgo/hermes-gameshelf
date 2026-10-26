"""Gomoku. 15 by 15, a1 at the top left. Five or more in a row wins. White plays X and moves first."""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import kit  # noqa: E402

ID = "gomoku"
TITLE = "Gomoku"
MARKS = ("X", "O")
EXAMPLE = "move h8"
MAX_PLIES = 225
HELP = ["Place a stone on any empty point. Five or more in a row, in any direction, wins."]

_SIZE = 15
_COLS = "abcdefghijklmno"
_CENTER = (7, 7)
_LINES = ((0, 1), (1, 0), (1, 1), (1, -1))


def create(root: Path, settings: dict | None = None):
    del settings
    return kit.Table(Path(root), kit.rules(globals()))


def fresh() -> dict:
    return {"board": [["." for _ in range(_SIZE)] for _ in range(_SIZE)]}


def _mark(side: str) -> str:
    return MARKS[0] if side == "white" else MARKS[1]


def _square(text: str) -> tuple[int, int] | None:
    text = text.strip().lower()
    if len(text) < 2 or text[0] not in _COLS or not text[1:].isdigit():
        return None
    row = int(text[1:]) - 1
    if not 0 <= row < _SIZE:
        return None
    return row, _COLS.index(text[0])


def _name(row: int, col: int) -> str:
    return f"{_COLS[col]}{row + 1}"


def parse(words: list[str]) -> str | None:
    if not words:
        return None
    spot = _square(words[0])
    return _name(*spot) if spot else None


def show(move: str) -> str:
    return move


def legal(state: dict) -> list[str]:
    board = state["board"]
    return [_name(row, col) for row in range(_SIZE) for col in range(_SIZE) if board[row][col] == "."]


def _run(board: list[list[str]], row: int, col: int, mark: str, dr: int, dc: int) -> tuple[int, int]:
    """Stones in a row through (row, col) as if mark stood there, and how many ends are open."""
    count, opened = 1, 0
    for sign in (1, -1):
        r, c = row + dr * sign, col + dc * sign
        while 0 <= r < _SIZE and 0 <= c < _SIZE and board[r][c] == mark:
            count += 1
            r += dr * sign
            c += dc * sign
        if 0 <= r < _SIZE and 0 <= c < _SIZE and board[r][c] == ".":
            opened += 1
    return count, opened


def _wins(board: list[list[str]], row: int, col: int, mark: str) -> bool:
    return any(_run(board, row, col, mark, dr, dc)[0] >= 5 for dr, dc in _LINES)


def play(state: dict, move: str) -> str:
    board = state["board"]
    row, col = _square(move)
    mark = _mark(state["turn"])
    board[row][col] = mark
    if _wins(board, row, col, mark):
        state["status"] = "win"
        state["winner"] = state["turn"]
    elif not any("." in line for line in board):
        state["status"] = "draw"
        state["winner"] = ""
    else:
        state["turn"] = "black" if state["turn"] == "white" else "white"
    return ""


def _worth(count: int, opened: int) -> int:
    if count >= 5:
        return 100000
    if opened == 0:
        return 0
    table = {4: (1000, 10000), 3: (100, 1000), 2: (10, 100), 1: (1, 2)}
    return table[count][opened - 1]


def _near(board: list[list[str]], row: int, col: int) -> bool:
    for r in range(max(0, row - 2), min(_SIZE, row + 3)):
        for c in range(max(0, col - 2), min(_SIZE, col + 3)):
            if board[r][c] != ".":
                return True
    return False


def bot(state: dict) -> str:
    board = state["board"]
    mine = _mark(state["turn"])
    theirs = "O" if mine == "X" else "X"
    empty = [(row, col) for row in range(_SIZE) for col in range(_SIZE) if board[row][col] == "."]
    if len(empty) == _SIZE * _SIZE:
        return _name(*_CENTER)
    candidates = [spot for spot in empty if _near(board, *spot)] or empty
    for spot in candidates:
        if _wins(board, *spot, mine):
            return _name(*spot)
    for spot in candidates:
        if _wins(board, *spot, theirs):
            return _name(*spot)

    def score(spot: tuple[int, int]) -> tuple[float, int, int, int]:
        row, col = spot
        attack = sum(_worth(*_run(board, row, col, mine, dr, dc)) for dr, dc in _LINES)
        defend = sum(_worth(*_run(board, row, col, theirs, dr, dc)) for dr, dc in _LINES)
        distance = abs(row - _CENTER[0]) + abs(col - _CENTER[1])
        return (attack + 0.9 * defend, -distance, -row, -col)

    return _name(*max(candidates, key=score))


def draw(state: dict) -> list[str]:
    board = state["board"]
    lines = ["   " + " ".join(_COLS)]
    lines += [f"{row + 1:2d} " + " ".join(board[row]) for row in range(_SIZE)]
    return lines
