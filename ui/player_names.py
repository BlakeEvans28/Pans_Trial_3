"""Helpers for consistent player-name display."""

from __future__ import annotations

import re
from typing import Mapping, Any


DEFAULT_PLAYER_NAMES = {0: "Player 1", 1: "Player 2"}


def normalize_player_names(players: Mapping[int, Any] | None = None) -> dict[int, str]:
    """Return two display names, making duplicate picked names unambiguous."""
    names = dict(DEFAULT_PLAYER_NAMES)
    for player_id in (0, 1):
        raw_name = "" if players is None else str(players.get(player_id, "") or "")
        picked_name = " ".join(raw_name.split()).strip()
        if picked_name:
            names[player_id] = picked_name

    if names[0].casefold() == names[1].casefold():
        base_name = names[1]
        suffix = 1
        candidate = f"{base_name}{suffix}"
        while candidate.casefold() == names[0].casefold():
            suffix += 1
            candidate = f"{base_name}{suffix}"
        names[1] = candidate

    return names


def get_window_player_names(window) -> dict[int, str]:
    """Return display names from the active multiplayer session, or defaults."""
    session = getattr(window, "multiplayer_session", None)
    if session is not None:
        return normalize_player_names(getattr(session, "players", None))
    local_names = getattr(window, "local_player_names", None)
    return normalize_player_names(local_names)


def get_player_name(window, player_id: int) -> str:
    """Return one player's display name."""
    return get_window_player_names(window).get(player_id, DEFAULT_PLAYER_NAMES.get(player_id, f"Player {player_id + 1}"))


def replace_player_tokens(text: str, player_names: Mapping[int, str] | None = None) -> str:
    """Replace P1/P2 and Player 1/2 tokens in short UI copy with display names."""
    if not text:
        return text

    names = normalize_player_names(player_names)
    replacements = {
        "Player 1": names[0],
        "Player 2": names[1],
        "P1": names[0],
        "P2": names[1],
    }

    def replace(match: re.Match[str]) -> str:
        return replacements[match.group(0)]

    return re.sub(r"\bPlayer [12]\b|\bP[12]\b", replace, str(text))
