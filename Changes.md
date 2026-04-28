# Changes Log

Use this file to track the most recent committed changes in reverse chronological order.

## Instructions For Future AI Updates

1. Add each new log entry directly below this instruction section.
2. Keep the newest entry at the top and the older entrys as you go down to the bottom. 
3. Create one entry per calendar day of related work you are documenting.
4. Include the calendar day of that work in `YYYY-MM-DD` format.
5. Say who made the change. Use the commit author name when possible.
6. Summarize what changed in a short sentence or a few short bullet points.
7. Keep the summary focused on meaningful code, content, or behavior changes.
8. Do not delete or rewrite older entries unless the user explicitly asks for it.

## 2026-04-28 - Codex
Commit: `pending` - Added browser rooms and localhost web play
Summary:
- Added a dependency-free localhost browser server plus static web client so Pan's Trial can now be opened in two browser tabs or windows and played through a shared room.
- Inserted a `Start Game -> Room Selection` flow for the desktop client too, including room creation, joining by code, waiting for a second player, and synchronized two-player startup.
- Added shared multiplayer setup helpers and localhost room networking so both the browser version and the desktop room flow use the live Python game engine.
- Updated gameplay rendering to respect per-player perspective during networked matches so each client sees only its own hand while the board state stays synchronized.

## 2026-04-28 - Codex
Commit: `pending` - Retuned Restructure and scrollable UI layouts
Summary:
- Lowered the `Restructure` title so it starts closer to the old `Choose` baseline, and shifted the subtitle plus color-choice rows down to match.
- Extended the mouse-wheel `How To Play` guide layout so its stone sections run about `1.4x` longer before reaching the bottom controls.
- Increased the victory parchment/banner height to about `1.1x` its contained size on the end-game screen.
- Capped the victory match-summary viewport at `6` visible text lines while keeping wheel scrolling for overflow.

## 2026-04-27 - Brandt Homan
Commit: `pending` - Matched the omen-resolution subtitle to the outlined forest text
Summary:
- Changed `Resolving the color roles...` on the omen reveal screen to use the same outlined white text treatment as the forest-background helper copy so it stays readable against the art.

## 2026-04-27 - Brandt Homan
Commit: `pending` - Expanded Pan request stone spacing and shortened victory summary
Summary:
- Reworked the `Choose Pan's Request` popup so the stone grows around a fixed text-and-plank layout instead of stretching the content into the stone border.
- Made the Pan request stone panel taller while keeping the words and wood planks at the same size, giving the border more breathing room above and below the content.
- Shortened the victory screen's scrollable match-summary parchment to about `80%` of its previous height while keeping its top edge anchored in place.
- Removed the resolved handwritten Pan request stone-fit note from `Future_Improvements.md`.

## 2026-04-27 - Blake Evans
Commits: `aea4b5f`, `66b7085` - Added scrollable victory-summary and labyrinth-art revisions
Summary:
- Added a mouse-wheel-scrollable match-summary viewport on the victory banner and regression coverage that keeps the wrapped text clipped inside the parchment frame.
- Iterated on decorative board and player art by adding labyrinth-frame and player-face assets, then refining coin-face scaling/alignment while keeping the square grid as the default fallback.
- Updated Appeasing Pan hierarchy expectations and added renderer/UI checks around the board layout, coin art, and scroll-wheel behavior.

## 2026-04-26 - Brandt Homan
Commit: `pending` - Tuned stone popup layout and readability
Summary:
- Converted the damage-pile popup into a larger stone plaque and gave its rows more room so card labels stop overlapping.
- Reworked the Appeasing Pan request popup and Restructure popup sizing, spacing, and inner layout so their text and buttons fit the visible stone face more cleanly.
- Updated the shared stone-panel scaling and text-safe content box so tall plaques keep a wider usable center instead of pushing text onto the border.
- Changed forest-background helper text to outlined white lettering for better contrast without losing readability against the art.
- Refreshed `Future_Improvements.md` with a new handwritten note about the remaining Pan request / Restructure stone-fit issue.

## 2026-04-26 - Brandt Homan
Commit: `pending` - Polished request popups, settings layout, and coin flip animation
Summary:
- Enlarged the Appeasing Pan request chooser and Restructure selector, moved Restructure onto the shared stone panel style, and gave the request and role text more room so labels no longer crowd the panel borders.
- Hid the Appeasing Pan winner banner immediately after the winning player makes the first request choice instead of leaving it up through the rest of request resolution.
- Reworked the Settings layout so the `Back` button stays visible at any screen size by sizing the option planks from the remaining space.
- Fixed the Coin Flip screen so the coin always alternates between `P1` and `P2` during the animation before settling on the actual starting player.

