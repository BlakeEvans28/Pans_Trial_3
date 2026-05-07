# Gameplay and Rules

This page describes the current implemented rules in the digital project.

## Goal

Force the opponent to `25` or more total damage before you reach that threshold yourself.

## Match Setup

Each match starts with three separate card groups:

- The Ace-through-9 cards form the shuffled 6x6 labyrinth.
- The four Jacks are set aside as Omens.
- The draft pool is the 12 high cards: four Satyrs (`10`), four Oracles (`Queen`), and four Heroes (`King`).

A coin flip decides who drafts first. Players alternate picks until ten cards have been taken. All Satyrs and Oracles are drafted, but only two Heroes may be drafted. The two Heroes left behind become the player identity cards.

## Omen Assignment

After the draft, the four Jacks are revealed in order. That order assigns each suit family to one of four current roles:

- `Walls`
- `Traps`
- `Ballista`
- `Weapons`

A card keeps its suit for the whole match, but the suit's effect depends on the current Omen mapping. A later `Restructure` request can swap those role assignments mid-game.

## Traversing the Labyrinth

Traversing is the main board phase.

- The board is a `6x6` toroidal grid.
- Leaving one edge wraps to the opposite edge.
- A Traversing cycle contains `6` total turns: `3` for each player.
- The active player alternates after every move, pickup, or forced pass.
- The current implementation begins Traversing with Player 2.

On a Traversing turn, the active player may either move one tile or spend the turn interacting with the card on their current tile.

## Tile and Interaction Effects

### Walls

- A move into a Wall is illegal.
- A Wall tile also cannot be picked up from the current tile.

### Traps

- Landing on a Trap adds that card to the triggering player's damage pile.
- Picking up a Trap from the current tile does the same.
- The Trap card is removed from the board, which creates a hole.

### Weapons

- Landing on or picking up a Weapon adds that card to the player's normal hand.
- Weapons stay in the same hand used for Appeasing Pan.
- A card is combat-legal only while its current suit role is `Weapons`.

### Ballista

- Landing on a Ballista starts a targeting state instead of applying normal pickup behavior.
- The player may choose any reachable tile in a straight line.
- Ballista paths continue until blocked by a Wall.
- The launch does not trigger the effect of the destination tile.
- If the destination contains the other player, combat starts immediately.

## Combat

Combat is a temporary substate inside Traversing.

- Combat begins when both players occupy the same tile.
- The moving player chooses a combat card first.
- The opponent chooses second if they also have at least one legal Weapon-role card.
- Each selected weapon card is removed from the user's hand and added to the opponent's damage pile.

Because both players can strike in one combat, collisions can damage both sides in the same event.

## Appeasing Pan

After six Traversing turns, the game checks whether both players still have at least one normal hand card.

- If both do, the game enters `Appeasing Pan`.
- If either player has no hand cards left, Appeasing Pan is skipped and the game returns directly to another Traversing cycle.

During Appeasing Pan:

1. Each player submits one hand card.
2. The played suits are compared using the phase hierarchy.
3. If both cards share the same suit, rank breaks the tie.
4. The winner chooses the first Pan request.

The current trump hierarchy is:

- `Walls > Traps > Ballista > Weapons`

## Pan Requests

The winner chooses one request first. The loser chooses a different request second unless `Ignore Us` is chosen first and ends the sequence.

### Restructure

- Choose two suits.
- Swap their current Omen role assignments.
- This changes how matching cards behave on the board and in hands.

### Steal Life

- Choose one card from your own damage pile.
- Choose one card from the opponent's damage pile.
- Swap those two cards.

### Ignore Us

- End the request sequence immediately.
- No second request is chosen after this.

### Plane Shift

- Choose a row or column.
- Choose a direction.
- Wrap that full line by one tile.
- Cards and any player standing on that line move with it.

## Hole Placement After Appeasing Pan

After requests resolve, the Appeasing loser handles the two cards that were played in the phase.

- Open holes are empty board spaces.
- A space occupied by a player is not a legal hole.
- The loser places the played cards into open holes when possible.
- If fewer holes remain than cards waiting to be placed, the unplaced cards return to that loser's hand.

## Forced Pass State

Some request outcomes can trap a player by leaving them with no legal moves. When that happens, the trapped player is forced to pass their next `3` Traversing turns.

## Win Condition

- A player loses immediately when their damage pile reaches `25` or more total damage.
- The surviving player becomes Pan's champion.
