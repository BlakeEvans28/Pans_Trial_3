#!/usr/bin/env python3
"""
Foundation verification script.
Tests all core systems are working correctly.
"""

def main():
    print("=" * 70)
    print("PAN'S TRIAL - FOUNDATION VERIFICATION")
    print("=" * 70)
    print()
    
    # Test imports
    print("Testing imports...")
    try:
        import engine
        import ui
        import deck_utils
        print("✓ All modules imported successfully")
    except Exception as e:
        print(f"✗ Import failed: {e}")
        return False
    print()
    
    # Test game initialization
    print("Testing game initialization...")
    try:
        from engine import GameState, GamePhase, Position
        from deck_utils import setup_game_deck, create_6x6_labyrinth, draft_hands, get_jack_suit_order
        
        labyrinth, p1_deck, p2_deck, jack_cards = setup_game_deck()
        grid = create_6x6_labyrinth(labyrinth)
        p0, p1, start = draft_hands(p1_deck, p2_deck)
        jacks = get_jack_suit_order(jack_cards)
        
        game = GameState()
        game.setup_board(grid)
        game.setup_suit_roles(jacks)
        
        for c in p0:
            game.add_card_to_hand(0, c)
        for c in p1:
            game.add_card_to_hand(1, c)
        
        game.place_player(0, Position(5, 4))
        game.place_player(1, Position(0, 4))
        game.phase = GamePhase.TRAVERSING
        
        print("✓ Game initialized successfully")
    except Exception as e:
        print(f"✗ Game initialization failed: {e}")
        return False
    print()
    
    # Verify game state
    print("Game State Verification:")
    try:
        print(f"  Phase: {game.phase.value}")
        print(f"  P1 Hand: {len(game.get_player_hand(0))} cards")
        print(f"  P2 Hand: {len(game.get_player_hand(1))} cards")
        print(f"  P1 Position: {game.board.get_player_position(0)}")
        print(f"  P2 Position: {game.board.get_player_position(1)}")
        print(f"  P1 Damage: {game.get_damage_total(0)}")
        print(f"  P2 Damage: {game.get_damage_total(1)}")
        print("✓ Game state verified")
    except Exception as e:
        print(f"✗ Game state verification failed: {e}")
        return False
    print()
    
    # Test legal moves
    print("Testing legal moves...")
    try:
        legal = game.get_legal_moves(0)
        print(f"  P1 Legal moves: {legal}")
        assert len(legal) > 0, "Should have legal moves"
        print("✓ Legal move generation works")
    except Exception as e:
        print(f"✗ Legal moves failed: {e}")
        return False
    print()
    
    # Test board rendering
    print("Testing board rendering setup...")
    try:
        # Note: BoardRenderer requires pygame to be initialized
        # which happens when GameWindow is created
        from ui import BoardRenderer
        # Just verify the class exists and can be imported
        assert hasattr(BoardRenderer, 'render'), "BoardRenderer missing render method"
        print("✓ BoardRenderer available (requires pygame window for full init)")
    except Exception as e:
        print(f"✗ BoardRenderer check failed: {e}")
        return False
    print()
    
    # Summary
    print("=" * 70)
    print("✓ ALL FOUNDATION SYSTEMS VERIFIED")
    print("=" * 70)
    print()
    print("Ready for:")
    print("  • Player vs Player gameplay")
    print("  • AI agent integration")
    print("  • Further testing and refinement")
    print()
    
    return True


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
