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

from pan_theme import get_family_code, get_family_name, get_rank_name, get_rank_name_with_value, get_reversed_hierarchy
from .screen_manager import Screen, ScreenType
from .board_renderer import BoardRenderer
from .input_handler import InputHandler
from .suit_icons import draw_suit_icon
from engine import (
    CardRank, GameState, GamePhase, MoveAction, Position,
    ChooseRequestAction, RequestType, PickupCurrentCardAction, PlayCardAction, ChooseCombatCardAction,
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

            # Handle board click for traversing
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
            # Handle arrow key and WASD movement.
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
            elif (
                self.game.get_pending_request_type() == "plane_shift"
                and self.game.get_pending_plane_shift_direction() is None
            ):
                direction = DIRECTION_KEYS.get(event.key)

                if direction:
                    action = SelectPlaneShiftDirectionAction(self.game.current_player, direction)
                    self.game.apply_action(action)
                    return True
        
        elif event.type == pygame_gui.UI_BUTTON_PRESSED:
            # Movement buttons
            for direction, btn in self.move_buttons:
                if event.ui_element == btn:
                    if self.game.phase == GamePhase.TRAVERSING and not self.game.has_pending_ballista():
                        try:
                            action = MoveAction(self.game.current_player, direction)
                            self.game.apply_action(action)
                            print(f"Player {action.player_id + 1} moved {direction}")
                        except Exception as e:
                            print(f"Move failed: {e}")
                    elif (
                        self.game.get_pending_request_type() == "plane_shift"
                        and self.game.get_pending_plane_shift_direction() is None
                    ):
                        action = SelectPlaneShiftDirectionAction(self.game.current_player, direction)
                        self.game.apply_action(action)
                    return True

            if event.ui_element == self.pickup_button:
                if self.game.phase == GamePhase.TRAVERSING and not self.game.has_pending_ballista():
                    action = PickupCurrentCardAction(self.game.current_player)
                    self.game.apply_action(action)
                return True
            
            # Request buttons
            for request_name, btn in self.request_buttons:
                if event.ui_element == btn:
                    if self.game.can_choose_request(self.game.current_player):
                        request_type_map = {
                            "restructure": RequestType.RESTRUCTURE,
                            "steal_life": RequestType.STEAL_LIFE,
                            "ignore_us": RequestType.IGNORE_US,
                            "plane_shift": RequestType.PLANE_SHIFT
                        }
                        request_type = request_type_map.get(request_name.lower().replace(' ', '_'))
                        if request_type:
                            action = ChooseRequestAction(self.game.current_player, request_type)
                            self.game.apply_action(action)
                            print(f"Player {action.player_id + 1} chose request: {request_name}")
                    return True
            
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

            # Restructure suit/color buttons
            for index, btn in enumerate(self.restructure_buttons):
                if event.ui_element == btn:
                    if index < len(self.game.jack_order):
                        action = SelectRestructureSuitAction(self.game.current_player, self.game.jack_order[index])
                        self.game.apply_action(action)
                    return True

            # Damage pile buttons
            for player_id, buttons in self.damage_buttons.items():
                for index, btn in enumerate(buttons):
                    if event.ui_element == btn:
                        if index < len(self.game.damage[player_id].cards):
                            card = self.game.damage[player_id].cards[index]
                            action = SelectDamageCardAction(self.game.current_player, player_id, card)
                            self.game.apply_action(action)
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
                status_text = f"APPEASING PAN: {player} chooses one of their damage cards"
            else:
                status_text = f"APPEASING PAN: {player} chooses one of P{2 - self.game.current_player} damage cards"
        elif pending_request_type == "plane_shift":
            direction = self.game.get_pending_plane_shift_direction()
            if direction is None:
                status_text = f"APPEASING PAN: {player} chooses Plane Shift direction"
            else:
                line_type = "row" if direction in ["left", "right"] else "column"
                status_text = f"APPEASING PAN: {player} clicks a {line_type} to shift {direction}"
        elif pending_request_type == "restructure":
            selected = len(self.game.get_pending_restructure_suits())
            status_text = f"APPEASING PAN: {player} chooses Restructure color {selected + 1} of 2"
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
                status_text = f"APPEASING PAN: {player} chooses a request"
        else:
            status_text = f"TRAVERSING: {player} Turn (Move {self.game.movement_turn // 2 + 1})"
        
        self.status_label.set_text(status_text)
        
        # Update damage info
        p1_damage = self.game.get_damage_total(0)
        p2_damage = self.game.get_damage_total(1)
        self.info_label.set_text(f"P1 Damage: {p1_damage} | P2 Damage: {p2_damage}")

        # Update the small turn indicator above the card buttons.
        for i, label in enumerate(self.hand_labels):
            label.set_text(f"Player {i+1} Turn")
            if i == self.game.current_player:
                label.show()
            else:
                label.hide()
        
        # Enable/disable buttons based on phase
        choosing_plane_shift_direction = (
            pending_request_type == "plane_shift"
            and self.game.get_pending_plane_shift_direction() is None
        )
        showing_damage_selection = pending_request_type == "steal_life"
        showing_restructure_selection = pending_request_type == "restructure"
        placing_phase_cards = self.game.has_pending_card_placement()

        for _, btn in self.move_buttons:
            if showing_damage_selection or showing_restructure_selection or placing_phase_cards:
                btn.hide()
                btn.disabled = True
            else:
                btn.show()
                btn.disabled = not (
                    (
                        self.game.phase == GamePhase.TRAVERSING
                        and not self.game.has_pending_combat()
                        and not self.game.has_pending_ballista()
                    )
                    or choosing_plane_shift_direction
                )

        if showing_damage_selection or showing_restructure_selection or placing_phase_cards:
            self.pickup_button.hide()
            self.pickup_button.disabled = True
        else:
            self.pickup_button.show()
            self.pickup_button.disabled = not (
                self.game.phase == GamePhase.TRAVERSING
                and not self.game.has_pending_combat()
                and not self.game.has_pending_ballista()
                and self.game.can_pick_up_current_card(self.game.current_player)
            )
        
        for _, btn in self.request_buttons:
            if showing_damage_selection or showing_restructure_selection or placing_phase_cards:
                btn.hide()
                btn.disabled = True
            else:
                btn.show()
                btn.disabled = not self.game.can_choose_request(self.game.current_player)
        
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
        selected_restructure_suits = self.game.get_pending_restructure_suits()
        for index, btn in enumerate(self.restructure_buttons):
            if showing_restructure_selection and index < len(self.game.jack_order):
                suit = self.game.jack_order[index]
                prefix = "[X] " if suit in selected_restructure_suits else ""
                btn.set_text(f"{prefix}{get_family_name(suit)}")
                btn.disabled = suit in selected_restructure_suits
                btn.show()
            else:
                btn.set_text("")
                btn.disabled = True
                btn.hide()

        # Update damage pile controls for Steal Life.
        selected_damage_card = self.game.get_pending_steal_life_card()
        for player_id, label in enumerate(self.damage_labels):
            if showing_damage_selection:
                total = self.game.get_damage_total(player_id)
                label.set_text(f"P{player_id + 1} Damage ({total})")
                label.show()
            else:
                label.hide()

        for player_id, buttons in self.damage_buttons.items():
            cards = self.game.damage[player_id].cards
            for index, btn in enumerate(buttons):
                if showing_damage_selection and index < len(cards):
                    card = cards[index]
                    prefix = "[X] " if player_id == self.game.current_player and selected_damage_card == card else ""
                    btn.set_text(f"{prefix}{self._format_card_label(card)}")
                    if selected_damage_card is None:
                        btn.disabled = player_id != self.game.current_player
                    else:
                        btn.disabled = player_id == self.game.current_player
                    btn.show()
                else:
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
        if self.game.phase == GamePhase.APPEASING:
            self._render_color_hierarchy_strip(surface)
    
    def on_enter(self) -> None:
        """Activate game screen."""
        # Show all UI elements
        self.status_label.show()
        self.info_label.show()
        for _, btn in self.move_buttons:
            btn.show()
        self.pickup_button.show()
        for _, btn in self.request_buttons:
            btn.show()
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
        # Hide UI elements
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

    def _format_card_label(self, card) -> str:
        """Render a compact label for a hand or damage card."""
        return f"{get_rank_name(card.rank)} {get_family_code(card.suit)}"

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
