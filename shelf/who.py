"""Who is playing. Discord ids stay the key. The name is what the board shows."""

from __future__ import annotations

import json
import os
from pathlib import Path


class Player:
    def __init__(self, id: str, name: str, platform: str, bot: bool = False, named: bool = False) -> None:
        self.id = id
        self.name = name
        self.platform = platform
        self.bot = bot
        self.named = named


def clean_name(text: str) -> str:
    flattened = " ".join(str(text or "").replace("\n", " ").split())
    kept = "".join(ch for ch in flattened if ch.isalnum() or ch in " _-.")
    kept = kept.strip()[:32]
    if kept.lower() in {"human", "local", "cpu"} or not any(ch.isalnum() for ch in kept):
        return ""
    return kept


def _platform_name(platform: object, source: object) -> str:
    if platform:
        return str(getattr(platform, "value", platform) or "").strip().lower() or "local"
    if source is None:
        return "local"
    raw = getattr(source, "platform", "") or ""
    return str(getattr(raw, "value", raw) or "local").strip().lower() or "local"


class NameBook:
    def __init__(self, path: Path) -> None:
        self.path = Path(path)

    def get(self, player_id: str) -> str:
        return self._read().get(player_id, "")

    def remember(self, player_id: str, name: str) -> None:
        data = self._read()
        data[player_id] = name
        self._write(data)

    def set(self, player: Player, words: list[str]) -> str:
        where = "Discord" if player.platform == "discord" else player.platform
        if not words:
            return f"You are {player.name} on {where}."
        chosen = clean_name(" ".join(words))
        if not chosen:
            return "Usage: /games name Argo"
        self.remember(player.id, chosen)
        player.name = chosen
        player.named = True
        return f"You are {chosen} on {where}."

    def _read(self) -> dict[str, str]:
        if not self.path.is_file():
            return {}
        try:
            loaded = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        if not isinstance(loaded, dict):
            return {}
        return {str(key): str(value) for key, value in loaded.items()}

    def _write(self, data: dict[str, str]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".json.tmp")
        temporary.write_text(json.dumps(data), encoding="utf-8")
        os.replace(temporary, self.path)


def identify(platform: object, source: object, book: NameBook) -> Player:
    """Build the person from the Hermes session. A Discord user id is the stable key."""
    bot = bool(getattr(source, "is_bot", False))
    user_id = str(getattr(source, "user_id", "") or "").strip()
    shown = clean_name(str(getattr(source, "user_name", "") or ""))
    where = _platform_name(platform, source)
    player_id = f"{where}:{user_id}" if user_id else "local"
    saved = book.get(player_id)
    if saved:
        name = saved
        named = True
    elif shown:
        name = shown
        book.remember(player_id, name)
        named = True
    else:
        name = "You"
        named = False
    return Player(player_id, name, where, bot, named)
