# For BRANDT, BLAKE, WALKER (NOT FOR AI TO DO)




# For AI

- The full screen version of the UI is not appeasing. I want it to go back to the old version where the heiarchy was on the right side, the damages were on the left and the tap to inspect didn't exist. I want the banner back on top. I don't like the tap to inspect. Rework the damage to say health, and subtract down from 25 their value left based on the traps and weapons used against them. I also want the pop ups to go to the old HUD version as well. They dont fit well in this new version. like the appeasing pan was a 2x2.

- Player Trial hands in the draft should have the color of the card selected in it. The trial hands should also be next to eachother in full screen like they used to be, not on top of eachother.

- The "Create room" "join room" "ready" and "back" planks in the two player page need to be 0.5 a button down from the bottom of the room code enter screen. and I want a .25 button size gap from the bottom of the top 2 buttons to the top of the bottom 2 buttons.

## Must-have before submitting

- Make one public playable URL that starts the game without any local setup. The current hosted room-server path should be tested from a different computer or phone, not just localhost.
- Add a short in-game first-run tutorial or guided first turn. Judges should understand the goal, movement, combat/request choices, and win condition without reading a separate document.
- Add a "Solo Tutorial" mode, even if the AI is simple. A competition judge may not have a second player available during review.
- Make the Two Player flow self-explanatory: create room, copy/share room code, join room, ready up, reconnect/leave handling, and clear error messages when the server is unreachable.
- Add a loading screen with progress text and a retry/reload hint. Browser builds can take time, and a silent wait looks broken.


## Prototype polish

- Add hover/click sounds and visual feedback to all major buttons so the web version feels responsive.
- Add a concise controls/help overlay accessible during gameplay.
- Add a pause/menu button with Restart, Main Menu, Settings, and Leave Room.
- Improve mobile/tablet layout or explicitly show a "desktop/laptop recommended" message if mobile is not a target.
- Add stronger feedback for turn ownership in multiplayer: "Your turn", "Waiting for Player 2", and disabled actions for the inactive player.
- Add small animation moments for drafting, omen reveal, movement, attacks, traps, and victory.

## Stability and deployment

- Add an automated smoke test that builds the web package and confirms `WEB_BUILD/site/index.html` plus `/rooms` can be served together.
- Add browser console error checks during local web testing, especially for missing assets/audio and blocked network requests.
- Add a simple health endpoint to the room server, such as `/health`, for hosted uptime checks.
- Add cleanup for inactive multiplayer rooms so old rooms do not pile up on a hosted server.
- Add environment-variable configuration for production settings like allowed origins, room timeout, and max rooms.
- Confirm the final build size is accepted by the chosen competition host.

## Nice-to-have stretch goals

- Add matchmaking-style "Quick Room" so players do not need to manually share a code.
- Add spectator/replay mode for judging and demos.
- Add a settings preset for accessibility: larger text, reduced animation, and high contrast.
- Add credits/license screen for art, fonts, audio, and libraries.
- Add a small title-screen badge or footer with version/build date so testers can report bugs against the right build.
