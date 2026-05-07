# Pan's Trial Wiki

Pan's Trial is a two-player tactical card-and-labyrinth game built for ECE 348. Players draft high-value cards, reveal Omens that assign each suit a changing role, move through a 6x6 wraparound labyrinth, fight with weapon cards, and enter Appeasing Pan to reshape the board or health state.

This wiki is a GitHub-ready documentation bundle for the current project. It is meant to support players, judges, teammates, and future contributors.

## Start Here

- [Getting Started](Getting-Started)
- [Gameplay and Rules](Gameplay-and-Rules)
- [Project Architecture](Project-Architecture)
- [Multiplayer and Rooms](Multiplayer-and-Rooms)
- [Web Build and Deployment](Web-Build-and-Deployment)
- [Testing and Balance](Testing-and-Balance)
- [Development Guide](Development-Guide)
- [Roadmap](Roadmap)
- [Publishing the Wiki](Publishing-the-Wiki)

## Project Snapshot

- The full gameplay loop is implemented: coin flip, draft, Omen reveal, Traversing, Appeasing Pan, Pan requests, post-Appeasing hole placement, victory resolution, match summary, and rematch flow.
- The project supports single player against AI, two-player room-code multiplayer, desktop play from source, a Windows executable, and a browser build.
- The codebase is split into a headless rules engine, a Pygame UI, multiplayer transport layers, browser build tooling, and automated regression tests.
- The same engine powers gameplay, tests, multiplayer state, and headless balance simulations.

## Suggested Reading Paths

- New players: start with [Getting Started](Getting-Started), then read [Gameplay and Rules](Gameplay-and-Rules).
- Developers: start with [Project Architecture](Project-Architecture), then use [Development Guide](Development-Guide) and [Testing and Balance](Testing-and-Balance).
- Deployment and demo prep: start with [Web Build and Deployment](Web-Build-and-Deployment), then read [Multiplayer and Rooms](Multiplayer-and-Rooms).

## Core Files and Folders

- `main.py` starts the desktop and browser game.
- `engine/` contains the headless game rules.
- `ui/` contains screens, rendering, input, and audio.
- `multiplayer/` contains room clients, room state helpers, and serialization.
- `room_server.py` hosts the room API and can also serve the web build.
- `build_web.py` creates the browser package and deployment site.
- `tests/test_rules.py` contains the main regression suite.
- `balance_testing.py` runs AI-vs-AI balance studies without the UI.
