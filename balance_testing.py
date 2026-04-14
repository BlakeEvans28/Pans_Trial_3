"""
Headless balance-testing harness for Pan's Trial.

Creates three AI profiles, runs 100 simulated games, writes an Excel workbook
with detailed logs, and produces a short rubric-aligned report.
"""

from __future__ import annotations

import argparse
import copy
import random
import statistics
import zipfile
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable
from xml.sax.saxutils import escape

from deck_utils import create_6x6_labyrinth, get_jack_suit_order, setup_pregame_cards
from engine import (
    Card,
    CardRank,
    ChooseCombatCardAction,
    ChooseRequestAction,
    GamePhase,
    GameState,
    MoveAction,
    PickupCurrentCardAction,
    PlaceCardsAction,
    PlayCardAction,
    Position,
    RequestType,
    ResolveBallistaShotAction,
    ResolvePlaneShiftAction,
    SelectDamageCardAction,
    SelectRestructureSuitAction,
    SelectPlaneShiftDirectionAction,
    SuitRole,
)
from pan_theme import get_family_name, get_rank_name_with_value


OUTPUT_XLSX = "Balancing_Testing_01.xlsx"
OUTPUT_REPORT = "Balancing_Testing_01_Report.md"
DEFAULT_GAMES = 100
MAX_ACTIONS_PER_GAME = 5000


@dataclass
class GameRun:
    summary: dict
    events: list[dict]


def format_card(card: Card | None) -> str:
    if card is None:
        return ""
    return f"{get_rank_name_with_value(card.rank)} {get_family_name(card.suit)}"


def format_cards(cards: Iterable[Card]) -> str:
    return " | ".join(format_card(card) for card in cards)


def format_pos(pos: Position | None) -> str:
    if pos is None:
        return ""
    return f"({pos.row},{pos.col})"


def toroidal_distance(a: Position, b: Position) -> int:
    row_delta = min((a.row - b.row) % 6, (b.row - a.row) % 6)
    col_delta = min((a.col - b.col) % 6, (b.col - a.col) % 6)
    return row_delta + col_delta


def iter_positions() -> Iterable[Position]:
    for row in range(6):
        for col in range(6):
            yield Position(row, col)


def snapshot_state(game: GameState) -> dict:
    return {
        "phase": game.phase.value,
        "current_player": game.current_player + 1,
        "movement_turn": game.movement_turn,
        "p1_pos": format_pos(game.board.get_player_position(0)),
        "p2_pos": format_pos(game.board.get_player_position(1)),
        "p1_damage": game.get_damage_total(0),
        "p2_damage": game.get_damage_total(1),
        "p1_hand": len(game.get_player_hand(0)),
        "p2_hand": len(game.get_player_hand(1)),
        "p1_weapons": len(game.get_player_weapons(0)),
        "p2_weapons": len(game.get_player_weapons(1)),
        "pending_request": game.get_pending_request_type() or "",
        "request_winner": "" if game.current_request_winner is None else game.current_request_winner + 1,
        "forced_pass_p1": game.forced_pass_turns[0],
        "forced_pass_p2": game.forced_pass_turns[1],
        "pending_ballista_targets": len(game.get_pending_ballista_targets()),
    }


def append_event(
    events: list[dict],
    game_id: int,
    seed: int,
    matchup: str,
    player1_ai: str,
    player2_ai: str,
    event_index: int,
    event_type: str,
    actor: str,
    detail: str,
    game: GameState | None,
    note: str = "",
) -> None:
    row = {
        "game_id": game_id,
        "seed": seed,
        "matchup": matchup,
        "player1_ai": player1_ai,
        "player2_ai": player2_ai,
        "event_index": event_index,
        "event_type": event_type,
        "actor": actor,
        "detail": detail,
        "note": note,
    }
    if game is not None:
        row.update(snapshot_state(game))
    events.append(row)


def clone_and_apply(game: GameState, action) -> GameState | None:
    rng_state = random.getstate()
    try:
        clone = copy.deepcopy(game)
        if not clone.apply_action(action):
            return None
        return clone
    finally:
        random.setstate(rng_state)


def get_suit_strength(game: GameState, suit) -> int:
    hierarchy = list(reversed(game.jack_order))
    if suit in hierarchy:
        return len(hierarchy) - hierarchy.index(suit)
    return 0


def get_role_positions(game: GameState, role: SuitRole) -> list[Position]:
    positions = []
    for pos in iter_positions():
        card = game.board.get_card(pos)
        if card is not None and game.suit_roles.get(card.suit) == role:
            positions.append(pos)
    return positions


def nearest_distance(origin: Position, targets: list[Position]) -> int:
    if not targets:
        return 6
    return min(toroidal_distance(origin, target) for target in targets)


def evaluate_state(game: GameState, player_id: int) -> float:
    opponent = 1 - player_id
    own_pos = game.board.get_player_position(player_id)
    opp_pos = game.board.get_player_position(opponent)
    own_damage = game.get_damage_total(player_id)
    opp_damage = game.get_damage_total(opponent)
    own_weapons = len(game.get_player_weapons(player_id))
    opp_weapons = len(game.get_player_weapons(opponent))
    own_hand = len(game.get_player_hand(player_id))
    opp_hand = len(game.get_player_hand(opponent))

    score = (opp_damage - own_damage) * 4.5
    score += (own_weapons - opp_weapons) * 7.5
    score += (own_hand - opp_hand) * 1.2
    score += (len(game.get_legal_moves(player_id)) - len(game.get_legal_moves(opponent))) * 1.1

    if own_damage >= 20:
        score -= 20
    if opp_damage >= 20:
        score += 20

    if own_pos is not None and opp_pos is not None:
        distance_to_opponent = toroidal_distance(own_pos, opp_pos)
        if own_weapons > 0:
            score += (6 - distance_to_opponent) * 2.5
        else:
            weapon_targets = get_role_positions(game, SuitRole.WEAPONS)
            score += (6 - nearest_distance(own_pos, weapon_targets)) * 2.0

    if game.has_pending_combat():
        if game.current_player == player_id:
            score += 15
        else:
            score -= 10

    if game.has_pending_ballista() and game.current_player == player_id:
        score += 4

    return score


