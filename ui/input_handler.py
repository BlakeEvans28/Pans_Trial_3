"""
Input handling for Pan's Trial gameplay.
Manages click-to-move and request selection.
"""

from typing import Optional
import sys
from pathlib import Path
import pygame

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from engine import Action, Board, MoveAction, PickupCurrentCardAction, Position


class InputHandler:
    """Handles player input during gameplay."""
    
    def __init__(self, board_renderer: "BoardRenderer"):
        self.renderer = board_renderer
        self.pending_action: Optional[Action] = None
    
    def handle_mouse_click(self, pos: tuple[int, int], player_id: int, game_state) -> Optional[Action]:
        """
        Handle click on board.
        Returns action if valid move, None otherwise.
        """
        # Get cell at click position
        cell = self.renderer.get_cell_at_mouse(pos)
        if cell is None:
            return None
        
        # Get current player position
        current_pos = game_state.board.get_player_position(player_id)
        if current_pos is None:
            return None

        if cell == current_pos and game_state.can_pick_up_current_card(player_id):
            return PickupCurrentCardAction(player_id)
        
        # Get direction to clicked cell
        direction = self.get_direction_to_cell(current_pos, cell)
        if direction is None:
            return None
        
        # Check if move is legal
        legal_moves = game_state.get_legal_moves(player_id)
        if direction not in legal_moves:
            return None
        
        return MoveAction(player_id, direction)
    
    def get_direction_to_cell(self, from_pos: Position, to_pos: Position) -> Optional[str]:
        """
        Get direction from one cell to adjacent cell.
        Returns None if cells are not adjacent.
        """
        if from_pos.col == to_pos.col:
            if (from_pos.row - 1) % Board.ROWS == to_pos.row:
                return "up"
            if (from_pos.row + 1) % Board.ROWS == to_pos.row:
                return "down"

        if from_pos.row == to_pos.row:
            if (from_pos.col - 1) % Board.COLS == to_pos.col:
                return "left"
            if (from_pos.col + 1) % Board.COLS == to_pos.col:
                return "right"

        return None
