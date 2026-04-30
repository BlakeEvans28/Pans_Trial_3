"""
Pan's Trial - Main entry point with screen management.
Initializes game and runs the game loop.
"""

import asyncio
import sys
import traceback
from random import choice, shuffle

IS_WEB = sys.platform == "emscripten"


def _set_web_status(message: str) -> None:
    """Show a short loader status message inside the browser overlay."""
    if not IS_WEB:
        return
    try:
        import platform

        platform.window.panTrialStatus = message
        platform.window.infobox.style.display = "block"
        platform.window.infobox.innerText = message
    except Exception:
        pass


def _mark_web_ready() -> None:
    """Tell the browser loader that the first game frame rendered successfully."""
    if not IS_WEB:
        return
    try:
        import platform

        platform.window.panTrialReady = True
        platform.window.panTrialStatus = "Pan's Trial is ready."
    except Exception:
        pass


def _show_web_error(message: str) -> None:
    """Surface startup/runtime failures inside the browser page itself."""
    if not IS_WEB:
        return
    try:
        import platform

        platform.window.panTrialReady = False
        platform.window.panTrialError = message
        platform.window.panTrialStatus = "Pan's Trial failed to start."
        platform.window.infobox.style.display = "block"
        platform.window.infobox.style.whiteSpace = "pre-wrap"
        platform.window.infobox.style.maxWidth = "80vw"
        platform.window.infobox.style.maxHeight = "70vh"
        platform.window.infobox.style.overflow = "auto"
        platform.window.infobox.style.textAlign = "left"
        platform.window.infobox.innerText = message
        platform.console.error(message)
    except Exception:
        pass


def initialize_game(
    labyrinth_cards: list,
    p0_hand: list,
    p1_hand: list,
    jack_order: list,
    starting_player: int = 1,
) -> object:
    """Initialize a new game from the completed pregame setup."""
    from deck_utils import create_6x6_labyrinth
    from engine import GamePhase, GameState, Position

    game = GameState()
    game.setup_suit_roles(jack_order)

    for _ in range(100):
        labyrinth_grid = create_6x6_labyrinth(labyrinth_cards)
        game.setup_board(labyrinth_grid)
        game.place_player(0, Position(5, 3))  # Bottom: col 3 (4th to the right)
        game.place_player(1, Position(0, 2))  # Top: col 2 (4th to the right)
        if game.get_legal_moves(0) and game.get_legal_moves(1):
            break
        shuffle(labyrinth_cards)

    for card in p0_hand:
        game.add_card_to_hand(0, card)
    for card in p1_hand:
        game.add_card_to_hand(1, card)

    game.current_player = starting_player
    game.traversing_resume_player = starting_player
    game.phase = GamePhase.TRAVERSING
    
    return game


