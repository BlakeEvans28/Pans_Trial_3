# Changes Log

Use this file to track the most recent committed changes in reverse chronological order.

## Instructions For Future AI Updates

1. Add each new log entry directly below this instruction section.
2. Keep the newest entry at the top and the older entrys as you go down to the bottom. 
3. Create one entry per commit you are documenting.
4. Include the calendar day of the commit in `YYYY-MM-DD` format.
5. Say who made the change. Use the commit author name when possible.
6. Summarize what changed in a short sentence or a few short bullet points.
7. Keep the summary focused on meaningful code, content, or behavior changes.
8. Do not delete or rewrite older entries unless the user explicitly asks for it.

## 2026-04-22 - Brandt Homan
Commit: `pending` - Extended title theming into gameplay controls
Summary:
- Fixed Plane Shift confirmation previews so column shifts display as columns and the animation snaps from its final frame back to the first instead of reversing.
- Applied the title-screen wood-button treatment to more gameplay controls, including request choices, Plane Shift action buttons, damage chips, and popup action buttons.

## 2026-04-21 - Brandt Homan
Commit: `pending` - Added title art, music, and UI smoke checks
Summary:
- Reworked the title screen so `PanTitle.png` fills the screen and right-side `Pan_Icon.png` wood buttons show overlaid labels with hover brightening.
- Added `Pan_Background.png` as the cover-scaled background for the non-title screens and restyled menu-screen controls as wood buttons.
- Switched audio to the checked-in intro and phase music loops while keeping only the battle clash sound effect.
- Added compact hand-card Inspect hints, an animated Plane Shift confirmation preview, Settings missing-art warnings, and regression-style UI smoke checks.

## 2026-04-21 - Brandt Homan
Commit: `pending` - Kept move and Ballista highlights clear of card numbers
Summary:
- Changed legal-move, Ballista-target, and board-cell highlight outlines so they leave the top-left card value visible.

## 2026-04-21 - Brandt Homan
Commit: `pending` - Pick combat weapons from the normal hand
Summary:
- Removed the visible right-side weapon subhand from gameplay and made combat weapon selection happen directly from the active player's normal hand cards.
- Highlighted usable weapon cards during combat and changed compact Inspect actions to use legal weapon cards from the hand.

## 2026-04-21 - Brandt Homan
Commit: `pending` - Moved Restructure controls beside the maze
Summary:
- Changed the Restructure color-swap selector from a centered modal into an off-board side panel so the maze remains visible while choosing which omen roles to swap.

## 2026-04-21 - Brandt Homan
Commit: `pending` - Kept hand cards visible outside Appeasing Pan
Summary:
- Made the active player's hand cards render during normal gameplay instead of only during Appeasing Pan card play.
- Changed Wall tile labels to show colored combat-value numbers like Trap and Ballista tiles.

## 2026-04-21 - Brandt Homan
Commit: `pending` - Added card inspect, Plane Shift confirmation, and shared trap art
Summary:
- Added compact hand-card Inspect popups so small screens can enlarge a card before choosing to play it.
- Added a Plane Shift confirmation popup before the selected row or column moves, plus a Settings button to reset the first tutorial cycle.
- Switched trap tiles to the shared `Trap.png` artwork and rendered trap card numbers in the current trap-family color.

## 2026-04-21 - Brandt Homan
Commit: `pending` - Added audio, same-size cards, and clearer Plane Shift UI
Summary:
- Added generated combat, trap, and spooky labyrinth audio tied to the existing sound-volume setting with graceful fallback when audio is unavailable.
- Updated tutorial tips to turn off after one Appeasing Pan cycle and added in-overlay Tips Off controls for draft and gameplay tutorials.
- Made hand and Appeasing placement cards render at labyrinth tile size with matching artwork, added active-player movement highlights, redesigned Plane Shift with numbered rows/columns and direction popups, allowed Steal Life reselection, and colored Ballista tile numbers by the Ballista family color.

