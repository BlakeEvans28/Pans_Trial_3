"""Localhost room server and client for Pan's Trial quick matches."""

from __future__ import annotations

from dataclasses import dataclass, field
import json
from random import shuffle
import socket
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Lock, Thread, current_thread
from typing import Any
from urllib import error as urlerror
from urllib import request
from urllib.parse import urlparse

from deck_utils import create_6x6_labyrinth, draft_hands, get_jack_suit_order, setup_game_deck
from engine import Action, GameState, Position
from .serialization import decode_action, decode_game_state, encode_action, encode_game_state


DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765


def create_quick_match_game() -> GameState:
    """Create a direct-to-labyrinth two-player game for localhost rooms."""
    from engine import GamePhase

    labyrinth_cards, player0_deck, player1_deck, jack_cards = setup_game_deck()
    player0_hand, player1_hand, starting_player = draft_hands(player0_deck, player1_deck)
    jack_order = get_jack_suit_order(jack_cards)

    game = GameState()
    game.setup_suit_roles(jack_order)

    for _ in range(100):
        grid = create_6x6_labyrinth(labyrinth_cards)
        game.setup_board(grid)
        game.place_player(0, Position(5, 3))
        game.place_player(1, Position(0, 2))
        if game.get_legal_moves(0) and game.get_legal_moves(1):
            break
        shuffle(labyrinth_cards)

    for card in player0_hand:
        game.add_card_to_hand(0, card)
    for card in player1_hand:
        game.add_card_to_hand(1, card)

    game.current_player = starting_player
    game.traversing_resume_player = starting_player
    game.phase = GamePhase.TRAVERSING
    return game


@dataclass
class Room:
    code: str
    game: GameState
    players: dict[int, str] = field(default_factory=dict)
    revision: int = 0
    message: str = "Waiting for another player."

    @property
    def ready(self) -> bool:
        return 0 in self.players and 1 in self.players

    def snapshot(self, player_id: int | None = None) -> dict[str, Any]:
        return {
            "room_code": self.code,
            "player_id": player_id,
            "players": {str(key): value for key, value in sorted(self.players.items())},
            "ready": self.ready,
            "revision": self.revision,
            "message": "Both players connected." if self.ready else self.message,
            "state": encode_game_state(self.game),
        }


class RoomStore:
    """Thread-safe in-memory room storage for one local server process."""

    def __init__(self) -> None:
        self._rooms: dict[str, Room] = {}
        self._lock = Lock()
        self._next_code = 1000

    def create_room(self, player_name: str) -> tuple[Room, int]:
        with self._lock:
            while True:
                code = str(self._next_code)
                self._next_code += 1
                if code not in self._rooms:
                    break
            room = Room(code=code, game=create_quick_match_game())
            room.players[0] = player_name or "Player 1"
            self._rooms[code] = room
            return room, 0

    def join_room(self, code: str, player_name: str) -> tuple[Room, int]:
        with self._lock:
            room = self._get_room_locked(code)
            open_seats = [player_id for player_id in (0, 1) if player_id not in room.players]
            if not open_seats:
                raise ValueError("Room already has two players")
            player_id = open_seats[0]
            room.players[player_id] = player_name or f"Player {player_id + 1}"
            room.message = "Both players connected." if room.ready else "Waiting for another player."
            room.revision += 1
            return room, player_id

    def get_room(self, code: str) -> Room:
        with self._lock:
            room = self._get_room_locked(code)
            self._advance_automation_locked(room)
            return room

    def submit_action(
        self,
        code: str,
        player_id: int,
        action: Action,
        expected_revision: int | None = None,
    ) -> Room:
        with self._lock:
            room = self._get_room_locked(code)
            if not room.ready:
                raise ValueError("Room is waiting for another player")
            if player_id not in room.players:
                raise ValueError("Player is not in this room")
            if expected_revision is not None and expected_revision != room.revision:
                raise ValueError("Room state changed; refresh and try again")
            if action.player_id != player_id:
                raise ValueError("Submitted action does not belong to this player")
            if room.game.current_player != player_id:
                raise ValueError("It is not this player's turn")

            if not room.game.apply_action(action):
                raise ValueError("Action was rejected by the game rules")

            room.revision += 1
            self._advance_automation_locked(room)
            if self._check_game_over_once(room):
                room.revision += 1
            return room

    def leave_room(self, code: str, player_id: int) -> Room | None:
        with self._lock:
            room = self._get_room_locked(code)
            if player_id in room.players:
                departed_name = room.players.pop(player_id)
                room.message = f"{departed_name} left the room."
                room.revision += 1
            if not room.players:
                del self._rooms[code]
                return None
            return room

    def _advance_automation_locked(self, room: Room) -> None:
        advanced = False
        for _ in range(8):
            if not room.game.advance_forced_traversing():
                break
            advanced = True
        if self._check_game_over_once(room):
            advanced = True
        if advanced:
            room.revision += 1

    def _check_game_over_once(self, room: Room) -> bool:
        if room.game.winner is not None:
            return False
        return room.game.check_game_over()

    def _get_room_locked(self, code: str) -> Room:
        try:
            return self._rooms[code]
        except KeyError as exc:
            raise ValueError("Room was not found") from exc


def _json_response(handler: BaseHTTPRequestHandler, status: int, payload: dict[str, Any]) -> None:
    data = json.dumps(payload).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json")
    handler.send_header("Content-Length", str(len(data)))
    handler.send_header("Access-Control-Allow-Origin", "*")
    handler.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
    handler.send_header("Access-Control-Allow-Headers", "Content-Type")
    handler.send_header("Access-Control-Allow-Private-Network", "true")
    handler.end_headers()
    handler.wfile.write(data)


