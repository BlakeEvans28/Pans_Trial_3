"""
Tests for Pan's Trial game rules.
"""

import os
import json
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame
import pygame_gui
import pytest
from engine import (
    Card, CardRank, CardSuit, GameState, GamePhase,
    MoveAction, PickupCurrentCardAction, PlayCardAction, Position, SuitRole, ChooseCombatCardAction,
    ChooseRequestAction, RequestType, ResolveBallistaShotAction, SelectDamageCardAction,
    SelectRestructureSuitAction, SelectPlaneShiftDirectionAction, ResolvePlaneShiftAction,
    CancelRequestSelectionAction, PlaceCardsAction
)
from deck_utils import setup_game_deck, create_6x6_labyrinth, draft_hands, get_jack_suit_order
from multiplayer import LocalRoomClient, LocalRoomServer
from multiplayer.browser_room import BrowserRoomClient
from multiplayer.local_room import RoomStore, create_quick_match_game
from multiplayer.serialization import encode_game_state
from ui.audio_manager import AudioManager
from ui.input_handler import InputHandler
from ui.board_renderer import BoardRenderer
from ui.game_screen import GameScreen
from ui.player_names import normalize_player_names, replace_player_tokens
from ui.screen_manager import CoinFlipScreen, DraftScreen, GameOverScreen, JackRevealScreen, MultiplayerLobbyScreen, SettingsScreen
from ui.window import GameWindow


class SmokeAudio:
    """Small audio test double for UI smoke checks."""

    def set_volume(self, volume: float) -> None:
        self.volume = volume

    def play_phase_music(self) -> None:
        self.phase_music_started = True


class SmokeWindow:
    """Minimal GameWindow-shaped object for screen smoke tests."""

    BASE_WINDOW_WIDTH = 1200
    BASE_WINDOW_HEIGHT = 900

    def __init__(self, width: int = 900, height: int = 700):
        self.WINDOW_WIDTH = width
        self.WINDOW_HEIGHT = height
        self.fullscreen = False
        self.text_scale = 1.0
        self.animation_speed = 1.0
        self.sound_volume = 0.5
        self.tutorial_enabled = False
        self.audio = SmokeAudio()
        self.ui_manager = pygame_gui.UIManager((width, height))
        self.reset_calls = 0

    def get_scale(self) -> float:
        return min(self.WINDOW_WIDTH / self.BASE_WINDOW_WIDTH, self.WINDOW_HEIGHT / self.BASE_WINDOW_HEIGHT)

    def get_layout_mode(self) -> str:
        if self.WINDOW_WIDTH < 720 or self.WINDOW_HEIGHT < 680:
            return "compact"
        if self.WINDOW_WIDTH < 1020 or self.WINDOW_HEIGHT < 760:
            return "medium"
        return "wide"

    def is_compact_layout(self) -> bool:
        return self.get_layout_mode() == "compact"

    def scale(self, value: int, minimum: int = 1) -> int:
        return max(minimum, int(round(value * self.get_scale())))

    def scale_x(self, value: int, minimum: int = 1) -> int:
        return max(minimum, int(round(value * self.WINDOW_WIDTH / self.BASE_WINDOW_WIDTH)))

    def scale_y(self, value: int, minimum: int = 1) -> int:
        return max(minimum, int(round(value * self.WINDOW_HEIGHT / self.BASE_WINDOW_HEIGHT)))

    def font_size(self, value: int, minimum: int = 1) -> int:
        return max(minimum, int(round(value * self.get_scale() * self.text_scale)))

    def toggle_fullscreen(self) -> bool:
        self.fullscreen = not self.fullscreen
        return True

    def reset_tutorial_tips(self) -> None:
        self.reset_calls += 1
        game_screen = getattr(self, "game_screen_ref", None)
        if game_screen is not None and hasattr(game_screen, "reset_tutorial_cycle"):
            game_screen.reset_tutorial_cycle()


@pytest.fixture(scope="module", autouse=True)
def pygame_smoke_display():
    """Give pygame surfaces a tiny display for convert_alpha smoke tests."""
    pygame.display.init()
    pygame.font.init()
    if pygame.display.get_surface() is None:
        pygame.display.set_mode((1, 1))
    yield
    pygame.display.quit()


@pytest.fixture
def game_setup():
    """Set up a fresh game for testing."""
    labyrinth, p0_deck, p1_deck, jack_cards = setup_game_deck()
    grid = create_6x6_labyrinth(labyrinth)
    p0, p1, start = draft_hands(p0_deck, p1_deck)
    jacks = get_jack_suit_order(jack_cards)
    
    game = GameState()
    game.setup_board(grid)
    game.setup_suit_roles(jacks)
    
    for c in p0:
        game.add_card_to_hand(0, c)
    for c in p1:
        game.add_card_to_hand(1, c)
    
    game.place_player(0, Position(5, 3))
    game.place_player(1, Position(0, 2))
    game.phase = GamePhase.TRAVERSING
    
    return game


def test_audio_manager_tries_next_desktop_music_candidate(monkeypatch):
    """A bad preferred MP3 should not silence the whole maze soundtrack."""
    first_track = Path("PanPhase1_Updated.mp3")
    fallback_track = Path("PanPhase1.mp3")

    audio = AudioManager.__new__(AudioManager)
    audio.allow_music_files = True
    audio.is_web = False
    audio.current_music = None
    audio.track_paths = {"phase": (first_track, fallback_track)}
    audio.last_error = None
    audio._ensure_desktop_ready = lambda: True
    audio._refresh_track_paths = lambda: None
    audio._apply_desktop_volume = lambda: None

    attempts = []
    plays = []

    class FakeMusic:
        def get_busy(self) -> bool:
            return False

        def load(self, path: str) -> None:
            attempts.append(Path(path).name)
            if Path(path) == first_track:
                raise pygame.error("bad codec")

        def play(self, loops: int, fade_ms: int) -> None:
            plays.append((loops, fade_ms))

    monkeypatch.setattr(pygame.mixer, "music", FakeMusic())

    audio.play_phase_music()

    assert attempts == ["PanPhase1_Updated.mp3", "PanPhase1.mp3"]
    assert plays == [(-1, 650)]
    assert audio.current_music == "phase"
    assert audio.last_error is None


def test_audio_manager_sends_web_music_candidates_as_newline_list():
    """The browser bridge receives every candidate so it can retry blocked tracks."""
    audio = AudioManager.__new__(AudioManager)
    audio.allow_music_files = True
    audio.is_web = True
    audio.current_music = None
    audio.track_urls = {"phase": ("audio/PanPhase1_Updated.mp3", "audio/PanPhase1.mp3")}
    audio.enabled = True
    audio.volume = 0.5
    audio.last_error = None

    class Bridge:
        def __init__(self) -> None:
            self.calls = []

        def playMusic(self, src: str, volume: float) -> None:
            self.calls.append((src, volume))

    bridge = Bridge()
    audio._ensure_web_ready = lambda: True
    audio._get_web_audio_bridge = lambda: bridge

    audio.play_phase_music()

    assert bridge.calls == [("audio/PanPhase1_Updated.mp3\naudio/PanPhase1.mp3", 0.5)]
    assert audio.current_music == "phase"
    assert audio.last_error is None


def _first_legal_draft_index(client: LocalRoomClient) -> int:
    for index, card in enumerate(client.available_cards):
        if card is None:
            continue
        if card.rank == CardRank.KING and client.kings_drafted >= 2:
            continue
        return index
    raise AssertionError("No legal draft card found")


def _ready_and_complete_room_draft(host: LocalRoomClient, guest: LocalRoomClient) -> None:
    assert host.mark_ready()
    assert guest.mark_ready()
    host.refresh()
    guest.refresh()

    assert host.stage in {"coin_flip", "draft"}
    assert guest.stage in {"coin_flip", "draft"}

    for _ in range(10):
        active = host if host.current_drafter == host.player_id else guest
        assert active.submit_draft_pick(_first_legal_draft_index(active))
        host.refresh()
        guest.refresh()

    assert host.stage == "game"
    assert guest.stage == "game"
    assert host.game is not None
    assert guest.game is not None


def test_local_room_server_create_join_and_submit_move():
    """Two localhost clients can join a room and share the authoritative game state."""
    server = LocalRoomServer(port=8876)
    server.start()
    try:
        host = LocalRoomClient.create("Host", server.base_url)
        guest = LocalRoomClient.join("Guest", server.base_url, host.room_code)
        host.refresh()

        assert host.ready
        assert guest.ready
        assert host.players == {0: "Host", 1: "Guest"}
        assert guest.players == {0: "Host", 1: "Guest"}
        assert host.stage == "lobby"
        assert host.game is None

        assert not host.submit_action(MoveAction(0, "up"))
        assert "Game has not started" in host.last_error

        _ready_and_complete_room_draft(host, guest)

        active_player = host.game.current_player
        acting_client = host if active_player == host.player_id else guest
        direction = acting_client.game.get_legal_moves(active_player)[0]
        starting_position = acting_client.game.board.get_player_position(active_player)

        assert acting_client.submit_action(MoveAction(active_player, direction))
        host.refresh()
        guest.refresh()
        synced_position = host.game.board.get_player_position(active_player)

        assert host.revision == guest.revision
        assert synced_position != starting_position
        assert guest.game.board.get_player_position(active_player) == synced_position
        assert host.game.current_player == guest.game.current_player
    finally:
        server.stop()


def test_local_room_rejects_wrong_player_and_frees_seat_on_leave():
    """The room server should enforce seats and allow a departed guest to be replaced."""
    server = LocalRoomServer(port=8896)
    server.start()
    try:
        host = LocalRoomClient.create("Host", server.base_url)
        guest = LocalRoomClient.join("Guest", server.base_url, host.room_code)
        host.refresh()

        with pytest.raises(OSError, match="already has two players"):
            LocalRoomClient.join("Third", server.base_url, host.room_code)

        guest.leave()
        replacement = LocalRoomClient.join("Replacement", server.base_url, host.room_code)
        replacement.refresh()
        assert replacement.players[1] == "Replacement"

        host.leave()
        new_host = LocalRoomClient.join("NewHost", server.base_url, host.room_code)
        assert new_host.player_id == 0
        new_host.refresh()
        assert new_host.players[0] == "NewHost"

        _ready_and_complete_room_draft(new_host, replacement)
        active_player = new_host.game.current_player
        wrong_client = replacement if active_player == new_host.player_id else new_host
        direction = new_host.game.get_legal_moves(active_player)[0]

        assert not wrong_client.submit_action(MoveAction(active_player, direction))
        assert "does not belong" in wrong_client.last_error
    finally:
        server.stop()


