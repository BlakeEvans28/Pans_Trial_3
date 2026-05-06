"""Shared game setup helpers for room-backed Pan's Trial matches."""

from __future__ import annotations

from random import shuffle

from deck_utils import create_6x6_labyrinth, draft_hands, get_jack_suit_order, setup_game_deck
from engine import Card, GameState, Position


def create_game_from_pregame(
    labyrinth_cards: list[Card],
    player0_hand: list[Card],
    player1_hand: list[Card],
    jack_order: list,
    starting_player: int = 1,
) -> GameState:
    """Create a traversing game from completed shared pregame setup."""
    from engine import GamePhase

    game = GameState()
    game.setup_suit_roles(jack_order)
    available_labyrinth_cards = list(labyrinth_cards)

    for _ in range(100):
        grid = create_6x6_labyrinth(available_labyrinth_cards)
        game.setup_board(grid)
        game.place_player(0, Position(5, 3))
        game.place_player(1, Position(0, 2))
        if game.get_legal_moves(0) and game.get_legal_moves(1):
            break
        shuffle(available_labyrinth_cards)

    for card in player0_hand:
        game.add_card_to_hand(0, card)
    for card in player1_hand:
        game.add_card_to_hand(1, card)

    game.current_player = starting_player
    game.traversing_resume_player = starting_player
    game.phase = GamePhase.TRAVERSING
    return game


def create_quick_match_game() -> GameState:
    """Create a direct-to-labyrinth two-player game for room tests and smoke play."""
    labyrinth_cards, player0_deck, player1_deck, jack_cards = setup_game_deck()
    player0_hand, player1_hand, starting_player = draft_hands(player0_deck, player1_deck)
    jack_order = get_jack_suit_order(jack_cards)
    return create_game_from_pregame(labyrinth_cards, player0_hand, player1_hand, jack_order, starting_player)
