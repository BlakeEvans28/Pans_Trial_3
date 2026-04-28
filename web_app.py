"""
Dependency-free localhost browser server for Pan's Trial.

This starts a small HTTP server that hosts a browser client, keeps in-memory
rooms, and routes browser actions through the existing Python game engine.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import mimetypes
from pathlib import Path
from threading import Lock
from time import time
from types import SimpleNamespace
from urllib.parse import parse_qs, urlparse
from uuid import uuid4

from engine import (
    CardSuit,
    ChooseCombatCardAction,
    ChooseRequestAction,
    GamePhase,
    MoveAction,
    PickupCurrentCardAction,
    PlaceCardsAction,
    PlayCardAction,
    Position,
    RequestType,
    ResolveBallistaShotAction,
    ResolvePlaneShiftAction,
    SelectDamageCardAction,
    SelectPlaneShiftDirectionAction,
    SelectRestructureSuitAction,
)
from game_setup import create_random_game
from multiplayer import generate_room_code
from pan_theme import get_family_name, get_rank_name


HOST = "127.0.0.1"
PORT = 8000
WEB_ROOT = Path(__file__).resolve().parent / "web_client"
TOKEN_HEADER = "X-PanTrial-Token"

REQUEST_TYPE_MAP = {
    "restructure": RequestType.RESTRUCTURE,
    "steal_life": RequestType.STEAL_LIFE,
    "ignore_us": RequestType.IGNORE_US,
    "plane_shift": RequestType.PLANE_SHIFT,
}


@dataclass
class BrowserSession:
    """One browser player's room/session identity."""

    token: str
    room_code: str
    player_id: int
    player_name: str
    joined_at: float = field(default_factory=time)


@dataclass
class BrowserRoom:
    """One room in the browser-hosted local server."""

    room_code: str
    players: dict[int, BrowserSession] = field(default_factory=dict)
    game_state: object | None = None
    status: str = "waiting"
    message: str = "Waiting for a second player to join."
    latest_notice: str | None = None
    updated_at: float = field(default_factory=time)