def test_local_room_suffixes_duplicate_picked_names():
    """Two players who pick the same name should display as unique names."""
    server = LocalRoomServer(port=8906)
    server.start()
    try:
        host = LocalRoomClient.create("Brandt", server.base_url)
        guest = LocalRoomClient.join("Brandt", server.base_url, host.room_code)
        host.refresh()

        assert host.players == {0: "Brandt", 1: "Brandt1"}
        assert guest.players == {0: "Brandt", 1: "Brandt1"}
    finally:
        server.stop()


def test_local_room_rematch_waits_for_both_players():
    """A multiplayer rematch should restart only after both players choose Play Again."""
    server = LocalRoomServer(port=8926)
    server.start()
    try:
        host = LocalRoomClient.create("Host", server.base_url)
        guest = LocalRoomClient.join("Guest", server.base_url, host.room_code)
        _ready_and_complete_room_draft(host, guest)

        room = server.store.get_room(host.room_code)
        room.game.winner = 0
        room.revision += 1
        host.refresh()
        guest.refresh()

        assert host.request_rematch()
        guest.refresh()

        assert host.stage == "game"
        assert guest.stage == "game"
        assert guest.rematch_votes == {0}
        assert guest.message == "Host would like to play again."

        assert guest.request_rematch()
        host.refresh()
        guest.refresh()

        assert host.stage == "coin_flip"
        assert guest.stage == "coin_flip"
        assert host.game is None
        assert guest.game is None
        assert host.rematch_votes == set()
        assert guest.rematch_votes == set()
        assert host.ready_players == {0, 1}
        assert guest.ready_players == {0, 1}
        assert len(host.draft_cards) == 12
        assert host.draft_hands == {0: [], 1: []}
    finally:
        server.stop()


def test_local_room_menu_declines_pending_rematch_for_other_player():
    """If one player goes to menu after game over, the other cannot rematch alone."""
    server = LocalRoomServer(port=8946)
    server.start()
    try:
        host = LocalRoomClient.create("Host", server.base_url)
        guest = LocalRoomClient.join("Guest", server.base_url, host.room_code)
        _ready_and_complete_room_draft(host, guest)

        room = server.store.get_room(host.room_code)
        room.game.winner = 1
        room.revision += 1
        host.refresh()
        guest.refresh()

        assert host.request_rematch()
        assert guest.decline_rematch()
        guest.leave()
        host.refresh()

        assert host.rematch_declined is True
        assert host.rematch_declined_by == 1
        assert host.rematch_declined_name == "Guest"
        assert host.rematch_votes == set()
        assert not host.request_rematch()
        assert host.rematch_declined is True
    finally:
        server.stop()


def test_local_room_server_root_shows_status_page():
    """Opening the printed room-server URL in a browser should explain how to connect."""
    from urllib import request

    server = LocalRoomServer(port=8916)
    server.start()
    try:
        with request.urlopen(f"{server.base_url}/", timeout=0.75) as response:
            body = response.read().decode("utf-8")
            content_type = response.headers.get("Content-Type", "")

        assert "text/html" in content_type
        assert "Pan's Trial room server is running" in body
        assert "Two Player" in body
        assert "Unknown endpoint" not in body
    finally:
        server.stop()


def test_room_server_can_serve_web_build_and_room_api():
    """A hosted room server should be able to serve the game page and rooms from one URL."""
    from urllib import request

    web_root = Path(__file__).resolve().parent / "fixtures" / "web_root"

    server = LocalRoomServer(port=8936, web_root=web_root)
    server.start()
    try:
        with request.urlopen(f"{server.base_url}/", timeout=0.75) as response:
            body = response.read().decode("utf-8")
            content_type = response.headers.get("Content-Type", "")

        assert "text/html" in content_type
        assert "Pan's Trial" in body

        with request.urlopen(f"{server.base_url}/bundle.tar.gz", timeout=0.75) as response:
            assert response.read().strip() == b"fake-bundle"
            assert response.headers.get("Content-Type") == "application/gzip"

        host = LocalRoomClient.create("Host", server.base_url)
        assert host.room_code
        assert host.player_id == 0
    finally:
        server.stop()


def test_room_server_health_endpoint_and_room_limits():
    """Hosted deployments should expose health data and reject rooms after the configured cap."""
    from urllib import request

    server = LocalRoomServer(port=8956, max_rooms=1, room_timeout_seconds=60)
    server.start()
    try:
        with request.urlopen(f"{server.base_url}/health", timeout=0.75) as response:
            payload = json.loads(response.read().decode("utf-8"))

        assert payload["ok"] is True
        assert payload["rooms"] == 0
        assert payload["max_rooms"] == 1

        LocalRoomClient.create("Host", server.base_url)
        with pytest.raises(OSError, match="server is full"):
            LocalRoomClient.create("Second", server.base_url)
    finally:
        server.stop()


def test_room_store_cleans_up_inactive_rooms():
    """Inactive rooms should be dropped so hosted servers do not fill forever."""
    store = RoomStore(room_timeout_seconds=60)
    room, _ = store.create_room("Host")
    room.last_touched -= 61

    assert store.room_count() == 0


def test_room_store_game_over_poll_is_one_shot():
    """Polling a finished room should not keep mutating its summary."""
    store = RoomStore()
    room, _ = store.create_room("Host")
    room.players[1] = "Guest"
    room.ready_players = {0, 1}
    room.stage = "game"
    room.game = create_quick_match_game()
    room.game.damage[0].cards = [
        Card(CardRank.KING, CardSuit.HEARTS),
        Card(CardRank.KING, CardSuit.DIAMONDS),
        Card(CardRank.ACE, CardSuit.CLUBS),
    ]

    store.get_room(room.code)
    first_revision = room.revision
    first_events = list(room.game.major_events)

    store.get_room(room.code)

    assert room.revision == first_revision
    assert room.game.major_events == first_events


def test_room_store_rejects_stale_action_revision():
    """The room server should reject actions from clients with old snapshots."""
    store = RoomStore()
    room, _ = store.create_room("Host")
    room.players[1] = "Guest"
    room.ready_players = {0, 1}
    room.stage = "game"
    room.game = create_quick_match_game()
    active_player = room.game.current_player
    direction = room.game.get_legal_moves(active_player)[0]
    starting_position = room.game.board.get_player_position(active_player)
    stale_revision = room.revision
    room.revision += 1

    with pytest.raises(ValueError, match="Room state changed"):
        store.submit_action(
            room.code,
            active_player,
            MoveAction(active_player, direction),
            expected_revision=stale_revision,
        )

    assert room.game.board.get_player_position(active_player) == starting_position


def test_room_store_accepts_simultaneous_appeasing_cards_from_stale_snapshots():
    """Both room clients may submit Appeasing cards without waiting for a turn refresh."""
    store = RoomStore()
    room, _ = store.create_room("Host")
    room.players[1] = "Guest"
    room.ready_players = {0, 1}
    room.stage = "game"
    room.game = create_quick_match_game()
    room.game.phase = GamePhase.APPEASING
    room.game.current_player = 0
    room.game.current_request_winner = None
    room.game.phase_started_cards = []

    card0 = room.game.get_player_hand(0)[0]
    card1 = room.game.get_player_hand(1)[0]
    stale_revision = room.revision

    store.submit_action(
        room.code,
        1,
        PlayCardAction(1, card1),
        expected_revision=stale_revision,
    )
    assert room.revision > stale_revision

    store.submit_action(
        room.code,
        0,
        PlayCardAction(0, card0),
        expected_revision=stale_revision,
    )

    assert room.game.current_request_winner in {0, 1}
    assert len(room.game.phase_started_cards) == 2


def test_browser_room_client_uses_javascript_bridge(monkeypatch, game_setup):
    """Web clients should create rooms through the browser HTTP bridge."""
    import platform

    class Bridge:
        def __init__(self) -> None:
            self.calls = []

        def request(self, method: str, url: str, body: str) -> str:
            self.calls.append((method, url, body))
            return json.dumps(
                {
                    "room_code": "1000",
                    "player_id": 0,
                    "players": {"0": "WebHost"},
                    "ready": False,
                    "revision": 0,
                    "message": "Waiting",
                    "state": encode_game_state(game_setup),
                }
            )

    bridge = Bridge()
    monkeypatch.setattr(platform, "window", type("Window", (), {"panTrialRoomBridge": bridge})(), raising=False)

    client = BrowserRoomClient.create("WebHost", "http://192.168.1.10:8765")

    assert client.room_code == "1000"
    assert client.player_id == 0
    assert client.players == {0: "WebHost"}
    assert bridge.calls[0][0] == "POST"
    assert bridge.calls[0][1] == "http://192.168.1.10:8765/rooms"


def test_browser_room_import_does_not_need_desktop_http_server():
    """The web room client should import in runtimes that do not ship http.server."""
    import subprocess
    import sys
    import textwrap

    script = textwrap.dedent(
        """
        import builtins

        real_import = builtins.__import__

        def guarded_import(name, globals=None, locals=None, fromlist=(), level=0):
            if name == "http.server":
                raise ModuleNotFoundError("No module named 'http.server'")
            return real_import(name, globals, locals, fromlist, level)

        builtins.__import__ = guarded_import

        from multiplayer.browser_room import BrowserRoomClient

        print(BrowserRoomClient.__name__)
        """
    )

    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=Path(__file__).resolve().parents[1],
        capture_output=True,
        text=True,
        timeout=10,
    )

    assert result.returncode == 0, result.stderr + result.stdout
    assert "BrowserRoomClient" in result.stdout


def test_multiplayer_lobby_screen_lays_out_room_controls():
    """The room screen exposes code-only create/join controls."""
    window = SmokeWindow(width=1200, height=900)
    screen = MultiplayerLobbyScreen(window)

    assert set(screen.button_rects) == {"create", "join", "ready", "back"}
    assert screen.get_player_name() == "Player"
    assert screen.get_server_url() == MultiplayerLobbyScreen.DEFAULT_SERVER_URL
    assert not screen.server_entry.visible
    screen.on_enter()
    assert screen.name_entry.visible
    assert screen.room_entry.visible
    assert not screen.server_entry.visible
    screen.server_entry.set_text("127.0.0.1:8765")
    assert screen.get_server_url() == MultiplayerLobbyScreen.DEFAULT_SERVER_URL
    button_height = screen.button_rects["create"].height
    assert screen.button_rects["create"].y - screen.room_entry.relative_rect.bottom == int(button_height * 0.5)
    assert screen.button_rects["ready"].y - screen.button_rects["create"].bottom == int(button_height * 0.25) - button_height // 2
    screen.set_status("Room created.", room_code="1001")
    notice_rect = screen._get_room_code_notice_rect()
    assert notice_rect.y == screen.room_entry.relative_rect.y - screen.scale_y(64, 48) + screen.scale_y(20, 15)
    assert not notice_rect.colliderect(screen.room_entry.relative_rect)

    surface = pygame.Surface((window.WINDOW_WIDTH, window.WINDOW_HEIGHT))
    screen.render(surface)


