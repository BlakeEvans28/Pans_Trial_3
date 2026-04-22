"""
Screen management system for Pan's Trial.
Handles different game screens: Start, Game, GameOver, etc.
"""

from enum import Enum
from random import shuffle
import sys
from pathlib import Path
import pygame
import pygame_gui

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))
from engine import CardRank, CardSuit
from pan_theme import (
    get_card_display,
    get_family_color,
    get_family_name,
    get_rank_name,
    get_rank_name_with_value,
)
from .suit_icons import draw_suit_icon


class ScreenType(Enum):
    """Different screens in the game."""
    START = "start"
    HOW_TO_PLAY = "how_to_play"
    SETTINGS = "settings"
    COIN_FLIP = "coin_flip"
    DRAFT = "draft"
    JACK_REVEAL = "jack_reveal"
    GAME = "game"
    GAME_OVER = "game_over"


class Screen:
    """Base class for all screens."""

    ASSET_ROOT = Path(__file__).resolve().parent.parent / "assets"
    PAN_BACKGROUND_PATH = ASSET_ROOT / "Pan_Background.png"
    PAN_ICON_PATH = ASSET_ROOT / "Pan_Icon.png"
    WOOD_LABEL_CENTER_Y_RATIO = 0.50
    
    def __init__(self, window: "GameWindow"):
        self.window = window
        self.ui_manager = window.ui_manager
        self._background_base = self._load_image(self.PAN_BACKGROUND_PATH)
        self._background_cache: dict[tuple[int, int], pygame.Surface] = {}
        self._wood_icon_base = self._crop_wood_icon(self._load_image(self.PAN_ICON_PATH))
        self._wood_icon_cache: dict[tuple[tuple[int, int], bool], pygame.Surface] = {}
        self._title_style_font_cache: dict[int, pygame.font.Font] = {}

    def scale(self, value: int, minimum: int = 1) -> int:
        """Scale a measurement from the base 1200x900 layout."""
        return self.window.scale(value, minimum)

    def scale_x(self, value: int, minimum: int = 1) -> int:
        """Scale a horizontal measurement from the base layout."""
        return self.window.scale_x(value, minimum)

    def scale_y(self, value: int, minimum: int = 1) -> int:
        """Scale a vertical measurement from the base layout."""
        return self.window.scale_y(value, minimum)

    def is_compact_layout(self) -> bool:
        """Return True when the active window should use phone-style layouts."""
        return self.window.is_compact_layout()

    def font_size(self, value: int, minimum: int = 1) -> int:
        """Scale a font size using the active text-size setting."""
        return self.window.font_size(value, minimum)

    def _load_image(self, path: Path) -> pygame.Surface | None:
        """Load a screen image if the asset is available."""
        if not path.exists():
            return None
        try:
            return pygame.image.load(str(path)).convert_alpha()
        except pygame.error:
            return None

    def _crop_wood_icon(self, image: pygame.Surface | None) -> pygame.Surface | None:
        """Crop Pan_Icon to the visible plank area for reusable UI buttons."""
        if image is None:
            return None
        crop_rect = pygame.Rect(
            0,
            int(image.get_height() * 0.08),
            image.get_width(),
            int(image.get_height() * 0.62),
        )
        return image.subsurface(crop_rect).copy()

    def _get_title_style_font(self, size: int) -> pygame.font.Font:
        """Return a bold serif font that echoes the title lettering."""
        size = max(1, size)
        if size not in self._title_style_font_cache:
            for family in ["georgia", "garamond", "timesnewroman", "times new roman"]:
                font_path = pygame.font.match_font(family, bold=True)
                if font_path is not None:
                    self._title_style_font_cache[size] = pygame.font.Font(font_path, size)
                    break
            else:
                self._title_style_font_cache[size] = pygame.font.Font(None, size)
        return self._title_style_font_cache[size]

    def _render_screen_background(self, surface: pygame.Surface, fallback: tuple[int, int, int] = (16, 20, 30)) -> None:
        """Render Pan_Background with the same cover-scaling rule as the title art."""
        if self._background_base is None:
            surface.fill(fallback)
            return

        size = self._get_cover_scaled_size(self._background_base, surface.get_size())
        if size not in self._background_cache:
            self._background_cache[size] = pygame.transform.smoothscale(self._background_base, size)
        surface.blit(self._background_cache[size], (0, 0))

    def _get_cover_scaled_size(self, image: pygame.Surface, frame_size: tuple[int, int]) -> tuple[int, int]:
        """Return an image size that covers the frame and crops right/bottom overflow."""
        frame_width, frame_height = frame_size
        scale = max(frame_width / image.get_width(), frame_height / image.get_height())
        return (
            max(1, int(image.get_width() * scale)),
            max(1, int(image.get_height() * scale)),
        )

    def _get_wood_icon_height_for_width(self, width: int) -> int:
        """Return Pan_Icon height for a width while preserving aspect ratio."""
        if self._wood_icon_base is None or self._wood_icon_base.get_width() <= 0:
            return max(self.scale_y(64, 44), width // 3)
        return max(1, int(width * self._wood_icon_base.get_height() / self._wood_icon_base.get_width()))

    def _get_wood_icon_width_for_height(self, height: int) -> int:
        """Return Pan_Icon width for a height while preserving aspect ratio."""
        if self._wood_icon_base is None or self._wood_icon_base.get_height() <= 0:
            return max(1, height * 3)
        return max(1, int(height * self._wood_icon_base.get_width() / self._wood_icon_base.get_height()))

    def _get_scaled_wood_icon(self, size: tuple[int, int], bright: bool) -> pygame.Surface | None:
        """Return the wood icon scaled to a rect, brightened when hovered."""
        if self._wood_icon_base is None:
            return None
        key = (size, bright)
        if key not in self._wood_icon_cache:
            icon = pygame.transform.smoothscale(self._wood_icon_base, size)
            if bright:
                icon = icon.copy()
                icon.fill((58, 58, 58, 0), special_flags=pygame.BLEND_RGBA_ADD)
            self._wood_icon_cache[key] = icon
        return self._wood_icon_cache[key]

    def _get_wood_label_center(self, rect: pygame.Rect) -> tuple[int, int]:
        """Return the visual center of the wood plank inside the icon canvas."""
        return (rect.centerx, rect.y + int(rect.height * self.WOOD_LABEL_CENTER_Y_RATIO))

    def _get_wood_text_font(self, label: str, rect: pygame.Rect, preferred_size: int) -> pygame.font.Font:
        """Return a title-style font sized to fit the visible plank."""
        max_width = max(1, int(rect.width * 0.72))
        size = max(self.font_size(18, 14), preferred_size)
        while size > self.font_size(16, 12):
            font = self._get_title_style_font(size)
            if font.size(label)[0] <= max_width:
                return font
            size -= 2
        return self._get_title_style_font(size)

    def _render_wood_button(
        self,
        surface: pygame.Surface,
        rect: pygame.Rect,
        label: str,
        hovered: bool,
        preferred_font_size: int | None = None,
        enabled: bool = True,
    ) -> None:
        """Render a Pan_Icon wood button with centered title-style text."""
        icon = self._get_scaled_wood_icon(rect.size, hovered and enabled)
        if icon is not None:
            surface.blit(icon, rect.topleft)
        else:
            pygame.draw.rect(surface, (96, 66, 38), rect, border_radius=self.scale(10, 6))

        if not enabled:
            veil = pygame.Surface(rect.size, pygame.SRCALPHA)
            veil.fill((10, 10, 12, 132))
            surface.blit(veil, rect.topleft)

        font_size = preferred_font_size if preferred_font_size is not None else self.font_size(32, 22)
        font = self._get_wood_text_font(label, rect, font_size)
        if enabled:
            text_color = (255, 246, 214) if hovered else (246, 236, 204)
        else:
            text_color = (156, 150, 136)
        label_surface = font.render(label, True, text_color)
        shadow = font.render(label, True, (24, 14, 8))
        label_rect = label_surface.get_rect(center=self._get_wood_label_center(rect))
        surface.blit(shadow, label_rect.move(self.scale(3, 2), self.scale(3, 2)))
        surface.blit(label_surface, label_rect)
    
    def handle_events(self, event: pygame.event.Event) -> bool:
        """Handle event. Return True if event was consumed."""
        raise NotImplementedError
    
    def update(self, time_delta: float) -> None:
        """Update screen state."""
        raise NotImplementedError
    
    def render(self, surface: pygame.Surface) -> None:
        """Render screen."""
        raise NotImplementedError
    
    def on_enter(self) -> None:
        """Called when screen is activated."""
        pass
    
    def on_exit(self) -> None:
        """Called when screen is deactivated."""
        pass

    def on_resize(self) -> None:
        """Recompute any cached layout after the window size changes."""
        pass


class StartScreen(Screen):
    """Start/menu screen."""

    ASSET_ROOT = Path(__file__).resolve().parent.parent / "assets"
    MENU_ACTIONS = [
        ("PLAY", "Start Game"),
        ("HOW_TO_PLAY", "How To Play"),
        ("SETTINGS", "Settings"),
        ("QUIT", "Quit"),
    ]
    MENU_LABEL_CENTER_Y_RATIO = 0.38
    
    def __init__(self, window: "GameWindow"):
        super().__init__(window)
        self.title_font = None
        self.info_font = None
        self.menu_font = None
        self.menu_buttons: list[tuple[str, str, pygame.Rect]] = []
        self.hovered_menu_action = None
        self._title_base = self._load_image(self.ASSET_ROOT / "PanTitle.png")
        self._icon_base = self._load_image(self.ASSET_ROOT / "Pan_Icon.png")
        self._title_cache: dict[tuple[int, int], pygame.Surface] = {}
        self._icon_cache: dict[tuple[tuple[int, int], bool], pygame.Surface] = {}
        self._refresh_fonts()
        self._create_ui()
        self.on_resize()

    def _refresh_fonts(self) -> None:
        """Refresh cached fonts for the current window scale."""
        self.title_font = pygame.font.Font(None, self.font_size(72, 42))
        self.info_font = pygame.font.Font(None, self.font_size(24, 18))
        self.menu_font = self._make_title_style_font(self.font_size(42, 30))

    def _make_title_style_font(self, size: int) -> pygame.font.Font:
        """Return a large serif font that sits closer to the title lettering."""
        for family in ["georgia", "garamond", "timesnewroman", "times new roman"]:
            font_path = pygame.font.match_font(family, bold=True)
            if font_path is not None:
                return pygame.font.Font(font_path, size)
        return pygame.font.Font(None, size)

    def _load_image(self, path: Path) -> pygame.Surface | None:
        """Load a title-screen image if the asset is available."""
        if not path.exists():
            return None
        try:
            return pygame.image.load(str(path)).convert_alpha()
        except pygame.error:
            return None
    
    def _create_ui(self):
        """Create manual title-menu hitboxes."""
        self._layout_ui()

    def _layout_ui(self) -> None:
        """Lay out the wood-icon title menu down the right side."""
        icon_overlap = self.scale_y(66, 44) if not self.is_compact_layout() else self.scale_y(46, 30)
        gap = -icon_overlap
        side_margin = self.scale_x(42, 18) if not self.is_compact_layout() else self.scale_x(18, 10)
        min_width = 190 if self.is_compact_layout() else 330
        max_width = 360 if self.is_compact_layout() else 520
        icon_width = min(max_width, max(min_width, int(self.window.WINDOW_WIDTH * (0.46 if self.is_compact_layout() else 0.31))))
        icon_height = self._get_icon_height_for_width(icon_width)
        vertical_margin = self.scale_y(52, 28)
        max_total_height = max(icon_height, self.window.WINDOW_HEIGHT - 2 * vertical_margin)
        total_height = len(self.MENU_ACTIONS) * icon_height + (len(self.MENU_ACTIONS) - 1) * gap
        if total_height > max_total_height:
            available_icon_height = max(1, (max_total_height - (len(self.MENU_ACTIONS) - 1) * gap) // len(self.MENU_ACTIONS))
            icon_width = self._get_icon_width_for_height(available_icon_height)
            icon_height = self._get_icon_height_for_width(icon_width)
        total_height = len(self.MENU_ACTIONS) * icon_height + (len(self.MENU_ACTIONS) - 1) * gap
        start_x = max(self.scale_x(12, 8), self.window.WINDOW_WIDTH - side_margin - icon_width)
        start_y = max(
            vertical_margin,
            min(
                (self.window.WINDOW_HEIGHT - total_height) // 2,
                self.window.WINDOW_HEIGHT - total_height - vertical_margin,
            ),
        )

        self.menu_buttons = []
        for index, (action, label) in enumerate(self.MENU_ACTIONS):
            rect = pygame.Rect(
                start_x,
                start_y + index * (icon_height + gap),
                icon_width,
                icon_height,
            )
            self.menu_buttons.append((action, label, rect))
    
    def _hide_all_elements(self):
        """Start screen renders controls manually."""
        self.hovered_menu_action = None
    
    def handle_events(self, event: pygame.event.Event) -> bool:
        """Handle events."""
        if event.type == pygame.MOUSEMOTION:
            self.hovered_menu_action = self._menu_action_at(event.pos)
            return False
        if event.type == pygame.MOUSEBUTTONDOWN:
            action = self._menu_action_at(event.pos)
            if action is not None:
                return action
        return False
    
    def update(self, time_delta: float) -> None:
        """Update."""
        pass
    
    def render(self, surface: pygame.Surface) -> None:
        """Render start screen."""
        surface.fill((20, 20, 30))
        self._render_title_art(surface)
        self._render_menu_buttons(surface)

    def _render_title_art(self, surface: pygame.Surface) -> None:
        """Render the checked-in title artwork as a full-screen background."""
        if self._title_base is None:
            fallback = self.title_font.render("Pan's Trial", True, (238, 214, 142))
            surface.blit(fallback, fallback.get_rect(center=(self.window.WINDOW_WIDTH // 2, self.scale_y(130, 90))))
            return

        image = self._get_scaled_title_art()
        surface.blit(image, (0, 0))

    def _get_scaled_title_art(self) -> pygame.Surface:
        """Return the title image proportionally scaled to cover the frame."""
        scale = max(
            self.window.WINDOW_WIDTH / self._title_base.get_width(),
            self.window.WINDOW_HEIGHT / self._title_base.get_height(),
        )
        size = (
            max(1, int(self._title_base.get_width() * scale)),
            max(1, int(self._title_base.get_height() * scale)),
        )
        if size not in self._title_cache:
            self._title_cache[size] = pygame.transform.smoothscale(self._title_base, size)
        return self._title_cache[size]

    def _render_menu_buttons(self, surface: pygame.Surface) -> None:
        """Render right-side wood-icon buttons with overlaid labels."""
        mouse_pos = pygame.mouse.get_pos()
        self.hovered_menu_action = self._menu_action_at(mouse_pos)
        for action, label, rect in self.menu_buttons:
            hovered = action == self.hovered_menu_action

            icon = self._get_scaled_icon(rect.size, hovered)
            if icon is not None:
                surface.blit(icon, rect.topleft)
            else:
                pygame.draw.rect(surface, (96, 66, 38), rect, border_radius=self.scale(10, 6))

            label_surface = self.menu_font.render(label, True, (255, 246, 214) if hovered else (246, 236, 204))
            shadow = self.menu_font.render(label, True, (24, 14, 8))
            label_rect = label_surface.get_rect(center=self._get_menu_label_center(rect))
            surface.blit(shadow, label_rect.move(self.scale(3, 2), self.scale(3, 2)))
            surface.blit(label_surface, label_rect)

    def _get_menu_label_center(self, rect: pygame.Rect) -> tuple[int, int]:
        """Return the visual center of the wood plank within the icon canvas."""
        return (rect.centerx, rect.y + int(rect.height * self.MENU_LABEL_CENTER_Y_RATIO))

    def _get_icon_height_for_width(self, width: int) -> int:
        """Return the Pan icon height that preserves its source aspect ratio."""
        if self._icon_base is None or self._icon_base.get_width() <= 0:
            return max(self.scale_y(64, 44), width // 3)
        return max(1, int(width * self._icon_base.get_height() / self._icon_base.get_width()))

    def _get_icon_width_for_height(self, height: int) -> int:
        """Return the Pan icon width that preserves its source aspect ratio."""
        if self._icon_base is None or self._icon_base.get_height() <= 0:
            return max(1, height * 3)
        return max(1, int(height * self._icon_base.get_width() / self._icon_base.get_height()))

    def _get_scaled_icon(self, size: tuple[int, int], bright: bool) -> pygame.Surface | None:
        """Return the Pan icon, brightened when hovered."""
        if self._icon_base is None:
            return None
        key = (size, bright)
        if key not in self._icon_cache:
            icon = pygame.transform.smoothscale(self._icon_base, size)
            if bright:
                icon = icon.copy()
                icon.fill((58, 58, 58, 0), special_flags=pygame.BLEND_RGBA_ADD)
            self._icon_cache[key] = icon
        return self._icon_cache[key]

    def _menu_action_at(self, pos: tuple[int, int]) -> str | None:
        """Return the title-menu action at a mouse position."""
        for action, _, rect in self.menu_buttons:
            if rect.collidepoint(pos):
                return action
        return None
    
    def on_enter(self) -> None:
        """Activate start screen."""
        # Hide all game screen elements first
        if hasattr(self.window, 'game_screen_ref'):
            game_screen = self.window.game_screen_ref
            game_screen.status_label.hide()
            game_screen.info_label.hide()
            for _, btn in game_screen.move_buttons:
                btn.hide()
            for _, btn in game_screen.request_buttons:
                btn.hide()
        
        self.hovered_menu_action = None
    
    def on_exit(self) -> None:
        """Deactivate start screen."""
        self.hovered_menu_action = None

    def on_resize(self) -> None:
        """Resize fonts and button positions."""
        self._refresh_fonts()
        self._layout_ui()


class HowToPlayScreen(Screen):
    """How-to-play screen reachable from the home page."""

    SECTIONS = [
        (
            "Goal",
            "Force the other player to 25 or more damage while keeping your own damage lower.",
        ),
        (
            "Draft",
            "Players draft Satyrs (10), Oracles (11), and Heroes (12). The two undrafted Heroes become the player cards.",
        ),
        (
            "Omens",
            "The four Omens assign each color family to a role: Walls, Traps, Ballista, or Weapons.",
        ),
        (
            "Traversing",
            "Move around the 6x6 toroidal labyrinth. Walls block, Traps add damage, Weapons enter your hand, and Ballista tiles launch you in a straight line.",
        ),
        (
            "Appeasing Pan",
            "After six movement turns, both players play one hand card. Color role strength decides first; matching colors use rank.",
        ),
        (
            "Requests",
            "The Appeasing winner chooses first from Restructure, Steal Life, Ignore Us, or Plane Shift. The loser chooses second unless Ignore Us ends the phase.",
        ),
        (
            "Holes",
            "After requests, the Appeasing loser places the two played cards into open holes. If holes run out, the remaining cards return to that loser's hand.",
        ),
    ]

    def __init__(self, window: "GameWindow"):
        super().__init__(window)
        self.title_font = None
        self.heading_font = None
        self.body_font = None
        self.small_font = None
        self.back_button = None
        self.back_button_rect = pygame.Rect(0, 0, 1, 1)
        self.hovered_button = None
        self.scroll_offset = 0
        self.max_scroll = 0
        self._refresh_fonts()
        self._create_ui()
        self.on_resize()
        self._hide_all_elements()

    def _refresh_fonts(self) -> None:
        """Refresh fonts for the current window scale."""
        self.title_font = pygame.font.Font(None, self.font_size(64, 38))
        self.heading_font = pygame.font.Font(None, self.font_size(30, 22))
        self.body_font = pygame.font.Font(None, self.font_size(24, 17))
        self.small_font = pygame.font.Font(None, self.font_size(22, 16))

    def _create_ui(self) -> None:
        """Create How To Play UI controls."""
        self.back_button = pygame_gui.elements.UIButton(
            relative_rect=pygame.Rect((0, 0), (1, 1)),
            text="Back",
            manager=self.ui_manager,
            object_id="how_to_back_button",
        )

    def _layout_ui(self) -> None:
        """Lay out the back button for the current window size."""
        button_width = min(self.scale_x(330, 220), self.window.WINDOW_WIDTH - 2 * self.scale_x(24, 14))
        button_height = self._get_wood_icon_height_for_width(button_width)
        self.back_button_rect = pygame.Rect(
            (self.window.WINDOW_WIDTH - button_width) // 2,
            self.window.WINDOW_HEIGHT - button_height - self.scale_y(6, 4),
            button_width,
            button_height,
        )
        self.back_button.set_relative_position(
            (
                self.back_button_rect.x,
                self.back_button_rect.y,
            )
        )
        self.back_button.set_dimensions((button_width, button_height))

    def _hide_all_elements(self) -> None:
        """Hide all How To Play controls."""
        self.back_button.hide()

    def handle_events(self, event: pygame.event.Event) -> bool:
        """Handle How To Play events."""
        if event.type == pygame_gui.UI_BUTTON_PRESSED and event.ui_element == self.back_button:
            return "MENU"
        if event.type == pygame.MOUSEMOTION:
            self.hovered_button = "back" if self.back_button_rect.collidepoint(event.pos) else None
            return False
        if event.type == pygame.MOUSEBUTTONDOWN and self.back_button_rect.collidepoint(event.pos):
            return "MENU"
        if event.type == pygame.MOUSEWHEEL:
            self.scroll_offset = max(0, min(self.max_scroll, self.scroll_offset - event.y * self.scale(48, 32)))
            return True
        return False

    def update(self, time_delta: float) -> None:
        """How To Play has no timed state."""
        pass

    def render(self, surface: pygame.Surface) -> None:
        """Render the How To Play page."""
        self._render_screen_background(surface, (16, 20, 30))

        title = self.title_font.render("HOW TO PLAY", True, (238, 214, 142))
        title_rect = title.get_rect(center=(self.window.WINDOW_WIDTH // 2, self.scale_y(76, 54)))
        surface.blit(title, title_rect)

        subtitle = self.small_font.render(
            "A quick guide to the draft, labyrinth, and Appeasing Pan.",
            True,
            (190, 198, 210),
        )
        subtitle_rect = subtitle.get_rect(center=(self.window.WINDOW_WIDTH // 2, self.scale_y(122, 88)))
        surface.blit(subtitle, subtitle_rect)

        viewport_rect = pygame.Rect(
            self.scale_x(48, 24),
            self.scale_y(160, 118),
            self.window.WINDOW_WIDTH - 2 * self.scale_x(48, 24),
            self.window.WINDOW_HEIGHT - self.scale_y(280, 204),
        )
        columns = 2 if self.window.WINDOW_WIDTH >= 900 else 1
        rows = (len(self.SECTIONS) + columns - 1) // columns
        gap = self.scale(14, 8)
        card_width = (viewport_rect.width - gap * (columns - 1)) // columns
        card_height = max(
            self.scale_y(112, 86) if columns == 1 else self.scale_y(76, 58),
            (viewport_rect.height - gap * (rows - 1)) // rows if columns > 1 else 0,
        )
        content_height = rows * card_height + (rows - 1) * gap
        self.max_scroll = max(0, content_height - viewport_rect.height)
        self.scroll_offset = min(self.scroll_offset, self.max_scroll)

        if self.max_scroll:
            hint = self.small_font.render("Mouse wheel scrolls this guide.", True, (150, 158, 170))
            surface.blit(hint, (viewport_rect.x, viewport_rect.bottom + self.scale_y(8, 5)))

        old_clip = surface.get_clip()
        surface.set_clip(viewport_rect)
        for index, (heading, body) in enumerate(self.SECTIONS):
            col = index // rows
            row = index % rows
            card_rect = pygame.Rect(
                viewport_rect.x + col * (card_width + gap),
                viewport_rect.y + row * (card_height + gap) - self.scroll_offset,
                card_width,
                card_height,
            )
            if card_rect.bottom < viewport_rect.top or card_rect.top > viewport_rect.bottom:
                continue
            pygame.draw.rect(surface, (28, 34, 48), card_rect, border_radius=self.scale(14, 8))
            pygame.draw.rect(surface, (96, 112, 136), card_rect, 1, border_radius=self.scale(14, 8))

            heading_surface = self.heading_font.render(heading, True, (244, 226, 164))
            surface.blit(heading_surface, (card_rect.x + self.scale(18, 10), card_rect.y + self.scale(10, 7)))

            body_rect = pygame.Rect(
                card_rect.x + self.scale(18, 10),
                card_rect.y + self.scale(42, 30),
                card_rect.width - self.scale(36, 20),
                card_rect.height - self.scale(50, 36),
            )
            self._draw_wrapped_text(surface, body, self.body_font, (222, 226, 232), body_rect, self.scale(22, 15), 4)
        surface.set_clip(old_clip)
        self._render_wood_button(
            surface,
            self.back_button_rect,
            "Back",
            self.hovered_button == "back",
            self.font_size(38, 26),
        )

    def _draw_wrapped_text(
        self,
        surface: pygame.Surface,
        text: str,
        font: pygame.font.Font,
        color: tuple[int, int, int],
        rect: pygame.Rect,
        line_height: int,
        max_lines: int,
    ) -> None:
        """Draw wrapped text clipped to a fixed number of lines."""
        words = text.split()
        lines = []
        current = ""
        for word in words:
            candidate = word if not current else f"{current} {word}"
            if font.size(candidate)[0] <= rect.width:
                current = candidate
            else:
                if current:
                    lines.append(current)
                current = word
        if current:
            lines.append(current)

        for index, line in enumerate(lines[:max_lines]):
            line_surface = font.render(line, True, color)
            surface.blit(line_surface, (rect.x, rect.y + index * line_height))

    def on_enter(self) -> None:
        """Activate the How To Play screen."""
        self.back_button.hide()

    def on_exit(self) -> None:
        """Deactivate the How To Play screen."""
        self.back_button.hide()
        self.hovered_button = None

    def on_resize(self) -> None:
        """Refresh fonts and layout after resize."""
        self._refresh_fonts()
        self._layout_ui()


class SettingsScreen(Screen):
    """Game settings screen for display, text, animation, sound, and tutorial options."""

    ASSET_ROOT = Path(__file__).resolve().parent.parent / "assets"
    REQUIRED_ART_ASSETS = [
        ASSET_ROOT / "Trap.png",
        ASSET_ROOT / "Ballista.png",
        ASSET_ROOT / "Stone_Wall.jpg",
    ]
    TEXT_SCALES = [("Small", 0.9), ("Normal", 1.0), ("Large", 1.18)]
    ANIMATION_SPEEDS = [("Slow", 0.75), ("Normal", 1.0), ("Fast", 1.35)]
    SOUND_LEVELS = [("Muted", 0.0), ("50%", 0.5), ("100%", 1.0)]

    def __init__(self, window: "GameWindow"):
        super().__init__(window)
        self.title_font = None
        self.body_font = None
        self.small_font = None
        self.fullscreen_button = None
        self.text_button = None
        self.animation_button = None
        self.sound_button = None
        self.tutorial_button = None
        self.tutorial_reset_button = None
        self.back_button = None
        self.button_labels: dict[str, str] = {}
        self.setting_button_rects: dict[str, pygame.Rect] = {}
        self.hovered_setting_key = None
        self._refresh_fonts()
        self._create_ui()
        self.on_resize()
        self._hide_all_elements()

    def _refresh_fonts(self) -> None:
        """Refresh fonts for the current text-size setting."""
        self.title_font = pygame.font.Font(None, self.font_size(64, 38))
        self.body_font = pygame.font.Font(None, self.font_size(28, 20))
        self.small_font = pygame.font.Font(None, self.font_size(22, 16))

    def _create_ui(self) -> None:
        """Create settings buttons."""
        self.fullscreen_button = pygame_gui.elements.UIButton(
            relative_rect=pygame.Rect((0, 0), (1, 1)),
            text="",
            manager=self.ui_manager,
            object_id="settings_fullscreen",
        )
        self.text_button = pygame_gui.elements.UIButton(
            relative_rect=pygame.Rect((0, 0), (1, 1)),
            text="",
            manager=self.ui_manager,
            object_id="settings_text",
        )
        self.animation_button = pygame_gui.elements.UIButton(
            relative_rect=pygame.Rect((0, 0), (1, 1)),
            text="",
            manager=self.ui_manager,
            object_id="settings_animation",
        )
        self.sound_button = pygame_gui.elements.UIButton(
            relative_rect=pygame.Rect((0, 0), (1, 1)),
            text="",
            manager=self.ui_manager,
            object_id="settings_sound",
        )
        self.tutorial_button = pygame_gui.elements.UIButton(
            relative_rect=pygame.Rect((0, 0), (1, 1)),
            text="",
            manager=self.ui_manager,
            object_id="settings_tutorial",
        )
        self.tutorial_reset_button = pygame_gui.elements.UIButton(
            relative_rect=pygame.Rect((0, 0), (1, 1)),
            text="Reset Tutorial Cycle",
            manager=self.ui_manager,
            object_id="settings_tutorial_reset",
        )
        self.back_button = pygame_gui.elements.UIButton(
            relative_rect=pygame.Rect((0, 0), (1, 1)),
            text="Back",
            manager=self.ui_manager,
            object_id="settings_back",
        )

    def _layout_ui(self) -> None:
        """Lay out settings controls."""
        outer_margin = self.scale_x(52, 22)
        column_gap = self.scale_x(26, 14)
        row_gap = self.scale_y(4, 2)
        columns = 1 if self.is_compact_layout() else 2
        available_width = self.window.WINDOW_WIDTH - 2 * outer_margin - (columns - 1) * column_gap
        button_width = min(self.scale_x(390, 250), max(self.scale_x(230, 190), available_width // columns))
        button_height = self._get_wood_icon_height_for_width(button_width)
        start_y = self.scale_y(212, 156) if self.get_missing_required_art_assets() else self.scale_y(188, 138)
        option_controls = self._setting_option_controls()
        rows = (len(option_controls) + columns - 1) // columns
        grid_width = columns * button_width + (columns - 1) * column_gap
        start_x = (self.window.WINDOW_WIDTH - grid_width) // 2

        self.setting_button_rects = {}
        for index, (key, button) in enumerate(option_controls):
            row = index // columns
            col = index % columns
            rect = pygame.Rect(
                start_x + col * (button_width + column_gap),
                start_y + row * (button_height + row_gap),
                button_width,
                button_height,
            )
            self.setting_button_rects[key] = rect
            button.set_relative_position((rect.x, rect.y))
            button.set_dimensions((button_width, button_height))

        back_width = min(self.scale_x(320, 220), button_width)
        back_height = self._get_wood_icon_height_for_width(back_width)
        back_y = start_y + rows * (button_height + row_gap) + self.scale_y(2, 1)
        back_rect = pygame.Rect((self.window.WINDOW_WIDTH - back_width) // 2, back_y, back_width, back_height)
        self.setting_button_rects["back"] = back_rect
        self.back_button.set_relative_position((back_rect.x, back_rect.y))
        self.back_button.set_dimensions((back_rect.width, back_rect.height))

    def _setting_option_controls(self) -> list[tuple[str, object]]:
        """Return only the setting options, without the Back control."""
        return [
            ("fullscreen", self.fullscreen_button),
            ("text", self.text_button),
            ("animation", self.animation_button),
            ("sound", self.sound_button),
            ("tutorial", self.tutorial_button),
            ("tutorial_reset", self.tutorial_reset_button),
        ]

    def _setting_controls(self) -> list[tuple[str, object]]:
        """Return setting-control keys with their hidden pygame_gui buttons."""
        return self._setting_option_controls() + [("back", self.back_button)]

    def _setting_buttons(self) -> list:
        """Return only the hidden setting-control buttons."""
        return [
            self.fullscreen_button,
            self.text_button,
            self.animation_button,
            self.sound_button,
            self.tutorial_button,
            self.tutorial_reset_button,
        ]

    def _hide_all_elements(self) -> None:
        """Hide settings controls."""
        for button in self._setting_buttons() + [self.back_button]:
            button.hide()

    def _cycle_value(self, options: list[tuple[str, float]], current: float) -> float:
        """Return the next value from a list of labeled numeric options."""
        values = [value for _, value in options]
        if current not in values:
            return values[0]
        return values[(values.index(current) + 1) % len(values)]

    def _label_for_value(self, options: list[tuple[str, float]], current: float) -> str:
        """Return the label that matches a numeric setting value."""
        for label, value in options:
            if value == current:
                return label
        return options[0][0]

    def _refresh_button_text(self) -> None:
        """Refresh settings button labels."""
        self.button_labels = {
            "fullscreen": f"Display: {'Fullscreen' if self.window.fullscreen else 'Windowed'}",
            "text": f"Text Size: {self._label_for_value(self.TEXT_SCALES, self.window.text_scale)}",
            "animation": f"Animation Speed: {self._label_for_value(self.ANIMATION_SPEEDS, self.window.animation_speed)}",
            "sound": f"Sound Volume: {self._label_for_value(self.SOUND_LEVELS, self.window.sound_volume)}",
            "tutorial": f"Tutorial Tips: {'On' if self.window.tutorial_enabled else 'Off'}",
            "tutorial_reset": "Reset First Tutorial",
            "back": "Back",
        }
        self.fullscreen_button.set_text(self.button_labels["fullscreen"])
        self.text_button.set_text(self.button_labels["text"])
        self.animation_button.set_text(self.button_labels["animation"])
        self.sound_button.set_text(self.button_labels["sound"])
        self.tutorial_button.set_text(self.button_labels["tutorial"])
        self.tutorial_reset_button.set_text(self.button_labels["tutorial_reset"])
        self.back_button.set_text(self.button_labels["back"])

    def get_missing_required_art_assets(self) -> list[str]:
        """Return required artwork filenames that are unavailable."""
        return [path.name for path in self.REQUIRED_ART_ASSETS if not path.exists()]

    def handle_events(self, event: pygame.event.Event) -> bool:
        """Handle settings clicks."""
        if event.type == pygame.MOUSEMOTION:
            self.hovered_setting_key = self._setting_key_at(event.pos)
            return False
        if event.type == pygame.MOUSEBUTTONDOWN:
            key = self._setting_key_at(event.pos)
            if key is not None:
                return self._activate_setting_key(key)
            return False

        if event.type != pygame_gui.UI_BUTTON_PRESSED:
            return False

        key_by_element = {button: key for key, button in self._setting_controls()}
        key = key_by_element.get(event.ui_element)
        if key is None:
            return False
        return self._activate_setting_key(key)

    def _setting_key_at(self, pos: tuple[int, int]) -> str | None:
        """Return the setting control key at a mouse position."""
        for key, rect in self.setting_button_rects.items():
            if rect.collidepoint(pos):
                return key
        return None

    def _activate_setting_key(self, key: str):
        """Apply one Settings control action."""
        if key == "back":
            return "MENU"
        if key == "fullscreen":
            self.window.toggle_fullscreen()
            self.on_resize()
            return "RESIZED"
        if key == "text":
            self.window.text_scale = self._cycle_value(self.TEXT_SCALES, self.window.text_scale)
            self.on_resize()
            return "RESIZED"
        if key == "animation":
            self.window.animation_speed = self._cycle_value(self.ANIMATION_SPEEDS, self.window.animation_speed)
        elif key == "sound":
            self.window.sound_volume = self._cycle_value(self.SOUND_LEVELS, self.window.sound_volume)
            self.window.audio.set_volume(self.window.sound_volume)
        elif key == "tutorial":
            self.window.tutorial_enabled = not self.window.tutorial_enabled
        elif key == "tutorial_reset":
            self.window.reset_tutorial_tips()
        self._refresh_button_text()
        return True

    def update(self, time_delta: float) -> None:
        """Settings have no timed state."""
        pass

    def render(self, surface: pygame.Surface) -> None:
        """Render the settings page."""
        self._render_screen_background(surface, (18, 22, 32))
        title = self.title_font.render("SETTINGS", True, (238, 214, 142))
        title_rect = title.get_rect(center=(self.window.WINDOW_WIDTH // 2, self.scale_y(84, 58)))
        surface.blit(title, title_rect)

        lines = [
            "Use these controls to make the UI fit your device.",
            "Reset First Tutorial turns the one-cycle tips back on.",
        ]
        for index, text in enumerate(lines):
            line = self.small_font.render(text, True, (190, 198, 210))
            line_rect = line.get_rect(center=(self.window.WINDOW_WIDTH // 2, self.scale_y(132 + index * 28, 92 + index * 18)))
            surface.blit(line, line_rect)

        missing_assets = self.get_missing_required_art_assets()
        if missing_assets:
            warning_rect = pygame.Rect(
                self.scale_x(34, 18),
                self.scale_y(178, 130),
                self.window.WINDOW_WIDTH - 2 * self.scale_x(34, 18),
                self.scale_y(42, 32),
            )
            pygame.draw.rect(surface, (58, 44, 32), warning_rect, border_radius=self.scale(10, 6))
            pygame.draw.rect(surface, (224, 166, 92), warning_rect, 2, border_radius=self.scale(10, 6))
            warning = f"Missing art: {', '.join(missing_assets)}. Fallback tile colors will be used."
            self._draw_wrapped_settings_text(surface, warning, warning_rect.inflate(-self.scale_x(18, 10), -self.scale_y(8, 5)))

        self._render_settings_buttons(surface)

    def _render_settings_buttons(self, surface: pygame.Surface) -> None:
        """Render Settings controls as title-style wood buttons."""
        for key, rect in self.setting_button_rects.items():
            self._render_wood_button(
                surface,
                rect,
                self.button_labels.get(key, key.title()),
                self.hovered_setting_key == key,
                self.font_size(27, 18),
            )

    def _draw_wrapped_settings_text(self, surface: pygame.Surface, text: str, rect: pygame.Rect) -> None:
        """Draw one compact wrapped Settings warning."""
        words = text.split()
        lines = []
        current = ""
        for word in words:
            candidate = word if not current else f"{current} {word}"
            if self.small_font.size(candidate)[0] <= rect.width:
                current = candidate
            else:
                if current:
                    lines.append(current)
                current = word
        if current:
            lines.append(current)

        line_height = self.scale_y(18, 13)
        for index, line in enumerate(lines[:2]):
            rendered = self.small_font.render(line, True, (248, 224, 180))
            surface.blit(rendered, (rect.x, rect.y + index * line_height))

    def on_enter(self) -> None:
        """Activate settings controls."""
        self._refresh_button_text()
        self._hide_all_elements()

    def on_exit(self) -> None:
        """Deactivate settings controls."""
        self._hide_all_elements()
        self.hovered_setting_key = None

    def on_resize(self) -> None:
        """Refresh fonts and layout when size or text scale changes."""
        self._refresh_fonts()
        self._layout_ui()
        self._refresh_button_text()


class CoinFlipScreen(Screen):
    """Animated coin flip that chooses the first drafter."""

    def __init__(self, window: "GameWindow"):
        super().__init__(window)
        self.title_font = None
        self.body_font = None
        self.small_font = None
        self.elapsed = 0.0
        self.first_player = 0
        self.finished = False
        self._consumed = False
        self._refresh_fonts()

    def _refresh_fonts(self) -> None:
        """Refresh coin-flip fonts."""
        self.title_font = pygame.font.Font(None, self.font_size(64, 38))
        self.body_font = pygame.font.Font(None, self.font_size(34, 24))
        self.small_font = pygame.font.Font(None, self.font_size(24, 16))

    def start_flip(self, first_player: int) -> None:
        """Start a new flip animation for the chosen first drafter."""
        self.first_player = first_player
        self.elapsed = 0.0
        self.finished = False
        self._consumed = False

    def handle_events(self, event: pygame.event.Event) -> bool:
        """The coin flip is automatic."""
        return False

    def update(self, time_delta: float) -> None:
        """Advance the flip timer."""
        self.elapsed += time_delta * self.window.animation_speed
        if self.elapsed >= 2.0:
            self.finished = True

    def render(self, surface: pygame.Surface) -> None:
        """Render the coin flip screen."""
        self._render_screen_background(surface, (14, 18, 28))
        title = self.title_font.render("COIN FLIP", True, (238, 214, 142))
        title_rect = title.get_rect(center=(self.window.WINDOW_WIDTH // 2, self.scale_y(110, 78)))
        surface.blit(title, title_rect)

        center = (self.window.WINDOW_WIDTH // 2, self.window.WINDOW_HEIGHT // 2 - self.scale_y(18, 12))
        radius = self.scale(82, 54)
        flipping = not self.finished and int(self.elapsed * 10) % 2 == 0
        label = "P1" if (flipping or self.first_player == 0) else "P2"
        fill = (208, 84, 84) if label == "P1" else (84, 118, 216)
        pygame.draw.circle(surface, fill, center, radius)
        pygame.draw.circle(surface, (248, 232, 166), center, radius, self.scale(5, 3))
        coin_text = self.title_font.render(label, True, (24, 24, 30))
        surface.blit(coin_text, coin_text.get_rect(center=center))

        result = (
            f"Player {self.first_player + 1} drafts first."
            if self.finished
            else "Flipping to decide who drafts first..."
        )
        result_text = self.body_font.render(result, True, (228, 228, 228))
        result_rect = result_text.get_rect(center=(self.window.WINDOW_WIDTH // 2, center[1] + radius + self.scale_y(60, 42)))
        surface.blit(result_text, result_rect)

        hint = self.small_font.render("The draft starts automatically.", True, (160, 168, 180))
        hint_rect = hint.get_rect(center=(self.window.WINDOW_WIDTH // 2, result_rect.bottom + self.scale_y(32, 22)))
        surface.blit(hint, hint_rect)

    def on_enter(self) -> None:
        """Coin flip has no UI elements."""
        pass

    def on_exit(self) -> None:
        """Coin flip has no UI elements."""
        pass

    def on_resize(self) -> None:
        """Refresh fonts after resize."""
        self._refresh_fonts()

    def consume_result(self):
        """Return the chosen first drafter once the animation finishes."""
        if not self.finished or self._consumed:
            return None
        self._consumed = True
        return self.first_player


class DraftScreen(Screen):
    """Pregame drafting screen for the 12-card face-card pool."""

    def __init__(self, window: "GameWindow"):
        super().__init__(window)
        self.title_font = None
        self.body_font = None
        self.small_font = None
        self.card_font = None

        self.card_rects = []
        self.draft_cards = []
        self.available_cards = []
        self.player_hands = {0: [], 1: []}
        self.current_player = 0
        self.kings_drafted = 0
        self.player_cards = []
        self.draft_grid_bottom = 0
        self.tutorial_toggle_rect = None
        self._refresh_fonts()
        self._create_ui()
        self.on_resize()
        self._hide_all_elements()

    def _refresh_fonts(self) -> None:
        """Refresh all draft-phase fonts."""
        self.title_font = pygame.font.Font(None, self.font_size(64, 38))
        self.body_font = pygame.font.Font(None, self.font_size(30, 20))
        self.small_font = pygame.font.Font(None, self.font_size(24, 16))
        self.card_font = pygame.font.Font(None, self.font_size(34, 22))

    def _create_ui(self):
        """Create the 6x2 grid of draft card hitboxes."""
        self._layout_card_rects()

    def _layout_card_rects(self) -> None:
        """Lay out the 6x2 draft grid for the current window size."""
        compact = self.is_compact_layout()
        columns = 3 if compact else 6
        rows = (12 + columns - 1) // columns
        margin = self.scale_x(34, 16)
        col_spacing = self.scale(12, 6)
        row_spacing = self.scale(18, 8)
        available_width = self.window.WINDOW_WIDTH - 2 * margin
        button_width = min(
            self.scale(150, 92),
            (available_width - (columns - 1) * col_spacing) // columns,
        )
        button_height = self.scale_y(74, 54) if compact else self.scale(96, 62)
        grid_width = columns * button_width + (columns - 1) * col_spacing
        start_x = (self.window.WINDOW_WIDTH - grid_width) // 2
        start_y = self.scale_y(230, 158) if compact else self.scale_y(255, 180)

        self.card_rects = []
        for index in range(12):
            row = index // columns
            col = index % columns
            x = start_x + col * (button_width + col_spacing)
            y = start_y + row * (button_height + row_spacing)
            self.card_rects.append(pygame.Rect((x, y), (button_width, button_height)))
        self.draft_grid_bottom = start_y + rows * button_height + (rows - 1) * row_spacing

    def _hide_all_elements(self):
        """Draft cards are rendered manually; no UI elements to hide."""
        pass

    def start_draft(self, draft_cards: list, starting_player: int = 0) -> None:
        """Reset the screen with a fresh shuffled draft pool."""
        self.draft_cards = list(draft_cards)
        self.available_cards = list(draft_cards)
        self.player_hands = {0: [], 1: []}
        self.current_player = starting_player
        self.kings_drafted = 0
        self.player_cards = []
        self._update_buttons()

    def handle_events(self, event: pygame.event.Event) -> bool:
        """Handle draft card picks."""
        if event.type != pygame.MOUSEBUTTONDOWN:
            return False

        if (
            self.window.tutorial_enabled
            and self.tutorial_toggle_rect is not None
            and self.tutorial_toggle_rect.collidepoint(event.pos)
        ):
            self.window.tutorial_enabled = False
            self.tutorial_toggle_rect = None
            return True

        for index, rect in enumerate(self.card_rects):
            if rect.collidepoint(event.pos):
                return self._pick_card(index)

        return False

    def _pick_card(self, index: int):
        """Draft one card and advance the turn order."""
        if index >= len(self.available_cards):
            return True

        card = self.available_cards[index]
        if card is None or not self._can_pick_card(card):
            return True

        self.player_hands[self.current_player].append(card)
        if card.rank == CardRank.KING:
            self.kings_drafted += 1
        self.available_cards[index] = None

        total_picks = len(self.player_hands[0]) + len(self.player_hands[1])
        self._update_buttons()

        if total_picks >= 10:
            self.player_cards = [card for card in self.available_cards if card is not None]
            return "DRAFT_COMPLETE"

        self.current_player = 1 - self.current_player
        self._update_buttons()
        return True

    def _can_pick_card(self, card) -> bool:
        """Only two Kings may be drafted; the remaining two become player cards."""
        return not (card.rank == CardRank.KING and self.kings_drafted >= 2)

    def _update_buttons(self) -> None:
        """Draft cards are rendered manually; no button state to refresh."""
        return

    def update(self, time_delta: float) -> None:
        """Update draft button state."""
        self._update_buttons()

    def render(self, surface: pygame.Surface) -> None:
        """Render draft instructions and current picks."""
        self._render_screen_background(surface, (16, 18, 28))
        self._render_value_legend(surface)
        compact = self.is_compact_layout()

        title = self.title_font.render("INITIAL DRAFT", True, (235, 225, 190))
        title_rect = title.get_rect(center=(self.window.WINDOW_WIDTH // 2, self.scale_y(62, 44) if compact else self.scale_y(90, 64)))
        surface.blit(title, title_rect)

        prompt = self.body_font.render(
            f"Player {self.current_player + 1} picks a card",
            True,
            (220, 220, 220),
        )
        prompt_rect = prompt.get_rect(center=(self.window.WINDOW_WIDTH // 2, self.scale_y(104, 76) if compact else self.scale_y(150, 112)))
        surface.blit(prompt, prompt_rect)

        rules = (
            ["Draft 8 Satyrs/Oracles + 2 Heroes. Remaining Heroes become player cards."]
            if compact
            else [
                "Draft all 4 Satyrs, all 4 Oracles, and only 2 Heroes.",
                "The 2 Heroes left behind become the player cards.",
            ]
        )
        for index, text in enumerate(rules):
            line = self.small_font.render(text, True, (150, 150, 150))
            line_rect = line.get_rect(
                center=(
                    self.window.WINDOW_WIDTH // 2,
                    self.scale_y(134 + index * 18, 104 + index * 14) if compact else self.scale_y(190 + index * 28, 144 + index * 18),
                )
            )
            surface.blit(line, line_rect)

        drafted_low_cards = len(self.player_hands[0]) + len(self.player_hands[1]) - self.kings_drafted
        count_text = (
            f"S/O: {drafted_low_cards}/8 | Heroes: {self.kings_drafted}/2"
            if self.is_compact_layout()
            else f"Satyrs/Oracles drafted: {drafted_low_cards}/8   Heroes drafted: {self.kings_drafted}/2"
        )
        counts = self.small_font.render(count_text, True, (185, 185, 185))
        counts_y = self.draft_grid_bottom + self.scale_y(28, 20)
        counts_rect = counts.get_rect(center=(self.window.WINDOW_WIDTH // 2, counts_y))
        surface.blit(counts, counts_rect)

        for index, rect in enumerate(self.card_rects):
            card = self.available_cards[index] if index < len(self.available_cards) else None
            self._render_draft_card(surface, rect, card)

        margin = self.scale_x(70, 20)
        panel_gap = self.scale_x(60, 12)
        panel_y = counts_y + self.scale_y(32, 22)
        if self.is_compact_layout():
            panel_width = self.window.WINDOW_WIDTH - 2 * margin
            panel_height = max(self.scale_y(66, 54), (self.window.WINDOW_HEIGHT - panel_y - margin - panel_gap) // 2)
            panel_rects = [
                pygame.Rect(margin, panel_y, panel_width, panel_height),
                pygame.Rect(margin, panel_y + panel_height + panel_gap, panel_width, panel_height),
            ]
        else:
            panel_height = max(self.scale_y(210, 150), self.window.WINDOW_HEIGHT - panel_y - margin)
            panel_width = max(
                self.scale_x(300, 220),
                (self.window.WINDOW_WIDTH - 2 * margin - panel_gap) // 2,
            )
            panel_rects = [
                pygame.Rect(margin, panel_y, panel_width, panel_height),
                pygame.Rect(margin + panel_width + panel_gap, panel_y, panel_width, panel_height),
            ]

        self._render_hand_panel(surface, panel_rects[0], "Player 1 Trial Hand", self.player_hands[0], (210, 120, 120))
        self._render_hand_panel(surface, panel_rects[1], "Player 2 Trial Hand", self.player_hands[1], (120, 160, 230))
        self._render_tutorial_overlay(surface)

    def _render_tutorial_overlay(self, surface: pygame.Surface) -> None:
        """Show optional draft tutorial guidance."""
        if not self.window.tutorial_enabled or not self.card_rects:
            self.tutorial_toggle_rect = None
            return

        grid_rect = self.card_rects[0].copy()
        for rect in self.card_rects[1:]:
            grid_rect.union_ip(rect)
        pygame.draw.rect(surface, (252, 222, 104), grid_rect.inflate(self.scale(10, 6), self.scale(10, 6)), 3, border_radius=10)

        text = "Tutorial: click a draft card. Draft all Satyrs and Oracles, but only two Heroes."
        panel_rect = pygame.Rect(
            self.scale_x(22, 14),
            max(self.scale_y(152, 112), grid_rect.top - self.scale_y(58, 42)),
            min(self.scale_x(720, 320), self.window.WINDOW_WIDTH - 2 * self.scale_x(22, 14)),
            self.scale_y(42, 34),
        )
        pygame.draw.rect(surface, (24, 28, 40), panel_rect, border_radius=self.scale(10, 6))
        pygame.draw.rect(surface, (252, 222, 104), panel_rect, 2, border_radius=self.scale(10, 6))
        button_width = min(self.scale_x(132, 92), max(self.scale_x(86, 72), panel_rect.width // 4))
        button_height = max(self.scale_y(24, 20), panel_rect.height - self.scale_y(12, 8))
        self.tutorial_toggle_rect = pygame.Rect(
            panel_rect.right - button_width - self.scale_x(8, 5),
            panel_rect.centery - button_height // 2,
            button_width,
            button_height,
        )
        pygame.draw.rect(surface, (52, 58, 72), self.tutorial_toggle_rect, border_radius=self.scale(8, 5))
        pygame.draw.rect(surface, (252, 222, 104), self.tutorial_toggle_rect, 1, border_radius=self.scale(8, 5))
        off_label = self.small_font.render("Tips Off", True, (240, 236, 214))
        surface.blit(off_label, off_label.get_rect(center=self.tutorial_toggle_rect.center))

        line = self.small_font.render(text, True, (238, 238, 238))
        surface.blit(line, (panel_rect.x + self.scale(12, 8), panel_rect.y + self.scale(11, 7)))

    def on_enter(self) -> None:
        """Manual card rendering needs no UI activation."""
        pass

    def on_exit(self) -> None:
        """Manual card rendering needs no UI teardown."""
        pass

    def on_resize(self) -> None:
        """Refresh fonts and hitboxes after a resize."""
        self._refresh_fonts()
        self._layout_card_rects()

    def get_draft_result(self) -> tuple[list, list, list]:
        """Return the drafted player hands and remaining Kings."""
        return (
            list(self.player_hands[0]),
            list(self.player_hands[1]),
            list(self.player_cards),
        )

    def _format_card(self, card) -> str:
        """Render a compact card label without glyph icons."""
        return get_card_display(card)

    def _muted_family_color(self, suit, enabled: bool = True) -> tuple[int, int, int]:
        """Return a readable pastel version of a family color for draft cards."""
        base = get_family_color(suit)
        target = (238, 236, 220) if enabled else (166, 166, 158)
        amount = 0.58 if enabled else 0.72
        return tuple(int(channel * (1 - amount) + target[index] * amount) for index, channel in enumerate(base))

    def _render_draft_card(self, surface: pygame.Surface, rect: pygame.Rect, card) -> None:
        """Draw one draft card with a vector suit icon."""
        if card is None:
            radius = self.scale(10, 6)
            pygame.draw.rect(surface, (42, 42, 52), rect, border_radius=radius)
            pygame.draw.rect(surface, (90, 90, 100), rect, 2, border_radius=radius)
            taken = self.body_font.render("Taken", True, (165, 165, 165))
            taken_rect = taken.get_rect(center=rect.center)
            surface.blit(taken, taken_rect)
            return

        enabled = self._can_pick_card(card)
        fill = self._muted_family_color(card.suit, enabled)
        border = get_family_color(card.suit) if enabled else (95, 95, 95)
        text_color = (35, 35, 35)

        radius = self.scale(12, 8)
        pygame.draw.rect(surface, fill, rect, border_radius=radius)
        pygame.draw.rect(surface, border, rect, 3, border_radius=radius)

        rank = self.card_font.render(get_rank_name(card.rank), True, text_color)
        rank_rect = rank.get_rect(center=(rect.centerx, rect.y + self.scale(28, 18)))
        surface.blit(rank, rank_rect)

        suit_name = self.small_font.render(get_family_name(card.suit), True, text_color)
        suit_rect = suit_name.get_rect(center=(rect.centerx, rect.centery + self.scale(10, 6)))
        surface.blit(suit_name, suit_rect)

    def _render_hand_panel(
        self,
        surface: pygame.Surface,
        rect: pygame.Rect,
        title: str,
        cards: list,
        accent: tuple[int, int, int],
    ) -> None:
        """Draw one player's drafted hand as visible cards instead of text."""
        radius = self.scale(14, 8)
        pygame.draw.rect(surface, (24, 28, 40), rect, border_radius=radius)
        pygame.draw.rect(surface, accent, rect, 3, border_radius=radius)

        title_text = self.body_font.render(f"{title} ({len(cards)}/5)", True, (230, 230, 230))
        inner_margin = self.scale(18, 10)
        surface.blit(title_text, (rect.x + inner_margin, rect.y + self.scale(14, 10)))

        if rect.height < self.scale_y(112, 86):
            label_y = rect.y + self.scale_y(42, 30)
            label_width = max(self.scale_x(48, 38), (rect.width - 2 * inner_margin - 4 * self.scale(6, 4)) // 5)
            spacing = self.scale(6, 4)
            for index in range(5):
                chip_rect = pygame.Rect(
                    rect.x + inner_margin + index * (label_width + spacing),
                    label_y,
                    label_width,
                    self.scale_y(26, 20),
                )
                pygame.draw.rect(surface, (38, 42, 54), chip_rect, border_radius=self.scale(7, 5))
                pygame.draw.rect(surface, (92, 98, 112), chip_rect, 1, border_radius=self.scale(7, 5))
                if index < len(cards):
                    label = self.small_font.render(get_card_display(cards[index], compact=True), True, (232, 232, 232))
                    surface.blit(label, label.get_rect(center=chip_rect.center))
            return

        card_spacing = self.scale(10, 6)
        card_width = max(
            self.scale(52, 40),
            (rect.width - 2 * inner_margin - 4 * card_spacing) // 5,
        )
        card_height = min(
            max(self.scale(82, 62), rect.height - self.scale(70, 52)),
            self.scale(120, 92),
        )
        start_x = rect.x + inner_margin
        start_y = rect.y + self.scale(58, 42)

        for index in range(5):
            card_rect = pygame.Rect(
                start_x + index * (card_width + card_spacing),
                start_y,
                card_width,
                card_height,
            )
            if index < len(cards):
                self._render_hand_card(surface, card_rect, cards[index], accent)
            else:
                empty_radius = self.scale(10, 6)
                pygame.draw.rect(surface, (38, 42, 54), card_rect, border_radius=empty_radius)
                pygame.draw.rect(surface, (80, 84, 98), card_rect, 2, border_radius=empty_radius)

    def _render_hand_card(
        self,
        surface: pygame.Surface,
        rect: pygame.Rect,
        card,
        accent: tuple[int, int, int],
    ) -> None:
        """Draw one drafted hand card in the bottom hand display."""
        radius = self.scale(10, 6)
        pygame.draw.rect(surface, self._muted_family_color(card.suit), rect, border_radius=radius)
        pygame.draw.rect(surface, accent, rect, 3, border_radius=radius)

        rank = self.small_font.render(get_rank_name(card.rank), True, (35, 35, 35))
        rank_rect = rank.get_rect(center=(rect.centerx, rect.y + self.scale(22, 16)))
        surface.blit(rank, rank_rect)

        suit_name = self.small_font.render(get_family_name(card.suit), True, (35, 35, 35))
        suit_rect = suit_name.get_rect(center=(rect.centerx, rect.centery + self.scale(8, 4)))
        surface.blit(suit_name, suit_rect)

    def _render_value_legend(self, surface: pygame.Surface) -> None:
        """Show the draft-phase values for the three high-rank card types."""
        if self.is_compact_layout():
            return

        panel_rect = pygame.Rect(
            self.scale_x(28, 16),
            self.scale_y(28, 16),
            self.scale_x(230, 170),
            self.scale_y(126, 94),
        )
        radius = self.scale(14, 8)
        pygame.draw.rect(surface, (25, 28, 38), panel_rect, border_radius=radius)
        pygame.draw.rect(surface, (106, 112, 132), panel_rect, 2, border_radius=radius)

        title = self.small_font.render("Draft Value Guide", True, (232, 232, 232))
        surface.blit(title, (panel_rect.x + self.scale(14, 8), panel_rect.y + self.scale(12, 8)))

        lines = [
            get_rank_name_with_value(CardRank.TEN),
            get_rank_name_with_value(CardRank.QUEEN),
            get_rank_name_with_value(CardRank.KING),
        ]
        for index, text in enumerate(lines):
            line = self.small_font.render(text, True, (205, 205, 205))
            surface.blit(
                line,
                (
                    panel_rect.x + self.scale(18, 10),
                    panel_rect.y + self.scale(42, 28) + index * self.scale(24, 16),
                ),
            )


class JackRevealScreen(Screen):
    """Animated pregame reveal for the randomized Jack suit order."""

    ROLE_NAMES = ["Walls", "Traps", "Ballista", "Weapons"]

    def __init__(self, window: "GameWindow"):
        super().__init__(window)
        self.title_font = None
        self.body_font = None
        self.card_font = None
        self.small_font = None

        self.jack_order = []
        self.player_cards = []
        self.elapsed = 0.0
        self.revealed_count = 0
        self.finished = False
        self._consumed = False
        self._refresh_fonts()

    def _refresh_fonts(self) -> None:
        """Refresh reveal fonts after a resize."""
        self.title_font = pygame.font.Font(None, self.font_size(62, 36))
        self.body_font = pygame.font.Font(None, self.font_size(30, 20))
        self.card_font = pygame.font.Font(None, self.font_size(42, 24))
        self.small_font = pygame.font.Font(None, self.font_size(24, 16))

    def start_reveal(self, jack_cards: list, player_cards: list | None = None) -> None:
        """Begin a new autonomous Jack reveal animation."""
        shuffled_jacks = list(jack_cards)
        shuffle(shuffled_jacks)
        self.jack_order = [card.suit for card in shuffled_jacks[:4]]
        self.player_cards = list(player_cards or [])
        self.elapsed = 0.0
        self.revealed_count = 0
        self.finished = False
        self._consumed = False

    def handle_events(self, event: pygame.event.Event) -> bool:
        """The reveal is autonomous; user input is ignored."""
        return False

    def update(self, time_delta: float) -> None:
        """Advance the reveal animation over time."""
        if self.finished or not self.jack_order:
            return

        self.elapsed += time_delta
        reveal_interval = 0.85
        finish_delay = 1.1

        new_revealed = min(4, int(self.elapsed / reveal_interval))
        if new_revealed > self.revealed_count:
            self.revealed_count = new_revealed

        if self.elapsed >= reveal_interval * 4 + finish_delay:
            self.finished = True

    def render(self, surface: pygame.Surface) -> None:
        """Render the animated Jack order reveal."""
        self._render_screen_background(surface, (12, 16, 26))

        title = self.title_font.render("THE OMENS DETERMINE THE TRIAL", True, (225, 225, 205))
        title_rect = title.get_rect(center=(self.window.WINDOW_WIDTH // 2, self.scale_y(100, 74)))
        surface.blit(title, title_rect)

        subtitle = self.body_font.render("Resolving the color roles...", True, (150, 150, 170))
        subtitle_rect = subtitle.get_rect(center=(self.window.WINDOW_WIDTH // 2, self.scale_y(150, 112)))
        surface.blit(subtitle, subtitle_rect)

        compact = self.is_compact_layout()
        columns = 2 if compact else 4
        spacing = self.scale(24, 10)
        card_width = min(
            self.scale_x(150, 104) if compact else self.scale(180, 100),
            (self.window.WINDOW_WIDTH - self.scale_x(80, 32) - (columns - 1) * spacing) // columns,
        )
        card_height = max(self.scale_y(112, 84), int(card_width * (0.78 if compact else 1.22)))
        rows = (4 + columns - 1) // columns
        total_width = columns * card_width + (columns - 1) * spacing
        start_x = (self.window.WINDOW_WIDTH - total_width) // 2
        y = self.scale_y(170, 122) if compact else self.scale_y(260, 190)
        border_radius = self.scale(12, 8)

        for index in range(4):
            row = index // columns
            col = index % columns
            rect = pygame.Rect(
                start_x + col * (card_width + spacing),
                y + row * (card_height + spacing),
                card_width,
                card_height,
            )
            pygame.draw.rect(surface, (62, 68, 88), rect, border_radius=border_radius)
            pygame.draw.rect(surface, (130, 136, 156), rect, 2, border_radius=border_radius)

            if index < self.revealed_count:
                suit = self.jack_order[index]
                card_text = self.card_font.render("Omen", True, (235, 235, 235))
                card_rect = card_text.get_rect(center=(rect.centerx, rect.y + int(rect.height * 0.28)))
                surface.blit(card_text, card_rect)
                draw_suit_icon(surface, suit, (rect.centerx, rect.y + int(rect.height * 0.52)), size=self.scale(18, 10))

                color_name = self.small_font.render(get_family_name(suit), True, (220, 220, 220))
                color_rect = color_name.get_rect(center=(rect.centerx, rect.y + int(rect.height * 0.68)))
                surface.blit(color_name, color_rect)

                role_text = self.body_font.render(self.ROLE_NAMES[index], True, (235, 196, 100))
                role_rect = role_text.get_rect(center=(rect.centerx, rect.y + int(rect.height * 0.86)))
                surface.blit(role_text, role_rect)
            elif index == self.revealed_count and not self.finished:
                shuffle_text = self.card_font.render("Omen", True, (190, 190, 220))
                shuffle_rect = shuffle_text.get_rect(center=(rect.centerx, rect.y + int(rect.height * 0.28)))
                surface.blit(shuffle_text, shuffle_rect)
                cycling_suit = self._cycling_suit()
                draw_suit_icon(
                    surface,
                    cycling_suit,
                    (rect.centerx, rect.y + int(rect.height * 0.52)),
                    size=self.scale(18, 10),
                    color=(190, 190, 220),
                )

                color_name = self.small_font.render(get_family_name(cycling_suit), True, (185, 185, 205))
                color_rect = color_name.get_rect(center=(rect.centerx, rect.y + int(rect.height * 0.68)))
                surface.blit(color_name, color_rect)

                pending = self.small_font.render("shuffling...", True, (165, 165, 180))
                pending_rect = pending.get_rect(center=(rect.centerx, rect.y + int(rect.height * 0.86)))
                surface.blit(pending, pending_rect)
            else:
                hidden = self.card_font.render("?", True, (155, 155, 170))
                hidden_rect = hidden.get_rect(center=(rect.centerx, rect.y + int(rect.height * 0.44)))
                surface.blit(hidden, hidden_rect)

        footer = self.small_font.render("The Omens reveal automatically, then the labyrinth begins.", True, (145, 145, 160))
        grid_bottom = y + rows * card_height + (rows - 1) * spacing
        footer_rect = footer.get_rect(center=(self.window.WINDOW_WIDTH // 2, grid_bottom + self.scale_y(28, 20)))
        surface.blit(footer, footer_rect)

        if self.player_cards:
            card_w = self.scale_x(160, 112) if compact else self.scale_x(170, 120)
            card_h = self.scale_y(78, 58) if compact else self.scale_y(90, 64)
            gap = self.scale_x(24, 14) if compact else self.scale_x(80, 48)
            player_y = min(
                footer_rect.bottom + self.scale_y(16, 10),
                self.window.WINDOW_HEIGHT - card_h - self.scale_y(18, 12),
            )
            left_rect = pygame.Rect(self.window.WINDOW_WIDTH // 2 - gap // 2 - card_w, player_y, card_w, card_h)
            right_rect = pygame.Rect(self.window.WINDOW_WIDTH // 2 + gap // 2, player_y, card_w, card_h)
            self._render_player_card(surface, left_rect, "P1 Player Card", self.player_cards[0] if len(self.player_cards) > 0 else None)
            self._render_player_card(surface, right_rect, "P2 Player Card", self.player_cards[1] if len(self.player_cards) > 1 else None)

    def on_enter(self) -> None:
        """Nothing to show outside the rendered animation."""
        pass

    def on_exit(self) -> None:
        """Nothing to hide outside the rendered animation."""
        pass

    def on_resize(self) -> None:
        """Refresh reveal fonts when the window changes size."""
        self._refresh_fonts()

    def consume_result(self):
        """Return the revealed suit order once, after the animation finishes."""
        if not self.finished or self._consumed:
            return None
        self._consumed = True
        return list(self.jack_order)

    def _cycling_suit(self) -> CardSuit:
        """Return a fast-changing suit for the active reveal slot."""
        suits = [CardSuit.HEARTS, CardSuit.DIAMONDS, CardSuit.CLUBS, CardSuit.SPADES]
        return suits[int(self.elapsed * 10) % len(suits)]

    def _format_player_card(self, player_id: int) -> str:
        """Render one of the leftover Kings used as a player card."""
        if player_id >= len(self.player_cards):
            return "-"
        card = self.player_cards[player_id]
        return get_card_display(card)

    def _render_player_card(self, surface: pygame.Surface, rect: pygame.Rect, title: str, card) -> None:
        """Draw one leftover King card without font suit glyphs."""
        radius = self.scale(12, 8)
        pygame.draw.rect(surface, (240, 240, 232), rect, border_radius=radius)
        pygame.draw.rect(surface, (170, 150, 105), rect, 3, border_radius=radius)

        heading = self.small_font.render(title, True, (35, 35, 35))
        heading_rect = heading.get_rect(center=(rect.centerx, rect.y + self.scale(16, 12)))
        surface.blit(heading, heading_rect)

        if card is None:
            return

        rank = self.body_font.render(get_rank_name_with_value(card.rank), True, (35, 35, 35))
        rank_rect = rank.get_rect(center=(rect.centerx, rect.y + self.scale(42, 30)))
        surface.blit(rank, rank_rect)

        draw_suit_icon(
            surface,
            card.suit,
            (rect.centerx, rect.y + self.scale(66, 48)),
            size=self.scale(14, 8),
            color=get_family_color(card.suit),
        )


class GameOverScreen(Screen):
    """Game over screen showing the winner and final damage totals."""

    def __init__(self, window: "GameWindow"):
        super().__init__(window)
        self.title_font = None
        self.subtitle_font = None
        self.body_font = None
        self.small_font = None

        self.winner_text = "Player 1 Wins!"
        self.damage_text = "Final damage - P1: 0 | P2: 0"
        self.match_summary = {}

        self.play_again_button = None
        self.menu_button = None
        self.game_over_button_rects: dict[str, pygame.Rect] = {}
        self.hovered_button = None
        self._refresh_fonts()
        self._create_ui()
        self.on_resize()
        self._hide_all_elements()

    def _refresh_fonts(self) -> None:
        """Refresh game-over fonts after a resize."""
        self.title_font = pygame.font.Font(None, self.font_size(72, 42))
        self.subtitle_font = pygame.font.Font(None, self.font_size(40, 26))
        self.body_font = pygame.font.Font(None, self.font_size(32, 22))
        self.small_font = pygame.font.Font(None, self.font_size(21, 15))

    def _create_ui(self):
        """Create UI elements."""
        self.play_again_button = pygame_gui.elements.UIButton(
            relative_rect=pygame.Rect((0, 0), (1, 1)),
            text="Play Again",
            manager=self.ui_manager,
            object_id="play_again_button"
        )

        self.menu_button = pygame_gui.elements.UIButton(
            relative_rect=pygame.Rect((0, 0), (1, 1)),
            text="Main Menu",
            manager=self.ui_manager,
            object_id="menu_button"
        )

    def _layout_ui(self) -> None:
        """Lay out game-over buttons for the current window size."""
        button_width = min(self.scale_x(360, 240), self.window.WINDOW_WIDTH - 2 * self.scale_x(40, 18))
        button_height = self._get_wood_icon_height_for_width(button_width)
        center_x = (self.window.WINDOW_WIDTH - button_width) // 2
        gap = self.scale_y(2, 1)
        menu_y = self.window.WINDOW_HEIGHT - button_height - self.scale_y(10, 6)
        play_again_y = menu_y - button_height - gap

        self.game_over_button_rects = {
            "play": pygame.Rect(center_x, play_again_y, button_width, button_height),
            "menu": pygame.Rect(center_x, menu_y, button_width, button_height),
        }
        for key, button in [("play", self.play_again_button), ("menu", self.menu_button)]:
            rect = self.game_over_button_rects[key]
            button.set_relative_position((rect.x, rect.y))
            button.set_dimensions((rect.width, rect.height))

    def set_result(self, winner: int, p1_damage: int, p2_damage: int, match_summary: dict | None = None) -> None:
        """Set winner screen text."""
        self.winner_text = f"Player {winner + 1} Wins!"
        self.damage_text = f"Final damage - P1: {p1_damage} | P2: {p2_damage}"
        self.match_summary = match_summary or {}

    def _hide_all_elements(self):
        """Hide all UI elements initially."""
        self.play_again_button.hide()
        self.menu_button.hide()

    def handle_events(self, event: pygame.event.Event) -> bool:
        """Handle game-over screen events."""
        if event.type == pygame.MOUSEMOTION:
            self.hovered_button = self._game_over_button_at(event.pos)
            return False
        if event.type == pygame.MOUSEBUTTONDOWN:
            key = self._game_over_button_at(event.pos)
            if key == "play":
                return "PLAY"
            if key == "menu":
                return "MENU"
            return False
        if event.type == pygame_gui.UI_BUTTON_PRESSED:
            if event.ui_element == self.play_again_button:
                return "PLAY"
            if event.ui_element == self.menu_button:
                return "MENU"
        return False

    def _game_over_button_at(self, pos: tuple[int, int]) -> str | None:
        """Return the Game Over wood button at a mouse position."""
        for key, rect in self.game_over_button_rects.items():
            if rect.collidepoint(pos):
                return key
        return None

    def update(self, time_delta: float) -> None:
        """Update."""
        pass

    def render(self, surface: pygame.Surface) -> None:
        """Render game-over screen."""
        self._render_screen_background(surface, (18, 18, 28))

        title = self.title_font.render("VICTORY", True, (220, 180, 90))
        title_rect = title.get_rect(center=(self.window.WINDOW_WIDTH // 2, self.scale_y(150, 110)))
        surface.blit(title, title_rect)

        winner = self.subtitle_font.render(self.winner_text, True, (230, 230, 230))
        winner_rect = winner.get_rect(center=(self.window.WINDOW_WIDTH // 2, self.scale_y(260, 192)))
        surface.blit(winner, winner_rect)

        damage = self.body_font.render(self.damage_text, True, (170, 170, 170))
        damage_rect = damage.get_rect(center=(self.window.WINDOW_WIDTH // 2, self.scale_y(318, 232)))
        surface.blit(damage, damage_rect)

        self._render_match_summary(surface, damage_rect.bottom + self.scale_y(20, 14))

        prompt = self.body_font.render("Choose what to do next.", True, (140, 140, 140))
        button_top = min(rect.top for rect in self.game_over_button_rects.values()) if self.game_over_button_rects else self.window.WINDOW_HEIGHT
        prompt_rect = prompt.get_rect(center=(self.window.WINDOW_WIDTH // 2, button_top - self.scale_y(12, 8)))
        surface.blit(prompt, prompt_rect)
        self._render_game_over_buttons(surface)

    def _render_game_over_buttons(self, surface: pygame.Surface) -> None:
        """Render Play Again and Main Menu as wood buttons."""
        labels = {"play": "Play Again", "menu": "Main Menu"}
        for key, rect in self.game_over_button_rects.items():
            self._render_wood_button(
                surface,
                rect,
                labels[key],
                self.hovered_button == key,
                self.font_size(34, 24),
            )

    def _render_match_summary(self, surface: pygame.Surface, start_y: int) -> None:
        """Render final damage cards, recent requests, and major events."""
        if not self.match_summary:
            return

        margin = self.scale_x(56, 20)
        panel_rect = pygame.Rect(
            margin,
            start_y,
            self.window.WINDOW_WIDTH - 2 * margin,
            min(self.scale_y(220, 160), self.window.WINDOW_HEIGHT - start_y - self.scale_y(210, 150)),
        )
        if panel_rect.height < self.scale_y(120, 88):
            return

        pygame.draw.rect(surface, (28, 32, 44), panel_rect, border_radius=self.scale(14, 8))
        pygame.draw.rect(surface, (104, 114, 138), panel_rect, 1, border_radius=self.scale(14, 8))

        title = self.body_font.render("Match Summary", True, (238, 214, 142))
        surface.blit(title, (panel_rect.x + self.scale(18, 10), panel_rect.y + self.scale(10, 7)))

        damage_cards = self.match_summary.get("damage_cards", {})
        p1_cards = ", ".join(get_card_display(card, compact=True) for card in damage_cards.get(0, [])[-6:]) or "None"
        p2_cards = ", ".join(get_card_display(card, compact=True) for card in damage_cards.get(1, [])[-6:]) or "None"
        lines = [
            f"P1 damage: {p1_cards}",
            f"P2 damage: {p2_cards}",
        ]
        lines.extend(self.match_summary.get("appeasing", [])[-2:])
        lines.extend(self.match_summary.get("requests", [])[-2:])
        lines.extend(self.match_summary.get("events", [])[-3:])

        text_rect = pygame.Rect(
            panel_rect.x + self.scale(18, 10),
            panel_rect.y + self.scale(48, 34),
            panel_rect.width - self.scale(36, 20),
            panel_rect.height - self.scale(58, 40),
        )
        self._draw_wrapped_summary(surface, lines, text_rect, max_lines=8)

    def _draw_wrapped_summary(
        self,
        surface: pygame.Surface,
        lines: list[str],
        rect: pygame.Rect,
        max_lines: int,
    ) -> None:
        """Draw a wrapped summary list."""
        y = rect.y
        line_height = self.scale_y(21, 15)
        rendered = 0
        for line in lines:
            words = line.split()
            current = ""
            for word in words:
                candidate = word if not current else f"{current} {word}"
                if self.small_font.size(candidate)[0] <= rect.width:
                    current = candidate
                else:
                    if current and rendered < max_lines:
                        surface.blit(self.small_font.render(current, True, (222, 226, 232)), (rect.x, y))
                        y += line_height
                        rendered += 1
                    current = word
            if current and rendered < max_lines:
                surface.blit(self.small_font.render(current, True, (222, 226, 232)), (rect.x, y))
                y += line_height
                rendered += 1
            if rendered >= max_lines:
                break

    def on_enter(self) -> None:
        """Activate game-over screen."""
        self.play_again_button.hide()
        self.menu_button.hide()

    def on_exit(self) -> None:
        """Deactivate game-over screen."""
        self.play_again_button.hide()
        self.menu_button.hide()
        self.hovered_button = None

    def on_resize(self) -> None:
        """Refresh fonts and buttons after a resize."""
        self._refresh_fonts()
        self._layout_ui()


class ScreenManager:
    """Manages screen transitions."""

    INTRO_MUSIC_SCREENS = {
        ScreenType.START,
        ScreenType.COIN_FLIP,
        ScreenType.DRAFT,
        ScreenType.JACK_REVEAL,
        ScreenType.GAME_OVER,
    }
    
    def __init__(self, window: "GameWindow"):
        self.window = window
        self.screens: dict[ScreenType, Screen] = {}
        self.current_screen: ScreenType = None
        self.next_screen: ScreenType = None
    
    def add_screen(self, screen_type: ScreenType, screen: Screen) -> None:
        """Add a screen to the manager."""
        self.screens[screen_type] = screen
    
    def set_screen(self, screen_type: ScreenType) -> None:
        """Switch to a screen."""
        if self.current_screen is not None:
            self.screens[self.current_screen].on_exit()
        
        self.current_screen = screen_type
        self.screens[screen_type].on_enter()
        self._sync_music_for_screen(screen_type)

    def _sync_music_for_screen(self, screen_type: ScreenType) -> None:
        """Play the looping track that belongs to the active screen."""
        audio = getattr(self.window, "audio", None)
        if audio is None:
            return
        if screen_type in self.INTRO_MUSIC_SCREENS:
            audio.play_intro_music()
        elif screen_type == ScreenType.GAME:
            audio.play_phase_music()
    
    def get_current(self) -> Screen:
        """Get current screen."""
        return self.screens[self.current_screen]
    
    def handle_events(self, event: pygame.event.Event):
        """Handle event on current screen."""
        return self.get_current().handle_events(event)
    
    def update(self, time_delta: float) -> None:
        """Update current screen."""
        self.get_current().update(time_delta)
    
    def render(self, surface: pygame.Surface) -> None:
        """Render current screen."""
        self.get_current().render(surface)

    def handle_resize(self) -> None:
        """Notify every screen that the window size changed."""
        for screen in self.screens.values():
            screen.on_resize()
