"""
ARCHITECTURE FOR AI INTEGRATION

This document explains how Pan's Trial engine is designed to support AI agents
without any modifications to the engine itself.
"""

# ============================================================================
# CORE DESIGN PRINCIPLE: Engine-Agent Separation
# ============================================================================

"""
The engine provides a PURE STATE and ACTION interface that any agent can use:

┌─────────────────────────────────────────────────────────────┐
│                    Game Engine (Pure Logic)                 │
│                  (No UI, No pygame, Headless)              │
├─────────────────────────────────────────────────────────────┤
│ - GameState: Full game state                                │
│ - get_legal_moves(): All valid actions                      │
│ - apply_action(): Execute and validate                      │
│ - check_game_over(): Terminal detection                     │
└─────────────────────────────────────────────────────────────┘
         ▲                                    ▲
         │ State Query                       │ Action
         │                                    │
    ┌────┴─────────────────────┬─────────────┘
    │                          │
    │                          ▼
    │              ┌───────────────────┐
    │              │   Agent Interface │
    │              ├───────────────────┤
    │              │ choose_action()   │
    │              │ get_reward()      │
    │              │ is_done()         │
    │              └───────────────────┘
    │                     ▲
    ├─────────────────────┼──────────────┬────────────────┐
    │                     │              │                │
    ▼                     │              ▼                ▼
┌──────────────┐  ┌───────────────┐  ┌──────────┐  ┌──────────┐
│ HumanAgent   │  │HeuristicAgent │  │ RLAgent  │  │AIvAI Sim │
│   (Current)  │  │  (Later)      │  │ (PART 2) │  │(PART 3)  │
└──────────────┘  └───────────────┘  └──────────┘  └──────────┘
"""


# ============================================================================
# AGENT INTERFACE SPECIFICATION
# ============================================================================

from typing import Protocol, Optional
from engine import GameState, Action, GamePhase


class Agent(Protocol):
    """Interface all agents must implement."""
    
    def choose_action(self, state: GameState, player_id: int) -> Action:
        """
        Given game state, choose the best action for this player.
        
        Args:
            state: Current game state (query only, don't modify)
            player_id: Which player (0 or 1)
        
        Returns:
            Action: The chosen action
        """
        ...
    
    def reset(self) -> None:
        """Reset agent for new game."""
        ...


# ============================================================================
# EXAMPLE: HUMAN AGENT (Current Implementation)
# ============================================================================

class HumanAgent:
    """Agent controlled by human player via UI input."""
    
    def __init__(self):
        self.last_move = None
    
    def choose_action(self, state: GameState, player_id: int) -> Optional[Action]:
        """
        Human provides input via UI click.
        Returns None until input is received.
        """
        # UI sets this via event handling
        return self.last_move
    
    def reset(self) -> None:
        self.last_move = None


# ============================================================================
# EXAMPLE: HEURISTIC AGENT (Next Step)
# ============================================================================

class HeuristicAgent:
    """Agent using rule-based heuristics."""
    
    def choose_action(self, state: GameState, player_id: int) -> Action:
        """Choose action based on hand-coded strategy."""
        
        # Get all legal moves
        legal_moves = state.get_legal_moves(player_id)
        
        if state.phase == GamePhase.TRAVERSING:
            # Movement phase
            opponent_id = 1 - player_id
            opponent_pos = state.board.get_player_position(opponent_id)
            
            # Strategy: Move toward opponent
            best_move = self._find_best_move(
                state, player_id, opponent_pos, legal_moves
            )
            return best_move
        
        elif state.phase == GamePhase.APPEASING:
            # Card play phase
            hand = state.get_player_hand(player_id)
            best_card = self._find_best_card(state, player_id, hand)
            return PlayCardAction(player_id, best_card)
    
    def _find_best_move(self, state, player_id, target_pos, legal_moves):
        """Find move that gets closest to target."""
        # Calculate distance for each move
        # Return best move
        pass
    
    def _find_best_card(self, state, player_id, hand):
        """Find best card to play in Appeasing phase."""
        # Evaluate card strength
        # Consider trump order
        # Return best card
        pass
    
    def reset(self) -> None:
        pass


