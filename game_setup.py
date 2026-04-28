"""
Shared game setup helpers for local and multiplayer Pan's Trial matches.
"""

from random import shuffle

from deck_utils import create_6x6_labyrinth, draft_hands, get_jack_suit_order, setup_game_deck
from engine import GamePhase, GameState, Position


def initialize_game(
    labyrinth_cards: list,
    p0_hand: list,
    p1_hand: list,
    jack_order: list,
    starting_player: int = 1,
) -> GameState:
    """Initialize a new game from a completed setup."""
    game = GameState()
    game.setup_suit_roles(jack_order)

    for _ in range(100):
        labyrinth_grid = create_6x6_labyrinth(labyrinth_cards)
        game.setup_board(labyrinth_grid)
        game.place_player(0, Position(5, 3))
        game.place_player(1, Position(0, 2))
        if game.get_legal_moves(0) and game.get_legal_moves(1):
            break
        shuffle(labyrinth_cards)

    for card in p0_hand:
        game.add_card_to_hand(0, card)
    for card in p1_hand:
        game.add_card_to_hand(1, card)

    game.current_player = starting_player
    game.traversing_resume_player = starting_player
    game.phase = GamePhase.TRAVERSING
    return game


def create_random_game() -> GameState:
    """Create a fully randomized ready-to-play game for multiplayer rooms."""
    labyrinth_cards, player1_deck, player2_deck, jack_cards = setup_game_deck()
    p0_hand, p1_hand, starting_player = draft_hands(player1_deck, player2_deck)
    jack_order = get_jack_suit_order(jack_cards)
    return initialize_game(labyrinth_cards, p0_hand, p1_hand, jack_order, starting_player=starting_player)
