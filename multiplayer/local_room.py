"""Localhost room server and client for Pan's Trial quick matches."""

from __future__ import annotations

from dataclasses import dataclass, field
import html
import json
import mimetypes
from pathlib import Path, PurePosixPath
from random import choice
import socket
import ssl
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Lock, Thread, current_thread
from typing import Any
from urllib import error as urlerror
from urllib import request
from urllib.parse import unquote, urlparse

from deck_utils import get_jack_suit_order, setup_pregame_cards
from engine import Action, ActionType, Card, CardRank, GameState
from .game_setup import create_game_from_pregame, create_quick_match_game
from .serialization import (
    decode_action,
    decode_game_state,
    decode_room_payload,
    encode_action,
    encode_game_state,
    encode_room_payload,
)


DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765
DEFAULT_MAX_ROOMS = 200
DEFAULT_ROOM_TIMEOUT_SECONDS = 60 * 60 * 6


def _get_unique_player_name(player_name: str, player_id: int, existing_names) -> str:
    """Return a non-empty room display name, suffixing duplicate picked names."""
    name = " ".join(str(player_name or "").split()).strip() or f"Player {player_id + 1}"
    existing = {str(existing or "").strip().casefold() for existing in existing_names if str(existing or "").strip()}
    if name.casefold() not in existing:
        return name

    suffix = 1
    candidate = f"{name}{suffix}"
    while candidate.casefold() in existing:
        suffix += 1
        candidate = f"{name}{suffix}"
    return candidate


