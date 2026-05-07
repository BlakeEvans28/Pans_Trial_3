"""Single-player AI helpers for Pan's Trial."""

from __future__ import annotations

import math
import pickle
from dataclasses import dataclass

from .actions import (
    ChooseCombatCardAction,
    ChooseRequestAction,
    MoveAction,
    PickupCurrentCardAction,
    PlaceCardsAction,
    PlayCardAction,
    RequestType,
    ResolveBallistaShotAction,
    ResolvePlaneShiftAction,
    SelectDamageCardAction,
    SelectPlaneShiftDirectionAction,
    SelectRestructureSuitAction,
)
from .board import Board, Position
from .cards import Card, CardRank, CardSuit, SuitRole
from .game_state import GamePhase, GameState


REQUEST_TYPE_MAP = {
    "restructure": RequestType.RESTRUCTURE,
    "steal_life": RequestType.STEAL_LIFE,
    "ignore_us": RequestType.IGNORE_US,
    "plane_shift": RequestType.PLANE_SHIFT,
}


@dataclass
class SmartPanAI:
    """Depth-limited heuristic AI for the local single-player mode."""

    player_id: int = 1
    search_depth: int = 3
    action_delay: float = 0.95
    action_preview_delay: float = 0.65
    draft_delay: float = 0.95
    draft_preview_delay: float = 0.70
    max_branching: int = 8

    def is_my_turn(self, game: GameState) -> bool:
        """Return True when this AI owns the next legal decision."""
        return self._next_actor(game) == self.player_id

    def choose_draft_index(
        self,
        available_cards: list[Card | None],
        current_hand: list[Card],
        opponent_hand: list[Card],
        kings_drafted: int,
    ) -> int | None:
        """Choose the strongest available draft card for the AI hand."""
        best_index = None
        best_score = -math.inf
        for index, card in enumerate(available_cards):
            if card is None:
                continue
            if card.rank == CardRank.KING and kings_drafted >= 2:
                continue

            score = self._score_draft_card(card, current_hand, opponent_hand)
            if score > best_score:
                best_score = score
                best_index = index
        return best_index

    def choose_action(self, game: GameState):
        """Return the best current legal action for the AI player."""
        actor = self._next_actor(game)
        if actor != self.player_id:
            return None

        depth = self.search_depth
        if game.phase == GamePhase.APPEASING or game.has_pending_request_resolution():
            depth += 1

        actions = self._generate_actions(game, actor)
        if not actions:
            return None

        actions = self._prune_actions(game, actions, actor)
        best_action = actions[0]
        best_score = -math.inf

        for action in actions:
            simulated = self._clone_game(game)
            if not simulated.apply_action(action):
                continue
            self._advance_forced_passes(simulated)
            simulated.check_game_over()
            score = self._search(simulated, depth - 1, -math.inf, math.inf)
            if score > best_score:
                best_score = score
                best_action = action

        return best_action

    def _search(self, game: GameState, depth: int, alpha: float, beta: float) -> float:
        game.check_game_over()
        actor = self._next_actor(game)
        if depth <= 0 or actor is None or game.winner is not None:
            return self._evaluate(game)

        actions = self._generate_actions(game, actor)
        if not actions:
            clone = self._clone_game(game)
            advanced = self._advance_forced_passes(clone)
            if advanced:
                return self._search(clone, depth - 1, alpha, beta)
            return self._evaluate(game)

        actions = self._prune_actions(game, actions, actor)
        maximizing = actor == self.player_id

        if maximizing:
            value = -math.inf
            for action in actions:
                simulated = self._clone_game(game)
                if not simulated.apply_action(action):
                    continue
                self._advance_forced_passes(simulated)
                simulated.check_game_over()
                value = max(value, self._search(simulated, depth - 1, alpha, beta))
                alpha = max(alpha, value)
                if alpha >= beta:
                    break
            return value

        value = math.inf
        for action in actions:
            simulated = self._clone_game(game)
            if not simulated.apply_action(action):
                continue
            self._advance_forced_passes(simulated)
            simulated.check_game_over()
            value = min(value, self._search(simulated, depth - 1, alpha, beta))
            beta = min(beta, value)
            if alpha >= beta:
                break
        return value

    def _generate_actions(self, game: GameState, actor: int) -> list:
        if game.winner is not None:
            return []

        if game.has_pending_combat():
            if not game.pending_combat_players or game.pending_combat_players[0] != actor:
                return []
            return [
                ChooseCombatCardAction(actor, card)
                for card in sorted(
                    game.get_player_weapons(actor),
                    key=lambda current: current.combat_value(),
                    reverse=True,
                )
            ]

        if game.has_pending_ballista():
            if game.current_player != actor:
                return []
            return [
                ResolveBallistaShotAction(actor, target.row, target.col)
                for target in self._sorted_positions(
                    game.get_pending_ballista_targets(),
                    game,
                    actor,
                )
            ]

        if game.has_pending_card_placement():
            if game.current_player != actor:
                return []
            holes = self._sorted_positions(game.get_hole_positions(), game, actor)[:8]
            pending_cards = game.get_pending_placement_cards()
            card_order = sorted(
                range(len(pending_cards)),
                key=lambda index: pending_cards[index].combat_value(),
                reverse=True,
            )
            actions = []
            for card_index in card_order:
                for hole in holes:
                    actions.append(PlaceCardsAction(actor, [hole], [card_index]))
            return actions

        pending_request = game.get_pending_request_type()
        if pending_request == "steal_life":
            return self._generate_steal_life_actions(game, actor)
        if pending_request == "restructure":
            return self._generate_restructure_actions(game, actor)
        if pending_request == "plane_shift":
            return self._generate_plane_shift_actions(game, actor)

        if game.can_choose_request(actor):
            return [
                ChooseRequestAction(actor, REQUEST_TYPE_MAP[request_type])
                for request_type in game.get_available_request_types(actor)
            ]

        if game.phase == GamePhase.APPEASING:
            hand = [
                card
                for card in game.get_player_hand(actor)
                if game.can_submit_appeasing_card(actor, card)
            ]
            return [
                PlayCardAction(actor, card)
                for card in sorted(
                    hand,
                    key=lambda current: self._score_appeasing_card(game, current),
                    reverse=True,
                )
            ]

        if game.phase != GamePhase.TRAVERSING or game.current_player != actor:
            return []

        actions = []
        if game.can_pick_up_current_card(actor):
            actions.append(PickupCurrentCardAction(actor))
        for direction in game.get_legal_moves(actor):
            actions.append(MoveAction(actor, direction))
        return actions

    def _generate_steal_life_actions(self, game: GameState, actor: int) -> list:
        pending = game.pending_request_resolution or {}
        if int(pending.get("player", -1)) != actor:
            return []

        chosen_card = game.get_pending_steal_life_card()
        if chosen_card is None:
            return [
                SelectDamageCardAction(actor, actor, card)
                for card in sorted(
                    game.damage[actor].cards,
                    key=lambda current: current.combat_value(),
                )
            ]

        opponent = 1 - actor
        return [
            SelectDamageCardAction(actor, opponent, card)
            for card in sorted(
                game.damage[opponent].cards,
                key=lambda current: current.combat_value(),
                reverse=True,
            )
        ]

    def _generate_restructure_actions(self, game: GameState, actor: int) -> list:
        pending = game.pending_request_resolution or {}
        if int(pending.get("player", -1)) != actor:
            return []

        selected = set(game.get_pending_restructure_suits())
        suits = [suit for suit in game.jack_order if suit not in selected]
        return [SelectRestructureSuitAction(actor, suit) for suit in suits]

    def _generate_plane_shift_actions(self, game: GameState, actor: int) -> list:
        pending = game.pending_request_resolution or {}
        if int(pending.get("player", -1)) != actor:
            return []

        direction = game.get_pending_plane_shift_direction()
        if direction is None:
            return [
                SelectPlaneShiftDirectionAction(actor, direction_name)
                for direction_name in ("left", "right", "up", "down")
            ]

        return [ResolvePlaneShiftAction(actor, index) for index in range(Board.ROWS)]

    def _prune_actions(self, game: GameState, actions: list, actor: int) -> list:
        if len(actions) <= self.max_branching:
            return actions

        scored_actions = []
        for action in actions:
            simulated = self._clone_game(game)
            if not simulated.apply_action(action):
                continue
            self._advance_forced_passes(simulated)
            simulated.check_game_over()
            scored_actions.append((self._evaluate(simulated), action))

        if not scored_actions:
            return actions[: self.max_branching]

        reverse = actor == self.player_id
        scored_actions.sort(key=lambda item: item[0], reverse=reverse)
        return [action for _, action in scored_actions[: self.max_branching]]

    def _evaluate(self, game: GameState) -> float:
        opponent = 1 - self.player_id
        if game.winner == self.player_id:
            return 100000.0
        if game.winner == opponent:
            return -100000.0

        ai_hand = game.get_player_hand(self.player_id)
        opponent_hand = game.get_player_hand(opponent)
        ai_damage = game.get_damage_total(self.player_id)
        opponent_damage = game.get_damage_total(opponent)
        ai_weapons = game.get_player_weapons(self.player_id)
        opponent_weapons = game.get_player_weapons(opponent)
        ai_moves = len(game.get_legal_moves(self.player_id))
        opponent_moves = len(game.get_legal_moves(opponent))

        score = 0.0
        score += (opponent_damage - ai_damage) * 55.0
        score += (sum(card.combat_value() for card in ai_hand) - sum(card.combat_value() for card in opponent_hand)) * 3.5
        score += (len(ai_hand) - len(opponent_hand)) * 10.0
        score += (sum(card.combat_value() for card in ai_weapons) - sum(card.combat_value() for card in opponent_weapons)) * 8.0
        score += (ai_moves - opponent_moves) * 4.0

        ai_pos = game.board.get_player_position(self.player_id)
        opponent_pos = game.board.get_player_position(opponent)
        if ai_pos is not None and opponent_pos is not None:
            distance = self._distance(ai_pos, opponent_pos)
            score += (4 - distance) * 2.5 if ai_weapons else (distance - 3) * 1.2

        if game.phase == GamePhase.APPEASING:
            score += 12.0 if game.current_request_winner == self.player_id else 0.0
            score -= 12.0 if game.current_request_winner == opponent else 0.0
            score += len(game.get_available_request_types(self.player_id)) * 3.0 if game.can_choose_request(self.player_id) else 0.0
            score -= len(game.get_available_request_types(opponent)) * 3.0 if game.can_choose_request(opponent) else 0.0

        if game.has_pending_combat() and game.pending_combat_players:
            next_fighter = game.pending_combat_players[0]
            best_ai_weapon = max((card.combat_value() for card in ai_weapons), default=0)
            best_enemy_weapon = max((card.combat_value() for card in opponent_weapons), default=0)
            if next_fighter == self.player_id:
                score += 10.0 + best_ai_weapon * 2.0
            else:
                score -= 10.0 + best_enemy_weapon * 2.0

        if game.has_pending_ballista():
            score += 9.0 if game.current_player == self.player_id else -9.0

        if game.has_pending_card_placement():
            score += 6.0 if game.current_player == self.player_id else -6.0

        return score

    def _score_draft_card(self, card: Card, current_hand: list[Card], opponent_hand: list[Card]) -> float:
        score = float(card.combat_value() * 9)
        if card.rank == CardRank.KING:
            score += 44.0
        elif card.rank == CardRank.QUEEN:
            score += 28.0
        elif card.rank == CardRank.TEN:
            score += 18.0

        owned_suits = {owned.suit for owned in current_hand}
        if card.suit not in owned_suits:
            score += 8.0

        opponent_suits = {owned.suit for owned in opponent_hand}
        if card.rank == CardRank.KING and not any(owned.rank == CardRank.KING for owned in opponent_hand):
            score += 6.0
        if card.suit not in opponent_suits:
            score += 1.5
        return score

    def _score_appeasing_card(self, game: GameState, card: Card) -> float:
        hierarchy = game.get_appeasing_hierarchy()
        strength = {suit: len(hierarchy) - index for index, suit in enumerate(hierarchy)}
        role = game.suit_roles.get(card.suit)
        score = float(card.combat_value() * 3)
        score += strength.get(card.suit, 0) * 9.0
        if role == SuitRole.WEAPONS:
            score += 3.0
        if card.rank == CardRank.KING:
            score += 2.0
        return score

    def _sorted_positions(
        self,
        positions: list[Position],
        game: GameState,
        actor: int,
    ) -> list[Position]:
        opponent_pos = game.board.get_player_position(1 - actor)
        if opponent_pos is None:
            return list(positions)
        return sorted(positions, key=lambda pos: (self._distance(pos, opponent_pos), self._distance_to_center(pos)))

    @staticmethod
    def _distance(first: Position, second: Position) -> int:
        row_delta = abs(first.row - second.row)
        col_delta = abs(first.col - second.col)
        row_distance = min(row_delta, Board.ROWS - row_delta)
        col_distance = min(col_delta, Board.COLS - col_delta)
        return row_distance + col_distance

    @staticmethod
    def _distance_to_center(position: Position) -> int:
        centers = (2, 3)
        return min(abs(position.row - row) + abs(position.col - col) for row in centers for col in centers)

    @staticmethod
    def _clone_game(game: GameState) -> GameState:
        return pickle.loads(pickle.dumps(game, protocol=pickle.HIGHEST_PROTOCOL))

    @staticmethod
    def _advance_forced_passes(game: GameState) -> bool:
        advanced = False
        for _ in range(6):
            if not game.advance_forced_traversing():
                break
            advanced = True
            game.check_game_over()
        return advanced

    @staticmethod
    def _next_actor(game: GameState) -> int | None:
        if game.winner is not None:
            return None
        if game.has_pending_combat():
            return game.pending_combat_players[0] if game.pending_combat_players else None
        if game.has_pending_ballista() or game.has_pending_card_placement():
            return game.current_player

        pending = game.pending_request_resolution
        if pending is not None:
            return int(pending.get("player", game.current_player))

        for player_id in (game.current_player, 1 - game.current_player):
            if game.can_choose_request(player_id):
                return player_id

        if game.phase == GamePhase.APPEASING:
            for player_id in (game.current_player, 1 - game.current_player):
                if any(game.can_submit_appeasing_card(player_id, card) for card in game.get_player_hand(player_id)):
                    return player_id
            return None

        if game.phase == GamePhase.TRAVERSING:
            return game.current_player
        return None


StrategicAI = SmartPanAI
