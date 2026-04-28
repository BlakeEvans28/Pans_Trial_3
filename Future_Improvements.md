# For BRANDT, BLAKE, WALKER (NOT FOR AI TO DO)

- Maybe we should have the suit drawing before the draft so we can use the sprites we already have for their corresponding suit. This removes confusion with why the "face" draft cards change entirely after draft

- we could get rid of colors (if the above proposal is agreed upon)

- use pygbag to create the game in the web browser

# For AI
- Add `tarot_ballista.png`, `tarot_trap.png`, `tarot_wall.png`, `tarot_weapons.png` to the omen shuffling screen. replace the square background images for the four squares with the corresponding names (ex wall is replaced with `tarot_wall.png`)
- remove the Omen and wall/ballista/traps/weapons text on each of the 4 cards
- keep the colors and text version of the respective color on each card
- on the How To Play screen, the text on the scroll wheel does not dissapear until the whole text box is out of frame. Make it to where when any part of the text is out of the bounds of the scroll frame that it is not visible (just as the images do currently).
- When a Player picks a request, whatever icon appears for them to do their request, add a back button to allows the player to change their request pick if necessary.
- When at the choose a request screen, add a view labyrinth button that makes the request screen dissapear and unshades the background. When in this mode, add a button to the side that says "return to requests" that returns them to the choose a request screen when pressed. (use the wood icon for these buttons).
- If the first player to pick a request picks something, the other player cannot pick that same request.
- Update pygame to pygame ce