# ============================================================================
# EXAMPLE: RL AGENT (PART 2 Integration)
# ============================================================================

from gymnasium import Env, spaces
import numpy as np


class PanTrialEnv(Env):
    """
    Gymnasium environment wrapper for Pan's Trial.
    Allows RL agents (stable-baselines3) to train.
    """
    
    def __init__(self):
        self.game = GameState()
        self._setup_game()
        
        # Define action and observation spaces
        self.action_space = spaces.Discrete(4)  # 4 directions
        self.observation_space = spaces.Box(
            low=0, high=255,
            shape=(6, 6, 3),  # 6x6 grid with 3 channels
            dtype=np.uint8
        )
    
    def reset(self):
        """Reset game and return initial observation."""
        self.game = GameState()
        self._setup_game()
        return self._get_observation()
    
    def step(self, action):
        """Execute action and return (obs, reward, done, info)."""
        
        # Convert action to MoveAction
        direction_map = {0: "up", 1: "down", 2: "left", 3: "right"}
        move = MoveAction(0, direction_map[action])
        
        # Apply action
        success = self.game.apply_action(move)
        
        # Calculate reward
        reward = self._calculate_reward(success)
        
        # Check if done
        done = self.game.check_game_over()
        
        # Get observation
        obs = self._get_observation()
        
        return obs, reward, done, {}
    
    def _get_observation(self) -> np.ndarray:
        """Convert game state to RL observation."""
        # Create 6x6 grid representation
        # Encode card types, player positions
        # Return as numpy array
        pass
    
    def _calculate_reward(self, move_successful: bool) -> float:
        """Calculate reward for this step."""
        
        if not move_successful:
            return -1.0  # Invalid move penalty
        
        reward = 0.0
        
        # Damage reward: Punish taking damage
        p0_damage = self.game.get_damage_total(0)
        reward -= p0_damage * 0.1
        
        # Combat reward: Reward dealing damage
        p1_damage = self.game.get_damage_total(1)
        reward += p1_damage * 0.1
        
        # Win bonus
        if self.game.check_game_over() and self.game.winner == 0:
            reward += 100.0
        
        return reward
    
    def _setup_game(self):
        """Initialize game."""
        from deck_utils import setup_game_deck, create_6x6_labyrinth, draft_hands, get_jack_suit_order
        
        labyrinth, hand = setup_game_deck()
        grid = create_6x6_labyrinth(labyrinth)
        p0, p1, _ = draft_hands(hand)
        jacks = get_jack_suit_order(hand)
        
        self.game.setup_board(grid)
        self.game.setup_suit_roles(jacks)
        
        for c in p0:
            self.game.add_card_to_hand(0, c)
        for c in p1:
            self.game.add_card_to_hand(1, c)
        
        from engine import Position
        self.game.place_player(0, Position(5, 4))
        self.game.place_player(1, Position(0, 4))
        self.game.phase = GamePhase.TRAVERSING


# Usage with stable-baselines3:
"""
from stable_baselines3 import PPO

# Create environment
env = PanTrialEnv()

# Train agent
model = PPO("MlpPolicy", env, verbose=1)
model.learn(total_timesteps=100000)

# Use trained agent
obs = env.reset()
for _ in range(1000):
    action, _ = model.predict(obs)
    obs, reward, done, _ = env.step(action)
    if done:
        obs = env.reset()
"""


# ============================================================================
# EXAMPLE: AI vs AI SIMULATION
# ============================================================================