class BrowserGameService:
    """In-memory room and game manager for the browser version."""

    def __init__(self):
        self._lock = Lock()
        self._rooms: dict[str, BrowserRoom] = {}
        self._sessions: dict[str, BrowserSession] = {}

    def create_room(self, player_name: str, requested_code: str | None = None) -> dict:
        """Create a room and join it as player 1."""
        with self._lock:
            room_code = (requested_code or "").strip().upper() or self._new_room_code()
            if room_code in self._rooms:
                raise ValueError(f"Room {room_code} already exists.")
            room = BrowserRoom(room_code=room_code, message="Waiting for a second player to join.")
            self._rooms[room_code] = room
            session = self._add_session_to_room(room, player_name)
            return self._serialize_room_join(session, room)

    def join_room(self, room_code: str, player_name: str) -> dict:
        """Join an existing room as the next available player."""
        with self._lock:
            code = room_code.strip().upper()
            room = self._rooms.get(code)
            if room is None:
                raise ValueError(f"Room {code} does not exist.")
            if room.status == "closed":
                raise ValueError(f"Room {code} is closed.")
            if len(room.players) >= 2:
                raise ValueError(f"Room {code} is already full.")
            session = self._add_session_to_room(room, player_name)
            if len(room.players) == 2 and room.game_state is None:
                room.game_state = create_random_game()
                room.status = "active"
                room.message = "Both players have joined. The match is live."
                room.updated_at = time()
            else:
                room.message = "Waiting for a second player to join."
            return self._serialize_room_join(session, room)

    def get_state(self, token: str) -> dict:
        """Return the current room and game view for one browser session."""
        with self._lock:
            session = self._require_session(token)
            room = self._require_room(session.room_code)
            return self._serialize_room_state(session, room)

    def leave(self, token: str) -> dict:
        """Remove a browser session from its room."""
        with self._lock:
            session = self._sessions.pop(token, None)
            if session is None:
                return {"ok": True}
            room = self._rooms.get(session.room_code)
            if room is None:
                return {"ok": True}
            room.players.pop(session.player_id, None)
            room.updated_at = time()
            if not room.players:
                self._rooms.pop(room.room_code, None)
            elif room.status == "active":
                room.status = "closed"
                room.message = "Your opponent left the room."
                room.latest_notice = room.message
            else:
                room.message = "Waiting for a second player to join."
            return {"ok": True}

    def apply_action(self, token: str, action_payload: dict) -> dict:
        """Apply one browser-submitted action to the authoritative game state."""
        with self._lock:
            session = self._require_session(token)
            room = self._require_room(session.room_code)
            if room.status != "active" or room.game_state is None:
                raise ValueError("The room is not in an active game yet.")

            action = self._build_action(room.game_state, session, action_payload)
            applied = room.game_state.apply_action(action)
            if not applied:
                raise ValueError("That action is not legal right now.")

            for _ in range(6):
                if not room.game_state.advance_forced_traversing():
                    break
            room.game_state.check_game_over()
            room.latest_notice = room.game_state.consume_appeasing_return_notice()
            room.updated_at = time()
            return self._serialize_room_state(session, room)

    def _new_room_code(self) -> str:
        """Return an unused room code."""
        code = generate_room_code()
        while code in self._rooms:
            code = generate_room_code()
        return code

    def _require_session(self, token: str) -> BrowserSession:
        """Return a session or raise a user-facing error."""
        session = self._sessions.get(token)
        if session is None:
            raise ValueError("That browser session is no longer active.")
        return session

    def _require_room(self, room_code: str) -> BrowserRoom:
        """Return a room or raise a user-facing error."""
        room = self._rooms.get(room_code)
        if room is None:
            raise ValueError("That room no longer exists.")
        return room

    def _add_session_to_room(self, room: BrowserRoom, player_name: str) -> BrowserSession:
        """Create and store one new browser session in a room."""
        available = [player_id for player_id in (0, 1) if player_id not in room.players]
        if not available:
            raise ValueError(f"Room {room.room_code} is already full.")
        session = BrowserSession(
            token=uuid4().hex,
            room_code=room.room_code,
            player_id=available[0],
            player_name=(player_name or "Player").strip() or "Player",
        )
        room.players[session.player_id] = session
        room.updated_at = time()
        self._sessions[session.token] = session
        return session

    def _serialize_room_join(self, session: BrowserSession, room: BrowserRoom) -> dict:
        """Return the initial response after creating or joining a room."""
        payload = {
            "ok": True,
            "token": session.token,
            "room": {
                "room_code": room.room_code,
                "status": room.status,
                "message": room.message,
                "players": self._serialize_room_players(room),
            },
            "player": {
                "player_id": session.player_id,
                "player_name": session.player_name,
            },
        }
        if room.status == "active" and room.game_state is not None:
            payload["game"] = self._serialize_game_view(room, session.player_id)
        return payload

    def _serialize_room_state(self, session: BrowserSession, room: BrowserRoom) -> dict:
        """Return the latest state payload for one browser session."""
        payload = {
            "ok": True,
            "token": session.token,
            "room": {
                "room_code": room.room_code,
                "status": room.status,
                "message": room.message,
                "players": self._serialize_room_players(room),
            },
            "player": {
                "player_id": session.player_id,
                "player_name": session.player_name,
            },
            "notice": room.latest_notice,
        }
        if room.status == "active" and room.game_state is not None:
            payload["game"] = self._serialize_game_view(room, session.player_id)
        return payload

    @staticmethod
    def _serialize_room_players(room: BrowserRoom) -> list[dict]:
        """Return room player info ordered by player number."""
        return [
            {
                "player_id": player_id,
                "player_name": room.players[player_id].player_name,
            }
            for player_id in sorted(room.players)
        ]

    def _serialize_game_view(self, room: BrowserRoom, player_id: int) -> dict:
        """Return a browser-safe game-state view for one player."""
        game = room.game_state
        opponent_id = 1 - player_id
        player_positions = {
            pid: game.board.get_player_position(pid)
            for pid in [0, 1]
        }
        ballista_targets = {
            (pos.row, pos.col)
            for pos in game.get_pending_ballista_targets()
        } if game.pending_ballista_player == player_id else set()
        placement_targets = {
            (pos.row, pos.col)
            for pos in game.get_hole_positions()
        } if game.pending_placement_player == player_id else set()

        board_rows = []
        for row in range(6):
            row_cells = []
            for col in range(6):
                pos = Position(row, col)
                card = game.board.get_card(pos)
                role = game.suit_roles.get(card.suit).value if card is not None and card.suit in game.suit_roles else None
                occupants = [
                    pid
                    for pid, player_pos in player_positions.items()
                    if player_pos == pos
                ]
                target_type = None
                if (row, col) in ballista_targets:
                    target_type = "ballista"
                elif (row, col) in placement_targets:
                    target_type = "placement"
                row_cells.append(
                    {
                        "row": row,
                        "col": col,
                        "card": self._serialize_card(card) if card is not None else None,
                        "role": role,
                        "is_hole": card is None,
                        "occupants": occupants,
                        "target_type": target_type,
                    }
                )
            board_rows.append(row_cells)

        return {
            "phase": game.phase.value,
            "winner": game.winner,
            "current_player": game.current_player,
            "movement_turn": game.movement_turn,
            "status_text": self._build_status_text(game, player_id),
            "players": [
                self._serialize_player_view(room, game, pid, pid == player_id)
                for pid in [0, 1]
            ],
            "board": board_rows,
            "suit_roles": [
                {
                    "suit": suit.value,
                    "family_name": get_family_name(suit),
                    "role": role.value,
                }
                for suit, role in game.suit_roles.items()
            ],
            "logs": {
                "appeasing": list(game.appeasing_history[-4:]),
                "requests": list(game.request_history[-4:]),
                "events": list(game.major_events[-8:]),
            },
            "controls": self._build_controls(game, player_id),
        }

    def _serialize_player_view(self, room: BrowserRoom, game, player_id: int, is_local: bool) -> dict:
        """Return per-player public info plus private local hand details."""
        hand = game.get_player_hand(player_id)
        damage_cards = list(game.damage[player_id].cards)
        position = game.board.get_player_position(player_id)
        return {
            "player_id": player_id,
            "player_name": room.players.get(player_id, SimpleNamespace(player_name=f"Player {player_id + 1}")).player_name,
            "position": self._serialize_position(position),
            "damage_total": game.get_damage_total(player_id),
            "damage_cards": [
                {
                    "index": index,
                    "card": self._serialize_card(card),
                }
                for index, card in enumerate(damage_cards)
            ],
            "hand_count": len(hand),
            "hand": [
                {
                    "index": index,
                    "card": self._serialize_card(card),
                    "role": game.suit_roles.get(card.suit).value if card.suit in game.suit_roles else None,
                }
                for index, card in enumerate(hand)
            ] if is_local else [],
        }

    def _build_controls(self, game, player_id: int) -> dict:
        """Return browser UI controls that are currently legal for the local player."""
        opponent_id = 1 - player_id
        current_turn = game.current_player == player_id
        pending_request_type = game.get_pending_request_type()
        hand = game.get_player_hand(player_id)
        hand_cards = []
        can_play_appeasing = (
            current_turn
            and game.phase == GamePhase.APPEASING
            and game.current_request_winner is None
            and not game.has_pending_request_resolution()
            and not game.has_pending_card_placement()
        )
        can_choose_weapon = current_turn and game.has_pending_combat()
        for index, card in enumerate(hand):
            hand_cards.append(
                {
                    "index": index,
                    "card": self._serialize_card(card),
                    "role": game.suit_roles.get(card.suit).value if card.suit in game.suit_roles else None,
                    "can_play": can_play_appeasing,
                    "can_use_weapon": can_choose_weapon and game.can_use_weapon(player_id, card),
                }
            )

        controls = {
            "can_act": current_turn and game.phase != GamePhase.GAME_OVER,
            "movement": [],
            "can_pick_up_current": False,
            "hand_cards": hand_cards,
            "request_types": [],
            "restructure_suits": [],
            "steal_life": None,
            "plane_shift": None,
            "ballista_targets": [],
            "placement": None,
        }

        if game.phase == GamePhase.TRAVERSING and current_turn and not game.has_pending_ballista() and not game.has_pending_combat():
            controls["movement"] = list(game.get_legal_moves(player_id))
            controls["can_pick_up_current"] = game.can_pick_up_current_card(player_id)

        if game.can_choose_request(player_id):
            controls["request_types"] = list(game.get_available_request_types(player_id))

        if pending_request_type == "restructure" and game.pending_request_resolution["player"] == player_id:
            selected = set(game.get_pending_restructure_suits())
            controls["restructure_suits"] = [
                {
                    "suit": suit.value,
                    "family_name": get_family_name(suit),
                    "role": role.value,
                    "selected": suit in selected,
                }
                for suit, role in game.suit_roles.items()
            ]

        if pending_request_type == "steal_life" and game.pending_request_resolution["player"] == player_id:
            selected_own = game.get_pending_steal_life_card()
            own_index = None
            if selected_own is not None:
                for index, card in enumerate(game.damage[player_id].cards):
                    if card == selected_own:
                        own_index = index
                        break
            controls["steal_life"] = {
                "selected_own_index": own_index,
                "own_cards": [
                    {"index": index, "card": self._serialize_card(card)}
                    for index, card in enumerate(game.damage[player_id].cards)
                ],
                "enemy_cards": [
                    {"index": index, "card": self._serialize_card(card)}
                    for index, card in enumerate(game.damage[opponent_id].cards)
                ],
            }

        if pending_request_type == "plane_shift" and game.pending_request_resolution["player"] == player_id:
            direction = game.get_pending_plane_shift_direction()
            axis = None
            if direction in {"left", "right"}:
                axis = "row"
            elif direction in {"up", "down"}:
                axis = "column"
            controls["plane_shift"] = {
                "direction": direction,
                "directions": ["up", "down", "left", "right"] if direction is None else [],
                "axis": axis,
                "indices": list(range(6)) if direction is not None else [],
            }

        if game.pending_ballista_player == player_id:
            controls["ballista_targets"] = [
                self._serialize_position(pos)
                for pos in game.get_pending_ballista_targets()
            ]

        if game.pending_placement_player == player_id:
            controls["placement"] = {
                "cards": [
                    {
                        "index": index,
                        "card": self._serialize_card(card),
                    }
                    for index, card in enumerate(game.get_pending_placement_cards())
                ],
                "holes": [
                    self._serialize_position(pos)
                    for pos in game.get_hole_positions()
                ],
            }

        return controls

    def _build_status_text(self, game, player_id: int) -> str:
        """Return the browser status banner text for the local player."""
        if game.phase == GamePhase.GAME_OVER and game.winner is not None:
            if game.winner == player_id:
                return "You won the match."
            return "You lost the match."

        if game.pending_ballista_player is not None:
            if game.pending_ballista_player == player_id:
                return "Choose a Ballista destination."
            return "Waiting for the opponent's Ballista destination."

        if game.has_pending_combat():
            if game.current_player == player_id:
                return "Choose a weapon card for combat."
            return "Waiting for the opponent's combat choice."

        if game.pending_placement_player is not None:
            if game.pending_placement_player == player_id:
                return "Place the played Appeasing card into a hole."
            return "Waiting for the opponent to place the played cards."

        pending_request_type = game.get_pending_request_type()
        if pending_request_type == "restructure":
            if game.pending_request_resolution["player"] == player_id:
                return "Choose two color families to swap."
            return "Waiting for the opponent to finish Restructure."
        if pending_request_type == "steal_life":
            if game.pending_request_resolution["player"] == player_id:
                return "Choose your damage card, then an opponent damage card."
            return "Waiting for the opponent to finish Steal Life."
        if pending_request_type == "plane_shift":
            if game.pending_request_resolution["player"] == player_id:
                if game.get_pending_plane_shift_direction() is None:
                    return "Choose a Plane Shift direction."
                return "Choose the row or column to shift."
            return "Waiting for the opponent to finish Plane Shift."

        if game.can_choose_request(player_id):
            return "Choose Pan's Request."
        if game.current_request_winner is not None:
            return "Waiting for the opponent's request choice."

        if game.phase == GamePhase.APPEASING:
            if game.current_player == player_id:
                return "Play a hand card for Appeasing Pan."
            return "Waiting for the opponent's Appeasing Pan card."

        if game.phase == GamePhase.TRAVERSING:
            if game.current_player == player_id:
                return "Your turn: move or use the current tile."
            return "Waiting for the opponent's move."

        return "Game in progress."

    def _build_action(self, game, session: BrowserSession, payload: dict):
        """Convert a browser action payload into an engine action object."""
        action_type = str(payload.get("type", "")).strip()
        player_id = session.player_id

        if action_type == "move":
            return MoveAction(player_id, str(payload["direction"]))
        if action_type == "pickup_current":
            return PickupCurrentCardAction(player_id)
        if action_type == "play_card":
            return PlayCardAction(player_id, self._card_from_index(game.get_player_hand(player_id), payload["card_index"]))
        if action_type == "choose_combat_card":
            return ChooseCombatCardAction(player_id, self._card_from_index(game.get_player_hand(player_id), payload["card_index"]))
        if action_type == "choose_request":
            request_type = str(payload["request_type"])
            if request_type not in REQUEST_TYPE_MAP:
                raise ValueError("Unknown request type.")
            return ChooseRequestAction(player_id, REQUEST_TYPE_MAP[request_type])
        if action_type == "select_damage_card":
            pile_owner = int(payload["pile_owner"])
            if pile_owner not in [0, 1]:
                raise ValueError("Damage pile owner must be 0 or 1.")
            card = self._card_from_index(game.damage[pile_owner].cards, payload["card_index"])
            return SelectDamageCardAction(player_id, pile_owner, card)
        if action_type == "select_restructure_suit":
            return SelectRestructureSuitAction(player_id, CardSuit(str(payload["suit"])))
        if action_type == "select_plane_shift_direction":
            return SelectPlaneShiftDirectionAction(player_id, str(payload["direction"]))
        if action_type == "resolve_plane_shift":
            return ResolvePlaneShiftAction(player_id, int(payload["index"]))
        if action_type == "resolve_ballista_shot":
            return ResolveBallistaShotAction(player_id, int(payload["row"]), int(payload["col"]))
        if action_type == "place_card":
            row = int(payload["row"])
            col = int(payload["col"])
            card_index = int(payload["card_index"])
            return PlaceCardsAction(player_id, [Position(row, col)], [card_index])
        raise ValueError("Unknown action type.")

    @staticmethod
    def _card_from_index(cards: list, raw_index) -> object:
        """Return a card object from a browser-supplied list index."""
        index = int(raw_index)
        if index < 0 or index >= len(cards):
            raise ValueError("That card is no longer available.")
        return cards[index]

    @staticmethod
    def _serialize_card(card) -> dict:
        """Return a browser-friendly card payload."""
        return {
            "rank": card.rank.value,
            "rank_name": get_rank_name(card.rank),
            "suit": card.suit.value,
            "family_name": get_family_name(card.suit),
            "label": str(card),
            "combat_value": card.combat_value(),
        }

    @staticmethod
    def _serialize_position(pos: Position | None) -> dict | None:
        """Return a browser-friendly position payload."""
        if pos is None:
            return None
        return {
            "row": pos.row,
            "col": pos.col,
            "label": f"R{pos.row + 1} C{pos.col + 1}",
        }


