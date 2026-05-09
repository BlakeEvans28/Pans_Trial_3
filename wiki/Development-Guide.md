# Development Guide

This page is for contributors who need to change rules, UI, multiplayer behavior, or deployment tooling without fighting the architecture.

## Principles to Preserve

- Keep the engine headless. Do not add Pygame dependencies to `engine/`.
- Prefer typed actions and state transitions over ad hoc UI-side rule logic.
- Let the UI read game state and submit actions instead of mutating rules directly.
- Add or update regression coverage when behavior changes.
- Keep documentation current enough that the next teammate can follow the change.

## Add or Change a Card Effect

Typical files:

- `engine/game_state.py`
- `tests/test_rules.py`
- `ui/board_renderer.py` or `ui/game_screen.py` if the visuals or prompts also change

Typical workflow:

1. Change the rule behavior in `GameState`.
2. Add or update tests for the new state transition.
3. Update the UI only if the new rule needs a new prompt, icon, or visual state.

## Add or Change a Pan Request

Typical files:

- `engine/actions.py`
- `engine/game_state.py`
- `ui/game_screen.py`
- `tests/test_rules.py`

Typical workflow:

1. Add or update the request type definition.
2. Implement the request resolution in the engine.
3. Add the player-facing request flow in the UI.
4. Cover the request with regression tests.

## Add or Change a Screen

Typical files:

- `ui/screen_manager.py`
- `ui/window.py`
- `ui/game_screen.py` when the screen is match-specific

Typical workflow:

1. Add the screen state and transitions.
2. Make sure the new screen hides or shows the right controls.
3. Add smoke checks if the layout or flow is easy to regress.

## Improve AI or Balance Tooling

Typical files:

- `engine/ai.py`
- `balance_testing.py`
- `ARCHITECTURE_FOR_AI.py`

Typical workflow:

1. Improve the agent logic or evaluation heuristic.
2. Run the regression suite.
3. Run a balance sample and compare the resulting win and damage patterns.

## Multiplayer Changes

Typical files:

- `multiplayer/local_room.py`
- `multiplayer/browser_room.py`
- `multiplayer/serialization.py`
- `room_server.py`

Be careful to keep:

- snapshot formats compatible
- browser and Python client behavior aligned
- leave, rematch, and reconnect flows tested

## Good Places to Look First

- [`README.md`](https://github.com/BlakeEvans28/Pans_Trial_3/blob/main/README.md) for the current user-facing project overview
- [`Changes.md`](https://github.com/BlakeEvans28/Pans_Trial_3/blob/main/Changes.md) for recent implementation history
- [`tests/test_rules.py`](https://github.com/BlakeEvans28/Pans_Trial_3/blob/main/tests/test_rules.py) for current expected behavior
- [`PROJECT_STATUS.md`](https://github.com/BlakeEvans28/Pans_Trial_3/blob/main/PROJECT_STATUS.md) and [`ARCHITECTURE_FOR_AI.py`](https://github.com/BlakeEvans28/Pans_Trial_3/blob/main/ARCHITECTURE_FOR_AI.py) for design intent

## Documentation Habit

After meaningful work:

1. Update the relevant docs when behavior changed.
2. Add a short entry to `Changes.md` if the work is noteworthy.
3. Rebuild the web package if the browser deliverable changed.

## Rule of Thumb

If a change feels like "just a UI tweak" but it affects legality, turn order, or victory state, move that logic into the engine instead.

## Related Wiki Pages

- [Project Architecture](Project-Architecture)
- [Testing and Balance](Testing-and-Balance)
- [Publication Case](Publication-Case)