class GameSimulator:
    """Run simulations with different agents."""
    
    @staticmethod
    def simulate_game(agent0: Agent, agent1: Agent, verbose=False) -> int:
        """
        Run a complete game between two agents.
        Returns winner (0 or 1).
        """
        from deck_utils import setup_game_deck, create_6x6_labyrinth, draft_hands, get_jack_suit_order
        
        # Setup game
        game = GameState()
        labyrinth, hand = setup_game_deck()
        grid = create_6x6_labyrinth(labyrinth)
        p0, p1, _ = draft_hands(hand)
        jacks = get_jack_suit_order(hand)
        
        game.setup_board(grid)
        game.setup_suit_roles(jacks)
        
        for c in p0:
            game.add_card_to_hand(0, c)
        for c in p1:
            game.add_card_to_hand(1, c)
        
        from engine import Position
        game.place_player(0, Position(5, 4))
        game.place_player(1, Position(0, 4))
        game.phase = GamePhase.TRAVERSING
        
        # Play game
        turn = 0
        while not game.check_game_over():
            current_player = game.current_player
            agent = agent0 if current_player == 0 else agent1
            
            # Get action from agent
            action = agent.choose_action(game, current_player)
            
            # Execute action
            game.apply_action(action)
            
            if verbose and turn % 10 == 0:
                print(f"Turn {turn}: P0={game.get_damage_total(0)}, P1={game.get_damage_total(1)}")
            
            turn += 1
        
        if verbose:
            print(f"Game over: Player {game.winner} wins!")
        
        return game.winner
    
    @staticmethod
    def tournament(agents: list[Agent], matches: int) -> dict:
        """Run tournament between agents."""
        scores = {i: 0 for i in range(len(agents))}
        
        for i, agent1 in enumerate(agents):
            for j, agent2 in enumerate(agents):
                if i != j:
                    for _ in range(matches):
                        winner = GameSimulator.simulate_game(agent1, agent2)
                        if winner == i:
                            scores[i] += 1
        
        return scores


# ============================================================================
# USAGE PATTERNS
# ============================================================================

"""
# PATTERN 1: Single game with human vs AI
human = HumanAgent()
heuristic = HeuristicAgent()

game = GameState()
# ... setup game ...

while not game.check_game_over():
    if game.current_player == 0:
        # Human input (from UI)
        action = human.choose_action(game, 0)
    else:
        # AI decision
        action = heuristic.choose_action(game, 1)
    
    game.apply_action(action)


# PATTERN 2: AI vs AI simulation
agent1 = HeuristicAgent()
agent2 = HeuristicAgent()
winner = GameSimulator.simulate_game(agent1, agent2, verbose=True)


# PATTERN 3: RL training
from stable_baselines3 import PPO

env = PanTrialEnv()
model = PPO("MlpPolicy", env)
model.learn(total_timesteps=100000)


# PATTERN 4: Tournament evaluation
agents = [HeuristicAgent(), HeuristicAgent()]
scores = GameSimulator.tournament(agents, matches=10)
print(scores)
"""


# ============================================================================
# KEY DESIGN DECISIONS
# ============================================================================

"""
1. NO UI DEPENDENCY IN ENGINE
   - Engine doesn't import pygame
   - Engine doesn't know about rendering
   - Engine is 100% headless testable

2. STATE IMMUTABILITY
   - Agents query state, don't modify it
   - State changes only via apply_action()
   - Clean separation of concerns

3. ACTION OBJECTS
   - Strongly typed (Action, MoveAction, PlayCardAction)
   - Easy to log, replay, analyze
   - Natural for RL environments

4. STANDARDIZED INTERFACE
   - All agents implement same interface
   - Easy to swap agents
   - Easy to run simulations

5. GYMNASIUM COMPATIBLE
   - Can wrap as standard gym environment
   - Works with stable-baselines3, Ray RLlib, etc.
   - No modifications needed to engine
"""


# ============================================================================
# SUMMARY
# ============================================================================

"""
This architecture ensures:

✓ Engine stays pure and testable
✓ UI is pluggable (can swap for different UIs)
✓ Agents are interchangeable
✓ Easy to add new agent types
✓ Supports RL training without modification
✓ Supports AI vs AI simulations
✓ Supports self-play training

The engine is a GAME ENGINE, not a game implementation.
The game is implemented through agents and UIs that use the engine.

This is the same architecture used by:
- Chess engines (e.g., Stockfish)
- Go engines (e.g., AlphaGo, KataGo)
- Video game physics engines
"""
