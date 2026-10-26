"""Game Shelf discovery and the shared fair-play gate."""

from __future__ import annotations

import importlib.util
import json
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLUGINS = ROOT.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from shelf.catalog import Catalog  # noqa: E402
from shelf.commands import run  # noqa: E402
from shelf.who import NameBook, Player, identify  # noqa: E402


def _hello(directory: Path) -> None:
    directory.mkdir(parents=True)
    (directory / "game.json").write_text(json.dumps({
        "id": "hello",
        "plugin": "hello-game",
        "title": "Hello",
        "summary": "A one-word game.",
        "entry": "game.py",
        "factory": "create",
    }), encoding="utf-8")
    (directory / "game.py").write_text(
        "def create(root, settings):\n"
        "    class Game:\n"
        "        def command(self, raw, *, source='command', complete=None):\n"
        "            return f'hello:{source}:{raw}'\n"
        "    return Game()\n",
        encoding="utf-8",
    )


def test_center_lists_chess_and_another_plugin(tmp_path: Path) -> None:
    foreign = tmp_path / "plugins" / "hello-game"
    _hello(foreign)
    catalog = Catalog([PLUGINS, tmp_path / "plugins"], tmp_path / "data", {"allow_ai": True})
    listed = catalog.list_text()
    assert "chess:" in listed
    assert "hello:" in listed
    assert run(catalog, "hello ping", source="tool") == "hello:tool:ping"


def test_center_blocks_an_ai_opposite_a_human_until_a_person_agrees(tmp_path: Path) -> None:
    catalog = Catalog([PLUGINS], tmp_path / "data", {"allow_ai": True})
    refused = run(catalog, "chess new white=human black=@scout", source="tool")
    assert "person" in refused.lower()
    assert not (tmp_path / "data" / "chess" / "match.db").exists()
    agreed = run(catalog, "allow-ai chess black=@scout", source="command")
    assert "White to move" in agreed


def test_profile_floor_blocks_ai_and_still_lets_people_play(tmp_path: Path) -> None:
    catalog = Catalog([PLUGINS], tmp_path / "data", {"allow_ai": False})
    refused = run(catalog, "allow-ai chess black=@scout", source="command")
    assert "off" in refused.lower()
    assert not (tmp_path / "data" / "chess" / "match.db").exists()
    started = run(catalog, "chess new white=human black=human", source="command")
    assert "White to move" in started


def test_disabled_plugin_stays_off_the_shelf(tmp_path: Path) -> None:
    catalog = Catalog(
        [PLUGINS],
        tmp_path / "data",
        {"allow_ai": True},
        enabled=lambda name: name != "agent-arena",
    )
    assert "chess:" not in catalog.list_text()


