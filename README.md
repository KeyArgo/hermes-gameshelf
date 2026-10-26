# hermes-gameshelf

Game Shelf for **Hermes Agent**. Version **0.1.0**. This is not a Hermes BBS door.

```bash
hermes plugins install KeyArgo/hermes-gameshelf --enable
```

Development snapshots live in the private repo `KeyArgo/hermes-gameshelf-dev` (`0.1.0-dev`).

One shelf for games that run inside **Hermes Agent**.

`/games` lists every title. Games are rows on that list. They do not add their own slash commands. Every game here is worth playing twice: once against another person, and once against a bot when nobody is free.

| Game | Plugin | Who can sit down |
|---|---|---|
| Chess | `agent-arena` (GPL-3) | People. A Hermes profile after you agree. |
| Connect Four | `classic-games` | People, a bot account, or the built-in player after you agree. |
| Kalah | `classic-games` | Same. |
| Reversi | `classic-games` | Same. |
| Gomoku | `classic-games` | Same. |
| Checkers | `classic-games` | Same. |

Tic-tac-toe and Minesweeper still play by id (`/games tictactoe new`). They are not on the list.

## Playing

`/games reversi new` sits you as white. White moves first in every game. The other person types `/games reversi join`, or just plays their move. `/games reversi move d3` plays. `/games reversi state` shows the board. `resign` resigns your own seat. `abandon` ends the game, and only a seated player can do it. `new` will not wipe a game two other people are playing.

`/games allow-ai reversi black=local` is you agreeing to play the built-in player. A model calling `games_play` cannot give that yes. The profile switch `allow_ai: false` turns every AI seat off and still lets people play each other.

Moves:

- Connect Four: `move 4`, a column 1 to 7.
- Kalah: `move 3`, a pit 1 to 6 from your own left.
- Reversi: `move d3`, a1 at the top left. No move means you pass, automatically.
- Gomoku: `move h8` on a 15 by 15 board. Five or more in a row wins.
- Checkers: `move c3 d4`, or a whole jump chain `move c3 e5 c7`. Captures are required. 80 moves with no capture and no crowning is a draw.

## Names and who is who

On IRC and Discord, your nick or display name is used. Your user id there is the key, so two people cannot play each other's turns. Anywhere else, `/games name Argo` sets the name the board shows. On one keyboard (CLI, TUI, Desktop) you can still play both seats.

A bot account can play only the games whose `game.json` says `"bots": true`. Chess does not. A bot cannot type `allow-ai`.

## The lobby

`/games chat say anyone for checkers?` posts a line. `/games chat` shows the last lines. `/games looking checkers` puts you on the list of people who want that game. `/games looking stop` takes you off. `/games doom` is the same lobby, filtered to Doom. The Doom match itself runs later on players' machines.

The lobby belongs to the referee profile. Everyone who talks to that profile shares it.

## A HermesNet IRC games channel

Put one referee profile in the channel through the IRC gateway that ships with Hermes Agent. Everyone in the channel plays through that profile, under their own nick.

```yaml
# config.yaml of the referee profile
gateway:
  platforms:
    irc:
      enabled: true
      extra:
        server: YOUR_HERMESNET_IRC_HOST
        port: 6697
        use_tls: true
        nickname: referee
        channel: "#games"
plugins:
  enabled: [hermes-gameshelf, classic-games, agent-arena]
```

Then `hermes gateway start`.

Two cautions. The IRC gateway only answers nicks in `allowed_users` unless `IRC_ALLOW_ALL_USERS=true`, and with that switch on anyone in the channel can talk to that profile, not only `/games`. Use a profile made for refereeing, with no tools beyond the shelf. A nick is only a person if the server enforces NickServ. On an open server, someone can take a nick and play that seat.

## Hermes Desktop

The plugin ships a lobby page: **Games** in the sidebar, a status-bar button, and *Open Game Shelf* in the command palette. Games on the left, the board in the middle, the lobby chat on the right. New game, Join, Play the built-in player, Looking, Move, Resign, and Abandon each send the same `/games` line you would type. The page shows the text board it gets back. It does not check moves.

The page needs `hermes-gameshelf` in `plugins.enabled` so its backend (`dashboard/plugin_api.py`) loads.

## Add a game

Put this next to your `plugin.yaml`:

```json
{
  "id": "nim",
  "plugin": "my-nim",
  "title": "Nim",
  "summary": "One sentence.",
  "entry": "game.py",
  "factory": "create",
  "bots": false
}
```

`plugin` is your Hermes plugin name. The shelf lists the game when that plugin is enabled. `bots` is optional; set it true when a bot account is a real player of that game. `"listed": false` keeps a game playable by id and off the list. `game.py` provides:

```python
def create(root, settings):
    return Game()

class Game:
    def command(self, raw, *, source, complete=None, player=None) -> str:
        return "..."
```

`source` is `command` when a person typed it and `tool` when a model called it. `player` is who typed it (`id`, `name`, `platform`, `bot`), or `None` from a tool. `complete(prompt)` asks Hermes Agent for one reply. Do not register your own slash command. `/games` is the shelf.

A two-seat game in `classic-games` only writes its rules. `kit.Table` handles seats, turns, consent, saving, and the built-in player.
