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
    get_reversed_hierarchy,
)
from .screen_manager import Screen, ScreenType
from .board_renderer import BoardRenderer
from .input_handler import InputHandler
from .suit_icons import draw_suit_icon
from engine import (
    CardRank, GameState, GamePhase, MoveAction, Position,
    ChooseRequestAction, RequestType, PlayCardAction, ChooseCombatCardAction,
    SelectDamageCardAction, SelectRestructureSuitAction, SelectPlaneShiftDirectionAction,
    ResolvePlaneShiftAction, ResolveBallistaShotAction, PlaceCardsAction
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
        "example": "Example: trade Crimson Weapons with Azure Traps.",
    },
    "steal_life": {
        "title": "Steal Life",
        "description": "Exchange one of your damage cards with one from the enemy pile.",
        "example": "Example: swap your Hero damage with their 3.",
    },
    "ignore_us": {
        "title": "Ignore Us",
        "description": "End Pan's requests immediately and move straight to hole placement.",
        "example": "Example: skip the second chooser entirely.",
    },
    "plane_shift": {
        "title": "Plane Shift",
        "description": "Choose a direction, then click a row or column to wrap it by one tile.",
        "example": "Example: shift row 2 left or column 5 down.",
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
        self.popup_title_font = pygame.font.Font(None, 38)
        self.popup_body_font = pygame.font.Font(None, 28)
        self.popup_small_font = pygame.font.Font(None, 22)
        self.damage_popup_player = None
        
        self._create_ui()
        
        # Start with all elements hidden (will be shown when screen is activated)
        self._hide_all_elements()
    
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
            if card_x + card_width > WINDOW_WIDTH - MARGIN:
                break  # Don't go off screen
            
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
            if self._handle_center_popup_click(event.pos):
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
                    self.game.apply_action(action)
                    return True

            if self.game.has_pending_card_placement() and hasattr(self.renderer, "BOARD_X"):
                clicked_cell = self.renderer.get_cell_at_mouse(event.pos)
                if clicked_cell is not None:
                    action = PlaceCardsAction(self.game.current_player, [clicked_cell])
                    self.game.apply_action(action)
                    return True
            elif self.game.phase == GamePhase.TRAVERSING:
                action = self.input_handler.handle_mouse_click(
                    event.pos, self.game.current_player, self.game
                )
                if action:
                    self.game.apply_action(action)
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
                    self.game.apply_action(action)
                    return True
        
        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE and self.damage_popup_player is not None:
                self.damage_popup_player = None
                return True

            if (
                self.game.get_pending_request_type() == "plane_shift"
                and self.game.get_pending_plane_shift_direction() is None
            ):
                direction = DIRECTION_KEYS.get(event.key)

                if direction:
                    action = SelectPlaneShiftDirectionAction(self.game.current_player, direction)
                    self.game.apply_action(action)
                    return True

            if self.game.phase == GamePhase.TRAVERSING and not self.game.has_pending_ballista():
                direction = DIRECTION_KEYS.get(event.key)
                
                if direction:
                    try:
                        action = MoveAction(self.game.current_player, direction)
                        self.game.apply_action(action)
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
                            self.game.apply_action(action)
                            print(f"Player {action.player_id + 1} played {card}")
                    return True

            # Weapon pile buttons
            for index, btn in enumerate(self.weapon_buttons):
                if event.ui_element == btn:
                    player_weapons = self.game.get_player_weapons(self.game.current_player)
                    if index < len(player_weapons) and self.game.has_pending_combat():
                        card = player_weapons[index]
                        action = ChooseCombatCardAction(self.game.current_player, card)
                        self.game.apply_action(action)
                        print(f"Player {action.player_id + 1} used weapon card: {card}")
                    return True
        
        return False
    
    def update(self, time_delta: float) -> None:
        """Update game state display."""
        for _ in range(6):
            if not self.game.advance_forced_traversing():
                break

        # Update status
        player = f"P{self.game.current_player + 1}"
        pending_request_type = self.game.get_pending_request_type()
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
                status_text = f"APPEASING PAN: {player} selects the enemy damage card to steal"
        elif pending_request_type == "plane_shift":
            direction = self.game.get_pending_plane_shift_direction()
            if direction is None:
                status_text = f"APPEASING PAN: {player} chooses Plane Shift direction from the popup"
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

        if pending_request_type in {"steal_life", "restructure"} or showing_request_selection:
            self.damage_popup_player = None

        # Update the small turn indicator above the card buttons.
        for i, label in enumerate(self.hand_labels):
            label.set_text(f"Player {i+1} Turn")
            if i == self.game.current_player:
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
        
        # Update card buttons
        player_hand = self.game.get_player_hand(self.game.current_player)
        for i, btn in enumerate(self.card_buttons):
            if i < len(player_hand):
                card = player_hand[i]
                btn.set_text(self._format_card_label(card))
                btn.disabled = not (
                    (
                        self.game.phase == GamePhase.APPEASING
                        and self.game.current_request_winner is None
                        and not self.game.has_pending_request_resolution()
                        and not self.game.has_pending_card_placement()
                    )
                )
                btn.show()
            else:
                btn.set_text("")
                btn.disabled = True
                btn.hide()

        # Update active player's combat-eligible weapon-color cards from their normal hand.
        player_weapons = self.game.get_player_weapons(self.game.current_player)
        self.weapon_label.set_text(f"P{self.game.current_player + 1} Weapon Cards ({len(player_weapons)})")
        self.weapon_label.show()

        for index, btn in enumerate(self.weapon_buttons):
            if index < len(player_weapons):
                btn.set_text(self._format_card_label(player_weapons[index]))
                btn.disabled = not self.game.has_pending_combat()
                btn.show()
            else:
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
        surface.fill((20, 20, 30))
        
        suit_role_render = {}
        for suit, role in self.game.suit_roles.items():
            suit_role_render[suit] = role.value

        if self.game.has_pending_ballista():
            highlight_positions = set(self.game.get_pending_ballista_targets())
        elif self.game.has_pending_card_placement():
            highlight_positions = set(self.game.get_hole_positions())
        else:
            highlight_positions = set()
        
        # Render board
        self.renderer.render(surface, self.game.board, suit_role_render, self.game.phase, highlight_positions)
        self._render_suit_role_legend(surface)
        self._render_rank_guide(surface)
        self._render_damage_summary(surface)
        if self.game.phase == GamePhase.APPEASING:
            self._render_color_hierarchy_strip(surface)
        self._render_active_popups(surface)
    
    def on_enter(self) -> None:
        """Activate game screen."""
        self.status_label.show()
        self.info_label.hide()
        for _, btn in self.move_buttons:
            btn.hide()
        self.pickup_button.hide()
        for _, btn in self.request_buttons:
            btn.hide()
        for btn in self.card_buttons:
            btn.show()
        self.weapon_label.show()
        for btn in self.weapon_buttons:
            btn.show()
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
        """Return True when Plane Shift still needs a direction choice."""
        return (
            self.game.get_pending_request_type() == "plane_shift"
            and self.game.get_pending_plane_shift_direction() is None
        )

    def _has_center_popup(self) -> bool:
        """Return True when a centered modal popup is active."""
        return any([
            self._is_request_popup_active(),
            self._is_steal_life_popup_active(),
            self._is_restructure_popup_active(),
            self._is_plane_shift_direction_popup_active(),
        ])

    def _get_centered_panel_rect(self, width: int, height: int) -> pygame.Rect:
        """Return a centered popup rect."""
        return pygame.Rect(
            (self.window.WINDOW_WIDTH - width) // 2,
            (self.window.WINDOW_HEIGHT - height) // 2,
            width,
            height,
        )

    def _get_damage_summary_rects(self) -> dict[int, pygame.Rect]:
        """Return the clickable top-right damage summary rects."""
        width = 184
        height = 32
        x = self.window.WINDOW_WIDTH - width - 24
        return {
            0: pygame.Rect(x, 18, width, height),
            1: pygame.Rect(x, 56, width, height),
        }

    def _get_request_popup_layout(self) -> tuple[pygame.Rect, list[tuple[str, pygame.Rect]]]:
        """Return request popup panel and button rects."""
        request_types = self.game.get_available_request_types(self.game.current_player)
        cols = 2 if len(request_types) > 1 else 1
        rows = max(1, (len(request_types) + cols - 1) // cols)
        button_width = 360 if cols == 2 else 420
        button_height = 100
        spacing_x = 20
        spacing_y = 18
        panel_width = cols * button_width + (cols - 1) * spacing_x + 60
        panel_height = rows * button_height + (rows - 1) * spacing_y + 110
        panel_rect = self._get_centered_panel_rect(panel_width, panel_height)

        rects = []
        for index, request_type in enumerate(request_types):
            row = index // cols
            col = index % cols
            rect = pygame.Rect(
                panel_rect.x + 30 + col * (button_width + spacing_x),
                panel_rect.y + 66 + row * (button_height + spacing_y),
                button_width,
                button_height,
            )
            rects.append((request_type, rect))
        return panel_rect, rects

    def _get_steal_life_popup_layout(self) -> tuple[pygame.Rect, list[tuple[int, object, pygame.Rect]]]:
        """Return Steal Life popup panel and clickable damage-card rects."""
        left_cards = self.game.damage[0].cards
        right_cards = self.game.damage[1].cards
        rows = max(1, len(left_cards), len(right_cards))
        panel_height = min(170 + rows * 36, 720)
        panel_rect = self._get_centered_panel_rect(840, panel_height)

        rects = []
        lane_width = 330
        start_y = panel_rect.y + 126
        left_x = panel_rect.x + 40
        right_x = panel_rect.centerx + 20
        for player_id, cards, x in [
            (0, left_cards, left_x),
            (1, right_cards, right_x),
        ]:
            for index, card in enumerate(cards):
                rect = pygame.Rect(x, start_y + index * 36, lane_width, 30)
                rects.append((player_id, card, rect))
        return panel_rect, rects

    def _get_restructure_popup_layout(self) -> tuple[pygame.Rect, list[tuple[object, pygame.Rect]]]:
        """Return Restructure popup panel and suit button rects."""
        panel_rect = self._get_centered_panel_rect(620, 258)
        rects = []
        for index, suit in enumerate(self.game.jack_order):
            row = index // 2
            col = index % 2
            rect = pygame.Rect(
                panel_rect.x + 34 + col * 278,
                panel_rect.y + 96 + row * 72,
                244,
                54,
            )
            rects.append((suit, rect))
        return panel_rect, rects

    def _get_plane_shift_popup_layout(self) -> tuple[pygame.Rect, list[tuple[str, pygame.Rect]]]:
        """Return Plane Shift direction popup panel and direction rects."""
        panel_rect = self._get_centered_panel_rect(500, 246)
        directions = ["up", "left", "right", "down"]
        rects = []
        for index, direction in enumerate(directions):
            row = index // 2
            col = index % 2
            rect = pygame.Rect(
                panel_rect.x + 36 + col * 214,
                panel_rect.y + 92 + row * 66,
                180,
                46,
            )
            rects.append((direction, rect))
        return panel_rect, rects

    def _get_damage_popup_layout(self, player_id: int) -> tuple[pygame.Rect, list[tuple[object, pygame.Rect]]]:
        """Return the generic damage-pile popup layout for one player."""
        cards = self.game.damage[player_id].cards
        cols = 2 if len(cards) > 8 else 1
        rows = max(1, (len(cards) + cols - 1) // cols)
        panel_width = 580 if cols == 2 else 340
        panel_height = min(128 + rows * 34, 720)
        panel_rect = self._get_centered_panel_rect(panel_width, panel_height)

        rects = []
        col_width = 240
        start_x = panel_rect.x + 26
        start_y = panel_rect.y + 70
        for index, card in enumerate(cards):
            col = index // rows
            row = index % rows
            rect = pygame.Rect(
                start_x + col * (col_width + 24),
                start_y + row * 34,
                col_width,
                28,
            )
            rects.append((card, rect))
        return panel_rect, rects

    def _handle_center_popup_click(self, pos: tuple[int, int]) -> bool:
        """Handle clicks inside the centered modal popups."""
        if self._is_request_popup_active():
            panel_rect, option_rects = self._get_request_popup_layout()
            if not panel_rect.collidepoint(pos):
                return True
            for request_type, rect in option_rects:
                if rect.collidepoint(pos):
                    action = ChooseRequestAction(self.game.current_player, REQUEST_TYPE_MAP[request_type])
                    self.game.apply_action(action)
                    return True
            return True

        if self._is_steal_life_popup_active():
            panel_rect, card_rects = self._get_steal_life_popup_layout()
            if not panel_rect.collidepoint(pos):
                return True
            for player_id, card, rect in card_rects:
                if rect.collidepoint(pos):
                    action = SelectDamageCardAction(self.game.current_player, player_id, card)
                    self.game.apply_action(action)
                    return True
            return True

        if self._is_restructure_popup_active():
            panel_rect, suit_rects = self._get_restructure_popup_layout()
            if not panel_rect.collidepoint(pos):
                return True
            for suit, rect in suit_rects:
                if rect.collidepoint(pos):
                    action = SelectRestructureSuitAction(self.game.current_player, suit)
                    self.game.apply_action(action)
                    return True
            return True

        if self._is_plane_shift_direction_popup_active():
            panel_rect, direction_rects = self._get_plane_shift_popup_layout()
            if not panel_rect.collidepoint(pos):
                return True
            for direction, rect in direction_rects:
                if rect.collidepoint(pos):
                    action = SelectPlaneShiftDirectionAction(self.game.current_player, direction)
                    self.game.apply_action(action)
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

    def _render_damage_summary(self, surface: pygame.Surface) -> None:
        """Render clickable damage summary chips."""
        for player_id, rect in self._get_damage_summary_rects().items():
            active = self.damage_popup_player == player_id
            fill = (56, 60, 76) if active else (33, 37, 49)
            border = (224, 199, 120) if active else (106, 112, 128)
            pygame.draw.rect(surface, fill, rect, border_radius=10)
            pygame.draw.rect(surface, border, rect, 2, border_radius=10)

            label = self.popup_small_font.render(
                f"P{player_id + 1} Damage: {self.game.get_damage_total(player_id)}",
                True,
                (232, 232, 232),
            )
            label_rect = label.get_rect(center=rect.center)
            surface.blit(label, label_rect)

    def _render_active_popups(self, surface: pygame.Surface) -> None:
        """Render whichever modal popup is currently active."""
        if self._is_request_popup_active():
            self._render_popup_backdrop(surface)
            self._render_request_popup(surface)
            return

        if self._is_steal_life_popup_active():
            self._render_popup_backdrop(surface)
            self._render_steal_life_popup(surface)
            return

        if self._is_restructure_popup_active():
            self._render_popup_backdrop(surface)
            self._render_restructure_popup(surface)
            return

        if self._is_plane_shift_direction_popup_active():
            self._render_popup_backdrop(surface)
            self._render_plane_shift_direction_popup(surface)
            return

        if self.damage_popup_player is not None:
            self._render_popup_backdrop(surface, alpha=110)
            self._render_damage_popup(surface, self.damage_popup_player)

    def _render_request_popup(self, surface: pygame.Surface) -> None:
        """Render the centered request-selection popup."""
        panel_rect, option_rects = self._get_request_popup_layout()
        pygame.draw.rect(surface, (20, 24, 34), panel_rect, border_radius=18)
        pygame.draw.rect(surface, (140, 146, 165), panel_rect, 2, border_radius=18)

        title = self.popup_title_font.render("Choose Pan's Request", True, (240, 236, 214))
        surface.blit(title, (panel_rect.x + 28, panel_rect.y + 18))

        subtitle = self.popup_small_font.render(
            f"Player {self.game.current_player + 1} chooses now.",
            True,
            (198, 198, 198),
        )
        surface.blit(subtitle, (panel_rect.x + 30, panel_rect.y + 50))

        for request_type, rect in option_rects:
            copy = REQUEST_POPUP_COPY[request_type]
            pygame.draw.rect(surface, (38, 44, 58), rect, border_radius=14)
            pygame.draw.rect(surface, (108, 114, 134), rect, 2, border_radius=14)

            title_surface = self.popup_body_font.render(copy["title"], True, (238, 238, 238))
            surface.blit(title_surface, (rect.x + 16, rect.y + 12))

            self._draw_wrapped_text(
                surface,
                copy["description"],
                self.popup_small_font,
                (208, 208, 208),
                pygame.Rect(rect.x + 16, rect.y + 42, rect.width - 32, 32),
                line_height=18,
                max_lines=2,
            )
            self._draw_wrapped_text(
                surface,
                copy["example"],
                self.popup_small_font,
                (170, 200, 220),
                pygame.Rect(rect.x + 16, rect.y + 74, rect.width - 32, 18),
                line_height=18,
                max_lines=1,
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
        surface.blit(title, (panel_rect.x + 30, panel_rect.y + 18))

        instruction = "Select your damage card first, then select the enemy card you want to steal."
        self._draw_wrapped_text(
            surface,
            instruction,
            self.popup_small_font,
            (212, 212, 212),
            pygame.Rect(panel_rect.x + 30, panel_rect.y + 54, panel_rect.width - 60, 36),
            line_height=18,
            max_lines=2,
        )

        headings = {
            0: (panel_rect.x + 40, f"P1 Damage ({self.game.get_damage_total(0)})"),
            1: (panel_rect.centerx + 20, f"P2 Damage ({self.game.get_damage_total(1)})"),
        }
        for player_id, (x, text) in headings.items():
            highlight = player_id == chooser if first_selection_pending else player_id != chooser
            color = (240, 220, 150) if highlight else (200, 200, 200)
            heading = self.popup_body_font.render(text, True, color)
            surface.blit(heading, (x, panel_rect.y + 92))

        if not card_rects:
            empty = self.popup_body_font.render("No damage cards available.", True, (210, 210, 210))
            empty_rect = empty.get_rect(center=panel_rect.center)
            surface.blit(empty, empty_rect)
            return

        for player_id, card, rect in card_rects:
            selectable = player_id == chooser if first_selection_pending else player_id != chooser
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
            surface.blit(label, (rect.x + 12, rect.y + 6))

    def _render_restructure_popup(self, surface: pygame.Surface) -> None:
        """Render the centered Restructure color selector."""
        panel_rect, suit_rects = self._get_restructure_popup_layout()
        selected_suits = set(self.game.get_pending_restructure_suits())

        pygame.draw.rect(surface, (20, 24, 34), panel_rect, border_radius=18)
        pygame.draw.rect(surface, (128, 158, 188), panel_rect, 2, border_radius=18)

        title = self.popup_title_font.render("Restructure", True, (240, 236, 214))
        surface.blit(title, (panel_rect.x + 30, panel_rect.y + 18))

        subtitle = self.popup_small_font.render(
            "Choose two colors to swap their omen roles.",
            True,
            (210, 210, 210),
        )
        surface.blit(subtitle, (panel_rect.x + 30, panel_rect.y + 56))

        for suit, rect in suit_rects:
            role = self.game.suit_roles.get(suit)
            selected = suit in selected_suits
            fill = (54, 68, 86) if selected else (36, 42, 54)
            border = (234, 201, 114) if selected else (104, 112, 128)
            pygame.draw.rect(surface, fill, rect, border_radius=12)
            pygame.draw.rect(surface, border, rect, 2, border_radius=12)

            draw_suit_icon(surface, suit, (rect.x + 24, rect.centery), size=10)
            family = self.popup_body_font.render(get_family_name(suit), True, (238, 238, 238))
            surface.blit(family, (rect.x + 44, rect.y + 8))

            role_text = role.value.title() if role else "Unknown"
            detail = self.popup_small_font.render(role_text, True, (194, 204, 220))
            surface.blit(detail, (rect.x + 46, rect.y + 31))

    def _render_plane_shift_direction_popup(self, surface: pygame.Surface) -> None:
        """Render the centered Plane Shift direction picker."""
        panel_rect, direction_rects = self._get_plane_shift_popup_layout()
        pygame.draw.rect(surface, (20, 24, 34), panel_rect, border_radius=18)
        pygame.draw.rect(surface, (150, 138, 188), panel_rect, 2, border_radius=18)

        title = self.popup_title_font.render("Plane Shift", True, (240, 236, 214))
        surface.blit(title, (panel_rect.x + 28, panel_rect.y + 18))

        subtitle = self.popup_small_font.render(
            "Choose a direction first. Then click the row or column on the board.",
            True,
            (210, 210, 210),
        )
        surface.blit(subtitle, (panel_rect.x + 28, panel_rect.y + 56))

        labels = {
            "up": "Shift Up",
            "left": "Shift Left",
            "right": "Shift Right",
            "down": "Shift Down",
        }
        for direction, rect in direction_rects:
            pygame.draw.rect(surface, (40, 46, 60), rect, border_radius=12)
            pygame.draw.rect(surface, (110, 118, 138), rect, 2, border_radius=12)
            label = self.popup_body_font.render(labels[direction], True, (236, 236, 236))
            label_rect = label.get_rect(center=rect.center)
            surface.blit(label, label_rect)

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
        surface.blit(title, (panel_rect.x + 24, panel_rect.y + 18))

        subtitle = self.popup_small_font.render("Click outside this popup to close it.", True, (192, 192, 192))
        surface.blit(subtitle, (panel_rect.x + 26, panel_rect.y + 50))

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
            surface.blit(label, (rect.x + 10, rect.y + 6))

    def _render_suit_role_legend(self, surface: pygame.Surface) -> None:
        """Render suit-role mappings with drawn icons instead of font glyphs."""
        start_x = self.window.WINDOW_WIDTH - 215
        start_y = 82
        row_height = 30

        for index, suit in enumerate(self.game.jack_order):
            role = self.game.suit_roles.get(suit)
            y = start_y + index * row_height
            draw_suit_icon(surface, suit, (start_x + 12, y + 10), size=12)
            family = get_family_name(suit)
            text = f"{family}: {role.value.title()}" if role else f"{family}: Unknown"
            legend = self.renderer.font_small.render(text, True, (210, 210, 210))
            surface.blit(legend, (start_x + 28, y))

    def _render_color_hierarchy_strip(self, surface: pygame.Surface) -> None:
        """Show the reversed Omen color order used as the Phase 2 hierarchy reference."""
        hierarchy = get_reversed_hierarchy(self.game.jack_order)
        if not hierarchy:
            return

        title = self.renderer.font_small.render("Phase 2 Colors (Strong -> Weak)", True, (225, 225, 225))
        title_rect = title.get_rect(center=(self.window.WINDOW_WIDTH // 2, 66))
        surface.blit(title, title_rect)

        chip_width = 128
        chip_height = 24
        spacing = 10
        total_width = len(hierarchy) * chip_width + (len(hierarchy) - 1) * spacing
        start_x = (self.window.WINDOW_WIDTH - total_width) // 2
        y = 78

        for index, suit in enumerate(hierarchy):
            rect = pygame.Rect(start_x + index * (chip_width + spacing), y, chip_width, chip_height)
            pygame.draw.rect(surface, (42, 46, 60), rect, border_radius=12)
            pygame.draw.rect(surface, (180, 180, 190), rect, 1, border_radius=12)
            draw_suit_icon(surface, suit, (rect.x + 15, rect.centery), size=8)
            label = self.renderer.font_small.render(get_family_name(suit), True, (225, 225, 225))
            surface.blit(label, (rect.x + 30, rect.y + 3))

    def _render_rank_guide(self, surface: pygame.Surface) -> None:
        """Show the themed high-rank mapping during every gameplay phase."""
        panel_rect = pygame.Rect(self.window.WINDOW_WIDTH - 215, 225, 190, 122)
        pygame.draw.rect(surface, (30, 34, 46), panel_rect, border_radius=12)
        pygame.draw.rect(surface, (110, 115, 130), panel_rect, 1, border_radius=12)

        title = self.renderer.font_small.render("Card Ranks (Always)", True, (230, 230, 230))
        surface.blit(title, (panel_rect.x + 12, panel_rect.y + 8))

        lines = [
            get_rank_name_with_value(CardRank.KING),
            get_rank_name_with_value(CardRank.QUEEN),
            get_rank_name_with_value(CardRank.TEN),
            "1-9 stay numeric",
            "Ranks never reverse",
        ]

        for index, text in enumerate(lines):
            line = self.renderer.font_small.render(text, True, (205, 205, 205))
            surface.blit(line, (panel_rect.x + 12, panel_rect.y + 32 + index * 18))
