""" /games is the front door. The game id picks which plugin handles the rest."""

from __future__ import annotations

import shlex

from .catalog import Catalog
from .lobby import looking, talk
from .who import NameBook

_LOBBY = {"chat", "looking", "doom", "name"}


def run(
    catalog: Catalog,
    raw: str,
    *,
    source: str = "command",
    complete=None,
    player=None,
    names: NameBook | None = None,
) -> str:
    try:
        parts = shlex.split(raw or "")
    except ValueError:
        return "Could not read that. Try /games"
    if not parts:
        return catalog.list_text()
    refusal = _bot_refusal(catalog, parts, player)
    if refusal:
        return refusal
    head = parts[0].lower()
    if head == "chat":
        return talk(catalog.data_root, player, parts[1:])
    if head == "doom":
        return talk(catalog.data_root, player, parts[1:], game="doom")
    if head == "looking":
        game = parts[1].lower() if len(parts) > 1 else ""
        return looking(catalog.data_root, player, game, catalog.has(game))
    if head == "name":
        if names is None or player is None:
            return "Type /games name Argo"
        return names.set(player, parts[1:])
    if head in {"allow-ai", "allow_ai"}:
        if len(parts) < 2:
            return "Usage: /games allow-ai connect4 black=local"
        game_id = parts[1].lower()
        rest = "allow-ai " + " ".join(parts[2:])
        return catalog.play(game_id, rest, source=source, complete=complete, player=player)
    rest = " ".join(parts[1:])
    if not rest:
        return catalog.play(head, "help", source=source, complete=complete, player=player)
    return catalog.play(head, rest, source=source, complete=complete, player=player)


def _bot_refusal(catalog: Catalog, parts: list[str], player) -> str | None:
    """A bot may play only the games that say so. Chess stays a person's seat."""
    if player is None or not getattr(player, "bot", False):
        return None
    head = parts[0].lower()
    if head in _LOBBY:
        return None
    if head in {"allow-ai", "allow_ai"} or (len(parts) > 1 and parts[1].lower() in {"allow-ai", "allow_ai"}):
        return "A bot cannot agree to an AI seat. A person types /games allow-ai."
    allowed = catalog.allows_bots(head)
    if allowed is None or allowed:
        return None
    welcome = catalog.bot_titles()
    title = catalog.title(head)
    if welcome:
        return f"{title} does not allow bots. Bots can play {', '.join(welcome)}."
    return f"{title} does not allow bots."
