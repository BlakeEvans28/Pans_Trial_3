"""
Pan's Trial - Main entry point with screen management.
Initializes game and runs the game loop.
"""

import sys
from random import shuffle
import pygame
from engine import GameState, GamePhase, Position
from ui import (
    GameWindow,
    ScreenManager,
    ScreenType,
    StartScreen,
    DraftScreen,
    JackRevealScreen,
    GameOverScreen,
    GameScreen,
)
from deck_utils import setup_pregame_cards, create_6x6_labyrinth


def initialize_game(
    labyrinth_cards: list,
    p0_hand: list,
    p1_hand: list,
    jack_order: list,
    starting_player: int = 1,
) -> GameState:
    """Initialize a new game from the completed pregame setup."""
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


def main():
    """Main game loop with screens."""
    # Initialize window
    window = GameWindow()
    screen_manager = ScreenManager(window)
    
    # Create screens
    start_screen = StartScreen(window)
    draft_screen = DraftScreen(window)
    jack_reveal_screen = JackRevealScreen(window)
    game_over_screen = GameOverScreen(window)
    game = None
    game_screen = None
    pregame_setup = None
    
    # Add screens to manager
    screen_manager.add_screen(ScreenType.START, start_screen)
    screen_manager.add_screen(ScreenType.DRAFT, draft_screen)
    screen_manager.add_screen(ScreenType.JACK_REVEAL, jack_reveal_screen)
    screen_manager.add_screen(ScreenType.GAME_OVER, game_over_screen)
    
    # Start with start screen (this will hide game screen elements)
    screen_manager.set_screen(ScreenType.START)
    
    print("=" * 60)
    print("PAN'S TRIAL - PART 2: INTERACTIVE GAMEPLAY")
    print("=" * 60)
    print("Click 'Start Game' to begin the draft")
    print("Draft Satyrs, Oracles, and 2 Heroes before the labyrinth begins")
    print("The Omen reveal runs automatically before gameplay starts")
    print("=" * 60)
    
    try:
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
                        "jack_cards": jack_cards,
                        "hands": ([], []),
                        "player_cards": [],
                        "starting_player": 1,
                    }
                    draft_screen.start_draft(draft_cards)
                    screen_manager.set_screen(ScreenType.DRAFT)

                elif result == "DRAFT_COMPLETE":
                    p0_hand, p1_hand, player_cards = draft_screen.get_draft_result()
                    pregame_setup["hands"] = (p0_hand, p1_hand)
                    pregame_setup["player_cards"] = player_cards
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
                        screen_manager.add_screen(ScreenType.GAME, game_screen)
                    else:
                        game_screen.game = game
                    screen_manager.set_screen(ScreenType.GAME)
            
            # Render
            window.screen.blit(window.background, (0, 0))
            screen_manager.render(window.screen)
            window.ui_manager.draw_ui(window.screen)
            pygame.display.flip()
            
            # Check game over
            if (
                game is not None
                and screen_manager.current_screen == ScreenType.GAME
                and game.check_game_over()
            ):
                print(f"\nGAME OVER! Player {game.winner + 1} wins!")
                print(f"Final damage - P1: {game.get_damage_total(0)}, P2: {game.get_damage_total(1)}")
                game_over_screen.set_result(
                    game.winner,
                    game.get_damage_total(0),
                    game.get_damage_total(1),
                )
                screen_manager.set_screen(ScreenType.GAME_OVER)
    
    except KeyboardInterrupt:
        print("\nGame interrupted by user.")
    finally:
        window.quit()
        print("Game closed.")


if __name__ == "__main__":
    main()
