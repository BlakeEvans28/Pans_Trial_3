# Balancing Testing 01 Report

## Introduction
Pan's Trial is a two-player tactical card-and-labyrinth game where both players draft their initial hands, navigate a toroidal board, use weapon-color hand cards in combat, and try to force the opponent to 25 or more damage before Pan names a new champion. This report summarizes a headless balance study built directly on the current engine with no UI dependency. The study uses 100 AI-vs-AI simulations across three skill profiles: Experienced, Amateur, and Beginner. The goal is to measure whether the current mechanics reward stronger play in a predictable way without creating a single dominant seat or runaway state that ends variety.

## Rules
The simulations use the game's live engine rules. Each game starts with the 10-card draft, the randomized Omen color assignment, and the standard 6x6 toroidal labyrinth. Traversing remains a three-moves-per-player phase with wall blocking, pickups, ballista targeting, weapon-color combat from the normal hand, and damage tracking. Appeasing Pan uses the reversed color hierarchy for suit strength, with card rank breaking ties only when both cards share the same color. After requests resolve, the loser places the two played cards into labyrinth holes when possible. If a player has no normal hand cards left, Appeasing Pan is skipped and the game returns directly to Traversing.

## Results
The 100-game study produced an average of 235.83 logged actions per game. Final damage averages were 19.22 for Player 1 and 19.24 for Player 2. The fixed starting seat, Player 2, won 48 games while Player 1 won 52. Appeasing Pan was skipped 0 times after hands were exhausted.

### Archetype Results
- Experienced: 51/67 wins (76.12%)
- Amateur: 48/67 wins (71.64%)
- Beginner: 1/66 wins (1.52%)

### Matchup Results
- Amateur vs Beginner: 17 games, winners -> Amateur 17
- Amateur vs Experienced: 17 games, winners -> Experienced 9, Amateur 8
- Beginner vs Amateur: 16 games, winners -> Amateur 15, Beginner 1
- Beginner vs Experienced: 16 games, winners -> Experienced 16
- Experienced vs Amateur: 17 games, winners -> Experienced 9, Amateur 8
- Experienced vs Beginner: 17 games, winners -> Experienced 17

### Request Usage
- ignore_us: 49
- plane_shift: 124
- restructure: 49
- steal_life: 88

### Balance Notes
- The skill ladder is the clearest balance signal: stronger tactical selection should produce stronger win rates. If Experienced materially outperforms Amateur and Beginner, the game is rewarding decision quality rather than pure randomness.
- The starting-seat split is an important fairness check because Player 2 always begins Traversing. A large Player 2 skew would suggest a first-mover advantage worth revisiting.
- The Phase 2 skip count matters because it shows how often the game transitions into a mostly board-and-combat endgame after the drafted hand economy is exhausted.
- Request usage helps identify whether one Pan favor is becoming a dominant default instead of situational.

## Conclusion
This simulation pass gives a reproducible balance snapshot grounded in the current implementation. The game appears healthiest when stronger agents win more often, but the seat split, request distribution, and frequency of skipped Appeasing phases should be reviewed together before calling the game fully balanced. The attached workbook keeps every game result and per-action state log so the balance claims can be audited directly.
