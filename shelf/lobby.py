"""The games lobby: a short chat and a list of who wants a game. One file per Hermes Agent profile.

When the referee profile sits in a HermesNet IRC channel, everyone in that channel shares this lobby.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from .who import Player

_KEEP = 40
_SHOW = 12
_TEXT = 200
_FILE = "lobby.json"


def talk(folder: Path, player: Player | None, words: list[str], *, game: str = "") -> str:
    """/games chat … and /games doom …. ``game`` is "doom" for the Doom lobby."""
    if player is None:
        return "Type /games chat in the chat."
    head = words[0].lower() if words else ""
    rest = words[1:]
    if head in {"", "who", "look"}:
        return board(folder, game=game)
    if not player.named:
        return "Pick a name first with /games name Argo. On IRC or Discord, your name there is used."
    if head == "say":
        return _say(folder, player, " ".join(rest), game)
    if head == "looking" and game:
        return _looking(folder, player, game)
    if head == "stop":
        return _looking(folder, player, "")
    prefix = f"/games {game}" if game else "/games chat"
    return (
        "Usage:\n"
        f"{prefix}\n"
        f"{prefix} say anyone for a game?\n"
        + (f"{prefix} looking\n" if game else "/games looking reversi\n")
        + f"{prefix} stop"
    )


def looking(folder: Path, player: Player | None, game: str, known: bool) -> str:
    """/games looking <game>. ``known`` is whether that game is on the shelf."""
    if player is None:
        return "Type /games looking <game> in the chat."
    if not game:
        return board(folder)
    if game == "stop":
        return _looking(folder, player, "")
    if not known and game != "doom":
        return f"No game named {game}. /games lists them."
    if not player.named:
        return "Pick a name first with /games name Argo. On IRC or Discord, your name there is used."
    return _looking(folder, player, game)


def snapshot(folder: Path) -> dict:
    state = _load(folder)
    return {
        "lines": state["lines"][-_SHOW:],
        "looking": [{"name": item["name"], "game": item["game"]} for item in state["looking"].values()],
    }


def board(folder: Path, *, game: str = "") -> str:
    state = _load(folder)
    wanted = [
        f"{item['name']} ({item['game']})"
        for item in state["looking"].values()
        if not game or item["game"] == game
    ]
    label = "Looking for a Doom match" if game == "doom" else "Looking for a game"
    lines = [f"{label}: {', '.join(wanted) if wanted else 'nobody yet'}"]
    spoken = state["lines"]
    if not spoken:
        lines.append("No messages yet. /games chat say hello")
    else:
        lines.extend(f"{item['name']}: {item['text']}" for item in spoken[-_SHOW:])
    if game == "doom":
        lines.append("The Doom match will run on players' machines. This chat is how you find people.")
    return "\n".join(lines)


def _say(folder: Path, player: Player, text: str, game: str) -> str:
    spoken = " ".join(text.split())[:_TEXT]
    if not spoken:
        return "Usage: /games chat say anyone for a game?"
    state = _load(folder)
    state["lines"].append({"id": player.id, "name": player.name, "text": spoken})
    state["lines"] = state["lines"][-_KEEP:]
    _save(folder, state)
    return board(folder, game=game)


def _looking(folder: Path, player: Player, game: str) -> str:
    state = _load(folder)
    if game:
        state["looking"][player.id] = {"name": player.name, "game": game}
    else:
        state["looking"].pop(player.id, None)
    _save(folder, state)
    return board(folder, game="doom" if game == "doom" else "")


def _load(folder: Path) -> dict:
    path = Path(folder) / _FILE
    empty = {"lines": [], "looking": {}}
    if not path.is_file():
        return empty
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return empty
    if not isinstance(loaded, dict):
        return empty
    lines = [
        {"id": str(item.get("id", "")), "name": str(item.get("name", "")), "text": str(item.get("text", ""))}
        for item in loaded.get("lines") or []
        if isinstance(item, dict)
    ]
    looking = {
        str(key): {"name": str(value.get("name", "")), "game": str(value.get("game", ""))}
        for key, value in (loaded.get("looking") or {}).items()
        if isinstance(value, dict)
    }
    return {"lines": lines, "looking": looking}


def _save(folder: Path, state: dict) -> None:
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / _FILE
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(state), encoding="utf-8")
    os.replace(temporary, path)
