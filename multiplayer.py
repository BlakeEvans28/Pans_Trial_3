"""
Lightweight localhost room-based multiplayer support for Pan's Trial.

The server keeps the authoritative GameState and broadcasts full state updates
to up to two local clients in the same room.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import pickle
import queue
import secrets
import socket
import struct
import threading
import time

from game_setup import create_random_game


DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 5050
ROOM_CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def generate_room_code(length: int = 4) -> str:
    """Return an easy-to-read room code."""
    return "".join(secrets.choice(ROOM_CODE_ALPHABET) for _ in range(max(4, length)))


def _recv_exact(sock: socket.socket, size: int) -> bytes | None:
    """Read an exact number of bytes from a socket."""
    chunks = bytearray()
    while len(chunks) < size:
        try:
            chunk = sock.recv(size - len(chunks))
        except OSError:
            return None
        if not chunk:
            return None
        chunks.extend(chunk)
    return bytes(chunks)


def _recv_message(sock: socket.socket):
    """Receive one length-prefixed pickle payload."""
    header = _recv_exact(sock, 4)
    if header is None:
        return None
    size = struct.unpack("!I", header)[0]
    payload = _recv_exact(sock, size)
    if payload is None:
        return None
    return pickle.loads(payload)


def _send_message(sock: socket.socket, message, send_lock: threading.Lock) -> bool:
    """Send one length-prefixed pickle payload."""
    payload = pickle.dumps(message, protocol=pickle.HIGHEST_PROTOCOL)
    packet = struct.pack("!I", len(payload)) + payload
    try:
        with send_lock:
            sock.sendall(packet)
        return True
    except OSError:
        return False


@dataclass
class ConnectedClient:
    """Server-side connection metadata for one joined player."""

    sock: socket.socket
    address: tuple[str, int]
    send_lock: threading.Lock = field(default_factory=threading.Lock)
    player_id: int | None = None
    player_name: str = ""
    room_code: str | None = None


@dataclass
class RoomState:
    """Server-side room state."""

    room_code: str
    clients: dict[int, ConnectedClient] = field(default_factory=dict)
    game_state: object | None = None
    status: str = "waiting"

    @property
    def player_count(self) -> int:
        return len(self.clients)


class LocalRoomServer(threading.Thread):
    """Threaded localhost server that owns room and game state."""

    def __init__(self, host: str = DEFAULT_HOST, port: int = DEFAULT_PORT):
        super().__init__(daemon=True)
        self.host = host
        self.port = port
        self.ready_event = threading.Event()
        self._stop_event = threading.Event()
        self._lock = threading.Lock()
        self._rooms: dict[str, RoomState] = {}
        self._server_socket: socket.socket | None = None

    def run(self) -> None:
        """Accept incoming client sockets and hand each one to a worker thread."""
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind((self.host, self.port))
        server.listen()
        server.settimeout(0.5)
        self._server_socket = server
        self.ready_event.set()

        try:
            while not self._stop_event.is_set():
                try:
                    conn, address = server.accept()
                except socket.timeout:
                    continue
                except OSError:
                    break
                worker = threading.Thread(
                    target=self._handle_client,
                    args=(ConnectedClient(conn, address),),
                    daemon=True,
                )
                worker.start()
        finally:
            try:
                server.close()
            except OSError:
                pass

    def stop(self) -> None:
        """Stop the listener thread."""
        self._stop_event.set()
        if self._server_socket is not None:
            try:
                self._server_socket.close()
            except OSError:
                pass

    def _handle_client(self, client: ConnectedClient) -> None:
        """Process messages from one client until disconnect."""
        try:
            while not self._stop_event.is_set():
                message = _recv_message(client.sock)
                if message is None:
                    break
                self._process_message(client, message)
        finally:
            self._disconnect_client(client)

    def _process_message(self, client: ConnectedClient, message: dict) -> None:
        """Route one received client message."""
        message_type = message.get("type")
        if message_type == "join_room":
            room_code = str(message.get("room_code", "")).strip().upper()
            player_name = str(message.get("player_name", "")).strip() or "Player"
            self._join_room(client, room_code, player_name)
            return

        if message_type != "player_action":
            self._send_to_client(client, {"type": "error", "message": "Unknown message type."})
            return

        with self._lock:
            room = self._rooms.get(client.room_code or "")
            if room is None or room.game_state is None or client.player_id is None:
                self._send_to_client(client, {"type": "error", "message": "No active room is attached to this client."})
                return
            if room.clients.get(client.player_id) is not client:
                self._send_to_client(client, {"type": "error", "message": "Player identity mismatch for this room."})
                return

            action = message.get("action")
            applied = room.game_state.apply_action(action)
            if not applied:
                self._send_to_client(client, {"type": "error", "message": "That action is not legal right now."})
                return

            for _ in range(6):
                if not room.game_state.advance_forced_traversing():
                    break
            room.game_state.check_game_over()
            notice = room.game_state.consume_appeasing_return_notice()
            state_message = {
                "type": "game_state",
                "room_code": room.room_code,
                "game_state": room.game_state,
                "notice": notice,
            }

        self._broadcast_room(room, state_message)

    def _join_room(self, client: ConnectedClient, room_code: str, player_name: str) -> None:
        """Add a client to a room, starting a game when the second player arrives."""
        if not room_code:
            self._send_to_client(client, {"type": "error", "message": "Enter a room code first."})
            return

        room_update: dict | None = None
        game_start: dict | None = None
        with self._lock:
            room = self._rooms.setdefault(room_code, RoomState(room_code=room_code))
            available_ids = [player_id for player_id in (0, 1) if player_id not in room.clients]
            if not available_ids:
                self._send_to_client(client, {"type": "error", "message": f"Room {room_code} is already full."})
                return

            player_id = available_ids[0]
            client.player_id = player_id
            client.player_name = player_name
            client.room_code = room_code
            room.clients[player_id] = client

            players = self._get_room_player_payload(room)
            join_message = {
                "type": "room_joined",
                "room_code": room_code,
                "player_id": player_id,
                "player_count": room.player_count,
                "players": players,
                "status": room.status,
            }
            self._send_to_client(client, join_message)

            room_update = {
                "type": "room_update",
                "room_code": room_code,
                "player_count": room.player_count,
                "players": players,
                "status": room.status,
                "message": self._get_room_status_message(room),
            }

            if room.player_count == 2 and room.game_state is None:
                room.game_state = create_random_game()
                room.status = "active"
                game_start = {
                    "type": "game_start",
                    "room_code": room_code,
                    "player_count": room.player_count,
                    "players": self._get_room_player_payload(room),
                    "game_state": room.game_state,
                }
                room_update = {
                    "type": "room_update",
                    "room_code": room_code,
                    "player_count": room.player_count,
                    "players": self._get_room_player_payload(room),
                    "status": room.status,
                    "message": "Both players are here. Starting the match.",
                }

        if room_update is not None:
            self._broadcast_room(room, room_update)
        if game_start is not None:
            self._broadcast_room(room, game_start)

    def _disconnect_client(self, client: ConnectedClient) -> None:
        """Remove a client from its room and inform anyone left behind."""
        room_update = None
        room_closed = None
        room = None
        with self._lock:
            room_code = client.room_code
            if not room_code or room_code not in self._rooms:
                self._close_socket_quietly(client.sock)
                return

            room = self._rooms[room_code]
            if client.player_id in room.clients and room.clients[client.player_id] is client:
                del room.clients[client.player_id]

            if room.player_count == 0:
                del self._rooms[room_code]
            elif room.status == "active":
                room_closed = {
                    "type": "room_closed",
                    "room_code": room_code,
                    "message": "Your opponent disconnected. The room has been closed.",
                }
                del self._rooms[room_code]
            else:
                room_update = {
                    "type": "room_update",
                    "room_code": room_code,
                    "player_count": room.player_count,
                    "players": self._get_room_player_payload(room),
                    "status": room.status,
                    "message": self._get_room_status_message(room),
                }

        if room_update is not None and room is not None:
            self._broadcast_room(room, room_update)
        if room_closed is not None and room is not None:
            self._broadcast_room(room, room_closed)
        self._close_socket_quietly(client.sock)

    def _get_room_player_payload(self, room: RoomState) -> list[dict]:
        """Return a consistent player list for room updates."""
        payload = []
        for player_id in sorted(room.clients):
            client = room.clients[player_id]
            payload.append(
                {
                    "player_id": player_id,
                    "player_name": client.player_name,
                }
            )
        return payload

    @staticmethod
    def _get_room_status_message(room: RoomState) -> str:
        """Return the room's current waiting/active status line."""
        if room.status == "active":
            return "Both players are connected."
        if room.player_count == 0:
            return "Waiting for players."
        if room.player_count == 1:
            return "Waiting for a second player to join."
        return "Room is full."

    def _broadcast_room(self, room: RoomState, message: dict) -> None:
        """Send one message to every client in a room."""
        for client in list(room.clients.values()):
            self._send_to_client(client, message)

    def _send_to_client(self, client: ConnectedClient, message: dict) -> None:
        """Send one message to one client, disconnecting it on failure."""
        if not _send_message(client.sock, message, client.send_lock):
            threading.Thread(target=self._disconnect_client, args=(client,), daemon=True).start()

    @staticmethod
    def _close_socket_quietly(sock: socket.socket) -> None:
        """Close a socket without surfacing shutdown noise."""
        try:
            sock.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        try:
            sock.close()
        except OSError:
            pass


