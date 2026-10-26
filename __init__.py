"""Hermes Agent plugin: Game Shelf. /games is the only game command."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

try:
    from .shelf.catalog import Catalog
    from .shelf.commands import run
    from .shelf.who import NameBook, identify
except ImportError:
    from shelf.catalog import Catalog
    from shelf.commands import run
    from shelf.who import NameBook, identify


def plugin_roots() -> list[Path]:
    """Sibling plugins of this one. That is ~/.hermes/plugins when installed."""
    return [Path(__file__).resolve().parent.parent]


def open_catalog(
    data_root: Path,
    settings: dict[str, Any] | None = None,
    roots: list[Path] | None = None,
    enabled=None,
) -> Catalog:
    return Catalog(roots if roots is not None else plugin_roots(), data_root, settings, enabled=enabled)


def register(ctx: Any, *, data_root: Path | None = None, roots: list[Path] | None = None) -> None:
    def settings() -> dict[str, Any]:
        return {"allow_ai": ctx.get_config("allow_ai", default=True), "role": "referee"}

    def root() -> Path:
        if data_root is not None:
            return data_root
        from plugins.plugin_storage import plugin_data_dir
        return plugin_data_dir("hermes-gameshelf")

    def enabled(plugin_id: str) -> bool:
        has = getattr(ctx, "has_plugin", None)
        if not callable(has):
            return True
        return bool(has(plugin_id))

    def catalog() -> Catalog:
        return open_catalog(root(), settings(), roots, enabled=enabled)

    def on_games(raw: str = "", **kwargs: Any) -> str:
        book = NameBook(root() / "players.json")
        player = identify(kwargs.get("platform") or "", kwargs.get("source"), book)
        return run(
            catalog(),
            raw,
            source="command",
            complete=_complete(ctx, settings),
            player=player,
            names=book,
        )

    ctx.register_command(
        "games",
        on_games,
        "Game Shelf. /games lists the games. /games reversi new. /games chat say hi",
    )

    def games_play(args: dict, **kwargs: Any) -> str:
        del kwargs
        if not isinstance(args, dict):
            return json.dumps({"ok": False, "reason": "bad_args"})
        game_id = str(args.get("game") or "")
        line = str(args.get("line") or "")
        text = run(catalog(), f"{game_id} {line}".strip(), source="tool", complete=_complete(ctx, settings))
        return json.dumps({"ok": True, "text": text})

    ctx.register_tool(
        name="games_play",
        toolset="hermes_gameshelf",
        schema={
            "name": "games_play",
            "description": (
                "Play a game on the Game Shelf. The person plays, or they type "
                "/games allow-ai before an AI takes a seat."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "game": {"type": "string"},
                    "line": {"type": "string", "description": "The game command, such as move e4"},
                },
                "required": ["game", "line"],
            },
        },
        handler=games_play,
    )


def _complete(ctx: Any, settings):
    del settings

    def complete(prompt: str) -> dict[str, Any]:
        result = ctx.llm.complete(
            messages=[
                {"role": "system", "content": "Answer with one legal game action and nothing else."},
                {"role": "user", "content": prompt},
            ],
            max_tokens=80,
            purpose="hermes-gameshelf",
        )
        usage = getattr(result, "usage", None)
        tokens = int(usage.get("total_tokens") or 0) if isinstance(usage, dict) else int(getattr(usage, "total_tokens", 0) or 0)
        return {"move": str(getattr(result, "text", "") or ""), "remark": "", "tokens": tokens}

    return complete
