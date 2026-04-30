"""Browser-side room client that talks to a Python room server through JavaScript."""

from __future__ import annotations

import json
from typing import Any

from engine import Action, GameState
from .serialization import decode_game_state, encode_action


class BrowserRoomClient:
    """Polling client for web builds using the page's JavaScript HTTP bridge."""

    def __init__(self, base_url: str, room_code: str, player_id: int, player_name: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.room_code = room_code
        self.player_id = player_id
        self.player_name = player_name
        self.players: dict[int, str] = {}
        self.ready = False
        self.revision = -1
        self.message = ""
        self.game: GameState | None = None
        self.last_error: str | None = None
        self._poll_elapsed = 0.0

    @classmethod
    def create(cls, player_name: str, base_url: str) -> "BrowserRoomClient":
        response = _bridge_request("POST", f"{base_url.rstrip('/')}/rooms", {"name": player_name})
        client = cls(base_url, response["room_code"], int(response["player_id"]), player_name)
        client._apply_snapshot(response)
        return client

    @classmethod
    def join(cls, player_name: str, base_url: str, room_code: str) -> "BrowserRoomClient":
        response = _bridge_request("POST", f"{base_url.rstrip('/')}/rooms/{room_code}/join", {"name": player_name})
        client = cls(base_url, response["room_code"], int(response["player_id"]), player_name)
        client._apply_snapshot(response)
        return client

    def update(self, time_delta: float = 0.0) -> bool:
        self._poll_elapsed += time_delta
        if self._poll_elapsed < 0.35:
            return False
        self._poll_elapsed = 0.0
        return self.refresh()

    def refresh(self) -> bool:
        try:
            snapshot = _bridge_request("GET", f"{self.base_url}/rooms/{self.room_code}")
            return self._apply_snapshot(snapshot)
        except OSError as exc:
            self.last_error = str(exc)
            return False

    def submit_action(self, action: Action) -> bool:
        try:
            snapshot = _bridge_request(
                "POST",
                f"{self.base_url}/rooms/{self.room_code}/actions",
                {
                    "player_id": self.player_id,
                    "revision": self.revision,
                    "action": encode_action(action),
                },
            )
            return self._apply_snapshot(snapshot)
        except OSError as exc:
            self.last_error = str(exc)
            return False

    def leave(self) -> None:
        try:
            _bridge_request(
                "POST",
                f"{self.base_url}/rooms/{self.room_code}/leave",
                {"player_id": self.player_id},
            )
        except OSError:
            pass

    def _apply_snapshot(self, snapshot: dict[str, Any]) -> bool:
        previous_revision = self.revision
        self.players = {int(key): value for key, value in snapshot.get("players", {}).items()}
        self.ready = bool(snapshot.get("ready"))
        self.revision = int(snapshot.get("revision", self.revision))
        self.message = str(snapshot.get("message") or "")
        if snapshot.get("state"):
            self.game = decode_game_state(snapshot["state"])
        self.last_error = None
        return self.revision != previous_revision


def _bridge_request(method: str, url: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    bridge = _get_bridge()
    try:
        raw_response = bridge.request(method, url, json.dumps(payload or {}))
    except Exception as exc:
        raise OSError(str(exc)) from exc

    try:
        response = json.loads(str(raw_response or "{}"))
    except json.JSONDecodeError as exc:
        raise OSError(f"Room server returned invalid JSON: {exc}") from exc

    if isinstance(response, dict) and response.get("error"):
        raise OSError(str(response["error"]))
    return response


def _get_bridge():
    try:
        import platform

        bridge = getattr(platform.window, "panTrialRoomBridge", None)
    except Exception as exc:
        raise OSError("Browser room bridge is unavailable.") from exc

    if bridge is None:
        raise OSError("Browser room bridge is unavailable.")
    return bridge
