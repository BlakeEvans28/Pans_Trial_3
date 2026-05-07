# Multiplayer and Rooms

Pan's Trial supports room-code multiplayer for both desktop-adjacent local hosting and browser play.

## What Multiplayer Covers

- Room creation and joining by short room code
- Ready gate before the pregame flow begins
- Shared coin flip and synchronized draft
- Shared Omen order and shared gameplay state
- Reconnect-friendly snapshot polling
- Rematch voting after a finished game
- Leave and decline-rematch handling when a player exits

## Room Lifecycle

The room system uses four main stages:

- `lobby`: players connect, choose names, and mark ready.
- `coin_flip`: both players are ready and the game announces the first drafter.
- `draft`: both players see the same draft pool and alternate picks.
- `game`: the completed pregame state becomes a live shared `GameState`.

After game over, the same room can move into a rematch flow if both players agree.

## Ready Gate

Two-player matches do not start immediately when the second player joins.

- The host creates a room.
- The second player joins using the room code.
- Both players must press `Ready`.
- Only then does the room advance into coin flip and draft.

This prevents accidental starts while one player is still connecting or reading the screen.

## Synchronization Model

The multiplayer code uses synchronized room snapshots plus typed actions.

- Pregame state tracks the labyrinth cards, draft pool, current drafter, drafted hands, Kings drafted, and player identity cards.
- Gameplay state is encoded from the live engine state.
- Clients poll for updates and apply snapshots locally.

Because the game state is serializable, browser and desktop clients can stay aligned without separate rule implementations.

## Python Room Server

The main deployment path is the Python room server in `room_server.py`.

What it does:

- Hosts the room API
- Can serve `WEB_BUILD/site` from the same URL
- Exposes `/health` for uptime checks
- Supports room limits and inactive-room cleanup
- Supports optional TLS with `--certfile` and `--keyfile`

Run it locally:

```powershell
.\.venv-web\Scripts\python.exe room_server.py --host 127.0.0.1 --port 8000
```

Run it for LAN testing:

```powershell
.\.venv-web\Scripts\python.exe room_server.py --host 0.0.0.0 --port 8000
```

## PHP Relay Option

For shared hosts that cannot run a long-lived Python backend, the project also includes `WEB_BUILD/room_server.php`.

This mode:

- Works with browser builds on PHP-capable hosting
- Uses token-aware requests and staged snapshot gates
- Is meant for lightweight hosted multiplayer when Python hosting is unavailable

The Python room server remains the stricter and more authoritative option for competitive or production-style hosting.

## Reconnect, Leave, and Rematch Behavior

- Clients poll for fresh snapshots and can recover room state after short interruptions.
- The browser client records the active room so the page wrapper can attempt a best-effort leave if the tab closes.
- If a player leaves after a finished match, the room can mark the rematch as declined so the other player is told to return to the main menu.
- Rematches require both players to vote yes.

## Important Files

- `multiplayer/local_room.py`
- `multiplayer/browser_room.py`
- `multiplayer/serialization.py`
- `multiplayer/game_setup.py`
- `room_server.py`
- `WEB_BUILD/room_server.php`

## Recommended Reading

- [Web Build and Deployment](Web-Build-and-Deployment)
- [Project Architecture](Project-Architecture)
