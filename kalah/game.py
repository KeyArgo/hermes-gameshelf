"""Kalah. Six pits a side, four seeds each. Pits are numbered 1 to 6 from your own left."""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import kit  # noqa: E402

ID = "kalah"
TITLE = "Kalah"
MARKS = ("bottom", "top")
EXAMPLE = "move 1"
MAX_PLIES = 400
HELP = [
    "Pick a pit, 1 to 6 from your own left. Its seeds are sown one per pit, counterclockwise.",
    "A last seed in your store is another turn. A last seed in an empty pit of yours takes the pit opposite.",
]

_SEEDS = 4
_STORE = {"white": 6, "black": 13}
_DEPTH = 6


def create(root: Path, settings: dict | None = None):
    del settings
    return kit.Table(Path(root), kit.rules(globals()))


def fresh() -> dict:
    pits = [_SEEDS] * 14
    pits[6] = 0
    pits[13] = 0
    return {"pits": pits}


def _index(side: str, pit: int) -> int:
    return pit - 1 if side == "white" else pit + 6


def _own(side: str) -> range:
    return range(0, 6) if side == "white" else range(7, 13)


def parse(words: list[str]) -> int | None:
    if not words or not words[0].isdigit():
        return None
    return int(words[0])


def legal(state: dict) -> list[int]:
    side = state["turn"]
    return [pit for pit in range(1, 7) if state["pits"][_index(side, pit)] > 0]


def show(move: int) -> str:
    return str(move)


def play(state: dict, pit: int) -> str:
    side = state["turn"]
    other = "black" if side == "white" else "white"
    pits = state["pits"]
    position = _index(side, pit)
    seeds = pits[position]
    pits[position] = 0
    while seeds:
        position = (position + 1) % 14
        if position == _STORE[other]:
            continue
        pits[position] += 1
        seeds -= 1
    note = ""
    again = position == _STORE[side]
    if not again and position in _own(side) and pits[position] == 1 and pits[12 - position] > 0:
        taken = pits[position] + pits[12 - position]
        pits[_STORE[side]] += taken
        pits[position] = 0
        pits[12 - position] = 0
        note = f"Captured {taken}."
    if all(pits[index] == 0 for index in _own("white")) or all(pits[index] == 0 for index in _own("black")):
        for owner in ("white", "black"):
            for index in _own(owner):
                pits[_STORE[owner]] += pits[index]
                pits[index] = 0
        white, black = pits[6], pits[13]
        if white == black:
            state["status"] = "draw"
            state["winner"] = ""
        else:
            state["status"] = "win"
            state["winner"] = "white" if white > black else "black"
        return (note + " " if note else "") + f"Final {white} to {black}."
    if again:
        return (note + " " if note else "") + "Another turn."
    state["turn"] = other
    return note


def _copy(state: dict) -> dict:
    return {"pits": state["pits"][:], "turn": state["turn"], "status": "active", "winner": ""}


def _value(state: dict, me: str) -> int:
    other = "black" if me == "white" else "white"
    diff = state["pits"][_STORE[me]] - state["pits"][_STORE[other]]
    if state["status"] != "active":
        return diff * 1000
    return diff


def _search(state: dict, me: str, depth: int, alpha: float, beta: float) -> float:
    if depth == 0 or state["status"] != "active":
        return _value(state, me)
    maximizing = state["turn"] == me
    best = float("-inf") if maximizing else float("inf")
    for pit in legal(state):
        child = _copy(state)
        play(child, pit)
        score = _search(child, me, depth - 1, alpha, beta)
        if maximizing:
            best = max(best, score)
            alpha = max(alpha, score)
        else:
            best = min(best, score)
            beta = min(beta, score)
        if beta <= alpha:
            break
    return best


def bot(state: dict) -> int:
    me = state["turn"]
    choice, best = legal(state)[0], float("-inf")
    for pit in legal(state):
        child = _copy(state)
        play(child, pit)
        score = _search(child, me, _DEPTH - 1, float("-inf"), float("inf"))
        if score > best:
            choice, best = pit, score
    return choice


def draw(state: dict) -> list[str]:
    pits = state["pits"]
    top = "".join(f"[{pits[index]:2d}]" for index in range(12, 6, -1))
    bottom = "".join(f"[{pits[index]:2d}]" for index in range(0, 6))
    return [
        "Top    6   5   4   3   2   1",
        f"     {top}",
        f"[{pits[13]:2d}]" + " " * 25 + f"[{pits[6]:2d}]",
        f"     {bottom}",
        "Bottom 1   2   3   4   5   6",
        f"Stores: White {pits[6]}  Black {pits[13]}",
    ]
