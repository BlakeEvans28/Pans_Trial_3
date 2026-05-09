# Publication Case

This page adapts the written final report into a web-readable argument for why Pan's Trial should continue beyond the class prototype stage.

## Executive Summary

Pan's Trial is a two-player tactical card-and-labyrinth game. Each match begins with a public draft, then assigns four card families to changing roles: Walls, Traps, Ballista, and Weapons. Players traverse a 6x6 toroidal labyrinth, collect or trigger cards, fight with weapon cards, and periodically enter Appeasing Pan, a second phase where card strength determines who receives first choice of a powerful request.

The digital version solves the hardest parts of the tabletop concept. It tracks movement legality, wraparound edges, changing suit roles, combat legality, health totals, request resolution, and post-Appeasing card placement automatically. That lets players focus on strategy instead of rule maintenance.

The project is also built like a product candidate. It has a headless rules engine, a Pygame interface, room-code multiplayer, browser build tooling, a local and hosted server path, regression tests, and a balance harness. Those systems make the game testable, publishable, and practical for continued engineering.

## Problem and Relevance

Many tabletop strategy games are exciting because they ask players to manage board position, hidden resources, role changes, damage, timing, and future threats. That same richness can become a barrier when players must constantly maintain the rules by hand.

Pan's Trial addresses that problem by digitizing a compact but layered two-player design. It keeps the tabletop feel of cards, drafting, and spatial tactics while the software handles legality, feedback, state transitions, and scoring. The result is easier to learn, easier to test, and easier to publish than the original physical prototype.

## Publishable Hook

Pan's Trial can be pitched in one sentence:

> Draft cards, survive a shifting labyrinth, and bargain with Pan for power.

That hook works because it communicates genre, conflict, and theme. The game also creates clear visual moments: a player lands on a Trap, a Ballista line opens across the board, Omens swap suit roles, or the Appeasing winner reshapes the labyrinth.

## Why the Digital Design Works

- The 6x6 toroidal board is easier to play when software handles wraparound movement.
- The Omen legend keeps role assignments visible throughout the match.
- Appeasing Pan can show the strongest-to-weakest role order at the moment it matters.
- Requests such as Restructure, Steal Life, Ignore Us, and Plane Shift can be presented as guided UI flows.
- The code enforces legality, which makes the game more approachable for new players and more reliable for competitive play.

For the full rule flow, see [Gameplay and Rules](Gameplay-and-Rules).

## Engineering Readiness

The current source tree is not a throwaway prototype. It includes:

| Area | Responsibility |
| --- | --- |
| [`engine/`](https://github.com/BlakeEvans28/Pans_Trial_3/tree/main/engine) | Cards, board, game state, actions, phase transitions, requests, combat, win detection, and serializable rules state. |
| [`ui/`](https://github.com/BlakeEvans28/Pans_Trial_3/tree/main/ui) | Pygame screens, game rendering, board rendering, input handling, audio, icons, tutorial overlays, and themed panels. |
| [`multiplayer/`](https://github.com/BlakeEvans28/Pans_Trial_3/tree/main/multiplayer) | Local and browser room clients, room storage, HTTP room API, snapshots, ready/rematch flow, and serialization. |
| [`build_web.py`](https://github.com/BlakeEvans28/Pans_Trial_3/blob/main/build_web.py) | Browser staging, asset handling, runtime packaging, archives, and web deployment output. |
| [`room_server.py`](https://github.com/BlakeEvans28/Pans_Trial_3/blob/main/room_server.py) | Static web hosting, room API, `/health`, LAN binding, room limits, cleanup, and optional TLS. |
| [`tests/`](https://github.com/BlakeEvans28/Pans_Trial_3/tree/main/tests) | Regression tests for rules, multiplayer, web serving, layout, rematch behavior, text entry, and UI smoke coverage. |

For implementation details, see [Project Architecture](Project-Architecture) and [Development Guide](Development-Guide).

## Design Constraints

| Constraint | Current response |
| --- | --- |
| Two-player duel | Room-code multiplayer keeps the game focused on direct competitive decisions. |
| Changing suit roles | The Omen legend stays visible, and Appeasing Pan shows role strength during card comparison. |
| State-heavy requests | The UI guides each request with prompts, highlights, and confirmation controls. |
| Cross-platform delivery | Pygame-CE powers desktop play, while Pygbag packages the same source for browser play. |
| Low-friction multiplayer | `room_server.py` can serve both the web game and room API from one origin. |
| Future feature work | The engine/UI split lets engineers add rules with focused changes and tests. |

## Evidence

The written report highlights two important results:

- The regression suite verifies the rules, multiplayer flow, browser serving behavior, rematch handling, UI smoke checks, and layout-sensitive flows.
- A 100-game AI-vs-AI balance study produced a near-even seat split, with Player 1 winning 52 games and Player 2 winning 48.

The balance study also found average final damage values of 19.22 for Player 1 and 19.24 for Player 2, suggesting the core loop stays competitive. Stronger AI profiles also beat weaker profiles at high rates, which supports the claim that the game rewards better decisions rather than only starting position or randomness.

For the detailed verification page, see [Testing and Balance](Testing-and-Balance).

## Web-First Strategy

The strongest publication path is web-first. A player can open one URL, create a room, share a code, and play without installing Python or a desktop executable. That matters for judges, classmates, friends, public playtests, and future customers.

The recommended platform sequence is:

1. Public web demo with tutorial, two-player rooms, feedback collection, and a stable hosted room server.
2. Itch.io release as either pay-what-you-want or a low fixed price.
3. Steam release after tutorial, polish, and stability improve.
4. Mobile or tablet version once touch layout and hosted multiplayer are production-ready.

The safest monetization principle is to avoid selling competitive power. Paid content should be cosmetic, access-based, or convenience-based so the fairness evidence remains credible.

## Next Product Work

- Add an in-game first-run tutorial and a Solo Tutorial mode.
- Harden reconnect, leave, and server-error messaging.
- Tune match length and request balance using the existing simulation harness.
- Prepare a trailer, screenshots, and store-page copy.
- Host a public HTTPS demo backed by the Python room server where possible.

See [Roadmap](Roadmap) for the working priority order.
