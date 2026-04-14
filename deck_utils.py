"""
Deck utilities and game setup.
"""

from random import shuffle
from engine import Card, CardRank, CardSuit


def create_standard_deck() -> list[Card]:
    """Create a standard 52-card deck."""
    cards = []
    for suit in CardSuit:
        for rank in CardRank:
            cards.append(Card(rank, suit))
    return cards


def get_labyrinth_cards(deck: list[Card]) -> list[Card]:
    """Get cards for the 6x6 labyrinth grid (Ace through 9 only)."""
    labyrinth = []
    for card in deck:
        if card.rank.value <= CardRank.NINE.value:
            labyrinth.append(card)
    return labyrinth


def get_hand_cards(deck: list[Card]) -> list[Card]:
    """Get cards for player hands (Kings, Queens, 10s, Jacks)."""
    hand = []
    for card in deck:
        if card.rank in [CardRank.JACK, CardRank.QUEEN, CardRank.KING, CardRank.TEN]:
            hand.append(card)
    return hand


def get_draft_cards(deck: list[Card]) -> list[Card]:
    """Get the 12-card draft pool (all 10s, Queens, and Kings)."""
    return [card for card in deck if card.rank in [CardRank.TEN, CardRank.QUEEN, CardRank.KING]]


def get_jack_cards(deck: list[Card]) -> list[Card]:
    """Get only jack cards for suit role assignment."""
    return [card for card in deck if card.rank == CardRank.JACK]


def setup_pregame_cards() -> tuple[list[Card], list[Card], list[Card]]:
    """
    Build the cards needed before gameplay starts.
    Returns (labyrinth_cards, draft_cards, jack_cards)
    """
    deck = create_standard_deck()
    labyrinth = get_labyrinth_cards(deck)
    draft_cards = get_draft_cards(deck)
    jack_cards = get_jack_cards(deck)

    shuffle(labyrinth)
    shuffle(draft_cards)
    shuffle(jack_cards)

    return labyrinth, draft_cards, jack_cards


def setup_game_deck() -> tuple[list[Card], list[Card], list[Card], list[Card]]:
    """
    Set up deck for game.
    Returns (labyrinth_cards, player1_deck, player2_deck, jack_cards)
    """
    labyrinth = get_labyrinth_cards(create_standard_deck())
    player1_deck = get_hand_cards(create_standard_deck())
    player2_deck = get_hand_cards(create_standard_deck())
    jack_cards = get_jack_cards(create_standard_deck())

    shuffle(labyrinth)
    shuffle(player1_deck)
    shuffle(player2_deck)
    shuffle(jack_cards)

    return labyrinth, player1_deck, player2_deck, jack_cards


def create_6x6_labyrinth(labyrinth_cards: list[Card]) -> list[list[Card]]:
    """Create a 6x6 labyrinth grid from shuffled cards."""
    if len(labyrinth_cards) < 36:
        raise ValueError("Need at least 36 cards for labyrinth")
    
    grid = []
    for row in range(6):
        grid_row = []
        for col in range(6):
            grid_row.append(labyrinth_cards[row * 6 + col])
        grid.append(grid_row)
    
    return grid


def _draw_rank_cards(deck: list[Card], rank: CardRank, count: int) -> list[Card]:
    """Draw a number of cards of a given rank from a personal deck."""
    matches = [card for card in deck if card.rank == rank][:count]
    if len(matches) != count:
        raise ValueError(f"Need {count} {rank.name} cards")
    return matches


def draft_hands(player1_deck: list[Card], player2_deck: list[Card]) -> tuple[list[Card], list[Card], int]:
    """
    Build each player's hand from their own personal deck.
    Returns (player0_hand, player1_hand, starting_player)
    """
    p0_hand = (
        _draw_rank_cards(player1_deck, CardRank.KING, 1)
        + _draw_rank_cards(player1_deck, CardRank.QUEEN, 2)
        + _draw_rank_cards(player1_deck, CardRank.TEN, 2)
    )
    p1_hand = (
        _draw_rank_cards(player2_deck, CardRank.KING, 1)
        + _draw_rank_cards(player2_deck, CardRank.QUEEN, 2)
        + _draw_rank_cards(player2_deck, CardRank.TEN, 2)
    )

    starting_player = 1

    return p0_hand, p1_hand, starting_player


def get_jack_suit_order(jack_cards: list[Card]) -> list[CardSuit]:
    """Get the 4 Jacks in random order for suit role assignment."""
    if len(jack_cards) < 4:
        raise ValueError("Need 4 Jacks")

    shuffled_jacks = jack_cards[:]
    shuffle(shuffled_jacks)
    return [card.suit for card in shuffled_jacks[:4]]
