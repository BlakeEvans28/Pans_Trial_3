"""
Core game state for Pan's Trial.
Manages board, player states, and game flow.
"""

from enum import Enum
from typing import Optional
from .cards import Card, CardRank, CardSuit, SuitRole, PlayerHand, DamagePile
from .board import Board, Position
from .actions import (
    Action, MoveAction, PickupCurrentCardAction, PlayCardAction, ChooseCombatCardAction,
    ChooseRequestAction, SelectDamageCardAction, SelectRestructureSuitAction,
    SelectPlaneShiftDirectionAction, ResolvePlaneShiftAction, ResolveBallistaShotAction,
    PlaceCardsAction, ActionType
)


class GamePhase(Enum):
    """Game phases."""
    SETUP = "setup"
    TRAVERSING = "traversing"  # Movement phase
    APPEASING = "appeasing"  # Card play phase
    GAME_OVER = "game_over"


class GameState:
    """Main game state manager."""

    def __init__(self):
        """Initialize a new game."""
        self.board = Board()
        self.phase = GamePhase.SETUP
        
        # Player states (0 and 1)
        self.current_player = 0
        self.hands: dict[int, PlayerHand] = {0: PlayerHand([]), 1: PlayerHand([])}
        self.weapons: dict[int, PlayerHand] = {0: PlayerHand([]), 1: PlayerHand([])}
        self.damage: dict[int, DamagePile] = {0: DamagePile([]), 1: DamagePile([])}
        
        # Suit roles (Jacks order determines which suit has which role)
        self.suit_roles: dict[CardSuit, SuitRole] = {}
        self.jack_order: list[CardSuit] = []  # Order of jacks
        
        # Turn tracking
        self.movement_turn = 0  # 0-2 for each player's turn (3 moves per player per round)
        self.phase_started_cards: list[tuple[int, Card]] = []  # (player_id, card) played this Appeasing phase
        self.current_request_winner: Optional[int] = None  # Who won the current request
        self.current_request_loser: Optional[int] = None
        self.pending_request_players: list[int] = []
        self.pending_request_resolution: Optional[dict] = None
        self.pending_placement_player: Optional[int] = None
        self.pending_placement_cards: list[Card] = []
        self.appeasing_return_notice: Optional[str] = None
        self.pending_ballista_player: Optional[int] = None
        self.pending_ballista_targets: list[Position] = []
        self.pending_combat_players: list[int] = []
        self.combat_moving_player: Optional[int] = None
        self.combat_pending_transition = False
        self.forced_pass_turns: dict[int, int] = {0: 0, 1: 0}
        self.traversing_resume_player = 0
        
        # Game history
        self.winner: Optional[int] = None
        self.appeasing_history: list[str] = []
        self.request_history: list[str] = []
        self.major_events: list[str] = []

    def setup_board(self, grid_cards: list[list[Card]]) -> None:
        """Set up the initial 6x6 board."""
        if len(grid_cards) != 6 or any(len(row) != 6 for row in grid_cards):
            raise ValueError("Board must be 6x6")
        
        for row in range(6):
            for col in range(6):
                self.board.set_card(Position(row, col), grid_cards[row][col])

    def setup_suit_roles(self, jack_suits: list[CardSuit]) -> None:
        """Set up suit roles based on Jack order."""
        if len(jack_suits) != 4:
            raise ValueError("Must have 4 suits for Jack order")
        
        roles = [SuitRole.WALLS, SuitRole.TRAPS, SuitRole.BALLISTA, SuitRole.WEAPONS]
        self.suit_roles = {suit: role for suit, role in zip(jack_suits, roles)}
        self.jack_order = jack_suits

    def get_appeasing_hierarchy(self) -> list[CardSuit]:
        """Return Phase 2 suits ordered from strongest trump to weakest."""
        suits_by_role = {role: suit for suit, role in self.suit_roles.items()}
        role_priority = [
            SuitRole.WEAPONS,
            SuitRole.BALLISTA,
            SuitRole.TRAPS,
            SuitRole.WALLS,
        ]
        return [suits_by_role[role] for role in role_priority if role in suits_by_role]

    def place_player(self, player_id: int, pos: Position) -> None:
        """Place player on board."""
        if player_id not in [0, 1]:
            raise ValueError("Player ID must be 0 or 1")
        self.board.place_player(player_id, pos)

    def add_card_to_hand(self, player_id: int, card: Card) -> None:
        """Add card to player's hand."""
        if player_id not in [0, 1]:
            raise ValueError("Player ID must be 0 or 1")
        self.hands[player_id].add_card(card)

    def get_player_hand(self, player_id: int) -> list[Card]:
        """Get player's hand."""
        if player_id not in [0, 1]:
            raise ValueError("Player ID must be 0 or 1")
        return self.hands[player_id].cards

    def get_player_weapons(self, player_id: int) -> list[Card]:
        """Get combat-eligible weapon cards from the player's normal hand."""
        if player_id not in [0, 1]:
            raise ValueError("Player ID must be 0 or 1")
        return [
            card for card in self.hands[player_id].cards
            if self.suit_roles.get(card.suit) == SuitRole.WEAPONS
        ]

    def can_use_weapon(self, player_id: int, card: Card) -> bool:
        """Check if a normal hand card can be used in combat."""
        return card in self.hands[player_id].cards and self.suit_roles.get(card.suit) == SuitRole.WEAPONS

    def get_damage_total(self, player_id: int) -> int:
        """Get total damage for player."""
        return self.damage[player_id].total_damage()

    def _record_event(self, text: str) -> None:
        """Record a concise major match event for the final summary."""
        self.major_events.append(text)
        if len(self.major_events) > 12:
            self.major_events = self.major_events[-12:]

    def get_match_summary(self) -> dict:
        """Return final match summary details for the Game Over screen."""
        return {
            "damage_cards": {
                0: list(self.damage[0].cards),
                1: list(self.damage[1].cards),
            },
            "appeasing": list(self.appeasing_history[-6:]),
            "requests": list(self.request_history[-8:]),
            "events": list(self.major_events[-8:]),
        }

    def can_choose_request(self, player_id: int) -> bool:
        """Check if this player is next to choose an Appeasing Pan request."""
        return (
            self.phase == GamePhase.APPEASING
            and self.current_request_winner is not None
            and bool(self.pending_request_players)
            and self.pending_request_players[0] == player_id
            and self.pending_request_resolution is None
            and self.pending_placement_player is None
        )

    def can_select_request_type(self, player_id: int, request_type: str) -> bool:
        """Return True when a specific request is currently legal for the player."""
        if not self.can_choose_request(player_id):
            return False

        if request_type == "ignore_us":
            return player_id == self.current_request_winner

        if request_type == "steal_life":
            opponent_id = 1 - player_id
            return bool(self.damage[player_id].cards) and bool(self.damage[opponent_id].cards)

        if request_type == "restructure":
            return len(self.jack_order) >= 2

        return request_type == "plane_shift"

    def get_available_request_types(self, player_id: int) -> list[str]:
        """Return request types the current chooser may actually click."""
        order = ["restructure", "steal_life", "ignore_us", "plane_shift"]
        return [
            request_type
            for request_type in order
            if self.can_select_request_type(player_id, request_type)
        ]

    def has_pending_combat(self) -> bool:
        """Return True while players are choosing combat damage cards."""
        return bool(self.pending_combat_players)

    def has_pending_ballista(self) -> bool:
        """Return True while a player is choosing a ballista direction."""
        return self.pending_ballista_player is not None

    def get_pending_ballista_targets(self) -> list[Position]:
        """Return all reachable tiles for the active ballista shot."""
        return list(self.pending_ballista_targets)

    def has_pending_request_resolution(self) -> bool:
        """Return True while an Appeasing Pan request still needs player input."""
        return self.pending_request_resolution is not None

    def get_pending_request_type(self) -> Optional[str]:
        """Return the request type currently being resolved, if any."""
        if self.pending_request_resolution is None:
            return None
        return self.pending_request_resolution["type"]

    def get_pending_plane_shift_direction(self) -> Optional[str]:
        """Return the selected Plane Shift direction, if any."""
        if self.get_pending_request_type() != "plane_shift":
            return None
        return self.pending_request_resolution["direction"]

    def get_pending_steal_life_card(self) -> Optional[Card]:
        """Return the chooser's currently selected Steal Life damage card, if any."""
        if self.get_pending_request_type() != "steal_life":
            return None
        return self.pending_request_resolution["selected_own"]

    def get_pending_restructure_suits(self) -> list[CardSuit]:
        """Return suits already selected for Restructure."""
        if self.get_pending_request_type() != "restructure":
            return []
        return list(self.pending_request_resolution["selected_suits"])

    def has_pending_card_placement(self) -> bool:
        """Return True while played Appeasing cards are being placed into holes."""
        return self.pending_placement_player is not None

    def get_pending_placement_cards(self) -> list[Card]:
        """Return the played cards still waiting to be placed or returned."""
        return list(self.pending_placement_cards)

    def consume_appeasing_return_notice(self) -> Optional[str]:
        """Return and clear the latest auto-return notice from Appeasing Pan."""
        notice = self.appeasing_return_notice
        self.appeasing_return_notice = None
        return notice

    def is_player_on_position(self, pos: Position) -> bool:
        """Return True when either player is currently standing on the position."""
        return any(
            self.board.get_player_position(player_id) == pos
            for player_id in [0, 1]
        )

    def get_hole_positions(self) -> list[Position]:
        """Return all positions that currently contain a board hole."""
        holes = []
        for row in range(6):
            for col in range(6):
                pos = Position(row, col)
                if self.board.get_card(pos) is None and not self.is_player_on_position(pos):
                    holes.append(pos)
        return holes

    def is_defeated(self, player_id: int) -> bool:
        """Check if player has 25+ damage."""
        return self.damage[player_id].is_defeated()

    def get_legal_moves(self, player_id: int) -> list[str]:
        """Get legal movement directions from current position."""
        pos = self.board.get_player_position(player_id)
        if pos is None:
            return []
        
        legal = []
        directions = [("up", -1, 0), ("down", 1, 0), ("left", 0, -1), ("right", 0, 1)]
        
        for direction, dr, dc in directions:
            new_pos = Position(pos.row + dr, pos.col + dc)
            target_card = self.board.get_card(new_pos)
            
            # Check if move is legal based on card role
            if target_card is not None:
                role = self.suit_roles.get(target_card.suit)
                
                # Walls block movement
                if role == SuitRole.WALLS:
                    continue
            
            legal.append(direction)
        
        return legal

    def can_pick_up_current_card(self, player_id: int) -> bool:
        """Return True when the current tile can be interacted with using the current-tile action."""
        pos = self.board.get_player_position(player_id)
        if pos is None:
            return False

        card = self.board.get_card(pos)
        if card is None:
            return False

        role = self.suit_roles.get(card.suit)
        if role == SuitRole.WALLS:
            return False

        if role == SuitRole.BALLISTA:
            return bool(self._get_ballista_targets(player_id))

        return True

    def can_play_card(self, player_id: int, card: Card) -> bool:
        """Check if player can play card."""
        return card in self.hands[player_id].cards

    def can_run_appeasing_phase(self) -> bool:
        """Return True when both players still have a normal hand card for Phase 2."""
        return bool(self.hands[0].cards) and bool(self.hands[1].cards)

    def apply_action(self, action: Action) -> bool:
        """
        Apply an action and return True if successful.
        Engine validates and executes all game rules.
        """
        if action.player_id not in [0, 1]:
            return False
        
        # Route to appropriate handler
        if action.type == ActionType.MOVE:
            return self._handle_move(action)
        elif action.type == ActionType.PICK_UP_CURRENT:
            return self._handle_pick_up_current(action)
        elif action.type == ActionType.PLAY_CARD:
            return self._handle_play_card(action)
        elif action.type == ActionType.CHOOSE_COMBAT_CARD:
            return self._handle_choose_combat_card(action)
        elif action.type == ActionType.CHOOSE_REQUEST:
            return self._handle_choose_request(action)
        elif action.type == ActionType.SELECT_DAMAGE_CARD:
            return self._handle_select_damage_card(action)
        elif action.type == ActionType.SELECT_RESTRUCTURE_SUIT:
            return self._handle_select_restructure_suit(action)
        elif action.type == ActionType.SELECT_PLANE_SHIFT_DIRECTION:
            return self._handle_select_plane_shift_direction(action)
        elif action.type == ActionType.RESOLVE_PLANE_SHIFT:
            return self._handle_resolve_plane_shift(action)
        elif action.type == ActionType.RESOLVE_BALLISTA_SHOT:
            return self._handle_resolve_ballista_shot(action)
        elif action.type == ActionType.PLACE_CARDS:
            return self._handle_place_cards(action)
        
        return False

    def _handle_move(self, action: MoveAction) -> bool:
        """Handle movement action."""
        if self.phase != GamePhase.TRAVERSING:
            return False

        if self.pending_combat_players:
            return False

        if self.pending_ballista_player is not None:
            return False

        if action.player_id != self.current_player:
            return False

        if self.forced_pass_turns[action.player_id] > 0:
            return False
        
        legal = self.get_legal_moves(action.player_id)
        if action.direction not in legal:
            return False
        
        # Execute movement
        self._execute_move(action.player_id, action.direction)

        if self.pending_combat_players or self.pending_ballista_player is not None:
            self.combat_pending_transition = True
            return True

        self._finish_traversing_move()
        
        return True

    def _handle_pick_up_current(self, action: PickupCurrentCardAction) -> bool:
        """Handle spending a traversing move to interact with the current tile."""
        if self.phase != GamePhase.TRAVERSING:
            return False

        if self.pending_combat_players or self.pending_ballista_player is not None:
            return False

        if action.player_id != self.current_player:
            return False

        if self.forced_pass_turns[action.player_id] > 0:
            return False

        if not self.can_pick_up_current_card(action.player_id):
            return False

        self._pick_up_current_card(action.player_id)
        if self.pending_ballista_player is not None:
            self.combat_pending_transition = True
            return True
        self._finish_traversing_move()
        return True

    def _execute_move(self, player_id: int, direction: str) -> None:
        """Execute movement and apply card effects."""
        pos = self.board.get_player_position(player_id)
        
        # Calculate new position
        movements = {"up": (-1, 0), "down": (1, 0), "left": (0, -1), "right": (0, 1)}
        dr, dc = movements[direction]
        new_pos = Position(pos.row + dr, pos.col + dc)
        
        # Move player
        self.board.place_player(player_id, new_pos)
        
        # Check for other player (combat)
        opponent_id = 1 - player_id
        if self.board.get_player_position(opponent_id) == new_pos:
            self._start_combat(player_id, opponent_id)
            return
        
        # Apply card effect
        card = self.board.get_card(new_pos)
        if card is not None:
            role = self.suit_roles.get(card.suit)
            self._apply_card_effect(player_id, card, role)

    def _apply_card_effect(self, player_id: int, card: Card, role: Optional[SuitRole]) -> None:
        """Apply the effect of landing on a card."""
        if role == SuitRole.TRAPS:
            # Take damage
            self.damage[player_id].add_card(card)
            self.board.set_card(self.board.get_player_position(player_id), None)
            self._record_event(f"P{player_id + 1} triggered trap {card}.")
        
        elif role == SuitRole.WEAPONS:
            # Weapons stay in the normal hand; their current role controls combat eligibility.
            self.hands[player_id].add_card(card)
            self.board.set_card(self.board.get_player_position(player_id), None)
            self._record_event(f"P{player_id + 1} collected weapon {card}.")
        
        elif role == SuitRole.BALLISTA:
            self._start_ballista(player_id)
            self._record_event(f"P{player_id + 1} started a Ballista launch.")

    def _pick_up_current_card(self, player_id: int) -> None:
        """Resolve the current-tile interaction without moving."""
        pos = self.board.get_player_position(player_id)
        if pos is None:
            return

        card = self.board.get_card(pos)
        if card is None:
            return

        role = self.suit_roles.get(card.suit)
        if role == SuitRole.WALLS:
            return

        if role == SuitRole.BALLISTA:
            self._start_ballista(player_id)
            return

        if role == SuitRole.TRAPS:
            self.damage[player_id].add_card(card)
            self._record_event(f"P{player_id + 1} picked up trap damage {card}.")
        else:
            self.hands[player_id].add_card(card)
            self._record_event(f"P{player_id + 1} picked up {card}.")

        self.board.set_card(pos, None)

    def _start_combat(self, attacker_id: int, defender_id: int) -> None:
        """Start combat when players land on the same tile."""
        self.pending_combat_players = []
        self.combat_moving_player = attacker_id
        self._record_event(f"P{attacker_id + 1} started combat with P{defender_id + 1}.")

        if self.get_player_weapons(attacker_id):
            self.pending_combat_players.append(attacker_id)

        if self.get_player_weapons(defender_id):
            self.pending_combat_players.append(defender_id)

        if self.pending_combat_players:
            self.current_player = self.pending_combat_players[0]

    def _start_ballista(self, player_id: int) -> None:
        """Start a ballista launch choice for the current player."""
        targets = self._get_ballista_targets(player_id)
        if targets:
            self.pending_ballista_player = player_id
            self.pending_ballista_targets = targets
            self.current_player = player_id

    def _get_ballista_targets(self, player_id: int) -> list[Position]:
        """Get every reachable tile along each ballista line until a wall blocks the path."""
        start_pos = self.board.get_player_position(player_id)
        if start_pos is None:
            return []

        movements = {"up": (-1, 0), "down": (1, 0), "left": (0, -1), "right": (0, 1)}
        targets: list[Position] = []
        seen: set[Position] = set()

        for dr, dc in movements.values():
            current = start_pos
            for _ in range(5):
                next_pos = Position(current.row + dr, current.col + dc)
                next_card = self.board.get_card(next_pos)
                if next_card is not None and self.suit_roles.get(next_card.suit) == SuitRole.WALLS:
                    break

                destination = Position(next_pos.row % 6, next_pos.col % 6)
                if destination not in seen:
                    targets.append(destination)
                    seen.add(destination)
                current = destination

        return targets

    def _handle_resolve_ballista_shot(self, action: ResolveBallistaShotAction) -> bool:
        """Resolve a clickable ballista destination."""
        if self.phase != GamePhase.TRAVERSING:
            return False

        if self.pending_ballista_player is None:
            return False

        if action.player_id != self.pending_ballista_player:
            return False

        destination = Position(action.row, action.col)
        if destination not in self.pending_ballista_targets:
            return False

        self._resolve_ballista_shot(action.player_id, destination)
        if not self.pending_combat_players and self.pending_ballista_player is None:
            self._finish_traversing_move()
        return True

    def _resolve_ballista_shot(self, player_id: int, destination: Position) -> None:
        """Move a player to a chosen ballista destination without triggering landing effects."""
        self.pending_ballista_player = None
        self.pending_ballista_targets = []

        self.board.place_player(player_id, destination)
        self._record_event(f"P{player_id + 1} launched by Ballista to ({destination.row + 1}, {destination.col + 1}).")

        opponent_id = 1 - player_id
        if self.board.get_player_position(opponent_id) == destination:
            self._start_combat(player_id, opponent_id)

    def _handle_choose_combat_card(self, action: ChooseCombatCardAction) -> bool:
        """Handle selecting a damage card during combat."""
        if self.phase != GamePhase.TRAVERSING:
            return False

        if not self.pending_combat_players:
            return False

        if self.pending_combat_players[0] != action.player_id:
            return False

        if not self.can_use_weapon(action.player_id, action.card):
            return False

        opponent_id = 1 - action.player_id
        self.hands[action.player_id].remove_card(action.card)
        self.damage[opponent_id].add_card(action.card)
        self._record_event(f"P{action.player_id + 1} hit P{opponent_id + 1} with {action.card}.")
        self.pending_combat_players.pop(0)

        if self.pending_combat_players:
            self.current_player = self.pending_combat_players[0]
        else:
            self.combat_pending_transition = False
            self._finish_traversing_move()

        return True

    def _handle_play_card(self, action: PlayCardAction) -> bool:
        """Handle card play in Appeasing Pan phase."""
        if self.phase != GamePhase.APPEASING:
            return False

        if self.pending_placement_player is not None:
            return False

        if self.current_request_winner is not None:
            return False

        if action.player_id != self.current_player:
            return False
        
        if not self.can_play_card(action.player_id, action.card):
            return False
        
        # Add card to phase cards
        self.phase_started_cards.append((action.player_id, action.card))
        self.hands[action.player_id].remove_card(action.card)
        
        # Check if both players have played
        if len(self.phase_started_cards) == 2:
            self._resolve_appeasing_phase()
        else:
            self.current_player = 1 - action.player_id
        
        return True

    def _finish_traversing_move(self) -> None:
        """Advance turn state after a traversing move fully resolves."""
        acting_player = self.combat_moving_player if self.combat_moving_player is not None else self.current_player
        self.movement_turn += 1

        if self.movement_turn >= 6:  # 3 moves per player = 6 total
            self.traversing_resume_player = acting_player
            if self.can_run_appeasing_phase():
                self.phase = GamePhase.APPEASING
                self.movement_turn = 0
            else:
                self.phase = GamePhase.TRAVERSING
                self.movement_turn = 0
                self.current_player = self.traversing_resume_player
        else:
            self.current_player = 1 - acting_player

        self.pending_ballista_player = None
        self.pending_ballista_targets = []
        self.combat_moving_player = None
        self.combat_pending_transition = False

    def _handle_choose_request(self, action: ChooseRequestAction) -> bool:
        """Handle request selection after winning Appeasing Pan."""
        return self._choose_request(action.player_id, action.request_type.value, action.params)

    def _resolve_appeasing_phase(self) -> None:
        """Resolve the Appeasing Pan phase and determine request winner."""
        if len(self.phase_started_cards) != 2:
            return
        
        # Determine winner by the explicit Phase 2 role priority:
        # Weapons > Ballista > Traps > Walls. Matching suits use card rank.
        (p1_id, card1), (p2_id, card2) = self.phase_started_cards
        hierarchy = self.get_appeasing_hierarchy()
        strength = {suit: index for index, suit in enumerate(hierarchy)}
        suit1 = strength.get(card1.suit, len(hierarchy))
        suit2 = strength.get(card2.suit, len(hierarchy))

        if suit1 < suit2:
            self.current_request_winner = p1_id
        elif suit2 < suit1:
            self.current_request_winner = p2_id
        else:
            val1 = card1.combat_value()
            val2 = card2.combat_value()
            if val1 > val2:
                self.current_request_winner = p1_id
            elif val2 > val1:
                self.current_request_winner = p2_id
            else:
                self.current_request_winner = self.current_player
        
        loser = 1 - self.current_request_winner
        self.current_request_loser = loser
        self.traversing_resume_player = loser
        self.pending_request_players = [self.current_request_winner, loser]
        self.current_player = self.current_request_winner
        winner_card = card1 if self.current_request_winner == p1_id else card2
        loser_card = card2 if self.current_request_winner == p1_id else card1
        self.appeasing_history.append(
            f"P{self.current_request_winner + 1} beat P{loser + 1}: {winner_card} over {loser_card}."
        )

    def choose_request(self, player_id: int, request_type: str) -> bool:
        """Player chooses a request to execute."""
        return self._choose_request(player_id, request_type, {})

    def _choose_request(self, player_id: int, request_type: str, params: Optional[dict] = None) -> bool:
        """Player chooses a request to execute, with optional parameters."""
        if self.phase != GamePhase.APPEASING:
            return False

        if not self.can_choose_request(player_id):
            return False
        
        # Execute the request
        return self._execute_request(player_id, request_type, params or {})

    def _execute_request(self, chooser_id: int, request_type: str, params: dict) -> bool:
        """Execute the chosen request."""
        if not self.can_select_request_type(chooser_id, request_type):
            return False

        opponent_id = 1 - chooser_id
        request_label = request_type.replace("_", " ").title()
        self.request_history.append(f"P{chooser_id + 1} chose {request_label}.")
        self._record_event(f"P{chooser_id + 1} chose {request_label}.")
        
        if request_type == "restructure":
            selected_suits = params.get("suits") or []
            if len(selected_suits) == 2:
                if not self._swap_suit_roles(selected_suits[0], selected_suits[1]):
                    return False
                self._finish_request_choice(request_type, check_for_traps=True)
                return True

            self.pending_request_resolution = {
                "type": "restructure",
                "player": chooser_id,
                "selected_suits": [],
            }
            return True
            
        elif request_type == "steal_life":
            if not self.damage[chooser_id].cards or not self.damage[opponent_id].cards:
                return False

            self.pending_request_resolution = {
                "type": "steal_life",
                "player": chooser_id,
                "selected_own": None,
            }
            return True
            
        elif request_type == "ignore_us":
            self._finish_request_choice(request_type)
            return True
            
        elif request_type == "plane_shift":
            self.pending_request_resolution = {
                "type": "plane_shift",
                "player": chooser_id,
                "direction": None,
            }
            return True
        
        return False

    def _finish_request_choice(self, request_type: str, check_for_traps: bool = False) -> None:
        """Advance request order after one request fully resolves."""
        if self.pending_request_players:
            self.pending_request_players.pop(0)

        if check_for_traps:
            self._mark_players_trapped_from_requests()

        if request_type == "ignore_us":
            self.pending_request_players = []

        if self.pending_request_players:
            self.current_player = self.pending_request_players[0]
        else:
            self._start_card_placement_or_reset()

    def _start_card_placement_or_reset(self) -> None:
        """Start loser placement of played Appeasing cards, or return them if no holes exist."""
        if not self.phase_started_cards or self.current_request_loser is None:
            self.reset_turn()
            return

        self.pending_placement_player = self.current_request_loser
        self.pending_placement_cards = [card for _, card in self.phase_started_cards]
        self.current_player = self.pending_placement_player
        self._return_unplaceable_cards_if_needed()

    def _return_unplaceable_cards_if_needed(self) -> None:
        """Return remaining played cards to the loser if no more holes can hold them."""
        if self.pending_placement_player is None:
            return

        holes = self.get_hole_positions()
        if holes and self.pending_placement_cards:
            return

        returned_count = len(self.pending_placement_cards)
        returned_player = self.pending_placement_player
        for card in self.pending_placement_cards:
            self.hands[self.pending_placement_player].add_card(card)
        if returned_count:
            plural = "s" if returned_count != 1 else ""
            self.appeasing_return_notice = (
                f"No open holes remained, so {returned_count} played card{plural} "
                f"returned to P{returned_player + 1}'s hand."
            )
            self._record_event(self.appeasing_return_notice)
        self.pending_placement_cards = []
        self.pending_placement_player = None
        self._mark_players_trapped_from_requests()
        self.reset_turn()

    def _handle_select_damage_card(self, action: SelectDamageCardAction) -> bool:
        """Handle Steal Life card selection."""
        if self.phase != GamePhase.APPEASING:
            return False

        pending = self.pending_request_resolution
        if pending is None or pending["type"] != "steal_life":
            return False

        if action.player_id != pending["player"]:
            return False

        if action.card not in self.damage[action.pile_owner].cards:
            return False

        chooser_id = action.player_id
        opponent_id = 1 - chooser_id

        if pending["selected_own"] is None:
            if action.pile_owner != chooser_id:
                return False
            pending["selected_own"] = action.card
            return True

        if action.pile_owner != opponent_id:
            return False

        own_card = pending["selected_own"]
        opponent_card = action.card
        self.damage[chooser_id].remove_card(own_card)
        self.damage[opponent_id].remove_card(opponent_card)
        self.damage[chooser_id].add_card(opponent_card)
        self.damage[opponent_id].add_card(own_card)
        self.pending_request_resolution = None
        self._finish_request_choice("steal_life")
        return True

    def _handle_select_restructure_suit(self, action: SelectRestructureSuitAction) -> bool:
        """Handle choosing the two suits/colors whose roles will be swapped."""
        if self.phase != GamePhase.APPEASING:
            return False

        pending = self.pending_request_resolution
        if pending is None or pending["type"] != "restructure":
            return False

        if action.player_id != pending["player"]:
            return False

        if action.suit not in self.suit_roles:
            return False

        selected = pending["selected_suits"]
        if action.suit in selected:
            return False

        selected.append(action.suit)
        if len(selected) < 2:
            return True

        if not self._swap_suit_roles(selected[0], selected[1]):
            return False

        self.pending_request_resolution = None
        self._finish_request_choice("restructure", check_for_traps=True)
        return True

    def _handle_select_plane_shift_direction(self, action: SelectPlaneShiftDirectionAction) -> bool:
        """Handle selecting the shift direction for Plane Shift."""
        if self.phase != GamePhase.APPEASING:
            return False

        pending = self.pending_request_resolution
        if pending is None or pending["type"] != "plane_shift":
            return False

        if action.player_id != pending["player"]:
            return False

        pending["direction"] = action.direction
        return True

    def _handle_resolve_plane_shift(self, action: ResolvePlaneShiftAction) -> bool:
        """Shift the chosen row or column for Plane Shift."""
        if self.phase != GamePhase.APPEASING:
            return False

        if action.index < 0 or action.index >= 6:
            return False

        pending = self.pending_request_resolution
        if pending is None or pending["type"] != "plane_shift":
            return False

        if action.player_id != pending["player"]:
            return False

        direction = pending["direction"]
        if direction is None:
            return False

        if direction == "left":
            self.board.move_row(action.index, -1)
        elif direction == "right":
            self.board.move_row(action.index, 1)
        elif direction == "up":
            self.board.move_col(action.index, -1)
        elif direction == "down":
            self.board.move_col(action.index, 1)
        else:
            return False

        self.pending_request_resolution = None
        self._finish_request_choice("plane_shift", check_for_traps=True)
        return True

    def _handle_place_cards(self, action: PlaceCardsAction) -> bool:
        """Place played Appeasing cards into board holes before Traversing resumes."""
        if self.phase != GamePhase.APPEASING:
            return False

        if self.pending_placement_player is None:
            return False

        if action.player_id != self.pending_placement_player:
            return False

        if not action.positions:
            return False

        if len(action.positions) > len(self.pending_placement_cards):
            return False

        if action.card_indices is None:
            card_indices = list(range(len(action.positions)))
        else:
            card_indices = list(action.card_indices)

        if len(card_indices) != len(action.positions):
            return False

        if len(set(card_indices)) != len(card_indices):
            return False

        for card_index in card_indices:
            if card_index < 0 or card_index >= len(self.pending_placement_cards):
                return False

        seen_positions = set()
        for pos in action.positions:
            if pos in seen_positions:
                return False
            if self.board.get_card(pos) is not None or self.is_player_on_position(pos):
                return False
            seen_positions.add(pos)

        selected_cards = [
            self.pending_placement_cards[card_index]
            for card_index in card_indices
        ]

        for card_index in sorted(card_indices, reverse=True):
            self.pending_placement_cards.pop(card_index)

        for pos, card in zip(action.positions, selected_cards):
            self.board.set_card(pos, card)

        self._return_unplaceable_cards_if_needed()
        return True

    def _swap_suit_roles(self, first_suit: CardSuit, second_suit: CardSuit) -> bool:
        """Swap two Omen suits and their assigned roles."""
        if first_suit == second_suit:
            return False
        if first_suit not in self.suit_roles or second_suit not in self.suit_roles:
            return False

        first_index = self.jack_order.index(first_suit)
        second_index = self.jack_order.index(second_suit)
        self.jack_order[first_index], self.jack_order[second_index] = (
            self.jack_order[second_index],
            self.jack_order[first_index],
        )

        roles = [SuitRole.WALLS, SuitRole.TRAPS, SuitRole.BALLISTA, SuitRole.WEAPONS]
        self.suit_roles = {suit: role for suit, role in zip(self.jack_order, roles)}
        return True

    def _restructure_board(self) -> None:
        """Backward-compatible helper: swap the first two Omen roles."""
        if len(self.jack_order) >= 2:
            self._swap_suit_roles(self.jack_order[0], self.jack_order[1])

    def _mark_players_trapped_from_requests(self) -> None:
        """Force trapped players to pass the next traversing phase."""
        for player_id in [0, 1]:
            if not self.get_legal_moves(player_id):
                self.forced_pass_turns[player_id] = max(self.forced_pass_turns[player_id], 3)

    def advance_forced_traversing(self) -> bool:
        """Automatically consume forced pass turns during traversing."""
        if self.phase != GamePhase.TRAVERSING:
            return False

        if self.pending_ballista_player is not None:
            return False

        if self.pending_combat_players:
            return False

        if self.forced_pass_turns[self.current_player] <= 0:
            return False

        self.forced_pass_turns[self.current_player] -= 1
        self.movement_turn += 1

        if self.movement_turn >= 6:
            self.movement_turn = 0
            self.traversing_resume_player = self.current_player
            if self.can_run_appeasing_phase():
                self.phase = GamePhase.APPEASING
            else:
                self.phase = GamePhase.TRAVERSING
                self.current_player = self.traversing_resume_player
        else:
            self.current_player = 1 - self.current_player

        return True

    def reset_turn(self) -> None:
        """Reset for next turn."""
        self.phase = GamePhase.TRAVERSING
        self.phase_started_cards = []
        self.movement_turn = 0
        self.current_request_winner = None
        self.current_request_loser = None
        self.pending_request_players = []
        self.pending_request_resolution = None
        self.pending_placement_player = None
        self.pending_placement_cards = []
        self.pending_ballista_player = None
        self.pending_ballista_targets = []
        self.pending_combat_players = []
        self.combat_moving_player = None
        self.combat_pending_transition = False
        self.current_player = self.traversing_resume_player

    def check_game_over(self) -> bool:
        """Check if game is over."""
        if self.is_defeated(0):
            self.winner = 1
            self.phase = GamePhase.GAME_OVER
            self._record_event("P1 reached 25 or more damage.")
            return True
        elif self.is_defeated(1):
            self.winner = 0
            self.phase = GamePhase.GAME_OVER
            self._record_event("P2 reached 25 or more damage.")
            return True
        return False
