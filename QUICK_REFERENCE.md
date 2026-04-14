# Quick Reference - Pan's Trial Foundation

## Files Created

### Engine (Game Logic)
- `engine/cards.py` - Card models, combat values
- `engine/board.py` - 6×6 toroidal grid system
- `engine/actions.py` - Action definitions
- `engine/game_state.py` - Core game state and rules
- `engine/__init__.py` - Package exports

### UI (Rendering)
- `ui/window.py` - Pygame window management
- `ui/board_renderer.py` - Board and card rendering
- `ui/__init__.py` - Package exports

### Utilities
- `main.py` - Game entry point
- `deck_utils.py` - Deck setup functions
- `verify_foundation.py` - Automated verification

### Testing
- `tests/test_rules.py` - 7 comprehensive tests

### Documentation
- `README.md` - Full architecture guide
- `PROJECT_STATUS.md` - This project status (detailed)
- `FOUNDATION_SUMMARY.txt` - Implementation summary
- `ARCHITECTURE_FOR_AI.py` - AI integration examples

## Key Classes

### Cards Module
```python
Card(rank, suit)              # Single card
CardRank                      # Enum: ACE-KING
CardSuit                      # Enum: HEARTS, DIAMONDS, CLUBS, SPADES
SuitRole                      # Enum: WALLS, TRAPS, BALLISTA, WEAPONS
PlayerHand                    # Player's cards
DamagePile                    # Player's damage
```

### Board Module
```python
Position(row, col)            # Grid coordinates (0-5, 0-5)
Board                         # 6×6 toroidal grid
  - get_cell(pos)             # Get cell content
  - set_card(pos, card)       # Set card
  - place_player(id, pos)     # Place player
  - move_row/col(idx, dir)    # Shift grid
  - get_player_position(id)   # Find player
```

### Actions Module
```python
ActionType                    # Enum: MOVE, PLAY_CARD, etc.
MoveAction(player_id, direction)
PlayCardAction(player_id, card)
ChooseRequestAction(player_id, request_type, params)
RequestType                   # Enum: RESTRUCTURE, STEAL_LIFE, etc.
```

### GameState Module
```python
GameState                     # Main game manager
GamePhase                     # Enum: SETUP, TRAVERSING, APPEASING, GAME_OVER

# Core Methods
setup_board(grid)
setup_suit_roles(jack_suits)
place_player(player_id, position)
add_card_to_hand(player_id, card)
get_legal_moves(player_id)
apply_action(action)
check_game_over()
get_damage_total(player_id)
```

### UI Modules
```python
GameWindow                    # Pygame window
  - tick()                    # Frame update
  - render()                  # Draw frame
  - quit()                    # Cleanup

BoardRenderer                 # Board rendering
  - render()                  # Draw board
  - get_cell_at_mouse()       # Mouse to grid
```

## Common Usage

### Initialize Game
```python
from engine import GameState, Position
from deck_utils import *

game = GameState()

# Setup
labyrinth, hand = setup_game_deck()
grid = create_6x6_labyrinth(labyrinth)
p0, p1, start = draft_hands(hand)
jacks = get_jack_suit_order(hand)

game.setup_board(grid)
game.setup_suit_roles(jacks)

for card in p0:
    game.add_card_to_hand(0, card)
for card in p1:
    game.add_card_to_hand(1, card)

game.place_player(0, Position(5, 4))
game.place_player(1, Position(0, 4))
```

### Game Loop
```python
while not game.check_game_over():
    player = game.current_player
    
    # Get legal moves
    moves = game.get_legal_moves(player)
    
    # Choose action
    action = choose_action(game, player)  # Human/AI
    
    # Execute
    game.apply_action(action)
```

### Query State
```python
hand = game.get_player_hand(0)
damage = game.get_damage_total(0)
position = game.board.get_player_position(0)
legal_moves = game.get_legal_moves(0)
game_over = game.check_game_over()
winner = game.winner
```

### Render
```python
from ui import GameWindow, BoardRenderer

window = GameWindow()
renderer = BoardRenderer()

while True:
    dt = window.tick()
    if dt is None:
        break
    
    renderer.render(window.screen, game.board, suit_roles)
```

## Card Values

| Rank | Value |
|------|-------|
| Ace | 1 |
| 2-10 | Face value |
| Queen | 11 |
| King | 12 |

## Suit Roles (Dynamic)

Determined by Jack shuffle each round:

| Role | Effect |
|------|--------|
| Walls | Block movement |
| Traps | Deal damage + steal card |
| Ballista | Free row/col movement |
| Weapons | Combat requirement |

## Request Types

| Request | Effect |
|---------|--------|
| Restructure | Swap two Jacks |
| Steal Life | Swap damage cards |
| Ignore Us | No effects |
| Plane Shift | Shift row/col |

## Movement

- 4 directions: up, down, left, right
- Toroidal wrapping (edges connect)
- 3 moves per player per turn
- Walls block, everything else passable

## Combat

Triggered when players land on same cell:
- Both players with weapons deal damage
- Damage = highest card from hand
- Card goes to opponent's damage pile

## Win Condition

First to 25+ total damage loses immediately

## Testing

```bash
# Run all tests
pytest tests/test_rules.py -v

# Run single test
pytest tests/test_rules.py::test_card_combat_value -v

# Verify foundation
python verify_foundation.py
```

## Imports

```python
# Engine
from engine import (
    Card, CardRank, CardSuit, SuitRole,
    Board, Position,
    GameState, GamePhase,
    Action, ActionType, MoveAction, PlayCardAction
)

# UI
from ui import GameWindow, BoardRenderer

# Utils
from deck_utils import *
```

## Next Tasks (PART 2)

1. Mouse input handling
2. Action button UI
3. Request implementation
4. Animations
5. Victory screen

## Architecture

```
Engine (pure Python, no pygame)
    ↓ (Actions)
UI (pygame rendering)
    ↓ (State query)
Agents (Human, AI, RL)
```

## Stats

- **Lines of Code**: 1,270+
- **Test Coverage**: 7 tests, 100% pass
- **Type Hints**: 100%
- **Documentation**: Complete
- **AI Ready**: ✓ Yes

## Commands

```bash
# Verify everything works
python verify_foundation.py

# Run tests
pytest tests/test_rules.py -v

# Run game (requires display)
python main.py

# View documentation
cat README.md
```

---

**Status**: ✅ Foundation Complete - Ready for PART 2