def list_actions(game: GameState, player_id: int) -> list:
    if player_id != game.current_player:
        return []

    if game.phase == GamePhase.TRAVERSING:
        if game.pending_combat_players:
            return [
                ChooseCombatCardAction(player_id, card)
                for card in game.get_player_weapons(player_id)
            ]

        if game.has_pending_ballista():
            return [
                ResolveBallistaShotAction(player_id, pos.row, pos.col)
                for pos in game.get_pending_ballista_targets()
            ]

        if game.forced_pass_turns[player_id] > 0:
            return []

        actions = []
        if game.can_pick_up_current_card(player_id):
            actions.append(PickupCurrentCardAction(player_id))
        actions.extend(MoveAction(player_id, direction) for direction in game.get_legal_moves(player_id))
        return actions

    if game.phase == GamePhase.APPEASING:
        pending = game.get_pending_request_type()

        if game.has_pending_card_placement():
            return [
                PlaceCardsAction(player_id, [pos])
                for pos in game.get_hole_positions()
            ]

        if pending == "steal_life":
            selected_own = game.get_pending_steal_life_card()
            if selected_own is None:
                return [
                    SelectDamageCardAction(player_id, player_id, card)
                    for card in game.damage[player_id].cards
                ]
            return [
                SelectDamageCardAction(player_id, 1 - player_id, card)
                for card in game.damage[1 - player_id].cards
            ]

        if pending == "plane_shift":
            direction = game.get_pending_plane_shift_direction()
            if direction is None:
                return [
                    SelectPlaneShiftDirectionAction(player_id, direction_name)
                    for direction_name in ["up", "down", "left", "right"]
                ]
            return [ResolvePlaneShiftAction(player_id, index) for index in range(6)]

        if pending == "restructure":
            selected_suits = set(game.get_pending_restructure_suits())
            return [
                SelectRestructureSuitAction(player_id, suit)
                for suit in game.jack_order
                if suit not in selected_suits
            ]

        if game.current_request_winner is None:
            return [PlayCardAction(player_id, card) for card in game.get_player_hand(player_id)]

        if game.can_choose_request(player_id):
            actions = [
                ChooseRequestAction(player_id, RequestType.RESTRUCTURE),
                ChooseRequestAction(player_id, RequestType.IGNORE_US),
                ChooseRequestAction(player_id, RequestType.PLANE_SHIFT),
            ]
            if game.damage[player_id].cards and game.damage[1 - player_id].cards:
                actions.append(ChooseRequestAction(player_id, RequestType.STEAL_LIFE))
            return actions

    return []


def describe_action(action) -> str:
    action_type = getattr(action, "type", None)
    if action_type is None:
        return str(action)
    kind = action_type.value
    if kind == "move":
        return f"Move {action.direction}"
    if kind == "pick_up_current":
        return "Pick Up Current Tile"
    if kind == "play_card":
        return f"Play {format_card(action.card)}"
    if kind == "choose_combat_card":
        return f"Combat {format_card(action.card)}"
    if kind == "choose_request":
        return f"Request {action.request_type.value}"
    if kind == "select_damage_card":
        owner = f"P{action.pile_owner + 1}"
        return f"Steal Life choose {format_card(action.card)} from {owner}"
    if kind == "select_restructure_suit":
        return f"Restructure choose {get_family_name(action.suit)}"
    if kind == "select_plane_shift_direction":
        return f"Plane Shift direction {action.direction}"
    if kind == "resolve_plane_shift":
        return f"Plane Shift index {action.index}"
    if kind == "resolve_ballista_shot":
        return f"Ballista target ({action.row},{action.col})"
    if kind == "place_cards":
        return "Place Appeasing card in " + ", ".join(format_pos(pos) for pos in action.positions)
    return kind


class BaseAgent:
    profile = "base"

    def __init__(self, seed: int):
        self.rng = random.Random(seed)

    def choose_draft_card(
        self,
        available_cards: list[Card],
        own_cards: list[Card],
        opponent_cards: list[Card],
    ) -> Card:
        raise NotImplementedError

    def choose_action(self, game: GameState, player_id: int):
        raise NotImplementedError

    def reset(self) -> None:
        return

    def _fallback_action(self, game: GameState, player_id: int):
        actions = list_actions(game, player_id)
        if not actions:
            raise RuntimeError(f"No legal actions available for player {player_id + 1}")
        return self.rng.choice(actions)


class BeginnerAgent(BaseAgent):
    profile = "Beginner"

    def choose_draft_card(self, available_cards, own_cards, opponent_cards):
        return self.rng.choice(available_cards)

    def choose_action(self, game: GameState, player_id: int):
        return self._fallback_action(game, player_id)