## 2026-04-21 - Brandt Homan
Commit: `pending` - Fixed tutorial highlight over Appeasing popups
Summary:
- Changed tutorial highlighting so active popups are highlighted directly instead of drawing the board highlight through the Appeasing Pan request popup.

## 2026-04-21 - Brandt Homan
Commit: `pending` - Added settings, tutorial, coin flip, art, and match summary
Summary:
- Added Settings and Coin Flip screens, including fullscreen/windowed mode, text size, animation speed, sound-volume storage, tutorial toggles, and randomized draft-start order.
- Added optional tutorial overlays, Game Over match summaries, event tracking, and board artwork that updates by each card's current Walls, Traps, Ballista, or Weapons role.
- Updated Draft cards to use readable muted family-color backgrounds, changed hand buttons to stacked card/role labels, and refreshed `Future_Improvements.md` with new review items.

## 2026-04-21 - Brandt Homan
Commit: `pending` - Added How To Play and gameplay clarity updates
Summary:
- Added a How To Play page that is reachable from the home screen and explains the draft, Omens, Traversing, Appeasing Pan, requests, and hole placement.
- Added Appeasing Pan result and card-return notice banners, role labels on bottom hand cards, and a clearer Ballista targeting overlay with path lines and dimmed unreachable tiles.
- Replaced the completed AI todo items in `Future_Improvements.md` with new improvement ideas for review and added regression coverage for automatic card-return notices.

## 2026-04-17 - Brandt Homan
Commit: `pending` - Flipped the Appeasing Pan hierarchy strip order
Summary:
- Reversed only the top-of-screen Appeasing Pan color strip so the displayed order matches the intended player-facing presentation.
- Left the underlying trump-resolution logic unchanged.

## 2026-04-17 - Brandt Homan
Commit: `pending` - Fixed reveal-card colors and explicit Appeasing Pan trump order
Summary:
- Updated the omen reveal screen so the two bottom hero/player cards now show their real family-color markers instead of black circles.
- Made Appeasing Pan use an explicit `Weapons > Ballista > Traps > Walls` trump hierarchy in both the winner-resolution logic and the on-screen hierarchy strip.
- Replaced the completed AI todo items in `Future_Improvements.md`, added new improvement candidates for review, and fixed the shared-tile player-offset helper while locking the rules with a new regression test.

## 2026-04-16 - Brandt Homan
Commit: `pending` - Added screen-fitting and resizable window layout
Summary:
- Made the game start at a size that fits the current display instead of assuming a fixed `1200x900` window.
- Enabled native window resizing and added resize-event handling so screens recompute their layout when the window size changes.
- Updated the board, menus, draft screen, gameplay overlays, legends, and popups to scale and stay aligned with the current window dimensions.

## 2026-04-15 - Blake Evans
Commit: `pending` - Added portrait-based player markers
Summary:
- Created a circular portrait asset from `Micah.jpg` for use as the in-game player icon.
- Replaced the board's text-only `P1` and `P2` markers with circular portrait markers that show `Player 1` or `Player 2` above the icon instead of inside it.
- Added scaling, caching, and shared-tile label spacing so the new player markers render cleanly even when both players occupy the same space.

## 2026-04-14 - Blake Evans
Commit: `pending` - Updated gameplay popups and traversal interactions
Summary:
- Replaced the old side-button request flow with centered request, Steal Life, Restructure, and Plane Shift popups, and made the top damage totals clickable to open a damage-pile popup.
- Removed the visible left-side movement and pickup controls, fixed toroidal edge click movement, offset the two player markers so shared tiles stay readable, and added the draft value legend plus colored draft suit markers.
- Prevented players from placing Appeasing cards into occupied holes, limited `Ignore Us` to the winning appeaser, and added regression coverage for ballista landings, toroidal click directions, request availability, and hole placement.

## Entry Template

## YYYY-MM-DD - Author Name (laptop owner, not codex)
Commit: `short-hash` - Commit title
Summary:
- Short summary of the main change.
- Short summary of another important change.

## Example

## 2026-04-14 - Blake Evans
Commit: `c5b9975` - Fixed
Summary:
- Replace these example lines with a brief summary of what changed in that commit.
