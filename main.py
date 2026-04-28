"""
Pan's Trial - Main entry point with screen management.
Initializes game and runs the game loop.
"""

import sys
import pygame
from engine import GamePhase
from game_setup import initialize_game
from multiplayer import LocalRoomClient
from ui import (
    GameWindow,
    ScreenManager,
    ScreenType,
    StartScreen,
    RoomSelectionScreen,
    HowToPlayScreen,
    SettingsScreen,
    CoinFlipScreen,
    DraftScreen,
    JackRevealScreen,
    GameOverScreen,
    GameScreen,
)


def main():
    """Main game loop with screens."""
    # Initialize window
    window = GameWindow()
    screen_manager = ScreenManager(window)
    multiplayer_client = LocalRoomClient()
    
    # Create screens
    start_screen = StartScreen(window)
    room_screen = RoomSelectionScreen(window, multiplayer_client)
    how_to_play_screen = HowToPlayScreen(window)
    settings_screen = SettingsScreen(window)
    coin_flip_screen = CoinFlipScreen(window)
    draft_screen = DraftScreen(window)
    jack_reveal_screen = JackRevealScreen(window)
    game_over_screen = GameOverScreen(window)
    game = None
    game_screen = None
    pregame_setup = None
    
    # Add screens to manager
    screen_manager.add_screen(ScreenType.START, start_screen)
    screen_manager.add_screen(ScreenType.ROOM_SELECT, room_screen)
    screen_manager.add_screen(ScreenType.HOW_TO_PLAY, how_to_play_screen)
    screen_manager.add_screen(ScreenType.SETTINGS, settings_screen)
    screen_manager.add_screen(ScreenType.COIN_FLIP, coin_flip_screen)
    screen_manager.add_screen(ScreenType.DRAFT, draft_screen)
    screen_manager.add_screen(ScreenType.JACK_REVEAL, jack_reveal_screen)
    screen_manager.add_screen(ScreenType.GAME_OVER, game_over_screen)
    
    # Start with start screen (this will hide game screen elements)
    screen_manager.set_screen(ScreenType.START)
    
    print("=" * 60)
    print("PAN'S TRIAL - PART 2: INTERACTIVE GAMEPLAY")
    print("=" * 60)
    print("Click 'Start Game' to open the localhost room screen")
    print("Two players must enter the same room code before the match begins")
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
                
                active_screen = screen_manager.current_screen
                result = screen_manager.handle_events(event)
                
                # Handle screen transitions
                if result == "PLAY":
                    if active_screen in {ScreenType.START, ScreenType.GAME_OVER}:
                        room_screen.prepare_for_new_session()
                        screen_manager.set_screen(ScreenType.ROOM_SELECT)

                elif result == "HOW_TO_PLAY":
                    screen_manager.set_screen(ScreenType.HOW_TO_PLAY)

                elif result == "SETTINGS":
                    screen_manager.set_screen(ScreenType.SETTINGS)

                elif result == "RESIZED":
                    screen_manager.handle_resize()

                elif result == "DRAFT_COMPLETE":
                    p0_hand, p1_hand, player_cards = draft_screen.get_draft_result()
                    pregame_setup["hands"] = (p0_hand, p1_hand)
                    pregame_setup["player_cards"] = player_cards
                    jack_reveal_screen.start_reveal(pregame_setup["jack_cards"], player_cards)
                    screen_manager.set_screen(ScreenType.JACK_REVEAL)
                
                elif result == "MENU":
                    if active_screen in {ScreenType.ROOM_SELECT, ScreenType.GAME_OVER}:
                        multiplayer_client.close()
                    screen_manager.set_screen(ScreenType.START)

                elif result == "QUIT":
                    running = False
            
            # Update
            dt = window.clock.tick(window.FPS) / 1000.0
            screen_manager.update(dt)
            window.ui_manager.update(dt)

            for message in multiplayer_client.poll_messages():
                message_type = message.get("type")
                if message_type in {"room_joined", "room_update", "error", "room_closed", "disconnected"}:
                    room_screen.apply_network_message(message)
                    if message_type in {"room_closed", "disconnected"} and screen_manager.current_screen == ScreenType.GAME:
                        room_screen.status_message = message.get("message", room_screen.status_message)
                        screen_manager.set_screen(ScreenType.ROOM_SELECT)
                    continue

                if message_type == "game_start":
                    room_screen.apply_network_message(message)
                    game = message["game_state"]
                    if game_screen is None:
                        game_screen = GameScreen(
                            window,
                            game,
                            local_player_id=multiplayer_client.player_id,
                            network_client=multiplayer_client,
                        )
                        window.game_screen_ref = game_screen
                        screen_manager.add_screen(ScreenType.GAME, game_screen)
                    else:
                        game_screen.local_player_id = multiplayer_client.player_id
                        game_screen.network_client = multiplayer_client
                        game_screen.sync_game_state(game)
                    screen_manager.set_screen(ScreenType.GAME)
                    continue

                if message_type == "game_state" and game_screen is not None:
                    game = message["game_state"]
                    game_screen.sync_game_state(game, notice=message.get("notice"))

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

            elif screen_manager.current_screen == ScreenType.COIN_FLIP:
                draft_starting_player = coin_flip_screen.consume_result()
                if draft_starting_player is not None and pregame_setup is not None:
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
            
            # Check game over
            if game is None or screen_manager.current_screen != ScreenType.GAME:
                continue

            if game_screen is not None and game_screen.is_networked_match():
                game_over = game.phase == GamePhase.GAME_OVER and game.winner is not None
            else:
                game_over = game.check_game_over()

            if game_over:
                print(f"\nGAME OVER! Player {game.winner + 1} wins!")
                print(f"Final damage - P1: {game.get_damage_total(0)}, P2: {game.get_damage_total(1)}")
                game_over_screen.set_result(
                    game.winner,
                    game.get_damage_total(0),
                    game.get_damage_total(1),
                    game.get_match_summary(),
                )
                screen_manager.set_screen(ScreenType.GAME_OVER)
    
    except KeyboardInterrupt:
        print("\nGame interrupted by user.")
    finally:
        multiplayer_client.close()
        window.quit()
        print("Game closed.")


if __name__ == "__main__":
    main()
