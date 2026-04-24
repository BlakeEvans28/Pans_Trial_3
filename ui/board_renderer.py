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
    
    BASE_CELL_SIZE = 80
    MIN_CELL_SIZE = 56
    MAX_CELL_SIZE = 104
    GRID_WIDTH = 6
    GRID_HEIGHT = 6
    
    # Colors
    GRID_COLOR = (100, 100, 120)
    CELL_COLOR = (40, 40, 50)
    HOLE_COLOR = (20, 20, 20)
    PLAYER1_COLOR = (200, 50, 50)
    PLAYER2_COLOR = (50, 50, 200)
    PLAYER_MARKER_RADIUS = 17
    ASSET_ROOT = Path(__file__).resolve().parent.parent / "assets"
    PLAYER_PORTRAIT_PATH = Path(__file__).resolve().parent.parent / "assets" / "player_portrait_micah.png"
    MEDIEVAL_SHARP_PATH = ASSET_ROOT / "MedievalSharp.ttf"
    
    def __init__(self):
        """Initialize board renderer."""
        self.CELL_SIZE = self.BASE_CELL_SIZE
        self.BOARD_WIDTH = self.CELL_SIZE * self.GRID_WIDTH
        self.BOARD_HEIGHT = self.CELL_SIZE * self.GRID_HEIGHT
        self.BOARD_X = 0
        self.BOARD_Y = 0
        self.font_small = None
        self.font_medium = None
        self.player_label_font = None
        self._refresh_fonts()
        self._player_portrait_base = self._load_player_portrait()
        self._player_portrait_cache: dict[int, pygame.Surface] = {}
        self._tile_art_base = self._load_tile_art()
        self._tile_art_cache: dict[tuple[str, int], pygame.Surface] = {}

    def _refresh_fonts(self) -> None:
        """Refresh fonts to match the current cell size."""
        small_size = max(18, int(round(self.CELL_SIZE * 0.30)))
        medium_size = max(22, int(round(self.CELL_SIZE * 0.40)))
        label_size = max(16, int(round(self.CELL_SIZE * 0.22)))
        
        # Try to use MedievalSharp from assets, fall back to default
        if self.MEDIEVAL_SHARP_PATH.exists():
            self.font_small = pygame.font.Font(str(self.MEDIEVAL_SHARP_PATH), small_size)
            self.font_medium = pygame.font.Font(str(self.MEDIEVAL_SHARP_PATH), medium_size)
            self.player_label_font = pygame.font.Font(str(self.MEDIEVAL_SHARP_PATH), label_size)
        else:
            self.font_small = pygame.font.Font(None, small_size)
            self.font_medium = pygame.font.Font(None, medium_size)
            self.player_label_font = pygame.font.Font(None, label_size)

    def _load_player_portrait(self) -> Optional[pygame.Surface]:
        """Load the circular portrait asset used for player markers."""
        if not self.PLAYER_PORTRAIT_PATH.exists():
            return None
        return pygame.image.load(str(self.PLAYER_PORTRAIT_PATH)).convert_alpha()

    def _load_tile_art(self) -> dict[str, pygame.Surface]:
        """Load labyrinth role artwork from assets."""
        art = {}
        paths = {
            "walls": self.ASSET_ROOT / "Stone_Wall.jpg",
            "ballista": self.ASSET_ROOT / "Ballista.png",
            "traps": self.ASSET_ROOT / "Trap.png",
        }
        for key, path in paths.items():
            if path.exists():
                art[key] = pygame.image.load(str(path)).convert_alpha()

        cards_dir = self.ASSET_ROOT / "cards"
        for role, prefix in [("weapons", "Weapon")]:
            for value in range(1, 13):
                path = cards_dir / f"{prefix}{value:02}.png"
                if path.exists():
                    art[f"{role}_{value}"] = pygame.image.load(str(path)).convert_alpha()
        return art

    def _get_scaled_tile_art(self, key: str, size: tuple[int, int]) -> Optional[pygame.Surface]:
        """Return cached artwork scaled to one board cell."""
        if key not in self._tile_art_base:
            return None
        cache_key = (key, size[0])
        if cache_key not in self._tile_art_cache:
            self._tile_art_cache[cache_key] = pygame.transform.smoothscale(self._tile_art_base[key], size)
        return self._tile_art_cache[cache_key]

    def _get_card_art_value(self, card) -> int:
        """Return the 1-12 value used for numbered tile art."""
        return max(1, min(12, card.combat_value()))

    def _get_card_art_key(self, card, suit_role: str | None) -> str | None:
        """Return the asset key for a card in its current labyrinth role."""
        if suit_role == "walls":
            return "walls"
        if suit_role == "ballista":
            return "ballista"
        if suit_role == "traps":
            return "traps"
        if suit_role == "weapons":
            return f"weapons_{self._get_card_art_value(card)}"
        return None

    def _get_scaled_player_portrait(self, diameter: int) -> Optional[pygame.Surface]:
        """Return a cached portrait surface sized for the current marker."""
        if self._player_portrait_base is None:
            return None
        if diameter not in self._player_portrait_cache:
            self._player_portrait_cache[diameter] = pygame.transform.smoothscale(
                self._player_portrait_base,
                (diameter, diameter),
            )
        return self._player_portrait_cache[diameter]

    @staticmethod
    def get_player_x_offset(
        player_id: int,
        sharing_tile: bool,
        cell_size: int | None = None,
    ) -> int:
        """Offset player markers only when both players occupy the same tile."""
        if not sharing_tile:
            return 0
        active_cell_size = cell_size if cell_size is not None else BoardRenderer.BASE_CELL_SIZE
        return -active_cell_size // 5 if player_id == 0 else active_cell_size // 5

    def update_layout(self, surface_width: int, surface_height: int) -> None:
        """Recompute board metrics for the current window size."""
        compact = surface_width < 720 or surface_height < 680
        if compact:
            side_gutter = max(18, int(surface_width * 0.07))
            top_margin = max(150, int(surface_height * 0.21))
            bottom_margin = max(130, int(surface_height * 0.18))
            min_cell_size = 44
        else:
            side_gutter = min(max(180, int(surface_width * 0.18)), surface_width // 4)
            top_margin = max(86, int(surface_height * 0.11))
            bottom_margin = max(190, int(surface_height * 0.20))
            min_cell_size = self.MIN_CELL_SIZE

        available_width = max(min_cell_size * self.GRID_WIDTH, surface_width - 2 * side_gutter)
        available_height = max(min_cell_size * self.GRID_HEIGHT, surface_height - top_margin - bottom_margin)
        cell_size = min(
            self.MAX_CELL_SIZE,
            max(
                min_cell_size,
                min(
                    available_width // self.GRID_WIDTH,
                    available_height // self.GRID_HEIGHT,
                ),
            ),
        )

        if cell_size != self.CELL_SIZE:
            self.CELL_SIZE = cell_size
            self._refresh_fonts()

        self.BOARD_WIDTH = self.CELL_SIZE * self.GRID_WIDTH
        self.BOARD_HEIGHT = self.CELL_SIZE * self.GRID_HEIGHT
        self.BOARD_X = (surface_width - self.BOARD_WIDTH) // 2
        self.BOARD_Y = max(top_margin, (surface_height - bottom_margin - self.BOARD_HEIGHT) // 2)

    def get_board_rect(self) -> pygame.Rect:
        """Return the board rect for the most recent layout."""
        return pygame.Rect(self.BOARD_X, self.BOARD_Y, self.BOARD_WIDTH, self.BOARD_HEIGHT)
    
    def render(
        self,
        surface: pygame.Surface,
        board: Board,
        suit_roles: dict,
        phase: GamePhase = None,
        highlight_positions: Optional[set[Position]] = None,
    ) -> None:
        """Render the board to surface."""
        self.update_layout(surface.get_width(), surface.get_height())
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
                    self.render_card_tile(surface, card, suit_role, pygame.Rect(x, y, w, h), phase)

                if pos in highlight_positions:
                    self.draw_value_safe_outline(
                        surface,
                        pygame.Rect(x + 6, y + 6, w - 12, h - 12),
                        (245, 220, 120),
                        3,
                    )

    def draw_value_safe_outline(
        self,
        surface: pygame.Surface,
        rect: pygame.Rect,
        color: tuple[int, int, int],
        width: int = 3,
    ) -> None:
        """Draw a target outline while leaving top-left card values readable."""
        label_gap = max(24, int(self.CELL_SIZE * 0.38))
        top_start_x = min(rect.right, rect.left + label_gap)
        left_start_y = min(rect.bottom, rect.top + label_gap)

        pygame.draw.line(surface, color, (top_start_x, rect.top), (rect.right, rect.top), width)
        pygame.draw.line(surface, color, (rect.right, rect.top), (rect.right, rect.bottom), width)
        pygame.draw.line(surface, color, (rect.right, rect.bottom), (rect.left, rect.bottom), width)
        pygame.draw.line(surface, color, (rect.left, rect.bottom), (rect.left, left_start_y), width)

    def render_card_tile(
        self,
        surface: pygame.Surface,
        card,
        suit_role: str | None,
        rect: pygame.Rect,
        phase=None,
        dimmed: bool = False,
    ) -> None:
        """Render a card exactly like a labyrinth tile, reusable for hands and dragging."""
        if suit_role is not None and not isinstance(suit_role, str):
            suit_role = suit_role.value

        color = get_family_color(card.suit) if suit_role in ["walls", "traps", "ballista", "weapons"] else self.CELL_COLOR
        pygame.draw.rect(surface, color, rect)
        pygame.draw.rect(surface, self.GRID_COLOR, rect, 2)
        self._render_card_art(surface, card, suit_role, rect, phase)

        if dimmed:
            veil = pygame.Surface(rect.size, pygame.SRCALPHA)
            veil.fill((6, 8, 12, 150))
            surface.blit(veil, rect.topleft)

    def _render_card_art(self, surface: pygame.Surface, card, suit_role: str, rect: pygame.Rect, phase) -> None:
        """Render role artwork for a labyrinth card."""
        art_key = self._get_card_art_key(card, suit_role)
        art = self._get_scaled_tile_art(art_key, rect.size) if art_key else None
        if art is not None:
            surface.blit(art, rect.topleft)
            pygame.draw.rect(surface, self.GRID_COLOR, rect, 2)
            if suit_role in {"walls", "ballista", "traps"}:
                self._render_card_info(surface, card, rect.x + 5, rect.y + 5, suit_role, phase)
            return

        self._render_card_info(surface, card, rect.x + 5, rect.y + 5, suit_role, phase)
    
    def _render_card_info(self, surface: pygame.Surface, card, x: int, y: int, suit_role: str, phase) -> None:
        """Render card rank only; tile color already communicates the role."""
        label = str(card.combat_value()) if suit_role in {"walls", "ballista", "traps"} else card.rank.display_name
        text_color = get_family_color(card.suit) if suit_role in {"walls", "ballista", "traps"} else (200, 200, 200)
        shadow = self.font_small.render(label, True, (8, 10, 14))
        surface.blit(shadow, (x + 1, y + 1))
        rank_text = self.font_small.render(label, True, text_color)
        surface.blit(rank_text, (x, y))
    
    def _render_players(self, surface: pygame.Surface, board: Board) -> None:
        """Render player positions."""
        shared_tile = (
            board.get_player_position(0) is not None
            and board.get_player_position(0) == board.get_player_position(1)
        )
        for player_id in [0, 1]:
            pos = board.get_player_position(player_id)
            if pos is not None:
                color = self.PLAYER1_COLOR if player_id == 0 else self.PLAYER2_COLOR

                x_offset = self.get_player_x_offset(player_id, shared_tile, self.CELL_SIZE)
                x = self.BOARD_X + pos.col * self.CELL_SIZE + self.CELL_SIZE // 2 + x_offset
                y = self.BOARD_Y + pos.row * self.CELL_SIZE + self.CELL_SIZE // 2
                self._render_player_marker(surface, player_id, color, x, y, shared_tile)

    def _render_player_marker(
        self,
        surface: pygame.Surface,
        player_id: int,
        color: tuple[int, int, int],
        x: int,
        y: int,
        shared_tile: bool,
    ) -> None:
        """Render a labeled portrait marker for one player."""
        radius = self.PLAYER_MARKER_RADIUS - 2 if shared_tile else self.PLAYER_MARKER_RADIUS
        center = (x, y + 6)

        pygame.draw.circle(surface, (16, 18, 24), (center[0], center[1] + 2), radius + 1)

        portrait = self._get_scaled_player_portrait(radius * 2)
        if portrait is not None:
            portrait_rect = portrait.get_rect(center=center)
            surface.blit(portrait, portrait_rect)
        else:
            pygame.draw.circle(surface, (20, 20, 28), center, radius)

        pygame.draw.circle(surface, color, center, radius, 3)
        pygame.draw.circle(surface, (236, 236, 240), center, radius, 1)

        self._render_player_label(surface, player_id, color, center, radius, shared_tile)

    def _render_player_label(
        self,
        surface: pygame.Surface,
        player_id: int,
        color: tuple[int, int, int],
        center: tuple[int, int],
        radius: int,
        shared_tile: bool,
    ) -> None:
        """Render the player name above the circular portrait."""
        label = self.player_label_font.render(f"Player {player_id + 1}", True, (246, 246, 248))
        label_rect = label.get_rect()
        label_rect.inflate_ip(14, 8)

        label_x = center[0]
        if shared_tile:
            label_x += -16 if player_id == 0 else 16

        label_rect.midbottom = (label_x, center[1] - radius - 4)
        chip = pygame.Surface(label_rect.size, pygame.SRCALPHA)
        pygame.draw.rect(chip, (14, 16, 22, 220), chip.get_rect(), border_radius=10)
        pygame.draw.rect(chip, (*color, 235), chip.get_rect(), 1, border_radius=10)
        surface.blit(chip, label_rect.topleft)
        surface.blit(label, label.get_rect(center=label_rect.center))
    
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

    def get_cell_rect(self, pos: Position) -> pygame.Rect:
        """Return the on-screen rect for a board cell."""
        return pygame.Rect(
            self.BOARD_X + pos.col * self.CELL_SIZE + 2,
            self.BOARD_Y + pos.row * self.CELL_SIZE + 2,
            self.CELL_SIZE - 4,
            self.CELL_SIZE - 4,
        )
