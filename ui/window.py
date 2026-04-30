"""
Pygame window and rendering setup for Pan's Trial UI.
"""

import sys
import warnings
import pygame
import pygame_gui
from typing import Optional
from pygame_gui.core.gui_font_freetype import GUIFontFreetype
from pygame_gui.core.gui_font_pygame import GUIFontPygame
from pygame_gui.core.package_resource import PackageResource
from pygame_gui.core.resource_loaders import IResourceLoader
from pygame_gui.core.utility import FontResource, ImageResource

from .audio_manager import AudioManager

_WEB_PYGAME_GUI_RESOURCE_PATCHED = False


class SequentialResourceLoader(IResourceLoader):
    """Web-safe pygame_gui loader that avoids background Python threads."""

    def __init__(self) -> None:
        self._resources = []
        self._started = False

    def add_resource(self, resource) -> None:
        if self._started:
            raise ValueError("Too late to add this resource to the loader")
        self._resources.append(resource)

    def start(self) -> None:
        self._started = True

    def update(self) -> tuple[bool, float]:
        while self._resources:
            resource = self._resources.pop(0)
            error = resource.load()
            if error is not None:
                warnings.warn(str(error))
        return True, 1.0

    def started(self) -> bool:
        return self._started


def _patch_pygame_gui_resources_for_web() -> None:
    """Force pygame_gui package resources to load from real bundle paths on wasm."""
    global _WEB_PYGAME_GUI_RESOURCE_PATCHED

    if _WEB_PYGAME_GUI_RESOURCE_PATCHED or sys.platform != "emscripten":
        return

    def resolve_location(location):
        if isinstance(location, PackageResource):
            return location.to_path()
        return location

    def load_font_resource(self):
        error = None
        location = resolve_location(self.location)
        try:
            if isinstance(location, str):
                if self.font_type_to_use == "freetype":
                    self.loaded_font = GUIFontFreetype(
                        location, self.size, self.force_style, self.style
                    )
                else:
                    self.loaded_font = GUIFontPygame(
                        location, self.size, self.force_style, self.style
                    )
            else:
                return _original_font_load(self)
        except (pygame.error, OSError, RuntimeError):
            error = FileNotFoundError(f"Unable to load resource with path: {location}")
        return error

    def load_image_resource(self):
        error = None
        location = resolve_location(self.location)
        try:
            if isinstance(location, str):
                self.loaded_surface = pygame.image.load(location).convert_alpha()
            else:
                return _original_image_load(self)
        except (pygame.error, OSError, RuntimeError):
            error = FileNotFoundError(f"Unable to load resource with path: {location}")

        if (
            error is None
            and self.loaded_surface is not None
            and not self.is_file_premultiplied
        ):
            self.loaded_surface = self.loaded_surface.premul_alpha()

        return error

    _original_font_load = FontResource.load
    _original_image_load = ImageResource.load
    FontResource.load = load_font_resource
    ImageResource.load = load_image_resource
    _WEB_PYGAME_GUI_RESOURCE_PATCHED = True


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
        self.is_web = sys.platform == "emscripten"
        if self.is_web:
            _patch_pygame_gui_resources_for_web()
        self.supports_fullscreen_toggle = not self.is_web
        pygame.mixer.pre_init(44100, -16, 1, 512)
        pygame.init()

        self.WINDOW_WIDTH, self.WINDOW_HEIGHT = self._get_initial_window_size()
        self.minimum_resize_width = min(self.MIN_WINDOW_WIDTH, self.WINDOW_WIDTH)
        self.minimum_resize_height = min(self.MIN_WINDOW_HEIGHT, self.WINDOW_HEIGHT)
        self.windowed_size = (self.WINDOW_WIDTH, self.WINDOW_HEIGHT)
        self.fullscreen = False
        self.text_scale = 1.0
        self.animation_speed = 1.0
        self.sound_volume = 0.5
        self.tutorial_enabled = False
        self.audio = AudioManager()
        self.audio.set_volume(self.sound_volume)
        display_flags = 0 if self.is_web else pygame.RESIZABLE

        self.screen = pygame.display.set_mode(
            (self.WINDOW_WIDTH, self.WINDOW_HEIGHT),
            display_flags,
        )
        pygame.display.set_caption("Pan's Trial")

        self.clock = pygame.time.Clock()
        self.running = True

        # UI Manager for pygame_gui
        if self.is_web:
            self.ui_manager = pygame_gui.UIManager(
                (self.WINDOW_WIDTH, self.WINDOW_HEIGHT),
                resource_loader=SequentialResourceLoader(),
            )
        else:
            self.ui_manager = pygame_gui.UIManager((self.WINDOW_WIDTH, self.WINDOW_HEIGHT))

        # Game state
        self.time_delta = 0
        self.background = pygame.Surface((self.WINDOW_WIDTH, self.WINDOW_HEIGHT))
        self._refresh_background()

    def _get_initial_window_size(self) -> tuple[int, int]:
        """Pick a starting size that fits on the current display."""
        if self.is_web:
            return self.BASE_WINDOW_WIDTH, self.BASE_WINDOW_HEIGHT

        display_info = pygame.display.Info()
        current_w = display_info.current_w or self.BASE_WINDOW_WIDTH
        current_h = display_info.current_h or self.BASE_WINDOW_HEIGHT
        available_width = max(self.MIN_WINDOW_WIDTH, current_w - self.SCREEN_MARGIN_X)
        available_height = max(self.MIN_WINDOW_HEIGHT, current_h - self.SCREEN_MARGIN_Y)

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
        if self.fullscreen or self.is_web:
            return False

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

    def toggle_fullscreen(self) -> bool:
        """Toggle fullscreen mode and return True when the window size changed."""
        if not self.supports_fullscreen_toggle:
            return False

        self.fullscreen = not self.fullscreen
        if self.fullscreen:
            self.windowed_size = (self.WINDOW_WIDTH, self.WINDOW_HEIGHT)
            display_info = pygame.display.Info()
            self.WINDOW_WIDTH = display_info.current_w
            self.WINDOW_HEIGHT = display_info.current_h
            self.screen = pygame.display.set_mode((self.WINDOW_WIDTH, self.WINDOW_HEIGHT), pygame.FULLSCREEN)
        else:
            self.WINDOW_WIDTH, self.WINDOW_HEIGHT = self.windowed_size
            self.screen = pygame.display.set_mode((self.WINDOW_WIDTH, self.WINDOW_HEIGHT), pygame.RESIZABLE)

        self.ui_manager.set_window_resolution((self.WINDOW_WIDTH, self.WINDOW_HEIGHT))
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

    def font_size(self, value: int, minimum: int = 1) -> int:
        """Scale a font size using the current window and text-size setting."""
        return max(minimum, int(round(value * self.get_scale() * self.text_scale)))

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

    def reset_tutorial_tips(self) -> None:
        """Reset gameplay tip state without forcing tutorial tips back on."""
        game_screen = getattr(self, "game_screen_ref", None)
        if game_screen is not None and hasattr(game_screen, "reset_tutorial_cycle"):
            game_screen.reset_tutorial_cycle()
