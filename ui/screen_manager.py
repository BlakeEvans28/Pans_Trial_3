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
    DRAFT = "draft"
    JACK_REVEAL = "jack_reveal"
    GAME = "game"
    GAME_OVER = "game_over"


class Screen:
    """Base class for all screens."""
    
    def __init__(self, window: "GameWindow"):
        self.window = window
        self.ui_manager = window.ui_manager

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
    
    def __init__(self, window: "GameWindow"):
        super().__init__(window)
        self.title_font = None
        self.subtitle_font = None
        self.info_font = None
        self.play_button = None
        self.how_to_button = None
        self.quit_button = None
        self._refresh_fonts()
        self._create_ui()
        self.on_resize()
        
        # Start with elements hidden (will be shown when screen is activated)
        self._hide_all_elements()

    def _refresh_fonts(self) -> None:
        """Refresh cached fonts for the current window scale."""
        self.title_font = pygame.font.Font(None, self.scale(72, 42))
        self.subtitle_font = pygame.font.Font(None, self.scale(36, 24))
        self.info_font = pygame.font.Font(None, self.scale(24, 18))
    
    def _create_ui(self):
        """Create UI elements."""
        self.play_button = pygame_gui.elements.UIButton(
            relative_rect=pygame.Rect((0, 0), (1, 1)),
            text="Start Game",
            manager=self.ui_manager,
            object_id="play_button"
        )

        self.how_to_button = pygame_gui.elements.UIButton(
            relative_rect=pygame.Rect((0, 0), (1, 1)),
            text="How To Play",
            manager=self.ui_manager,
            object_id="how_to_play_button"
        )
        
        self.quit_button = pygame_gui.elements.UIButton(
            relative_rect=pygame.Rect((0, 0), (1, 1)),
            text="Quit",
            manager=self.ui_manager,
            object_id="quit_button"
        )

    def _layout_ui(self) -> None:
        """Lay out menu buttons for the current window size."""
        button_width = self.scale_x(300, 220)
        button_height = self.scale_y(60, 44)
        button_gap = self.scale_y(16, 10)
        center_x = (self.window.WINDOW_WIDTH - button_width) // 2
        total_height = button_height * 3 + button_gap * 2
        play_y = self.window.WINDOW_HEIGHT // 2 - total_height // 2
        how_y = play_y + button_height + button_gap
        quit_y = how_y + button_height + button_gap

        for button, y in [
            (self.play_button, play_y),
            (self.how_to_button, how_y),
            (self.quit_button, quit_y),
        ]:
            button.set_relative_position((center_x, y))
            button.set_dimensions((button_width, button_height))
    
    def _hide_all_elements(self):
        """Hide all UI elements initially."""
        self.play_button.hide()
        self.how_to_button.hide()
        self.quit_button.hide()
    
    def handle_events(self, event: pygame.event.Event) -> bool:
        """Handle events."""
        if event.type == pygame_gui.UI_BUTTON_PRESSED:
            if event.ui_element == self.play_button:
                return "PLAY"
            elif event.ui_element == self.how_to_button:
                return "HOW_TO_PLAY"
            elif event.ui_element == self.quit_button:
                return "QUIT"
        return False
    
    def update(self, time_delta: float) -> None:
        """Update."""
        pass
    
    def render(self, surface: pygame.Surface) -> None:
        """Render start screen."""
        surface.fill((20, 20, 30))
        
        # Title - centered at top
        title = self.title_font.render("PAN'S TRIAL", True, (200, 100, 200))
        title_rect = title.get_rect(center=(self.window.WINDOW_WIDTH // 2, self.scale_y(120, 84)))
        surface.blit(title, title_rect)
        
        # Subtitle - centered below title
        subtitle = self.subtitle_font.render("Card Game", True, (150, 150, 150))
        subtitle_rect = subtitle.get_rect(center=(self.window.WINDOW_WIDTH // 2, self.scale_y(200, 150)))
        surface.blit(subtitle, subtitle_rect)
        
        # Instructions - centered below subtitle
        inst = self.info_font.render("Two-Player Card Game", True, (100, 100, 100))
        inst_rect = inst.get_rect(center=(self.window.WINDOW_WIDTH // 2, self.scale_y(280, 210)))
        surface.blit(inst, inst_rect)
    
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
        
        # Show start screen elements
        self.play_button.show()
        self.how_to_button.show()
        self.quit_button.show()
    
    def on_exit(self) -> None:
        """Deactivate start screen."""
        self.play_button.hide()
        self.how_to_button.hide()
        self.quit_button.hide()

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
        self.scroll_offset = 0
        self.max_scroll = 0
        self._refresh_fonts()
        self._create_ui()
        self.on_resize()
        self._hide_all_elements()

    def _refresh_fonts(self) -> None:
        """Refresh fonts for the current window scale."""
        self.title_font = pygame.font.Font(None, self.scale(64, 38))
        self.heading_font = pygame.font.Font(None, self.scale(30, 22))
        self.body_font = pygame.font.Font(None, self.scale(24, 17))
        self.small_font = pygame.font.Font(None, self.scale(22, 16))

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
        button_width = self.scale_x(220, 160)
        button_height = self.scale_y(52, 40)
        self.back_button.set_relative_position(
            (
                (self.window.WINDOW_WIDTH - button_width) // 2,
                self.window.WINDOW_HEIGHT - button_height - self.scale_y(30, 20),
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
        if event.type == pygame.MOUSEWHEEL:
            self.scroll_offset = max(0, min(self.max_scroll, self.scroll_offset - event.y * self.scale(48, 32)))
            return True
        return False

    def update(self, time_delta: float) -> None:
        """How To Play has no timed state."""
        pass

    def render(self, surface: pygame.Surface) -> None:
        """Render the How To Play page."""
        surface.fill((16, 20, 30))

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
        self.back_button.show()

    def on_exit(self) -> None:
        """Deactivate the How To Play screen."""
        self.back_button.hide()

    def on_resize(self) -> None:
        """Refresh fonts and layout after resize."""
        self._refresh_fonts()
        self._layout_ui()


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
        self._refresh_fonts()
        self._create_ui()
        self.on_resize()
        self._hide_all_elements()

    def _refresh_fonts(self) -> None:
        """Refresh all draft-phase fonts."""
        self.title_font = pygame.font.Font(None, self.scale(64, 38))
        self.body_font = pygame.font.Font(None, self.scale(30, 20))
        self.small_font = pygame.font.Font(None, self.scale(24, 16))
        self.card_font = pygame.font.Font(None, self.scale(34, 22))

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

    def start_draft(self, draft_cards: list) -> None:
        """Reset the screen with a fresh shuffled draft pool."""
        self.draft_cards = list(draft_cards)
        self.available_cards = list(draft_cards)
        self.player_hands = {0: [], 1: []}
        self.current_player = 0
        self.kings_drafted = 0
        self.player_cards = []
        self._update_buttons()

    def handle_events(self, event: pygame.event.Event) -> bool:
        """Handle draft card picks."""
        if event.type != pygame.MOUSEBUTTONDOWN:
            return False

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
        surface.fill((16, 18, 28))
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
        fill = (245, 245, 235) if enabled else (155, 155, 150)
        border = (205, 180, 120) if enabled else (95, 95, 95)
        text_color = (35, 35, 35)

        radius = self.scale(12, 8)
        pygame.draw.rect(surface, fill, rect, border_radius=radius)
        pygame.draw.rect(surface, border, rect, 3, border_radius=radius)

        rank = self.card_font.render(get_rank_name(card.rank), True, text_color)
        rank_rect = rank.get_rect(center=(rect.centerx, rect.y + self.scale(28, 18)))
        surface.blit(rank, rank_rect)

        draw_suit_icon(
            surface,
            card.suit,
            (rect.centerx, rect.centery + self.scale(8, 4)),
            size=self.scale(20, 12),
            color=get_family_color(card.suit),
        )

        suit_name = self.small_font.render(get_family_name(card.suit), True, text_color)
        suit_rect = suit_name.get_rect(center=(rect.centerx, rect.bottom - self.scale(18, 12)))
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
        pygame.draw.rect(surface, (243, 243, 236), rect, border_radius=radius)
        pygame.draw.rect(surface, accent, rect, 3, border_radius=radius)

        rank = self.small_font.render(get_rank_name(card.rank), True, (35, 35, 35))
        rank_rect = rank.get_rect(center=(rect.centerx, rect.y + self.scale(22, 16)))
        surface.blit(rank, rank_rect)

        draw_suit_icon(
            surface,
            card.suit,
            (rect.centerx, rect.centery - self.scale(4, 2)),
            size=self.scale(18, 10),
            color=get_family_color(card.suit),
        )

        suit_name = self.small_font.render(get_family_name(card.suit), True, (35, 35, 35))
        suit_rect = suit_name.get_rect(center=(rect.centerx, rect.bottom - self.scale(18, 12)))
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
        self.title_font = pygame.font.Font(None, self.scale(62, 36))
        self.body_font = pygame.font.Font(None, self.scale(30, 20))
        self.card_font = pygame.font.Font(None, self.scale(42, 24))
        self.small_font = pygame.font.Font(None, self.scale(24, 16))

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
        surface.fill((12, 16, 26))

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

        self.winner_text = "Player 1 Wins!"
        self.damage_text = "Final damage - P1: 0 | P2: 0"

        self.play_again_button = None
        self.menu_button = None
        self._refresh_fonts()
        self._create_ui()
        self.on_resize()
        self._hide_all_elements()

    def _refresh_fonts(self) -> None:
        """Refresh game-over fonts after a resize."""
        self.title_font = pygame.font.Font(None, self.scale(72, 42))
        self.subtitle_font = pygame.font.Font(None, self.scale(40, 26))
        self.body_font = pygame.font.Font(None, self.scale(32, 22))

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
        button_width = self.scale_x(300, 220)
        button_height = self.scale_y(60, 44)
        center_x = (self.window.WINDOW_WIDTH - button_width) // 2
        play_again_y = self.window.WINDOW_HEIGHT // 2 + self.scale_y(80, 56)
        menu_y = play_again_y + self.scale_y(90, 62)

        for button, y in [
            (self.play_again_button, play_again_y),
            (self.menu_button, menu_y),
        ]:
            button.set_relative_position((center_x, y))
            button.set_dimensions((button_width, button_height))

    def set_result(self, winner: int, p1_damage: int, p2_damage: int) -> None:
        """Set winner screen text."""
        self.winner_text = f"Player {winner + 1} Wins!"
        self.damage_text = f"Final damage - P1: {p1_damage} | P2: {p2_damage}"

    def _hide_all_elements(self):
        """Hide all UI elements initially."""
        self.play_again_button.hide()
        self.menu_button.hide()

    def handle_events(self, event: pygame.event.Event) -> bool:
        """Handle game-over screen events."""
        if event.type == pygame_gui.UI_BUTTON_PRESSED:
            if event.ui_element == self.play_again_button:
                return "PLAY"
            if event.ui_element == self.menu_button:
                return "MENU"
        return False

    def update(self, time_delta: float) -> None:
        """Update."""
        pass

    def render(self, surface: pygame.Surface) -> None:
        """Render game-over screen."""
        surface.fill((18, 18, 28))

        title = self.title_font.render("VICTORY", True, (220, 180, 90))
        title_rect = title.get_rect(center=(self.window.WINDOW_WIDTH // 2, self.scale_y(150, 110)))
        surface.blit(title, title_rect)

        winner = self.subtitle_font.render(self.winner_text, True, (230, 230, 230))
        winner_rect = winner.get_rect(center=(self.window.WINDOW_WIDTH // 2, self.scale_y(260, 192)))
        surface.blit(winner, winner_rect)

        damage = self.body_font.render(self.damage_text, True, (170, 170, 170))
        damage_rect = damage.get_rect(center=(self.window.WINDOW_WIDTH // 2, self.scale_y(330, 242)))
        surface.blit(damage, damage_rect)

        prompt = self.body_font.render("Choose what to do next.", True, (140, 140, 140))
        prompt_rect = prompt.get_rect(center=(self.window.WINDOW_WIDTH // 2, self.scale_y(390, 286)))
        surface.blit(prompt, prompt_rect)

    def on_enter(self) -> None:
        """Activate game-over screen."""
        self.play_again_button.show()
        self.menu_button.show()

    def on_exit(self) -> None:
        """Deactivate game-over screen."""
        self.play_again_button.hide()
        self.menu_button.hide()

    def on_resize(self) -> None:
        """Refresh fonts and buttons after a resize."""
        self._refresh_fonts()
        self._layout_ui()


class ScreenManager:
    """Manages screen transitions."""
    
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