@dataclass
class Room:
    code: str
    game: GameState | None = None
    players: dict[int, str] = field(default_factory=dict)
    ready_players: set[int] = field(default_factory=set)
    stage: str = "lobby"
    revision: int = 0
    message: str = "Waiting for another player."
    labyrinth_cards: list[Card] = field(default_factory=list)
    draft_cards: list[Card] = field(default_factory=list)
    available_cards: list[Card | None] = field(default_factory=list)
    jack_cards: list[Card] = field(default_factory=list)
    jack_order: list = field(default_factory=list)
    draft_starting_player: int = 0
    current_drafter: int = 0
    draft_hands: dict[int, list[Card]] = field(default_factory=lambda: {0: [], 1: []})
    kings_drafted: int = 0
    player_cards: list[Card] = field(default_factory=list)
    rematch_votes: set[int] = field(default_factory=set)
    rematch_declined: bool = False
    rematch_declined_by: int | None = None
    rematch_declined_name: str = ""
    last_touched: float = field(default_factory=time.monotonic)

    @property
    def ready(self) -> bool:
        return 0 in self.players and 1 in self.players

    @property
    def all_players_ready(self) -> bool:
        return self.ready and 0 in self.ready_players and 1 in self.ready_players

    def snapshot(self, player_id: int | None = None) -> dict[str, Any]:
        payload = {
            "room_code": self.code,
            "player_id": player_id,
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


class RoomStore:
    """Thread-safe in-memory room storage for one local server process."""

    def __init__(
        self,
        *,
        max_rooms: int = DEFAULT_MAX_ROOMS,
        room_timeout_seconds: int = DEFAULT_ROOM_TIMEOUT_SECONDS,
    ) -> None:
        self._rooms: dict[str, Room] = {}
        self._lock = Lock()
        self._next_code = 1000
        self.max_rooms = max(1, int(max_rooms))
        self.room_timeout_seconds = max(60, int(room_timeout_seconds))

    def create_room(self, player_name: str) -> tuple[Room, int]:
        with self._lock:
            self._cleanup_inactive_rooms_locked()
            if len(self._rooms) >= self.max_rooms:
                raise ValueError("Room server is full; try again later")
            while True:
                code = str(self._next_code)
                self._next_code += 1
                if code not in self._rooms:
                    break
            labyrinth_cards, draft_cards, jack_cards = setup_pregame_cards()
            draft_starting_player = choice([0, 1])
            room = Room(
                code=code,
                labyrinth_cards=labyrinth_cards,
                draft_cards=list(draft_cards),
                available_cards=list(draft_cards),
                jack_cards=jack_cards,
                jack_order=get_jack_suit_order(jack_cards),
                draft_starting_player=draft_starting_player,
                current_drafter=draft_starting_player,
            )
            room.players[0] = _get_unique_player_name(player_name, 0, [])
            room.message = "Waiting for another player."
            self._rooms[code] = room
            return room, 0

    def join_room(self, code: str, player_name: str) -> tuple[Room, int]:
        with self._lock:
            self._cleanup_inactive_rooms_locked()
            room = self._get_room_locked(code)
            self._touch_room_locked(room)
            if room.stage != "lobby":
                raise ValueError("Room has already started")
            open_seats = [player_id for player_id in (0, 1) if player_id not in room.players]
            if not open_seats:
                raise ValueError("Room already has two players")
            player_id = open_seats[0]
            room.players[player_id] = _get_unique_player_name(player_name, player_id, room.players.values())
            room.message = "Both players connected. Press Ready when you are both looking at this screen."
            room.revision += 1
            return room, player_id

    def get_room(self, code: str) -> Room:
        with self._lock:
            self._cleanup_inactive_rooms_locked()
            room = self._get_room_locked(code)
            self._touch_room_locked(room)
            self._advance_automation_locked(room)
            return room

    def toggle_player_ready(self, code: str, player_id: int) -> Room:
        with self._lock:
            room = self._get_room_locked(code)
            self._touch_room_locked(room)
            if player_id not in room.players:
                raise ValueError("Player is not in this room")
            if not room.ready:
                raise ValueError("Room is waiting for another player")
            if room.stage != "lobby":
                return room

            if player_id in room.ready_players:
                room.ready_players.remove(player_id)
                room.message = f"{room.players[player_id]} is no longer ready."
                room.revision += 1
                return room

            room.ready_players.add(player_id)
            if room.all_players_ready:
                room.stage = "coin_flip"
                room.message = "Both players are ready. Starting the coin flip."
            else:
                room.message = f"{room.players[player_id]} is ready. Waiting for the other player."
            room.revision += 1
            return room

    def set_player_ready(self, code: str, player_id: int) -> Room:
        """Backward-compatible name for the lobby ready/unready toggle."""
        return self.toggle_player_ready(code, player_id)

    def submit_draft_pick(
        self,
        code: str,
        player_id: int,
        card_index: int,
        expected_revision: int | None = None,
    ) -> Room:
        with self._lock:
            room = self._get_room_locked(code)
            self._touch_room_locked(room)
            if not room.all_players_ready:
                raise ValueError("Both players must be ready before the draft")
            if room.stage not in {"coin_flip", "draft"}:
                raise ValueError("The draft is not active")
            if player_id != room.current_drafter:
                raise ValueError("It is not this player's draft pick")
            if expected_revision is not None and expected_revision != room.revision:
                raise ValueError("Room state changed; refresh and try again")
            if card_index < 0 or card_index >= len(room.available_cards):
                raise ValueError("Draft card is out of range")

            card = room.available_cards[card_index]
            if card is None:
                raise ValueError("Draft card was already taken")
            if not self._can_draft_card_locked(room, card):
                raise ValueError("Only two Heroes may be drafted")

            room.stage = "draft"
            room.draft_hands[player_id].append(card)
            if card.rank == CardRank.KING:
                room.kings_drafted += 1
            room.available_cards[card_index] = None

            total_picks = len(room.draft_hands[0]) + len(room.draft_hands[1])
            if total_picks >= 10:
                room.player_cards = [card for card in room.available_cards if card is not None]
                room.game = create_game_from_pregame(
                    room.labyrinth_cards,
                    room.draft_hands[0],
                    room.draft_hands[1],
                    room.jack_order,
                    starting_player=1,
                )
                room.stage = "game"
                room.message = "Draft complete. Revealing the omens."
            else:
                room.current_drafter = 1 - room.current_drafter
                next_name = room.players.get(room.current_drafter, f"Player {room.current_drafter + 1}")
                room.message = f"Waiting for {next_name} to draft."

            room.revision += 1
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
            self._touch_room_locked(room)
            if room.stage != "game" or room.game is None:
                raise ValueError("Game has not started yet")
            if player_id not in room.players:
                raise ValueError("Player is not in this room")
            if action.player_id != player_id:
                raise ValueError("Submitted action does not belong to this player")
            simultaneous_appeasing_card = (
                getattr(action, "type", None) == ActionType.PLAY_CARD
                and room.game.can_submit_appeasing_card(player_id, getattr(action, "card", None))
            )
            if (
                expected_revision is not None
                and expected_revision != room.revision
                and not simultaneous_appeasing_card
            ):
                raise ValueError("Room state changed; refresh and try again")
            if room.game.current_player != player_id and not simultaneous_appeasing_card:
                raise ValueError("It is not this player's turn")

            if not room.game.apply_action(action):
                raise ValueError("Action was rejected by the game rules")

            room.revision += 1
            self._advance_automation_locked(room)
            if self._check_game_over_once(room):
                room.revision += 1
            return room

    def request_rematch(self, code: str, player_id: int) -> Room:
        """Record one player's Play Again vote and restart once both players agree."""
        with self._lock:
            room = self._get_room_locked(code)
            self._touch_room_locked(room)
            self._validate_finished_room_locked(room, player_id)
            if room.rematch_declined:
                return room
            if player_id in room.rematch_votes:
                return room

            room.rematch_votes.add(player_id)
            if room.ready and room.rematch_votes.issuperset({0, 1}):
                self._reset_for_rematch_locked(room)
                room.message = "Both players chose Play Again. Starting a new coin flip."
            else:
                player_name = room.players.get(player_id, f"Player {player_id + 1}")
                room.message = f"{player_name} would like to play again."
            room.revision += 1
            return room

    def decline_rematch(self, code: str, player_id: int) -> Room:
        """Mark the finished match as not rematching because one player chose menu."""
        with self._lock:
            room = self._get_room_locked(code)
            self._touch_room_locked(room)
            self._validate_finished_room_locked(room, player_id)
            changed = not room.rematch_declined or room.rematch_declined_by != player_id
            player_name = room.players.get(player_id, f"Player {player_id + 1}")
            self._mark_rematch_declined_locked(room, player_id, player_name)
            if changed:
                room.revision += 1
            return room

    def _can_draft_card_locked(self, room: Room, card: Card) -> bool:
        return not (card.rank == CardRank.KING and room.kings_drafted >= 2)

    def leave_room(self, code: str, player_id: int) -> Room | None:
        with self._lock:
            room = self._get_room_locked(code)
            self._touch_room_locked(room)
            if player_id in room.players:
                departed_name = room.players.pop(player_id)
                if self._is_finished_game_locked(room) and not room.rematch_declined:
                    self._mark_rematch_declined_locked(room, player_id, departed_name)
                room.ready_players.discard(player_id)
                room.message = f"{departed_name} left the room."
                room.revision += 1
            if not room.players:
                del self._rooms[code]
                return None
            return room

    def room_count(self) -> int:
        """Return active room count after dropping stale rooms."""
        with self._lock:
            self._cleanup_inactive_rooms_locked()
            return len(self._rooms)

    def _touch_room_locked(self, room: Room) -> None:
        room.last_touched = time.monotonic()

    def _cleanup_inactive_rooms_locked(self) -> None:
        now = time.monotonic()
        stale_codes = [
            code
            for code, room in self._rooms.items()
            if now - room.last_touched > self.room_timeout_seconds
        ]
        for code in stale_codes:
            del self._rooms[code]

    def _advance_automation_locked(self, room: Room) -> None:
        if room.stage != "game" or room.game is None:
            return
        advanced = False
        for _ in range(8):
            if not room.game.advance_forced_traversing():
                break
            advanced = True
        if self._check_game_over_once(room):
            advanced = True
        if advanced:
            room.revision += 1

    def _validate_finished_room_locked(self, room: Room, player_id: int) -> None:
        if player_id not in room.players:
            raise ValueError("Player is not in this room")
        if not self._is_finished_game_locked(room):
            raise ValueError("The match is not finished yet")

    def _is_finished_game_locked(self, room: Room) -> bool:
        return room.stage == "game" and room.game is not None and room.game.winner is not None

    def _mark_rematch_declined_locked(self, room: Room, player_id: int, player_name: str) -> None:
        room.rematch_votes.clear()
        room.rematch_declined = True
        room.rematch_declined_by = player_id
        room.rematch_declined_name = player_name
        room.message = f"{player_name} returned to the main menu."

    def _reset_for_rematch_locked(self, room: Room) -> None:
        labyrinth_cards, draft_cards, jack_cards = setup_pregame_cards()
        draft_starting_player = choice([0, 1])
        room.game = None
        room.stage = "coin_flip"
        room.ready_players = {0, 1}
        room.labyrinth_cards = labyrinth_cards
        room.draft_cards = list(draft_cards)
        room.available_cards = list(draft_cards)
        room.jack_cards = jack_cards
        room.jack_order = get_jack_suit_order(jack_cards)
        room.draft_starting_player = draft_starting_player
        room.current_drafter = draft_starting_player
        room.draft_hands = {0: [], 1: []}
        room.kings_drafted = 0
        room.player_cards = []
        room.rematch_votes.clear()
        room.rematch_declined = False
        room.rematch_declined_by = None
        room.rematch_declined_name = ""

    def _check_game_over_once(self, room: Room) -> bool:
        if room.game is None:
            return False
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


def _html_response(handler: BaseHTTPRequestHandler, status: int, body: str) -> None:
    data = body.encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "text/html; charset=utf-8")
    handler.send_header("Content-Length", str(len(data)))
    handler.end_headers()
    handler.wfile.write(data)