class AmateurAgent(BaseAgent):
    profile = "Amateur"

    def choose_draft_card(self, available_cards, own_cards, opponent_cards):
        def score(card: Card) -> float:
            base = {CardRank.KING: 75, CardRank.QUEEN: 58, CardRank.TEN: 42}[card.rank]
            if card.rank == CardRank.KING and not any(c.rank == CardRank.KING for c in own_cards):
                base += 10
            if card.suit not in [c.suit for c in own_cards]:
                base += 4
            return base + self.rng.random() * 22

        return max(available_cards, key=score)

    def choose_action(self, game: GameState, player_id: int):
        actions = list_actions(game, player_id)
        if not actions:
            return self._fallback_action(game, player_id)

        if game.phase == GamePhase.TRAVERSING:
            if game.has_pending_ballista():
                return self._choose_ballista_target(game, player_id, actions)
            if game.has_pending_combat():
                return max(actions, key=lambda action: action.card.combat_value())
            return self._choose_traversing_action(game, player_id, actions)

        if game.phase == GamePhase.APPEASING:
            pending = game.get_pending_request_type()
            if game.has_pending_card_placement():
                return self.rng.choice(actions)
            if pending == "steal_life":
                return self._choose_steal_life(game, player_id, actions)
            if pending == "plane_shift":
                return self._choose_plane_shift(game, player_id, actions)
            if pending == "restructure":
                return self.rng.choice(actions)
            if game.current_request_winner is None:
                return max(
                    actions,
                    key=lambda action: (action.card.combat_value(), get_suit_strength(game, action.card.suit)),
                )
            return self._choose_request(game, player_id, actions)

        return self._fallback_action(game, player_id)

    def _choose_traversing_action(self, game: GameState, player_id: int, actions: list):
        if self.rng.random() < 0.3:
            return self.rng.choice(actions)

        opponent = 1 - player_id
        opponent_pos = game.board.get_player_position(opponent)
        own_pos = game.board.get_player_position(player_id)
        weapon_targets = get_role_positions(game, SuitRole.WEAPONS)

        def score(action) -> float:
            if isinstance(action, PickupCurrentCardAction):
                pos = game.board.get_player_position(player_id)
                card = game.board.get_card(pos)
                role = game.suit_roles.get(card.suit) if card else None
                if role == SuitRole.WEAPONS:
                    return 50
                if role == SuitRole.TRAPS:
                    return -25
                if role == SuitRole.BALLISTA:
                    return 8
                return 5

            movement = {"up": (-1, 0), "down": (1, 0), "left": (0, -1), "right": (0, 1)}
            dr, dc = movement[action.direction]
            target = Position(own_pos.row + dr, own_pos.col + dc)
            target_card = game.board.get_card(target)
            role = game.suit_roles.get(target_card.suit) if target_card else None
            total = 0.0
            if role == SuitRole.WEAPONS:
                total += 30
            elif role == SuitRole.BALLISTA:
                total += 8
            elif role == SuitRole.TRAPS:
                total -= 14

            wrapped_target = Position(target.row % 6, target.col % 6)
            if opponent_pos is not None:
                if len(game.get_player_weapons(player_id)) > 0:
                    total += (6 - toroidal_distance(wrapped_target, opponent_pos)) * 2
                elif weapon_targets:
                    total += (6 - nearest_distance(wrapped_target, weapon_targets)) * 1.5
            return total + self.rng.random() * 2

        return max(actions, key=score)

    def _choose_ballista_target(self, game: GameState, player_id: int, actions: list):
        if self.rng.random() < 0.35:
            return self.rng.choice(actions)

        opponent_pos = game.board.get_player_position(1 - player_id)

        def score(action) -> float:
            target = Position(action.row, action.col)
            score_value = 0.0
            if opponent_pos is not None:
                if len(game.get_player_weapons(player_id)) > 0:
                    score_value += (6 - toroidal_distance(target, opponent_pos)) * 3
                else:
                    weapon_targets = get_role_positions(game, SuitRole.WEAPONS)
                    score_value += (6 - nearest_distance(target, weapon_targets)) * 2
            target_card = game.board.get_card(target)
            if target_card is not None:
                role = game.suit_roles.get(target_card.suit)
                if role == SuitRole.WEAPONS:
                    score_value += 20
                elif role == SuitRole.TRAPS:
                    score_value -= 12
            return score_value + self.rng.random()

        return max(actions, key=score)

    def _choose_steal_life(self, game: GameState, player_id: int, actions: list):
        if game.get_pending_steal_life_card() is None:
            return max(actions, key=lambda action: action.card.combat_value())
        return min(actions, key=lambda action: action.card.combat_value())

    def _choose_plane_shift(self, game: GameState, player_id: int, actions: list):
        if self.rng.random() < 0.4:
            return self.rng.choice(actions)

        pending_direction = game.get_pending_plane_shift_direction()
        if pending_direction is None:
            opponent_pos = game.board.get_player_position(1 - player_id)
            own_pos = game.board.get_player_position(player_id)
            candidates = []
            for action in actions:
                if action.direction in ["left", "right"]:
                    axis_score = 1 if opponent_pos and own_pos and opponent_pos.row != own_pos.row else 0
                else:
                    axis_score = 1 if opponent_pos and own_pos and opponent_pos.col != own_pos.col else 0
                candidates.append((axis_score + self.rng.random(), action))
            return max(candidates, key=lambda item: item[0])[1]

        opponent_pos = game.board.get_player_position(1 - player_id)
        own_pos = game.board.get_player_position(player_id)
        if pending_direction in ["left", "right"]:
            preferred = opponent_pos.row if opponent_pos is not None else (own_pos.row if own_pos is not None else 0)
        else:
            preferred = opponent_pos.col if opponent_pos is not None else (own_pos.col if own_pos is not None else 0)
        for action in actions:
            if action.index == preferred:
                return action
        return self.rng.choice(actions)

    def _choose_request(self, game: GameState, player_id: int, actions: list):
        options = {action.request_type.value: action for action in actions}
        own_damage = game.get_damage_total(player_id)
        opp_damage = game.get_damage_total(1 - player_id)
        if "steal_life" in options and own_damage >= opp_damage:
            return options["steal_life"]
        if "plane_shift" in options and self.rng.random() < 0.4:
            return options["plane_shift"]
        if "restructure" in options and self.rng.random() < 0.35:
            return options["restructure"]
        if self.rng.random() < 0.25:
            return self.rng.choice(actions)
        return options.get("ignore_us", actions[0])


