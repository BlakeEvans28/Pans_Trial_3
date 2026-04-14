"""
Pygame window and rendering setup for Pan's Trial UI.
"""

import pygame
import pygame_gui
from pygame_gui.elements import UIButton
from typing import Optional, Callable


class GameWindow:
    """Main pygame window for Pan's Trial."""
    
    WINDOW_WIDTH = 1200
    WINDOW_HEIGHT = 900
    FPS = 60
    
    def __init__(self):
        """Initialize pygame window."""
        pygame.init()
        
        self.screen = pygame.display.set_mode((self.WINDOW_WIDTH, self.WINDOW_HEIGHT))
        pygame.display.set_caption("Pan's Trial")
        
        self.clock = pygame.time.Clock()
        self.running = True
        
        # UI Manager for pygame_gui
        self.ui_manager = pygame_gui.UIManager((self.WINDOW_WIDTH, self.WINDOW_HEIGHT))
        
        # Game state
        self.time_delta = 0
        self.background = pygame.Surface((self.WINDOW_WIDTH, self.WINDOW_HEIGHT))
        self.background.fill((20, 20, 30))  # Dark background

    def handle_events(self) -> bool:
        """
        Handle pygame events.
        Returns False if quit requested.
        """
        for event in pygame.event.get():
            self.ui_manager.process_events(event)
            
            if event.type == pygame.QUIT:
                return False
        
        return True

    def update(self, time_delta: float) -> None:
        """Update game state."""
        self.time_delta = time_delta
        self.ui_manager.update(time_delta)

    def render(self) -> None:
        """Render frame."""
        self.screen.blit(self.background, (0, 0))
        self.ui_manager.draw_ui(self.screen)
        pygame.display.flip()

    def tick(self) -> Optional[float]:
        """
        Tick clock and return time delta.
        Returns None if quit requested.
        """
        self.time_delta = self.clock.tick(self.FPS) / 1000.0
        
        if not self.handle_events():
            return None
        
        self.update(self.time_delta)
        self.render()
        
        return self.time_delta

    def quit(self) -> None:
        """Shutdown pygame."""
        pygame.quit()

    def set_background_color(self, color: tuple[int, int, int]) -> None:
        """Set background color."""
        self.background.fill(color)