def _static_file_response(handler: BaseHTTPRequestHandler, file_path: Path) -> None:
    content_type, encoding = mimetypes.guess_type(str(file_path))
    if file_path.name.endswith(".tar.gz"):
        content_type = "application/gzip"
        encoding = None
    elif file_path.suffix in {".apk", ".whl"}:
        content_type = "application/octet-stream"

    data = file_path.read_bytes()
    handler.send_response(200)
    handler.send_header("Content-Type", content_type or "application/octet-stream")
    if encoding:
        handler.send_header("Content-Encoding", encoding)
    handler.send_header("Content-Length", str(len(data)))
    handler.end_headers()
    handler.wfile.write(data)


def _server_status_page(server_url: str) -> str:
    escaped_server_url = html.escape(server_url, quote=True)
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Pan's Trial Room Server</title>
  <style>
    body {{
      margin: 0;
      min-height: 100vh;
      display: grid;
      place-items: center;
      background: #1d221f;
      color: #f3ead8;
      font-family: Arial, sans-serif;
    }}
    main {{
      width: min(720px, calc(100% - 32px));
      padding: 28px;
      border: 1px solid #8a7558;
      border-radius: 8px;
      background: #2e352f;
      box-shadow: 0 18px 45px rgba(0, 0, 0, 0.35);
    }}
    h1 {{
      margin: 0 0 12px;
      font-size: clamp(28px, 6vw, 44px);
    }}
    p {{
      margin: 12px 0;
      line-height: 1.5;
    }}
    code {{
      display: inline-block;
      padding: 3px 6px;
      border-radius: 5px;
      background: #171b18;
      color: #f8d77e;
    }}
    ol {{
      margin: 16px 0 0;
      padding-left: 24px;
    }}
    li {{
      margin: 8px 0;
      line-height: 1.45;
    }}
  </style>
