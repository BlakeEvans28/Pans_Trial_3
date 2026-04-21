"""
Pygame window and rendering setup for Pan's Trial UI.
"""

import pygame
import pygame_gui
from typing import Optional


class GameWindow:
    """Main pygame window for Pan's Trial."""

    BASE_WINDOW_WIDTH = 1200
    BASE_WINDOW_HEIGHT = 900
    MIN_WINDOW_WIDTH = 390
    MIN_WINDOW_HEIGHT = 620
    SCREEN_MARGIN_X = 80
    SCREEN_MARGIN_Y = 120
    FPS = 60

    def __init__(self):
        """Initialize pygame window."""
        pygame.init()

        self.WINDOW_WIDTH, self.WINDOW_HEIGHT = self._get_initial_window_size()
        self.minimum_resize_width = min(self.MIN_WINDOW_WIDTH, self.WINDOW_WIDTH)
        self.minimum_resize_height = min(self.MIN_WINDOW_HEIGHT, self.WINDOW_HEIGHT)

        self.screen = pygame.display.set_mode(
            (self.WINDOW_WIDTH, self.WINDOW_HEIGHT),
            pygame.RESIZABLE,
        )
        pygame.display.set_caption("Pan's Trial")

        self.clock = pygame.time.Clock()
        self.running = True

        # UI Manager for pygame_gui
        self.ui_manager = pygame_gui.UIManager((self.WINDOW_WIDTH, self.WINDOW_HEIGHT))

        # Game state
        self.time_delta = 0
        self.background = pygame.Surface((self.WINDOW_WIDTH, self.WINDOW_HEIGHT))
        self._refresh_background()

    def _get_initial_window_size(self) -> tuple[int, int]:
        """Pick a starting size that fits on the current display."""
        display_info = pygame.display.Info()
        available_width = max(self.MIN_WINDOW_WIDTH, display_info.current_w - self.SCREEN_MARGIN_X)
        available_height = max(self.MIN_WINDOW_HEIGHT, display_info.current_h - self.SCREEN_MARGIN_Y)

        width = min(self.BASE_WINDOW_WIDTH, available_width)
        height = min(self.BASE_WINDOW_HEIGHT, available_height)

        width = max(min(self.MIN_WINDOW_WIDTH, available_width), width)
        height = max(min(self.MIN_WINDOW_HEIGHT, available_height), height)
        return width, height

    def _refresh_background(self) -> None:
        """Rebuild the cached background surface for the current size."""
        self.background = pygame.Surface((self.WINDOW_WIDTH, self.WINDOW_HEIGHT))
        self.background.fill((20, 20, 30))

    def resize(self, width: int, height: int) -> bool:
        """Resize the window and UI manager. Returns True when size changed."""
        width = max(self.minimum_resize_width, int(width))
        height = max(self.minimum_resize_height, int(height))

        if (width, height) == (self.WINDOW_WIDTH, self.WINDOW_HEIGHT):
            return False

        self.WINDOW_WIDTH = width
        self.WINDOW_HEIGHT = height
        self.screen = pygame.display.set_mode((width, height), pygame.RESIZABLE)
        self.ui_manager.set_window_resolution((width, height))
        self._refresh_background()
        return True

    def get_scale(self) -> float:
        """Return the current UI scale relative to the original 1200x900 layout."""
        return min(
            self.WINDOW_WIDTH / self.BASE_WINDOW_WIDTH,
            self.WINDOW_HEIGHT / self.BASE_WINDOW_HEIGHT,
        )

    def get_layout_mode(self) -> str:
        """Return the current responsive layout bucket."""
        if self.WINDOW_WIDTH < 720 or self.WINDOW_HEIGHT < 680:
            return "compact"
        if self.WINDOW_WIDTH < 1020 or self.WINDOW_HEIGHT < 760:
            return "medium"
        return "wide"

    def is_compact_layout(self) -> bool:
        """Return True when the UI should favor phone-sized stacked layouts."""
        return self.get_layout_mode() == "compact"

    def scale(self, value: int, minimum: int = 1) -> int:
        """Scale an isotropic measurement using the current window size."""
        return max(minimum, int(round(value * self.get_scale())))

    def scale_x(self, value: int, minimum: int = 1) -> int:
        """Scale a horizontal measurement."""
        return max(minimum, int(round(value * self.WINDOW_WIDTH / self.BASE_WINDOW_WIDTH)))

    def scale_y(self, value: int, minimum: int = 1) -> int:
        """Scale a vertical measurement."""
        return max(minimum, int(round(value * self.WINDOW_HEIGHT / self.BASE_WINDOW_HEIGHT)))

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