def test_multiplayer_lobby_code_only_flow_keeps_server_url_internal():
    """Players should only need the room code while the server URL remains automatic."""
    window = SmokeWindow(width=1200, height=900)
    window.is_web = True
    screen = MultiplayerLobbyScreen(window)

    screen.on_enter()
    screen.room_entry.set_text("1000")
    screen.set_status("Room created.", room_code="1000", server_url="https://pans.example")

    assert screen.get_room_code() == "1000"
    assert screen.get_server_url() == "https://pans.example"
    assert screen.room_code_text == "1000"
    assert screen.server_url_text == "https://pans.example"
    assert not screen.server_entry.visible


def test_multiplayer_lobby_web_uses_hosted_default_server_url(monkeypatch):
    """Hosted web builds should default Two Player rooms to the page's server URL."""
    import platform

    window = SmokeWindow(width=1200, height=900)
    window.is_web = True

    class WindowBridge:
        @staticmethod
        def panTrialResolveRoomServerUrl() -> str:
            return "https://pans.example"

    monkeypatch.setattr(platform, "window", WindowBridge(), raising=False)

    screen = MultiplayerLobbyScreen(window)

    assert screen.get_server_url() == "https://pans.example"


def test_player_name_helpers_replace_tokens_and_suffix_duplicates():
    """UI copy should use picked names instead of P1/P2 or Player 1/2."""
    names = normalize_player_names({0: "Alex", 1: "Alex"})

    assert names == {0: "Alex", 1: "Alex1"}
    assert replace_player_tokens("P2 hit Player 1.", names) == "Alex1 hit Alex."


def test_multiplayer_text_entry_supports_undo_shortcut():
    """Ctrl+Z should undo the last edit inside multiplayer text fields."""
    window = SmokeWindow(width=1200, height=900)
    screen = MultiplayerLobbyScreen(window)
    entry = screen.name_entry
    entry.focus()
    entry.set_text("Pan")

    backspace = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_BACKSPACE, mod=0)
    undo = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_z, mod=pygame.KMOD_CTRL)

    assert entry.process_event(backspace) is True
    assert entry.get_text() == "Pa"
    assert entry.process_event(undo) is True
    assert entry.get_text() == "Pan"


def test_multiplayer_web_text_entry_clipboard_shortcuts(monkeypatch):
    """Web text fields should support Ctrl+C, Ctrl+V, and Ctrl+X through the page bridge."""
    import platform

    class Clipboard:
        def __init__(self) -> None:
            self.written = []

        def readText(self, fallback: str) -> str:
            return "1234"

        def writeText(self, text: str) -> str:
            self.written.append(text)
            return text

    clipboard = Clipboard()
    monkeypatch.setattr(
        platform,
        "window",
        type("Window", (), {"panTrialClipboard": clipboard})(),
        raising=False,
    )

    window = SmokeWindow(width=1200, height=900)
    window.is_web = True
    screen = MultiplayerLobbyScreen(window)
    entry = screen.room_entry
    entry.focus()
    entry.set_text("")

    paste = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_v, mod=pygame.KMOD_CTRL)
    copy = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_c, mod=pygame.KMOD_CTRL)
    cut = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_x, mod=pygame.KMOD_CTRL)
    undo = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_z, mod=pygame.KMOD_CTRL)

    assert entry.process_event(paste) is True
    assert entry.get_text() == "1234"

    entry.select_range = [0, 4]
    assert entry.process_event(copy) is True
    assert clipboard.written[-1] == "1234"

    entry.select_range = [0, 4]
    assert entry.process_event(cut) is True
    assert entry.get_text() == ""
    assert clipboard.written[-1] == "1234"

    assert entry.process_event(undo) is True
    assert entry.get_text() == "1234"


def test_multiplayer_game_screen_blocks_remote_turn_input(game_setup):
    """A client should not submit actions for the other player's turn."""
    game = game_setup
    game.phase = GamePhase.TRAVERSING
    game.current_player = 1
    window = SmokeWindow(width=1200, height=900)

    class Session:
        player_id = 0
        room_code = "1000"
        players = {0: "Host", 1: "Guest"}
        ready = True
        last_error = None
        submitted = []

        def update(self, time_delta: float) -> bool:
            return False

        def submit_action(self, action):
            self.submitted.append(action)
            return True

    session = Session()
    session.game = game
    window.multiplayer_session = session
    screen = GameScreen(window, game)

    direction = game.get_legal_moves(1)[0]

    assert screen._apply_action(MoveAction(1, direction)) is False
    assert session.submitted == []

    screen.damage_popup_player = 1
    damage_event = pygame.event.Event(
        pygame.MOUSEBUTTONDOWN,
        {"pos": screen._get_damage_summary_rects()[0].center},
    )
    key_event = pygame.event.Event(pygame.KEYDOWN, {"key": pygame.K_UP})

    assert screen.handle_events(damage_event) is True
    assert screen.handle_events(key_event) is True
    assert screen.damage_popup_player is None
    assert session.submitted == []

    surface = pygame.Surface((window.WINDOW_WIDTH, window.WINDOW_HEIGHT))
    screen.render(surface)
    assert screen.hand_card_rects == []
    assert screen._get_player_names() == {0: "Host", 1: "Guest"}


def test_card_combat_value():
    """Test card combat value calculation."""
    assert Card(CardRank.ACE, CardSuit.HEARTS).combat_value() == 1
    assert Card(CardRank.TWO, CardSuit.HEARTS).combat_value() == 2
    assert Card(CardRank.TEN, CardSuit.HEARTS).combat_value() == 10
    assert Card(CardRank.QUEEN, CardSuit.HEARTS).combat_value() == 11
    assert Card(CardRank.KING, CardSuit.HEARTS).combat_value() == 12


def test_toroidal_wrapping(game_setup):
    """Test toroidal grid wrapping."""
    game = game_setup
    
    # Get position at (5, 3)
    assert game.board.get_player_position(0) == Position(5, 3)
    
    # Test that wrapping calculation works
    # Moving from row 5 with direction down should wrap to row 0
    wrapped_row = (5 + 1) % 6
    assert wrapped_row == 0
    
    # Test column wrapping
    wrapped_col = (4 + 1) % 6
    assert wrapped_col == 5


def test_click_direction_handles_toroidal_edges():
    """Click-to-move should treat opposite edges as adjacent on the toroidal board."""
    handler = InputHandler(None)

    assert handler.get_direction_to_cell(Position(0, 0), Position(5, 0)) == "up"
    assert handler.get_direction_to_cell(Position(5, 0), Position(0, 0)) == "down"
    assert handler.get_direction_to_cell(Position(0, 0), Position(0, 5)) == "left"
    assert handler.get_direction_to_cell(Position(0, 5), Position(0, 0)) == "right"


def test_damage_calculation(game_setup):
    """Test damage accumulation."""
    game = game_setup
    
    # Add damage
    game.damage[0].add_card(Card(CardRank.FIVE, CardSuit.HEARTS))
    assert game.get_damage_total(0) == 5
    
    # Add more damage
    game.damage[0].add_card(Card(CardRank.QUEEN, CardSuit.HEARTS))
    assert game.get_damage_total(0) == 16  # 5 + 11
    
    # Check defeat condition
    assert not game.is_defeated(0)
    
    # Add more to reach 25
    game.damage[0].add_card(Card(CardRank.KING, CardSuit.HEARTS))
    assert game.get_damage_total(0) == 28
    assert game.is_defeated(0)


def test_board_shift(game_setup):
    """Test row/column shifting."""
    game = game_setup
    
    # Get initial state of row 0
    initial_row = [cell.card for cell in game.board.get_row(0)]
    
    # Shift row 0 right
    game.board.move_row(0, 1)
    
    # Last card should wrap to beginning
    shifted_row = [cell.card for cell in game.board.get_row(0)]
    assert shifted_row[0] == initial_row[-1]
    assert shifted_row[1] == initial_row[0]


def test_player_positions(game_setup):
    """Test player placement and position tracking."""
    game = game_setup
    
    # Check initial positions
    assert game.board.get_player_position(0) == Position(5, 3)
    assert game.board.get_player_position(1) == Position(0, 2)
    
    # Move player
    game.board.place_player(0, Position(4, 3))
    assert game.board.get_player_position(0) == Position(4, 3)
    
    # Check player at position
    assert game.board.get_player_at(Position(4, 3)) == 0
    assert game.board.get_player_at(Position(5, 3)) is None


def test_legal_moves(game_setup):
    """Test legal movement calculation."""
    game = game_setup
    
    # Player 0 should have legal moves
    legal = game.get_legal_moves(0)
    assert len(legal) > 0
    assert all(d in ["up", "down", "left", "right"] for d in legal)


def test_wall_tiles_block_movement(game_setup):
    """Players should not be able to move onto wall tiles."""
    game = game_setup
    wall_suit = next(suit for suit, role in game.suit_roles.items() if role == SuitRole.WALLS)

    game.board.place_player(0, Position(2, 2))
    game.board.set_card(Position(2, 3), Card(CardRank.FOUR, wall_suit))

    assert "right" not in game.get_legal_moves(0)
    assert not game.apply_action(MoveAction(0, "right"))
    assert game.board.get_player_position(0) == Position(2, 2)


def test_pick_up_current_card_uses_move_and_removes_tile(game_setup):
    """Players may spend a traversing move to pick up the card beneath them if it is not a wall."""
    game = game_setup
    weapon_suit = next(suit for suit, role in game.suit_roles.items() if role == SuitRole.WEAPONS)
    current_pos = Position(2, 2)
    current_card = Card(CardRank.THREE, weapon_suit)
    hand_before = len(game.get_player_hand(0))

    game.board.place_player(0, current_pos)
    game.board.set_card(current_pos, current_card)
    game.current_player = 0
    game.phase = GamePhase.TRAVERSING

    assert game.can_pick_up_current_card(0)
    assert game.apply_action(PickupCurrentCardAction(0))
    assert current_card in game.get_player_hand(0)
    assert len(game.get_player_hand(0)) == hand_before + 1
    assert game.board.get_card(current_pos) is None