class ExperiencedAgent(BaseAgent):
    profile = "Experienced"

    def choose_draft_card(self, available_cards, own_cards, opponent_cards):
        own_suits = [card.suit for card in own_cards]
        opponent_has_king = any(card.rank == CardRank.KING for card in opponent_cards)

        def score(card: Card) -> float:
            base = {CardRank.KING: 120, CardRank.QUEEN: 80, CardRank.TEN: 55}[card.rank]
            if card.rank == CardRank.KING and not any(c.rank == CardRank.KING for c in own_cards):
                base += 40
            if card.rank == CardRank.KING and not opponent_has_king:
                base += 15
            if card.suit not in own_suits:
                base += 10
            return base + self.rng.random()

        return max(available_cards, key=score)

    def choose_action(self, game: GameState, player_id: int):
        actions = list_actions(game, player_id)
        if not actions:
            return self._fallback_action(game, player_id)

        if game.phase == GamePhase.TRAVERSING:
            if game.has_pending_combat():
                return max(actions, key=lambda action: action.card.combat_value())
            return self._best_scored_action(game, player_id, actions)

        if game.phase == GamePhase.APPEASING:
            pending = game.get_pending_request_type()
            if game.has_pending_card_placement():
                return self._best_scored_action(game, player_id, actions)
            if pending == "steal_life":
                return self._choose_steal_life(game, player_id, actions)
            if pending == "plane_shift":
                return self._choose_plane_shift(game, player_id, actions)
            if pending == "restructure":
                return self._best_scored_action(game, player_id, actions)
            if game.current_request_winner is None:
                return max(
                    actions,
                    key=lambda action: (
                        get_suit_strength(game, action.card.suit),
                        action.card.combat_value(),
                    ),
                )
            return self._choose_request(game, player_id, actions)

        return self._fallback_action(game, player_id)

    def _best_scored_action(self, game: GameState, player_id: int, actions: list):
        best_action = actions[0]
        best_score = float("-inf")
        for action in actions:
            clone = clone_and_apply(game, action)
            if clone is None:
                continue
            score = evaluate_state(clone, player_id) + self._immediate_action_bonus(game, player_id, action)
            if score > best_score:
                best_score = score
                best_action = action
        return best_action

    def _immediate_action_bonus(self, game: GameState, player_id: int, action) -> float:
        if isinstance(action, PickupCurrentCardAction):
            pos = game.board.get_player_position(player_id)
            card = game.board.get_card(pos)
            role = game.suit_roles.get(card.suit) if card else None
            if role == SuitRole.WEAPONS:
                return 30
            if role == SuitRole.BALLISTA:
                return 8
            if role == SuitRole.TRAPS:
                return -18
            return 4

        if isinstance(action, MoveAction):
            movement = {"up": (-1, 0), "down": (1, 0), "left": (0, -1), "right": (0, 1)}
            own_pos = game.board.get_player_position(player_id)
            opponent_pos = game.board.get_player_position(1 - player_id)
            dr, dc = movement[action.direction]
            target = Position(own_pos.row + dr, own_pos.col + dc)
            wrapped_target = Position(target.row % 6, target.col % 6)
            card = game.board.get_card(target)
            role = game.suit_roles.get(card.suit) if card else None
            bonus = 0.0
            if role == SuitRole.WEAPONS:
                bonus += 24
            elif role == SuitRole.BALLISTA:
                bonus += 8
            elif role == SuitRole.TRAPS:
                bonus -= 16
            if opponent_pos is not None and wrapped_target == opponent_pos:
                if game.get_player_weapons(player_id):
                    bonus += 22
                elif game.get_player_weapons(1 - player_id):
                    bonus -= 14
            return bonus

        return 0.0

    def _choose_steal_life(self, game: GameState, player_id: int, actions: list):
        if game.get_pending_steal_life_card() is None:
            return max(actions, key=lambda action: action.card.combat_value())
        return min(actions, key=lambda action: action.card.combat_value())

    def _choose_plane_shift(self, game: GameState, player_id: int, actions: list):
        pending_direction = game.get_pending_plane_shift_direction()
        if pending_direction is None:
            best_action = actions[0]
            best_score = float("-inf")
            for action in actions:
                clone = clone_and_apply(game, action)
                if clone is None:
                    continue
                future_actions = list_actions(clone, player_id)
                if not future_actions:
                    score = evaluate_state(clone, player_id)
                else:
                    score = max(
                        (
                            evaluate_state(next_clone, player_id)
                            for option in future_actions
                            for next_clone in [clone_and_apply(clone, option)]
                            if next_clone is not None
                        ),
                        default=evaluate_state(clone, player_id),
                    )
                if score > best_score:
                    best_score = score
                    best_action = action
            return best_action
        return self._best_scored_action(game, player_id, actions)

    def _choose_request(self, game: GameState, player_id: int, actions: list):
        options = {action.request_type.value: action for action in actions}
        if "steal_life" in options:
            own_high = max((card.combat_value() for card in game.damage[player_id].cards), default=0)
            opp_low = min((card.combat_value() for card in game.damage[1 - player_id].cards), default=99)
            if own_high > opp_low:
                return options["steal_life"]

        if "plane_shift" in options:
            clone = clone_and_apply(game, options["plane_shift"])
            if clone is not None:
                future = list_actions(clone, player_id)
                future_score = max(
                    (
                        evaluate_state(after, player_id)
                        for option in future
                        for after in [clone_and_apply(clone, option)]
                        if after is not None
                    ),
                    default=evaluate_state(clone, player_id),
                )
                if future_score >= evaluate_state(game, player_id):
                    return options["plane_shift"]

        if "restructure" in options:
            own_moves = len(game.get_legal_moves(player_id))
            opp_moves = len(game.get_legal_moves(1 - player_id))
            if game.get_damage_total(player_id) > game.get_damage_total(1 - player_id) or own_moves < opp_moves:
                return options["restructure"]

        return options.get("ignore_us", actions[0])


