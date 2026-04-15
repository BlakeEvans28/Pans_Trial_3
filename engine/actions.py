"""
Action definitions for Pan's Trial.
Actions are the interface between engine and UI/AI.
"""

from dataclasses import dataclass
from enum import Enum
from .cards import Card, CardSuit
from .board import Position


class ActionType(Enum):
    """Types of actions players can take."""
    MOVE = "move"
    PICK_UP_CURRENT = "pick_up_current"
    PLAY_CARD = "play_card"
    CHOOSE_COMBAT_CARD = "choose_combat_card"
    CHOOSE_REQUEST = "choose_request"
    SELECT_DAMAGE_CARD = "select_damage_card"
    SELECT_RESTRUCTURE_SUIT = "select_restructure_suit"
    SELECT_PLANE_SHIFT_DIRECTION = "select_plane_shift_direction"
    RESOLVE_PLANE_SHIFT = "resolve_plane_shift"
    RESOLVE_BALLISTA_SHOT = "resolve_ballista_shot"
    PLACE_CARDS = "place_cards"


class RequestType(Enum):
    """Request types in Appeasing Pan phase."""
    RESTRUCTURE = "restructure"
    STEAL_LIFE = "steal_life"
    IGNORE_US = "ignore_us"
    PLANE_SHIFT = "plane_shift"


@dataclass
class Action:
    """Base action."""
    player_id: int


@dataclass
class MoveAction(Action):
    """Move player to adjacent cell."""
    direction: str  # "up", "down", "left", "right"

    def __post_init__(self):
        self.type = ActionType.MOVE
        if self.direction not in ["up", "down", "left", "right"]:
            raise ValueError(f"Invalid direction: {self.direction}")


@dataclass
class PickupCurrentCardAction(Action):
    """Pick up the card underneath the current player instead of moving."""

    def __post_init__(self):
        self.type = ActionType.PICK_UP_CURRENT


@dataclass
class PlayCardAction(Action):
    """Play a card during Appeasing Pan phase."""
    card: Card

    def __post_init__(self):
        self.type = ActionType.PLAY_CARD


@dataclass
class ChooseCombatCardAction(Action):
    """Choose a damage card during same-tile combat."""
    card: Card

    def __post_init__(self):
        self.type = ActionType.CHOOSE_COMBAT_CARD


@dataclass
class ChooseRequestAction(Action):
    """Choose a request after winning card play."""
    request_type: RequestType
    params: dict = None  # For parameterized requests (e.g., which jacks, which row/col)

    def __post_init__(self):
        self.type = ActionType.CHOOSE_REQUEST
        if self.params is None:
            self.params = {}


@dataclass
class SelectDamageCardAction(Action):
    """Select a damage card during Steal Life resolution."""
    pile_owner: int
    card: Card

    def __post_init__(self):
        self.type = ActionType.SELECT_DAMAGE_CARD


@dataclass
class SelectRestructureSuitAction(Action):
    """Select one suit/color to swap during Restructure resolution."""
    suit: CardSuit

    def __post_init__(self):
        self.type = ActionType.SELECT_RESTRUCTURE_SUIT


@dataclass
class SelectPlaneShiftDirectionAction(Action):
    """Select the direction for Plane Shift."""
    direction: str

    def __post_init__(self):
        self.type = ActionType.SELECT_PLANE_SHIFT_DIRECTION
        if self.direction not in ["up", "down", "left", "right"]:
            raise ValueError(f"Invalid direction: {self.direction}")


@dataclass
class ResolvePlaneShiftAction(Action):
    """Choose the row or column to shift during Plane Shift."""
    index: int

    def __post_init__(self):
        self.type = ActionType.RESOLVE_PLANE_SHIFT


@dataclass
class ResolveBallistaShotAction(Action):
    """Choose the exact ballista destination tile."""
    row: int
    col: int

    def __post_init__(self):
        self.type = ActionType.RESOLVE_BALLISTA_SHOT


@dataclass
class PlaceCardsAction(Action):
    """Place cards in holes after Appeasing Pan phase."""
    positions: list[Position]  # Where to place the cards
    card_indices: list[int] | None = None  # Which pending cards to place at those positions

    def __post_init__(self):
        self.type = ActionType.PLACE_CARDS


def movement_to_direction(delta_row: int, delta_col: int) -> str:
    """Convert row/col delta to direction string."""
    if delta_row == -1 and delta_col == 0:
        return "up"
    elif delta_row == 1 and delta_col == 0:
        return "down"
    elif delta_row == 0 and delta_col == -1:
        return "left"
    elif delta_row == 0 and delta_col == 1:
        return "right"
    else:
        raise ValueError(f"Invalid movement: ({delta_row}, {delta_col})")


def direction_to_movement(direction: str) -> tuple[int, int]:
    """Convert direction string to (delta_row, delta_col)."""
    directions = {
        "up": (-1, 0),
        "down": (1, 0),
        "left": (0, -1),
        "right": (0, 1),
    }
    if direction not in directions:
        raise ValueError(f"Invalid direction: {direction}")
    return directions[direction]
