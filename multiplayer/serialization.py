"""Shared local-room serialization helpers."""

from __future__ import annotations

import base64
import pickle

from engine import Action, GameState


def _encode_object(value: object) -> str:
    return base64.b64encode(pickle.dumps(value, protocol=pickle.HIGHEST_PROTOCOL)).decode("ascii")


def _decode_object(value: str) -> object:
    return pickle.loads(base64.b64decode(value.encode("ascii")))


def encode_game_state(game: GameState) -> str:
    """Return a compact local-only string representation of a game state."""
    return _encode_object(game)


def decode_game_state(payload: str) -> GameState:
    """Decode a game state produced by encode_game_state."""
    decoded = _decode_object(payload)
    if not isinstance(decoded, GameState):
        raise ValueError("Payload did not contain a GameState")
    return decoded


def encode_action(action: Action) -> str:
    """Return a compact local-only string representation of a game action."""
    return _encode_object(action)


def decode_action(payload: str) -> Action:
    """Decode an action produced by encode_action."""
    decoded = _decode_object(payload)
    if not isinstance(decoded, Action):
        raise ValueError("Payload did not contain an Action")
    return decoded
