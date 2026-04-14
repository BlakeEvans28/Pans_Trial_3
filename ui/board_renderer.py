"""
Board rendering for the 6x6 grid.
"""

import pygame
from typing import Optional
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from pan_theme import get_family_color
from engine import Board, Position, GamePhase


class BoardRenderer:
    """Renders the game board in pygame."""
    
    # Board rendering settings - centered in window
    CELL_SIZE = 80  # Slightly smaller for better fit
    GRID_WIDTH = 6
    GRID_HEIGHT = 6
    BOARD_WIDTH = CELL_SIZE * GRID_WIDTH
    BOARD_HEIGHT = CELL_SIZE * GRID_HEIGHT
    
    # Colors
    GRID_COLOR = (100, 100, 120)
    CELL_COLOR = (40, 40, 50)
    HOLE_COLOR = (20, 20, 20)
    PLAYER1_COLOR = (200, 50, 50)
    PLAYER2_COLOR = (50, 50, 200)
    
    def __init__(self):
        """Initialize board renderer."""
        self.font_small = pygame.font.Font(None, 24)
        self.font_medium = pygame.font.Font(None, 32)
    
    def render(
        self,
        surface: pygame.Surface,
        board: Board,
        suit_roles: dict,
        phase: GamePhase = None,
        highlight_positions: Optional[set[Position]] = None,
    ) -> None:
        """Render the board to surface."""
        # Calculate centered board position
        surface_width = surface.get_width()
        surface_height = surface.get_height()
        
        # Center horizontally, leaving room for the Pan's Favor strip above the board.
        self.BOARD_X = (surface_width - self.BOARD_WIDTH) // 2
        self.BOARD_Y = 110
        
        self._render_grid(surface)
        self._render_cells(surface, board, suit_roles, phase, highlight_positions or set())
        self._render_players(surface, board)
    
    def _render_grid(self, surface: pygame.Surface) -> None:
        """Render grid lines."""
        # Horizontal lines
        for row in range(self.GRID_HEIGHT + 1):
            y = self.BOARD_Y + row * self.CELL_SIZE
            pygame.draw.line(
                surface, self.GRID_COLOR,
                (self.BOARD_X, y),
                (self.BOARD_X + self.BOARD_WIDTH, y),
                2
            )
        
        # Vertical lines
        for col in range(self.GRID_WIDTH + 1):
            x = self.BOARD_X + col * self.CELL_SIZE
            pygame.draw.line(
                surface, self.GRID_COLOR,
                (x, self.BOARD_Y),
                (x, self.BOARD_Y + self.BOARD_HEIGHT),
                2
            )
    
    def _render_cells(
        self,
        surface: pygame.Surface,
        board: Board,
        suit_roles: dict,
        phase,
        highlight_positions: set[Position],
    ) -> None:
        """Render cards in cells."""
        for row in range(self.GRID_HEIGHT):
            for col in range(self.GRID_WIDTH):
                pos = Position(row, col)
                cell_content = board.get_cell(pos)
                
                x = self.BOARD_X + col * self.CELL_SIZE + 2
                y = self.BOARD_Y + row * self.CELL_SIZE + 2
                w = self.CELL_SIZE - 4
                h = self.CELL_SIZE - 4
                
                # Draw cell background based on card type
                if cell_content.card is None:
                    color = self.HOLE_COLOR
                    pygame.draw.rect(surface, color, (x, y, w, h))
                else:
                    card = cell_content.card
                    suit_role = suit_roles.get(card.suit)
                    
                    # Color the labyrinth tile with the currently assigned family color
                    # so the board always matches the omen legend on the right.
                    color = get_family_color(card.suit) if suit_role in ["walls", "traps", "ballista", "weapons"] else self.CELL_COLOR
                    
                    pygame.draw.rect(surface, color, (x, y, w, h))
                    pygame.draw.rect(surface, self.GRID_COLOR, (x, y, w, h), 2)
                    
                    # Draw card info
                    self._render_card_info(surface, card, x + 5, y + 5, suit_role, phase)

                if pos in highlight_positions:
                    pygame.draw.rect(surface, (245, 220, 120), (x + 6, y + 6, w - 12, h - 12), 3, border_radius=8)
    
    def _render_card_info(self, surface: pygame.Surface, card, x: int, y: int, suit_role: str, phase) -> None:
        """Render card rank only; tile color already communicates the role."""
        rank_text = self.font_small.render(card.rank.display_name, True, (200, 200, 200))
        surface.blit(rank_text, (x, y))
    
    def _render_players(self, surface: pygame.Surface, board: Board) -> None:
        """Render player positions."""
        for player_id in [0, 1]:
            pos = board.get_player_position(player_id)
            if pos is not None:
                color = self.PLAYER1_COLOR if player_id == 0 else self.PLAYER2_COLOR
                
                x = self.BOARD_X + pos.col * self.CELL_SIZE + self.CELL_SIZE // 2
                y = self.BOARD_Y + pos.row * self.CELL_SIZE + self.CELL_SIZE // 2
                radius = 15
                
                pygame.draw.circle(surface, color, (x, y), radius, 3)
                
                # Player label
                label = self.font_small.render(f"P{player_id + 1}", True, color)
                surface.blit(label, (x - 10, y - 10))
    
    def get_cell_at_mouse(self, mouse_pos: tuple[int, int]) -> Optional[Position]:
        """Get grid cell at mouse position."""
        x, y = mouse_pos
        
        # Check if mouse is in board area
        if not (self.BOARD_X <= x <= self.BOARD_X + self.BOARD_WIDTH and
                self.BOARD_Y <= y <= self.BOARD_Y + self.BOARD_HEIGHT):
            return None
        
        col = (x - self.BOARD_X) // self.CELL_SIZE
        row = (y - self.BOARD_Y) // self.CELL_SIZE
        
        if 0 <= row < self.GRID_HEIGHT and 0 <= col < self.GRID_WIDTH:
            return Position(row, col)
        
        return None
