# Web Build Handoff

This file captures the web-build work attempted for Pan's Trial so another teammate can pick it up quickly.

## Goal

Use `pygbag` to run Pan's Trial in a browser, using the professor's reference `WEB_BUILD.zip` and `build_web.py` as a model.

## Source Material Reviewed

- Professor reference folder: `C:\Users\24hom\Downloads\WEB_BUILD`
- Professor reference script: `C:\Users\24hom\Downloads\build_web.py`
- Installed `pygbag` runtime internals:
  `C:\Users\24hom\AppData\Local\Programs\Python\Python312\Lib\site-packages\pygbag\support\cpythonrc.py`

## Important Outcome

The current web bundle is definitely packaging Pan's Trial, not the professor's game.

Verified bundled Pan's Trial files included:
- `assets/main.py`
- `assets/ui/game_screen.py`
- `assets/engine/game_state.py`
- `assets/assets/PanTitle.png`
- `assets/assets/Pan_Icon.png`

Professor-specific project folders like `SRC/`, `CONFIG/`, and hockey content were not in the generated Pan's Trial bundle.

## Files Added Or Changed For Web/Desktop Work

### New Files

- `build_web.py`
- `WEB_BUILD/index_template.html`
- `WEB_BUILD_HANDOFF.md`

### Existing Files Changed

- `main.py`
- `ui/window.py`
- `ui/audio_manager.py`
- `ui/screen_manager.py`
- `Pans_Trial_slim.spec`
- `.gitignore`

### Local Build Artifact Rebuilt

- `Pans_Trial.exe`

## What Was Implemented

### 1. Custom web build script

`build_web.py` was added to stage and package the game for browser delivery.

Current behavior:
- Copies only Pan's Trial runtime files into a staging area.
- Bundles `pygame_gui` package code plus minimal `data/` assets needed at runtime.
- Bundles the `i18n` package.
- Creates both:
  - `.apk`
  - `.tar.gz`
- Installs a custom `index.html` from `WEB_BUILD/index_template.html`
- Copies `assets/Pan_Icon.png` as the favicon.
- Creates `WEB_BUILD/pans_trial_web.zip` locally for deployment.

### 2. Browser-safe runtime changes

`ui/window.py`
- Detects `sys.platform == "emscripten"`.
- Disables fullscreen toggling on web.
- Uses a custom `SequentialResourceLoader` for `pygame_gui` to avoid Python background threads in the browser.
- Uses safer display size fallback logic if `pygame.display.Info()` returns zero sizes.

`ui/audio_manager.py`
- Added `allow_music_files` so browser builds skip MP3 music loading.
- Cached track paths for desktop use.

`ui/screen_manager.py`
- Settings screen hides fullscreen controls when fullscreen toggling is unsupported.

### 3. Browser loader template

`WEB_BUILD/index_template.html`
- Based on the professor-style `pygbag` loader.
- Loads the generated bundle from `.apk` or `.tar.gz`.
- Shows click-to-start prompt for media engagement.
- Added error trapping intended to show startup errors in-page instead of silently failing.
- Added a startup wait loop that now waits for the game to report that the first frame was rendered.

### 4. Game entry-point changes

`main.py` was changed several times during debugging:

- Converted the main loop to `async def main()`.
- Added `await asyncio.sleep(0)` once per frame for browser responsiveness.
- Added browser status/error helpers:
  - `_set_web_status(...)`
  - `_mark_web_ready()`
  - `_show_web_error(...)`
- Changed the web launch path away from direct `asyncio.run(main())` and onto `asyncio.create_task(main())` when running in the browser.
- Moved heavy imports into `main()` so startup progress can be surfaced step-by-step.
- Changed startup so only the `StartScreen` is created before the first frame; other screens are now created lazily.

## Desktop executable work completed

`Pans_Trial_slim.spec`
- Updated to bundle the `audio/` folder in addition to `assets/`.