def _read_json(handler: BaseHTTPRequestHandler) -> dict[str, Any]:
    length = int(handler.headers.get("Content-Length", "0") or 0)
    if length <= 0:
        return {}
    return json.loads(handler.rfile.read(length).decode("utf-8"))


def make_room_handler(store: RoomStore):
    """Build a request handler bound to a specific room store."""

    class LocalRoomHandler(BaseHTTPRequestHandler):
        def do_OPTIONS(self) -> None:
            _json_response(self, 204, {})

        def do_GET(self) -> None:
            try:
                parts = self._path_parts()
                if len(parts) == 2 and parts[0] == "rooms":
                    room = store.get_room(parts[1])
                    _json_response(self, 200, room.snapshot())
                    return
                _json_response(self, 404, {"error": "Unknown endpoint"})
            except ValueError as exc:
                _json_response(self, 400, {"error": str(exc)})

        def do_POST(self) -> None:
            try:
                parts = self._path_parts()
                body = _read_json(self)
                if parts == ["rooms"]:
                    room, player_id = store.create_room(str(body.get("name") or "").strip())
                    _json_response(self, 200, room.snapshot(player_id))
                    return

                if len(parts) == 3 and parts[0] == "rooms" and parts[2] == "join":
                    room, player_id = store.join_room(parts[1], str(body.get("name") or "").strip())
                    _json_response(self, 200, room.snapshot(player_id))
                    return

                if len(parts) == 3 and parts[0] == "rooms" and parts[2] == "actions":
                    player_id = int(body.get("player_id"))
                    action = decode_action(body["action"])
                    revision = body.get("revision")
                    expected_revision = int(revision) if revision is not None else None
                    room = store.submit_action(parts[1], player_id, action, expected_revision)
                    _json_response(self, 200, room.snapshot(player_id))
                    return

                if len(parts) == 3 and parts[0] == "rooms" and parts[2] == "leave":
                    player_id = int(body.get("player_id"))
                    room = store.leave_room(parts[1], player_id)
                    if room is None:
                        _json_response(self, 200, {"left": True, "room_closed": True})
                    else:
                        _json_response(self, 200, room.snapshot())
                    return

                _json_response(self, 404, {"error": "Unknown endpoint"})
            except (KeyError, TypeError, ValueError) as exc:
                _json_response(self, 400, {"error": str(exc)})

        def log_message(self, format: str, *args) -> None:
            return

        def _path_parts(self) -> list[str]:
            return [part for part in urlparse(self.path).path.split("/") if part]

    return LocalRoomHandler


class LocalRoomServer:
    """Background localhost server used by the Create Room flow."""

    def __init__(self, host: str = DEFAULT_HOST, port: int = DEFAULT_PORT) -> None:
        self.host = host
        self.port = port
        self.store = RoomStore()
        self.httpd: ThreadingHTTPServer | None = None
        self.thread: Thread | None = None

    @property
    def base_url(self) -> str:
        return f"http://{self.host}:{self.port}"

    def start(self) -> None:
        if self.httpd is not None:
            return

        handler = make_room_handler(self.store)
        port = self.port
        last_error = None
        for candidate in range(port, port + 20):
            try:
                self.httpd = ThreadingHTTPServer((self.host, candidate), handler)
                self.port = candidate
                break
            except OSError as exc:
                last_error = exc
        if self.httpd is None:
            raise OSError(f"Unable to start local room server: {last_error}")

        self.thread = Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()

    def stop(self) -> None:
        if self.httpd is None:
            return
        self.httpd.shutdown()
        self.httpd.server_close()
        self.httpd = None
        if self.thread is not None and self.thread is not current_thread():
            self.thread.join(timeout=1.0)
        self.thread = None


class LocalRoomClient:
    """Polling client for the local room server."""

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
    def create(cls, player_name: str, base_url: str) -> "LocalRoomClient":
        response = _post_json(f"{base_url.rstrip('/')}/rooms", {"name": player_name})
        client = cls(base_url, response["room_code"], int(response["player_id"]), player_name)
        client._apply_snapshot(response)
        return client

    @classmethod
    def join(cls, player_name: str, base_url: str, room_code: str) -> "LocalRoomClient":
        response = _post_json(f"{base_url.rstrip('/')}/rooms/{room_code}/join", {"name": player_name})
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
            snapshot = _get_json(f"{self.base_url}/rooms/{self.room_code}")
            return self._apply_snapshot(snapshot)
        except OSError as exc:
            self.last_error = str(exc)
            return False

    def submit_action(self, action: Action) -> bool:
        try:
            snapshot = _post_json(
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
            _post_json(
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


def _post_json(url: str, payload: dict[str, Any]) -> dict[str, Any]:
    data = json.dumps(payload).encode("utf-8")
    req = request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
    return _request_json(req)


def _get_json(url: str) -> dict[str, Any]:
    return _request_json(request.Request(url, method="GET"))


def _request_json(req: request.Request) -> dict[str, Any]:
    try:
        with request.urlopen(req, timeout=0.75) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urlerror.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        try:
            message = json.loads(detail).get("error", detail)
        except json.JSONDecodeError:
            message = detail
        raise OSError(message) from exc
    except (socket.timeout, urlerror.URLError) as exc:
        raise OSError(str(exc)) from exc

    if isinstance(payload, dict) and "error" in payload:
        raise OSError(str(payload["error"]))
    return payload
