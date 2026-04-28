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
    STONE_PANEL_PATH = ASSET_ROOT / "stone.png"
    MEDIEVAL_SHARP_PATH = ASSET_ROOT / "MedievalSharp.ttf"
    WOOD_LABEL_CENTER_Y_RATIO = 0.50
    
    def __init__(self, window: "GameWindow"):
        self.window = window
        self.ui_manager = window.ui_manager
        self._background_base = self._load_image(self.PAN_BACKGROUND_PATH)
        self._background_cache: dict[tuple[int, int], pygame.Surface] = {}
        self._wood_icon_base = self._crop_wood_icon(self._load_image(self.PAN_ICON_PATH))
        self._wood_icon_cache: dict[tuple[tuple[int, int], bool], pygame.Surface] = {}
        self._stone_panel_base = self._crop_stone_panel(self._load_image(self.STONE_PANEL_PATH))
        self._stone_panel_cache: dict[tuple[int, int], pygame.Surface] = {}
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

    def _crop_stone_panel(self, image: pygame.Surface | None) -> pygame.Surface | None:
        """Trim transparent slack around the stone art so the plaque can fill more of each box."""
        if image is None:
            return None
        bounds = image.get_bounding_rect(min_alpha=6)
        if bounds.width <= 0 or bounds.height <= 0:
            return image
        pad = 4
        left = max(0, bounds.x - pad)
        top = max(0, bounds.y - pad)
        right = min(image.get_width(), bounds.right + pad)
        bottom = min(image.get_height(), bounds.bottom + pad)
        return image.subsurface(pygame.Rect(left, top, right - left, bottom - top)).copy()

    def _get_title_style_font(self, size: int) -> pygame.font.Font:
        """Return a bold serif font that echoes the title lettering."""
        size = max(1, size)
        if size not in self._title_style_font_cache:
            # Try MedievalSharp first from assets
            if self.MEDIEVAL_SHARP_PATH.exists():
                self._title_style_font_cache[size] = pygame.font.Font(str(self.MEDIEVAL_SHARP_PATH), size)
            else:
                # Fall back to system serif fonts
                for family in ["georgia", "garamond", "timesnewroman", "times new roman"]:
                    font_path = pygame.font.match_font(family, bold=True)
                    if font_path is not None:
                        self._title_style_font_cache[size] = pygame.font.Font(font_path, size)
                        break
                else:
                    self._title_style_font_cache[size] = pygame.font.Font(None, size)
        return self._title_style_font_cache[size]

    def _get_game_font(self, size: int) -> pygame.font.Font:
        """Return a game-style font, preferring MedievallSharp if available."""
        # Try MedievalSharp from assets first, then fall back to default
        if self.MEDIEVAL_SHARP_PATH.exists():
            return pygame.font.Font(str(self.MEDIEVAL_SHARP_PATH), size)
        return pygame.font.Font(None, size)

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

    def _point_hits_surface_alpha(
        self,
        rect: pygame.Rect,
        pos: tuple[int, int],
        surface: pygame.Surface | None,
        alpha_threshold: int = 12,
    ) -> bool:
        """Return True when a point hits a non-transparent pixel of a rendered surface."""
        if not rect.collidepoint(pos):
            return False
        if surface is None or rect.width <= 0 or rect.height <= 0:
            return True

        local_x = pos[0] - rect.x
        local_y = pos[1] - rect.y
        if not (0 <= local_x < surface.get_width() and 0 <= local_y < surface.get_height()):
            return False
        return surface.get_at((int(local_x), int(local_y))).a >= alpha_threshold

    def _point_hits_wood_icon(self, rect: pygame.Rect, pos: tuple[int, int], alpha_threshold: int = 12) -> bool:
        """Return True when a point hits the visible wood-button art instead of its transparent padding."""
        return self._point_hits_surface_alpha(
            rect,
            pos,
            self._get_scaled_wood_icon(rect.size, False),
            alpha_threshold=alpha_threshold,
        )

    def _blit_scaled_patch(
        self,
        target: pygame.Surface,
        source: pygame.Surface,
        src_rect: pygame.Rect,
        dst_rect: pygame.Rect,
    ) -> None:
        """Scale one image patch into its destination rect."""
        if src_rect.width <= 0 or src_rect.height <= 0 or dst_rect.width <= 0 or dst_rect.height <= 0:
            return
        patch = source.subsurface(src_rect)
        if patch.get_size() != dst_rect.size:
            patch = pygame.transform.smoothscale(patch, dst_rect.size)
        target.blit(patch, dst_rect.topleft)

    def _get_scaled_stone_panel(self, size: tuple[int, int]) -> pygame.Surface | None:
        """Return stone art stretched with preserved borders so it fits any panel size."""
        if self._stone_panel_base is None or size[0] <= 0 or size[1] <= 0:
            return None
        if size not in self._stone_panel_cache:
            panel = pygame.Surface(size, pygame.SRCALPHA)
            src_w = self._stone_panel_base.get_width()
            src_h = self._stone_panel_base.get_height()
            src_border_x = max(1, int(src_w * 0.125))
            src_border_y = max(1, int(src_h * 0.125))
            # Cap preserved border thickness by width too, so tall plaques keep a usable center.
            dst_border_x = min(
                max(
                    self.scale_x(18, 12),
                    min(int(size[1] * 0.20), int(size[0] * 0.125)),
                ),
                max(1, size[0] // 3),
            )
            dst_border_y = min(
                max(
                    self.scale_y(14, 8),
                    min(int(size[1] * 0.16), int(size[0] * 0.20)),
                ),
                max(1, size[1] // 3),
            )
            src_x = [0, src_border_x, src_w - src_border_x, src_w]
            src_y = [0, src_border_y, src_h - src_border_y, src_h]
            dst_x = [0, dst_border_x, size[0] - dst_border_x, size[0]]
            dst_y = [0, dst_border_y, size[1] - dst_border_y, size[1]]
            for row in range(3):
                for col in range(3):
                    self._blit_scaled_patch(
                        panel,
                        self._stone_panel_base,
                        pygame.Rect(
                            src_x[col],
                            src_y[row],
                            src_x[col + 1] - src_x[col],
                            src_y[row + 1] - src_y[row],
                        ),
                        pygame.Rect(
                            dst_x[col],
                            dst_y[row],
                            dst_x[col + 1] - dst_x[col],
                            dst_y[row + 1] - dst_y[row],
                        ),
                    )
            self._stone_panel_cache[size] = panel
        return self._stone_panel_cache[size]

    @staticmethod
    def _shift_color(color: tuple[int, int, int], delta: int) -> tuple[int, int, int]:
        """Lighten or darken a color by a fixed delta."""
        return tuple(max(0, min(255, channel + delta)) for channel in color)

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

    def _render_wood_panel(
        self,
        surface: pygame.Surface,
        rect: pygame.Rect,
        border_color: tuple[int, int, int] | None = None,
        dim_alpha: int = 94,
    ) -> None:
        """Render a large text/panel box with the shared wood art."""
        icon = self._get_scaled_wood_icon(rect.size, False)
        if icon is not None:
            if dim_alpha > 0:
                icon = icon.copy()
                shade = max(0, 255 - dim_alpha)
                icon.fill((shade, shade, shade, 255), special_flags=pygame.BLEND_RGBA_MULT)
            surface.blit(icon, rect.topleft)
        else:
            pygame.draw.rect(surface, (72, 46, 28), rect, border_radius=self.scale(12, 8))

        if border_color is not None:
            pygame.draw.rect(surface, border_color, rect, self.scale(3, 2), border_radius=self.scale(14, 8))

    def _render_stone_panel(
        self,
        surface: pygame.Surface,
        rect: pygame.Rect,
        dim_alpha: int = 34,
        shadow_alpha: int = 72,
    ) -> None:
        """Render a shared stone plaque without any extra highlight outline."""
        if rect.width <= 0 or rect.height <= 0:
            return

        panel = self._get_scaled_stone_panel(rect.size)
        if panel is not None:
            if dim_alpha > 0:
                panel = panel.copy()
                shade = max(0, 255 - dim_alpha)
                panel.fill((shade, shade, shade, 255), special_flags=pygame.BLEND_RGBA_MULT)
            surface.blit(panel, rect.topleft)
        else:
            pygame.draw.rect(surface, (92, 88, 74), rect, border_radius=self.scale(12, 8))

    def _get_stone_content_rect(
        self,
        rect: pygame.Rect,
        *,
        extra_x: int = 0,
        extra_top: int = 0,
        extra_bottom: int = 0,
    ) -> pygame.Rect:
        """Return a text-safe inner rect that stays away from moss and stone borders."""
        pad_x = min(
            max(
                self.scale_x(18, 12),
                min(int(rect.height * 0.19), int(rect.width * 0.125)),
            ) + extra_x,
            max(1, rect.width // 3),
        )
        pad_top = min(
            max(
                self.scale_y(12, 8),
                min(int(rect.height * 0.14), int(rect.width * 0.18)),
            ) + extra_top,
            max(1, rect.height // 3),
        )
        pad_bottom = min(
            max(
                self.scale_y(11, 7),
                min(int(rect.height * 0.11), int(rect.width * 0.16)),
            ) + extra_bottom,
            max(1, rect.height // 3),
        )
        return pygame.Rect(
            rect.x + pad_x,
            rect.y + pad_top,
            max(1, rect.width - 2 * pad_x),
            max(1, rect.height - pad_top - pad_bottom),
        )

    def _render_carved_text(
        self,
        surface: pygame.Surface,
        font: pygame.font.Font,
        text: str,
        color: tuple[int, int, int],
        position: tuple[int, int],
        anchor: str = "topleft",
    ) -> pygame.Rect:
        """Render dark beveled lettering that reads like an engraving in stone."""
        mid_tone = color if sum(color) <= 240 else self._shift_color(color, -128)
        face_color = self._shift_color(mid_tone, -44)
        edge_light = self._shift_color(mid_tone, 34)
        edge_dark = self._shift_color(mid_tone, -86)
        main = font.render(text, True, face_color)
        light = font.render(text, True, edge_light)
        dark = font.render(text, True, edge_dark)
        rect = main.get_rect()
        setattr(rect, anchor, position)
        offset = self.scale(1, 1)
        for dx, dy in [(-offset, 0), (0, -offset), (-offset, -offset)]:
            surface.blit(light, rect.move(dx, dy))
        for dx, dy in [(offset, 0), (0, offset), (offset, offset)]:
            surface.blit(dark, rect.move(dx, dy))
        surface.blit(main, rect)
        return rect

    def _render_outlined_text(
        self,
        surface: pygame.Surface,
        font: pygame.font.Font,
        text: str,
        face_color: tuple[int, int, int],
        outline_color: tuple[int, int, int],
        position: tuple[int, int],
        anchor: str = "topleft",
        outline_width: int | None = None,
    ) -> pygame.Rect:
        """Render bright text with a small dark outline for busy backgrounds."""
        main = font.render(text, True, face_color)
        outline = font.render(text, True, outline_color)
        rect = main.get_rect()
        setattr(rect, anchor, position)
        width = outline_width if outline_width is not None else self.scale(1, 1)
        for dx, dy in [
            (-width, 0),
            (width, 0),
            (0, -width),
            (0, width),
            (-width, -width),
            (-width, width),
            (width, -width),
            (width, width),
        ]:
            surface.blit(outline, rect.move(dx, dy))
        surface.blit(main, rect)
        return rect

    def _wrap_text_lines(
        self,
        text: str,
        font: pygame.font.Font,
        max_width: int,
        max_lines: int,
    ) -> list[str]:
        """Wrap text to the given pixel width and cap the number of lines."""
        words = text.split()
        lines = []
        current = ""
        for word in words:
            candidate = word if not current else f"{current} {word}"
            if font.size(candidate)[0] <= max_width:
                current = candidate
            else:
                if current:
                    lines.append(current)
                current = word
        if current:
            lines.append(current)
        return lines[:max_lines]

    def _draw_wrapped_carved_text(
        self,
        surface: pygame.Surface,
        text: str,
        font: pygame.font.Font,
        color: tuple[int, int, int],
        rect: pygame.Rect,
        line_height: int,
        max_lines: int,
        align: str = "left",
    ) -> None:
        """Draw wrapped readable text inside a stone panel."""
        max_visible_lines = min(max_lines, max(1, rect.height // max(1, line_height)))
        lines = self._wrap_text_lines(text, font, rect.width, max_visible_lines)
        old_clip = surface.get_clip()
        surface.set_clip(rect)
        for index, line in enumerate(lines):
            y = rect.y + index * line_height
            if align == "center":
                self._render_carved_text(surface, font, line, color, (rect.centerx, y), anchor="midtop")
            else:
                self._render_carved_text(surface, font, line, color, (rect.x, y))
        surface.set_clip(old_clip)

    def _get_fitted_game_font(
        self,
        text: str,
        preferred_size: int,
        rect: pygame.Rect,
        max_lines: int,
        min_size: int,
    ) -> pygame.font.Font:
        """Return the largest game font that fits the wrapped text into the rect."""
        for size in range(max(preferred_size, min_size), min_size - 1, -1):
            font = self._get_game_font(size)
            lines = self._wrap_text_lines(text, font, rect.width, 999)
            if len(lines) <= max_lines and len(lines) * font.get_linesize() <= rect.height:
                return font
        return self._get_game_font(min_size)

    @staticmethod
    def _overlap_area(first: pygame.Rect, second: pygame.Rect) -> int:
        """Return the overlapping area between two rects."""
        clipped = first.clip(second)
        return clipped.width * clipped.height

    def _clamp_panel_rect(self, rect: pygame.Rect, margin: int) -> pygame.Rect:
        """Keep a floating panel inside the current screen bounds."""
        max_x = max(margin, self.window.WINDOW_WIDTH - rect.width - margin)
        max_y = max(margin, self.window.WINDOW_HEIGHT - rect.height - margin)
        rect.x = max(margin, min(rect.x, max_x))
        rect.y = max(margin, min(rect.y, max_y))
        return rect

    def _choose_tutorial_panel_rect(
        self,
        target_rect: pygame.Rect,
        size: tuple[int, int],
        avoid_rects: list[pygame.Rect],
    ) -> pygame.Rect:
        """Choose a tutorial panel position that avoids the target and key UI."""
        width, height = size
        margin = self.scale(18, 12)
        gap = self.scale(14, 8)
        target = target_rect.copy()
        candidates = [
            pygame.Rect(target.centerx - width // 2, target.top - height - gap, width, height),
            pygame.Rect(target.centerx - width // 2, target.bottom + gap, width, height),
            pygame.Rect(target.left - width - gap, target.centery - height // 2, width, height),
            pygame.Rect(target.right + gap, target.centery - height // 2, width, height),
            pygame.Rect(margin, margin, width, height),
            pygame.Rect(self.window.WINDOW_WIDTH - width - margin, margin, width, height),
            pygame.Rect(margin, self.window.WINDOW_HEIGHT - height - margin, width, height),
            pygame.Rect(self.window.WINDOW_WIDTH - width - margin, self.window.WINDOW_HEIGHT - height - margin, width, height),
            pygame.Rect((self.window.WINDOW_WIDTH - width) // 2, margin, width, height),
            pygame.Rect((self.window.WINDOW_WIDTH - width) // 2, self.window.WINDOW_HEIGHT - height - margin, width, height),
        ]

        protected_rects = [target] + [rect for rect in avoid_rects if rect.width > 0 and rect.height > 0]

        def score(rect: pygame.Rect) -> tuple[int, int]:
            clamped = self._clamp_panel_rect(rect.copy(), margin)
            overlap = sum(self._overlap_area(clamped, protected) for protected in protected_rects)
            distance = abs(clamped.centerx - target.centerx) + abs(clamped.centery - target.centery)
            return overlap, distance

        return self._clamp_panel_rect(min(candidates, key=score).copy(), margin)
    
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
        self.title_font = self._get_game_font(self.font_size(72, 42))
        self.info_font = self._get_game_font(self.font_size(24, 18))
        self.menu_font = self._make_title_style_font(self.font_size(42, 30))

    def _make_title_style_font(self, size: int) -> pygame.font.Font:
        """Return a large serif font that sits closer to the title lettering."""
        # Try MedievalSharp from assets first
        if self.MEDIEVAL_SHARP_PATH.exists():
            return pygame.font.Font(str(self.MEDIEVAL_SHARP_PATH), size)
        # Fall back to system serif fonts
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
            if self._point_hits_surface_alpha(rect, pos, self._get_scaled_icon(rect.size, False)):
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
        self.title_font = self._get_game_font(self.font_size(64, 38))
        self.heading_font = self._get_game_font(self.font_size(30, 22))
        self.body_font = self._get_game_font(self.font_size(24, 17))
        self.small_font = self._get_game_font(self.font_size(22, 16))

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
            self.hovered_button = "back" if self._point_hits_wood_icon(self.back_button_rect, event.pos) else None
            return False
        if event.type == pygame.MOUSEBUTTONDOWN and self._point_hits_wood_icon(self.back_button_rect, event.pos):
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

        header_rect = pygame.Rect(
            self.scale_x(64, 26),
            self.scale_y(18, 12),
            self.window.WINDOW_WIDTH - 2 * self.scale_x(64, 26),
            self.scale_y(138, 104),
        )
        self._render_wood_panel(surface, header_rect, dim_alpha=78)
        header_content = header_rect.inflate(-self.scale_x(28, 16), -self.scale_y(18, 10))

        title_area = pygame.Rect(
            header_content.x,
            header_content.y + self.scale_y(4, 2),
            header_content.width,
            self.scale_y(42, 30),
        )
        title_font = self._get_fitted_game_font(
            "HOW TO PLAY",
            self.font_size(60, 36),
            title_area,
            1,
            self.font_size(28, 20),
        )
        title = title_font.render("HOW TO PLAY", True, (238, 214, 142))
        title_rect = title.get_rect(center=title_area.center)
        surface.blit(title, title_rect)

        subtitle_rect = pygame.Rect(
            header_content.x + self.scale_x(10, 6),
            title_area.bottom + self.scale_y(10, 6),
            header_content.width - 2 * self.scale_x(10, 6),
            self.scale_y(34, 24),
        )
        subtitle_font = self._get_fitted_game_font(
            "A quick guide to the draft, labyrinth, and Appeasing Pan.",
            self.font_size(22, 15),
            subtitle_rect,
            2,
            self.font_size(14, 11),
        )
        self._render_outlined_text(
            surface,
            subtitle_font,
            "A quick guide to the draft, labyrinth, and Appeasing Pan.",
            (222, 224, 228),
            (26, 18, 10),
            subtitle_rect.center,
            anchor="center",
        )

        viewport_rect = pygame.Rect(
            self.scale_x(48, 24),
            header_rect.bottom + self.scale_y(18, 12),
            self.window.WINDOW_WIDTH - 2 * self.scale_x(48, 24),
            max(1, self.back_button_rect.top - header_rect.bottom - self.scale_y(42, 28)),
        )
        columns = 2 if self.window.WINDOW_WIDTH >= 900 else 1
        if columns == 2 and len(self.SECTIONS) % 2 == 1:
            rows = len(self.SECTIONS) // 2 + 1
            items_per_side = len(self.SECTIONS) // 2
        else:
            rows = (len(self.SECTIONS) + columns - 1) // columns
            items_per_side = rows
        gap = self.scale(14, 8)
        card_width = (viewport_rect.width - gap * (columns - 1)) // columns
        card_height = max(
            self.scale_y(112, 86) if columns == 1 else self.scale_y(76, 58),
            (viewport_rect.height - gap * (rows - 1)) // rows if columns > 1 else 0,
        )
        card_height = max(1, int(round(card_height * 1.4)))
        content_height = rows * card_height + (rows - 1) * gap
        self.max_scroll = max(0, content_height - viewport_rect.height)
        self.scroll_offset = min(self.scroll_offset, self.max_scroll)

        if self.max_scroll:
            self._render_outlined_text(
                surface,
                self.small_font,
                "Mouse wheel scrolls this guide.",
                (244, 244, 244),
                (0, 0, 0),
                (viewport_rect.x, viewport_rect.bottom + self.scale_y(8, 5)),
            )

        old_clip = surface.get_clip()
        surface.set_clip(viewport_rect)
        display_indices = list(range(len(self.SECTIONS)))
        if columns == 2 and len(self.SECTIONS) % 2 == 1:
            display_indices = [0, 1, 2, 4, 5, 6, 3]
        for slot_index, section_index in enumerate(display_indices):
            heading, body = self.SECTIONS[section_index]
            if columns == 2 and len(self.SECTIONS) % 2 == 1:
                if slot_index < items_per_side:
                    col = 0
                    row = slot_index
                    x = viewport_rect.x
                elif slot_index < 2 * items_per_side:
                    col = 1
                    row = slot_index - items_per_side
                    x = viewport_rect.x + card_width + gap
                else:
                    col = 0
                    row = items_per_side
                    x = viewport_rect.x + (viewport_rect.width - card_width) // 2
            else:
                col = slot_index // rows
                row = slot_index % rows
                x = viewport_rect.x + col * (card_width + gap)
            card_rect = pygame.Rect(
                x,
                viewport_rect.y + row * (card_height + gap) - self.scroll_offset,
                card_width,
                card_height,
            )
            if card_rect.bottom < viewport_rect.top or card_rect.top > viewport_rect.bottom:
                continue
            self._render_stone_panel(surface, card_rect, dim_alpha=30)
            content_rect = self._get_stone_content_rect(
                card_rect,
                extra_x=self.scale_x(6, 4),
                extra_top=self.scale_y(2, 1),
                extra_bottom=self.scale_y(4, 2),
            )
            heading_rect = pygame.Rect(
                content_rect.x,
                content_rect.y,
                content_rect.width,
                max(self.scale_y(26, 20), content_rect.height // 4),
            )
            heading_font = self._get_fitted_game_font(
                heading,
                self.font_size(30, 22),
                heading_rect,
                1,
                self.font_size(20, 15),
            )
            self._render_carved_text(
                surface,
                heading_font,
                heading,
                (62, 54, 44),
                (heading_rect.centerx, heading_rect.y + self.scale_y(2, 1)),
                anchor="midtop",
            )

            body_rect = pygame.Rect(
                content_rect.x,
                heading_rect.bottom + self.scale_y(6, 4),
                content_rect.width,
                max(1, content_rect.bottom - heading_rect.bottom - self.scale_y(8, 5)),
            )
            body_font = self._get_fitted_game_font(
                body,
                self.font_size(24, 17),
                body_rect,
                4,
                self.font_size(16, 12),
            )
            self._draw_wrapped_carved_text(
                surface,
                body,
                body_font,
                (74, 66, 54),
                body_rect,
                max(self.scale(17, 13), body_font.get_linesize()),
                4,
            )
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
        self.title_font = self._get_game_font(self.font_size(64, 38))
        self.body_font = self._get_game_font(self.font_size(28, 20))
        self.small_font = self._get_game_font(self.font_size(22, 16))

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
        back_gap = self.scale_y(10, 6)
        bottom_margin = self.scale_y(8, 5)
        columns = 1 if self.is_compact_layout() else 2
        option_controls = self._setting_option_controls()
        rows = (len(option_controls) + columns - 1) // columns
        available_width = self.window.WINDOW_WIDTH - 2 * outer_margin - (columns - 1) * column_gap
        start_y = self.scale_y(212, 156) if self.get_missing_required_art_assets() else self.scale_y(188, 138)
        button_width_cap = min(self.scale_x(390, 250), max(1, available_width // columns))
        desired_back_width = min(self.scale_x(320, 220), self.window.WINDOW_WIDTH - 2 * outer_margin)
        desired_back_height = self._get_wood_icon_height_for_width(desired_back_width)
        available_grid_height = max(
            1,
            self.window.WINDOW_HEIGHT - start_y - desired_back_height - back_gap - bottom_margin,
        )
        button_height_cap = max(1, (available_grid_height - (rows - 1) * row_gap) // rows)
        button_width = max(1, min(button_width_cap, self._get_wood_icon_width_for_height(button_height_cap)))
        button_height = self._get_wood_icon_height_for_width(button_width)
        grid_width = columns * button_width + (columns - 1) * column_gap
        start_x = (self.window.WINDOW_WIDTH - grid_width) // 2
        grid_height = rows * button_height + (rows - 1) * row_gap

        back_width = min(
            self.window.WINDOW_WIDTH - 2 * outer_margin,
            min(self.scale_x(320, 220), max(button_width, self.scale_x(180, 140))),
        )
        back_height = self._get_wood_icon_height_for_width(back_width)
        back_y = self.window.WINDOW_HEIGHT - back_height - bottom_margin
        min_grid_y = self.scale_y(150, 108) if self.get_missing_required_art_assets() else self.scale_y(126, 92)
        grid_y = max(min_grid_y, min(start_y, back_y - back_gap - grid_height))

        self.setting_button_rects = {}
        for index, (key, button) in enumerate(option_controls):
            row = index // columns
            col = index % columns
            rect = pygame.Rect(
                start_x + col * (button_width + column_gap),
                grid_y + row * (button_height + row_gap),
                button_width,
                button_height,
            )
            self.setting_button_rects[key] = rect
            button.set_relative_position((rect.x, rect.y))
            button.set_dimensions((button_width, button_height))

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
            "tutorial_reset": "Reset Tip Cycle",
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
            if self._point_hits_wood_icon(rect, pos):
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
            if self.window.tutorial_enabled:
                self.window.reset_tutorial_tips()
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
            "Turn Tutorial Tips on here if you want in-game guidance.",
        ]
        for index, text in enumerate(lines):
            self._render_outlined_text(
                surface,
                self.small_font,
                text,
                (244, 244, 244),
                (0, 0, 0),
                (self.window.WINDOW_WIDTH // 2, self.scale_y(132 + index * 28, 92 + index * 18)),
                anchor="center",
            )

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

    FLIP_DURATION = 2.0
    FLIPS_PER_SECOND = 10
    COIN_ART_PATHS = {
        0: Screen.ASSET_ROOT / "p1.png",
        1: Screen.ASSET_ROOT / "p2.png",
    }

    def __init__(self, window: "GameWindow"):
        super().__init__(window)
        self.title_font = None
        self.body_font = None
        self.small_font = None
        self.elapsed = 0.0
        self.first_player = 0
        self.finished = False
        self._consumed = False
        self._coin_art_base = self._load_coin_art()
        self._coin_art_cache: dict[tuple[int, int], pygame.Surface] = {}
        self._refresh_fonts()

    def _refresh_fonts(self) -> None:
        """Refresh coin-flip fonts."""
        self.title_font = self._get_game_font(self.font_size(64, 38))
        self.body_font = self._get_game_font(self.font_size(34, 24))
        self.small_font = self._get_game_font(self.font_size(24, 16))

    def _load_coin_art(self) -> dict[int, pygame.Surface]:
        """Load and prepare the P1/P2 flip art so both faces animate on the same footprint."""
        art = {}
        for player_id, path in self.COIN_ART_PATHS.items():
            image = self._load_image(path)
            if image is None:
                continue
            art[player_id] = self._prepare_coin_art(image)
        return art

    def _get_coin_content_bounds(self, image: pygame.Surface) -> pygame.Rect:
        """Measure the visible coin face so both P1/P2 graphics scale from the same true bounds."""
        alpha_bounds = image.get_bounding_rect(min_alpha=12)
        if alpha_bounds.width > 0 and alpha_bounds.height > 0 and (
            alpha_bounds.width < image.get_width() or alpha_bounds.height < image.get_height()
        ):
            opaque_mask = pygame.mask.from_surface(image, 12)
            component = opaque_mask.connected_component((image.get_width() // 2, image.get_height() // 2))
            rects = component.get_bounding_rects()
            if rects:
                return rects[0]
            return alpha_bounds

        corners = [
            image.get_at((0, 0)),
            image.get_at((image.get_width() - 1, 0)),
            image.get_at((0, image.get_height() - 1)),
            image.get_at((image.get_width() - 1, image.get_height() - 1)),
        ]
        background = tuple(sum(color[index] for color in corners) // 4 for index in range(3))
        background_mask = pygame.mask.from_threshold(
            image,
            (*background, 255),
            (16, 16, 16, 255),
        )
        foreground_mask = background_mask.copy()
        foreground_mask.invert()
        component = foreground_mask.connected_component((image.get_width() // 2, image.get_height() // 2))
        rects = component.get_bounding_rects()
        if rects:
            return rects[0]
        return pygame.Rect(0, 0, image.get_width(), image.get_height())

    def _prepare_coin_art(self, image: pygame.Surface) -> pygame.Surface:
        """Normalize one coin face so both players render centered at the same scale."""
        bounds = self._get_coin_content_bounds(image)
        cropped = image.subsurface(bounds).copy()
        pad = max(4, int(round(max(bounds.width, bounds.height) * 0.02)))
        side = max(cropped.get_width(), cropped.get_height()) + pad * 2
        square = pygame.Surface((side, side), pygame.SRCALPHA)
        crop_rect = cropped.get_rect(center=(side // 2, side // 2))
        square.blit(cropped, crop_rect)

        masked = square.copy()
        mask = pygame.Surface((side, side), pygame.SRCALPHA)
        radius = max(1, side // 2 - pad)
        pygame.draw.circle(mask, (255, 255, 255, 255), (side // 2, side // 2), radius)
        masked.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
        return masked

    def _get_scaled_coin_art(self, player_id: int, diameter: int) -> pygame.Surface | None:
        """Return one prepared coin face scaled to the shared animation size."""
        base = self._coin_art_base.get(player_id)
        if base is None or diameter <= 0:
            return None
        cache_key = (player_id, diameter)
        if cache_key not in self._coin_art_cache:
            self._coin_art_cache[cache_key] = pygame.transform.smoothscale(base, (diameter, diameter))
        return self._coin_art_cache[cache_key]

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
        if self.elapsed >= self.FLIP_DURATION:
            self.elapsed = self.FLIP_DURATION
            self.finished = True

    def _get_visible_coin_label(self) -> str:
        """Return the coin face that should currently be visible."""
        if self.finished:
            return f"P{self.first_player + 1}"
        flip_index = int(self.elapsed * self.FLIPS_PER_SECOND)
        return "P1" if flip_index % 2 == 0 else "P2"

    def _get_visible_coin_player(self) -> int:
        """Return which player's coin art should currently be visible."""
        if self.finished:
            return self.first_player
        flip_index = int(self.elapsed * self.FLIPS_PER_SECOND)
        return 0 if flip_index % 2 == 0 else 1

    def render(self, surface: pygame.Surface) -> None:
        """Render the coin flip screen."""
        self._render_screen_background(surface, (14, 18, 28))

        top_panel = pygame.Rect(
            self.scale_x(190, 48),
            self.scale_y(28, 18),
            self.window.WINDOW_WIDTH - 2 * self.scale_x(190, 48),
            self.scale_y(124, 96),
        )
        self._render_stone_panel(surface, top_panel, dim_alpha=28, shadow_alpha=64)
        top_content = self._get_stone_content_rect(
            top_panel,
            extra_x=self.scale_x(8, 4),
            extra_top=self.scale_y(2, 1),
            extra_bottom=self.scale_y(2, 1),
        )
        title_area = pygame.Rect(
            top_content.x,
            top_content.y,
            top_content.width,
            self.scale_y(40, 28),
        )
        title_font = self._get_fitted_game_font(
            "COIN FLIP",
            self.font_size(56, 34),
            title_area,
            1,
            self.font_size(28, 20),
        )
        self._render_carved_text(
            surface,
            title_font,
            "COIN FLIP",
            (72, 64, 52),
            title_area.center,
            anchor="center",
        )
        subtitle_area = pygame.Rect(
            top_content.x,
            title_area.bottom + self.scale_y(8, 5),
            top_content.width,
            max(1, top_content.bottom - title_area.bottom - self.scale_y(8, 5)),
        )
        subtitle_font = self._get_fitted_game_font(
            "Determining who drafts first.",
            self.font_size(24, 16),
            subtitle_area,
            1,
            self.font_size(14, 11),
        )
        self._render_carved_text(
            surface,
            subtitle_font,
            "Determining who drafts first.",
            (78, 70, 58),
            subtitle_area.center,
            anchor="center",
        )

        bottom_panel = pygame.Rect(
            self.scale_x(220, 60),
            self.window.WINDOW_HEIGHT - self.scale_y(164, 126),
            self.window.WINDOW_WIDTH - 2 * self.scale_x(220, 60),
            self.scale_y(116, 90),
        )
        self._render_wood_panel(surface, bottom_panel, dim_alpha=46)

        available_height = max(1, bottom_panel.top - top_panel.bottom - self.scale_y(40, 28))
        coin_diameter = min(
            self.scale_x(360, 240),
            self.window.WINDOW_WIDTH - 2 * self.scale_x(120, 70),
            available_height,
        )
        center = (
            self.window.WINDOW_WIDTH // 2,
            top_panel.bottom + available_height // 2,
        )
        shadow_surface = pygame.Surface((coin_diameter + self.scale(40, 24), coin_diameter + self.scale(40, 24)), pygame.SRCALPHA)
        shadow_center = (shadow_surface.get_width() // 2, shadow_surface.get_height() // 2 + self.scale(10, 6))
        pygame.draw.circle(
            shadow_surface,
            (0, 0, 0, 90),
            shadow_center,
            coin_diameter // 2 + self.scale(8, 5),
        )
        shadow_rect = shadow_surface.get_rect(center=center)
        surface.blit(shadow_surface, shadow_rect.topleft)

        player_id = self._get_visible_coin_player()
        coin_art = self._get_scaled_coin_art(player_id, coin_diameter)
        if coin_art is not None:
            surface.blit(coin_art, coin_art.get_rect(center=center))
        else:
            label = self._get_visible_coin_label()
            fill = (208, 84, 84) if label == "P1" else (84, 118, 216)
            pygame.draw.circle(surface, fill, center, coin_diameter // 2)
            pygame.draw.circle(surface, (248, 232, 166), center, coin_diameter // 2, self.scale(5, 3))
            coin_text = self.title_font.render(label, True, (24, 24, 30))
            surface.blit(coin_text, coin_text.get_rect(center=center))

        result = (
            f"Player {self.first_player + 1} drafts first."
            if self.finished
            else "Flipping to decide who drafts first..."
        )
        bottom_content = pygame.Rect(
            bottom_panel.x + self.scale_x(26, 18),
            bottom_panel.y + self.scale_y(18, 12),
            bottom_panel.width - 2 * self.scale_x(26, 18),
            bottom_panel.height - 2 * self.scale_y(18, 12),
        )
        result_rect = pygame.Rect(
            bottom_content.x,
            bottom_content.y,
            bottom_content.width,
            max(1, bottom_content.height // 2),
        )
        result_font = self._get_fitted_game_font(
            result,
            self.font_size(34, 24),
            result_rect,
            1,
            self.font_size(18, 14),
        )
        self._render_outlined_text(
            surface,
            result_font,
            result,
            (248, 238, 206),
            (28, 18, 10),
            result_rect.center,
            anchor="center",
            outline_width=self.scale(2, 1),
        )

        note_rect = pygame.Rect(
            bottom_content.x,
            result_rect.bottom + self.scale_y(4, 2),
            bottom_content.width,
            max(1, bottom_content.bottom - result_rect.bottom - self.scale_y(4, 2)),
        )
        note_font = self._get_fitted_game_font(
            "The draft starts automatically.",
            self.font_size(22, 15),
            note_rect,
            1,
            self.font_size(13, 10),
        )
        self._render_outlined_text(
            surface,
            note_font,
            "The draft starts automatically.",
            (236, 228, 196),
            (20, 12, 8),
            note_rect.center,
            anchor="center",
        )

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
        self.draft_tutorial_panel_rect = None
        self._refresh_fonts()
        self._create_ui()
        self.on_resize()
        self._hide_all_elements()

    def _refresh_fonts(self) -> None:
        """Refresh all draft-phase fonts."""
        self.title_font = self._get_game_font(self.font_size(64, 38))
        self.body_font = self._get_game_font(self.font_size(30, 20))
        self.small_font = self._get_game_font(self.font_size(24, 16))
        self.card_font = self._get_game_font(self.font_size(34, 22))

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
            and self._point_hits_wood_icon(self.tutorial_toggle_rect, event.pos)
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

        rules = (
            ["Draft 8 Satyrs/Oracles + 2 Heroes. Remaining Heroes become player cards."]
            if compact
            else [
                "Draft all 4 Satyrs, all 4 Oracles, and only 2 Heroes.",
                "The 2 Heroes left behind become the player cards.",
            ]
        )
        if compact:
            info_panel_rect = pygame.Rect(
                self.scale_x(24, 14),
                self.scale_y(28, 18),
                self.window.WINDOW_WIDTH - 2 * self.scale_x(24, 14),
                self.scale_y(154, 118),
            )
        else:
            legend_right = self.scale_x(28, 16) + self.scale_x(230, 170) + self.scale_x(26, 14)
            info_width = min(
                self.scale_x(800, 580),
                self.window.WINDOW_WIDTH - legend_right - self.scale_x(36, 18),
            )
            info_panel_rect = pygame.Rect(
                max(legend_right, (self.window.WINDOW_WIDTH - info_width) // 2),
                self.scale_y(28, 18),
                info_width,
                self.scale_y(188, 144),
            )
        self._render_stone_panel(surface, info_panel_rect, dim_alpha=24)
        info_content = self._get_stone_content_rect(
            info_panel_rect,
            extra_x=self.scale_x(8, 4),
            extra_top=self.scale_y(4, 2),
        )
        title_area = pygame.Rect(
            info_content.x,
            info_content.y,
            info_content.width,
            self.scale_y(42, 30),
        )
        title_font = self._get_fitted_game_font(
            "INITIAL DRAFT",
            self.font_size(64, 38),
            title_area,
            1,
            self.font_size(34, 24),
        )
        self._render_carved_text(
            surface,
            title_font,
            "INITIAL DRAFT",
            (78, 70, 58),
            title_area.center,
            anchor="center",
        )

        prompt_text = f"Player {self.current_player + 1} picks a card"
        prompt_area = pygame.Rect(
            info_content.x,
            title_area.bottom + self.scale_y(6, 4),
            info_content.width,
            self.scale_y(30, 22),
        )
        prompt_font = self._get_fitted_game_font(
            prompt_text,
            self.font_size(34, 24),
            prompt_area,
            1,
            self.font_size(22, 16),
        )
        self._render_carved_text(
            surface,
            prompt_font,
            prompt_text,
            (72, 64, 52),
            prompt_area.center,
            anchor="center",
        )

        rules_area = pygame.Rect(
            info_content.x,
            prompt_area.bottom + self.scale_y(4, 3),
            info_content.width,
            max(1, info_content.bottom - (prompt_area.bottom + self.scale_y(8, 5))),
        )
        rule_line_rect = pygame.Rect(
            rules_area.x,
            rules_area.y,
            rules_area.width,
            max(1, rules_area.height // len(rules)),
        )
        rule_font = self._get_fitted_game_font(
            max(rules, key=len),
            self.font_size(22, 15),
            rule_line_rect,
            1,
            self.font_size(14, 11),
        )
        line_height = max(self.scale_y(18, 13), rule_font.get_linesize())
        rules_top = rules_area.y + max(0, (rules_area.height - len(rules) * line_height) // 2)
        old_clip = surface.get_clip()
        surface.set_clip(rules_area)
        for index, text in enumerate(rules):
            self._render_carved_text(
                surface,
                rule_font,
                text,
                (66, 58, 48),
                (rules_area.centerx, rules_top + index * line_height),
                anchor="midtop",
            )
        surface.set_clip(old_clip)

        drafted_low_cards = len(self.player_hands[0]) + len(self.player_hands[1]) - self.kings_drafted
        count_text = (
            f"S/O: {drafted_low_cards}/8 | Heroes: {self.kings_drafted}/2"
            if self.is_compact_layout()
            else f"Satyrs/Oracles drafted: {drafted_low_cards}/8   Heroes drafted: {self.kings_drafted}/2"
        )
        counts_y = self.draft_grid_bottom + self.scale_y(28, 20)
        counts_width = min(
            max(self.small_font.size(count_text)[0] + self.scale_x(76, 44), self.scale_x(320, 240)),
            self.window.WINDOW_WIDTH - 2 * self.scale_x(44, 24),
        )
        counts_rect = pygame.Rect(
            (self.window.WINDOW_WIDTH - counts_width) // 2,
            counts_y - self.scale_y(24, 18),
            counts_width,
            self.scale_y(50, 38),
        )
        self._render_stone_panel(surface, counts_rect, dim_alpha=24)
        counts_content = self._get_stone_content_rect(
            counts_rect,
            extra_top=self.scale_y(2, 1),
            extra_bottom=self.scale_y(2, 1),
        )
        count_font = self._get_fitted_game_font(
            count_text,
            self.font_size(24, 16),
            counts_content,
            1,
            self.font_size(14, 11),
        )
        self._render_carved_text(
            surface,
            count_font,
            count_text,
            (66, 58, 48),
            counts_content.center,
            anchor="center",
        )

        for index, rect in enumerate(self.card_rects):
            card = self.available_cards[index] if index < len(self.available_cards) else None
            self._render_draft_card(surface, rect, card)

        margin = self.scale_x(70, 20)
        panel_gap = self.scale_x(60, 12)
        self.draft_tutorial_panel_rect = None
        tutorial_gap = self.scale_y(12, 8)
        if self.window.tutorial_enabled and self.card_rects:
            self.draft_tutorial_panel_rect = self._get_draft_tutorial_panel_rect(counts_rect)
        panel_y = (
            self.draft_tutorial_panel_rect.bottom + tutorial_gap
            if self.draft_tutorial_panel_rect is not None
            else counts_y + self.scale_y(32, 22)
        )
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

    def _get_draft_grid_rect(self) -> pygame.Rect:
        """Return the bounding rect for all draft card hitboxes."""
        if not self.card_rects:
            return pygame.Rect(0, 0, 0, 0)
        grid_rect = self.card_rects[0].copy()
        for rect in self.card_rects[1:]:
            grid_rect.union_ip(rect)
        return grid_rect

    def _get_draft_tutorial_panel_rect(self, counts_rect: pygame.Rect) -> pygame.Rect:
        """Return a reserved tutorial panel slot below the draft grid and counts."""
        margin = self.scale_x(22, 14)
        width = min(self.scale_x(760, 320), self.window.WINDOW_WIDTH - 2 * margin)
        height = self.scale_y(62, 48)
        return pygame.Rect(
            (self.window.WINDOW_WIDTH - width) // 2,
            counts_rect.bottom + self.scale_y(8, 5),
            width,
            height,
        )

    def _render_tutorial_overlay(self, surface: pygame.Surface) -> None:
        """Show optional draft tutorial guidance."""
        if not self.window.tutorial_enabled or not self.card_rects:
            self.tutorial_toggle_rect = None
            return

        grid_rect = self._get_draft_grid_rect()
        pygame.draw.rect(surface, (252, 222, 104), grid_rect.inflate(self.scale(10, 6), self.scale(10, 6)), 3, border_radius=10)

        text = "Tutorial: click a draft card. Draft all Satyrs and Oracles, but only two Heroes."
        if self.draft_tutorial_panel_rect is None:
            counts_rect = pygame.Rect(0, self.draft_grid_bottom + self.scale_y(18, 12), 1, self.scale_y(24, 18))
            self.draft_tutorial_panel_rect = self._get_draft_tutorial_panel_rect(counts_rect)
        panel_rect = self.draft_tutorial_panel_rect
        self._render_stone_panel(surface, panel_rect, dim_alpha=28)
        button_width = min(self.scale_x(132, 92), max(self.scale_x(86, 72), panel_rect.width // 4))
        button_height = max(self.scale_y(24, 20), panel_rect.height - self.scale_y(12, 8))
        self.tutorial_toggle_rect = pygame.Rect(
            panel_rect.right - button_width - self.scale_x(8, 5),
            panel_rect.centery - button_height // 2,
            button_width,
            button_height,
        )
        self._render_wood_button(
            surface,
            self.tutorial_toggle_rect,
            "Tips Off",
            self._point_hits_wood_icon(self.tutorial_toggle_rect, pygame.mouse.get_pos()),
            self.font_size(16, 12),
        )

        text_rect = self._get_stone_content_rect(panel_rect)
        text_rect.width -= button_width + self.scale_x(10, 6)
        self._draw_wrapped_draft_text(surface, text, text_rect)

    def _draw_wrapped_draft_text(self, surface: pygame.Surface, text: str, rect: pygame.Rect) -> None:
        """Draw compact wrapped tutorial text inside a reserved panel."""
        font = self._get_fitted_game_font(
            text,
            self.font_size(24, 16),
            rect,
            2,
            self.font_size(15, 11),
        )
        self._draw_wrapped_carved_text(
            surface,
            text,
            font,
            (74, 66, 54),
            rect,
            max(self.scale_y(16, 12), font.get_linesize()),
            2,
        )

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
            surface.blit(taken, taken.get_rect(center=rect.center))
            return

        enabled = self._can_pick_card(card)
        fill = self._muted_family_color(card.suit, enabled)
        border = get_family_color(card.suit) if enabled else (95, 95, 95)
        text_color = (35, 35, 35) if enabled else (92, 92, 98)

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
        self._render_stone_panel(surface, rect, dim_alpha=26)
        content_rect = self._get_stone_content_rect(
            rect,
            extra_x=self.scale_x(8, 4),
            extra_top=self.scale_y(4, 2),
            extra_bottom=self.scale_y(4, 2),
        )
        title_text = f"{title} ({len(cards)}/5)"
        title_rect = pygame.Rect(
            content_rect.x,
            content_rect.y,
            content_rect.width,
            self.scale_y(28, 20),
        )
        title_font = self._get_fitted_game_font(
            title_text,
            self.font_size(30, 20),
            title_rect,
            1,
            self.font_size(18, 13),
        )
        self._render_carved_text(
            surface,
            title_font,
            title_text,
            (70, 62, 50),
            title_rect.center,
            anchor="center",
        )
        usable_rect = pygame.Rect(
            content_rect.x,
            title_rect.bottom + self.scale_y(8, 5),
            content_rect.width,
            max(1, content_rect.bottom - title_rect.bottom - self.scale_y(8, 5)),
        )

        if rect.height < self.scale_y(112, 86):
            label_y = usable_rect.y
            label_width = max(self.scale_x(48, 38), (usable_rect.width - 4 * self.scale(6, 4)) // 5)
            spacing = self.scale(6, 4)
            for index in range(5):
                chip_rect = pygame.Rect(
                    usable_rect.x + index * (label_width + spacing),
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
            (usable_rect.width - 4 * card_spacing) // 5,
        )
        card_height = min(
            max(self.scale(82, 62), usable_rect.height),
            self.scale(120, 92),
        )
        start_x = usable_rect.x
        start_y = usable_rect.y + max(0, (usable_rect.height - card_height) // 2)

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
            self.scale_x(260, 192),
            self.scale_y(148, 110),
        )
        self._render_stone_panel(surface, panel_rect, dim_alpha=26)
        content_rect = self._get_stone_content_rect(panel_rect)
        title_rect = pygame.Rect(
            content_rect.x,
            content_rect.y,
            content_rect.width,
            self.scale_y(24, 18),
        )
        title_font = self._get_fitted_game_font(
            "Draft Value Guide",
            self.font_size(22, 16),
            title_rect,
            1,
            self.font_size(16, 12),
        )
        self._render_carved_text(
            surface,
            title_font,
            "Draft Value Guide",
            (70, 62, 50),
            title_rect.center,
            anchor="center",
        )

        lines = [
            get_rank_name_with_value(CardRank.TEN),
            get_rank_name_with_value(CardRank.QUEEN),
            get_rank_name_with_value(CardRank.KING),
        ]
        lines_rect = pygame.Rect(
            content_rect.x,
            title_rect.bottom + self.scale_y(8, 5),
            content_rect.width,
            max(1, content_rect.bottom - title_rect.bottom - self.scale_y(8, 5)),
        )
        line_slot_rect = pygame.Rect(
            lines_rect.x,
            lines_rect.y,
            lines_rect.width,
            max(1, lines_rect.height // len(lines)),
        )
        line_font = self._get_fitted_game_font(
            max(lines, key=len),
            self.font_size(20, 15),
            line_slot_rect,
            1,
            self.font_size(15, 11),
        )
        old_clip = surface.get_clip()
        surface.set_clip(lines_rect)
        for index, text in enumerate(lines):
            self._render_carved_text(
                surface,
                line_font,
                text,
                (64, 56, 46),
                (
                    lines_rect.x,
                    lines_rect.y + index * max(self.scale(22, 15), line_font.get_linesize()),
                ),
            )
        surface.set_clip(old_clip)


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
        self.title_font = self._get_game_font(self.font_size(62, 36))
        self.body_font = self._get_game_font(self.font_size(30, 20))
        self.card_font = self._get_game_font(self.font_size(42, 24))
        self.small_font = self._get_game_font(self.font_size(24, 16))

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

        self._render_outlined_text(
            surface,
            self.body_font,
            "Resolving the color roles...",
            (244, 244, 244),
            (0, 0, 0),
            (self.window.WINDOW_WIDTH // 2, self.scale_y(150, 112)),
            anchor="center",
        )

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

        grid_bottom = y + rows * card_height + (rows - 1) * spacing
        footer_rect = self._render_outlined_text(
            surface,
            self.small_font,
            "The Omens reveal automatically, then the labyrinth begins.",
            (244, 244, 244),
            (0, 0, 0),
            (self.window.WINDOW_WIDTH // 2, grid_bottom + self.scale_y(28, 20)),
            anchor="center",
        )

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

    BANNER_PATH = Screen.ASSET_ROOT / "banner.png"
    VICTORY_ART_PATH = Screen.ASSET_ROOT / "victory.png"

    def __init__(self, window: "GameWindow"):
        super().__init__(window)
        self.title_font = None
        self.subtitle_font = None
        self.body_font = None
        self.small_font = None

        self.winner_text = "Player 1 Wins!"
        self.damage_text = "Final damage - P1: 0 | P2: 0"
        self.match_summary = {}
        self._banner_base = self._crop_overlay_asset(self._load_image(self.BANNER_PATH), pad=8)
        self._banner_cache: dict[tuple[int, int], pygame.Surface] = {}
        self._victory_art_base = self._crop_overlay_asset(self._load_image(self.VICTORY_ART_PATH), pad=8)
        self._victory_art_cache: dict[tuple[int, int], pygame.Surface] = {}

        self.play_again_button = None
        self.menu_button = None
        self.game_over_button_rects: dict[str, pygame.Rect] = {}
        self.hovered_button = None
        self.match_summary_panel_rect: pygame.Rect | None = None
        self.match_summary_scroll_rect: pygame.Rect | None = None
        self.match_summary_scroll_offset = 0
        self.match_summary_scroll_max = 0
        self._refresh_fonts()
        self._create_ui()
        self.on_resize()
        self._hide_all_elements()

    def _refresh_fonts(self) -> None:
        """Refresh game-over fonts after a resize."""
        self.title_font = self._get_title_style_font(self.font_size(42, 28))
        self.subtitle_font = self._get_game_font(self.font_size(38, 24))
        self.body_font = self._get_game_font(self.font_size(28, 19))
        self.small_font = self._get_game_font(self.font_size(21, 15))

    @staticmethod
    def _crop_overlay_asset(image: pygame.Surface | None, pad: int = 0) -> pygame.Surface | None:
        """Trim transparent slack around a decorative overlay asset."""
        if image is None:
            return None
        bounds = image.get_bounding_rect(min_alpha=6)
        if bounds.width <= 0 or bounds.height <= 0:
            return image
        left = max(0, bounds.x - pad)
        top = max(0, bounds.y - pad)
        right = min(image.get_width(), bounds.right + pad)
        bottom = min(image.get_height(), bounds.bottom + pad)
        return image.subsurface(pygame.Rect(left, top, right - left, bottom - top)).copy()

    @staticmethod
    def _get_contain_scaled_size(image: pygame.Surface, frame_size: tuple[int, int]) -> tuple[int, int]:
        """Return an image size that fits entirely within the frame."""
        frame_width, frame_height = frame_size
        if frame_width <= 0 or frame_height <= 0:
            return (0, 0)
        scale = min(frame_width / image.get_width(), frame_height / image.get_height())
        return (
            max(1, int(image.get_width() * scale)),
            max(1, int(image.get_height() * scale)),
        )

    @staticmethod
    def _get_scaled_overlay(
        image: pygame.Surface | None,
        cache: dict[tuple[int, int], pygame.Surface],
        size: tuple[int, int],
    ) -> pygame.Surface | None:
        """Return a cached scaled decorative overlay."""
        if image is None or size[0] <= 0 or size[1] <= 0:
            return None
        if size not in cache:
            cache[size] = pygame.transform.smoothscale(image, size)
        return cache[size]

    def _get_banner_content_rect(self, rect: pygame.Rect) -> pygame.Rect:
        """Return the parchment-safe text area inside the victory banner."""
        pad_x = max(self.scale_x(82, 44), int(rect.width * 0.13))
        pad_top = max(self.scale_y(86, 48), int(rect.height * 0.18))
        pad_bottom = max(self.scale_y(82, 46), int(rect.height * 0.17))
        return pygame.Rect(
            rect.x + pad_x,
            rect.y + pad_top,
            max(1, rect.width - 2 * pad_x),
            max(1, rect.height - pad_top - pad_bottom),
        )

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
        horizontal_margin = self.scale_x(44, 18)
        gap = self.scale_x(26, 12)
        available_width = max(2, self.window.WINDOW_WIDTH - 2 * horizontal_margin - gap)
        button_width = min(self.scale_x(330, 180), available_width // 2)
        button_height = self._get_wood_icon_height_for_width(button_width)
        row_width = button_width * 2 + gap
        row_x = (self.window.WINDOW_WIDTH - row_width) // 2
        row_y = self.window.WINDOW_HEIGHT - button_height - self.scale_y(6, 4)

        self.game_over_button_rects = {
            "play": pygame.Rect(row_x, row_y, button_width, button_height),
            "menu": pygame.Rect(row_x + button_width + gap, row_y, button_width, button_height),
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
        self.match_summary_scroll_offset = 0
        self.match_summary_scroll_max = 0

    def _hide_all_elements(self):
        """Hide all UI elements initially."""
        self.play_again_button.hide()
        self.menu_button.hide()

    def handle_events(self, event: pygame.event.Event) -> bool:
        """Handle game-over screen events."""
        if event.type == pygame.MOUSEMOTION:
            self.hovered_button = self._game_over_button_at(event.pos)
            return False
        if event.type == pygame.MOUSEWHEEL:
            if self._scroll_match_summary(event.y, pygame.mouse.get_pos()):
                return True
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
            if self._point_hits_wood_icon(rect, pos):
                return key
        return None

    def _scroll_match_summary(self, wheel_y: int, mouse_pos: tuple[int, int]) -> bool:
        """Scroll the match summary viewport when the pointer is over the parchment text frame."""
        if self.match_summary_scroll_rect is None or self.match_summary_scroll_max <= 0:
            return False
        if not self.match_summary_scroll_rect.collidepoint(mouse_pos):
            return False

        step = self.scale_y(34, 22)
        new_offset = max(
            0,
            min(self.match_summary_scroll_max, self.match_summary_scroll_offset - wheel_y * step),
        )
        if new_offset == self.match_summary_scroll_offset:
            return False
        self.match_summary_scroll_offset = new_offset
        return True

    def update(self, time_delta: float) -> None:
        """Update."""
        pass

    def render(self, surface: pygame.Surface) -> None:
        """Render game-over screen."""
        self._render_screen_background(surface, (18, 18, 28))

        victory_frame = pygame.Rect(
            self.scale_x(120, 44),
            self.scale_y(34, 18),
            self.window.WINDOW_WIDTH - 2 * self.scale_x(120, 44),
            self.scale_y(116, 72),
        )
        victory_rect = self._render_victory_art(surface, victory_frame)

        button_top = min(rect.top for rect in self.game_over_button_rects.values()) if self.game_over_button_rects else self.window.WINDOW_HEIGHT
        self._render_match_summary(surface, victory_rect.bottom + self.scale_y(12, 8), button_top - self.scale_y(10, 6))
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

    def _render_victory_art(self, surface: pygame.Surface, frame_rect: pygame.Rect) -> pygame.Rect:
        """Render the victory ribbon art in the top header area."""
        if self._victory_art_base is None:
            fallback = self.title_font.render("Victory", True, (232, 212, 156))
            fallback_rect = fallback.get_rect(center=frame_rect.center)
            surface.blit(fallback, fallback_rect)
            return fallback_rect

        scaled_size = self._get_contain_scaled_size(self._victory_art_base, frame_rect.size)
        art = self._get_scaled_overlay(self._victory_art_base, self._victory_art_cache, scaled_size)
        art_rect = art.get_rect(center=frame_rect.center)
        surface.blit(art, art_rect)
        return art_rect

    def _render_match_summary(self, surface: pygame.Surface, start_y: int, max_bottom: int) -> None:
        """Render winner, damage, and summary text on the parchment banner."""
        self.match_summary_panel_rect = None
        self.match_summary_scroll_rect = None
        self.match_summary_scroll_max = 0
        available_height = max_bottom - start_y
        if available_height < self.scale_y(180, 120):
            return

        max_width = min(self.window.WINDOW_WIDTH - 2 * self.scale_x(56, 24), self.scale_x(760, 420))
        if self._banner_base is not None:
            panel_size = self._get_contain_scaled_size(self._banner_base, (max_width, available_height))
        else:
            panel_size = (max_width, available_height)
        if panel_size[0] <= 0 or panel_size[1] <= 0:
            return

        panel_top = start_y + max(0, (available_height - panel_size[1]) // 2)
        panel_height = max(
            1,
            min(
                max_bottom - panel_top,
                int(panel_size[1] * 1.1),
            ),
        )
        panel_rect = pygame.Rect(
            (self.window.WINDOW_WIDTH - panel_size[0]) // 2,
            panel_top,
            panel_size[0],
            panel_height,
        )
        self.match_summary_panel_rect = panel_rect.copy()
        banner = self._get_scaled_overlay(self._banner_base, self._banner_cache, panel_rect.size)
        if banner is not None:
            surface.blit(banner, panel_rect.topleft)
        else:
            pygame.draw.rect(surface, (228, 214, 187), panel_rect, border_radius=self.scale(16, 10))
            pygame.draw.rect(surface, (98, 78, 54), panel_rect, self.scale(3, 2), border_radius=self.scale(16, 10))

        content_rect = self._get_banner_content_rect(panel_rect)
        winner_rect = pygame.Rect(
            content_rect.x,
            content_rect.y,
            content_rect.width,
            self.scale_y(52, 32),
        )
        damage_rect = pygame.Rect(
            content_rect.x,
            winner_rect.bottom + self.scale_y(8, 4),
            content_rect.width,
            self.scale_y(36, 24),
        )
        summary_title_rect = pygame.Rect(
            content_rect.x,
            damage_rect.bottom + self.scale_y(12, 8),
            content_rect.width,
            self.scale_y(34, 22),
        )

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

        winner_font = self._get_fitted_game_font(
            self.winner_text,
            self.font_size(40, 26),
            winner_rect,
            2,
            self.font_size(22, 16),
        )
        damage_font = self._get_fitted_game_font(
            self.damage_text,
            self.font_size(25, 18),
            damage_rect,
            2,
            self.font_size(16, 12),
        )
        summary_font = self._get_fitted_game_font(
            "Match Summary",
            self.font_size(27, 18),
            summary_title_rect,
            1,
            self.font_size(16, 12),
        )

        winner_surface = winner_font.render(self.winner_text, True, (72, 48, 24))
        winner_surface_rect = winner_surface.get_rect(center=winner_rect.center)
        surface.blit(winner_surface, winner_surface_rect)

        damage_surface = damage_font.render(self.damage_text, True, (96, 74, 46))
        damage_surface_rect = damage_surface.get_rect(center=damage_rect.center)
        surface.blit(damage_surface, damage_surface_rect)

        summary_title = summary_font.render("Match Summary", True, (82, 56, 28))
        summary_title_surface_rect = summary_title.get_rect(center=summary_title_rect.center)
        surface.blit(summary_title, summary_title_surface_rect)

        summary_body_font = self._get_game_font(self.font_size(21, 15))
        summary_line_height = max(self.scale_y(20, 14), summary_body_font.get_linesize())
        summary_visible_lines = 6
        max_text_frame_height = summary_line_height * summary_visible_lines
        text_frame_rect = pygame.Rect(
            content_rect.x + self.scale_x(6, 4),
            summary_title_rect.bottom + self.scale_y(10, 6),
            max(1, content_rect.width - 2 * self.scale_x(6, 4)),
            max(
                1,
                min(
                    content_rect.bottom
                    - self.scale_y(28, 20)
                    - (summary_title_rect.bottom + self.scale_y(10, 6)),
                    max_text_frame_height,
                ),
            ),
        )
        frame_fill = pygame.Surface(text_frame_rect.size, pygame.SRCALPHA)
        frame_fill.fill((255, 250, 240, 42))
        surface.blit(frame_fill, text_frame_rect.topleft)
        pygame.draw.rect(surface, (138, 112, 74), text_frame_rect, 1, border_radius=self.scale(6, 4))
        self.match_summary_scroll_rect = text_frame_rect.copy()
        self._draw_wrapped_banner_summary(surface, lines, text_frame_rect)

    def _draw_wrapped_banner_summary(
        self,
        surface: pygame.Surface,
        lines: list[str],
        rect: pygame.Rect,
    ) -> None:
        """Draw a scrollable wrapped summary list inside the parchment text frame."""
        font = self._get_game_font(self.font_size(21, 15))
        line_height = max(self.scale_y(20, 14), font.get_linesize())
        wrapped_lines: list[str] = []
        for line in lines or ["None"]:
            words = line.split()
            if not words:
                wrapped_lines.append("")
                continue
            current = words[0]
            for word in words[1:]:
                candidate = f"{current} {word}"
                if font.size(candidate)[0] <= rect.width:
                    current = candidate
                else:
                    wrapped_lines.append(current)
                    current = word
            wrapped_lines.append(current)

        total_height = len(wrapped_lines) * line_height
        self.match_summary_scroll_max = max(0, total_height - rect.height)
        self.match_summary_scroll_offset = max(0, min(self.match_summary_scroll_offset, self.match_summary_scroll_max))

        y = rect.y - self.match_summary_scroll_offset
        old_clip = surface.get_clip()
        surface.set_clip(rect)
        for line in wrapped_lines:
            line_surface = font.render(line, True, (78, 58, 34))
            surface.blit(line_surface, (rect.x, y))
            y += line_height
        surface.set_clip(old_clip)

    def on_enter(self) -> None:
        """Activate game-over screen."""
        self.play_again_button.hide()
        self.menu_button.hide()
        self.match_summary_scroll_offset = 0

    def on_exit(self) -> None:
        """Deactivate game-over screen."""
        self.play_again_button.hide()
        self.menu_button.hide()
        self.hovered_button = None
        self.match_summary_panel_rect = None
        self.match_summary_scroll_rect = None
        self.match_summary_scroll_offset = 0
        self.match_summary_scroll_max = 0

    def on_resize(self) -> None:
        """Refresh fonts and buttons after a resize."""
        self._refresh_fonts()
        self._layout_ui()
        self.match_summary_scroll_offset = 0


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
