"""
Tests that should be executed and evaluated by a human in an interpreter
"""

from pygame import Surface
from pygame.image import save_extended
from positron.utils.fonts import FontStyle, Font


def get_fonts(l: list[str]):
    """
    Get a list of (CSS) font family names
    and gives a complete list of fonts that will be rendered
    """

    return Font(l, 12, FontStyle("normal"), 400).fonts


def draw_font(families, size, style: str, weight=400):
    text = input("Your Text:")
    surf = Surface((100, 100))
    surf.fill("white")
    Font(families, size, FontStyle(style), weight).draw(surf, (20, 30), text, "black")
    save_extended(surf, "test.png")