</head>
<body>
  <main>
    <h1>Pan's Trial room server is running</h1>
    <p>This URL is the multiplayer room server, not the game screen.</p>
    <p>Use <code>{escaped_server_url}</code> in the game's <strong>Two Player</strong> screen as the Server URL.</p>
    <ol>
      <li>Open Pan's Trial and choose <strong>Two Player</strong>.</li>
      <li>Enter this Server URL, then choose <strong>Create Room</strong>.</li>
      <li>Share the same Server URL and the room code with the other player.</li>
    </ol>
  </main>
</body>
</html>"""


def _read_json(handler: BaseHTTPRequestHandler) -> dict[str, Any]:
    length = int(handler.headers.get("Content-Length", "0") or 0)
    if length <= 0:
        return {}
    return json.loads(handler.rfile.read(length).decode("utf-8"))


def make_room_handler(store: RoomStore, scheme: str = "http", web_root: Path | str | None = None):
    """Build a request handler bound to a specific room store."""

    resolved_web_root = Path(web_root).resolve() if web_root is not None else None

    class LocalRoomHandler(BaseHTTPRequestHandler):
        def do_OPTIONS(self) -> None:
            _json_response(self, 204, {})

        def do_GET(self) -> None:
            try:
                parts = self._path_parts()
                if parts == ["health"]:
                    _json_response(
                        self,
                        200,
                        {
                            "ok": True,
                            "rooms": store.room_count(),
                            "max_rooms": store.max_rooms,
                            "room_timeout_seconds": store.room_timeout_seconds,
                        },
                    )
                    return
                if parts and parts[0] == "rooms":
                    if len(parts) == 2:
                        room = store.get_room(parts[1])
                        _json_response(self, 200, room.snapshot())
                        return
                    _json_response(self, 404, {"error": "Unknown endpoint"})
                    return
                if resolved_web_root is not None and self._serve_static_file():
                    return
                if not parts:
                    host = self.headers.get("Host") or f"{self.server.server_address[0]}:{self.server.server_address[1]}"
                    _html_response(self, 200, _server_status_page(f"{scheme}://{host}"))
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

                if len(parts) == 3 and parts[0] == "rooms" and parts[2] == "ready":
                    player_id = int(body.get("player_id"))
                    room = store.toggle_player_ready(parts[1], player_id)
                    _json_response(self, 200, room.snapshot(player_id))
                    return

                if len(parts) == 3 and parts[0] == "rooms" and parts[2] == "draft":
                    player_id = int(body.get("player_id"))
                    revision = body.get("revision")
                    expected_revision = int(revision) if revision is not None else None
                    room = store.submit_draft_pick(
                        parts[1],
                        player_id,
                        int(body.get("card_index")),
                        expected_revision,
                    )
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

                if len(parts) == 3 and parts[0] == "rooms" and parts[2] == "rematch":
                    player_id = int(body.get("player_id"))
                    room = store.request_rematch(parts[1], player_id)
                    _json_response(self, 200, room.snapshot(player_id))
                    return

                if len(parts) == 3 and parts[0] == "rooms" and parts[2] == "decline":
                    player_id = int(body.get("player_id"))
                    room = store.decline_rematch(parts[1], player_id)
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

        def _serve_static_file(self) -> bool:
            if resolved_web_root is None:
                return False

            request_path = unquote(urlparse(self.path).path)
            relative_path = request_path.lstrip("/") or "index.html"
            if relative_path.endswith("/"):
                relative_path = f"{relative_path}index.html"

            candidate = (resolved_web_root / Path(*PurePosixPath(relative_path).parts)).resolve()
            try:
                candidate.relative_to(resolved_web_root)
            except ValueError:
                _json_response(self, 404, {"error": "Unknown endpoint"})
                return True

            if candidate.is_dir():
                candidate = candidate / "index.html"
            if not candidate.is_file():
                return False

            _static_file_response(self, candidate)
            return True

    return LocalRoomHandler


class LocalRoomServer:
    """Background localhost server used by the Create Room flow."""

    def __init__(
        self,
        host: str = DEFAULT_HOST,
        port: int = DEFAULT_PORT,
        ssl_context: ssl.SSLContext | None = None,
        web_root: Path | str | None = None,
        max_rooms: int = DEFAULT_MAX_ROOMS,
        room_timeout_seconds: int = DEFAULT_ROOM_TIMEOUT_SECONDS,
    ) -> None:
        self.host = host
        self.port = port
        self.ssl_context = ssl_context
        self.web_root = Path(web_root).resolve() if web_root is not None else None
        self.store = RoomStore(max_rooms=max_rooms, room_timeout_seconds=room_timeout_seconds)
        self.httpd: ThreadingHTTPServer | None = None
        self.thread: Thread | None = None

    @property
    def base_url(self) -> str:
        scheme = "https" if self.ssl_context is not None else "http"
        return f"{scheme}://{self.host}:{self.port}"

    def start(self) -> None:
        if self.httpd is not None:
            return

        scheme = "https" if self.ssl_context is not None else "http"
        handler = make_room_handler(self.store, scheme=scheme, web_root=self.web_root)
        port = self.port
        last_error = None
        for candidate in range(port, port + 20):
            try:
                self.httpd = ThreadingHTTPServer((self.host, candidate), handler)
                if self.ssl_context is not None:
                    self.httpd.socket = self.ssl_context.wrap_socket(self.httpd.socket, server_side=True)
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

    def mark_ready(self) -> bool:
        try:
            snapshot = _post_json(
                f"{self.base_url}/rooms/{self.room_code}/ready",
                {"player_id": self.player_id},
            )
            return self._apply_snapshot(snapshot)
        except OSError as exc:
            self.last_error = str(exc)
            return False

    def submit_draft_pick(self, card_index: int) -> bool:
        try:
            snapshot = _post_json(
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
            snapshot = _post_json(
                f"{self.base_url}/rooms/{self.room_code}/rematch",
                {"player_id": self.player_id},
            )
            return self._apply_snapshot(snapshot)
        except OSError as exc:
            self.last_error = str(exc)
            return False

    def decline_rematch(self) -> bool:
        try:
            snapshot = _post_json(
                f"{self.base_url}/rooms/{self.room_code}/decline",
                {"player_id": self.player_id},
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
        previous_players = dict(self.players)
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
