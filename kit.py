"""Seats, turns, and saved state for Game Shelf titles. No game rules live here."""

from __future__ import annotations

import contextlib
import json
import os
import shlex
from pathlib import Path

SIDES = ("white", "black")


def seat_kind(token: str) -> str:
    text = str(token or "").strip().lower()
    if text in {"", "human"} or text.startswith("human:"):
        return "human"
    if text == "local":
        return "local"
    return "profile"


def words(raw: str) -> list[str] | None:
    try:
        return shlex.split(raw or "")
    except ValueError:
        return None


def pairs(parts: list[str]) -> dict[str, str]:
    found: dict[str, str] = {}
    for part in parts:
        if "=" in part:
            key, value = part.split("=", 1)
            found[key.lower()] = value
    return found


def load(root: Path) -> dict | None:
    path = Path(root) / "state.json"
    if not path.is_file():
        return None
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return loaded if isinstance(loaded, dict) else None


def write(root: Path, state: dict) -> None:
    """Replace state.json. Call inside locked() or through save()."""
    folder = Path(root)
    folder.mkdir(parents=True, exist_ok=True)
    temporary = folder / "state.json.tmp"
    temporary.write_text(json.dumps(state), encoding="utf-8")
    os.replace(temporary, folder / "state.json")


@contextlib.contextmanager
def locked(root: Path):
    import fcntl

    folder = Path(root)
    folder.mkdir(parents=True, exist_ok=True)
    with (folder / ".lock").open("a+", encoding="utf-8") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lock.fileno(), fcntl.LOCK_UN)


def save(root: Path, state: dict) -> None:
    with locked(root):
        write(root, state)


def clear(root: Path) -> None:
    path = Path(root) / "state.json"
    if path.is_file():
        path.unlink()


def shared_keyboard(player: object) -> bool:
    """One keyboard can play both seats. Two people on a chat platform cannot."""
    if player is None:
        return True
    return str(getattr(player, "platform", "") or "") in {"", "local", "cli", "tui", "desktop"}


def claim(state: dict, side: str, player: object) -> str | None:
    """Bind an open human seat to this person, or refuse if it is someone else's turn."""
    if player is None:
        return None
    if seat_kind(str(state.get(side) or "")) != "human":
        return None
    bound = str(state.get(f"{side}_id") or "")
    other = "black" if side == "white" else "white"
    other_id = str(state.get(f"{other}_id") or "")
    player_id = str(getattr(player, "id", "") or "")
    player_name = str(getattr(player, "name", "") or "You")
    if bound and bound != player_id:
        return f"It's {state.get(f'{side}_name') or 'the other player'}'s turn."
    if not bound and other_id == player_id and not shared_keyboard(player):
        return f"You are {player_name}. The other person plays the open seat."
    if not bound:
        state[f"{side}_id"] = player_id
        state[f"{side}_name"] = player_name
        state[side] = "human"
    return None


def sit(state: dict, side: str, player: object, kind: str = "human") -> None:
    state[side] = kind
    if kind == "local":
        state[f"{side}_id"] = "local"
        state[f"{side}_name"] = "Local"
        return
    if player is None:
        state[f"{side}_id"] = ""
        state[f"{side}_name"] = ""
        return
    state[f"{side}_id"] = str(getattr(player, "id", "") or "")
    state[f"{side}_name"] = str(getattr(player, "name", "") or "You")


def seat_line(state: dict, side: str) -> str:
    name = str(state.get(f"{side}_name") or "")
    if name:
        return name
    if not state.get(side):
        return "waiting"
    if state.get(side) == "local":
        return "Local"
    return side


def rules(namespace: dict):
    """A game's module globals as the rules object. The shelf loads games without sys.modules."""
    import types

    return types.SimpleNamespace(**namespace)


