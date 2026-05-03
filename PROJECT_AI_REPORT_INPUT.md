# Pan's Trial - Project Report Input for AI Processing

## ADJUSTMENTS & COMMENTS (Edit this section with any changes you want in the final report)

Please add any comments, corrections, or specific sections you'd like emphasized in the LaTeX report below:

```
[YOUR COMMENTS HERE - This section will be considered when generating the final report]

Examples:
- Emphasize the multiplayer networking aspects
- Include more detail on the card game mechanics
- Focus on the web deployment pipeline
- Add performance benchmarks
- Highlight specific technical achievements
- etc.
```

---

## PROJECT OVERVIEW

**Project Name:** Pan's Trial - Interactive Card Game

**Course:** ECE 348 (Group Project)

**Current Date:** May 2, 2026

**Status:** Functional with web and desktop deployment capabilities

**Description:** 
Pan's Trial is an interactive card game featuring strategic labyrinth navigation, card drafting, and turn-based combat. The game supports both single-player and two-player multiplayer modes, with implementations for desktop (Pygame) and web (Pygbag) platforms.

---

## KEY FEATURES

### Game Mechanics
- **Card Drafting System:** Players draft Satyrs, Oracles, and Heroes before gameplay
- **Labyrinth Board:** 6x6 procedurally-generated labyrinth with card placement
- **Turn-Based Gameplay:** Traversing phase with card-based actions
- **Multiplayer Support:** Real-time two-player matches with room-based matchmaking

### Platforms
- **Desktop:** Native Pygame application for Windows
- **Web:** Browser-based gameplay via Pygbag with WebSocket multiplayer
- **Server:** Local room server for hosting multiplayer games

### Architecture Features
- Async game loop with frame-rate independent updates
- Multiplayer room management with player synchronization
- Internationalization (i18n) support for multiple languages
- Custom pygame_gui integration with browser-safe threading
- Web-safe audio streaming

---

## PROJECT STRUCTURE

### Core Engine (`engine/`)
- `game_state.py` - Game state management, turn logic, win conditions
- `board.py` - Labyrinth board representation and pathfinding
- `cards.py` - Card definitions and mechanics
- `actions.py` - Game actions and effects
- `__init__.py` - Engine package exports

### User Interface (`ui/`)
- `window.py` - Main game window, display scaling, web detection
- `game_screen.py` - Primary gameplay screen rendering and input
- `screen_manager.py` - Screen navigation and state management
- `input_handler.py` - Keyboard and mouse input processing
- `board_renderer.py` - Labyrinth board visualization
- `audio_manager.py` - Sound and music playback (desktop/web aware)
- `suit_icons.py` - Card suit visual rendering
- `player_names.py` - Player display name management

### Multiplayer (`multiplayer/`)
- `local_room.py` - Local room server for desktop/LAN play
- `browser_room.py` - WebSocket-based room client for web play
- `serialization.py` - Game state serialization for network transmission
- `__init__.py` - Multiplayer package exports

### Internationalization (`i18n/`)
- `config.py` - i18n configuration
- `translations.py` - Translation data
- `translator.py` - Translation lookup and substitution
- `resource_loader.py` - Resource loading utilities
- `__init__.py` - i18n package exports

### Build & Deployment
- `build_web.py` - Web bundle creation and packaging for Pygbag
- `room_server.py` - Standalone room server for multiplayer hosting
- `main.py` - Entry point with async game loop and screen management
- `deck_utils.py` - Card deck setup and initialization

### Assets
- `assets/cards/` - Card image files
- `assets/PanTitle.png` - Title screen artwork
- `assets/Pan_Icon.png` - Application icon/favicon
- `audio/` - Audio files (MP3 for desktop, WAV for web)

### Configuration & Documentation
- `requirements-web.txt` - Web build dependencies (pygame-ce, pygame_gui, python-i18n, Pillow)
- `WEB_BUILD/` - Web build output and HTML template
- `WEB_BUILD_HANDOFF.md` - Web build documentation
- `README.md` - Project readme
- `QUICK_REFERENCE.md` - Quick start guide

---

## DEPENDENCIES

### Core Runtime
- **pygame-ce** (2.5.7) - Game engine and rendering
- **pygame_gui** (0.6.14) - UI widget library
- **python-i18n** (0.3.9) - Internationalization framework
- **Pillow** (12.2.0+) - Image processing for web optimization

### Development Tools
- **pytest** - Unit testing framework
- **pygbag** - Web deployment (Emscripten/WebAssembly)

---

## BUILDING & RUNNING

### Desktop Single-Player
```
.venv-run\Scripts\python.exe main.py
```

### Desktop Two-Player
```
.venv-run\Scripts\python.exe room_server.py
(in another terminal)
.venv-run\Scripts\python.exe main.py
```

### Web Build
```
.venv-run\Scripts\python.exe build_web.py
```

### Web with Multiplayer
```
.venv-run\Scripts\python.exe build_web.py
(wait for completion)
.venv-run\Scripts\python.exe room_server.py
(open http://localhost:8000 in browser)
```

---

## TECHNICAL HIGHLIGHTS

### Cross-Platform Compatibility
- Async/await pattern allows responsive event handling on web
- Platform detection via `sys.platform == "emscripten"` for web-specific code
- Resource loader abstractions for different asset loading strategies

### Networking & Multiplayer
- RESTful API for room creation/joining
- WebSocket protocol for real-time game state synchronization
- Room codes for easy player matchmaking
- Serializable game state for network transmission

### Web Deployment Pipeline
- Automated bundling with `build_web.py`
- Image optimization with Pillow for faster web loading
- HTML5 audio streaming for browser compatibility
- Custom pygame_gui thread handling for browser safety

### Graphics & Rendering
- Procedural labyrinth generation
- Scaled rendering for different screen sizes
- Icon-based menu system with hover states
- Optimized sprite rendering for web

---

## TESTING & VERIFICATION

- `tests/test_rules.py` - Game rule verification
- `balance_testing.py` - Card balance analysis
- `verify_foundation.py` - Foundation validation

---

## KNOWN LIMITATIONS & FUTURE WORK

- Web multiplayer requires server deployment for internet play (currently LAN only)
- Audio streaming model differs between desktop (MP3) and web (WAV/streaming)
- Fullscreen mode disabled on web platform
- Browser-safe threading limits background processing

---

## DEPLOYMENT NOTES

### Local LAN Play
- Run `room_server.py` on one machine
- Share the LAN IP address (e.g., `192.168.x.x:8000`)
- Other players access via browser or direct connection

### Production Deployment
- Deploy `room_server.py` on a public server with SSL certificates
- Use `--certfile` and `--keyfile` flags for HTTPS
- Configure `--web-root` to serve the web build
- Set PORT environment variable as needed

---

## FILES TO INCLUDE IN REPORT

This input document references the following key files (consider including code snippets or descriptions):
- Main entry point: `main.py`
- Web builder: `build_web.py`
- Room server: `room_server.py`
- Game state engine: `engine/game_state.py`
- Screen manager: `ui/screen_manager.py`
- Game screen: `ui/game_screen.py`
