# Pan's Trial

Pan's Trial is a two-player digital strategy game built for ECE 348. Two challengers enter a shifting 6x6 labyrinth, draft powerful cards, reveal Omens that assign each suit a board role, race through the maze, fight with weapon cards, and use the Appeasing Pan phase to reshape the board or alter health totals.

## Current Status

- The full game loop is implemented: draft, coin flip, Omen reveal, Traversing the Labyrinth, Appeasing Pan, Pan requests, post-Appeasing hole placement, game over, match summary, and Play Again.
- The game can be played from the Windows executable, from source with `main.py`, or in a browser through the `pygbag` web build.
- The main menu includes `Single Player Against AI`, `Two Player`, `How To Play`, `Settings`, and `Quit`.
- `Two Player` uses room codes, a Ready gate, synchronized coin flip/draft/Omen reveal/gameplay, reconnect-friendly snapshots, and shared rematch consent.
- The current gameplay HUD shows health remaining out of 25 on the left, the phase banner at the top, and the Omen role legend on the right.
- During Appeasing Pan, the Omen legend lists roles from strongest to weakest and shows an explicit `Strongest` to `Weakest` arrow.
- The latest rule/UI regression suite is `tests/test_rules.py`, currently 111 tests.

## Repository Layout

- `main.py` - desktop and browser game entry point.
- `room_server.py` - room server and static web host for hosted or LAN Two Player games.
- `build_web.py` - stages and packages the browser build.
- `engine/` - core rules, game state, cards, board, and actions.
- `ui/` - pygame screens, board rendering, input handling, audio, and visual helpers.
- `multiplayer/` - local/browser room clients, server store, and serialization helpers.
- `assets/` and `audio/` - checked-in visual and sound assets used by desktop and web builds.
- `tests/test_rules.py` - rule, multiplayer, and UI smoke/regression tests.
- `WEB_BUILD/site` - generated browser site after running `build_web.py`.

## Controls

- `Arrow Keys` or `WASD`: move through the labyrinth.
- `Mouse`: choose draft cards, move with board clicks, pick cards, select hand cards, choose requests, target Ballista shots, choose Plane Shift lines, pick Restructure colors, and place Appeasing cards into holes.
- `Pick Up`: spend a movement turn to collect the card under the active player, except walls.

## Rules Summary

Each game starts with a draft from high-rank cards. The remaining player cards become the player identities, and the Omens assign the four suit families to the current board roles: Walls, Traps, Ballista, and Weapons.

During Traversing the Labyrinth, players alternate movement turns. The board wraps at the edges. Walls block movement. Traps reduce the triggering player's health. Ballista tiles let the player move in a straight line until a wall blocks the path. Weapon-role hand cards are kept for combat and can be used when both players meet on the same tile.

During Appeasing Pan, both players play one normal hand card if possible. Appeasing uses the reversed Omen hierarchy for trump strength, with rank breaking ties only when both cards share the same suit. The winner chooses a Pan request first, then the loser chooses unless `Ignore Us` ends the request sequence. Requests include `Restructure`, `Steal Life`, `Ignore Us`, and `Plane Shift`.

After requests resolve, the Appeasing loser places the two played cards into open labyrinth holes when possible. If holes run out, the remaining cards return to that loser's hand. A player loses when their lost-health total reaches 25 or more, and the other player becomes Pan's champion.

## Run From Source

Use a fresh Python environment from the project folder. Python 3.12 or 3.13 works for desktop play; Python 3.12 is required for the browser build.

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install pygame-ce pygame_gui pandas pytest
.\.venv\Scripts\python.exe main.py
```

## Run Tests

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_rules.py
```

The web-build environment can also run the tests:

```powershell
.\.venv-web\Scripts\python.exe -m pytest tests\test_rules.py
```

## Build The Web Version

The web build uses Python 3.12 and the pygame-web runtime. From the project folder:

```powershell
py -3.12 -m venv .venv-web
.\.venv-web\Scripts\python.exe -m pip install --upgrade pip
.\.venv-web\Scripts\python.exe -m pip install -r requirements-web.txt
.\.venv-web\Scripts\python.exe build_web.py --build-only
```

The build writes a deployable site to:

```text
WEB_BUILD\site
```

It also writes a local deployment zip:

```text
WEB_BUILD\pans_trial_web.zip
```

The zip is intentionally ignored by git because it is large and generated.

## Run The Web Game Locally

For the most accurate local web test, run the room server. It serves both the web game and the `/rooms` multiplayer API from the same origin:

```powershell
.\.venv-web\Scripts\python.exe room_server.py --host 127.0.0.1 --port 8000
```

Open:

```text
http://127.0.0.1:8000
```

For testing from another computer or phone on the same Wi-Fi, bind to all interfaces:

```powershell
.\.venv-web\Scripts\python.exe room_server.py --host 0.0.0.0 --port 8000
```

Then open the printed `LAN Game URL` on each device. The same URL is used for `Two Player`; the first client creates a room code, and the second client joins with that code.

For static single-browser testing only, you can also build and serve in one command:

```powershell
.\.venv-web\Scripts\python.exe build_web.py --port 8000
```

After rebuilding the web version, hard-refresh the browser with `Ctrl+F5` if it still shows an older bundle.

## Hosted Web Deployment

For one hosted URL that supports both the game and multiplayer rooms:

```powershell
.\.venv-web\Scripts\python.exe build_web.py --build-only
.\.venv-web\Scripts\python.exe room_server.py --host 0.0.0.0
```

The included `Procfile` and `render.yaml` are set up for hosts that can run the room server and serve `WEB_BUILD/site`. Hosted room servers expose `/health` for uptime checks. Room limits can be tuned with `PAN_TRIAL_MAX_ROOMS`, `PAN_TRIAL_ROOM_TIMEOUT_SECONDS`, or the matching `room_server.py` flags.

If the page is served over HTTPS, the room API should also be HTTPS. Browsers often block an HTTPS page from contacting a plain HTTP room server. To run the room server with TLS:

```powershell
.\.venv-web\Scripts\python.exe room_server.py --certfile path\to\cert.pem --keyfile path\to\key.pem
```

## Build The Windows Executable

The current checked-in executable is `Pans_Trial.exe`. To rebuild it from source with the included PyInstaller spec:

```powershell
.\.venv\Scripts\python.exe -m pip install pyinstaller
.\.venv\Scripts\python.exe -m PyInstaller --noconfirm --clean --distpath . --workpath build\pyinstaller_slim Pans_Trial_slim.spec
```

## Submission Notes

For a lightweight GitHub submission, the executable, gameplay video, and README can be attached directly, while the full source project can be distributed as a release zip. The active development workspace contains the full source, assets, tests, web build tooling, room server, and supporting reports.
