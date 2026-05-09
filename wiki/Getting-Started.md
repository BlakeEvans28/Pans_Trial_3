# Getting Started

This page is the quickest way to run Pan's Trial locally, understand the controls, and choose the right launch path for your use case.

## Choose a Run Path

- `Pans_Trial.exe`: quickest Windows launch if you just want to play the checked-in desktop build.
- `main.py`: best path for active development and local desktop testing.
- `build_web.py`: best path when you need the browser build or hosted multiplayer flow.
- `room_server.py`: best path when you want the browser build and room-code multiplayer from one local URL.

## Prerequisites

- Python `3.12` or `3.13` works for desktop play from source.
- Python `3.12` is required for the browser build path.
- Windows PowerShell commands below assume you are in the project root.

## Run the Desktop Game From Source

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install pygame-ce pygame_gui pandas pytest
.\.venv\Scripts\python.exe main.py
```

## Run the Browser Build Locally

```powershell
py -3.12 -m venv .venv-web
.\.venv-web\Scripts\python.exe -m pip install --upgrade pip
.\.venv-web\Scripts\python.exe -m pip install -r requirements-web.txt
.\.venv-web\Scripts\python.exe build_web.py --build-only
.\.venv-web\Scripts\python.exe room_server.py --host 127.0.0.1 --port 8000
```

Then open:

```text
http://127.0.0.1:8000
```

## Quick LAN Multiplayer

To test with another computer or phone on the same network:

```powershell
.\.venv-web\Scripts\python.exe room_server.py --host 0.0.0.0 --port 8000
```

Open the printed `LAN Game URL` on each device. The same URL hosts both the browser game and the room API.

## Main Menu Options

- `Single Player Against AI`: local game against the current AI.
- `Two Player`: room-code multiplayer flow.
- `How To Play`: in-game rules overview.
- `Settings`: display, text, sound, tutorial, and related options.
- `Quit`: exits the game.

## Controls

- `Arrow Keys` or `WASD`: move through the labyrinth.
- `Mouse`: choose draft cards, click board moves, target Ballista launches, play hand cards, choose requests, resolve request popups, and place Appeasing cards into holes.
- `Pick Up`: spend a Traversing turn to interact with the card on the current tile when the tile is not a Wall.

## First Session Flow

1. Start the game and choose either single-player or two-player mode.
2. Complete the coin flip and face-card draft.
3. Review the Omen assignments before gameplay starts.
4. Play through Traversing and Appeasing Pan cycles until one player reaches 25 or more damage.
5. Use the match summary and rematch flow after game over.

## What to Notice During a Demo

- The Omen legend explains which suits currently act as Walls, Traps, Ballista, and Weapons.
- During Appeasing Pan, the role order explains why one submitted card wins request priority.
- Request screens are intentionally guided because Restructure, Steal Life, Ignore Us, and Plane Shift are state-heavy effects.
- The same rules are enforced in single player, room-code multiplayer, tests, and balance simulations.

## Useful Next Pages

- [Gameplay and Rules](Gameplay-and-Rules)
- [Multiplayer and Rooms](Multiplayer-and-Rooms)
- [Web Build and Deployment](Web-Build-and-Deployment)
- [Media and References](Media-and-References)