def test_current_tile_ballista_starts_launch_without_collecting(game_setup):
    """Using the current-tile action on a ballista should launch from it without removing the tile."""
    game = game_setup
    ballista_suit = next(suit for suit, role in game.suit_roles.items() if role == SuitRole.BALLISTA)
    current_pos = Position(2, 2)
    current_card = Card(CardRank.THREE, ballista_suit)
    hand_before = len(game.get_player_hand(0))

    game.board.place_player(0, current_pos)
    game.board.set_card(current_pos, current_card)
    game.current_player = 0
    game.phase = GamePhase.TRAVERSING

    assert game.can_pick_up_current_card(0)
    assert game.apply_action(PickupCurrentCardAction(0))
    assert game.has_pending_ballista()
    assert current_card not in game.get_player_hand(0)
    assert len(game.get_player_hand(0)) == hand_before
    assert game.board.get_card(current_pos) == current_card


def test_cannot_pick_up_current_wall_tile(game_setup):
    """Walls remain uncollectable even when standing on them."""
    game = game_setup
    wall_suit = next(suit for suit, role in game.suit_roles.items() if role == SuitRole.WALLS)
    current_pos = Position(2, 2)

    game.board.place_player(0, current_pos)
    game.board.set_card(current_pos, Card(CardRank.FOUR, wall_suit))
    game.current_player = 0
    game.phase = GamePhase.TRAVERSING

    assert not game.can_pick_up_current_card(0)
    assert not game.apply_action(PickupCurrentCardAction(0))


def test_hand_management(game_setup):
    """Test card hand management."""
    game = game_setup
    
    initial_hand = game.get_player_hand(0)
    assert len(initial_hand) == 5
    
    # Add card
    card = Card(CardRank.ACE, CardSuit.DIAMONDS)
    game.add_card_to_hand(0, card)
    assert len(game.get_player_hand(0)) == 6
    assert card in game.get_player_hand(0)


def test_labyrinth_excludes_ten_and_higher():
    """The labyrinth should only contain Ace through 9 cards."""
    labyrinth, p0_deck, p1_deck, jack_cards = setup_game_deck()

    assert all(card.rank.value <= CardRank.NINE.value for card in labyrinth)
    assert all(card.rank.value >= CardRank.TEN.value for card in p0_deck)
    assert all(card.rank.value >= CardRank.TEN.value for card in p1_deck)


def test_weapons_go_to_hand_and_become_combat_eligible(game_setup):
    """Weapon-role cards should stay in the normal hand and be usable for combat."""
    game = game_setup
    weapon_suit = next(suit for suit, role in game.suit_roles.items() if role == SuitRole.WEAPONS)
    weapon_card = Card(CardRank.NINE, weapon_suit)
    initial_hand_size = len(game.get_player_hand(0))

    game._apply_card_effect(0, weapon_card, SuitRole.WEAPONS)

    assert len(game.get_player_hand(0)) == initial_hand_size + 1
    assert weapon_card in game.get_player_hand(0)
    assert weapon_card in game.get_player_weapons(0)


def test_trap_adds_only_to_landing_players_damage(game_setup):
    """Trap cards should damage only the player who lands on them."""
    game = game_setup
    trap_suit = next(suit for suit, role in game.suit_roles.items() if role == SuitRole.TRAPS)
    trap_card = Card(CardRank.EIGHT, trap_suit)
    opponent_hand_before = list(game.get_player_hand(1))

    game._apply_card_effect(0, trap_card, SuitRole.TRAPS)

    assert trap_card in game.damage[0].cards
    assert game.damage[1].cards == []
    assert game.get_player_hand(1) == opponent_hand_before


def test_ballista_targets_clickable_tiles_until_wall(game_setup):
    """Ballista should allow clicking any tile along the path before the next wall."""
    game = game_setup
    wall_suit = next(suit for suit, role in game.suit_roles.items() if role == SuitRole.WALLS)

    game.board.place_player(0, Position(0, 0))
    game.board.set_card(Position(5, 0), None)
    game.board.set_card(Position(4, 0), None)
    game.board.set_card(Position(1, 0), Card(CardRank.TWO, wall_suit))
    game.board.set_card(Position(0, 5), Card(CardRank.THREE, wall_suit))
    game.board.set_card(Position(0, 1), Card(CardRank.FOUR, wall_suit))
    game.board.set_card(Position(3, 0), Card(CardRank.TWO, wall_suit))
    game._start_ballista(0)

    assert game.has_pending_ballista()
    assert game.get_pending_ballista_targets() == [Position(5, 0), Position(4, 0)]

    action = ResolveBallistaShotAction(0, 5, 0)
    assert game.apply_action(action)
    assert game.board.get_player_position(0) == Position(5, 0)


def test_ballista_landing_on_weapon_does_not_collect_it(game_setup):
    """Ballista landing should not auto-collect the destination weapon card."""
    game = game_setup
    ballista_suit = next(suit for suit, role in game.suit_roles.items() if role == SuitRole.BALLISTA)
    weapon_suit = next(suit for suit, role in game.suit_roles.items() if role == SuitRole.WEAPONS)
    destination = Position(0, 1)
    weapon_card = Card(CardRank.SEVEN, weapon_suit)
    hand_before = len(game.get_player_hand(0))

    game.board.place_player(0, Position(0, 0))
    game.board.set_card(Position(0, 0), Card(CardRank.THREE, ballista_suit))
    game.board.set_card(destination, weapon_card)
    game._start_ballista(0)

    assert game.apply_action(ResolveBallistaShotAction(0, destination.row, destination.col))
    assert weapon_card not in game.get_player_hand(0)
    assert len(game.get_player_hand(0)) == hand_before
    assert game.board.get_card(destination) == weapon_card


def test_ballista_landing_on_trap_does_not_add_damage(game_setup):
    """Ballista landing should not auto-apply trap damage."""
    game = game_setup
    ballista_suit = next(suit for suit, role in game.suit_roles.items() if role == SuitRole.BALLISTA)
    trap_suit = next(suit for suit, role in game.suit_roles.items() if role == SuitRole.TRAPS)
    destination = Position(0, 1)
    trap_card = Card(CardRank.SIX, trap_suit)

    game.board.place_player(0, Position(0, 0))
    game.board.set_card(Position(0, 0), Card(CardRank.THREE, ballista_suit))
    game.board.set_card(destination, trap_card)
    game._start_ballista(0)

    assert game.apply_action(ResolveBallistaShotAction(0, destination.row, destination.col))
    assert trap_card not in game.damage[0].cards
    assert game.board.get_card(destination) == trap_card


def test_ballista_landing_on_ballista_does_not_chain(game_setup):
    """Landing on a second ballista from a ballista should not immediately start another shot."""
    game = game_setup
    ballista_suit = next(suit for suit, role in game.suit_roles.items() if role == SuitRole.BALLISTA)
    first_destination = Position(0, 1)
    second_destination = Position(0, 2)

    game.board.place_player(0, Position(0, 0))
    game.board.set_card(first_destination, Card(CardRank.FOUR, ballista_suit))
    game.board.set_card(second_destination, Card(CardRank.FIVE, ballista_suit))
    game._start_ballista(0)

    assert game.apply_action(ResolveBallistaShotAction(0, first_destination.row, first_destination.col))
    assert not game.has_pending_ballista()
    assert game.board.get_player_position(0) == first_destination
    assert game.board.get_card(first_destination) == Card(CardRank.FOUR, ballista_suit)


def test_battle_is_ignored_when_neither_player_has_weapons(game_setup):
    """Same-tile contact should not trigger combat when nobody has weapons."""
    game = game_setup
    game.hands[0].cards.clear()
    game.hands[1].cards.clear()

    game._start_combat(0, 1)

    assert not game.has_pending_combat()


def test_combat_uses_chosen_weapon_suit_card_from_hand(game_setup):
    """Combat should use a chosen weapon-role hand card as damage."""
    game = game_setup
    weapon_suit = next(suit for suit, role in game.suit_roles.items() if role == SuitRole.WEAPONS)
    chosen_card = Card(CardRank.NINE, weapon_suit)
    game.hands[0].cards.clear()
    game.hands[1].cards.clear()
    game.add_card_to_hand(0, chosen_card)

    game._start_combat(0, 1)
    assert game.has_pending_combat()
    assert game.current_player == 0

    action = ChooseCombatCardAction(0, chosen_card)
    assert game.apply_action(action)
    assert chosen_card not in game.get_player_hand(0)
    assert chosen_card in game.damage[1].cards


def test_wraparound_move_into_weapon_holder_starts_combat(game_setup):
    """Wrapping onto the opponent's tile should still start combat if either player has a weapon."""
    game = game_setup
    weapon_suit = next(suit for suit, role in game.suit_roles.items() if role == SuitRole.WEAPONS)
    defender_weapon = Card(CardRank.SEVEN, weapon_suit)

    game.hands[0].cards.clear()
    game.hands[1].cards.clear()
    game.add_card_to_hand(1, defender_weapon)
    game.board.place_player(0, Position(0, 0))
    game.board.place_player(1, Position(5, 0))
    game.board.set_card(Position(5, 0), None)
    game.current_player = 0
    game.phase = GamePhase.TRAVERSING

    assert game.apply_action(MoveAction(0, "up"))
    assert game.has_pending_combat()
    assert game.pending_combat_players == [1]
    assert game.current_player == 1


def test_both_players_can_resolve_wraparound_combat_in_sequence(game_setup):
    """When both players have weapons after a wrap move, both should get a combat turn."""
    game = game_setup
    weapon_suit = next(suit for suit, role in game.suit_roles.items() if role == SuitRole.WEAPONS)
    attacker_weapon = Card(CardRank.NINE, weapon_suit)
    defender_weapon = Card(CardRank.SIX, weapon_suit)

    game.hands[0].cards.clear()
    game.hands[1].cards.clear()
    game.add_card_to_hand(0, attacker_weapon)
    game.add_card_to_hand(1, defender_weapon)
    game.board.place_player(0, Position(0, 0))
    game.board.place_player(1, Position(5, 0))
    game.board.set_card(Position(5, 0), None)
    game.current_player = 0
    game.phase = GamePhase.TRAVERSING

    assert game.apply_action(MoveAction(0, "up"))
    assert game.pending_combat_players == [0, 1]
    assert game.current_player == 0
    assert game.apply_action(ChooseCombatCardAction(0, attacker_weapon))
    assert game.current_player == 1
    assert game.apply_action(ChooseCombatCardAction(1, defender_weapon))
    assert attacker_weapon in game.damage[1].cards
    assert defender_weapon in game.damage[0].cards
    assert not game.has_pending_combat()


