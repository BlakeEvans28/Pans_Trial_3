"""
Game screen for Pan's Trial.
Handles the main gameplay screen with board and UI.
"""

import sys
from pathlib import Path
import pygame
import pygame_gui

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from pan_theme import (
    get_family_code,
    get_family_name,
    get_rank_name,
    get_rank_name_with_value,
)
from .screen_manager import Screen, ScreenType
from .board_renderer import BoardRenderer
from .input_handler import InputHandler
from .suit_icons import draw_suit_icon
from engine import (
    Action, CardRank, GameState, GamePhase, MoveAction, Position,
    ChooseRequestAction, RequestType, PlayCardAction, ChooseCombatCardAction,
    SelectDamageCardAction, SelectRestructureSuitAction, SelectPlaneShiftDirectionAction,
    ResolvePlaneShiftAction, ResolveBallistaShotAction, PlaceCardsAction,
    direction_to_movement,
)


DIRECTION_KEYS = {
    pygame.K_UP: "up",
    pygame.K_w: "up",
    pygame.K_DOWN: "down",
    pygame.K_s: "down",
    pygame.K_LEFT: "left",
    pygame.K_a: "left",
    pygame.K_RIGHT: "right",
    pygame.K_d: "right",
}

REQUEST_TYPE_MAP = {
    "restructure": RequestType.RESTRUCTURE,
    "steal_life": RequestType.STEAL_LIFE,
    "ignore_us": RequestType.IGNORE_US,
    "plane_shift": RequestType.PLANE_SHIFT,
}

REQUEST_POPUP_COPY = {
    "restructure": {
        "title": "Restructure",
        "description": "Swap two omen colors so their labyrinth roles trade places.",
        "disabled": "Requires at least two omen colors to swap.",
    },
    "steal_life": {
        "title": "Steal Life",
        "description": "Exchange one of your damage cards with one from the enemy pile.",
        "disabled": "Needs at least one damage card in both piles.",
    },
    "ignore_us": {
        "title": "Ignore Us",
        "description": "End Pan's requests immediately and move straight to hole placement.",
        "disabled": "",
    },
    "plane_shift": {
        "title": "Plane Shift",
        "description": "Choose a direction, then click a row or column to wrap it by one tile.",
        "disabled": "",
    },
}