async def main():
    """Main game loop with screens."""
    window = None
    try:
        _set_web_status("Importing pygame...")
        import pygame

        _set_web_status("Importing game engine...")
        from engine import GamePhase

        _set_web_status("Importing deck setup...")
        from deck_utils import setup_pregame_cards

        _set_web_status("Importing UI...")
        from ui.game_screen import GameScreen
        from ui.screen_manager import (
            CoinFlipScreen,
            DraftScreen,
            GameOverScreen,
            HowToPlayScreen,
            JackRevealScreen,
            ScreenManager,
            ScreenType,
            SettingsScreen,
            StartScreen,
        )
        from ui.window import GameWindow

        _set_web_status("Opening game window...")

        # Initialize window
        window = GameWindow()
        screen_manager = ScreenManager(window)
        game = None
        game_screen = None
        pregame_setup = None
        first_frame_drawn = False
        screens = {}

        def ensure_screen(screen_type: ScreenType):
            """Create screens lazily so the web build can paint the start menu fast."""
            if screen_type not in screens:
                if screen_type == ScreenType.START:
                    _set_web_status("Loading start screen...")
                    screen = StartScreen(window)
                elif screen_type == ScreenType.HOW_TO_PLAY:
                    screen = HowToPlayScreen(window)
                elif screen_type == ScreenType.SETTINGS:
                    screen = SettingsScreen(window)
                elif screen_type == ScreenType.COIN_FLIP:
                    screen = CoinFlipScreen(window)
                elif screen_type == ScreenType.DRAFT:
                    screen = DraftScreen(window)
                elif screen_type == ScreenType.JACK_REVEAL:
                    screen = JackRevealScreen(window)
                elif screen_type == ScreenType.GAME_OVER:
                    screen = GameOverScreen(window)
                elif screen_type == ScreenType.GAME:
                    screen = game_screen
                else:
                    raise ValueError(f"Unknown screen type: {screen_type}")

                if screen is None:
                    raise RuntimeError(f"Screen {screen_type.value} is not ready to be created")

                screens[screen_type] = screen
                screen_manager.add_screen(screen_type, screen)
            return screens[screen_type]

        # Start with only the start screen so the browser can render immediately.
        ensure_screen(ScreenType.START)
        screen_manager.set_screen(ScreenType.START)
        _set_web_status("Rendering start screen...")

        print("=" * 60)
        print("PAN'S TRIAL - PART 2: INTERACTIVE GAMEPLAY")
        print("=" * 60)
        print("Click 'Start Game' to begin the draft")
        print("Draft Satyrs, Oracles, and 2 Heroes before the labyrinth begins")
        print("The Omen reveal runs automatically before gameplay starts")
        print("=" * 60)

        running = True
        while running:
            # Handle events
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False

                elif event.type in (pygame.VIDEORESIZE, pygame.WINDOWSIZECHANGED):
                    if hasattr(event, "size"):
                        resized = window.resize(*event.size)
                    else:
                        resized = window.resize(*window.screen.get_size())
                    if resized:
                        screen_manager.handle_resize()
                
                window.ui_manager.process_events(event)
                
                result = screen_manager.handle_events(event)
                
                # Handle screen transitions
                if result == "PLAY":
                    labyrinth_cards, draft_cards, jack_cards = setup_pregame_cards()
                    pregame_setup = {
                        "labyrinth_cards": labyrinth_cards,
                        "draft_cards": draft_cards,
                        "jack_cards": jack_cards,
                        "hands": ([], []),
                        "player_cards": [],
                        "draft_starting_player": choice([0, 1]),
                        "starting_player": 1,
                    }
                    coin_flip_screen = ensure_screen(ScreenType.COIN_FLIP)
                    coin_flip_screen.start_flip(pregame_setup["draft_starting_player"])
                    screen_manager.set_screen(ScreenType.COIN_FLIP)

                elif result == "HOW_TO_PLAY":
                    ensure_screen(ScreenType.HOW_TO_PLAY)
                    screen_manager.set_screen(ScreenType.HOW_TO_PLAY)

                elif result == "SETTINGS":
                    ensure_screen(ScreenType.SETTINGS)
                    screen_manager.set_screen(ScreenType.SETTINGS)

                elif result == "RESIZED":
                    screen_manager.handle_resize()

                elif result == "DRAFT_COMPLETE":
                    draft_screen = ensure_screen(ScreenType.DRAFT)
                    p0_hand, p1_hand, player_cards = draft_screen.get_draft_result()
                    pregame_setup["hands"] = (p0_hand, p1_hand)
                    pregame_setup["player_cards"] = player_cards
                    jack_reveal_screen = ensure_screen(ScreenType.JACK_REVEAL)
                    jack_reveal_screen.start_reveal(pregame_setup["jack_cards"], player_cards)
                    screen_manager.set_screen(ScreenType.JACK_REVEAL)
                
                elif result == "MENU":
                    screen_manager.set_screen(ScreenType.START)

                elif result == "QUIT":
                    running = False
            
            # Update
            dt = window.clock.tick(window.FPS) / 1000.0
            screen_manager.update(dt)
            window.ui_manager.update(dt)

            if screen_manager.current_screen == ScreenType.JACK_REVEAL:
                jack_reveal_screen = screens.get(ScreenType.JACK_REVEAL)
                jack_order = jack_reveal_screen.consume_result()
                if jack_order is not None and pregame_setup is not None:
                    p0_hand, p1_hand = pregame_setup["hands"]
                    game = initialize_game(
                        pregame_setup["labyrinth_cards"],
                        p0_hand,
                        p1_hand,
                        jack_order,
                        pregame_setup["starting_player"],
                    )
                    if game_screen is None:
                        game_screen = GameScreen(window, game)
                        window.game_screen_ref = game_screen
                        screens[ScreenType.GAME] = game_screen
                        screen_manager.add_screen(ScreenType.GAME, game_screen)
                    else:
                        game_screen.game = game
                    screen_manager.set_screen(ScreenType.GAME)

            elif screen_manager.current_screen == ScreenType.COIN_FLIP:
                coin_flip_screen = screens.get(ScreenType.COIN_FLIP)
                draft_starting_player = coin_flip_screen.consume_result()
                if draft_starting_player is not None and pregame_setup is not None:
                    draft_screen = ensure_screen(ScreenType.DRAFT)
                    draft_screen.start_draft(
                        pregame_setup["draft_cards"],
                        starting_player=draft_starting_player,
                    )
                    screen_manager.set_screen(ScreenType.DRAFT)
            
            # Render
            window.screen.blit(window.background, (0, 0))
            screen_manager.render(window.screen)
            window.ui_manager.draw_ui(window.screen)
            pygame.display.flip()

            if IS_WEB and not first_frame_drawn:
                _mark_web_ready()
                first_frame_drawn = True
            
            # Check game over
            if (
                game is not None
                and screen_manager.current_screen == ScreenType.GAME
                and game.check_game_over()
            ):
                print(f"\nGAME OVER! Player {game.winner + 1} wins!")
                print(f"Final damage - P1: {game.get_damage_total(0)}, P2: {game.get_damage_total(1)}")
                game_over_screen = ensure_screen(ScreenType.GAME_OVER)
                game_over_screen.set_result(
                    game.winner,
                    game.get_damage_total(0),
                    game.get_damage_total(1),
                    game.get_match_summary(),
                )
                screen_manager.set_screen(ScreenType.GAME_OVER)

            if IS_WEB:
                # Yield once per frame so pygbag can keep the browser event loop responsive.
                await asyncio.sleep(0)
    
    except KeyboardInterrupt:
        print("\nGame interrupted by user.")
    except Exception:
        error_text = traceback.format_exc()
        print(error_text)
        _show_web_error(error_text)
        raise
    finally:
        if window is not None:
            window.quit()
        print("Game closed.")


def _run_desktop_main() -> None:
    """Start the async main loop on regular desktop Python."""
    run_async = getattr(asyncio, "run")
    run_async(main())


if IS_WEB:
    _set_web_status("Pan's Trial Python loaded...")

if IS_WEB or __name__ == "__main__":
    asyncio.run(main())