def test_initial_deal_weapon_suit_high_card_can_be_used_in_combat(game_setup):
    """Drafted high-rank cards keep their suit and can fight if their suit is Weapons."""
    game = game_setup
    weapon_suit = next(suit for suit, role in game.suit_roles.items() if role == SuitRole.WEAPONS)
    drafted_weapon = Card(CardRank.KING, weapon_suit)
    game.hands[0].cards.clear()
    game.hands[1].cards.clear()
    game.add_card_to_hand(0, drafted_weapon)

    game._start_combat(0, 1)

    assert game.has_pending_combat()
    assert game.apply_action(ChooseCombatCardAction(0, drafted_weapon))
    assert drafted_weapon in game.damage[1].cards


def test_restructure_swaps_two_selected_suit_roles(game_setup):
    """Restructure should swap only two selected suits and their assigned abilities."""
    game = game_setup
    game.setup_suit_roles([CardSuit.HEARTS, CardSuit.DIAMONDS, CardSuit.CLUBS, CardSuit.SPADES])
    original_board = [
        game.board.get_card(Position(row, col))
        for row in range(6)
        for col in range(6)
    ]
    game.phase = GamePhase.APPEASING
    game.current_request_winner = 0
    game.pending_request_players = [0]
    game.current_player = 0

    assert game.choose_request(0, "restructure")
    assert game.get_pending_request_type() == "restructure"
    assert game.apply_action(SelectRestructureSuitAction(0, CardSuit.HEARTS))
    assert game.apply_action(SelectRestructureSuitAction(0, CardSuit.SPADES))

    assert game.suit_roles[CardSuit.HEARTS] == SuitRole.WEAPONS
    assert game.suit_roles[CardSuit.SPADES] == SuitRole.WALLS
    assert [
        game.board.get_card(Position(row, col))
        for row in range(6)
        for col in range(6)
    ] == original_board


def test_both_players_choose_requests_unless_ignore_us(game_setup):
    """Appeasing should collect two request choices unless Ignore Us is picked first."""
    game = game_setup
    game.phase = GamePhase.APPEASING
    game.current_request_winner = 0
    game.pending_request_players = [0, 1]
    game.current_player = 0
    game.traversing_resume_player = 1

    assert game.apply_action(ChooseRequestAction(
        0,
        RequestType.RESTRUCTURE,
        {"suits": [game.jack_order[0], game.jack_order[1]]},
    ))
    assert game.phase == GamePhase.APPEASING
    assert game.current_player == 1
    assert game.pending_request_players == [1]

    assert game.apply_action(ChooseRequestAction(1, RequestType.PLANE_SHIFT))
    assert game.apply_action(SelectPlaneShiftDirectionAction(1, "left"))
    assert game.apply_action(ResolvePlaneShiftAction(1, 0))
    assert game.phase == GamePhase.TRAVERSING
    assert game.pending_request_players == []
    assert game.current_player == 1


def test_second_requester_cannot_choose_same_request_type(game_setup):
    """Once the first request resolves, the second chooser must pick a different request."""
    game = game_setup
    game.phase = GamePhase.APPEASING
    game.current_request_winner = 0
    game.pending_request_players = [0, 1]
    game.current_player = 0

    assert game.apply_action(ChooseRequestAction(
        0,
        RequestType.RESTRUCTURE,
        {"suits": [game.jack_order[0], game.jack_order[1]]},
    ))
    assert game.pending_request_players == [1]
    assert "restructure" in game.get_chosen_request_types()
    assert not game.can_select_request_type(1, "restructure")
    assert "restructure" not in game.get_available_request_types(1)
    assert not game.choose_request(1, "restructure")


def test_second_requester_cannot_choose_ignore_us(game_setup):
    """Only the initial request winner should be allowed to choose Ignore Us."""
    game = game_setup
    game.phase = GamePhase.APPEASING
    game.current_request_winner = 0
    game.pending_request_players = [1]
    game.current_player = 1

    assert not game.can_select_request_type(1, "ignore_us")
    assert "ignore_us" not in game.get_available_request_types(1)
    assert not game.choose_request(1, "ignore_us")


def test_ignore_us_skips_second_request_only(game_setup):
    """Ignore Us should end request selection without skipping traversing turns."""
    game = game_setup
    game.phase = GamePhase.APPEASING
    game.current_request_winner = 0
    game.pending_request_players = [0, 1]
    game.current_player = 0

    assert game.choose_request(0, "ignore_us")
    assert game.phase == GamePhase.TRAVERSING
    assert game.pending_request_players == []
    assert game.forced_pass_turns[1] == 0


def test_pending_request_selection_can_be_cancelled(game_setup):
    """A chooser should be able to back out of an unfinished request and pick again."""
    game = game_setup
    own_card = Card(CardRank.TEN, CardSuit.HEARTS)
    opponent_card = Card(CardRank.QUEEN, CardSuit.SPADES)
    game.damage[0].add_card(own_card)
    game.damage[1].add_card(opponent_card)
    game.phase = GamePhase.APPEASING
    game.current_request_winner = 0
    game.pending_request_players = [0, 1]
    game.current_player = 0

    assert game.choose_request(0, "steal_life")
    assert game.can_cancel_pending_request_selection(0)
    assert game.apply_action(SelectDamageCardAction(0, 0, own_card))
    assert game.apply_action(CancelRequestSelectionAction(0))
    assert not game.has_pending_request_resolution()
    assert game.pending_request_players == [0, 1]
    assert game.current_player == 0
    assert game.request_history == []
    assert game.choose_request(0, "plane_shift")


def test_multiplayer_back_submits_cancel_request_action(game_setup):
    """Back from a request popup should update the room server, not just local UI state."""
    game = game_setup
    own_card = Card(CardRank.TEN, CardSuit.HEARTS)
    opponent_card = Card(CardRank.QUEEN, CardSuit.SPADES)
    game.damage[0].add_card(own_card)
    game.damage[1].add_card(opponent_card)
    game.phase = GamePhase.APPEASING
    game.current_request_winner = 0
    game.pending_request_players = [0, 1]
    game.current_player = 0
    assert game.choose_request(0, "steal_life")

    class Session:
        player_id = 0
        room_code = "1000"
        players = {0: "Host", 1: "Guest"}
        ready = True
        last_error = None

        def __init__(self, active_game):
            self.game = active_game
            self.submitted = []

        def submit_action(self, action):
            self.submitted.append(action)
            return self.game.apply_action(action)

        def update(self, time_delta: float) -> bool:
            return False

    window = SmokeWindow(width=1200, height=900)
    session = Session(game)
    window.multiplayer_session = session
    screen = GameScreen(window, game)

    assert screen._cancel_pending_request_resolution()
    assert isinstance(session.submitted[-1], CancelRequestSelectionAction)
    assert not game.has_pending_request_resolution()
    assert game.pending_request_players == [0, 1]
    assert game.current_player == 0


def test_multiplayer_appeasing_card_selection_uses_local_player_hand(game_setup):
    """During simultaneous Appeasing selection, each client should play from their own hand."""
    game = game_setup
    game.phase = GamePhase.APPEASING
    game.current_player = 0
    game.current_request_winner = None
    game.phase_started_cards = []

    class Session:
        player_id = 1
        room_code = "1000"
        players = {0: "Host", 1: "Guest"}
        ready = True
        last_error = None

        def __init__(self, active_game):
            self.game = active_game
            self.submitted = []

        def submit_action(self, action):
            self.submitted.append(action)
            return self.game.apply_action(action)

        def update(self, time_delta: float) -> bool:
            return False

    window = SmokeWindow(width=1200, height=900)
    session = Session(game)
    window.multiplayer_session = session
    screen = GameScreen(window, game)

    assert not screen._is_multiplayer_input_locked()
    assert screen._get_hand_owner_player_id() == 1
    hand_rects = screen._get_hand_card_rects()
    assert hand_rects
    first_guest_card = game.get_player_hand(1)[hand_rects[0][0]]

    assert screen._handle_hand_card_click(hand_rects[0][1].center)
    assert isinstance(session.submitted[-1], PlayCardAction)
    assert session.submitted[-1].player_id == 1
    assert (1, first_guest_card) in game.phase_started_cards


def test_appeasing_stronger_color_beats_higher_rank(game_setup):
    """A lower card in a stronger trump suit should beat a higher card in a weaker suit."""
    game = game_setup
    game.setup_suit_roles([CardSuit.HEARTS, CardSuit.DIAMONDS, CardSuit.CLUBS, CardSuit.SPADES])
    game.phase_started_cards = [
        (0, Card(CardRank.TWO, CardSuit.HEARTS)),
        (1, Card(CardRank.KING, CardSuit.SPADES)),
    ]
    game.current_player = 1

    game._resolve_appeasing_phase()

    assert game.current_request_winner == 0


def test_appeasing_cards_can_be_submitted_in_either_order(game_setup):
    """Appeasing Pan card selection should not be gated by current_player turns."""
    game = game_setup
    game.phase = GamePhase.APPEASING
    game.current_player = 0
    game.current_request_winner = None
    game.phase_started_cards = []
    card0 = game.get_player_hand(0)[0]
    card1 = game.get_player_hand(1)[0]

    assert game.apply_action(PlayCardAction(1, card1))
    assert game.has_player_played_appeasing_card(1)
    assert not game.has_player_played_appeasing_card(0)
    assert game.current_request_winner is None

    assert game.apply_action(PlayCardAction(0, card0))
    assert game.current_request_winner in {0, 1}
    assert len(game.phase_started_cards) == 2


def test_appeasing_hierarchy_runs_walls_to_weapons(game_setup):
    """Phase 2 trump order should be Walls > Traps > Ballista > Weapons."""
    game = game_setup
    game.setup_suit_roles([CardSuit.HEARTS, CardSuit.DIAMONDS, CardSuit.CLUBS, CardSuit.SPADES])

    assert game.get_appeasing_hierarchy() == [
        CardSuit.HEARTS,
        CardSuit.DIAMONDS,
        CardSuit.CLUBS,
        CardSuit.SPADES,
    ]


def test_appeasing_same_suit_uses_rank(game_setup):
    """Cards of the same suit should be decided by their rank."""
    game = game_setup
    game.setup_suit_roles([CardSuit.HEARTS, CardSuit.DIAMONDS, CardSuit.CLUBS, CardSuit.SPADES])
    game.phase_started_cards = [
        (0, Card(CardRank.FIVE, CardSuit.SPADES)),
        (1, Card(CardRank.KING, CardSuit.SPADES)),
    ]
    game.current_player = 1

    game._resolve_appeasing_phase()

    assert game.current_request_winner == 1


