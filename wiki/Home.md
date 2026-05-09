# Pan's Trial Wiki

![Pan's Trial title art](https://raw.githubusercontent.com/BlakeEvans28/Pans_Trial_3/main/assets/PanTitle.png)

Pan's Trial is a two-player tactical card-and-labyrinth game built for ECE 348. Players draft high-value cards, reveal Omens that assign each suit a changing role, move through a 6x6 wraparound labyrinth, fight with weapon cards, and enter Appeasing Pan to reshape the board or health state.

This wiki is the digital report for the project. It reorganizes the written report into GitHub pages with direct links between rules, architecture, testing evidence, publication goals, code, media, and references.

## Live Links

- [Playthrough video](https://youtu.be/l11MAYjyqTs)
- [Professor-hosted web build](https://drpeterjamieson.com/PROJECTS/PANS_TRIAL/index.html)

## Report Goal

The written report argues that Pan's Trial is more than a class prototype: it is a playable, web-ready vertical slice that can continue toward public release. The wiki keeps that argument navigable:

- [Publication Case](Publication-Case) explains the problem, design hook, market strategy, and recommended next steps.
- [Gameplay and Rules](Gameplay-and-Rules) documents the player-facing rules and links rule behavior back to the implementation.
- [Project Architecture](Project-Architecture) shows how the code is split into engine, UI, multiplayer, build, and test layers.
- [Testing and Balance](Testing-and-Balance) summarizes the regression suite and the AI-vs-AI balance study.
- [Media and References](Media-and-References) collects images, video, audio, and the references cited by the report.

## Project Snapshot

- The full gameplay loop is implemented: coin flip, draft, Omen reveal, Traversing, Appeasing Pan, all four Pan requests, post-Appeasing hole placement, victory resolution, match summary, and rematch flow.
- The project supports single player against AI, two-player room-code multiplayer, desktop play from source, a Windows executable path, and a browser build.
- The codebase is split into a headless rules engine, a Pygame UI, multiplayer transport layers, browser build tooling, and automated regression tests.
- The same engine powers gameplay, tests, multiplayer state, and headless balance simulations.
- The web-first strategy lets the game become a one-link demo before later desktop, itch.io, Steam, or mobile/tablet releases.

## Start Here

- [Getting Started](Getting-Started)
- [Gameplay and Rules](Gameplay-and-Rules)
- [Publication Case](Publication-Case)
- [Project Architecture](Project-Architecture)
- [Multiplayer and Rooms](Multiplayer-and-Rooms)
- [Web Build and Deployment](Web-Build-and-Deployment)
- [Testing and Balance](Testing-and-Balance)
- [Development Guide](Development-Guide)
- [Roadmap](Roadmap)
- [Media and References](Media-and-References)
- [Publishing the Wiki](Publishing-the-Wiki)

## Suggested Reading Paths

- New players: start with [Getting Started](Getting-Started), then read [Gameplay and Rules](Gameplay-and-Rules).
- Instructors and reviewers: read [Publication Case](Publication-Case), [Testing and Balance](Testing-and-Balance), then [Media and References](Media-and-References).
- Developers: start with [Project Architecture](Project-Architecture), then use [Development Guide](Development-Guide) and [Testing and Balance](Testing-and-Balance).
- Deployment and demo prep: start with [Web Build and Deployment](Web-Build-and-Deployment), then read [Multiplayer and Rooms](Multiplayer-and-Rooms).

## Core Code Links

- [`main.py`](https://github.com/BlakeEvans28/Pans_Trial_3/blob/main/main.py) starts the desktop and browser game.
- [`engine/`](https://github.com/BlakeEvans28/Pans_Trial_3/tree/main/engine) contains the headless game rules.
- [`ui/`](https://github.com/BlakeEvans28/Pans_Trial_3/tree/main/ui) contains screens, rendering, input, and audio.
- [`multiplayer/`](https://github.com/BlakeEvans28/Pans_Trial_3/tree/main/multiplayer) contains room clients, room state helpers, and serialization.
- [`room_server.py`](https://github.com/BlakeEvans28/Pans_Trial_3/blob/main/room_server.py) hosts the room API and can also serve the web build.
- [`build_web.py`](https://github.com/BlakeEvans28/Pans_Trial_3/blob/main/build_web.py) creates the browser package and deployment site.
- [`tests/test_rules.py`](https://github.com/BlakeEvans28/Pans_Trial_3/blob/main/tests/test_rules.py) contains the main regression suite.
- [`balance_testing.py`](https://github.com/BlakeEvans28/Pans_Trial_3/blob/main/balance_testing.py) runs AI-vs-AI balance studies without the UI.