class PanTrialWebHandler(BaseHTTPRequestHandler):
    """HTTP handler for the browser client and JSON API."""

    server_version = "PanTrialBrowser/0.1"

    @property
    def service(self) -> BrowserGameService:
        return self.server.state.service

    def do_GET(self) -> None:
        """Handle GET requests for static files and state polling."""
        parsed = urlparse(self.path)
        if parsed.path == "/":
            self._serve_file(WEB_ROOT / "index.html")
            return
        if parsed.path.startswith("/static/"):
            relative = parsed.path.removeprefix("/static/")
            self._serve_file(WEB_ROOT / relative)
            return
        if parsed.path == "/api/state":
            params = parse_qs(parsed.query)
            token = self._token_from_request(params.get("token", [""])[0])
            if not token:
                self._send_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": "Missing browser session token."})
                return
            try:
                payload = self.service.get_state(token)
            except ValueError as exc:
                self._send_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": str(exc)})
                return
            self._send_json(HTTPStatus.OK, payload)
            return
        self._send_json(HTTPStatus.NOT_FOUND, {"ok": False, "error": "Not found."})

    def do_POST(self) -> None:
        """Handle room and action POST requests."""
        parsed = urlparse(self.path)
        body = self._read_json_body()
        if parsed.path == "/api/create-room":
            try:
                payload = self.service.create_room(
                    player_name=str(body.get("player_name", "")).strip() or "Player",
                    requested_code=str(body.get("room_code", "")).strip() or None,
                )
            except ValueError as exc:
                self._send_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": str(exc)})
                return
            self._send_json(HTTPStatus.OK, payload)
            return
        if parsed.path == "/api/join-room":
            try:
                payload = self.service.join_room(
                    room_code=str(body.get("room_code", "")).strip(),
                    player_name=str(body.get("player_name", "")).strip() or "Player",
                )
            except ValueError as exc:
                self._send_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": str(exc)})
                return
            self._send_json(HTTPStatus.OK, payload)
            return
        if parsed.path == "/api/action":
            token = self._token_from_request(body.get("token", ""))
            if not token:
                self._send_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": "Missing browser session token."})
                return
            try:
                payload = self.service.apply_action(token, body.get("action", {}))
            except ValueError as exc:
                self._send_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": str(exc)})
                return
            self._send_json(HTTPStatus.OK, payload)
            return
        if parsed.path == "/api/leave":
            token = self._token_from_request(body.get("token", ""))
            self._send_json(HTTPStatus.OK, self.service.leave(token))
            return
        self._send_json(HTTPStatus.NOT_FOUND, {"ok": False, "error": "Not found."})

    def log_message(self, format: str, *args) -> None:
        """Silence default HTTP request logging."""
        return

    def _serve_file(self, path: Path) -> None:
        """Serve one static file from the browser client directory."""
        if not path.exists() or not path.is_file():
            self._send_json(HTTPStatus.NOT_FOUND, {"ok": False, "error": "File not found."})
            return
        content = path.read_bytes()
        mime_type, _ = mimetypes.guess_type(path.name)
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", mime_type or "application/octet-stream")
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(content)

    def _send_json(self, status: HTTPStatus, payload: dict) -> None:
        """Send one JSON response."""
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _read_json_body(self) -> dict:
        """Read a JSON request body into a dict."""
        length = int(self.headers.get("Content-Length", "0") or 0)
        if length <= 0:
            return {}
        raw = self.rfile.read(length)
        if not raw:
            return {}
        return json.loads(raw.decode("utf-8"))

    def _token_from_request(self, raw_token) -> str:
        """Return the token from JSON or header, normalized to a string."""
        token = str(raw_token or "").strip()
        if token:
            return token
        return str(self.headers.get(TOKEN_HEADER, "")).strip()


def build_server(host: str = HOST, port: int = PORT) -> ThreadingHTTPServer:
    """Create the browser localhost server without starting it."""
    service = BrowserGameService()
    server = ThreadingHTTPServer((host, port), PanTrialWebHandler)
    server.state = SimpleNamespace(service=service)
    return server


def main() -> None:
    """Run the browser localhost server."""
    server = build_server()
    print(f"Pan's Trial browser server running at http://{HOST}:{PORT}")
    print("Open that URL in two browser tabs or windows, then join the same room.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down browser server.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