def test_traversing_skips_appeasing_when_a_player_has_no_hand_cards(game_setup):
    """If either player has no Phase 2 hand cards left, the game should loop back to Traversing."""
    game = game_setup
    game.hands[1].cards.clear()
    game.phase = GamePhase.TRAVERSING
    game.current_player = 0
    game.movement_turn = 5

    game._finish_traversing_move()

    assert game.phase == GamePhase.TRAVERSING
    assert game.movement_turn == 0
    assert game.current_player == 0
    assert game.current_request_winner is None


def test_steal_life_swaps_selected_damage_cards(game_setup):
    """Steal Life should swap one chosen damage card from each player."""
    game = game_setup
    own_card = Card(CardRank.TEN, CardSuit.HEARTS)
    opponent_card = Card(CardRank.QUEEN, CardSuit.SPADES)
    game.damage[0].add_card(own_card)
    game.damage[1].add_card(opponent_card)
    game.phase = GamePhase.APPEASING
    game.current_request_winner = 0
    game.pending_request_players = [0]
    game.current_player = 0
    game.traversing_resume_player = 1

    assert game.choose_request(0, "steal_life")
    assert game.has_pending_request_resolution()
    assert game.apply_action(SelectDamageCardAction(0, 0, own_card))
    assert game.get_pending_steal_life_card() == own_card
    assert game.apply_action(SelectDamageCardAction(0, 1, opponent_card))
    assert opponent_card in game.damage[0].cards
    assert own_card in game.damage[1].cards
    assert game.phase == GamePhase.TRAVERSING
    assert not game.has_pending_request_resolution()


def test_steal_life_allows_changing_own_card_before_enemy_pick(game_setup):
    """Steal Life should let the chooser change their own selected card before locking the swap."""
    game = game_setup
    first_own = Card(CardRank.TEN, CardSuit.HEARTS)
    second_own = Card(CardRank.NINE, CardSuit.DIAMONDS)
    opponent_card = Card(CardRank.QUEEN, CardSuit.SPADES)
    game.damage[0].add_card(first_own)
    game.damage[0].add_card(second_own)
    game.damage[1].add_card(opponent_card)
    game.phase = GamePhase.APPEASING
    game.current_request_winner = 0
    game.pending_request_players = [0]
    game.current_player = 0
    game.traversing_resume_player = 1

    assert game.choose_request(0, "steal_life")
    assert game.apply_action(SelectDamageCardAction(0, 0, first_own))
    assert game.get_pending_steal_life_card() == first_own
    assert game.apply_action(SelectDamageCardAction(0, 0, second_own))
    assert game.get_pending_steal_life_card() == second_own
    assert game.apply_action(SelectDamageCardAction(0, 1, opponent_card))

    assert first_own in game.damage[0].cards
    assert opponent_card in game.damage[0].cards
    assert second_own in game.damage[1].cards


def test_plane_shift_shifts_selected_row_and_moves_players(game_setup):
    """Plane Shift should shift the chosen row and carry players on it."""
    game = game_setup
    target_row = 5
    starting_cards = [game.board.get_card(Position(target_row, col)) for col in range(6)]
    game.board.place_player(0, Position(target_row, 3))
    game.phase = GamePhase.APPEASING
    game.current_request_winner = 0
    game.pending_request_players = [0]
    game.current_player = 0
    game.traversing_resume_player = 1

    assert game.choose_request(0, "plane_shift")
    assert game.has_pending_request_resolution()
    assert game.apply_action(SelectPlaneShiftDirectionAction(0, "right"))
    assert game.apply_action(ResolvePlaneShiftAction(0, target_row))

    shifted_cards = [game.board.get_card(Position(target_row, col)) for col in range(6)]
    assert shifted_cards[0] == starting_cards[-1]
    assert shifted_cards[1] == starting_cards[0]
    assert game.board.get_player_position(0) == Position(target_row, 4)
    assert game.phase == GamePhase.TRAVERSING


def test_appeasing_played_cards_are_placed_in_holes_by_loser(game_setup):
    """After requests, the loser should place the played cards into labyrinth holes."""
    game = game_setup
    card_a = Card(CardRank.TEN, CardSuit.HEARTS)
    card_b = Card(CardRank.QUEEN, CardSuit.SPADES)
    first_hole = Position(2, 2)
    second_hole = Position(3, 3)
    game.hands[1].cards.clear()
    game.board.set_card(first_hole, None)
    game.board.set_card(second_hole, None)
    game.phase = GamePhase.APPEASING
    game.phase_started_cards = [(0, card_a), (1, card_b)]
    game.current_request_winner = 0
    game.current_request_loser = 1
    game.pending_request_players = [0]
    game.current_player = 0

    assert game.choose_request(0, "ignore_us")
    assert game.has_pending_card_placement()
    assert game.current_player == 1
    assert game.apply_action(PlaceCardsAction(1, [first_hole]))
    assert game.board.get_card(first_hole) == card_a
    assert game.has_pending_card_placement()
    assert game.apply_action(PlaceCardsAction(1, [second_hole]))
    assert game.board.get_card(second_hole) == card_b
    assert game.phase == GamePhase.TRAVERSING
    assert card_a not in game.get_player_hand(1)
    assert card_b not in game.get_player_hand(1)


def test_appeasing_cards_can_place_selected_card_out_of_order(game_setup):
    """The placer should be able to choose which pending played card goes into a hole first."""
    game = game_setup
    card_a = Card(CardRank.TEN, CardSuit.HEARTS)
    card_b = Card(CardRank.QUEEN, CardSuit.SPADES)
    first_hole = Position(2, 2)
    second_hole = Position(3, 3)

    game.board.set_card(first_hole, None)
    game.board.set_card(second_hole, None)
    game.phase = GamePhase.APPEASING
    game.phase_started_cards = [(0, card_a), (1, card_b)]
    game.current_request_winner = 0
    game.current_request_loser = 1
    game.pending_request_players = []
    game.pending_placement_player = 1
    game.pending_placement_cards = [card_a, card_b]
    game.current_player = 1

    assert game.apply_action(PlaceCardsAction(1, [first_hole], [1]))
    assert game.board.get_card(first_hole) == card_b
    assert game.get_pending_placement_cards() == [card_a]
    assert game.apply_action(PlaceCardsAction(1, [second_hole], [0]))
    assert game.board.get_card(second_hole) == card_a


def test_appeasing_cards_return_to_loser_when_no_holes_exist(game_setup):
    """If there are no gaps, the losing player keeps the played phase cards."""
    game = game_setup
    card_a = Card(CardRank.TEN, CardSuit.HEARTS)
    card_b = Card(CardRank.QUEEN, CardSuit.SPADES)
    game.hands[1].cards.clear()
    game.phase = GamePhase.APPEASING
    game.phase_started_cards = [(0, card_a), (1, card_b)]
    game.current_request_winner = 0
    game.current_request_loser = 1
    game.pending_request_players = [0]
    game.current_player = 0

    assert game.choose_request(0, "ignore_us")
    assert game.phase == GamePhase.TRAVERSING
    assert not game.has_pending_card_placement()
    assert card_a in game.get_player_hand(1)
    assert card_b in game.get_player_hand(1)
    assert game.consume_appeasing_return_notice() == (
        "No open holes remained, so 2 played cards returned to P2's hand."
    )
    assert game.consume_appeasing_return_notice() is None


def test_hole_positions_exclude_tiles_currently_occupied_by_players(game_setup):
    """Players standing in holes should block those holes from post-appeasing placement."""
    game = game_setup
    occupied_hole = Position(2, 2)
    open_hole = Position(3, 3)

    game.board.set_card(occupied_hole, None)
    game.board.set_card(open_hole, None)
    game.board.place_player(0, occupied_hole)

    holes = game.get_hole_positions()

    assert occupied_hole not in holes
    assert open_hole in holes


def test_player_tokens_only_offset_when_sharing_a_tile():
    """Player markers should be centered normally and split only on shared tiles."""
    assert BoardRenderer.get_player_x_offset(0, sharing_tile=False) == 0
    assert BoardRenderer.get_player_x_offset(1, sharing_tile=False) == 0
    assert BoardRenderer.get_player_x_offset(0, sharing_tile=True) < 0
    assert BoardRenderer.get_player_x_offset(1, sharing_tile=True) > 0


def test_player_name_label_font_shrinks_for_long_names():
    """Long custom player names should fit inside marker label chips."""
    renderer = BoardRenderer()
    renderer.update_layout(1200, 900)
    long_name = "AlexandertheChampion"
    max_width = int(renderer.CELL_SIZE * 1.75)

    font = renderer._get_fitted_player_label_font(long_name, max_width)

    assert font.size(long_name)[0] <= max_width


def test_board_renderer_uses_square_grid_without_labyrinth_overlay():
    """The board renderer should stay on the classic square grid when the labyrinth frame is disabled."""
    renderer = BoardRenderer()
    assert renderer._labyrinth_frame_base is None
    assert renderer._labyrinth_frame_grid_rect is None

    renderer.update_layout(1200, 900)
    top_left = renderer.get_cell_rect(Position(0, 0))
    right_neighbor = renderer.get_cell_rect(Position(0, 1))
    below_neighbor = renderer.get_cell_rect(Position(1, 0))

    assert top_left.width == renderer.CELL_SIZE - 4
    assert top_left.height == renderer.CELL_SIZE - 4
    assert right_neighbor.x - top_left.x == renderer.CELL_SIZE
    assert below_neighbor.y - top_left.y == renderer.CELL_SIZE


def test_game_window_uses_browser_viewport_size_when_available(monkeypatch):
    """Web builds should size the game surface to the browser viewport."""
    import platform

    window = GameWindow.__new__(GameWindow)
    window.is_web = True

    monkeypatch.setattr(platform, "window", type("Window", (), {"innerWidth": 1510, "innerHeight": 812})(), raising=False)

    assert window._get_initial_window_size() == (1510, 812)


def test_game_window_falls_back_to_base_web_framebuffer_size(monkeypatch):
    """Web builds still have a stable fallback before the browser reports a viewport."""
    window = GameWindow.__new__(GameWindow)
    window.is_web = True

    monkeypatch.setattr(pygame.display, "Info", lambda: type("Info", (), {"current_w": 0, "current_h": 0})())

    assert window._get_initial_window_size() == (
        GameWindow.BASE_WINDOW_WIDTH,
        GameWindow.BASE_WINDOW_HEIGHT,
    )


