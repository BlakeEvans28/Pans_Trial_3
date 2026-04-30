# Project 2

## Pan's Trial

Pan's Trial is a two-player digital strategy game built for ECE 348. Two challengers enter a shifting labyrinth and compete to become Pan's next champion. Players draft their starting cards, traverse a 6x6 toroidal labyrinth, collect useful cards, fight when they land on the same tile, and use the Appeasing Pan phase to reshape the board or change damage totals.

## GitHub Submission Layout

- `Pans_Trial.exe` - single-file Windows executable for playing the game.
- gameplay video file - recorded example of the game being played.
- `README.md` - this guide.

The full project source code, assets, tests, and supporting files are packaged in the release zip named `PansTrial_v1.0` on the right side of the GitHub repository page under Releases. Download that release asset if you want the complete project files instead of only the attached executable/video/README set.

## How to Play the Executable

1. Download `Pans_Trial.exe` from the repository files.
2. Place it in any folder on your Windows machine.
3. Double-click `Pans_Trial.exe`.
4. Use the on-screen controls to start the draft and play the game.

If Windows shows a security warning, choose the option to run the app anyway. This can happen for student-built executables that are not code-signed.

## Download the Full Project

1. Open the GitHub repository page.
2. Find the Releases section on the right side.
3. Open the release named `PansTrial_v1.0`.
4. Download the attached zip file and extract it.

That release zip contains the complete Python project, including `main.py`, the `engine/` and `ui/` folders, tests, assets, and supporting project documents.

## Controls

- `Arrow Keys` or `WASD`: move through the labyrinth.
- `Mouse`: click cards, requests, Ballista targets, Plane Shift rows/columns, Restructure colors, and Appeasing Pan placement holes.
- `Pick Up`: spend a movement turn to collect the card under the current player, except walls.

## Rules Summary

The game starts with an initial draft. Players alternate choosing high-rank cards, and the remaining player cards are used as the player identities. The Omens then assign the four color families to the current labyrinth roles: Walls, Traps, Ballista, and Weapons.

During Traversing the Labyrinth, players alternate movement turns. The board wraps toroidally, so leaving one edge enters from the opposite edge. Walls block movement. Traps become damage for the player who triggers them. Ballista tiles let the player choose a reachable tile in a straight line until a wall blocks the path. Weapon-color cards are kept in the normal hand and may be used only during head-to-head combat.

During Appeasing Pan, both players play one normal hand card if possible. The reversed Omen color order determines trump strength, and same-color cards are decided by card rank. The winner chooses a request first, then the loser chooses unless Ignore Us ends the phase. Requests include Restructure, Steal Life, Ignore Us, and Plane Shift. At the end of the phase, the loser places the two played cards into labyrinth holes when possible; if there are not enough holes, the remaining played cards return to the loser's hand.

The game ends immediately when a player reaches 25 or more damage. The other player becomes Pan's champion.

## Run From Source

If you download and extract the `PansTrial_v1.0` release zip, you can run the game from source. This project was developed with Python 3.13 on Windows.

```powershell
python -m venv .venv
.\.venv\Scripts\activate
python -m pip install pygame-ce pygame_gui pandas pytest
python main.py
```

## Run Tests

If you download the full project release, the included rule tests can be run with:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_rules.py -q
```

## Build the Web Version

The browser build script uses the pygame-web Python 3.12 runtime. From the full project folder, create a fresh Python 3.12 environment and install the web build requirements:

```powershell
py -3.12 -m venv .venv-web
.\.venv-web\Scripts\activate
python -m pip install --upgrade pip
python -m pip install -r requirements-web.txt
python build_web.py --build-only
```

The build output is written to `WEB_BUILD\pans_trial_web.zip`. To build and serve it locally in one command, omit `--build-only`:

```powershell
python build_web.py --port 8000
```

Then open `http://localhost:8000` in a browser while the command is still running.

## Build the Executable

If you download the full project release, the submitted executable can be rebuilt with PyInstaller and the included slim spec file. The spec removes unused large pygame_gui CJK font bundles so the single executable stays below the 25 MB upload limit.

```powershell
.\.venv\Scripts\python.exe -m pip install pyinstaller
.\.venv\Scripts\python.exe -m PyInstaller --noconfirm --clean --distpath . --workpath build\pyinstaller_slim Pans_Trial_slim.spec
```

## Notes for GitHub

The repository file list is intentionally small for submission purposes. The playable `.exe`, the gameplay video, and this README are attached directly, while the complete project is provided through the `PansTrial_v1.0` release zip.