def create_agent(profile: str, seed: int):
    if profile == "Experienced":
        return ExperiencedAgent(seed)
    if profile == "Amateur":
        return AmateurAgent(seed)
    if profile == "Beginner":
        return BeginnerAgent(seed)
    raise ValueError(f"Unknown profile: {profile}")


def simulate_draft(agent_p1, agent_p2, draft_cards: list[Card], game_id: int, seed: int, events: list[dict], matchup: str):
    available = list(draft_cards)
    hands = {0: [], 1: []}
    current_player = 0
    kings_drafted = 0
    event_index = len(events)

    while len(hands[0]) + len(hands[1]) < 10:
        valid_cards = [
            card
            for card in available
            if card is not None and (card.rank != CardRank.KING or kings_drafted < 2)
        ]
        agent = agent_p1 if current_player == 0 else agent_p2
        card = agent.choose_draft_card(valid_cards, list(hands[current_player]), list(hands[1 - current_player]))
        if card not in valid_cards:
            card = valid_cards[0]

        index = available.index(card)
        available[index] = None
        hands[current_player].append(card)
        if card.rank == CardRank.KING:
            kings_drafted += 1

        append_event(
            events,
            game_id,
            seed,
            matchup,
            agent_p1.profile,
            agent_p2.profile,
            event_index,
            "draft_pick",
            f"P{current_player + 1} {agent.profile}",
            format_card(card),
            None,
            note=f"Remaining draft cards: {len([c for c in available if c is not None])}",
        )
        event_index += 1
        current_player = 1 - current_player

    player_cards = [card for card in available if card is not None]
    return hands[0], hands[1], player_cards


def initialize_headless_game(labyrinth_cards: list[Card], p1_hand: list[Card], p2_hand: list[Card], jack_order: list) -> GameState:
    game = GameState()
    game.setup_suit_roles(jack_order)

    for _ in range(100):
        labyrinth_grid = create_6x6_labyrinth(labyrinth_cards)
        game.setup_board(labyrinth_grid)
        game.place_player(0, Position(5, 3))
        game.place_player(1, Position(0, 2))
        if game.get_legal_moves(0) and game.get_legal_moves(1):
            break
        random.shuffle(labyrinth_cards)

    for card in p1_hand:
        game.add_card_to_hand(0, card)
    for card in p2_hand:
        game.add_card_to_hand(1, card)

    game.current_player = 1
    game.traversing_resume_player = 1
    game.phase = GamePhase.TRAVERSING
    return game


def build_schedule(total_games: int) -> list[tuple[str, str]]:
    pair_buckets = [
        ("Experienced", "Amateur", 34),
        ("Experienced", "Beginner", 33),
        ("Amateur", "Beginner", 33),
    ]
    schedule = []
    for left, right, count in pair_buckets:
        for index in range(count):
            if len(schedule) >= total_games:
                break
            if index % 2 == 0:
                schedule.append((left, right))
            else:
                schedule.append((right, left))
    return schedule[:total_games]


