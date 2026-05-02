"""Browser-side room client that talks to a Python room server through JavaScript."""

from __future__ import annotations

import json
from typing import Any

from engine import Action, Card, GameState
from .serialization import decode_game_state, decode_room_payload, encode_action


class BrowserRoomClient:
    """Polling client for web builds using the page's JavaScript HTTP bridge."""

    def __init__(self, base_url: str, room_code: str, player_id: int, player_name: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.room_code = room_code
        self.player_id = player_id
        self.player_name = player_name
        self.players: dict[int, str] = {}
        self.ready = False
        self.ready_players: set[int] = set()
        self.stage = "lobby"
        self.revision = -1
        self.message = ""
        self.game: GameState | None = None
        self.draft_cards: list[Card] = []
        self.available_cards: list[Card | None] = []
        self.jack_cards: list[Card] = []
        self.jack_order: list = []
        self.draft_starting_player = 0
        self.current_drafter = 0
        self.draft_hands: dict[int, list[Card]] = {0: [], 1: []}
        self.kings_drafted = 0
        self.player_cards: list[Card] = []
        self.rematch_votes: set[int] = set()
        self.rematch_declined = False
        self.rematch_declined_by: int | None = None
        self.rematch_declined_name = ""
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

    def mark_ready(self) -> bool:
        try:
            snapshot = _bridge_request(
                "POST",
                f"{self.base_url}/rooms/{self.room_code}/ready",
                {"player_id": self.player_id},
            )
            return self._apply_snapshot(snapshot)
        except OSError as exc:
            self.last_error = str(exc)
            return False

    def submit_draft_pick(self, card_index: int) -> bool:
        try:
            snapshot = _bridge_request(
                "POST",
                f"{self.base_url}/rooms/{self.room_code}/draft",
                {
                    "player_id": self.player_id,
                    "revision": self.revision,
                    "card_index": card_index,
                },
            )
            return self._apply_snapshot(snapshot)
        except OSError as exc:
            self.last_error = str(exc)
            return False

    def request_rematch(self) -> bool:
        try:
            snapshot = _bridge_request(
                "POST",
                f"{self.base_url}/rooms/{self.room_code}/rematch",
                {"player_id": self.player_id},
            )
            return self._apply_snapshot(snapshot)
        except OSError as exc:
            self.last_error = str(exc)
            return False

    def decline_rematch(self) -> bool:
        try:
            snapshot = _bridge_request(
                "POST",
                f"{self.base_url}/rooms/{self.room_code}/decline",
                {"player_id": self.player_id},
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
        self.ready_players = {int(player_id) for player_id in snapshot.get("ready_players", [])}
        self.stage = str(snapshot.get("stage") or self.stage)
        self.revision = int(snapshot.get("revision", self.revision))
        self.message = str(snapshot.get("message") or "")
        self.rematch_votes = {int(player_id) for player_id in snapshot.get("rematch_votes", [])}
        self.rematch_declined = bool(snapshot.get("rematch_declined", False))
        raw_declined_by = snapshot.get("rematch_declined_by")
        self.rematch_declined_by = int(raw_declined_by) if raw_declined_by is not None else None
        self.rematch_declined_name = str(snapshot.get("rematch_declined_name") or "")
        self._apply_pregame_snapshot(snapshot.get("pregame") or {})
        if snapshot.get("state"):
            self.game = decode_game_state(snapshot["state"])
        else:
            self.game = None
        self.last_error = None
        return self.revision != previous_revision

    def _apply_pregame_snapshot(self, pregame: dict[str, Any]) -> None:
        if not pregame:
            return
        if pregame.get("draft_cards"):
            self.draft_cards = list(decode_room_payload(pregame["draft_cards"]))
        if pregame.get("available_cards"):
            self.available_cards = list(decode_room_payload(pregame["available_cards"]))
        if pregame.get("jack_cards"):
            self.jack_cards = list(decode_room_payload(pregame["jack_cards"]))
        if pregame.get("jack_order"):
            self.jack_order = list(decode_room_payload(pregame["jack_order"]))
        self.draft_starting_player = int(pregame.get("draft_starting_player", self.draft_starting_player))
        self.current_drafter = int(pregame.get("current_drafter", self.current_drafter))
        if pregame.get("draft_hands"):
            self.draft_hands = {
                int(key): list(value)
                for key, value in dict(decode_room_payload(pregame["draft_hands"])).items()
            }
        self.kings_drafted = int(pregame.get("kings_drafted", self.kings_drafted))
        if pregame.get("player_cards"):
            self.player_cards = list(decode_room_payload(pregame["player_cards"]))


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