_SERVER_INSTANCE: LocalRoomServer | None = None
_SERVER_LOCK = threading.Lock()


def ensure_local_server_running(host: str = DEFAULT_HOST, port: int = DEFAULT_PORT) -> LocalRoomServer:
    """Start the localhost room server in-process when needed."""
    global _SERVER_INSTANCE
    with _SERVER_LOCK:
        if _SERVER_INSTANCE is not None and _SERVER_INSTANCE.is_alive():
            return _SERVER_INSTANCE
        _SERVER_INSTANCE = LocalRoomServer(host=host, port=port)
        _SERVER_INSTANCE.start()
    _SERVER_INSTANCE.ready_event.wait(timeout=2.0)
    return _SERVER_INSTANCE


class LocalRoomClient:
    """Client helper that connects a pygame app to the localhost room server."""

    def __init__(self, host: str = DEFAULT_HOST, port: int = DEFAULT_PORT, auto_start_server: bool = True):
        self.host = host
        self.port = port
        self.auto_start_server = auto_start_server
        self.sock: socket.socket | None = None
        self.send_lock = threading.Lock()
        self.listener_thread: threading.Thread | None = None
        self.messages: queue.Queue = queue.Queue()
        self._closing = False
        self._connected = False
        self.player_id: int | None = None
        self.player_name: str = ""
        self.room_code: str | None = None

    def connect(self) -> bool:
        """Connect to the room server, auto-starting it for localhost if needed."""
        if self._connected and self.sock is not None:
            return True

        for attempt in range(2):
            try:
                sock = socket.create_connection((self.host, self.port), timeout=2.0)
                sock.settimeout(None)
                self.sock = sock
                self._connected = True
                self._closing = False
                self.listener_thread = threading.Thread(target=self._listen_loop, daemon=True)
                self.listener_thread.start()
                return True
            except OSError:
                if attempt == 0 and self.auto_start_server:
                    ensure_local_server_running(self.host, self.port)
                    time.sleep(0.1)
                    continue
                break
        return False

    def join_room(self, room_code: str, player_name: str) -> bool:
        """Connect and request a room seat."""
        room_code = room_code.strip().upper()
        player_name = player_name.strip() or "Player"
        if not room_code:
            return False
        if not self.connect():
            return False
        self.player_name = player_name
        return self._send(
            {
                "type": "join_room",
                "room_code": room_code,
                "player_name": player_name,
            }
        )

    def send_action(self, action) -> bool:
        """Send one gameplay action to the authoritative room server."""
        if not self._connected or self.sock is None or self.player_id is None or self.room_code is None:
            return False
        return self._send(
            {
                "type": "player_action",
                "room_code": self.room_code,
                "player_id": self.player_id,
                "action": action,
            }
        )

    def poll_messages(self) -> list[dict]:
        """Drain queued server messages for the main thread."""
        drained = []
        while True:
            try:
                drained.append(self.messages.get_nowait())
            except queue.Empty:
                return drained

    def close(self) -> None:
        """Close the client connection and clear room identity."""
        self._closing = True
        self.player_id = None
        self.room_code = None
        self._connected = False
        if self.sock is not None:
            try:
                self.sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            try:
                self.sock.close()
            except OSError:
                pass
        self.sock = None
        self.messages = queue.Queue()

    def _listen_loop(self) -> None:
        """Receive server messages in the background."""
        while self.sock is not None and not self._closing:
            message = _recv_message(self.sock)
            if message is None:
                break
            if message.get("type") == "room_joined":
                self.player_id = message.get("player_id")
                self.room_code = message.get("room_code")
            elif message.get("type") == "room_closed":
                self.player_id = None
                self.room_code = None
            self.messages.put(message)

        was_closing = self._closing
        self._connected = False
        self.sock = None
        if not was_closing:
            self.player_id = None
            self.room_code = None
            self.messages.put(
                {
                    "type": "disconnected",
                    "message": "Connection to the localhost game room was lost.",
                }
            )

    def _send(self, message: dict) -> bool:
        """Send one message if the socket is still connected."""
        if self.sock is None:
            return False
        return _send_message(self.sock, message, self.send_lock)