def test_game_window_resizes_web_framebuffer(monkeypatch):
    """Browser resize events should update the game's internal layout size."""
    window = GameWindow.__new__(GameWindow)
    window.is_web = True
    window.fullscreen = False
    window.minimum_resize_width = 1
    window.minimum_resize_height = 1
    window.WINDOW_WIDTH = 1200
    window.WINDOW_HEIGHT = 900

    class UIManager:
        resolution = None

        def set_window_resolution(self, size):
            self.resolution = size

    window.ui_manager = UIManager()
    monkeypatch.setattr(window, "_get_browser_viewport_size", lambda: None)
    monkeypatch.setattr(pygame.display, "set_mode", lambda size, flags=0: pygame.Surface(size))

    assert window.resize(1600, 1100) is True
    assert window.WINDOW_WIDTH == 1600
    assert window.WINDOW_HEIGHT == 1100
    assert window.ui_manager.resolution == (1600, 1100)


def test_coin_flip_faces_share_one_centered_footprint():
    """P1 and P2 coin faces should scale to the same centered on-screen footprint."""
    window = SmokeWindow(width=1200, height=900)
    screen = CoinFlipScreen(window)

    p1_face = screen._get_scaled_coin_art(0, 240)
    p2_face = screen._get_scaled_coin_art(1, 240)

    assert p1_face is not None
    assert p2_face is not None
    assert p1_face.get_size() == (240, 240)
    assert p2_face.get_size() == (240, 240)

    p1_bounds = p1_face.get_bounding_rect(min_alpha=12)
    p2_bounds = p2_face.get_bounding_rect(min_alpha=12)
    assert abs(p1_bounds.centerx - p2_bounds.centerx) <= 1
    assert abs(p1_bounds.centery - p2_bounds.centery) <= 1
    assert abs(p1_bounds.width - p2_bounds.width) <= 2
    assert abs(p1_bounds.height - p2_bounds.height) <= 2


def test_settings_tutorial_reset_smoke():
    """Settings reset should only reset the tip cycle, not force tips back on."""
    window = SmokeWindow()
    screen = SettingsScreen(window)
    window.tutorial_enabled = False

    class GameplayStub:
        reset_called = False

        def reset_tutorial_cycle(self):
            self.reset_called = True

    gameplay_stub = GameplayStub()
    window.game_screen_ref = gameplay_stub

    event = pygame.event.Event(
        pygame_gui.UI_BUTTON_PRESSED,
        {"ui_element": screen.tutorial_reset_button},
    )

    assert screen.handle_events(event) is True
    assert window.tutorial_enabled is False
    assert window.reset_calls == 1
    assert gameplay_stub.reset_called is True


def test_settings_tutorial_toggle_turns_tips_on_and_resets_cycle():
    """Turning tutorial tips on from Settings should opt in and reset the cycle."""
    window = SmokeWindow()
    screen = SettingsScreen(window)

    class GameplayStub:
        reset_called = False

        def reset_tutorial_cycle(self):
            self.reset_called = True

    gameplay_stub = GameplayStub()
    window.game_screen_ref = gameplay_stub

    event = pygame.event.Event(
        pygame_gui.UI_BUTTON_PRESSED,
        {"ui_element": screen.tutorial_button},
    )

    assert screen.handle_events(event) is True
    assert window.tutorial_enabled is True
    assert window.reset_calls == 1
    assert gameplay_stub.reset_called is True


def test_draft_tutorial_panel_avoids_card_grid_smoke():
    """Draft tutorial text should not cover the highlighted draft-card grid."""
    window = SmokeWindow(width=1200, height=900)
    window.tutorial_enabled = True
    screen = DraftScreen(window)
    draft_cards = [
        Card(rank, suit)
        for rank in (CardRank.TEN, CardRank.QUEEN, CardRank.KING)
        for suit in (CardSuit.HEARTS, CardSuit.DIAMONDS, CardSuit.CLUBS, CardSuit.SPADES)
    ]
    screen.start_draft(draft_cards, starting_player=0)

    surface = pygame.Surface((window.WINDOW_WIDTH, window.WINDOW_HEIGHT))
    screen.render(surface)

    grid_rect = screen._get_draft_grid_rect()
    assert screen.draft_tutorial_panel_rect is not None
    assert screen.tutorial_toggle_rect is not None
    assert not screen.draft_tutorial_panel_rect.colliderect(grid_rect)
    assert not screen.tutorial_toggle_rect.colliderect(grid_rect)


def test_draft_grid_prefers_two_rows_of_six_on_wide_short_viewports():
    """A wide browser viewport should keep the draft pool as a 2x6 grid."""
    window = SmokeWindow(width=1600, height=620)
    screen = DraftScreen(window)

    rows = {rect.y for rect in screen.card_rects}
    columns = {rect.x for rect in screen.card_rects}

    assert len(rows) == 2
    assert len(columns) == 6


def test_draft_grid_falls_back_when_six_columns_cannot_fit():
    """Narrow screens should still use the compact 3x4 draft layout."""
    window = SmokeWindow(width=520, height=700)
    screen = DraftScreen(window)

    rows = {rect.y for rect in screen.card_rects}
    columns = {rect.x for rect in screen.card_rects}

    assert len(rows) == 4
    assert len(columns) == 3


def test_omen_reveal_cards_stay_one_row_on_compact_viewports():
    """The four Omen cards should render as a 4x1 grid even in compact layouts."""
    window = SmokeWindow(width=520, height=700)
    screen = JackRevealScreen(window)
    screen.start_reveal(
        [],
        jack_order=[CardSuit.HEARTS, CardSuit.DIAMONDS, CardSuit.CLUBS, CardSuit.SPADES],
    )
    screen.finished = True

    rendered_rects = []

    def collect_tarot_card(surface, rect, role_index):
        rendered_rects.append(rect.copy())

    screen._render_reveal_tarot_card = collect_tarot_card
    surface = pygame.Surface((window.WINDOW_WIDTH, window.WINDOW_HEIGHT))
    screen.render(surface)

    rows = {rect.y for rect in rendered_rects}
    columns = {rect.x for rect in rendered_rects}

    assert len(rendered_rects) == 4
    assert len(rows) == 1
    assert len(columns) == 4
    assert all(rect.height > rect.width for rect in rendered_rects)
    assert rendered_rects[0].left >= 0
    assert rendered_rects[-1].right <= window.WINDOW_WIDTH


def test_compact_hand_card_click_plays_directly(game_setup):
    """Compact hand cards should play directly without the retired Inspect popup."""
    window = SmokeWindow(width=560, height=660)
    game = game_setup
    game.current_player = 0
    game.phase = GamePhase.APPEASING
    game.current_request_winner = None
    screen = GameScreen(window, game)

    hand_rects = screen._get_hand_card_rects()
    assert hand_rects
    first_card = game.get_player_hand(0)[hand_rects[0][0]]
    assert screen._handle_hand_card_click(hand_rects[0][1].center)
    assert screen.inspected_hand_card_index is None
    assert not screen._is_hand_inspect_popup_active()
    assert (0, first_card) in game.phase_started_cards

    surface = pygame.Surface((window.WINDOW_WIDTH, window.WINDOW_HEIGHT))
    screen.render(surface)
    assert screen.hand_card_rects


@pytest.mark.parametrize("width,height", [(560, 660), (900, 700), (1200, 900)])
def test_player_hand_stays_one_row_when_many_cards(game_setup, width, height):
    """The active hand should shrink to one row instead of wrapping into two rows."""
    window = SmokeWindow(width=width, height=height)
    game = game_setup
    game.current_player = 0
    game.phase = GamePhase.APPEASING
    game.hands[0].cards.clear()
    ranks = [CardRank.ACE, CardRank.TWO, CardRank.THREE, CardRank.FOUR, CardRank.FIVE]
    suits = [CardSuit.HEARTS, CardSuit.DIAMONDS, CardSuit.CLUBS, CardSuit.SPADES]
    for index in range(10):
        game.add_card_to_hand(0, Card(ranks[index % len(ranks)], suits[index % len(suits)]))
    screen = GameScreen(window, game)

    hand_rects = [rect for _, rect in screen._get_hand_card_rects()]
    rows = {rect.y for rect in hand_rects}

    assert len(hand_rects) == 10
    assert len(rows) == 1
    assert hand_rects[0].left >= 0
    assert hand_rects[-1].right <= window.WINDOW_WIDTH


@pytest.mark.parametrize("width,height", [(560, 660), (900, 700), (1200, 900)])
def test_health_chips_leave_room_for_phase_ribbon_on_all_screen_sizes(game_setup, width, height):
    """Health buttons should sit on the left without covering the phase ribbon."""
    window = SmokeWindow(width=width, height=height)
    game = game_setup
    game.phase = GamePhase.TRAVERSING
    screen = GameScreen(window, game)

    health_rects = screen._get_damage_summary_rects()
    banner_rect = screen._get_phase_banner_box()
    legend_rect = screen._get_suit_role_legend_panel_rect()
    board_rect = screen.renderer.get_board_rect()

    assert health_rects[0].x == health_rects[1].x
    assert health_rects[1].top > health_rects[0].bottom
    assert banner_rect is not None
    assert legend_rect is not None
    assert banner_rect.width == int(board_rect.width * 0.75)
    assert legend_rect.left >= board_rect.right
    assert not health_rects[0].colliderect(banner_rect)
    assert not health_rects[1].colliderect(banner_rect)
    assert not legend_rect.colliderect(banner_rect)


def test_suit_role_legend_is_right_side_single_column_strength_order(game_setup):
    """The Omen legend should read highest-to-lowest in one right-side column."""
    window = SmokeWindow(width=1200, height=900)
    game = game_setup
    game.phase = GamePhase.TRAVERSING
    screen = GameScreen(window, game)

    label_calls = []

    def collect_label(surface, text, rect, preferred_size, minimum_size, **kwargs):
        label_calls.append((text, rect.copy()))

    screen._render_wood_legend_label = collect_label
    surface = pygame.Surface((window.WINDOW_WIDTH, window.WINDOW_HEIGHT))
    screen._render_suit_role_legend(surface)

    expected_labels = [
        screen._get_suit_role_label(game.suit_roles.get(suit))
        for suit in game.get_appeasing_hierarchy()
    ]
    rendered_labels = [text for text, _ in label_calls]
    label_rects = [rect for _, rect in label_calls]

    assert rendered_labels == expected_labels
    assert len({rect.x for rect in label_rects}) == 1
    assert len({rect.y for rect in label_rects}) == 4
    assert label_rects == sorted(label_rects, key=lambda rect: rect.y)