class GameScreen(Screen):
    """Main gameplay screen."""
    
    def __init__(self, window: "GameWindow", game: GameState):
        super().__init__(window)
        self.game = game
        self.renderer = BoardRenderer()
        self.input_handler = InputHandler(self.renderer)
        
        # UI elements
        self.status_label = None
        self.info_label = None
        self.move_buttons = []
        self.pickup_button = None
        self.request_buttons = []
        self.card_buttons = []  # For playing cards in Appeasing phase
        self.weapon_label = None
        self.weapon_buttons = []
        self.restructure_buttons = []
        self.damage_labels = []
        self.damage_buttons = {0: [], 1: []}
        self.jack_labels = []   # For displaying Jack suit roles/hierarchy
        self.hand_labels = []
        self.popup_title_font = None
        self.popup_body_font = None
        self.popup_small_font = None
        self.damage_popup_player = None
        self.selected_placement_card_index = None
        self.dragging_placement_card_index = None
        self.dragging_placement_card_pos = None
        self.hovered_placement_target = None
        self.pending_plane_shift_line = None
        self.hovered_plane_shift_line = None
        self.pending_plane_shift_confirmation = None
        self.tutorial_toggle_rect = None
        self.hand_card_rects = []
        self.inspected_hand_card_index = None
        self._tutorial_seen_appeasing_cycle = False
        self._last_tutorial_phase = self.game.phase
        self.notice_text = None
        self.notice_timer = 0.0
        self.plane_shift_preview_elapsed = 0.0
        
        self._refresh_fonts()
        self._create_ui()
        self.on_resize()
        
        # Start with all elements hidden (will be shown when screen is activated)
        self._hide_all_elements()

    def _refresh_fonts(self) -> None:
        """Refresh gameplay popup fonts after a resize."""
        self.popup_title_font = self._get_title_style_font(self.font_size(38, 26))
        self.popup_body_font = self._get_game_font(self.font_size(28, 20))
        self.popup_small_font = self._get_game_font(self.font_size(22, 16))

    def _apply_element_rect(self, element, rect: pygame.Rect) -> None:
        """Resize and reposition one pygame_gui element."""
        element.set_relative_position((rect.x, rect.y))
        element.set_dimensions((rect.width, rect.height))
    
    def _create_ui(self):
        """Create UI elements."""
        # Window dimensions
        WINDOW_WIDTH = self.window.WINDOW_WIDTH
        WINDOW_HEIGHT = self.window.WINDOW_HEIGHT
        
        # Consistent spacing
        MARGIN = 20
        BUTTON_WIDTH = 120
        BUTTON_HEIGHT = 40
        STATUS_HEIGHT = 40
        
        # Status label (top center)
        status_width = 400
        status_x = (WINDOW_WIDTH - status_width) // 2
        self.status_label = pygame_gui.elements.UILabel(
            relative_rect=pygame.Rect((status_x, MARGIN), (status_width, STATUS_HEIGHT)),
            text="Phase: Traversing",
            manager=self.ui_manager
        )
        
        # Info label (top right)
        info_width = 300
        info_x = WINDOW_WIDTH - info_width - MARGIN
        self.info_label = pygame_gui.elements.UILabel(
            relative_rect=pygame.Rect((info_x, MARGIN), (info_width, STATUS_HEIGHT)),
            text="P1 Damage: 0 | P2 Damage: 0",
            manager=self.ui_manager
        )
        
        # Movement buttons (left side, vertically centered relative to board)
        board_center_y = WINDOW_HEIGHT // 2
        button_spacing = 10
        total_button_height = 4 * BUTTON_HEIGHT + 3 * button_spacing
        move_start_y = board_center_y - total_button_height // 2
        
        self.move_buttons = []
        directions = ["Up", "Down", "Left", "Right"]
        for i, direction in enumerate(directions):
            btn_y = move_start_y + i * (BUTTON_HEIGHT + button_spacing)
            btn = pygame_gui.elements.UIButton(
                relative_rect=pygame.Rect((MARGIN, btn_y), (BUTTON_WIDTH, BUTTON_HEIGHT)),
                text=direction,
                manager=self.ui_manager,
                object_id=f"move_{direction.lower()}"
            )
            self.move_buttons.append((direction.lower(), btn))

        pickup_y = move_start_y + total_button_height + 20
        self.pickup_button = pygame_gui.elements.UIButton(
            relative_rect=pygame.Rect((MARGIN, pickup_y), (BUTTON_WIDTH, BUTTON_HEIGHT)),
            text="Pick Up",
            manager=self.ui_manager,
            object_id="pickup_current"
        )
        
        # Request buttons (right side, vertically centered relative to board)
        request_start_x = WINDOW_WIDTH - BUTTON_WIDTH - MARGIN
        request_start_y = board_center_y - total_button_height // 2
        
        self.request_buttons = []
        requests = ["Restructure", "Steal Life", "Ignore Us", "Plane Shift"]
        for i, request in enumerate(requests):
            btn_y = request_start_y + i * (BUTTON_HEIGHT + button_spacing)
            btn = pygame_gui.elements.UIButton(
                relative_rect=pygame.Rect((request_start_x, btn_y), (BUTTON_WIDTH, BUTTON_HEIGHT)),
                text=request,
                manager=self.ui_manager,
                object_id=f"request_{request.lower().replace(' ', '_')}"
            )
            self.request_buttons.append((request, btn))
    
        # Card buttons (bottom area for playing cards)
        card_area_y = WINDOW_HEIGHT - 120
        card_spacing = 10
        card_width = 100  # Wider for better text display
        card_height = 40
        
        # Show enough normal-hand slots for drafted cards plus collected/returned cards.
        self.card_buttons = []
        for i in range(10):
            card_x = MARGIN + i * (card_width + card_spacing)
            btn = pygame_gui.elements.UIButton(
                relative_rect=pygame.Rect((card_x, card_area_y), (card_width, card_height)),
                text=f"Card {i+1}",
                manager=self.ui_manager,
                object_id=f"card_{i}"
            )
            self.card_buttons.append(btn)
        
        # Jack labels (upper right, vertical line)
        jack_x = WINDOW_WIDTH - 150
        jack_y_start = MARGIN + 60  # Below status
        jack_spacing = 30
        
        self.jack_labels = []
        jack_roles = ["Walls", "Traps", "Ballista", "Weapons"]
        for i, role in enumerate(jack_roles):
            jack_y = jack_y_start + i * jack_spacing
            label = pygame_gui.elements.UILabel(
                relative_rect=pygame.Rect((jack_x, jack_y), (130, 25)),
                text=f"Jack {i+1}: {role}",
                manager=self.ui_manager
            )
            self.jack_labels.append(label)
        
        # Player hand labels (left side, below board)
        self.hand_labels = []
        for i in range(2):
            hand_y = WINDOW_HEIGHT - 175 + i * 28
            label = pygame_gui.elements.UILabel(
                relative_rect=pygame.Rect((MARGIN, hand_y), (260, 24)),
                text=f"Player {i+1} Turn",
                manager=self.ui_manager
            )
            self.hand_labels.append(label)

        # Active player's weapon pile on the right side.
        weapon_x = WINDOW_WIDTH - BUTTON_WIDTH - MARGIN
        weapon_label_y = 585
        weapon_button_y = weapon_label_y + 30
        weapon_button_height = 24
        weapon_button_spacing = 4
        weapon_slots = 9

        self.weapon_label = pygame_gui.elements.UILabel(
            relative_rect=pygame.Rect((weapon_x, weapon_label_y), (BUTTON_WIDTH, 24)),
            text="P1 Weapons",
            manager=self.ui_manager
        )

        for index in range(weapon_slots):
            btn_y = weapon_button_y + index * (weapon_button_height + weapon_button_spacing)
            btn = pygame_gui.elements.UIButton(
                relative_rect=pygame.Rect((weapon_x, btn_y), (BUTTON_WIDTH, weapon_button_height)),
                text="",
                manager=self.ui_manager,
                object_id=f"weapon_{index}"
            )
            self.weapon_buttons.append(btn)

        # Restructure suit/color choices, shown only while resolving Restructure.
        restructure_y = 360
        for index in range(4):
            btn = pygame_gui.elements.UIButton(
                relative_rect=pygame.Rect((weapon_x, restructure_y + index * 32), (BUTTON_WIDTH, 28)),
                text="",
                manager=self.ui_manager,
                object_id=f"restructure_suit_{index}"
            )
            self.restructure_buttons.append(btn)

        # Damage pile controls, shown only when a request needs direct damage-card selection.
        damage_label_y = MARGIN + 64
        damage_button_y = damage_label_y + 30
        damage_button_height = 28
        damage_button_spacing = 4
        damage_slots = 10

        for player_id in range(2):
            if player_id == 0:
                damage_x = MARGIN
            else:
                # Keep the right-side damage pile clear of the suit-role legend.
                damage_x = WINDOW_WIDTH - BUTTON_WIDTH - MARGIN - 170
            label = pygame_gui.elements.UILabel(
                relative_rect=pygame.Rect((damage_x, damage_label_y), (BUTTON_WIDTH, 24)),
                text=f"P{player_id + 1} Damage",
                manager=self.ui_manager
            )
            self.damage_labels.append(label)

            for index in range(damage_slots):
                btn_y = damage_button_y + index * (damage_button_height + damage_button_spacing)
                btn = pygame_gui.elements.UIButton(
                    relative_rect=pygame.Rect((damage_x, btn_y), (BUTTON_WIDTH, damage_button_height)),
                    text="",
                    manager=self.ui_manager,
                    object_id=f"damage_{player_id}_{index}"
                )
                self.damage_buttons[player_id].append(btn)

    def on_resize(self) -> None:
        """Relayout the gameplay UI when the window changes size."""
        self._refresh_fonts()
        self.renderer.update_layout(self.window.WINDOW_WIDTH, self.window.WINDOW_HEIGHT)
        board_rect = self.renderer.get_board_rect()
        compact = self.is_compact_layout()

        margin = self.scale(20, 12)
        button_width = max(
            self.scale(110, 92),
            min(self.scale(140, 108), board_rect.x - margin * 2, self.window.WINDOW_WIDTH - board_rect.right - margin * 2),
        )
        button_height = self.scale(40, 32)
        status_height = self.scale(40, 32)
        status_width = min(self.scale_x(520, 320), self.window.WINDOW_WIDTH - margin * 2)
        info_width = min(self.scale_x(320, 220), self.window.WINDOW_WIDTH - margin * 2)

        self._apply_element_rect(
            self.status_label,
            pygame.Rect(
                (self.window.WINDOW_WIDTH - status_width) // 2,
                margin,
                status_width,
                status_height,
            ),
        )
        self._apply_element_rect(
            self.info_label,
            pygame.Rect(
                self.window.WINDOW_WIDTH - info_width - margin,
                margin,
                info_width,
                status_height,
            ),
        )

        button_spacing = self.scale(10, 6)
        total_button_height = 4 * button_height + 3 * button_spacing
        left_panel_x = margin
        right_panel_x = self.window.WINDOW_WIDTH - button_width - margin
        move_start_y = board_rect.centery - total_button_height // 2

        for index, (_, button) in enumerate(self.move_buttons):
            self._apply_element_rect(
                button,
                pygame.Rect(
                    left_panel_x,
                    move_start_y + index * (button_height + button_spacing),
                    button_width,
                    button_height,
                ),
            )

        self._apply_element_rect(
            self.pickup_button,
            pygame.Rect(
                left_panel_x,
                move_start_y + total_button_height + self.scale(20, 12),
                button_width,
                button_height,
            ),
        )

        for index, (_, button) in enumerate(self.request_buttons):
            self._apply_element_rect(
                button,
                pygame.Rect(
                    right_panel_x,
                    move_start_y + index * (button_height + button_spacing),
                    button_width,
                    button_height,
                ),
            )

        card_spacing = self.scale(10, 4)
        card_height = self.scale_y(58, 48) if compact else self.scale_y(72, 60)
        bottom_margin = self.scale_y(18, 12) if compact else self.scale(26, 16)
        if compact:
            card_columns = 5
            card_rows = 2
            card_width = max(
                self.scale_x(56, 48),
                (self.window.WINDOW_WIDTH - 2 * margin - (card_columns - 1) * card_spacing) // card_columns,
            )
            total_cards_width = card_columns * card_width + (card_columns - 1) * card_spacing
            card_start_x = max(margin, (self.window.WINDOW_WIDTH - total_cards_width) // 2)
            card_row_y = self.window.WINDOW_HEIGHT - bottom_margin - card_rows * card_height - (card_rows - 1) * card_spacing
            for index, button in enumerate(self.card_buttons):
                row = index // card_columns
                col = index % card_columns
                self._apply_element_rect(
                    button,
                    pygame.Rect(
                        card_start_x + col * (card_width + card_spacing),
                        card_row_y + row * (card_height + card_spacing),
                        card_width,
                        card_height,
                    ),
                )
        else:
            card_row_y = self.window.WINDOW_HEIGHT - bottom_margin - card_height
            card_width = max(
                self.scale(72, 62),
                min(
                    self.scale(110, 96),
                    (self.window.WINDOW_WIDTH - 2 * margin - (len(self.card_buttons) - 1) * card_spacing) // len(self.card_buttons),
                ),
            )
            total_cards_width = len(self.card_buttons) * card_width + (len(self.card_buttons) - 1) * card_spacing
            card_start_x = max(margin, (self.window.WINDOW_WIDTH - total_cards_width) // 2)

            for index, button in enumerate(self.card_buttons):
                self._apply_element_rect(
                    button,
                    pygame.Rect(
                        card_start_x + index * (card_width + card_spacing),
                        card_row_y,
                        card_width,
                        card_height,
                    ),
                )

        hand_label_x = card_start_x
        hand_label_width = min(self.scale_x(260, 180), self.window.WINDOW_WIDTH - hand_label_x - margin)
        for index, label in enumerate(self.hand_labels):
            self._apply_element_rect(
                label,
                pygame.Rect(
                    hand_label_x,
                    card_row_y - self.scale(46, 34) + index * self.scale(24, 18) if compact else card_row_y - self.scale(54, 38) + index * self.scale(28, 20),
                    hand_label_width,
                    self.scale(24, 18),
                ),
            )

        jack_x = self.window.WINDOW_WIDTH - self.scale_x(150, 116)
        jack_y_start = margin + self.scale(60, 42)
        jack_spacing = self.scale(30, 22)
        for index, label in enumerate(self.jack_labels):
            self._apply_element_rect(
                label,
                pygame.Rect(
                    jack_x,
                    jack_y_start + index * jack_spacing,
                    self.scale_x(130, 104),
                    self.scale(25, 18),
                ),
            )

        weapon_button_height = self.scale_y(28, 22) if compact else self.scale(24, 20)
        weapon_button_spacing = self.scale(4, 2)
        if compact:
            weapon_label_y = board_rect.bottom + self.scale_y(8, 5)
            weapon_columns = 5
            weapon_width = max(
                self.scale_x(56, 48),
                (self.window.WINDOW_WIDTH - 2 * margin - (weapon_columns - 1) * weapon_button_spacing) // weapon_columns,
            )
            weapon_start_x = max(margin, (self.window.WINDOW_WIDTH - (weapon_columns * weapon_width + (weapon_columns - 1) * weapon_button_spacing)) // 2)
            self._apply_element_rect(
                self.weapon_label,
                pygame.Rect(margin, weapon_label_y, self.window.WINDOW_WIDTH - 2 * margin, self.scale(24, 18)),
            )
            for index, button in enumerate(self.weapon_buttons):
                row = index // weapon_columns
                col = index % weapon_columns
                self._apply_element_rect(
                    button,
                    pygame.Rect(
                        weapon_start_x + col * (weapon_width + weapon_button_spacing),
                        weapon_label_y + self.scale_y(26, 20) + row * (weapon_button_height + weapon_button_spacing),
                        weapon_width,
                        weapon_button_height,
                    ),
                )
        else:
            weapon_label_y = max(board_rect.top + self.scale(470, 310), move_start_y + total_button_height + self.scale(82, 54))
            weapon_button_y = weapon_label_y + self.scale(30, 22)
            self._apply_element_rect(
                self.weapon_label,
                pygame.Rect(right_panel_x, weapon_label_y, button_width, self.scale(24, 18)),
            )
            for index, button in enumerate(self.weapon_buttons):
                self._apply_element_rect(
                    button,
                    pygame.Rect(
                        right_panel_x,
                        weapon_button_y + index * (weapon_button_height + weapon_button_spacing),
                        button_width,
                        weapon_button_height,
                    ),
                )

        restructure_y = board_rect.top + self.scale(250, 172)
        restructure_height = self.scale(28, 22)
        for index, button in enumerate(self.restructure_buttons):
            self._apply_element_rect(
                button,
                pygame.Rect(
                    right_panel_x,
                    restructure_y + index * self.scale(32, 24),
                    button_width,
                    restructure_height,
                ),
            )

        damage_label_y = margin + self.scale(64, 46)
        damage_button_y = damage_label_y + self.scale(30, 22)
        damage_button_height = self.scale(28, 22)
        damage_button_spacing = self.scale(4, 2)
        right_damage_x = max(
            margin,
            self.window.WINDOW_WIDTH - button_width - margin - self.scale_x(170, 126),
        )

        for player_id, label in enumerate(self.damage_labels):
            damage_x = margin if player_id == 0 else right_damage_x
            self._apply_element_rect(
                label,
                pygame.Rect(damage_x, damage_label_y, button_width, self.scale(24, 18)),
            )

            for index, button in enumerate(self.damage_buttons[player_id]):
                self._apply_element_rect(
                    button,
                    pygame.Rect(
                        damage_x,
                        damage_button_y + index * (damage_button_height + damage_button_spacing),
                        button_width,
                        damage_button_height,
                    ),
                )
    
    def _hide_all_elements(self):
        """Hide all UI elements initially."""
        self.status_label.hide()
        self.info_label.hide()
        for _, btn in self.move_buttons:
            btn.hide()
        self.pickup_button.hide()
        for _, btn in self.request_buttons:
            btn.hide()
        for btn in self.card_buttons:
            btn.hide()
        self.weapon_label.hide()
        for btn in self.weapon_buttons:
            btn.hide()
        for btn in self.restructure_buttons:
            btn.hide()
        for label in self.jack_labels:
            label.hide()
        for label in self.hand_labels:
            label.hide()
        for label in self.damage_labels:
            label.hide()
        for buttons in self.damage_buttons.values():
            for btn in buttons:
                btn.hide()
    
    def handle_events(self, event: pygame.event.Event) -> bool:
        """Handle events."""
        if event.type == pygame.KEYDOWN and self.game.phase == GamePhase.SETUP:
            if event.key == pygame.K_SPACE:
                self.game.phase = GamePhase.TRAVERSING
                return True
        
        if event.type == pygame.MOUSEBUTTONDOWN:
            if self._handle_tutorial_toggle_click(event.pos):
                return True

            if self._handle_center_popup_click(event.pos):
                return True

            if self._handle_plane_shift_line_click(event.pos):
                return True

            if self._handle_pending_placement_mouse_down(event.pos):
                return True

            if self._handle_damage_popup_click(event.pos):
                return True

            if self._handle_damage_summary_click(event.pos):
                return True

            if self.game.has_pending_ballista() and hasattr(self.renderer, "BOARD_X"):
                clicked_cell = self.renderer.get_cell_at_mouse(event.pos)
                if clicked_cell is not None:
                    action = ResolveBallistaShotAction(
                        self.game.current_player,
                        clicked_cell.row,
                        clicked_cell.col,
                    )
                    self._apply_action(action)
                    return True

            if self.game.has_pending_card_placement() and hasattr(self.renderer, "BOARD_X"):
                return True
            elif self._handle_hand_card_click(event.pos):
                return True
            elif self.game.phase == GamePhase.TRAVERSING:
                action = self.input_handler.handle_mouse_click(
                    event.pos, self.game.current_player, self.game
                )
                if action:
                    self._apply_action(action)
                    return True
            elif (
                self.game.get_pending_request_type() == "plane_shift"
                and self.game.get_pending_plane_shift_direction() is not None
                and hasattr(self.renderer, "BOARD_X")
            ):
                clicked_cell = self.renderer.get_cell_at_mouse(event.pos)
                if clicked_cell is not None:
                    direction = self.game.get_pending_plane_shift_direction()
                    index = clicked_cell.row if direction in ["left", "right"] else clicked_cell.col
                    action = ResolvePlaneShiftAction(self.game.current_player, index)
                    self._apply_action(action)
                    return True

        elif event.type == pygame.MOUSEMOTION:
            self._update_plane_shift_hover(event.pos)
            if self._handle_pending_placement_mouse_motion(event.pos):
                return True

        elif event.type == pygame.MOUSEBUTTONUP:
            if self._handle_pending_placement_mouse_up(event.pos):
                return True
        
        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE and self.damage_popup_player is not None:
                self.damage_popup_player = None
                return True

            if (
                self.game.get_pending_request_type() == "plane_shift"
                and self.game.get_pending_plane_shift_direction() is None
            ):
                if self.pending_plane_shift_confirmation is not None:
                    if event.key in (pygame.K_RETURN, pygame.K_SPACE):
                        self._confirm_plane_shift()
                        return True
                    if event.key == pygame.K_ESCAPE:
                        self.pending_plane_shift_confirmation = None
                        return True
                    return True

                direction = DIRECTION_KEYS.get(event.key)

                if direction:
                    if self.pending_plane_shift_line is None:
                        return True
                    if self._commit_plane_shift_direction(direction):
                        return True
                    return True

            if self.game.phase == GamePhase.TRAVERSING and not self.game.has_pending_ballista():
                direction = DIRECTION_KEYS.get(event.key)
                
                if direction:
                    try:
                        action = MoveAction(self.game.current_player, direction)
                        self._apply_action(action)
                        print(f"Player {action.player_id + 1} moved {direction}")
                        return True
                    except Exception as e:
                        print(f"Move failed: {e}")
        
        elif event.type == pygame_gui.UI_BUTTON_PRESSED:
            # Card buttons
            for i, btn in enumerate(self.card_buttons):
                if event.ui_element == btn:
                    player_hand = self.game.get_player_hand(self.game.current_player)
                    if i < len(player_hand):
                        card = player_hand[i]
                        if self.game.phase == GamePhase.APPEASING:
                            action = PlayCardAction(self.game.current_player, card)
                            self._apply_action(action)
                            print(f"Player {action.player_id + 1} played {card}")
                    return True

        return False

    def _apply_action(self, action: Action) -> bool:
        """Apply a game action and trigger matching UI-side sounds."""
        had_combat = self.game.has_pending_combat()

        applied = self.game.apply_action(action)
        if not applied:
            return False

        audio = getattr(self.window, "audio", None)
        if audio is None:
            return True

        if not had_combat and self.game.has_pending_combat():
            audio.play_clash()
        return True

    def _handle_tutorial_toggle_click(self, pos: tuple[int, int]) -> bool:
        """Turn off tutorial tips from the currently visible tutorial panel."""
        if not self.window.tutorial_enabled or self.tutorial_toggle_rect is None:
            return False
        if not self.tutorial_toggle_rect.collidepoint(pos):
            return False
        self.window.tutorial_enabled = False
        self.tutorial_toggle_rect = None
        return True

    def reset_tutorial_cycle(self) -> None:
        """Let Settings restart the first Appeasing-cycle tutorial."""
        self._tutorial_seen_appeasing_cycle = False
        self._last_tutorial_phase = self.game.phase
        self.tutorial_toggle_rect = None

    def _update_tutorial_cycle_state(self) -> None:
        """Turn tutorials off after the first full Appeasing Pan cycle finishes."""
        if not self.window.tutorial_enabled:
            self.tutorial_toggle_rect = None
            self._last_tutorial_phase = self.game.phase
            return

        if self.game.phase == GamePhase.APPEASING:
            self._tutorial_seen_appeasing_cycle = True
        elif (
            self._tutorial_seen_appeasing_cycle
            and self._last_tutorial_phase == GamePhase.APPEASING
            and self.game.phase == GamePhase.TRAVERSING
        ):
            self.window.tutorial_enabled = False
            self.tutorial_toggle_rect = None

        self._last_tutorial_phase = self.game.phase
    
    def update(self, time_delta: float) -> None:
        """Update game state display."""
        self._update_tutorial_cycle_state()
        if getattr(self.window, "audio", None) is not None:
            self.window.audio.play_phase_music()
        self.plane_shift_preview_elapsed += time_delta * self.window.animation_speed

        for _ in range(6):
            if not self.game.advance_forced_traversing():
                break

        if self.notice_timer > 0:
            self.notice_timer = max(0.0, self.notice_timer - time_delta)
            if self.notice_timer == 0:
                self.notice_text = None

        return_notice = self.game.consume_appeasing_return_notice()
        if return_notice:
            self._show_notice(return_notice)

        # Update status
        player = f"P{self.game.current_player + 1}"
        pending_request_type = self.game.get_pending_request_type()
        if pending_request_type != "plane_shift":
            self.pending_plane_shift_line = None
            self.hovered_plane_shift_line = None
            self.pending_plane_shift_confirmation = None
        showing_request_selection = (
            self.game.phase == GamePhase.APPEASING
            and self.game.current_request_winner is not None
            and not self.game.has_pending_request_resolution()
            and not self.game.has_pending_card_placement()
        )
        
        if self.game.phase == GamePhase.SETUP:
            status_text = "SETUP: Drafting complete. Omens drawn and color roles assigned. Press SPACE to start game."
        elif self.game.has_pending_ballista():
            status_text = f"TRAVERSING BALLISTA: {player} clicks any reachable tile on the line"
        elif self.game.has_pending_combat():
            status_text = f"HEAD-TO-HEAD: {player} chooses a weapon-color hand card"
        elif self.game.has_pending_card_placement():
            pending_cards = self.game.get_pending_placement_cards()
            if pending_cards:
                status_text = f"APPEASING PAN: {player} places {self._format_card_label(pending_cards[0])} into a hole"
            else:
                status_text = "APPEASING PAN: Returning to the labyrinth..."
        elif pending_request_type == "steal_life":
            selected_card = self.game.get_pending_steal_life_card()
            if selected_card is None:
                status_text = f"APPEASING PAN: {player} selects their damage card first"
            else:
                status_text = f"APPEASING PAN: {player} selects enemy damage, or another own card to change"
        elif pending_request_type == "plane_shift":
            direction = self.game.get_pending_plane_shift_direction()
            if self.pending_plane_shift_confirmation is not None:
                axis, index, confirm_direction = self.pending_plane_shift_confirmation
                status_text = f"APPEASING PAN: {player} confirms {axis} {index + 1} shifts {confirm_direction}"
            elif direction is None and self.pending_plane_shift_line is None:
                status_text = f"APPEASING PAN: {player} clicks a numbered row or column"
            elif direction is None:
                axis, index = self.pending_plane_shift_line
                status_text = f"APPEASING PAN: {player} chooses how to shift {axis} {index + 1}"
            else:
                line_type = "row" if direction in ["left", "right"] else "column"
                status_text = f"APPEASING PAN: {player} clicks a {line_type} to shift {direction}"
        elif pending_request_type == "restructure":
            selected = len(self.game.get_pending_restructure_suits())
            status_text = f"APPEASING PAN: {player} chooses Restructure color {selected + 1} of 2 from the popup"
        elif self.game.phase == GamePhase.APPEASING:
            if self.game.current_request_winner is None:
                played_count = len(self.game.phase_started_cards)
                if played_count == 0:
                    status_text = f"APPEASING PAN: {player} plays a card"
                elif played_count == 1:
                    status_text = f"APPEASING PAN: {player} plays the second card"
                else:
                    status_text = "APPEASING PAN: Resolving duel..."
            else:
                status_text = f"APPEASING PAN: {player} chooses a request from the popup"
        else:
            status_text = f"TRAVERSING: {player} Turn (Move {self.game.movement_turn // 2 + 1})"
        
        self.status_label.set_text(status_text)
        self.info_label.hide()

        if (
            pending_request_type in {"steal_life", "restructure"}
            or showing_request_selection
            or self.game.has_pending_card_placement()
        ):
            self.damage_popup_player = None

        if not self.game.has_pending_card_placement():
            self.selected_placement_card_index = None
            self.dragging_placement_card_index = None
            self.dragging_placement_card_pos = None
            self.hovered_placement_target = None
        else:
            pending_cards = self.game.get_pending_placement_cards()
            if (
                self.selected_placement_card_index is not None
                and self.selected_placement_card_index >= len(pending_cards)
            ):
                self.selected_placement_card_index = None
            if (
                self.dragging_placement_card_index is not None
                and self.dragging_placement_card_index >= len(pending_cards)
            ):
                self.dragging_placement_card_index = None
                self.dragging_placement_card_pos = None
                self.hovered_placement_target = None

        if not self._is_hand_inspect_popup_active():
            self.inspected_hand_card_index = None

        # Update the small turn indicator above the card buttons.
        for i, label in enumerate(self.hand_labels):
            label.set_text(f"Player {i+1} Turn")
            if self.is_compact_layout() and self.game.has_pending_card_placement():
                label.hide()
            elif i == self.game.current_player:
                label.show()
            else:
                label.hide()
        
        for _, btn in self.move_buttons:
            btn.hide()
            btn.disabled = True

        self.pickup_button.hide()
        self.pickup_button.disabled = True
        
        for _, btn in self.request_buttons:
            btn.hide()
            btn.disabled = True
        
        # Hand cards are now drawn manually at labyrinth tile size.
        player_hand = self.game.get_player_hand(self.game.current_player)
        for btn in self.card_buttons:
            btn.set_text("")
            btn.disabled = True
            btn.hide()

        # Weapon cards are selected directly from the normal hand now.
        self.weapon_label.hide()
        for btn in self.weapon_buttons:
            btn.set_text("")
            btn.disabled = True
            btn.hide()

        # Update Restructure suit/color selector.
        for index, btn in enumerate(self.restructure_buttons):
            btn.set_text("")
            btn.disabled = True
            btn.hide()

        for label in self.damage_labels:
            label.hide()

        for buttons in self.damage_buttons.values():
            for btn in buttons:
                btn.set_text("")
                btn.disabled = True
                btn.hide()
        
        for label in self.jack_labels:
            label.hide()
    
    def render(self, surface: pygame.Surface) -> None:
        """Render game screen."""
        self._render_screen_background(surface, (20, 20, 30))
        
        suit_role_render = {}
        for suit, role in self.game.suit_roles.items():
            suit_role_render[suit] = role.value

        if self.game.has_pending_ballista():
            highlight_positions = set(self.game.get_pending_ballista_targets())
        elif self.game.has_pending_card_placement():
            highlight_positions = set(self.game.get_hole_positions())
        elif (
            self.game.get_pending_request_type() == "plane_shift"
            and self.pending_plane_shift_line is not None
        ):
            highlight_positions = self._get_plane_shift_line_positions(self.pending_plane_shift_line)
        elif (
            self.game.get_pending_request_type() == "plane_shift"
            and self.pending_plane_shift_confirmation is not None
        ):
            axis, index, _ = self.pending_plane_shift_confirmation
            highlight_positions = self._get_plane_shift_line_positions((axis, index))
        elif self.game.get_pending_request_type() == "plane_shift" and self.hovered_plane_shift_line is not None:
            highlight_positions = self._get_plane_shift_line_positions(self.hovered_plane_shift_line)
        else:
            highlight_positions = set()
        
        # Render board
        self.renderer.render(surface, self.game.board, suit_role_render, self.game.phase, highlight_positions)
        self._render_turn_move_highlights(surface)
        self._render_plane_shift_line_controls(surface)
        if self.game.has_pending_ballista():
            self._render_ballista_target_overlay(surface, highlight_positions)
        self._render_pending_placement_hover(surface)
        self._render_suit_role_legend(surface)
        self._render_rank_guide(surface)
        self._render_damage_summary(surface)
        self._render_hand_cards(surface)
        self._render_pending_placement_cards(surface)
        if self.game.phase == GamePhase.APPEASING:
            self._render_color_hierarchy_strip(surface)
        self._render_active_popups(surface)
        self._render_appeasing_result_banner(surface)
        self._render_notice_banner(surface)
        self._render_tutorial_overlay(surface)
    
    def on_enter(self) -> None:
        """Activate game screen."""
        if getattr(self.window, "audio", None) is not None:
            self.window.audio.play_phase_music()
        self.status_label.show()
        self.info_label.hide()
        for _, btn in self.move_buttons:
            btn.hide()
        self.pickup_button.hide()
        for _, btn in self.request_buttons:
            btn.hide()
        for btn in self.card_buttons:
            btn.show()
        self.weapon_label.hide()
        for btn in self.weapon_buttons:
            btn.hide()
        for btn in self.restructure_buttons:
            btn.hide()
        for label in self.jack_labels:
            label.hide()
        for label in self.hand_labels:
            label.show()
        for label in self.damage_labels:
            label.hide()
        for buttons in self.damage_buttons.values():
            for btn in buttons:
                btn.hide()
    
    def on_exit(self) -> None:
        """Deactivate game screen."""
        self.status_label.hide()
        self.info_label.hide()
        for _, btn in self.move_buttons:
            btn.hide()
        self.pickup_button.hide()
        for _, btn in self.request_buttons:
            btn.hide()
        for btn in self.card_buttons:
            btn.hide()
        self.weapon_label.hide()
        for btn in self.weapon_buttons:
            btn.hide()
        for btn in self.restructure_buttons:
            btn.hide()
        for label in self.jack_labels:
            label.hide()
        for label in self.hand_labels:
            label.hide()
        for label in self.damage_labels:
            label.hide()
        for buttons in self.damage_buttons.values():
            for btn in buttons:
                btn.hide()
        self.damage_popup_player = None

    def _format_card_label(self, card) -> str:
        """Render a compact label for a hand or damage card."""
        return f"{get_rank_name(card.rank)} {get_family_code(card.suit)}"

    def _get_card_role_name(self, card) -> str:
        """Return the current labyrinth role name for a card."""
        role = self.game.suit_roles.get(card.suit)
        return role.value.title() if role else "Unknown"

    def _get_card_role_short_name(self, card) -> str:
        """Return a short role label that fits narrow hand buttons."""
        role = self.game.suit_roles.get(card.suit)
        if role is None:
            return "?"
        return {
            "walls": "Wall",
            "traps": "Trap",
            "ballista": "Ball",
            "weapons": "Wpn",
        }.get(role.value, role.value[:4].title())

    def _format_card_role_label(self, card) -> str:
        """Render a compact card label with its current Omen role."""
        if self.is_compact_layout():
            return f"{get_rank_name(card.rank)} {get_family_code(card.suit)}\n{self._get_card_role_short_name(card)}"
        return f"{self._format_card_label(card)}\n{self._get_card_role_name(card)}"

    def _show_notice(self, text: str, seconds: float = 4.5) -> None:
        """Show a short gameplay notice banner."""
        self.notice_text = text
        self.notice_timer = seconds

    def _is_request_popup_active(self) -> bool:
        """Return True when the centered request chooser should be visible."""
        return (
            self.game.phase == GamePhase.APPEASING
            and self.game.current_request_winner is not None
            and not self.game.has_pending_request_resolution()
            and not self.game.has_pending_card_placement()
        )

    def _is_steal_life_popup_active(self) -> bool:
        """Return True when Steal Life card selection is in progress."""
        return self.game.get_pending_request_type() == "steal_life"

    def _is_restructure_popup_active(self) -> bool:
        """Return True when Restructure suit selection is in progress."""
        return self.game.get_pending_request_type() == "restructure"

    def _is_plane_shift_direction_popup_active(self) -> bool:
        """Return True when Plane Shift has a line selected and needs a direction."""
        return (
            self.game.get_pending_request_type() == "plane_shift"
            and self.game.get_pending_plane_shift_direction() is None
            and self.pending_plane_shift_line is not None
            and self.pending_plane_shift_confirmation is None
        )

    def _is_plane_shift_confirmation_popup_active(self) -> bool:
        """Return True when Plane Shift is waiting for final confirmation."""
        return (
            self.game.get_pending_request_type() == "plane_shift"
            and self.game.get_pending_plane_shift_direction() is None
            and self.pending_plane_shift_confirmation is not None
        )

    def _is_hand_inspect_popup_active(self) -> bool:
        """Return True when compact hand-card inspection is open."""
        cards = self.game.get_player_hand(self.game.current_player)
        return (
            self.inspected_hand_card_index is not None
            and self.is_compact_layout()
            and 0 <= self.inspected_hand_card_index < len(cards)
        )

    def _has_center_popup(self) -> bool:
        """Return True when a centered modal popup is active."""
        return any([
            self._is_hand_inspect_popup_active(),
            self._is_request_popup_active(),
            self._is_steal_life_popup_active(),
            self._is_restructure_popup_active(),
            self._is_plane_shift_direction_popup_active(),
            self._is_plane_shift_confirmation_popup_active(),
        ])

    def _get_centered_panel_rect(self, width: int, height: int) -> pygame.Rect:
        """Return a centered popup rect."""
        popup_margin = self.scale(20, 12)
        width = min(width, self.window.WINDOW_WIDTH - popup_margin * 2)
        height = min(height, self.window.WINDOW_HEIGHT - popup_margin * 2)
        return pygame.Rect(
            (self.window.WINDOW_WIDTH - width) // 2,
            (self.window.WINDOW_HEIGHT - height) // 2,
            width,
            height,
        )

    def _get_damage_summary_rects(self) -> dict[int, pygame.Rect]:
        """Return the clickable top-right damage summary rects."""
        if self.is_compact_layout():
            margin = self.scale_x(18, 12)
            gap = self.scale_x(10, 6)
            width = (self.window.WINDOW_WIDTH - 2 * margin - gap) // 2
            height = self.scale_y(28, 22)
            top = self.scale_y(58, 46)
            return {
                0: pygame.Rect(margin, top, width, height),
                1: pygame.Rect(margin + width + gap, top, width, height),
            }

        width = self.scale_x(184, 136)
        height = self.scale(32, 24)
        x = self.scale_x(24, 14)
        top = self.scale_y(18, 10)
        gap = self.scale_y(38, 28)
        return {
            0: pygame.Rect(x, top, width, height),
            1: pygame.Rect(x, top + gap, width, height),
        }

    def _get_request_popup_layout(self) -> tuple[pygame.Rect, list[tuple[str, pygame.Rect]]]:
        """Return request popup panel and button rects."""
        request_options = self._get_request_popup_options()
        cols = 1 if self.is_compact_layout() else (2 if len(request_options) > 1 else 1)
        rows = max(1, (len(request_options) + cols - 1) // cols)
        button_width = self.scale_x(360 if cols == 2 else 420, 250 if self.is_compact_layout() else 220)
        button_height = self.scale_y(82, 64) if self.is_compact_layout() else self.scale_y(100, 74)
        spacing_x = self.scale(20, 12)
        spacing_y = self.scale(18, 10)
        panel_width = cols * button_width + (cols - 1) * spacing_x + self.scale_x(60, 36)
        panel_height = rows * button_height + (rows - 1) * spacing_y + self.scale_y(110, 82)
        panel_rect = self._get_centered_panel_rect(panel_width, panel_height)

        rects = []
        for index, (request_type, _, _) in enumerate(request_options):
            row = index // cols
            col = index % cols
            rect = pygame.Rect(
                panel_rect.x + self.scale(30, 18) + col * (button_width + spacing_x),
                panel_rect.y + self.scale_y(66, 46) + row * (button_height + spacing_y),
                min(button_width, panel_rect.width - 2 * self.scale(30, 18)),
                button_height,
            )
            rects.append((request_type, rect))
        return panel_rect, rects

    def _get_request_popup_options(self) -> list[tuple[str, bool, str]]:
        """Return request popup entries with enabled state and optional disabled reason."""
        player_id = self.game.current_player
        options = []
        order = ["restructure", "steal_life", "ignore_us", "plane_shift"]

        for request_type in order:
            if request_type == "ignore_us" and player_id != self.game.current_request_winner:
                continue

            enabled = self.game.can_select_request_type(player_id, request_type)
            disabled_reason = ""
            if not enabled:
                disabled_reason = REQUEST_POPUP_COPY[request_type].get("disabled", "")
            options.append((request_type, enabled, disabled_reason))

        return options

    def _get_steal_life_popup_layout(self) -> tuple[pygame.Rect, list[tuple[int, object, pygame.Rect]]]:
        """Return Steal Life popup panel and clickable damage-card rects."""
        left_cards = self.game.damage[0].cards
        right_cards = self.game.damage[1].cards
        rows = max(1, len(left_cards), len(right_cards))
        panel_height = min(self.scale_y(170, 132) + rows * self.scale(36, 28), self.window.WINDOW_HEIGHT - self.scale(40, 24))
        panel_rect = self._get_centered_panel_rect(self.scale_x(840, 560), panel_height)

        rects = []
        lane_width = (
            (panel_rect.width - self.scale_x(76, 48)) // 2
            if self.is_compact_layout()
            else self.scale_x(330, 214)
        )
        start_y = panel_rect.y + self.scale(126, 92)
        left_x = panel_rect.x + self.scale(40, 24)
        right_x = panel_rect.right - self.scale(40, 24) - lane_width
        for player_id, cards, x in [
            (0, left_cards, left_x),
            (1, right_cards, right_x),
        ]:
            for index, card in enumerate(cards):
                rect = pygame.Rect(x, start_y + index * self.scale(36, 28), lane_width, self.scale(30, 22))
                rects.append((player_id, card, rect))
        return panel_rect, rects

    def _get_restructure_popup_layout(self) -> tuple[pygame.Rect, list[tuple[object, pygame.Rect]]]:
        """Return Restructure side-panel and suit button rects without covering the maze."""
        board_rect = self.renderer.get_board_rect()
        margin = self.scale(16, 10)
        gap = self.scale(12, 8)
        compact = self.is_compact_layout()
        button_height = self.scale_y(50, 38)
        spacing_y = self.scale_y(8, 6)
        header_height = self.scale_y(84, 62)
        panel_height = header_height + 4 * button_height + 3 * spacing_y + self.scale_y(22, 16)

        if board_rect.left >= self.scale_x(220, 170):
            panel_width = min(self.scale_x(250, 190), board_rect.left - margin - gap)
            panel_rect = pygame.Rect(
                margin,
                max(margin, board_rect.centery - panel_height // 2),
                panel_width,
                min(panel_height, self.window.WINDOW_HEIGHT - 2 * margin),
            )
        elif board_rect.right + self.scale_x(220, 170) + margin <= self.window.WINDOW_WIDTH:
            panel_width = min(self.scale_x(250, 190), self.window.WINDOW_WIDTH - board_rect.right - margin - gap)
            panel_rect = pygame.Rect(
                board_rect.right + gap,
                max(margin, board_rect.centery - panel_height // 2),
                panel_width,
                min(panel_height, self.window.WINDOW_HEIGHT - 2 * margin),
            )
        elif compact:
            panel_width = min(self.window.WINDOW_WIDTH - 2 * margin, self.scale_x(360, 300))
            panel_height = self.scale_y(154, 132)
            y = board_rect.bottom + gap
            if y + panel_height > self.window.WINDOW_HEIGHT - margin:
                y = max(margin, board_rect.top - panel_height - gap)
            panel_rect = pygame.Rect(
                (self.window.WINDOW_WIDTH - panel_width) // 2,
                y,
                panel_width,
                panel_height,
            )
        else:
            panel_width = min(self.scale_x(250, 190), self.window.WINDOW_WIDTH - 2 * margin)
            panel_rect = pygame.Rect(
                margin,
                max(margin, board_rect.top),
                panel_width,
                min(panel_height, self.window.WINDOW_HEIGHT - 2 * margin),
            )

        rects = []
        cols = 2 if compact and panel_rect.width >= self.scale_x(300, 260) else 1
        button_width = (
            (panel_rect.width - 2 * margin - (cols - 1) * gap) // cols
            if cols > 1
            else panel_rect.width - 2 * margin
        )
        start_y = panel_rect.y + (self.scale_y(74, 54) if cols == 1 else self.scale_y(72, 54))
        for index, suit in enumerate(self.game.jack_order):
            row = index // cols
            col = index % cols
            rect = pygame.Rect(
                panel_rect.x + margin + col * (button_width + gap),
                start_y + row * (button_height + spacing_y),
                button_width,
                button_height,
            )
            rects.append((suit, rect))
        return panel_rect, rects

    def _get_plane_shift_popup_layout(self) -> tuple[pygame.Rect, list[tuple[str, pygame.Rect]]]:
        """Return Plane Shift direction popup panel and direction rects."""
        directions = self._get_plane_shift_direction_options()
        panel_rect = self._get_centered_panel_rect(self.scale_x(500, 360), self.scale_y(190, 150))
        rects = []
        for index, direction in enumerate(directions):
            rect = pygame.Rect(
                panel_rect.x + self.scale(36, 22) + index * self.scale_x(214, 150),
                panel_rect.y + self.scale(96, 70),
                self.scale_x(180, 128),
                self.scale_y(46, 36),
            )
            rects.append((direction, rect))
        return panel_rect, rects

    def _get_plane_shift_confirmation_layout(self) -> tuple[pygame.Rect, dict[str, pygame.Rect]]:
        """Return Plane Shift confirmation popup and action button rects."""
        panel_rect = self._get_centered_panel_rect(self.scale_x(600, 370), self.scale_y(360, 300))
        button_width = (panel_rect.width - self.scale_x(76, 46)) // 2
        button_height = self.scale_y(46, 36)
        button_y = panel_rect.bottom - button_height - self.scale_y(24, 16)
        buttons = {
            "confirm": pygame.Rect(panel_rect.x + self.scale_x(24, 14), button_y, button_width, button_height),
            "change": pygame.Rect(
                panel_rect.right - self.scale_x(24, 14) - button_width,
                button_y,
                button_width,
                button_height,
            ),
        }
        return panel_rect, buttons

    def _get_plane_shift_confirmation_preview_rect(self, panel_rect: pygame.Rect) -> pygame.Rect:
        """Return the mini animation rect inside the confirmation popup."""
        return pygame.Rect(
            panel_rect.x + self.scale_x(28, 18),
            panel_rect.y + self.scale_y(116, 88),
            panel_rect.width - self.scale_x(56, 36),
            self.scale_y(136, 104),
        )

    def _get_plane_shift_direction_options(self) -> list[str]:
        """Return legal direction choices for the selected Plane Shift line."""
        if self.pending_plane_shift_line is None:
            return []
        axis, _ = self.pending_plane_shift_line
        return ["left", "right"] if axis == "row" else ["up", "down"]

    def _get_damage_popup_layout(self, player_id: int) -> tuple[pygame.Rect, list[tuple[object, pygame.Rect]]]:
        """Return the generic damage-pile popup layout for one player."""
        cards = self.game.damage[player_id].cards
        cols = 2 if len(cards) > 8 else 1
        rows = max(1, (len(cards) + cols - 1) // cols)
        panel_width = self.scale_x(580 if cols == 2 else 340, 240)
        panel_height = min(
            self.scale_y(128, 100) + rows * self.scale(34, 26),
            self.window.WINDOW_HEIGHT - self.scale(40, 24),
        )
        panel_rect = self._get_centered_panel_rect(panel_width, panel_height)

        rects = []
        col_width = self.scale_x(240, 172)
        start_x = panel_rect.x + self.scale(26, 16)
        start_y = panel_rect.y + self.scale(70, 52)
        for index, card in enumerate(cards):
            col = index // rows
            row = index % rows
            rect = pygame.Rect(
                start_x + col * (col_width + self.scale(24, 14)),
                start_y + row * self.scale(34, 26),
                col_width,
                self.scale(28, 22),
            )
            rects.append((card, rect))
        return panel_rect, rects

    def _get_hand_inspect_popup_layout(self) -> tuple[pygame.Rect, pygame.Rect, pygame.Rect, pygame.Rect]:
        """Return popup, enlarged card, play, and close rects for compact hand inspection."""
        panel_rect = self._get_centered_panel_rect(self.scale_x(460, 330), self.scale_y(450, 350))
        card_size = min(
            panel_rect.width - self.scale_x(88, 54),
            panel_rect.height - self.scale_y(178, 132),
            self.scale(230, 150),
        )
        card_rect = pygame.Rect(0, 0, card_size, card_size)
        card_rect.center = (panel_rect.centerx, panel_rect.y + self.scale_y(150, 112))

        button_width = (panel_rect.width - self.scale_x(72, 44)) // 2
        button_height = self.scale_y(46, 36)
        button_y = panel_rect.bottom - button_height - self.scale_y(26, 18)
        play_rect = pygame.Rect(panel_rect.x + self.scale_x(24, 14), button_y, button_width, button_height)
        close_rect = pygame.Rect(
            panel_rect.right - self.scale_x(24, 14) - button_width,
            button_y,
            button_width,
            button_height,
        )
        return panel_rect, card_rect, play_rect, close_rect

    def _get_plane_shift_line_controls(self) -> list[tuple[str, int, pygame.Rect]]:
        """Return row and column number controls around the board."""
        board_rect = self.renderer.get_board_rect()
        label_size = self.scale(30, 22)
        gap = self.scale(8, 5)
        controls = []

        row_x = max(self.scale_x(4, 2), board_rect.left - label_size - gap)
        for row in range(6):
            rect = pygame.Rect(
                row_x,
                board_rect.top + row * self.renderer.CELL_SIZE + (self.renderer.CELL_SIZE - label_size) // 2,
                label_size,
                label_size,
            )
            controls.append(("row", row, rect))

        col_y = min(
            self.window.WINDOW_HEIGHT - label_size - self.scale_y(4, 2),
            board_rect.bottom + gap,
        )
        for col in range(6):
            rect = pygame.Rect(
                board_rect.left + col * self.renderer.CELL_SIZE + (self.renderer.CELL_SIZE - label_size) // 2,
                col_y,
                label_size,
                label_size,
            )
            controls.append(("column", col, rect))

        return controls

    def _get_plane_shift_line_at(self, pos: tuple[int, int]) -> tuple[str, int] | None:
        """Return the numbered Plane Shift row or column at the mouse position."""
        if self.game.get_pending_request_type() != "plane_shift":
            return None
        if self.game.get_pending_plane_shift_direction() is not None:
            return None
        if self.pending_plane_shift_confirmation is not None:
            return None

        for axis, index, rect in self._get_plane_shift_line_controls():
            if rect.collidepoint(pos):
                return axis, index
        return None

    def _update_plane_shift_hover(self, pos: tuple[int, int]) -> None:
        """Track which Plane Shift line number the cursor is hovering."""
        hovered = self._get_plane_shift_line_at(pos)
        if hovered is not None:
            self.hovered_plane_shift_line = hovered
        elif self.game.get_pending_request_type() == "plane_shift":
            self.hovered_plane_shift_line = None

    def _handle_plane_shift_line_click(self, pos: tuple[int, int]) -> bool:
        """Select a numbered row or column before choosing Plane Shift direction."""
        line = self._get_plane_shift_line_at(pos)
        if line is None:
            return False
        self.pending_plane_shift_line = line
        self.hovered_plane_shift_line = line
        return True

    def _get_plane_shift_line_positions(self, line: tuple[str, int] | None) -> set[Position]:
        """Return board cells covered by a selected Plane Shift row or column."""
        if line is None:
            return set()
        axis, index = line
        if axis == "row":
            return {Position(index, col) for col in range(6)}
        return {Position(row, index) for row in range(6)}

    def _commit_plane_shift_direction(self, direction: str) -> bool:
        """Queue a Plane Shift direction and show confirmation before changing the board."""
        if self.pending_plane_shift_line is None:
            return False
        if direction not in self._get_plane_shift_direction_options():
            return False

        axis, index = self.pending_plane_shift_line
        self.pending_plane_shift_confirmation = (axis, index, direction)
        self.plane_shift_preview_elapsed = 0.0
        return True

    def _get_plane_shift_destination(self, pos: Position, axis: str, direction: str) -> Position:
        """Return where one selected line cell lands after the pending shift."""
        if axis == "row":
            delta = 1 if direction == "right" else -1
            return Position(pos.row, (pos.col + delta) % 6)

        delta = 1 if direction == "down" else -1
        return Position((pos.row + delta) % 6, pos.col)

    def _get_plane_shift_preview_progress(self) -> float:
        """Return forward-only preview progress that snaps back to the first frame."""
        cycle = (self.plane_shift_preview_elapsed % 1.15) / 1.15
        return cycle * cycle * (3.0 - 2.0 * cycle)

    def _confirm_plane_shift(self) -> bool:
        """Apply the selected Plane Shift after the confirmation popup."""
        if self.pending_plane_shift_confirmation is None:
            return False

        _, index, direction = self.pending_plane_shift_confirmation
        if not self._apply_action(SelectPlaneShiftDirectionAction(self.game.current_player, direction)):
            return False
        resolved = self._apply_action(ResolvePlaneShiftAction(self.game.current_player, index))
        if resolved:
            self.pending_plane_shift_line = None
            self.hovered_plane_shift_line = None
            self.pending_plane_shift_confirmation = None
        return resolved

    def _can_play_appeasing_hand_cards(self) -> bool:
        """Return True when the active player's hand cards can be played for Appeasing Pan."""
        return (
            self.game.phase == GamePhase.APPEASING
            and self.game.current_request_winner is None
            and not self.game.has_pending_request_resolution()
            and not self.game.has_pending_card_placement()
        )

    def _can_choose_hand_weapon(self) -> bool:
        """Return True when combat is waiting on a weapon card from the normal hand."""
        return self.game.has_pending_combat()

    def _can_use_hand_card_now(self, card) -> bool:
        """Return True when the clicked hand card has a valid immediate action."""
        if self._can_play_appeasing_hand_cards():
            return True
        if self._can_choose_hand_weapon():
            return self.game.can_use_weapon(self.game.current_player, card)
        return False

    def _get_hand_card_rects(self) -> list[tuple[int, pygame.Rect]]:
        """Return active-hand card rects at the same size as board tiles."""
        cards = self.game.get_player_hand(self.game.current_player)
        if not cards:
            return []

        tile_size = max(34, self.renderer.CELL_SIZE - 4)
        gap = self.scale(8, 4)
        margin = self.scale_x(24, 12)
        max_width = self.window.WINDOW_WIDTH - 2 * margin
        columns = max(1, min(len(cards), (max_width + gap) // (tile_size + gap)))
        if self.is_compact_layout():
            columns = min(columns, 5)
        rows = (len(cards) + columns - 1) // columns
        total_width = columns * tile_size + (columns - 1) * gap
        start_x = max(margin, (self.window.WINDOW_WIDTH - total_width) // 2)
        bottom_margin = self.scale_y(16, 10)
        hand_bottom = self.window.WINDOW_HEIGHT - bottom_margin
        if self.is_compact_layout() and self.game.has_pending_card_placement():
            placement_rects = [rect for _, rect in self._get_pending_placement_card_rects()]
            if placement_rects:
                hand_bottom = min(rect.top for rect in placement_rects) - self.scale_y(42, 30)
        start_y = hand_bottom - rows * tile_size - (rows - 1) * gap

        return [
            (
                index,
                pygame.Rect(
                    start_x + (index % columns) * (tile_size + gap),
                    start_y + (index // columns) * (tile_size + gap),
                    tile_size,
                    tile_size,
                ),
            )
            for index, _ in enumerate(cards)
        ]

    def _handle_hand_card_click(self, pos: tuple[int, int]) -> bool:
        """Inspect or play a manually rendered hand card."""
        player_hand = self.game.get_player_hand(self.game.current_player)
        for index, rect in self._get_hand_card_rects():
            if rect.collidepoint(pos) and index < len(player_hand):
                card = player_hand[index]
                if self._can_choose_hand_weapon():
                    if self.game.can_use_weapon(self.game.current_player, card):
                        player_id = self.game.current_player
                        if self._apply_action(ChooseCombatCardAction(player_id, card)):
                            print(f"Player {player_id + 1} used weapon card: {card}")
                    return True
                if self.is_compact_layout():
                    self.inspected_hand_card_index = index
                    return True
                if not self._can_play_appeasing_hand_cards():
                    return True
                player_id = self.game.current_player
                if self._apply_action(PlayCardAction(player_id, card)):
                    print(f"Player {player_id + 1} played {card}")
                return True
        return False

    def _handle_hand_inspect_popup_click(self, pos: tuple[int, int]) -> bool:
        """Handle compact enlarged hand-card popup actions."""
        if not self._is_hand_inspect_popup_active():
            return False

        panel_rect, _, play_rect, close_rect = self._get_hand_inspect_popup_layout()
        if close_rect.collidepoint(pos) or not panel_rect.collidepoint(pos):
            self.inspected_hand_card_index = None
            return True

        if play_rect.collidepoint(pos):
            player_hand = self.game.get_player_hand(self.game.current_player)
            index = self.inspected_hand_card_index
            if index is not None and index < len(player_hand):
                card = player_hand[index]
                if not self._can_use_hand_card_now(card):
                    return True
                player_id = self.game.current_player
                self.inspected_hand_card_index = None
                if self._can_choose_hand_weapon():
                    if self._apply_action(ChooseCombatCardAction(player_id, card)):
                        print(f"Player {player_id + 1} used weapon card: {card}")
                elif self._can_play_appeasing_hand_cards():
                    if self._apply_action(PlayCardAction(player_id, card)):
                        print(f"Player {player_id + 1} played {card}")
            return True

        return True

    def _handle_center_popup_click(self, pos: tuple[int, int]) -> bool:
        """Handle clicks inside the centered modal popups."""
        if self._handle_hand_inspect_popup_click(pos):
            return True

        if self._is_request_popup_active():
            panel_rect, option_rects = self._get_request_popup_layout()
            option_states = {
                request_type: enabled
                for request_type, enabled, _ in self._get_request_popup_options()
            }
            if not panel_rect.collidepoint(pos):
                return True
            for request_type, rect in option_rects:
                if rect.collidepoint(pos):
                    if option_states.get(request_type, False):
                        action = ChooseRequestAction(self.game.current_player, REQUEST_TYPE_MAP[request_type])
                        self._apply_action(action)
                    return True
            return True

        if self._is_steal_life_popup_active():
            panel_rect, card_rects = self._get_steal_life_popup_layout()
            if not panel_rect.collidepoint(pos):
                return True
            for player_id, card, rect in card_rects:
                if rect.collidepoint(pos):
                    action = SelectDamageCardAction(self.game.current_player, player_id, card)
                    self._apply_action(action)
                    return True
            return True

        if self._is_restructure_popup_active():
            panel_rect, suit_rects = self._get_restructure_popup_layout()
            if not panel_rect.collidepoint(pos):
                return True
            for suit, rect in suit_rects:
                if rect.collidepoint(pos):
                    action = SelectRestructureSuitAction(self.game.current_player, suit)
                    self._apply_action(action)
                    return True
            return True

        if self._is_plane_shift_direction_popup_active():
            panel_rect, direction_rects = self._get_plane_shift_popup_layout()
            if not panel_rect.collidepoint(pos):
                self.pending_plane_shift_line = None
                return True
            for direction, rect in direction_rects:
                if rect.collidepoint(pos):
                    self._commit_plane_shift_direction(direction)
                    return True
            return True

        if self._is_plane_shift_confirmation_popup_active():
            panel_rect, buttons = self._get_plane_shift_confirmation_layout()
            if not panel_rect.collidepoint(pos):
                return True
            if buttons["confirm"].collidepoint(pos):
                self._confirm_plane_shift()
                return True
            if buttons["change"].collidepoint(pos):
                self.pending_plane_shift_confirmation = None
                return True
            return True

        return False

    def _handle_damage_summary_click(self, pos: tuple[int, int]) -> bool:
        """Toggle the generic damage-pile popup when a summary chip is clicked."""
        if self._has_center_popup():
            return False

        for player_id, rect in self._get_damage_summary_rects().items():
            if rect.collidepoint(pos):
                self.damage_popup_player = None if self.damage_popup_player == player_id else player_id
                return True
        return False

    def _handle_damage_popup_click(self, pos: tuple[int, int]) -> bool:
        """Consume clicks while a generic damage popup is open."""
        if self.damage_popup_player is None or self._has_center_popup():
            return False

        for player_id, rect in self._get_damage_summary_rects().items():
            if rect.collidepoint(pos):
                self.damage_popup_player = None if self.damage_popup_player == player_id else player_id
                return True

        panel_rect, _ = self._get_damage_popup_layout(self.damage_popup_player)
        if panel_rect.collidepoint(pos):
            return True

        self.damage_popup_player = None
        return True

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
        """Draw wrapped text clipped to the given rect."""
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

    def _render_popup_backdrop(self, surface: pygame.Surface, alpha: int = 150) -> None:
        """Render a dim backdrop behind an active popup."""
        overlay = pygame.Surface((self.window.WINDOW_WIDTH, self.window.WINDOW_HEIGHT), pygame.SRCALPHA)
        overlay.fill((6, 8, 14, alpha))
        surface.blit(overlay, (0, 0))

    def _render_game_wood_button(
        self,
        surface: pygame.Surface,
        rect: pygame.Rect,
        label: str,
        *,
        enabled: bool = True,
        selected: bool = False,
        preferred_font_size: int | None = None,
    ) -> None:
        """Render an in-game action as a title-screen wood button."""
        hovered = enabled and rect.collidepoint(pygame.mouse.get_pos())
        self._render_wood_button(
            surface,
            rect,
            label,
            hovered or selected,
            preferred_font_size if preferred_font_size is not None else self.font_size(24, 16),
            enabled=enabled,
        )

    def _render_damage_summary(self, surface: pygame.Surface) -> None:
        """Render clickable damage summary chips."""
        for player_id, rect in self._get_damage_summary_rects().items():
            active = self.damage_popup_player == player_id
            self._render_game_wood_button(
                surface,
                rect,
                f"P{player_id + 1} Damage: {self.game.get_damage_total(player_id)}",
                selected=active,
                preferred_font_size=self.font_size(18, 13),
            )

    def _render_turn_move_highlights(self, surface: pygame.Surface) -> None:
        """Highlight the active player and their legal movement targets."""
        if self.game.phase != GamePhase.TRAVERSING:
            return
        if self.game.has_pending_ballista() or self.game.has_pending_combat():
            return

        current_pos = self.game.board.get_player_position(self.game.current_player)
        if current_pos is None:
            return

        player_color = (236, 78, 78) if self.game.current_player == 0 else (92, 132, 245)
        current_rect = self.renderer.get_cell_rect(current_pos)
        pygame.draw.rect(
            surface,
            player_color,
            current_rect.inflate(self.scale(8, 5), self.scale(8, 5)),
            self.scale(4, 3),
            border_radius=self.scale(12, 8),
        )

        for direction in self.game.get_legal_moves(self.game.current_player):
            dr, dc = direction_to_movement(direction)
            target = Position((current_pos.row + dr) % 6, (current_pos.col + dc) % 6)
            rect = self.renderer.get_cell_rect(target)
            glow = pygame.Surface(rect.size, pygame.SRCALPHA)
            pygame.draw.circle(glow, (116, 226, 156, 150), (rect.width // 2, rect.height // 2), max(7, rect.width // 8))
            pygame.draw.circle(glow, (218, 255, 225, 210), (rect.width // 2, rect.height // 2), max(3, rect.width // 18))
            surface.blit(glow, rect.topleft)
            self.renderer.draw_value_safe_outline(
                surface,
                rect.inflate(-self.scale(12, 8), -self.scale(12, 8)),
                (116, 226, 156),
                self.scale(2, 2),
            )

    def _render_plane_shift_line_controls(self, surface: pygame.Surface) -> None:
        """Render numbered Plane Shift row and column selectors."""
        if self.game.get_pending_request_type() != "plane_shift":
            return
        if self.game.get_pending_plane_shift_direction() is not None:
            return

        selected = self.pending_plane_shift_line
        hovered = self.hovered_plane_shift_line
        for axis, index, rect in self._get_plane_shift_line_controls():
            active = selected == (axis, index)
            hover = hovered == (axis, index)
            self._render_wood_button(
                surface,
                rect,
                str(index + 1),
                hover or active,
                self.font_size(20, 14),
            )

        line = selected or hovered
        if line is not None:
            for pos in self._get_plane_shift_line_positions(line):
                rect = self.renderer.get_cell_rect(pos)
                pygame.draw.rect(
                    surface,
                    (252, 222, 104),
                    rect.inflate(-self.scale(8, 5), -self.scale(8, 5)),
                    self.scale(3, 2),
                    border_radius=self.scale(9, 6),
                )

    def _render_plane_shift_board_preview(self, surface: pygame.Surface) -> None:
        """Animate the selected Plane Shift line toward its destination cells."""
        if self.pending_plane_shift_confirmation is None:
            return

        axis, _, direction = self.pending_plane_shift_confirmation
        progress = self._get_plane_shift_preview_progress()
        positions = sorted(
            self._get_plane_shift_line_positions((axis, self.pending_plane_shift_confirmation[1])),
            key=lambda pos: (pos.row, pos.col),
        )
        for pos in positions:
            source_rect = self.renderer.get_cell_rect(pos)
            destination = self._get_plane_shift_destination(pos, axis, direction)
            destination_rect = self.renderer.get_cell_rect(destination)

            pygame.draw.rect(
                surface,
                (116, 226, 190),
                destination_rect.inflate(-self.scale(14, 9), -self.scale(14, 9)),
                self.scale(2, 1),
                border_radius=self.scale(8, 5),
            )

            dot_x = int(source_rect.centerx + (destination_rect.centerx - source_rect.centerx) * progress)
            dot_y = int(source_rect.centery + (destination_rect.centery - source_rect.centery) * progress)
            pygame.draw.circle(surface, (255, 240, 142), (dot_x, dot_y), self.scale(5, 3))

    def _render_hand_cards(self, surface: pygame.Surface) -> None:
        """Render the active player's hand as same-size labyrinth tiles."""
        rects = self._get_hand_card_rects()
        self.hand_card_rects = rects
        if not rects:
            return

        cards = self.game.get_player_hand(self.game.current_player)
        can_play_appeasing = self._can_play_appeasing_hand_cards()
        choosing_weapon = self._can_choose_hand_weapon()
        title_rect = pygame.Rect(
            rects[0][1].x,
            rects[0][1].y - self.scale_y(32, 24),
            min(self.scale_x(330, 210), self.window.WINDOW_WIDTH - rects[0][1].x - self.scale_x(16, 8)),
            self.scale_y(26, 20),
        )
        pygame.draw.rect(surface, (22, 26, 36), title_rect, border_radius=self.scale(9, 6))
        pygame.draw.rect(surface, (100, 108, 124), title_rect, 1, border_radius=self.scale(9, 6))
        if choosing_weapon:
            prompt = "Pick a weapon from hand"
        elif can_play_appeasing:
            prompt = "Tap card to Inspect" if self.is_compact_layout() else "Click a card to play"
        else:
            prompt = "Active Hand"
        title = self.popup_small_font.render(f"P{self.game.current_player + 1} {prompt}", True, (232, 232, 232))
        surface.blit(title, title.get_rect(center=title_rect.center))

        suit_role_render = {
            suit: role.value
            for suit, role in self.game.suit_roles.items()
        }
        for index, rect in rects:
            if index >= len(cards):
                continue
            card = cards[index]
            self.renderer.render_card_tile(
                surface,
                card,
                suit_role_render.get(card.suit),
                rect,
                self.game.phase,
                dimmed=choosing_weapon and not self.game.can_use_weapon(self.game.current_player, card),
            )
            usable = self._can_use_hand_card_now(card)
            border = (252, 222, 104) if usable else (110, 116, 130)
            pygame.draw.rect(surface, border, rect, self.scale(3 if usable else 2, 1), border_radius=self.scale(8, 5))
            if self.is_compact_layout() and not choosing_weapon:
                self._render_compact_hand_inspect_hint(surface, rect, usable)

    def _render_compact_hand_inspect_hint(self, surface: pygame.Surface, rect: pygame.Rect, usable: bool) -> None:
        """Draw a small compact-card hint that tapping opens Inspect first."""
        hint_height = max(self.scale_y(14, 11), rect.height // 5)
        hint_rect = pygame.Rect(
            rect.x + self.scale(3, 2),
            rect.bottom - hint_height - self.scale(3, 2),
            rect.width - 2 * self.scale(3, 2),
            hint_height,
        )
        fill = (30, 34, 44, 214) if usable else (24, 26, 34, 190)
        hint_surface = pygame.Surface(hint_rect.size, pygame.SRCALPHA)
        pygame.draw.rect(hint_surface, fill, hint_surface.get_rect(), border_radius=self.scale(5, 3))
        surface.blit(hint_surface, hint_rect.topleft)

        label = "Tap Inspect" if hint_rect.width >= self.scale_x(58, 48) else "Inspect"
        text = self.popup_small_font.render(label, True, (248, 238, 188) if usable else (184, 184, 190))
        surface.blit(text, text.get_rect(center=hint_rect.center))


    def _render_ballista_target_overlay(self, surface: pygame.Surface, targets: set[Position]) -> None:
        """Dim unreachable cells and draw Ballista launch paths."""
        if not targets:
            return

        start = self.game.board.get_player_position(self.game.current_player)
        if start is None:
            return

        dim = pygame.Surface((self.window.WINDOW_WIDTH, self.window.WINDOW_HEIGHT), pygame.SRCALPHA)
        for row in range(6):
            for col in range(6):
                pos = Position(row, col)
                if pos == start or pos in targets:
                    continue
                pygame.draw.rect(dim, (4, 6, 12, 132), self.renderer.get_cell_rect(pos), border_radius=self.scale(8, 5))
        surface.blit(dim, (0, 0))

        line_color = (255, 218, 96)
        for path in self._get_ballista_target_paths(start, targets):
            previous = start
            for target in path:
                self._draw_ballista_segment(surface, previous, target, line_color)
                previous = target

        for pos in targets:
            rect = self.renderer.get_cell_rect(pos)
            center = rect.center
            pygame.draw.circle(surface, (255, 224, 104), center, self.scale(13, 8), 3)
            pygame.draw.circle(surface, (255, 246, 180), center, self.scale(5, 3))
            self.renderer.draw_value_safe_outline(
                surface,
                rect.inflate(-self.scale(10, 6), -self.scale(10, 6)),
                (255, 224, 104),
                3,
            )

    def _get_ballista_target_paths(self, start: Position, targets: set[Position]) -> list[list[Position]]:
        """Return reachable Ballista paths grouped by launch direction."""
        movements = [(-1, 0), (1, 0), (0, -1), (0, 1)]
        paths = []
        for dr, dc in movements:
            current = start
            path = []
            for _ in range(5):
                candidate = Position((current.row + dr) % 6, (current.col + dc) % 6)
                if candidate not in targets:
                    break
                path.append(candidate)
                current = candidate
            if path:
                paths.append(path)
        return paths

    def _draw_ballista_segment(
        self,
        surface: pygame.Surface,
        start: Position,
        end: Position,
        color: tuple[int, int, int],
    ) -> None:
        """Draw one Ballista path segment, splitting edge-wrap jumps."""
        start_rect = self.renderer.get_cell_rect(start)
        end_rect = self.renderer.get_cell_rect(end)
        start_center = start_rect.center
        end_center = end_rect.center
        width = max(3, self.scale(4, 3))

        if start.row == end.row and abs(start.col - end.col) == 5:
            y = start_center[1]
            if start.col == 0 and end.col == 5:
                pygame.draw.line(surface, color, start_center, (start_rect.left, y), width)
                pygame.draw.line(surface, color, (end_rect.right, y), end_center, width)
            else:
                pygame.draw.line(surface, color, start_center, (start_rect.right, y), width)
                pygame.draw.line(surface, color, (end_rect.left, y), end_center, width)
            return

        if start.col == end.col and abs(start.row - end.row) == 5:
            x = start_center[0]
            if start.row == 0 and end.row == 5:
                pygame.draw.line(surface, color, start_center, (x, start_rect.top), width)
                pygame.draw.line(surface, color, (x, end_rect.bottom), end_center, width)
            else:
                pygame.draw.line(surface, color, start_center, (x, start_rect.bottom), width)
                pygame.draw.line(surface, color, (x, end_rect.top), end_center, width)
            return

        pygame.draw.line(surface, color, start_center, end_center, width)

    def _render_appeasing_result_banner(self, surface: pygame.Surface) -> None:
        """Render a short explanation of the latest Appeasing Pan duel result."""
        if (
            self.game.phase != GamePhase.APPEASING
            or self.game.current_request_winner is None
            or len(self.game.phase_started_cards) != 2
        ):
            return

        played_cards = {player_id: card for player_id, card in self.game.phase_started_cards}
        winner = self.game.current_request_winner
        loser = 1 - winner
        if winner not in played_cards or loser not in played_cards:
            return

        winner_card = played_cards[winner]
        loser_card = played_cards[loser]
        title = f"P{winner + 1} wins Appeasing Pan"
        detail = (
            f"{self._format_card_role_label(winner_card)} beats "
            f"{self._format_card_role_label(loser_card)} - "
            f"{self._describe_appeasing_win(winner, winner_card, loser_card)}"
        )

        rect = pygame.Rect(
            self.window.WINDOW_WIDTH // 2 - self.scale_x(330, 230),
            self.scale_y(112, 82),
            self.scale_x(660, 460),
            self.scale_y(62, 48),
        )
        pygame.draw.rect(surface, (31, 36, 48), rect, border_radius=self.scale(14, 9))
        pygame.draw.rect(surface, (226, 198, 102), rect, 2, border_radius=self.scale(14, 9))

        title_surface = self.popup_body_font.render(title, True, (246, 232, 172))
        surface.blit(title_surface, (rect.x + self.scale(18, 12), rect.y + self.scale(8, 5)))
        detail_rect = pygame.Rect(
            rect.x + self.scale(18, 12),
            rect.y + self.scale(32, 24),
            rect.width - self.scale(36, 24),
            rect.height - self.scale(36, 26),
        )
        self._draw_wrapped_text(
            surface,
            detail,
            self.popup_small_font,
            (228, 228, 228),
            detail_rect,
            self.scale(18, 13),
            2,
        )

    def _describe_appeasing_win(self, winner: int, winner_card, loser_card) -> str:
        """Describe whether the Appeasing duel was won by role strength or rank."""
        if winner_card.suit != loser_card.suit:
            return (
                f"stronger color role ({self._get_card_role_name(winner_card)} "
                f"beats {self._get_card_role_name(loser_card)})."
            )

        winner_value = winner_card.combat_value()
        loser_value = loser_card.combat_value()
        if winner_value != loser_value:
            return f"higher rank ({winner_value} beats {loser_value})."

        return f"exact tie; P{winner + 1} keeps the request choice."

    def _render_notice_banner(self, surface: pygame.Surface) -> None:
        """Render a transient gameplay notice if one is active."""
        if not self.notice_text or self.notice_timer <= 0:
            return

        result_banner_active = (
            self.game.phase == GamePhase.APPEASING
            and self.game.current_request_winner is not None
            and len(self.game.phase_started_cards) == 2
        )
        y = self.scale_y(184, 136) if result_banner_active else self.scale_y(112, 82)
        rect = pygame.Rect(
            self.window.WINDOW_WIDTH // 2 - self.scale_x(300, 210),
            y,
            self.scale_x(600, 420),
            self.scale_y(44, 34),
        )
        pygame.draw.rect(surface, (44, 52, 66), rect, border_radius=self.scale(12, 8))
        pygame.draw.rect(surface, (154, 188, 218), rect, 2, border_radius=self.scale(12, 8))
        text_rect = rect.inflate(-self.scale(24, 16), -self.scale(8, 6))
        self._draw_wrapped_text(
            surface,
            self.notice_text,
            self.popup_small_font,
            (236, 238, 240),
            text_rect,
            self.scale(18, 13),
            2,
        )

    def _render_tutorial_overlay(self, surface: pygame.Surface) -> None:
        """Render optional context-sensitive tutorial guidance."""
        if not self.window.tutorial_enabled:
            self.tutorial_toggle_rect = None
            return

        board_rect = self.renderer.get_board_rect()
        target_rect = board_rect
        popup_target, popup_text = self._get_active_popup_tutorial_target()
        if popup_target is not None and popup_text is not None:
            target_rect = popup_target
            text = popup_text
        elif self.game.has_pending_ballista():
            text = "Tutorial: click one of the glowing Ballista targets. The yellow line shows the launch path."
        elif self.game.has_pending_card_placement():
            text = "Tutorial: drag each played card onto an open hole. Occupied spaces are not valid holes."
            card_rects = [rect for _, rect in self._get_pending_placement_card_rects()]
            if card_rects:
                target_rect = card_rects[0].copy()
                for rect in card_rects[1:]:
                    target_rect.union_ip(rect)
        elif self.game.phase == GamePhase.APPEASING and self.game.current_request_winner is None:
            text = "Tutorial: play one hand card for Appeasing Pan. Color role wins first, then rank breaks ties."
            hand_rects = [rect for _, rect in self._get_hand_card_rects()]
            if hand_rects:
                target_rect = hand_rects[0].copy()
                for rect in hand_rects[1:]:
                    target_rect.union_ip(rect)
        elif self.game.get_pending_request_type() == "plane_shift":
            text = "Tutorial: click a numbered row or column, then choose its shift direction."
            controls = [rect for _, _, rect in self._get_plane_shift_line_controls()]
            if controls:
                target_rect = controls[0].copy()
                for rect in controls[1:]:
                    target_rect.union_ip(rect)
        elif self.game.phase == GamePhase.APPEASING:
            text = "Tutorial: choose a request. The winner chooses first; the loser chooses second unless Ignore Us is picked."
        elif self.game.phase == GamePhase.TRAVERSING:
            text = "Tutorial: click an adjacent board space to move. The board wraps around its edges."
        else:
            return

        pygame.draw.rect(surface, (252, 222, 104), target_rect.inflate(self.scale(10, 6), self.scale(10, 6)), 3, border_radius=10)
        panel_width = min(self.scale_x(720, 330), self.window.WINDOW_WIDTH - 2 * self.scale_x(20, 12))
        panel_height = self.scale_y(46, 36)
        panel_y = self.scale_y(132, 96)
        if target_rect.top < self.window.WINDOW_HEIGHT // 2:
            panel_y = min(self.window.WINDOW_HEIGHT - panel_height - self.scale_y(16, 10), target_rect.bottom + self.scale_y(12, 8))
        panel_rect = pygame.Rect((self.window.WINDOW_WIDTH - panel_width) // 2, panel_y, panel_width, panel_height)
        pygame.draw.rect(surface, (24, 28, 40), panel_rect, border_radius=self.scale(10, 6))
        pygame.draw.rect(surface, (252, 222, 104), panel_rect, 2, border_radius=self.scale(10, 6))
        button_width = min(self.scale_x(132, 92), max(self.scale_x(86, 72), panel_rect.width // 4))
        button_height = max(self.scale_y(24, 20), panel_rect.height - self.scale_y(14, 10))
        self.tutorial_toggle_rect = pygame.Rect(
            panel_rect.right - button_width - self.scale_x(8, 5),
            panel_rect.centery - button_height // 2,
            button_width,
            button_height,
        )
        self._render_game_wood_button(
            surface,
            self.tutorial_toggle_rect,
            "Tips Off",
            preferred_font_size=self.font_size(16, 12),
        )

        text_rect = panel_rect.inflate(-self.scale(20, 12), -self.scale(8, 6))
        text_rect.width -= button_width + self.scale_x(10, 6)
        self._draw_wrapped_text(
            surface,
            text,
            self.popup_small_font,
            (238, 238, 238),
            text_rect,
            self.scale_y(18, 13),
            2,
        )

    def _get_active_popup_tutorial_target(self) -> tuple[pygame.Rect | None, str | None]:
        """Return the active modal rect so tutorial highlights do not cover it from behind."""
        if self._is_hand_inspect_popup_active():
            panel_rect, _, _, _ = self._get_hand_inspect_popup_layout()
            return panel_rect, "Tutorial: inspect the enlarged card, then play it or close this view."

        if self._is_request_popup_active():
            panel_rect, _ = self._get_request_popup_layout()
            return (
                panel_rect,
                "Tutorial: choose a request. The winner chooses first; the loser chooses second unless Ignore Us is picked.",
            )

        if self._is_steal_life_popup_active():
            panel_rect, _ = self._get_steal_life_popup_layout()
            return panel_rect, "Tutorial: choose one of your damage cards. You can change it before picking the enemy card."

        if self._is_restructure_popup_active():
            panel_rect, _ = self._get_restructure_popup_layout()
            return panel_rect, "Tutorial: choose two omen colors to swap their labyrinth roles."

        if self._is_plane_shift_direction_popup_active():
            panel_rect, _ = self._get_plane_shift_popup_layout()
            return panel_rect, "Tutorial: choose the Plane Shift direction for the selected row or column."

        if self._is_plane_shift_confirmation_popup_active():
            panel_rect, _ = self._get_plane_shift_confirmation_layout()
            return panel_rect, "Tutorial: confirm Plane Shift only after checking the highlighted row or column."

        if self.damage_popup_player is not None:
            panel_rect, _ = self._get_damage_popup_layout(self.damage_popup_player)
            return panel_rect, "Tutorial: review this damage pile, then click outside the popup to close it."

        return None, None

    def _render_active_popups(self, surface: pygame.Surface) -> None:
        """Render whichever modal popup is currently active."""
        if self._is_hand_inspect_popup_active():
            self._render_popup_backdrop(surface)
            self._render_hand_inspect_popup(surface)
            return

        if self._is_request_popup_active():
            self._render_popup_backdrop(surface)
            self._render_request_popup(surface)
            return

        if self._is_steal_life_popup_active():
            self._render_popup_backdrop(surface)
            self._render_steal_life_popup(surface)
            return

        if self._is_restructure_popup_active():
            self._render_restructure_popup(surface)
            return

        if self._is_plane_shift_direction_popup_active():
            self._render_popup_backdrop(surface)
            self._render_plane_shift_direction_popup(surface)
            return

        if self._is_plane_shift_confirmation_popup_active():
            self._render_popup_backdrop(surface, alpha=118)
            self._render_plane_shift_board_preview(surface)
            self._render_plane_shift_confirmation_popup(surface)
            return

        if self.damage_popup_player is not None:
            self._render_popup_backdrop(surface, alpha=110)
            self._render_damage_popup(surface, self.damage_popup_player)

    def _render_request_popup(self, surface: pygame.Surface) -> None:
        """Render the centered request-selection popup."""
        panel_rect, option_rects = self._get_request_popup_layout()
        option_states = {
            request_type: (enabled, disabled_reason)
            for request_type, enabled, disabled_reason in self._get_request_popup_options()
        }
        pygame.draw.rect(surface, (20, 24, 34), panel_rect, border_radius=18)
        pygame.draw.rect(surface, (140, 146, 165), panel_rect, 2, border_radius=18)

        title = self.popup_title_font.render("Choose Pan's Request", True, (240, 236, 214))
        surface.blit(title, (panel_rect.x + self.scale(28, 18), panel_rect.y + self.scale(18, 12)))

        subtitle = self.popup_small_font.render(
            f"Player {self.game.current_player + 1} chooses now.",
            True,
            (198, 198, 198),
        )
        surface.blit(subtitle, (panel_rect.x + self.scale(30, 18), panel_rect.y + self.scale(50, 36)))

        for request_type, rect in option_rects:
            copy = REQUEST_POPUP_COPY[request_type]
            enabled, disabled_reason = option_states[request_type]
            body_color = (208, 208, 208) if enabled else (136, 136, 144)
            detail_color = (170, 200, 220) if enabled else (200, 164, 124)

            wood_rect = pygame.Rect(
                rect.x + self.scale_x(4, 3),
                rect.y + self.scale_y(2, 1),
                rect.width - self.scale_x(8, 6),
                min(rect.height - self.scale_y(30, 22), self._get_wood_icon_height_for_width(rect.width - self.scale_x(8, 6))),
            )
            wood_rect.height = max(self.scale_y(44, 34), wood_rect.height)
            wood_rect.height = min(rect.height, wood_rect.height)
            self._render_game_wood_button(
                surface,
                wood_rect,
                copy["title"],
                enabled=enabled,
                preferred_font_size=self.font_size(26, 18),
            )

            detail_top = wood_rect.bottom + self.scale_y(2, 1)
            detail_rect = pygame.Rect(
                rect.x + self.scale(16, 10),
                detail_top,
                rect.width - self.scale(32, 20),
                max(self.scale_y(18, 14), rect.bottom - detail_top - self.scale_y(2, 1)),
            )

            self._draw_wrapped_text(
                surface,
                disabled_reason if not enabled and disabled_reason else copy["description"],
                self.popup_small_font,
                detail_color if not enabled and disabled_reason else body_color,
                detail_rect,
                line_height=self.scale(18, 14),
                max_lines=2,
            )

    def _render_hand_inspect_popup(self, surface: pygame.Surface) -> None:
        """Render a compact-layout enlarged hand-card inspection popup."""
        if not self._is_hand_inspect_popup_active():
            return

        player_hand = self.game.get_player_hand(self.game.current_player)
        card = player_hand[self.inspected_hand_card_index]
        panel_rect, card_rect, play_rect, close_rect = self._get_hand_inspect_popup_layout()

        pygame.draw.rect(surface, (20, 24, 34), panel_rect, border_radius=18)
        pygame.draw.rect(surface, (252, 222, 104), panel_rect, 2, border_radius=18)

        title = self.popup_title_font.render("Inspect Card", True, (240, 236, 214))
        surface.blit(title, (panel_rect.x + self.scale(26, 16), panel_rect.y + self.scale(18, 12)))

        subtitle = self.popup_small_font.render(
            f"P{self.game.current_player + 1}: {self._format_card_label(card)} - {self._get_card_role_name(card)}",
            True,
            (210, 210, 210),
        )
        surface.blit(subtitle, (panel_rect.x + self.scale(28, 18), panel_rect.y + self.scale(56, 40)))

        role = self.game.suit_roles.get(card.suit)
        self.renderer.render_card_tile(surface, card, role.value if role else None, card_rect, self.game.phase)
        pygame.draw.rect(surface, (252, 222, 104), card_rect, 3, border_radius=self.scale(10, 6))

        can_use = self._can_use_hand_card_now(card)
        action_label = "Use Weapon" if self._can_choose_hand_weapon() else "Play Card"
        buttons = [
            (play_rect, action_label, can_use),
            (close_rect, "Close", True),
        ]
        for rect, label, enabled in buttons:
            self._render_game_wood_button(
                surface,
                rect,
                label,
                enabled=enabled,
                preferred_font_size=self.font_size(20, 14),
            )

    def _render_steal_life_popup(self, surface: pygame.Surface) -> None:
        """Render the centered Steal Life selector."""
        panel_rect, card_rects = self._get_steal_life_popup_layout()
        chooser = self.game.current_player
        selected_own = self.game.get_pending_steal_life_card()
        first_selection_pending = selected_own is None

        pygame.draw.rect(surface, (20, 24, 34), panel_rect, border_radius=18)
        pygame.draw.rect(surface, (146, 126, 112), panel_rect, 2, border_radius=18)

        title = self.popup_title_font.render("Steal Life", True, (240, 236, 214))
        surface.blit(title, (panel_rect.x + self.scale(30, 18), panel_rect.y + self.scale(18, 12)))

        instruction = "Select your damage card first. You can change it before choosing the enemy card."
        self._draw_wrapped_text(
            surface,
            instruction,
            self.popup_small_font,
            (212, 212, 212),
            pygame.Rect(
                panel_rect.x + self.scale(30, 18),
                panel_rect.y + self.scale(54, 38),
                panel_rect.width - self.scale(60, 36),
                self.scale(36, 28),
            ),
            line_height=self.scale(18, 14),
            max_lines=2,
        )

        headings = {
            0: (panel_rect.x + self.scale(40, 24), f"P1 Damage ({self.game.get_damage_total(0)})"),
            1: (panel_rect.centerx + self.scale(20, 12), f"P2 Damage ({self.game.get_damage_total(1)})"),
        }
        for player_id, (x, text) in headings.items():
            highlight = player_id == chooser if first_selection_pending else True
            color = (240, 220, 150) if highlight else (200, 200, 200)
            heading = self.popup_body_font.render(text, True, color)
            surface.blit(heading, (x, panel_rect.y + self.scale(92, 68)))

        if not card_rects:
            empty = self.popup_body_font.render("No damage cards available.", True, (210, 210, 210))
            empty_rect = empty.get_rect(center=panel_rect.center)
            surface.blit(empty, empty_rect)
            return

        for player_id, card, rect in card_rects:
            selectable = player_id == chooser if first_selection_pending else True
            is_selected = player_id == chooser and selected_own == card
            fill = (70, 84, 102) if selectable else (44, 46, 56)
            border = (234, 201, 114) if is_selected else ((110, 116, 130) if selectable else (78, 82, 92))
            text_color = (238, 238, 238) if selectable else (156, 156, 156)

            pygame.draw.rect(surface, fill, rect, border_radius=10)
            pygame.draw.rect(surface, border, rect, 2, border_radius=10)
            label = self.popup_small_font.render(
                f"{self._format_card_label(card)} ({card.combat_value()})",
                True,
                text_color,
            )
            surface.blit(label, (rect.x + self.scale(12, 8), rect.y + self.scale(6, 4)))

    def _render_restructure_popup(self, surface: pygame.Surface) -> None:
        """Render the off-board Restructure color selector."""
        panel_rect, suit_rects = self._get_restructure_popup_layout()
        selected_suits = set(self.game.get_pending_restructure_suits())

        shadow = pygame.Surface(panel_rect.size, pygame.SRCALPHA)
        pygame.draw.rect(shadow, (0, 0, 0, 110), shadow.get_rect(), border_radius=18)
        surface.blit(shadow, panel_rect.move(self.scale(5, 3), self.scale(7, 4)).topleft)
        pygame.draw.rect(surface, (20, 24, 34), panel_rect, border_radius=18)
        pygame.draw.rect(surface, (128, 158, 188), panel_rect, 2, border_radius=18)

        title = self.popup_title_font.render("Restructure", True, (240, 236, 214))
        surface.blit(title, (panel_rect.x + self.scale(18, 12), panel_rect.y + self.scale(14, 10)))

        self._draw_wrapped_text(
            surface,
            "Choose two colors to swap. The maze stays visible for planning.",
            self.popup_small_font,
            (210, 210, 210),
            pygame.Rect(
                panel_rect.x + self.scale(18, 12),
                panel_rect.y + self.scale(44, 32),
                panel_rect.width - self.scale(36, 24),
                self.scale_y(34, 26),
            ),
            self.scale_y(16, 12),
            2,
        )

        for suit, rect in suit_rects:
            role = self.game.suit_roles.get(suit)
            selected = suit in selected_suits
            self._render_game_wood_button(
                surface,
                rect,
                get_family_name(suit),
                selected=selected,
                preferred_font_size=self.font_size(20, 14),
            )

            icon_x = rect.x + self.scale(18, 12)
            draw_suit_icon(surface, suit, (icon_x, rect.centery), size=self.scale(10, 6))

            role_text = role.value.title() if role else "Unknown"
            detail = self.popup_small_font.render(role_text, True, (232, 222, 192) if selected else (194, 204, 220))
            detail_rect = detail.get_rect(center=(rect.centerx, rect.y + int(rect.height * 0.70)))
            surface.blit(detail, detail_rect)

    def _render_plane_shift_direction_popup(self, surface: pygame.Surface) -> None:
        """Render the centered Plane Shift direction picker."""
        panel_rect, direction_rects = self._get_plane_shift_popup_layout()
        pygame.draw.rect(surface, (20, 24, 34), panel_rect, border_radius=18)
        pygame.draw.rect(surface, (150, 138, 188), panel_rect, 2, border_radius=18)

        selected_text = "line"
        if self.pending_plane_shift_line is not None:
            axis, index = self.pending_plane_shift_line
            selected_text = f"{axis} {index + 1}"

        title = self.popup_title_font.render("Plane Shift", True, (240, 236, 214))
        surface.blit(title, (panel_rect.x + self.scale(28, 18), panel_rect.y + self.scale(18, 12)))

        subtitle = self.popup_small_font.render(
            f"Choose the direction for {selected_text}.",
            True,
            (210, 210, 210),
        )
        surface.blit(subtitle, (panel_rect.x + self.scale(28, 18), panel_rect.y + self.scale(56, 40)))

        labels = {
            "up": "Shift Up",
            "left": "Shift Left",
            "right": "Shift Right",
            "down": "Shift Down",
        }
        for direction, rect in direction_rects:
            self._render_game_wood_button(
                surface,
                rect,
                labels[direction],
                preferred_font_size=self.font_size(22, 15),
            )

    def _render_plane_shift_confirmation_popup(self, surface: pygame.Surface) -> None:
        """Render final confirmation before Plane Shift changes the board."""
        if self.pending_plane_shift_confirmation is None:
            return

        axis, index, direction = self.pending_plane_shift_confirmation
        panel_rect, buttons = self._get_plane_shift_confirmation_layout()
        pygame.draw.rect(surface, (20, 24, 34), panel_rect, border_radius=18)
        pygame.draw.rect(surface, (252, 222, 104), panel_rect, 2, border_radius=18)

        title = self.popup_title_font.render("Confirm Plane Shift", True, (240, 236, 214))
        surface.blit(title, (panel_rect.x + self.scale(28, 18), panel_rect.y + self.scale(18, 12)))

        line_name = f"{axis.title()} {index + 1}"
        detail = f"{line_name} will shift {direction}. This moves the row/column immediately."
        self._draw_wrapped_text(
            surface,
            detail,
            self.popup_small_font,
            (218, 218, 218),
            pygame.Rect(
                panel_rect.x + self.scale(28, 18),
                panel_rect.y + self.scale(60, 42),
                panel_rect.width - self.scale(56, 36),
                self.scale_y(50, 38),
            ),
            self.scale_y(18, 14),
            2,
        )

        preview_rect = self._get_plane_shift_confirmation_preview_rect(panel_rect)
        self._render_plane_shift_popup_preview(surface, preview_rect, axis, direction)

        for key, label in [("confirm", "Apply Shift"), ("change", "Change Direction")]:
            rect = buttons[key]
            self._render_game_wood_button(
                surface,
                rect,
                label,
                selected=key == "confirm",
                preferred_font_size=self.font_size(18, 13),
            )

    def _render_plane_shift_popup_preview(
        self,
        surface: pygame.Surface,
        preview_rect: pygame.Rect,
        axis: str,
        direction: str,
    ) -> None:
        """Render a mini animated line preview inside the confirmation popup."""
        pygame.draw.rect(surface, (28, 34, 46), preview_rect, border_radius=self.scale(12, 8))
        pygame.draw.rect(surface, (114, 132, 158), preview_rect, 1, border_radius=self.scale(12, 8))

        label = self.popup_small_font.render(
            f"{axis.title()} preview: shifting {direction}",
            True,
            (210, 218, 228),
        )
        surface.blit(label, (preview_rect.x + self.scale(12, 8), preview_rect.y + self.scale(6, 4)))

        top = preview_rect.y + self.scale_y(30, 22)
        bottom = preview_rect.bottom - self.scale_y(8, 5)
        if axis == "column":
            cell_gap = self.scale(4, 2)
            available_height = max(1, bottom - top)
            cell_size = max(
                self.scale(8, 6),
                min(
                    self.scale(26, 18),
                    preview_rect.width // 5,
                    max(1, (available_height - 5 * cell_gap) // 6),
                ),
            )
            total_height = 6 * cell_size + 5 * cell_gap
            start_x = preview_rect.centerx - cell_size // 2
            start_y = top + max(0, (available_height - total_height) // 2)
            slots = [
                pygame.Rect(start_x, start_y + index * (cell_size + cell_gap), cell_size, cell_size)
                for index in range(6)
            ]
        else:
            cell_gap = self.scale(6, 4)
            available_width = preview_rect.width - self.scale_x(24, 16)
            available_height = max(1, bottom - top)
            cell_size = max(
                self.scale(10, 8),
                min(
                    self.scale(34, 24),
                    max(1, (available_width - 5 * cell_gap) // 6),
                    available_height,
                ),
            )
            total_width = 6 * cell_size + 5 * cell_gap
            start_x = preview_rect.x + (preview_rect.width - total_width) // 2
            slots = [
                pygame.Rect(start_x + index * (cell_size + cell_gap), top, cell_size, cell_size)
                for index in range(6)
            ]

        for slot in slots:
            pygame.draw.rect(surface, (18, 22, 30), slot, border_radius=self.scale(6, 4))
            pygame.draw.rect(surface, (78, 88, 108), slot, 1, border_radius=self.scale(6, 4))

        sign = 1 if direction in {"right", "down"} else -1
        progress = self._get_plane_shift_preview_progress()
        for index, slot in enumerate(slots):
            target = slots[(index + sign) % 6]
            x = int(slot.x + (target.x - slot.x) * progress)
            y = int(slot.y + (target.y - slot.y) * progress)
            moving = pygame.Rect(x, y, slot.width, slot.height)
            pygame.draw.rect(surface, (70, 88, 112), moving, border_radius=self.scale(6, 4))
            pygame.draw.rect(surface, (252, 222, 104), moving, 1, border_radius=self.scale(6, 4))
            number = self.popup_small_font.render(str(index + 1), True, (246, 238, 204))
            surface.blit(number, number.get_rect(center=moving.center))

    def _render_damage_popup(self, surface: pygame.Surface, player_id: int) -> None:
        """Render a centered popup listing one player's damage pile."""
        panel_rect, card_rects = self._get_damage_popup_layout(player_id)
        pygame.draw.rect(surface, (22, 26, 36), panel_rect, border_radius=18)
        pygame.draw.rect(surface, (136, 142, 160), panel_rect, 2, border_radius=18)

        title = self.popup_title_font.render(
            f"P{player_id + 1} Damage Pile ({self.game.get_damage_total(player_id)})",
            True,
            (240, 236, 214),
        )
        surface.blit(title, (panel_rect.x + self.scale(24, 16), panel_rect.y + self.scale(18, 12)))

        subtitle = self.popup_small_font.render("Click outside this popup to close it.", True, (192, 192, 192))
        surface.blit(subtitle, (panel_rect.x + self.scale(26, 16), panel_rect.y + self.scale(50, 36)))

        if not card_rects:
            empty = self.popup_body_font.render("No damage cards yet.", True, (212, 212, 212))
            empty_rect = empty.get_rect(center=panel_rect.center)
            surface.blit(empty, empty_rect)
            return

        for card, rect in card_rects:
            pygame.draw.rect(surface, (42, 48, 62), rect, border_radius=10)
            pygame.draw.rect(surface, (100, 108, 124), rect, 1, border_radius=10)
            label = self.popup_small_font.render(
                f"{self._format_card_label(card)} ({card.combat_value()})",
                True,
                (236, 236, 236),
            )
            surface.blit(label, (rect.x + self.scale(10, 6), rect.y + self.scale(6, 4)))

    def _get_pending_placement_card_rects(self) -> list[tuple[int, pygame.Rect]]:
        """Return same-size labyrinth tile rects for pending hole placement."""
        if not self.game.has_pending_card_placement():
            return []

        cards = self.game.get_pending_placement_cards()
        tile_size = max(34, self.renderer.CELL_SIZE - 4)
        spacing = self.scale(10, 6)

        if self.is_compact_layout():
            total_width = len(cards) * tile_size + max(0, len(cards) - 1) * spacing
            x = max(self.scale_x(18, 12), (self.window.WINDOW_WIDTH - total_width) // 2)
            y = self.window.WINDOW_HEIGHT - tile_size - self.scale_y(18, 12)
            return [
                (index, pygame.Rect(x + index * (tile_size + spacing), y, tile_size, tile_size))
                for index, _ in enumerate(cards)
            ]

        board_rect = self.renderer.get_board_rect()
        x = max(self.scale_x(18, 12), board_rect.left - tile_size - self.scale_x(34, 18))
        y = board_rect.top + self.scale_y(50, 34)
        return [
            (index, pygame.Rect(x, y + index * (tile_size + spacing), tile_size, tile_size))
            for index, _ in enumerate(cards)
        ]

    def _get_hovered_placement_target(self, mouse_pos: tuple[int, int]) -> Position | None:
        """Return the hovered board tile while dragging a pending placement card."""
        if not self.game.has_pending_card_placement() or not hasattr(self.renderer, "BOARD_X"):
            return None
        return self.renderer.get_cell_at_mouse(mouse_pos)

    def _is_valid_placement_target(self, pos: Position | None) -> bool:
        """Return True when the hovered tile is a valid hole target."""
        if pos is None:
            return False
        return pos in set(self.game.get_hole_positions())

    def _handle_pending_placement_mouse_down(self, pos: tuple[int, int]) -> bool:
        """Start dragging a pending placement card from the left-side stack."""
        if not self.game.has_pending_card_placement():
            return False

        for index, rect in self._get_pending_placement_card_rects():
            if rect.collidepoint(pos):
                self.selected_placement_card_index = index
                self.dragging_placement_card_index = index
                self.dragging_placement_card_pos = pos
                self.hovered_placement_target = self._get_hovered_placement_target(pos)
                return True
        return False

    def _handle_pending_placement_mouse_motion(self, pos: tuple[int, int]) -> bool:
        """Track the dragged pending placement card and hovered drop target."""
        if self.dragging_placement_card_index is None:
            return False

        self.dragging_placement_card_pos = pos
        self.hovered_placement_target = self._get_hovered_placement_target(pos)
        return True

    def _handle_pending_placement_mouse_up(self, pos: tuple[int, int]) -> bool:
        """Drop the dragged pending placement card onto a valid hole target."""
        if self.dragging_placement_card_index is None:
            return False

        drag_index = self.dragging_placement_card_index
        target = self._get_hovered_placement_target(pos)
        self.dragging_placement_card_pos = pos
        self.hovered_placement_target = target
        placed = False

        if self._is_valid_placement_target(target):
            action = PlaceCardsAction(
                self.game.current_player,
                [target],
                [drag_index],
            )
            placed = self._apply_action(action)

        self.dragging_placement_card_index = None
        self.dragging_placement_card_pos = None
        self.hovered_placement_target = None

        if placed:
            pending_cards = self.game.get_pending_placement_cards()
            if not pending_cards:
                self.selected_placement_card_index = None
            elif drag_index >= len(pending_cards):
                self.selected_placement_card_index = len(pending_cards) - 1
            else:
                self.selected_placement_card_index = drag_index
            return True

        self.selected_placement_card_index = drag_index
        return True

    def _render_pending_placement_hover(self, surface: pygame.Surface) -> None:
        """Render hover feedback for the current drag target."""
        if self.dragging_placement_card_index is None or self.hovered_placement_target is None:
            return

        rect = self.renderer.get_cell_rect(self.hovered_placement_target)
        color = (108, 235, 148) if self._is_valid_placement_target(self.hovered_placement_target) else (232, 112, 112)
        inset = self.scale(8, 4)
        pygame.draw.rect(surface, color, rect.inflate(-inset, -inset), 4, border_radius=self.scale(10, 6))

    def _render_pending_placement_cards(self, surface: pygame.Surface) -> None:
        """Render draggable pending placement cards on the left side of the screen."""
        if not self.game.has_pending_card_placement():
            return

        cards = self.game.get_pending_placement_cards()
        if not cards:
            return

        card_rects = self._get_pending_placement_card_rects()
        if not card_rects:
            return

        group_rect = card_rects[0][1].copy()
        for _, rect in card_rects[1:]:
            group_rect.union_ip(rect)

        if self.is_compact_layout():
            header_rect = pygame.Rect(
                max(self.scale_x(18, 12), group_rect.x),
                group_rect.y - self.scale_y(36, 28),
                min(self.window.WINDOW_WIDTH - 2 * self.scale_x(18, 12), max(group_rect.width, self.scale_x(260, 210))),
                self.scale_y(30, 24),
            )
        else:
            header_rect = pygame.Rect(
                group_rect.x,
                max(self.scale_y(82, 60), group_rect.y - self.scale_y(44, 32)),
                max(group_rect.width, self.scale_x(178, 138)),
                self.scale_y(34, 26),
            )
        pygame.draw.rect(surface, (28, 32, 44), header_rect, border_radius=self.scale(10, 6))
        pygame.draw.rect(surface, (98, 108, 126), header_rect, 1, border_radius=self.scale(10, 6))
        header = self.popup_small_font.render("Drag a Played Card", True, (232, 232, 232))
        header_rect_text = header.get_rect(center=header_rect.center)
        surface.blit(header, header_rect_text)

        if not self.is_compact_layout():
            instructions = self.popup_small_font.render("Hold, drag to a hole, release.", True, (186, 186, 186))
            surface.blit(instructions, (self.scale_x(28, 16), self.scale_y(146, 108)))

        for index, rect in card_rects:
            if index >= len(cards):
                continue
            selected = index == self.selected_placement_card_index
            dragging = index == self.dragging_placement_card_index
            self._render_pending_card_face(surface, rect, cards[index], selected=selected, dimmed=dragging)

        if (
            self.dragging_placement_card_index is not None
            and self.dragging_placement_card_pos is not None
            and self.dragging_placement_card_index < len(cards)
        ):
            tile_size = max(34, self.renderer.CELL_SIZE - 4)
            drag_rect = pygame.Rect(
                0,
                0,
                tile_size,
                tile_size,
            )
            drag_rect.center = self.dragging_placement_card_pos
            self._render_pending_card_face(
                surface,
                drag_rect,
                cards[self.dragging_placement_card_index],
                selected=True,
                floating=True,
            )

    def _render_pending_card_face(
        self,
        surface: pygame.Surface,
        rect: pygame.Rect,
        card,
        *,
        selected: bool = False,
        dimmed: bool = False,
        floating: bool = False,
    ) -> None:
        """Render a pending post-Appeasing card exactly like a labyrinth tile."""
        if floating:
            shadow = pygame.Surface(rect.size, pygame.SRCALPHA)
            pygame.draw.rect(shadow, (0, 0, 0, 80), shadow.get_rect(), border_radius=10)
            surface.blit(shadow, rect.move(self.scale(6, 4), self.scale(8, 6)))

        role = self.game.suit_roles.get(card.suit)
        self.renderer.render_card_tile(surface, card, role.value if role else None, rect, self.game.phase, dimmed=dimmed)
        border = (252, 222, 104) if selected or floating else (110, 116, 130)
        pygame.draw.rect(surface, border, rect, self.scale(3 if selected or floating else 2, 1), border_radius=self.scale(8, 5))

    def _render_suit_role_legend(self, surface: pygame.Surface) -> None:
        """Render suit-role mappings with drawn icons instead of font glyphs."""
        if self.is_compact_layout():
            if self.game.phase == GamePhase.APPEASING:
                return
            margin = self.scale_x(18, 12)
            gap = self.scale_x(10, 6)
            chip_width = (self.window.WINDOW_WIDTH - 2 * margin - gap) // 2
            chip_height = self.scale_y(24, 20)
            start_y = self.scale_y(88, 72)
            for index, suit in enumerate(self.game.jack_order):
                role = self.game.suit_roles.get(suit)
                row = index // 2
                col = index % 2
                rect = pygame.Rect(
                    margin + col * (chip_width + gap),
                    start_y + row * (chip_height + self.scale_y(6, 4)),
                    chip_width,
                    chip_height,
                )
                pygame.draw.rect(surface, (30, 34, 46), rect, border_radius=self.scale(9, 6))
                pygame.draw.rect(surface, (92, 104, 124), rect, 1, border_radius=self.scale(9, 6))
                draw_suit_icon(surface, suit, (rect.x + self.scale(14, 9), rect.centery), size=self.scale(8, 5))
                role_text = role.value.title() if role else "Unknown"
                label = self.renderer.font_small.render(f"{get_family_name(suit)}: {role_text}", True, (218, 218, 218))
                surface.blit(label, (rect.x + self.scale(28, 18), rect.y + self.scale(4, 3)))
            return

        start_x = self.window.WINDOW_WIDTH - self.scale_x(215, 156)
        start_y = self.scale_y(82, 62)
        row_height = self.scale(30, 22)

        for index, suit in enumerate(self.game.jack_order):
            role = self.game.suit_roles.get(suit)
            y = start_y + index * row_height
            draw_suit_icon(surface, suit, (start_x + self.scale(12, 8), y + self.scale(10, 6)), size=self.scale(12, 7))
            family = get_family_name(suit)
            text = f"{family}: {role.value.title()}" if role else f"{family}: Unknown"
            legend = self.renderer.font_small.render(text, True, (210, 210, 210))
            surface.blit(legend, (start_x + self.scale(28, 18), y))

    def _render_color_hierarchy_strip(self, surface: pygame.Surface) -> None:
        """Show the user-facing Phase 2 color strip across the top."""
        # Keep the duel-resolution helper untouched and flip only the visual strip order.
        hierarchy = list(reversed(self.game.get_appeasing_hierarchy()))
        if not hierarchy:
            return

        title = self.renderer.font_small.render("Phase 2 Colors (Strong -> Weak)", True, (225, 225, 225))
        compact = self.is_compact_layout()
        title_y = self.scale_y(88, 70) if compact else self.scale_y(66, 48)
        title_rect = title.get_rect(center=(self.window.WINDOW_WIDTH // 2, title_y))
        surface.blit(title, title_rect)

        chip_width = self.scale_x(84, 68) if compact else self.scale_x(128, 90)
        chip_height = self.scale_y(22, 18) if compact else self.scale_y(24, 18)
        spacing = self.scale(6, 4) if compact else self.scale(10, 6)
        total_width = len(hierarchy) * chip_width + (len(hierarchy) - 1) * spacing
        start_x = (self.window.WINDOW_WIDTH - total_width) // 2
        y = self.scale_y(102, 80) if compact else self.scale_y(78, 58)

        for index, suit in enumerate(hierarchy):
            rect = pygame.Rect(start_x + index * (chip_width + spacing), y, chip_width, chip_height)
            pygame.draw.rect(surface, (42, 46, 60), rect, border_radius=self.scale(12, 8))
            pygame.draw.rect(surface, (180, 180, 190), rect, 1, border_radius=self.scale(12, 8))
            draw_suit_icon(surface, suit, (rect.x + self.scale(15, 10), rect.centery), size=self.scale(8, 5))
            label = self.renderer.font_small.render(get_family_name(suit), True, (225, 225, 225))
            surface.blit(label, (rect.x + self.scale(30, 18), rect.y + self.scale(3, 2)))

    def _render_rank_guide(self, surface: pygame.Surface) -> None:
        """Show the themed high-rank mapping during every gameplay phase."""
        if self.is_compact_layout():
            board_rect = self.renderer.get_board_rect()
            text = "Ranks: Satyr 10 | Oracle 11 | Hero 12"
            line = self.renderer.font_small.render(text, True, (214, 214, 214))
            line_rect = line.get_rect(center=(self.window.WINDOW_WIDTH // 2, board_rect.top - self.scale_y(16, 12)))
            surface.blit(line, line_rect)
            return

        panel_rect = pygame.Rect(
            self.window.WINDOW_WIDTH - self.scale_x(215, 156),
            self.scale_y(225, 168),
            self.scale_x(190, 144),
            self.scale_y(122, 92),
        )
        pygame.draw.rect(surface, (30, 34, 46), panel_rect, border_radius=self.scale(12, 8))
        pygame.draw.rect(surface, (110, 115, 130), panel_rect, 1, border_radius=self.scale(12, 8))

        title = self.renderer.font_small.render("Card Ranks (Always)", True, (230, 230, 230))
        surface.blit(title, (panel_rect.x + self.scale(12, 8), panel_rect.y + self.scale(8, 6)))

        lines = [
            get_rank_name_with_value(CardRank.KING),
            get_rank_name_with_value(CardRank.QUEEN),
            get_rank_name_with_value(CardRank.TEN),
            "1-9 stay numeric",
            "Ranks never reverse",
        ]

        for index, text in enumerate(lines):
            line = self.renderer.font_small.render(text, True, (205, 205, 205))
            surface.blit(
                line,
                (
                    panel_rect.x + self.scale(12, 8),
                    panel_rect.y + self.scale(32, 24) + index * self.scale(18, 14),
                ),
            )