`Pans_Trial.exe`
- Rebuilt locally after the spec change.

## Commands Used For Verification

### Tests

```powershell
python -m pytest tests\test_rules.py -q
```

Result during this work:
- `51 passed`

### Rebuild web package

```powershell
python build_web.py --build-only
```

### Serve a specific built web folder

```powershell
cd c:\Users\24hom\OneDrive\Desktop\ECE348\Pans_Trial\build\pans_trial_web_<timestamp>\build\web
python -m http.server 8000
```

## User-Observed Behavior Timeline

### Early behavior

- Page loaded.
- User clicked the "game ready / click anywhere" prompt.
- Screen went black with no visible game.

### Middle debugging stage

- Added more in-page error reporting.
- Added bundle verification and confirmed it was Pan's Trial.
- User still reported black screen.

### Later debugging stage

- Loader text changed from immediate black screen to:
  `Starting Pan's Trial...`
- That was progress because the browser was clearly reaching the startup path.

### Latest user-reported state before this handoff

- The page still stayed on `Starting Pan's Trial...`
- The latest code after that report added more granular status markers, but that newest build has not yet been user-verified in conversation.

## Strongest Technical Hypotheses Reached

### Hypothesis A: browser event-loop conflict

After reviewing `pygbag`'s `cpythonrc.py`, a likely problem was that the page was already inside an async environment while `main.py` still used `asyncio.run(main())`.

That led to changing the browser launch path to `asyncio.create_task(main())`.

### Hypothesis B: heavy startup before first frame

The game originally built many screens and UI elements up front.
That can be expensive in a browser, especially with `pygame_gui`.

That led to:
- lazy screen creation
- moving imports into `main()`
- reporting status earlier

### Hypothesis C: `pygame_gui` loader/thread mismatch

`pygame_gui` resource loading in the browser looked risky because Python background threads are a poor fit for WASM startup.

That led to the custom sequential resource loader in `ui/window.py`.

## Key Runtime Investigation Notes

Review of `pygbag` support code showed:
- `shell.source(main)` eventually reaches `shell.runpy(...)`
- `runpy(...)` checks whether the script contains `asyncio.run`
- `runpy(...)` ultimately queues/evaluates the code through the toplevel async handler

This was important because the click-to-start overlay disappearing did not prove the game loop had actually started correctly.

## Most Recent Local Build Outputs

Latest local web build created during this session:
- `build\pans_trial_web_20260430_115501\build\web`

Local deploy zip:
- `WEB_BUILD\pans_trial_web.zip`

Note:
- `WEB_BUILD\pans_trial_web.zip` is larger than GitHub's normal 100 MB file limit and is intentionally not committed.

## Recommended Next Steps

1. Test the newest build folder directly:

```powershell
cd c:\Users\24hom\OneDrive\Desktop\ECE348\Pans_Trial\build\pans_trial_web_20260430_115501\build\web
python -m http.server 8000
```

2. Observe the exact loader message after clicking:
- `Pan's Trial Python loaded...`
- `Importing pygame...`
- `Importing game engine...`
- `Importing deck setup...`
- `Importing UI...`
- `Opening game window...`
- `Loading start screen...`
- `Rendering start screen...`

3. If it still never advances, the next likely move is to instrument or isolate the first failing import:
- `pygame`
- `pygame_gui`
- `ui.screen_manager`
- image/font loading inside `StartScreen`

4. If needed, temporarily strip the browser version down to:
- `pygame.init()`
- `display.set_mode(...)`
- `fill(...)`
- `flip(...)`

Then add UI/game imports back one layer at a time.

## Repo Notes For Whoever Picks This Up

- `build/` is ignored by git.
- `WEB_BUILD/*.zip` is now ignored so local deployment zips do not pollute git status.
- `Pans_Trial.exe` is tracked and was rebuilt locally.
- `Future_Improvements.md` had unrelated local modifications in the working tree and was intentionally left alone during this handoff.