def test_suit_role_legend_shows_strength_arrow_only_during_appeasing(game_setup):
    """Appeasing Pan should add a strongest-to-weakest guide to the Omen legend."""
    window = SmokeWindow(width=1200, height=900)
    game = game_setup
    screen = GameScreen(window, game)
    surface = pygame.Surface((window.WINDOW_WIDTH, window.WINDOW_HEIGHT))
    guide_labels = []
    arrow_rows = []

    def collect_strength_label(surface, text, rect, preferred_size, minimum_size):
        guide_labels.append((text, rect.copy()))

    def collect_strength_arrow(surface, panel_rect, row_rects):
        arrow_rows.append([rect.copy() for rect in row_rects])

    screen._render_legend_strength_label = collect_strength_label
    screen._render_legend_strength_arrow = collect_strength_arrow

    game.phase = GamePhase.TRAVERSING
    screen._render_suit_role_legend(surface)
    assert guide_labels == []
    assert arrow_rows == []

    game.phase = GamePhase.APPEASING
    screen._render_suit_role_legend(surface)
    assert [text for text, _ in guide_labels] == ["Strongest", "Weakest"]
    assert len(arrow_rows) == 1
    assert len(arrow_rows[0]) == 4
    assert arrow_rows[0][0].centery < arrow_rows[0][-1].centery


def test_frame_rate_overlay_toggles_with_f_and_sits_right_side(game_setup):
    """The gameplay FPS popup should be toggled by F and anchored on the right side."""
    window = SmokeWindow(width=1200, height=900)
    game = game_setup
    screen = GameScreen(window, game)

    assert not screen.frame_rate_overlay_visible
    assert screen.handle_events(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_f))
    assert screen.frame_rate_overlay_visible

    rect = screen._get_frame_rate_overlay_rect()
    assert rect.right <= window.WINDOW_WIDTH - screen.scale(18, 12)
    assert rect.left > window.WINDOW_WIDTH // 2
    assert abs(rect.centery - window.WINDOW_HEIGHT // 3) <= screen.scale_y(3, 2)

    labels = [label for label, _ in screen._get_frame_rate_lines()]
    assert {"FPS", "Frame", "Work", "Sleep", "Budget", "Headroom", "Over", "Speed"} <= set(labels)

    assert screen.handle_events(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_f))
    assert not screen.frame_rate_overlay_visible


@pytest.mark.parametrize("width,height", [(560, 660), (1200, 900)])
def test_request_side_buttons_sit_under_right_legend(game_setup, width, height):
    """Back and Return to Requests should be anchored below the right-side Omen legend."""
    window = SmokeWindow(width=width, height=height)
    game = game_setup
    game.phase = GamePhase.APPEASING
    screen = GameScreen(window, game)

    legend_rect = screen._get_suit_role_legend_panel_rect()
    return_rect = screen._get_request_labyrinth_return_rect()
    back_rect = screen._get_pending_request_back_button_rect()

    assert legend_rect is not None
    for rect in (return_rect, back_rect):
        assert rect.top >= legend_rect.bottom
        assert rect.colliderect(
            pygame.Rect(legend_rect.x, rect.y, legend_rect.width, rect.height)
        )
        assert rect.right <= window.WINDOW_WIDTH


def test_player_markers_are_larger_than_legacy_buttons():
    """Player portrait markers should be large enough to read as board buttons."""
    renderer = BoardRenderer()

    assert renderer._get_player_marker_radius(False) >= 22
    assert renderer._get_player_marker_radius(True) >= 19


@pytest.mark.parametrize("width,height", [(560, 660), (900, 700), (1200, 900)])
def test_pending_placement_cards_are_left_of_board_on_all_screen_sizes(game_setup, width, height):
    """Post-Appeasing played-card placement should be staged on the left side."""
    window = SmokeWindow(width=width, height=height)
    game = game_setup
    game.current_player = 0
    game.pending_placement_player = 0
    game.pending_placement_cards = [
        Card(CardRank.TEN, CardSuit.HEARTS),
        Card(CardRank.QUEEN, CardSuit.SPADES),
    ]
    screen = GameScreen(window, game)

    board_rect = screen.renderer.get_board_rect()
    placement_rects = [rect for _, rect in screen._get_pending_placement_card_rects()]

    assert placement_rects
    assert all(rect.right <= board_rect.left for rect in placement_rects)
    assert len({rect.x for rect in placement_rects}) == 1


def test_game_tutorial_panel_avoids_board_smoke(game_setup):
    """Gameplay tutorial text should not cover the highlighted board area."""
    window = SmokeWindow(width=900, height=700)
    window.tutorial_enabled = True
    game = game_setup
    game.phase = GamePhase.TRAVERSING
    game.current_player = 0
    screen = GameScreen(window, game)

    surface = pygame.Surface((window.WINDOW_WIDTH, window.WINDOW_HEIGHT))
    screen.render(surface)

    assert screen.tutorial_panel_rect is not None
    assert not screen.tutorial_panel_rect.colliderect(screen.renderer.get_board_rect())


def test_game_over_summary_scrolls_inside_parchment_frame():
    """Long match summaries should stay clipped inside the scroll body and respond to wheel scrolling."""
    window = SmokeWindow(width=1200, height=900)
    screen = GameOverScreen(window)
    long_line = (
        "P1 wandered through the labyrinth during Appeasing Pan and triggered a very long "
        "summary entry that should wrap across several lines inside the parchment viewport."
    )
    screen.set_result(
        1,
        29,
        22,
        {
            "damage_cards": {
                0: [Card(CardRank.QUEEN, CardSuit.HEARTS)] * 6,
                1: [Card(CardRank.KING, CardSuit.SPADES)] * 6,
            },
            "appeasing": [long_line, long_line],
            "requests": [long_line, long_line],
            "events": [long_line, long_line, long_line],
        },
    )

    surface = pygame.Surface((window.WINDOW_WIDTH, window.WINDOW_HEIGHT))
    screen.render(surface)

    assert screen.match_summary_panel_rect is not None
    assert screen.match_summary_scroll_rect is not None
    assert screen.match_summary_scroll_rect.bottom < screen.match_summary_panel_rect.bottom
    assert screen.match_summary_scroll_max > 0

    old_offset = screen.match_summary_scroll_offset
    assert screen._scroll_match_summary(-1, screen.match_summary_scroll_rect.center)
    assert screen.match_summary_scroll_offset > old_offset

    screen.render(surface)
    assert screen.match_summary_scroll_offset > 0


def test_game_over_uses_multiplayer_display_names():
    """Victory text should use room names, with duplicate names made unique."""
    window = SmokeWindow(width=1200, height=900)
    window.multiplayer_session = type("Session", (), {"players": {0: "Brandt", 1: "Brandt"}})()
    screen = GameOverScreen(window)

    screen.set_result(
        1,
        28,
        10,
        {
            "damage_cards": {},
            "events": ["P2 launched by Ballista. P1 reached 25 or more damage."],
        },
    )

    assert screen.winner_text == "Brandt1 Wins!"
    assert screen.damage_text == "Final health - Brandt: 0/25 | Brandt1: 15/25"
    assert screen._replace_player_tokens(screen.match_summary["events"][0]) == (
        "Brandt1 launched by Ballista. Brandt reached 25 or more damage."
    )


def test_game_over_multiplayer_play_again_is_room_vote():
    """Multiplayer Play Again should vote in the room instead of restarting alone."""
    window = SmokeWindow(width=1200, height=900)

    class Session:
        player_id = 0
        players = {0: "Host", 1: "Guest"}
        rematch_votes = set()
        rematch_declined = False
        rematch_declined_by = None
        rematch_declined_name = ""
        last_error = None
        request_calls = 0
        decline_calls = 0

        def request_rematch(self):
            self.request_calls += 1
            self.rematch_votes.add(self.player_id)
            return True

        def decline_rematch(self):
            self.decline_calls += 1
            self.rematch_declined = True
            self.rematch_declined_by = self.player_id
            self.rematch_declined_name = self.players[self.player_id]
            return True

    session = Session()
    window.multiplayer_session = session
    screen = GameOverScreen(window)

    play_event = pygame.event.Event(
        pygame.MOUSEBUTTONDOWN,
        {"pos": screen.game_over_button_rects["play"].center},
    )
    menu_event = pygame.event.Event(
        pygame.MOUSEBUTTONDOWN,
        {"pos": screen.game_over_button_rects["menu"].center},
    )

    assert screen.handle_events(play_event) is True
    assert session.request_calls == 1
    assert screen._get_multiplayer_rematch_notice() == "Waiting for Guest to choose Play Again."

    session.rematch_votes = {1}
    assert screen._get_multiplayer_rematch_notice() == "'Guest' would like to play again."

    assert screen.handle_events(menu_event) == "MENU"
    assert session.decline_calls == 1
    assert screen._is_play_again_enabled() is False

    assert screen.handle_events(play_event) is True
    assert session.request_calls == 1

    surface = pygame.Surface((window.WINDOW_WIDTH, window.WINDOW_HEIGHT))
    screen.render(surface)


def test_plane_shift_confirmation_preview_smoke(game_setup):
    """Plane Shift confirmation should queue and render the animated preview."""
    window = SmokeWindow(width=820, height=720)
    game = game_setup
    target_row = 2
    game.phase = GamePhase.APPEASING
    game.current_request_winner = 0
    game.pending_request_players = [0]
    game.current_player = 0
    game.traversing_resume_player = 1
    assert game.choose_request(0, "plane_shift")

    screen = GameScreen(window, game)
    screen.pending_plane_shift_line = ("row", target_row)
    assert screen._commit_plane_shift_direction("right")
    assert screen.pending_plane_shift_confirmation == ("row", target_row, "right")

    panel_rect, _ = screen._get_plane_shift_confirmation_layout()
    preview_rect = screen._get_plane_shift_confirmation_preview_rect(panel_rect)
    assert preview_rect.height > 0

    surface = pygame.Surface((window.WINDOW_WIDTH, window.WINDOW_HEIGHT))
    screen.update(0.16)
    screen.render(surface)
    assert screen.pending_plane_shift_confirmation == ("row", target_row, "right")

    screen.pending_plane_shift_line = ("column", 3)
    screen.pending_plane_shift_confirmation = None
    assert screen._commit_plane_shift_direction("down")
    screen._render_plane_shift_popup_preview(surface, preview_rect, "column", "down")

    screen.plane_shift_preview_elapsed = 1.14
    near_end_progress = screen._get_plane_shift_preview_progress()
    screen.plane_shift_preview_elapsed = 1.15
    reset_progress = screen._get_plane_shift_preview_progress()
    assert near_end_progress > reset_progress


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
