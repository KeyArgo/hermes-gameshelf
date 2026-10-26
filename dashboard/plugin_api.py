"""Game Shelf backend for the Hermes Desktop lobby page. Mounted at /api/plugins/hermes-gameshelf/.

Every action is a /games line run as the person at this Desktop, the same as typing it.
The page never applies a move or seats an AI on its own.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from fastapi import APIRouter

_HERE = Path(__file__).resolve().parent.parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from shelf.catalog import Catalog  # noqa: E402
from shelf.commands import run  # noqa: E402
from shelf.lobby import snapshot  # noqa: E402
from shelf.who import NameBook, identify  # noqa: E402

router = APIRouter()

_LINE = 300


def _config() -> dict:
    try:
        from hermes_cli.config import load_config

        return load_config() or {}
    except Exception:
        return {}


def _settings(config: dict) -> dict[str, Any]:
    entry = ((config.get("plugins") or {}).get("entries") or {}).get("hermes-gameshelf") or {}
    chosen = (entry.get("settings") or {}).get("allow_ai", (entry.get("config") or {}).get("allow_ai", True))
    return {"allow_ai": bool(chosen), "role": "referee"}


def _enabled(config: dict):
    listed = (config.get("plugins") or {}).get("enabled")
    if not isinstance(listed, list):
        return None
    names = {str(item) for item in listed}
    return lambda plugin_id: plugin_id in names


def _data_root() -> Path:
    from plugins.plugin_storage import plugin_data_dir

    return plugin_data_dir("hermes-gameshelf")


def _open() -> tuple[Catalog, NameBook]:
    config = _config()
    root = _data_root()
    catalog = Catalog([_HERE.parent], root, _settings(config), enabled=_enabled(config))
    return catalog, NameBook(root / "players.json")


def _say(line: str) -> str:
    catalog, book = _open()
    player = identify("desktop", None, book)
    return run(catalog, line, source="command", player=player, names=book)


@router.get("/view")
def view() -> dict:
    catalog, book = _open()
    player = identify("desktop", None, book)
    games = [
        {
            "id": manifest["id"],
            "title": manifest["title"],
            "summary": manifest.get("summary", ""),
            "bots": bool(manifest.get("bots")),
        }
        for manifest in catalog.listed()
    ]
    return {
        "player": {"name": player.name, "named": player.named},
        "allow_ai": bool(catalog.settings.get("allow_ai", True)),
        "games": games,
        "lobby": snapshot(catalog.data_root),
    }


@router.get("/board")
def board(game: str = "") -> dict:
    catalog, _book = _open()
    game = game.strip().lower()
    if not catalog.has(game):
        return {"text": ""}
    return {"text": _say(f"{game} state")}


@router.post("/command")
def command(body: dict | None = None) -> dict:
    line = str((body or {}).get("line") or "").replace("\n", " ").strip()[:_LINE]
    if not line:
        return {"text": "Type a /games line."}
    if line.startswith("/games"):
        line = line[len("/games"):].strip()
    return {"text": _say(line)}