def simulate_game(game_id: int, seed: int, player1_profile: str, player2_profile: str) -> GameRun:
    random.seed(seed)
    player1_agent = create_agent(player1_profile, seed + 101)
    player2_agent = create_agent(player2_profile, seed + 202)
    matchup = f"{player1_profile} vs {player2_profile}"
    events: list[dict] = []

    labyrinth_cards, draft_cards, jack_cards = setup_pregame_cards()
    p1_hand, p2_hand, player_cards = simulate_draft(player1_agent, player2_agent, draft_cards, game_id, seed, events, matchup)
    jack_order = get_jack_suit_order(jack_cards)
    game = initialize_headless_game(list(labyrinth_cards), p1_hand, p2_hand, jack_order)

    append_event(
        events,
        game_id,
        seed,
        matchup,
        player1_profile,
        player2_profile,
        len(events),
        "setup",
        "System",
        "Initial setup complete",
        game,
        note=f"Omens: {' > '.join(get_family_name(suit) for suit in jack_order)}; Leftover player cards: {format_cards(player_cards)}",
    )

    metrics = Counter()
    action_count = 0

    while action_count < MAX_ACTIONS_PER_GAME and not game.check_game_over():
        while game.advance_forced_traversing():
            metrics["forced_pass_events"] += 1
            append_event(
                events,
                game_id,
                seed,
                matchup,
                player1_profile,
                player2_profile,
                len(events),
                "forced_pass",
                f"P{game.current_player + 1}",
                "Forced traversing pass resolved",
                game,
            )
            if game.check_game_over():
                break

        if game.check_game_over():
            break

        if game.phase == GamePhase.APPEASING and game.current_request_winner is None and len(game.phase_started_cards) == 0:
            metrics["phase2_rounds"] += 1

        available_actions = list_actions(game, game.current_player)
        if not available_actions:
            if game.phase == GamePhase.TRAVERSING and not game.has_pending_ballista() and not game.has_pending_combat():
                metrics["stall_auto_pass"] += 1
                game._finish_traversing_move()
                append_event(
                    events,
                    game_id,
                    seed,
                    matchup,
                    player1_profile,
                    player2_profile,
                    len(events),
                    "stall_pass",
                    f"P{game.current_player + 1}",
                    "No legal action found; traversing move auto-passed for simulation continuity.",
                    game,
                )
                continue
            raise RuntimeError(f"No legal actions available for player {game.current_player + 1} in phase {game.phase.value}")

        current_player = game.current_player
        agent = player1_agent if current_player == 0 else player2_agent
        action = agent.choose_action(game, current_player)
        before_phase = game.phase.value
        action_description = describe_action(action)
        success = game.apply_action(action)
        if not success:
            fallback = agent._fallback_action(game, current_player)
            action_description += f" -> fallback {describe_action(fallback)}"
            success = game.apply_action(fallback)
            action = fallback

        metrics["actions"] += 1
        action_count += 1

        kind = getattr(action.type, "value", "")
        if kind == "choose_request":
            metrics["request_events"] += 1
        elif kind == "choose_combat_card":
            metrics["combat_events"] += 1
        elif kind == "resolve_ballista_shot":
            metrics["ballista_events"] += 1

        note = ""
        if before_phase == GamePhase.TRAVERSING.value and game.phase == GamePhase.TRAVERSING and game.movement_turn == 0 and not game.can_run_appeasing_phase():
            metrics["phase2_skipped"] += 1
            note = "Appeasing Pan skipped because at least one player had no hand cards."

        append_event(
            events,
            game_id,
            seed,
            matchup,
            player1_profile,
            player2_profile,
            len(events),
            "action",
            f"P{current_player + 1} {agent.profile}",
            action_description,
            game,
            note=note,
        )

    timed_out = not game.check_game_over()
    if timed_out:
        winner_player = 0 if game.get_damage_total(0) <= game.get_damage_total(1) else 1
        winner_reason = "Action cap reached; lower damage declared the balancing winner."
    else:
        winner_player = game.winner
        winner_reason = "Reached 25+ damage."

    append_event(
        events,
        game_id,
        seed,
        matchup,
        player1_profile,
        player2_profile,
        len(events),
        "game_end",
        "System",
        f"Winner: P{winner_player + 1}",
        game,
        note=winner_reason,
    )

    summary = {
        "game_id": game_id,
        "seed": seed,
        "matchup": matchup,
        "player1_ai": player1_profile,
        "player2_ai": player2_profile,
        "winner_player": winner_player + 1,
        "winner_ai": player1_profile if winner_player == 0 else player2_profile,
        "timed_out": "Yes" if timed_out else "No",
        "actions": metrics["actions"],
        "forced_pass_events": metrics["forced_pass_events"],
        "phase2_rounds": metrics["phase2_rounds"],
        "phase2_skipped": metrics["phase2_skipped"],
        "combat_events": metrics["combat_events"],
        "ballista_events": metrics["ballista_events"],
        "request_events": metrics["request_events"],
        "p1_damage": game.get_damage_total(0),
        "p2_damage": game.get_damage_total(1),
        "p1_hand_remaining": len(game.get_player_hand(0)),
        "p2_hand_remaining": len(game.get_player_hand(1)),
        "p1_weapons_remaining": len(game.get_player_weapons(0)),
        "p2_weapons_remaining": len(game.get_player_weapons(1)),
        "jacks_order": " > ".join(get_family_name(suit) for suit in jack_order),
        "p1_draft": format_cards(p1_hand),
        "p2_draft": format_cards(p2_hand),
        "leftover_player_cards": format_cards(player_cards),
        "result_reason": winner_reason,
    }
    return GameRun(summary=summary, events=events)


def mean_or_zero(values: list[float]) -> float:
    return round(statistics.mean(values), 3) if values else 0.0


def build_report_text(
    game_rows: list[dict],
    archetype_games: Counter,
    archetype_wins: Counter,
    seat_wins: Counter,
    matchup_games: Counter,
    matchup_wins: Counter,
    request_counts: Counter,
    phase2_skips: int,
) -> str:
    avg_actions = mean_or_zero([row["actions"] for row in game_rows])
    avg_p1_damage = mean_or_zero([row["p1_damage"] for row in game_rows])
    avg_p2_damage = mean_or_zero([row["p2_damage"] for row in game_rows])

    archetype_lines = []
    for profile in ["Experienced", "Amateur", "Beginner"]:
        games = archetype_games[profile]
        wins = archetype_wins[profile]
        rate = round((wins / games) * 100, 2) if games else 0.0
        archetype_lines.append(f"- {profile}: {wins}/{games} wins ({rate}%)")

    matchup_lines = []
    for matchup, total in sorted(matchup_games.items()):
        winner_counts = []
        for profile in ["Experienced", "Amateur", "Beginner"]:
            wins = matchup_wins[(matchup, profile)]
            if wins:
                winner_counts.append(f"{profile} {wins}")
        matchup_lines.append(f"- {matchup}: {total} games, winners -> {', '.join(winner_counts)}")

    request_lines = []
    for request_name, count in sorted(request_counts.items()):
        request_lines.append(f"- {request_name}: {count}")
    if not request_lines:
        request_lines.append("- No requests were recorded.")

    p1_wins = seat_wins["P1"]
    p2_wins = seat_wins["P2"]

    return f"""# Balancing Testing 01 Report

## Introduction
Pan's Trial is a two-player tactical card-and-labyrinth game where both players draft their initial hands, navigate a toroidal board, use weapon-color hand cards in combat, and try to force the opponent to 25 or more damage before Pan names a new champion. This report summarizes a headless balance study built directly on the current engine with no UI dependency. The study uses 100 AI-vs-AI simulations across three skill profiles: Experienced, Amateur, and Beginner. The goal is to measure whether the current mechanics reward stronger play in a predictable way without creating a single dominant seat or runaway state that ends variety.

## Rules
The simulations use the game's live engine rules. Each game starts with the 10-card draft, the randomized Omen color assignment, and the standard 6x6 toroidal labyrinth. Traversing remains a three-moves-per-player phase with wall blocking, pickups, ballista targeting, weapon-color combat from the normal hand, and damage tracking. Appeasing Pan uses the reversed color hierarchy for suit strength, with card rank breaking ties only when both cards share the same color. After requests resolve, the loser places the two played cards into labyrinth holes when possible. If a player has no normal hand cards left, Appeasing Pan is skipped and the game returns directly to Traversing.

## Results
The 100-game study produced an average of {avg_actions} logged actions per game. Final damage averages were {avg_p1_damage} for Player 1 and {avg_p2_damage} for Player 2. The fixed starting seat, Player 2, won {p2_wins} games while Player 1 won {p1_wins}. Appeasing Pan was skipped {phase2_skips} times after hands were exhausted.

### Archetype Results
{chr(10).join(archetype_lines)}

### Matchup Results
{chr(10).join(matchup_lines)}

### Request Usage
{chr(10).join(request_lines)}

### Balance Notes
- The skill ladder is the clearest balance signal: stronger tactical selection should produce stronger win rates. If Experienced materially outperforms Amateur and Beginner, the game is rewarding decision quality rather than pure randomness.
- The starting-seat split is an important fairness check because Player 2 always begins Traversing. A large Player 2 skew would suggest a first-mover advantage worth revisiting.
- The Phase 2 skip count matters because it shows how often the game transitions into a mostly board-and-combat endgame after the drafted hand economy is exhausted.
- Request usage helps identify whether one Pan favor is becoming a dominant default instead of situational.

## Conclusion
This simulation pass gives a reproducible balance snapshot grounded in the current implementation. The game appears healthiest when stronger agents win more often, but the seat split, request distribution, and frequency of skipped Appeasing phases should be reviewed together before calling the game fully balanced. The attached workbook keeps every game result and per-action state log so the balance claims can be audited directly.
"""