## 2026-04-25 - Blake Evans
Commit: `e6ece44` - Added phase-banner art and stone gameplay popups
Summary:
- Added `traversing.png` and `appeasing_pan.png` and rendered them as crossfading gameplay phase banners at the top of the main game screen.
- Switched several major gameplay popups to the shared stone-panel style and tightened request/inspect/Steal Life click handling around the wood-plank buttons.
- Refined tutorial and HUD layout so the phase banner, legend, damage chips, and popup surfaces avoid each other more cleanly.

## 2026-04-24 - Blake Evans
Commit: `f13a7cc` - Added shared stone panels, victory art, and refreshed audio assets
Summary:
- Added `stone.png`, `banner.png`, and `victory.png`, plus updated intro/phase music files for the title and game-over presentation.
- Introduced shared stone-panel rendering and text-safe content helpers and applied them across popups, tutorial panels, settings/help surfaces, and draft/gameplay info boxes.
- Reworked the game-over screen into a parchment-and-victory-art layout with a wrapped match summary and side-by-side wood action buttons.

## 2026-04-22 - Brandt Homan
Commit: `pending` - Extended title theming into gameplay controls
Summary:
- Fixed Plane Shift confirmation previews so column shifts display as columns and the animation snaps from its final frame back to the first instead of reversing.
- Applied the title-screen wood-button treatment to more gameplay controls, including request choices, Plane Shift action buttons, damage chips, and popup action buttons.
- Moved the wood treatment off individual cards and onto larger text panels like the draft value guide, trial-hand panels, and top-right suit-role legend.
- Removed the gameplay card-rank key from the labyrinth screens.
- Repositioned tutorial text panels so they avoid highlighted gameplay areas and added smoke checks for draft/gameplay tutorial placement.

## 2026-04-22 - Blake Evans
Commits: `6c4aa0e`, `050ccc7`, `1f90f30` - Expanded the forest/title UI theme
Summary:
- Added `Pan_Background.png` and pushed the forest-and-title presentation deeper across menus, gameplay panels, and supporting UI surfaces.
- Continued the wood/stone theming pass through gameplay controls, tutorial panels, and information boxes while tightening layout and readability.
- Reworked supporting audio/UI plumbing and added more rules/UI regression coverage alongside the day's theming updates.

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

## 2026-04-21 - Blake Evans
Commits: `e250154`, `5f34949`, `bfb7f1f`, `bc21656` - Added title/audio and card-art assets
Summary:
- Added `PanTitle.png`, `Pan_Icon.png`, `Pan_Intro.mp3`, and `PanPhase1.mp3` to prepare the title-screen art and music pass.
- Added full Trap and Weapon card image sets under `assets/cards/` for the gameplay/deck visuals.
- Added refreshed standalone `Trap.png` and `Ballista.png` board art assets and logged follow-up ideas in `Future_Improvements.md`.

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
Commits: `8dee5ca`, `44d9203` - Expanded gameplay popups and portrait player markers
Summary:
- Replaced the old side-button request flow with centered request, Steal Life, Restructure, and Plane Shift popups, and made the top damage totals clickable to open a damage-pile popup.
- Refined traversal/gameplay interactions by fixing toroidal edge clicks, tightening request and hole-placement rules, and adding draft/board clarity updates plus new regression coverage.
- Added `player_portrait_micah.png` and replaced the board's text-only `P1` and `P2` markers with circular portrait-based player markers that scale cleanly on shared tiles.

## 2026-04-14 - Blake Evans
Commits: `c5b9975`, `4519dfe` - Created the Project 3 codebase and docs
Summary:
- Added the initial engine, UI screens, main loop, tests, balancing scripts, executable/spec files, and project documentation for Project 3.
- Checked in the early reports, reference guides, and media artifacts that supported the initial delivery.
- Followed up with a small cleanup in `latex_apr_12_report.txt`.

## Entry Template

## YYYY-MM-DD - Author Name (laptop owner, not codex)
Commit(s): `short-hash[, short-hash]` - Daily title
Summary:
- Short summary of the main change.
- Short summary of another important change.

## Example

## 2026-04-14 - Blake Evans
Commit: `c5b9975` - Fixed
Summary:
- Replace these example lines with a brief summary of what changed in that commit.
