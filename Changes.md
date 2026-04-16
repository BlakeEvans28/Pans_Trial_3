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
