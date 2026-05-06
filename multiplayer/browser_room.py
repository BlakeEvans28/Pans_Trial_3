"""Browser-side room client that talks to a Python room server through JavaScript."""

from __future__ import annotations

import json
from random import choice
from typing import Any
from urllib.parse import quote

from deck_utils import get_jack_suit_order, setup_pregame_cards
from engine import Action, Card, GameState
from engine import ActionType, CardRank
from .game_setup import create_game_from_pregame
from .serialization import (
    decode_game_state,
    decode_room_payload,
    encode_action,
    encode_game_state,
    encode_room_payload,
)


class BrowserRoomClient:
    """Polling client for web builds using the page's JavaScript HTTP bridge."""

    def __init__(self, base_url: str, room_code: str, player_id: int, player_name: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.room_code = room_code
        self.player_id = player_id
        self.player_name = player_name
        self.relay_mode = _is_php_room_server_url(self.base_url)
        self.player_token = ""
        self.players: dict[int, str] = {}
        self.ready = False
        self.ready_players: set[int] = set()
        self.stage = "lobby"
        self.revision = -1
        self.message = ""
        self.game: GameState | None = None
        self.labyrinth_cards: list[Card] = []
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
        self.opponent_departed = False
        self.opponent_departed_name = ""
        self.last_error: str | None = None
        self._poll_elapsed = 0.0

    @classmethod
    def create(cls, player_name: str, base_url: str) -> "BrowserRoomClient":
        response = _bridge_request(
            "POST",
            _room_url(base_url, "rooms"),
            {"name": player_name, "pregame": _create_relay_pregame_payload()},
        )
        client = cls(base_url, response["room_code"], int(response["player_id"]), player_name)
        client._apply_snapshot(response)
        client._remember_active_room()
        return client

    @classmethod
    def join(cls, player_name: str, base_url: str, room_code: str) -> "BrowserRoomClient":
        response = _bridge_request("POST", _room_url(base_url, "rooms", room_code, "join"), {"name": player_name})
        client = cls(base_url, response["room_code"], int(response["player_id"]), player_name)
        client._apply_snapshot(response)
        client._remember_active_room()
        return client

    def update(self, time_delta: float = 0.0) -> bool:
        self._poll_elapsed += time_delta
        if self._poll_elapsed < 0.35:
            return False
        self._poll_elapsed = 0.0
        return self.refresh()

    def refresh(self) -> bool:
        try:
            snapshot = _bridge_request("GET", _room_url(self.base_url, "rooms", self.room_code))
            return self._apply_snapshot(snapshot)
        except OSError as exc:
            self.last_error = str(exc)
            return False

    def submit_action(self, action: Action) -> bool:
        if self.relay_mode:
            return self._submit_relay_action(action)
        try:
            snapshot = _bridge_request(
                "POST",
                _room_url(self.base_url, "rooms", self.room_code, "actions"),
                {
                    "player_id": self.player_id,
                    "player_token": self.player_token,
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
                _room_url(self.base_url, "rooms", self.room_code, "ready"),
                {"player_id": self.player_id, "player_token": self.player_token},
            )
            return self._apply_snapshot(snapshot)
        except OSError as exc:
            self.last_error = str(exc)
            return False

    def submit_draft_pick(self, card_index: int) -> bool:
        if self.relay_mode:
            return self._submit_relay_draft_pick(card_index)
        try:
            snapshot = _bridge_request(
                "POST",
                _room_url(self.base_url, "rooms", self.room_code, "draft"),
                {
                    "player_id": self.player_id,
                    "player_token": self.player_token,
                    "revision": self.revision,
                    "card_index": card_index,
                },
            )
            return self._apply_snapshot(snapshot)
        except OSError as exc:
            self.last_error = str(exc)
            return False

    def request_rematch(self) -> bool:
        if self.relay_mode:
            return self._request_relay_rematch()
        try:
            snapshot = _bridge_request(
                "POST",
                _room_url(self.base_url, "rooms", self.room_code, "rematch"),
                {"player_id": self.player_id, "player_token": self.player_token},
            )
            return self._apply_snapshot(snapshot)
        except OSError as exc:
            self.last_error = str(exc)
            return False

    def decline_rematch(self) -> bool:
        try:
            snapshot = _bridge_request(
                "POST",
                _room_url(self.base_url, "rooms", self.room_code, "decline"),
                {"player_id": self.player_id, "player_token": self.player_token},
            )
            return self._apply_snapshot(snapshot)
        except OSError as exc:
            self.last_error = str(exc)
            return False

    def leave(self) -> None:
        try:
            _bridge_request(
                "POST",
                _room_url(self.base_url, "rooms", self.room_code, "leave"),
                {"player_id": self.player_id, "player_token": self.player_token},
            )
        except OSError:
            pass
        self._clear_active_room()

    def _remember_active_room(self) -> None:
        """Tell the page wrapper which room to leave if the tab closes."""
        try:
            bridge = _get_bridge()
            remember = getattr(bridge, "rememberRoom", None)
            if remember is not None:
                remember(self.base_url, self.room_code, self.player_id, self.player_token)
        except Exception:
            pass

    def _clear_active_room(self) -> None:
        """Clear the page wrapper's best-effort tab-close leave target."""
        try:
            bridge = _get_bridge()
            clear = getattr(bridge, "clearRoom", None)
            if clear is not None:
                clear(self.room_code, self.player_id)
        except Exception:
            pass

    def _submit_relay_draft_pick(self, card_index: int) -> bool:
        previous_snapshot = self._build_snapshot()
        previous_revision = self.revision
        try:
            if not self.ready:
                raise OSError("Both players must be ready before the draft")
            if self.stage not in {"coin_flip", "draft"}:
                raise OSError("The draft is not active")
            if self.player_id != self.current_drafter:
                raise OSError("It is not this player's draft pick")
            if card_index < 0 or card_index >= len(self.available_cards):
                raise OSError("Draft card is out of range")

            card = self.available_cards[card_index]
            if card is None:
                raise OSError("Draft card was already taken")
            if card.rank == CardRank.KING and self.kings_drafted >= 2:
                raise OSError("Only two Heroes may be drafted")

            self.stage = "draft"
            self.draft_hands.setdefault(self.player_id, []).append(card)
            if card.rank == CardRank.KING:
                self.kings_drafted += 1
            self.available_cards[card_index] = None

            total_picks = len(self.draft_hands.get(0, [])) + len(self.draft_hands.get(1, []))
            if total_picks >= 10:
                self.player_cards = [card for card in self.available_cards if card is not None]
                self.game = create_game_from_pregame(
                    self.labyrinth_cards,
                    self.draft_hands.get(0, []),
                    self.draft_hands.get(1, []),
                    self.jack_order,
                    starting_player=1,
                )
                self.stage = "game"
                self.message = "Draft complete. Revealing the omens."
            else:
                self.current_drafter = 1 - self.current_drafter
                next_name = self.players.get(self.current_drafter, f"Player {self.current_drafter + 1}")
                self.message = f"Waiting for {next_name} to draft."

            snapshot = _bridge_request(
                "POST",
                _room_url(self.base_url, "rooms", self.room_code, "draft"),
                {
                    "player_id": self.player_id,
                    "player_token": self.player_token,
                    "revision": previous_revision,
                    "card_index": card_index,
                    "snapshot": self._build_snapshot(),
                },
            )
            return self._apply_snapshot(snapshot)
        except OSError as exc:
            self._apply_snapshot(previous_snapshot)
            self.last_error = str(exc)
            self.refresh()
            self.last_error = str(exc)
            return False

    def _submit_relay_action(self, action: Action) -> bool:
        previous_snapshot = self._build_snapshot()
        previous_revision = self.revision
        try:
            if self.stage != "game" or self.game is None:
                raise OSError("Game has not started yet")
            if action.player_id != self.player_id:
                raise OSError("Submitted action does not belong to this player")

            simultaneous_appeasing_card = (
                getattr(action, "type", None) == ActionType.PLAY_CARD
                and self.game.can_submit_appeasing_card(self.player_id, getattr(action, "card", None))
            )
            if self.game.current_player != self.player_id and not simultaneous_appeasing_card:
                raise OSError("It is not this player's turn")
            if not self.game.apply_action(action):
                raise OSError("Action was rejected by the game rules")

            self._advance_relay_game()
            snapshot = _bridge_request(
                "POST",
                _room_url(self.base_url, "rooms", self.room_code, "actions"),
                {
                    "player_id": self.player_id,
                    "player_token": self.player_token,
                    "revision": previous_revision,
                    "action_player_id": action.player_id,
                    "action_type": getattr(getattr(action, "type", None), "value", str(getattr(action, "type", ""))),
                    "snapshot": self._build_snapshot(),
                    "action": encode_action(action),
                },
            )
            return self._apply_snapshot(snapshot)
        except OSError as exc:
            self._apply_snapshot(previous_snapshot)
            self.last_error = str(exc)
            self.refresh()
            self.last_error = str(exc)
            return False

    def _request_relay_rematch(self) -> bool:
        try:
            snapshot = _bridge_request(
                "POST",
                _room_url(self.base_url, "rooms", self.room_code, "rematch"),
                {
                    "player_id": self.player_id,
                    "player_token": self.player_token,
                    "revision": self.revision,
                    "pregame": _create_relay_pregame_payload(),
                },
            )
            return self._apply_snapshot(snapshot)
        except OSError as exc:
            self.last_error = str(exc)
            return False

    def _advance_relay_game(self) -> None:
        if self.game is None:
            return
        for _ in range(8):
            if not self.game.advance_forced_traversing():
                break
        if self.game.winner is None:
            self.game.check_game_over()

    def _build_snapshot(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "room_code": self.room_code,
            "player_id": self.player_id,
            "players": {str(key): value for key, value in sorted(self.players.items())},
            "ready": self.ready,
            "ready_players": sorted(self.ready_players),
            "stage": self.stage,
            "revision": self.revision,
            "message": self.message,
            "rematch_votes": sorted(self.rematch_votes),
            "rematch_declined": self.rematch_declined,
            "rematch_declined_by": self.rematch_declined_by,
            "rematch_declined_name": self.rematch_declined_name,
            "server_mode": "php_relay" if self.relay_mode else "python_room",
            "pregame": {
                "labyrinth_cards": encode_room_payload(self.labyrinth_cards),
                "draft_cards": encode_room_payload(self.draft_cards),
                "available_cards": encode_room_payload(self.available_cards),
                "jack_cards": encode_room_payload(self.jack_cards),
                "jack_order": encode_room_payload(self.jack_order),
                "draft_starting_player": self.draft_starting_player,
                "current_drafter": self.current_drafter,
                "draft_hands": encode_room_payload(self.draft_hands),
                "kings_drafted": self.kings_drafted,
                "player_cards": encode_room_payload(self.player_cards),
            },
        }
        if self.game is not None:
            payload["state"] = encode_game_state(self.game)
        return payload

    def _apply_snapshot(self, snapshot: dict[str, Any]) -> bool:
        previous_revision = self.revision
        previous_players = dict(self.players)
        if snapshot.get("server_mode") == "php_relay":
            self.relay_mode = True
        if snapshot.get("player_token") is not None:
            self.player_token = str(snapshot.get("player_token") or "")
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
        previous_opponent = previous_players.get(1 - self.player_id, "")
        current_has_opponent = (1 - self.player_id) in self.players
        if previous_opponent and not current_has_opponent and self.stage in {"coin_flip", "draft", "game"}:
            self.opponent_departed = True
            self.opponent_departed_name = previous_opponent
        elif current_has_opponent:
            self.opponent_departed = False
            self.opponent_departed_name = ""
        self.last_error = None
        return self.revision != previous_revision

    def _apply_pregame_snapshot(self, pregame: dict[str, Any]) -> None:
        if not pregame:
            return
        if pregame.get("labyrinth_cards"):
            self.labyrinth_cards = list(decode_room_payload(pregame["labyrinth_cards"]))
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


def _create_relay_pregame_payload() -> dict[str, Any]:
    labyrinth_cards, draft_cards, jack_cards = setup_pregame_cards()
    jack_order = get_jack_suit_order(jack_cards)
    draft_starting_player = choice([0, 1])
    return {
        "labyrinth_cards": encode_room_payload(labyrinth_cards),
        "draft_cards": encode_room_payload(list(draft_cards)),
        "available_cards": encode_room_payload(list(draft_cards)),
        "jack_cards": encode_room_payload(jack_cards),
        "jack_order": encode_room_payload(jack_order),
        "draft_starting_player": draft_starting_player,
        "current_drafter": draft_starting_player,
        "draft_hands": encode_room_payload({0: [], 1: []}),
        "kings_drafted": 0,
        "player_cards": encode_room_payload([]),
    }


def _is_php_room_server_url(base_url: str) -> bool:
    url_without_query = str(base_url or "").split("?", 1)[0].rstrip("/")
    last_part = url_without_query.rsplit("/", 1)[-1].lower()
    return last_part.endswith(".php")


def _room_url(base_url: str, *parts: object) -> str:
    cleaned_base = str(base_url or "").rstrip("/")
    path = "/" + "/".join(quote(str(part).strip("/"), safe="") for part in parts if str(part).strip("/"))
    if _is_php_room_server_url(cleaned_base):
        separator = "&" if "?" in cleaned_base else "?"
        return f"{cleaned_base}{separator}path={quote(path, safe='/')}"
    return f"{cleaned_base}{path}"


def _bridge_request(method: str, url: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    bridge = _get_bridge()
    try:
        raw_response = bridge.request(method, url, json.dumps(payload or {}))
    except Exception as exc:
        raise OSError(_summarize_room_server_error(str(exc))) from exc

    try:
        response = json.loads(str(raw_response or "{}"))
    except json.JSONDecodeError as exc:
        raw_text = str(raw_response or "")
        if _looks_like_html(raw_text):
            raise OSError(_summarize_room_server_error(raw_text)) from exc
        raise OSError(f"Room server returned invalid JSON: {exc}") from exc

    if isinstance(response, dict) and response.get("error"):
        raise OSError(str(response["error"]))
    return response


def _looks_like_html(message: str) -> bool:
    lowered = str(message or "").lstrip().lower()
    return (
        lowered.startswith("<!doctype")
        or lowered.startswith("<html")
        or "<!doctype" in lowered[:300]
        or "<html" in lowered[:300]
    )


def _summarize_room_server_error(message: str) -> str:
    """Keep browser room failures readable when a static page answers API requests."""
    text = " ".join(str(message or "").split())
    if _looks_like_html(text):
        return (
            "This URL is serving a web page, not the Pan's Trial room API. "
            "Start room_server.py and use its Game URL, or add the roomServer URL for the running room server."
        )
    return text or "Room server request failed."


def _get_bridge():
    try:
        import platform

        bridge = getattr(platform.window, "panTrialRoomBridge", None)
    except Exception as exc:
        raise OSError("Browser room bridge is unavailable.") from exc

    if bridge is None:
        raise OSError("Browser room bridge is unavailable.")
    return bridge
