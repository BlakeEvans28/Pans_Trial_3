"""
Tests for Pan's Trial game rules.
"""

import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame
import pygame_gui
import pytest
from engine import (
    Card, CardRank, CardSuit, GameState, GamePhase,
    MoveAction, PickupCurrentCardAction, Position, SuitRole, ChooseCombatCardAction,
    ChooseRequestAction, RequestType, ResolveBallistaShotAction, SelectDamageCardAction,
    SelectRestructureSuitAction, SelectPlaneShiftDirectionAction, ResolvePlaneShiftAction,
    PlaceCardsAction
)
from deck_utils import setup_game_deck, create_6x6_labyrinth, draft_hands, get_jack_suit_order
from ui.input_handler import InputHandler
from ui.board_renderer import BoardRenderer
from ui.game_screen import GameScreen
from ui.screen_manager import SettingsScreen


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
        self.tutorial_enabled = True
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
        self.tutorial_enabled = True
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

    assert game.apply_action(ChooseRequestAction(
        1,
        RequestType.RESTRUCTURE,
        {"suits": [game.jack_order[2], game.jack_order[3]]},
    ))
    assert game.phase == GamePhase.TRAVERSING
    assert game.pending_request_players == []
    assert game.current_player == 1


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


def test_appeasing_stronger_color_beats_higher_rank(game_setup):
    """A stronger trump color should beat a weaker color regardless of rank."""
    game = game_setup
    game.setup_suit_roles([CardSuit.HEARTS, CardSuit.DIAMONDS, CardSuit.CLUBS, CardSuit.SPADES])
    game.phase_started_cards = [
        (0, Card(CardRank.NINE, CardSuit.HEARTS)),
        (1, Card(CardRank.EIGHT, CardSuit.SPADES)),
    ]
    game.current_player = 1

    game._resolve_appeasing_phase()

    assert game.current_request_winner == 1


def test_appeasing_hierarchy_runs_weapons_to_walls(game_setup):
    """Phase 2 trump order should be Weapons > Ballista > Traps > Walls."""
    game = game_setup
    game.setup_suit_roles([CardSuit.HEARTS, CardSuit.DIAMONDS, CardSuit.CLUBS, CardSuit.SPADES])

    assert game.get_appeasing_hierarchy() == [
        CardSuit.SPADES,
        CardSuit.CLUBS,
        CardSuit.DIAMONDS,
        CardSuit.HEARTS,
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


def test_settings_tutorial_reset_smoke():
    """Settings reset button should re-enable first-cycle tutorial state."""
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
    assert window.tutorial_enabled is True
    assert window.reset_calls == 1
    assert gameplay_stub.reset_called is True


def test_compact_hand_card_inspect_smoke(game_setup):
    """Compact hand cards should open the Inspect popup before play."""
    window = SmokeWindow(width=560, height=660)
    game = game_setup
    game.current_player = 0
    game.phase = GamePhase.APPEASING
    game.current_request_winner = None
    screen = GameScreen(window, game)

    hand_rects = screen._get_hand_card_rects()
    assert hand_rects
    assert screen._handle_hand_card_click(hand_rects[0][1].center)
    assert screen.inspected_hand_card_index == 0
    assert screen._is_hand_inspect_popup_active()

    surface = pygame.Surface((window.WINDOW_WIDTH, window.WINDOW_HEIGHT))
    screen.render(surface)
    assert screen.hand_card_rects


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


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
