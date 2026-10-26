"""Find game.json files and load each game the same way."""

from __future__ import annotations

import importlib.util
import inspect
import json
import re
from pathlib import Path
from typing import Any

from .fair import blocked

_ID = re.compile(r"[a-z0-9][a-z0-9-]{0,31}")


def _call(command, raw: str, *, source: str, complete, player) -> str:
    params = inspect.signature(command).parameters
    kwargs = {"source": source, "complete": complete}
    accepts_player = "player" in params or any(
        item.kind is inspect.Parameter.VAR_KEYWORD for item in params.values()
    )
    if accepts_player:
        kwargs["player"] = player
    return command(raw, **kwargs)


def _manifest_files(plugin_dir: Path) -> list[Path]:
    """A plugin's own game.json, plus one folder of games beside its plugin.yaml."""
    found: list[Path] = []
    direct = plugin_dir / "game.json"
    if direct.is_file():
        found.append(direct)
    if not (plugin_dir / "plugin.yaml").is_file():
        return found
    for game_dir in sorted(plugin_dir.iterdir()):
        nested = game_dir / "game.json"
        if game_dir.is_dir() and nested.is_file() and nested != direct:
            found.append(nested)
    return found


class Catalog:
    def __init__(
        self,
        roots: list[Path],
        data_root: Path,
        settings: dict[str, Any] | None = None,
        enabled=None,
    ) -> None:
        self.data_root = Path(data_root)
        self.settings = dict(settings or {})
        self._enabled = enabled
        self._manifests: list[tuple[Path, dict[str, Any]]] = []
        self._games: dict[str, Any] = {}
        seen: set[str] = set()
        for root in roots:
            if not root.is_dir():
                continue
            for child in sorted(root.iterdir()):
                if not child.is_dir():
                    continue
                for manifest_path in _manifest_files(child):
                    try:
                        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                    except (OSError, json.JSONDecodeError):
                        continue
                    game_id = str(manifest.get("id") or "")
                    if not _ID.fullmatch(game_id) or game_id in seen:
                        continue
                    if not manifest.get("entry") or not manifest.get("title"):
                        continue
                    plugin_id = str(manifest.get("plugin") or "")
                    if plugin_id and self._enabled is not None and not self._enabled(plugin_id):
                        continue
                    seen.add(game_id)
                    self._manifests.append((manifest_path.parent, manifest))

    def list_text(self) -> str:
        if not self._manifests:
            return "No games yet. A plugin joins by adding game.json next to its plugin."
        lines = ["Game Shelf"]
        for manifest in self.listed():
            line = f"{manifest['id']}: {manifest['title']} — {manifest.get('summary', '')}".rstrip()
            if manifest.get("bots"):
                line += " Bots can play."
            lines.append(line)
        lines.append("Play: /games connect4 new")
        lines.append("Find people: /games chat say anyone for reversi?  /games looking reversi")
        return "\n".join(lines)

    def listed(self) -> list[dict[str, Any]]:
        """Games shown on /games. A game.json with "listed": false still plays by id."""
        return [manifest for _directory, manifest in self._manifests if manifest.get("listed", True) is not False]

    def has(self, game_id: str) -> bool:
        return any(manifest["id"] == game_id for _directory, manifest in self._manifests)

    def allows_bots(self, game_id: str) -> bool | None:
        """True when this game welcomes a bot account. None when it is not on the shelf."""
        for _directory, manifest in self._manifests:
            if manifest["id"] == game_id:
                return bool(manifest.get("bots"))
        return None

    def title(self, game_id: str) -> str:
        for _directory, manifest in self._manifests:
            if manifest["id"] == game_id:
                return str(manifest.get("title") or game_id)
        return game_id

    def bot_titles(self) -> list[str]:
        return [str(manifest["title"]) for manifest in self.listed() if manifest.get("bots")]

    def play(self, game_id: str, raw: str, *, source: str, complete=None, player=None) -> str:
        refusal = blocked(raw, source, allow_ai=bool(self.settings.get("allow_ai", True)))
        if refusal:
            return refusal
        game = self._load(game_id)
        if isinstance(game, str):
            return game
        command = getattr(game, "command", None)
        if not callable(command):
            return f"{game_id} has no command()."
        return str(_call(command, raw, source=source, complete=complete, player=player))

    def _load(self, game_id: str):
        if game_id in self._games:
            return self._games[game_id]
        for directory, manifest in self._manifests:
            if manifest["id"] != game_id:
                continue
            entry = directory / str(manifest["entry"])
            if not entry.is_file():
                return f"{game_id} is missing {manifest['entry']}."
            module_name = f"hermes_gameshelf_game_{game_id.replace('-', '_')}"
            spec = importlib.util.spec_from_file_location(module_name, entry)
            if spec is None or spec.loader is None:
                return f"{game_id} could not be loaded."
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            factory = getattr(module, str(manifest.get("factory") or "create"), None)
            if not callable(factory):
                return f"{game_id} has no create()."
            game = factory(self.data_root / game_id, self.settings)
            self._games[game_id] = game
            return game
        return f"No game named {game_id}. /games lists them."