class Table:
    """Two seats, white moves first. ``rules`` is a module with the game's rules.

    rules must provide ID, TITLE, MARKS (white, black), EXAMPLE, HELP, MAX_PLIES and
    fresh() -> dict, parse(words) -> move | None, legal(state) -> list,
    play(state, move) -> note, bot(state) -> move, show(move) -> str, draw(state) -> list[str].
    play() sets state turn, status ("active", "win", "draw") and winner.
    """

    def __init__(self, root: Path, rules) -> None:
        self.root = Path(root)
        self.rules = rules

    def command(self, raw: str, *, source: str = "command", complete=None, player=None) -> str:
        del complete
        rules = self.rules
        parts = words(raw)
        if parts is None:
            return f"Could not read that. Try /games {rules.ID} {rules.EXAMPLE}"
        if not parts or parts[0].lower() == "help":
            return self.help()
        head, rest = parts[0].lower(), parts[1:]
        with locked(self.root):
            state = load(self.root)
            if head == "new":
                return self._new(state, rest, player)
            if head in {"allow-ai", "allow_ai"}:
                return self._allow(state, rest, source, player)
            if state is None or state.get("status") == "abandoned":
                return f"No game in progress. /games {rules.ID} new"
            if head in {"state", "board"}:
                return self.draw(state)
            if head == "join":
                return self._join(state, player)
            if head == "move":
                return self._move(state, rest, source, player)
            if head == "step":
                return self._step(state)
            if head == "resign":
                return self._resign(state, rest, player)
            if head == "abandon":
                return self._abandon(state, player)
        return self.help()

    def help(self) -> str:
        rules = self.rules
        lines = [rules.TITLE, *rules.HELP, "", "Usage:"]
        lines += [
            f"/games {rules.ID} new",
            f"/games {rules.ID} join",
            f"/games {rules.ID} allow-ai black=local",
            f"/games {rules.ID} {rules.EXAMPLE}",
            f"/games {rules.ID} state",
            f"/games {rules.ID} resign",
            f"/games {rules.ID} abandon",
        ]
        return "\n".join(lines)

    def _busy(self, state: dict | None, player) -> str | None:
        if not state or state.get("status") != "active" or player is None:
            return None
        player_id = str(getattr(player, "id", "") or "")
        others = [
            str(state.get(f"{side}_name") or side)
            for side in SIDES
            if str(state.get(f"{side}_id") or "") not in {"", "local", player_id}
        ]
        if not others:
            return None
        return (
            f"{self.rules.TITLE} is in progress with {' and '.join(others)}. "
            f"A seated player types /games {self.rules.ID} abandon first."
        )

    def _new(self, state: dict | None, rest: list[str], player) -> str:
        rules = self.rules
        busy = self._busy(state, player)
        if busy:
            return busy
        seats = pairs(rest)
        if rest and (not seats.get("white") or not seats.get("black")):
            return f"Usage: /games {rules.ID} new white=human black=human"
        white = seats.get("white", "human")
        black = seats.get("black", "human")
        if "profile" in {seat_kind(white), seat_kind(black)}:
            return f"The AI here is the built-in player. /games {rules.ID} allow-ai black=local"
        fresh = {
            "game": rules.ID,
            "turn": "white",
            "white": white,
            "black": black,
            "status": "active",
            "winner": "",
            "plies": 0,
            "last": "",
        }
        fresh.update(rules.fresh())
        if seat_kind(white) == "local":
            sit(fresh, "white", None, "local")
        elif player is not None:
            sit(fresh, "white", player, "human")
        if seat_kind(black) == "local":
            sit(fresh, "black", None, "local")
        elif player is not None and not shared_keyboard(player):
            fresh["black"] = ""
            fresh["black_id"] = ""
            fresh["black_name"] = ""
        return self._finish(fresh, [])

    def _allow(self, state: dict | None, rest: list[str], source: str, player) -> str:
        rules = self.rules
        if source != "command":
            return "Refused (consent_required)."
        seats = pairs(rest)
        if not seats and len(rest) == 1:
            seats = {"black": rest[0]}
        white = seats.get("white", "human")
        black = seats.get("black", "")
        if not black:
            return f"Usage: /games {rules.ID} allow-ai black=local"
        if "profile" in {seat_kind(white), seat_kind(black)}:
            return f"The AI here is the built-in player. /games {rules.ID} allow-ai black=local"
        if seat_kind(white) != "local" and seat_kind(black) != "local":
            return f"Name the AI seat. /games {rules.ID} allow-ai black=local"
        return self._new(state, [f"white={white}", f"black={black}"], player)

    def _join(self, state: dict, player) -> str:
        if state.get("status") != "active":
            return self.draw(state)
        if player is None:
            return f"Join from your own chat. /games {self.rules.ID} join"
        if state.get("black_id"):
            return "Both seats are taken."
        if state.get("white_id") == getattr(player, "id", ""):
            return f"You are already {player.name}."
        sit(state, "black", player, "human")
        write(self.root, state)
        return self.draw(state)

    def _move(self, state: dict, rest: list[str], source: str, player) -> str:
        rules = self.rules
        if state.get("status") != "active":
            return self.draw(state)
        side = state["turn"]
        kind = seat_kind(str(state.get(side) or ""))
        if kind == "local":
            return f"It's the built-in player's turn. /games {rules.ID} step"
        if source == "tool":
            return "Refused (human_turn)."
        refused = claim(state, side, player)
        if refused:
            return refused
        move = rules.parse(rest)
        legal = rules.legal(state)
        if move is None or move not in legal:
            hint = ", ".join(rules.show(item) for item in legal[:8])
            return f"Refused (illegal). Try: {hint}" if hint else "Refused (illegal)."
        shown = rules.show(move)
        note = rules.play(state, move)
        self._count(state, shown)
        return self._finish(state, [f"Played {shown}." + (f" {note}" if note else "")])

    def _step(self, state: dict) -> str:
        if state.get("status") != "active":
            return self.draw(state)
        if seat_kind(str(state.get(state["turn"]) or "")) != "local":
            return "Refused (human_turn)."
        return self._finish(state, [])

    def _resign(self, state: dict, rest: list[str], player) -> str:
        if state.get("status") != "active":
            return self.draw(state)
        if player is not None and not shared_keyboard(player):
            player_id = str(getattr(player, "id", "") or "")
            mine = [side for side in SIDES if state.get(f"{side}_id") == player_id]
            if not mine:
                return "Only a seated player can resign."
            side = mine[0] if len(mine) == 1 else state["turn"]
        else:
            side = rest[0].lower() if rest else state["turn"]
            if side not in SIDES:
                return f"Usage: /games {self.rules.ID} resign white"
        state["status"] = "resigned"
        state["winner"] = "black" if side == "white" else "white"
        write(self.root, state)
        return self.draw(state)

    def _abandon(self, state: dict, player) -> str:
        if player is not None and not shared_keyboard(player):
            player_id = str(getattr(player, "id", "") or "")
            bound = [str(state.get(f"{side}_id") or "") for side in SIDES]
            people = [item for item in bound if item and item != "local"]
            if people and player_id not in people:
                return "Only a seated player can abandon this game."
        state["status"] = "abandoned"
        write(self.root, state)
        return "Game abandoned."

    def _count(self, state: dict, shown: str) -> None:
        state["plies"] = int(state.get("plies") or 0) + 1
        state["last"] = shown
        if state.get("status") == "active" and state["plies"] >= self.rules.MAX_PLIES:
            state["status"] = "draw"
            state["winner"] = ""

    def _finish(self, state: dict, notes: list[str]) -> str:
        rules = self.rules
        guard = 0
        while (
            state.get("status") == "active"
            and seat_kind(str(state.get(state["turn"]) or "")) == "local"
            and guard < rules.MAX_PLIES + 1
        ):
            move = rules.bot(state)
            shown = rules.show(move)
            note = rules.play(state, move)
            self._count(state, shown)
            notes.append(f"Local played {shown}." + (f" {note}" if note else ""))
            guard += 1
        write(self.root, state)
        if len(notes) > 6:
            notes = [*notes[:1], f"… {len(notes) - 4} more moves …", *notes[-3:]]
        drawn = self.draw(state)
        return "\n".join([*notes, drawn]) if notes else drawn

    def draw(self, state: dict) -> str:
        rules = self.rules
        white_mark, black_mark = rules.MARKS
        lines = list(rules.draw(state))
        lines.append(
            f"White ({white_mark}): {seat_line(state, 'white')}    "
            f"Black ({black_mark}): {seat_line(state, 'black')}"
        )
        status = state.get("status")
        if status == "active":
            who = "White" if state["turn"] == "white" else "Black"
            lines.append(f"{who} to move.")
        elif state.get("winner"):
            winner = state["winner"]
            name = seat_line(state, winner)
            lines.append(f"Game over ({status}): {winner}." + (f" {name} wins." if name not in {winner, 'waiting'} else ""))
        else:
            lines.append(f"Game {status}.")
        return "\n".join(lines)
