"""
Utilities for drawing themed color-family markers without relying on font glyph support.
"""

import pygame
from engine import CardSuit
from pan_theme import get_family_code, get_family_color


def draw_suit_icon(
    surface: pygame.Surface,
    suit: CardSuit,
    center: tuple[int, int],
    size: int = 12,
    color: tuple[int, int, int] | None = None,
) -> None:
    """Draw one themed family marker as a colored token with a short code."""
    from pathlib import Path
    
    center_x, center_y = center
    radius = max(6, size)
    fill = color if color is not None else get_family_color(suit)
    border = (235, 235, 235)

    pygame.draw.circle(surface, fill, (center_x, center_y), radius)
    pygame.draw.circle(surface, border, (center_x, center_y), radius, 2)

    font_size = max(12, size + 4)
    # Try to use MedievalSharp from assets, fall back to default
    asset_root = Path(__file__).resolve().parent.parent / "assets"
    medieval_sharp_path = asset_root / "MedievalSharp.ttf"
    if medieval_sharp_path.exists():
        font = pygame.font.Font(str(medieval_sharp_path), font_size)
    else:
        font = pygame.font.Font(None, font_size)
    text = font.render(get_family_code(suit), True, (25, 25, 25))
    text_rect = text.get_rect(center=(center_x, center_y + 1))
    surface.blit(text, text_rect)
