"""
Card data models for Pan's Trial.
Pure Python - no pygame dependencies.
"""

from enum import Enum
from dataclasses import dataclass
from typing import Optional
from pan_theme import get_card_display, get_family_name, get_rank_name, get_rank_name_with_value


class CardRank(Enum):
    """Card ranks in Pan's Trial."""
    ACE = 1
    TWO = 2
    THREE = 3
    FOUR = 4
    FIVE = 5
    SIX = 6
    SEVEN = 7
    EIGHT = 8
    NINE = 9
    TEN = 10
    JACK = 11
    QUEEN = 12
    KING = 13

    @property
    def display_name(self) -> str:
        """Return the themed rank name for UI display."""
        return get_rank_name(self)

    @property
    def display_name_with_value(self) -> str:
        """Return the themed rank name with visible combat values for high ranks."""
        return get_rank_name_with_value(self)


class CardSuit(Enum):
    """Card suits."""
    HEARTS = "hearts"
    DIAMONDS = "diamonds"
    CLUBS = "clubs"
    SPADES = "spades"

    @property
    def display_name(self) -> str:
        """Return the themed family name for UI display."""
        return get_family_name(self)


class SuitRole(Enum):
    """Current role assigned to each suit by Jacks."""
    WALLS = "walls"
    TRAPS = "traps"
    BALLISTA = "ballista"
    WEAPONS = "weapons"


@dataclass(frozen=True)
class Card:
    """A single card in the game."""
    rank: CardRank
    suit: CardSuit

    def __str__(self) -> str:
        return get_card_display(self)

    def combat_value(self) -> int:
        """Get value for combat resolution."""
        # Map special cases
        if self.rank == CardRank.ACE:
            return 1
        elif self.rank == CardRank.QUEEN:
            return 11
        elif self.rank == CardRank.KING:
            return 12
        # For other cards, use their enum value (2-10)
        else:
            return self.rank.value


@dataclass(frozen=True)
class CellContent:
    """What occupies a cell in the grid."""
    card: Optional[Card] = None  # None indicates a hole
    player_id: Optional[int] = None  # 0 or 1, or None if no player here

    def is_hole(self) -> bool:
        """Check if this cell is a hole (empty space)."""
        return self.card is None


@dataclass
class PlayerHand:
    """Cards held by a player."""
    cards: list[Card]

    def add_card(self, card: Card) -> None:
        """Add a card to hand."""
        self.cards.append(card)

    def remove_card(self, card: Card) -> None:
        """Remove a card from hand."""
        self.cards.remove(card)

    def has_card(self, card: Card) -> bool:
        """Check if player has card."""
        return card in self.cards


@dataclass
class DamagePile:
    """Cards in a player's damage pile."""
    cards: list[Card]

    def add_card(self, card: Card) -> None:
        """Add damage card."""
        self.cards.append(card)

    def remove_card(self, card: Card) -> None:
        """Remove a damage card."""
        self.cards.remove(card)

    def total_damage(self) -> int:
        """Calculate total damage from all cards."""
        return sum(card.combat_value() for card in self.cards)

    def is_defeated(self) -> bool:
        """Check if player has 25+ damage."""
        return self.total_damage() >= 25