def test_loads_the_way_hermes_loads_a_plugin(tmp_path: Path) -> None:
    module_name = "hermes_plugins.hermes_gameshelf"
    parent = "hermes_plugins"
    if parent not in sys.modules:
        namespace = types.ModuleType(parent)
        namespace.__path__ = []  # type: ignore[attr-defined]
        namespace.__package__ = parent
        sys.modules[parent] = namespace
    for stale in [key for key in sys.modules if key == module_name or key.startswith(module_name + ".")]:
        del sys.modules[stale]
    spec = importlib.util.spec_from_file_location(
        module_name,
        ROOT / "__init__.py",
        submodule_search_locations=[str(ROOT)],
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    module.__package__ = module_name
    module.__path__ = [str(ROOT)]  # type: ignore[attr-defined]
    sys.modules[module_name] = module
    spec.loader.exec_module(module)

    class Ctx:
        def __init__(self) -> None:
            self.commands: dict = {}
            self.tools: dict = {}

        def get_config(self, key, default=None):
            return {"allow_ai": True}.get(key, default)

        def has_plugin(self, plugin_id: str) -> bool:
            return plugin_id == "agent-arena"

        def register_command(self, name, handler, description=""):
            self.commands[name] = handler

        def register_tool(self, **kwargs):
            self.tools[kwargs["name"]] = kwargs["handler"]

    ctx = Ctx()
    module.register(ctx, data_root=tmp_path / "data", roots=[PLUGINS])
    listed = ctx.commands["games"]("")
    assert "chess:" in listed
    assert "games_play" in ctx.tools


class _Source:
    def __init__(self, user_id: str, user_name: str, bot: bool = False) -> None:
        self.user_id = user_id
        self.user_name = user_name
        self.is_bot = bot
        self.platform = "discord"


def test_discord_name_is_remembered_and_can_be_changed(tmp_path: Path) -> None:
    book = NameBook(tmp_path / "players.json")
    ada = identify("discord", _Source("100", "ada.discord"), book)
    assert ada.id == "discord:100"
    assert ada.name == "ada.discord"
    again = identify("discord", _Source("100", "someone else"), book)
    assert again.name == "ada.discord"
    assert book.set(again, ["Scout"]) == "You are Scout on Discord."
    assert identify("discord", _Source("100", "ada.discord"), book).name == "Scout"


def test_doom_lobby_uses_discord_or_a_chosen_name(tmp_path: Path) -> None:
    catalog = Catalog([PLUGINS], tmp_path / "data", {"allow_ai": True})
    book = NameBook(tmp_path / "players.json")
    guest = identify("", None, book)
    refused = run(catalog, "doom say hello", source="command", player=guest, names=book)
    assert "name" in refused.lower()
    named = run(catalog, "name Argo", source="command", player=guest, names=book)
    assert "Argo" in named
    said = run(catalog, "doom say anyone for a match?", source="command", player=guest, names=book)
    assert "Argo: anyone for a match?" in said
    ada = identify("discord", _Source("100", "ada.discord"), book)
    looking = run(catalog, "doom looking", source="command", player=ada, names=book)
    assert "ada.discord" in looking
    assert "Argo: anyone for a match?" in looking


def test_a_bot_can_play_only_the_games_that_allow_it(tmp_path: Path) -> None:
    catalog = Catalog([PLUGINS], tmp_path / "data", {"allow_ai": True})
    book = NameBook(tmp_path / "players.json")
    bot = identify("discord", _Source("900", "shelf-bot", bot=True), book)
    assert bot.bot and bot.named
    listed = run(catalog, "", source="command", player=bot, names=book)
    assert "Bots can play." in listed
    assert "connect4:" in listed
    chess = run(catalog, "chess new white=human black=human", source="command", player=bot, names=book)
    assert "does not allow bots" in chess
    assert "Connect Four" in chess
    assert not (tmp_path / "data" / "chess" / "match.db").exists()
    opened = run(catalog, "connect4 new", source="command", player=bot, names=book)
    assert "shelf-bot" in opened
    said = run(catalog, "doom say looking for a deathmatch", source="command", player=bot, names=book)
    assert "shelf-bot: looking for a deathmatch" in said
    consent = run(catalog, "allow-ai connect4 black=local", source="command", player=bot, names=book)
    assert "cannot agree" in consent


class _Irc:
    def __init__(self, nick: str) -> None:
        self.user_id = nick
        self.user_name = nick
        self.is_bot = False
        self.platform = "irc"


def test_irc_nicks_are_people_in_the_games_lobby(tmp_path: Path) -> None:
    catalog = Catalog([PLUGINS], tmp_path / "data", {"allow_ai": True})
    book = NameBook(tmp_path / "players.json")
    ada = identify("irc", _Irc("ada"), book)
    bea = identify("irc", _Irc("bea"), book)
    assert (ada.id, ada.name, ada.named) == ("irc:ada", "ada", True)
    said = run(catalog, "chat say anyone for reversi?", source="command", player=ada, names=book)
    assert "ada: anyone for reversi?" in said
    wanted = run(catalog, "looking reversi", source="command", player=bea, names=book)
    assert "bea (reversi)" in wanted
    assert "ada: anyone for reversi?" in wanted
    assert "No game named" in run(catalog, "looking nothing", source="command", player=bea, names=book)
    stopped = run(catalog, "looking stop", source="command", player=bea, names=book)
    assert "bea (reversi)" not in stopped
    opened = run(catalog, "reversi new", source="command", player=ada, names=book)
    assert "waiting" in opened
    assert "ada's turn" in run(catalog, "reversi move d3", source="command", player=bea, names=book)
    assert "ada wants" not in run(catalog, "chat", source="tool")


def test_hidden_games_leave_the_list_and_still_play(tmp_path: Path) -> None:
    catalog = Catalog([PLUGINS], tmp_path / "data", {"allow_ai": True})
    listed = run(catalog, "", source="command")
    assert "tictactoe:" not in listed
    assert "minesweeper:" not in listed
    assert "checkers:" in listed
    assert "Played b2." in run(catalog, "tictactoe new", source="command") + run(
        catalog, "tictactoe move b2", source="command"
    )


def test_desktop_backend_runs_lines_as_the_person_at_the_desktop(tmp_path: Path, monkeypatch) -> None:
    fake = types.ModuleType("fastapi")

    class APIRouter:
        def get(self, _path):
            return lambda handler: handler

        def post(self, _path):
            return lambda handler: handler

    fake.APIRouter = APIRouter  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "fastapi", fake)
    spec = importlib.util.spec_from_file_location("hermes_gameshelf_plugin_api", ROOT / "dashboard" / "plugin_api.py")
    assert spec and spec.loader
    api = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(api)
    monkeypatch.setattr(api, "_data_root", lambda: tmp_path / "data")
    monkeypatch.setattr(api, "_config", lambda: {"plugins": {"enabled": ["hermes-gameshelf", "classic-games"]}})
    view = api.view()
    ids = [game["id"] for game in view["games"]]
    assert "connect4" in ids and "checkers" in ids
    assert "chess" not in ids
    assert "tictactoe" not in ids
    assert view["player"]["named"] is False
    assert "name" in api.command({"line": "chat say hi"})["text"].lower()
    assert "Argo" in api.command({"line": "/games name Argo"})["text"]
    assert "Argo: hi" in api.command({"line": "chat say hi"})["text"]
    assert "White to move." in api.command({"line": "allow-ai kalah black=local"})["text"]
    played = api.command({"line": "kalah move 1"})["text"]
    assert "Local played" in played
    assert "Stores:" in api.board("kalah")["text"]
    assert api.board("../etc")["text"] == ""
    after = api.view()
    assert after["player"] == {"name": "Argo", "named": True}
    assert after["lobby"]["lines"][-1] == {"id": "local", "name": "Argo", "text": "hi"}


def test_two_discord_players_cannot_take_each_others_turn(tmp_path: Path) -> None:
    catalog = Catalog([PLUGINS], tmp_path / "data", {"allow_ai": True})
    ada = Player("discord:1", "Ada", "discord")
    bea = Player("discord:2", "Bea", "discord")
    opened = run(catalog, "connect4 new", source="command", player=ada)
    assert "Ada" in opened
    assert "waiting" in opened
    blocked = run(catalog, "connect4 move 4", source="command", player=bea)
    assert "Ada" in blocked
    played = run(catalog, "connect4 move 4", source="command", player=ada)
    assert "Played 4." in played
    joined = run(catalog, "connect4 move 3", source="command", player=bea)
    assert "Bea" in joined
    stolen = run(catalog, "connect4 move 4", source="command", player=bea)
    assert "Ada" in stolen
