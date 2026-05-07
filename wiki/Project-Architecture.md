# Project Architecture

Pan's Trial is organized around a headless game engine with separate UI, multiplayer, and deployment layers. That split is one of the project's biggest strengths because it allows the same rules to power desktop play, browser play, automated tests, and AI simulations.

## Core Design Principles

- The engine must stay free of Pygame dependencies.
- Game state changes should happen through explicit action objects.
- Rendering should read state, not own rules.
- Multiplayer should synchronize snapshots and actions instead of re-implementing rules.
- New features should land with regression coverage whenever possible.

## High-Level Component Map

```text
main.py
  -> ui/
  -> engine/
  -> multiplayer/   (when using Two Player)

room_server.py
  -> multiplayer/local_room.py
  -> WEB_BUILD/site  (optional static host)

build_web.py
  -> browser-ready bundle
  -> WEB_BUILD/site
```

## Engine Layer

The `engine/` package is the rules core.

- `engine/cards.py`: card models, ranks, suits, role enums, hand helpers, and damage-pile helpers.
- `engine/board.py`: 6x6 toroidal board, player positions, and row or column shifting for `Plane Shift`.
- `engine/actions.py`: typed action objects and request enums used by the UI, multiplayer, and tests.
- `engine/game_state.py`: phase transitions, movement validation, combat, Appeasing Pan, request resolution, hole placement, and victory detection.
- `engine/ai.py`: AI decision logic used by the single-player mode and balance experiments.

Why it matters:

- The engine can be tested without opening a game window.
- Multiplayer clients only need to serialize state and actions.
- AI and balance tools can simulate games directly on the live rules.

## UI Layer

The `ui/` package handles presentation and interaction.

- `ui/window.py`: window lifecycle and top-level rendering loop support.
- `ui/screen_manager.py`: start screen, settings, draft, coin flip, help flow, game-over flow, and shared screen transitions.
- `ui/game_screen.py`: in-match rendering, requests, combat prompts, hole placement, and gameplay status UI.
- `ui/board_renderer.py`: board tiles, suits, role-driven visuals, and coordinate mapping.
- `ui/input_handler.py`: gameplay input interpretation.
- `ui/audio_manager.py`: music and sound behavior.
- `ui/text_entry.py` and `ui/player_names.py`: text field and naming helpers used in menus and multiplayer setup.

The UI should translate user intent into engine actions and then redraw from the updated state.

## Multiplayer Layer

The `multiplayer/` package provides shared-room support.

- `multiplayer/local_room.py`: in-memory room store, HTTP endpoints, local room server, and desktop polling client.
- `multiplayer/browser_room.py`: browser polling client and PHP-relay compatibility logic.
- `multiplayer/serialization.py`: encode and decode helpers for cards, actions, state, and room payloads.
- `multiplayer/game_setup.py`: helpers that create a live `GameState` from synchronized pregame data.

This design keeps one rules engine while supporting both Python-hosted and PHP-relay deployment paths.

## Tooling and Deployment

- `build_web.py`: stages the project for `pygbag`, copies the runtime dependencies, builds browser archives, refreshes `WEB_BUILD/site`, and creates a deployment zip.
- `room_server.py`: serves both the room API and the generated web build from one origin.
- `render.yaml` and `Procfile`: deployment helpers for hosted Python room-server setups.
- `WEB_BUILD/room_server.php`: shared-hosting relay for sites that support PHP file writes but cannot run the Python server.

## Testing and Analysis

- `tests/test_rules.py`: the main regression suite for rules, UI smoke coverage, multiplayer flows, layout checks, and web-serving behavior.
- `balance_testing.py`: headless AI-vs-AI match simulation and report generation.
- `ARCHITECTURE_FOR_AI.py`: design notes and extension patterns for AI agents and RL-style integration.

## Typical Runtime Flow

1. A screen or client gathers user input.
2. The UI or multiplayer client turns that intent into an engine action.
3. `GameState.apply_action()` validates and applies the change.
4. The UI redraws from the new state.
5. In multiplayer, the updated state or action is synchronized through the room layer.

## Why the Architecture Scales

- New rule changes stay concentrated in the engine.
- New UI polish stays concentrated in `ui/`.
- Browser and desktop builds share the same gameplay core.
- Balance studies use the same rule logic as real matches.
- Future AI experiments can plug into a stable action-and-state interface.
