"""
Shared theme helpers for Pan's Trial display names and colors.
"""

FAMILY_NAMES = {
    "hearts": "Crimson",
    "diamonds": "Gold",
    "clubs": "Verdant",
    "spades": "Azure",
}

FAMILY_CODES = {
    "hearts": "C",
    "diamonds": "G",
    "clubs": "V",
    "spades": "A",
}

FAMILY_COLORS = {
    "hearts": (196, 64, 78),
    "diamonds": (212, 176, 66),
    "clubs": (74, 160, 92),
    "spades": (72, 118, 196),
}

RANK_NAMES = {
    "ACE": "1",
    "TWO": "2",
    "THREE": "3",
    "FOUR": "4",
    "FIVE": "5",
    "SIX": "6",
    "SEVEN": "7",
    "EIGHT": "8",
    "NINE": "9",
    "TEN": "Satyr",
    "JACK": "Omen",
    "QUEEN": "Oracle",
    "KING": "Hero",
}

RANK_WITH_VALUE = {
    "TEN": "Satyr (10)",
    "JACK": "Omen",
    "QUEEN": "Oracle (11)",
    "KING": "Hero (12)",
}


def get_family_name(suit) -> str:
    """Return the themed color-family name for a suit enum or value."""
    value = getattr(suit, "value", suit)
    return FAMILY_NAMES.get(value, str(value).title())


def get_family_code(suit) -> str:
    """Return a short code for the themed color family."""
    value = getattr(suit, "value", suit)
    return FAMILY_CODES.get(value, "?")


def get_family_color(suit) -> tuple[int, int, int]:
    """Return the RGB color used for the family marker."""
    value = getattr(suit, "value", suit)
    return FAMILY_COLORS.get(value, (180, 180, 180))


def get_rank_name(rank) -> str:
    """Return the themed rank display name."""
    name = getattr(rank, "name", str(rank))
    return RANK_NAMES.get(name, name.title())


def get_rank_name_with_value(rank) -> str:
    """Return the themed rank name, preserving high-rank combat values visibly."""
    name = getattr(rank, "name", str(rank))
    if name in RANK_WITH_VALUE:
        return RANK_WITH_VALUE[name]
    return get_rank_name(rank)


def get_card_display(card, compact: bool = False) -> str:
    """Return a themed card label."""
    rank = get_rank_name_with_value(card.rank) if not compact else get_rank_name(card.rank)
    family = get_family_code(card.suit) if compact else get_family_name(card.suit)
    return f"{rank} {family}"


def get_reversed_hierarchy(order: list) -> list:
    """Return the reversed family order used for Phase 2 hierarchy display."""
    return list(reversed(order))
