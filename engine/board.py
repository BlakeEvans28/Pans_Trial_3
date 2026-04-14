"""
Board representation for Pan's Trial.
6x6 toroidal grid with card positions and player positions.
"""

from dataclasses import dataclass, field
from typing import Optional
from .cards import Card, CellContent, CardSuit, CardRank


@dataclass
class Position:
    """Board position (row, col)."""
    row: int
    col: int

    def __add__(self, other: "Position") -> "Position":
        """Add two positions."""
        return Position(self.row + other.row, self.col + other.col)

    def __eq__(self, other):
        if not isinstance(other, Position):
            return False
        return self.row == other.row and self.col == other.col

    def __hash__(self):
        return hash((self.row, self.col))


class Board:
    """6x6 toroidal board for the Labyrinth."""
    
    ROWS = 6
    COLS = 6

    def __init__(self):
        """Initialize empty board."""
        # Grid stores CellContent objects
        self.grid: list[list[CellContent]] = [
            [CellContent() for _ in range(self.COLS)] for _ in range(self.ROWS)
        ]
        # Track player positions
        self.player_positions: dict[int, Position] = {}

    def set_cell(self, pos: Position, content: CellContent) -> None:
        """Set cell content."""
        row, col = self._normalize_pos(pos)
        self.grid[row][col] = content

    def get_cell(self, pos: Position) -> CellContent:
        """Get cell content with toroidal wrapping."""
        row, col = self._normalize_pos(pos)
        return self.grid[row][col]

    def get_card(self, pos: Position) -> Optional[Card]:
        """Get card at position, or None if hole."""
        return self.get_cell(pos).card

    def set_card(self, pos: Position, card: Optional[Card]) -> None:
        """Set card at position (None = hole)."""
        content = self.get_cell(pos)
        self.set_cell(pos, CellContent(card=card, player_id=content.player_id))

    def place_player(self, player_id: int, pos: Position) -> None:
        """Place a player on the board."""
        # Normalize position for toroidal wrapping
        normalized_pos = Position(pos.row % self.ROWS, pos.col % self.COLS)
        
        # Remove from old position if exists
        if player_id in self.player_positions:
            old_pos = self.player_positions[player_id]
            content = self.get_cell(old_pos)
            self.set_cell(old_pos, CellContent(card=content.card, player_id=None))
        
        # Place at new position
        content = self.get_cell(normalized_pos)
        self.set_cell(normalized_pos, CellContent(card=content.card, player_id=player_id))
        self.player_positions[player_id] = normalized_pos

    def get_player_position(self, player_id: int) -> Optional[Position]:
        """Get player position."""
        return self.player_positions.get(player_id)

    def get_player_at(self, pos: Position) -> Optional[int]:
        """Get player ID at position, or None."""
        return self.get_cell(pos).player_id

    def move_row(self, row: int, direction: int) -> None:
        """
        Shift a row left (direction=-1) or right (direction=1).
        Toroidal wrapping applies.
        """
        if direction not in [-1, 1]:
            raise ValueError("Direction must be -1 or 1")
        
        old_row = self.grid[row][:]
        new_row = [None] * self.COLS
        
        for col in range(self.COLS):
            old_col = (col - direction) % self.COLS
            new_row[col] = old_row[old_col]
        
        self.grid[row] = new_row
        
        # Update player positions
        for player_id, pos in list(self.player_positions.items()):
            if pos.row == row:
                new_col = (pos.col + direction) % self.COLS
                self.player_positions[player_id] = Position(row, new_col)

    def move_col(self, col: int, direction: int) -> None:
        """
        Shift a column up (direction=-1) or down (direction=1).
        Toroidal wrapping applies.
        """
        if direction not in [-1, 1]:
            raise ValueError("Direction must be -1 or 1")
        
        old_col = [self.grid[row][col] for row in range(self.ROWS)]
        
        for row in range(self.ROWS):
            old_row = (row - direction) % self.ROWS
            self.grid[row][col] = old_col[old_row]
        
        # Update player positions
        for player_id, pos in list(self.player_positions.items()):
            if pos.col == col:
                new_row = (pos.row + direction) % self.ROWS
                self.player_positions[player_id] = Position(new_row, col)

    def _normalize_pos(self, pos: Position) -> tuple[int, int]:
        """Normalize position with toroidal wrapping."""
        row = pos.row % self.ROWS
        col = pos.col % self.COLS
        return row, col

    def get_row(self, row: int) -> list[CellContent]:
        """Get entire row."""
        return self.grid[row]

    def get_col(self, col: int) -> list[CellContent]:
        """Get entire column."""
        return [self.grid[row][col] for row in range(self.ROWS)]