def build_analysis(game_rows: list[dict], event_rows: list[dict]) -> tuple[list[list], list[str], str]:
    archetype_games = Counter()
    archetype_wins = Counter()
    seat_wins = Counter()
    matchup_games = Counter()
    matchup_wins = Counter()
    request_counts = Counter()
    phase2_skips = 0

    for row in game_rows:
        archetype_games[row["player1_ai"]] += 1
        archetype_games[row["player2_ai"]] += 1
        archetype_wins[row["winner_ai"]] += 1
        seat_wins[f"P{row['winner_player']}"] += 1
        matchup_games[row["matchup"]] += 1
        matchup_wins[(row["matchup"], row["winner_ai"])] += 1
        phase2_skips += row["phase2_skipped"]

    for row in event_rows:
        if row["event_type"] == "action" and row["detail"].startswith("Request "):
            request_counts[row["detail"].split(" ", 1)[1]] += 1

    summary_sheet = [["Metric", "Value"]]
    summary_sheet.append(["Total simulated games", len(game_rows)])
    summary_sheet.append(["Average actions per game", mean_or_zero([row["actions"] for row in game_rows])])
    summary_sheet.append(["Average P1 final damage", mean_or_zero([row["p1_damage"] for row in game_rows])])
    summary_sheet.append(["Average P2 final damage", mean_or_zero([row["p2_damage"] for row in game_rows])])
    summary_sheet.append(["Total Phase 2 skips", phase2_skips])
    summary_sheet.append(["Player 1 wins", seat_wins["P1"]])
    summary_sheet.append(["Player 2 wins", seat_wins["P2"]])
    summary_sheet.append([])
    summary_sheet.append(["Archetype", "Win rate"])
    for profile in ["Experienced", "Amateur", "Beginner"]:
        games = archetype_games[profile]
        rate = round((archetype_wins[profile] / games) * 100, 2) if games else 0.0
        summary_sheet.append([profile, f"{rate}% ({archetype_wins[profile]}/{games})"])
    summary_sheet.append([])
    summary_sheet.append(["Request", "Usage"])
    for request_name, count in sorted(request_counts.items()):
        summary_sheet.append([request_name, count])
    summary_sheet.append([])
    summary_sheet.append(["Matchup", "Games", "Top winner"])
    for matchup, count in sorted(matchup_games.items()):
        winners = [
            (winner_ai, matchup_wins[(matchup, winner_ai)])
            for winner_ai in ["Experienced", "Amateur", "Beginner"]
            if matchup_wins[(matchup, winner_ai)] > 0
        ]
        top = max(winners, key=lambda item: item[1])[0] if winners else "N/A"
        summary_sheet.append([matchup, count, top])

    key_findings = []
    for profile in ["Experienced", "Amateur", "Beginner"]:
        games = archetype_games[profile]
        rate = round((archetype_wins[profile] / games) * 100, 1) if games else 0.0
        key_findings.append(f"{profile} won {rate}% of its appearances ({archetype_wins[profile]}/{games}).")

    p2_win_rate = round((seat_wins["P2"] / len(game_rows)) * 100, 1) if game_rows else 0.0
    key_findings.append(f"Player 2, the fixed starting seat, won {p2_win_rate}% of all simulations.")
    key_findings.append(f"Appeasing Pan was skipped {phase2_skips} times across {len(game_rows)} games when a player ran out of normal hand cards.")
    if request_counts:
        most_used_request, most_used_count = request_counts.most_common(1)[0]
        key_findings.append(f"The most-used request was {most_used_request} ({most_used_count} selections).")

    report = build_report_text(game_rows, archetype_games, archetype_wins, seat_wins, matchup_games, matchup_wins, request_counts, phase2_skips)
    return summary_sheet, key_findings, report


