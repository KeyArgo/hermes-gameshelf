"""Connect Four. Columns are 1 through 7. White plays X and moves first."""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import kit  # noqa: E402

ID = "connect4"
TITLE = "Connect Four"
MARKS = ("X", "O")
EXAMPLE = "move 4"
MAX_PLIES = 42
HELP = ["Drop a piece in a column, 1 through 7. Four in a row wins."]

_ROWS = 6
_COLS = 7
_ORDER = (4, 3, 5, 2, 6, 1, 7)


def create(root: Path, settings: dict | None = None):
    del settings
    return kit.Table(Path(root), kit.rules(globals()))


def fresh() -> dict:
    return {"board": [["." for _ in range(_COLS)] for _ in range(_ROWS)]}


def parse(words: list[str]) -> int | None:
    if not words or not words[0].isdigit():
        return None
    return int(words[0])


def legal(state: dict) -> list[int]:
    return [column for column in range(1, _COLS + 1) if state["board"][_ROWS - 1][column - 1] == "."]


def show(move: int) -> str:
    return str(move)


def play(state: dict, column: int) -> str:
    board = state["board"]
    mark = MARKS[0] if state["turn"] == "white" else MARKS[1]
    for row in range(_ROWS):
        if board[row][column - 1] == ".":
            board[row][column - 1] = mark
            if _won(board, row, column - 1, mark):
                state["status"] = "win"
                state["winner"] = state["turn"]
            elif not legal(state):
                state["status"] = "draw"
            else:
                state["turn"] = "black" if state["turn"] == "white" else "white"
            return ""
    return ""


def _won(board: list[list[str]], row: int, col: int, mark: str) -> bool:
    for dr, dc in ((1, 0), (0, 1), (1, 1), (1, -1)):
        count = 1
        for sign in (1, -1):
            r, c = row + dr * sign, col + dc * sign
            while 0 <= r < _ROWS and 0 <= c < _COLS and board[r][c] == mark:
                count += 1
                r += dr * sign
                c += dc * sign
        if count >= 4:
            return True
    return False


def _trial(state: dict, turn: str) -> dict:
    return {"board": [row[:] for row in state["board"]], "turn": turn, "status": "active", "winner": ""}


def bot(state: dict) -> int:
    side = state["turn"]
    opponent = "black" if side == "white" else "white"
    open_columns = legal(state)
    for column in open_columns:
        trial = _trial(state, side)
        play(trial, column)
        if trial["winner"] == side:
            return column
    for column in open_columns:
        trial = _trial(state, opponent)
        play(trial, column)
        if trial["winner"] == opponent:
            return column
    for column in _ORDER:
        if column in open_columns:
            return column
    return open_columns[0]


def draw(state: dict) -> list[str]:
    lines = [" ".join(state["board"][row]) for row in range(_ROWS - 1, -1, -1)]
    lines.append("1 2 3 4 5 6 7")
    return lines