def workbook_cell(value, cell_ref: str) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return f'<c r="{cell_ref}" t="inlineStr"><is><t>{"TRUE" if value else "FALSE"}</t></is></c>'
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return f'<c r="{cell_ref}"><v>{value}</v></c>'
    text = escape(str(value))
    return f'<c r="{cell_ref}" t="inlineStr"><is><t xml:space="preserve">{text}</t></is></c>'


def column_name(index: int) -> str:
    letters = []
    while index > 0:
        index, remainder = divmod(index - 1, 26)
        letters.append(chr(65 + remainder))
    return "".join(reversed(letters))


def worksheet_xml(rows: list[list]) -> str:
    row_parts = []
    for row_index, row in enumerate(rows, start=1):
        cells = []
        for col_index, value in enumerate(row, start=1):
            if value == "":
                continue
            ref = f"{column_name(col_index)}{row_index}"
            cells.append(workbook_cell(value, ref))
        row_parts.append(f'<row r="{row_index}">{"".join(cells)}</row>')
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        f"<sheetData>{''.join(row_parts)}</sheetData>"
        "</worksheet>"
    )


def write_xlsx(workbook_path: Path, sheets: list[tuple[str, list[list]]]) -> None:
    created = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    with zipfile.ZipFile(workbook_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(
            "[Content_Types].xml",
            """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
  <Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>
  <Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>
  <Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>
"""
            + "".join(
                f'  <Override PartName="/xl/worksheets/sheet{index}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>\n'
                for index in range(1, len(sheets) + 1)
            )
            + "</Types>",
        )
        archive.writestr(
            "_rels/.rels",
            """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>
  <Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" Target="docProps/app.xml"/>
</Relationships>""",
        )
        archive.writestr(
            "docProps/core.xml",
            f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/" xmlns:dcmitype="http://purl.org/dc/dcmitype/" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
  <dc:creator>Codex</dc:creator>
  <cp:lastModifiedBy>Codex</cp:lastModifiedBy>
  <dcterms:created xsi:type="dcterms:W3CDTF">{created}</dcterms:created>
  <dcterms:modified xsi:type="dcterms:W3CDTF">{created}</dcterms:modified>
</cp:coreProperties>""",
        )
        archive.writestr(
            "docProps/app.xml",
            f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties" xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes">
  <Application>Codex</Application>
  <TitlesOfParts>
    <vt:vector size="{len(sheets)}" baseType="lpstr">
      {''.join(f'<vt:lpstr>{escape(name)}</vt:lpstr>' for name, _ in sheets)}
    </vt:vector>
  </TitlesOfParts>
</Properties>""",
        )
        archive.writestr(
            "xl/workbook.xml",
            """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <sheets>
"""
            + "".join(
                f'    <sheet name="{escape(name[:31])}" sheetId="{index}" r:id="rId{index}"/>\n'
                for index, (name, _) in enumerate(sheets, start=1)
            )
            + """  </sheets>
</workbook>""",
        )
        archive.writestr(
            "xl/_rels/workbook.xml.rels",
            """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
"""
            + "".join(
                f'  <Relationship Id="rId{index}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet{index}.xml"/>\n'
                for index in range(1, len(sheets) + 1)
            )
            + f'  <Relationship Id="rId{len(sheets) + 1}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>\n'
            + "</Relationships>",
        )
        archive.writestr(
            "xl/styles.xml",
            """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <fonts count="1"><font><sz val="11"/><name val="Calibri"/><family val="2"/></font></fonts>
  <fills count="2"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill></fills>
  <borders count="1"><border><left/><right/><top/><bottom/><diagonal/></border></borders>
  <cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>
  <cellXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/></cellXfs>
  <cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles>
</styleSheet>""",
        )
        for index, (_, rows) in enumerate(sheets, start=1):
            archive.writestr(f"xl/worksheets/sheet{index}.xml", worksheet_xml(rows))


def rows_from_dicts(rows: list[dict]) -> list[list]:
    if not rows:
        return [[]]
    headers = []
    for row in rows:
        for key in row.keys():
            if key not in headers:
                headers.append(key)
    return [headers] + [[row.get(header, "") for header in headers] for row in rows]


def run_balance_study(output_dir: Path, total_games: int = DEFAULT_GAMES) -> tuple[Path, Path, list[str]]:
    schedule = build_schedule(total_games)
    game_rows = []
    event_rows = []

    for game_id, (player1_profile, player2_profile) in enumerate(schedule, start=1):
        seed = 7000 + game_id * 17
        result = simulate_game(game_id, seed, player1_profile, player2_profile)
        game_rows.append(result.summary)
        event_rows.extend(result.events)

    summary_sheet, key_findings, report_text = build_analysis(game_rows, event_rows)

    workbook_path = output_dir / OUTPUT_XLSX
    report_path = output_dir / OUTPUT_REPORT
    report_path.write_text(report_text, encoding="utf-8")

    write_xlsx(
        workbook_path,
        [
            ("Summary", summary_sheet),
            ("Games", rows_from_dicts(game_rows)),
            ("Events", rows_from_dicts(event_rows)),
            ("Key Findings", [["Finding"], *[[line] for line in key_findings]]),
        ],
    )

    return workbook_path, report_path, key_findings


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run headless balance testing for Pan's Trial.")
    parser.add_argument("--games", type=int, default=DEFAULT_GAMES, help="Number of games to simulate.")
    parser.add_argument("--output-dir", type=Path, default=Path("."), help="Directory for the workbook and report.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    workbook_path, report_path, key_findings = run_balance_study(args.output_dir, args.games)
    print(f"Workbook written to: {workbook_path}")
    print(f"Report written to: {report_path}")
    print("Key findings:")
    for line in key_findings:
        print(f"- {line}")


if __name__ == "__main__":
    main()
