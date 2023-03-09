"""
Utils around fonts
"""

from dataclasses import dataclass, field
from functools import cached_property
from itertools import takewhile
from typing import Literal

import pygame as pg
from pygame.font import match_font, SysFont as _SysFont

from positron.config import generic_font_families
from positron.types import Color, ColorValue, Coordinate, Surface, Font as _Font
from positron.utils import log_error, log_error_once, draw_text, sum_tuples


@dataclass(frozen=True)
class FontStyle:
    value: Literal["normal", "italic", "oblique"]
    angle: float

    def __init__(
        self, value: Literal["normal", "italic", "oblique"], angle: str | None = None
    ):
        assert value in ("normal", "italic", "oblique")
        object.__setattr__(self, "value", value)
        object.__setattr__(self, "angle", 14 if angle is None else float(angle))


# registered_fonts: dict[str, ] = {}

font_cache: dict[tuple[str, int, FontStyle, bool], _Font] = {}


def find_font(family: str, size: float, style: FontStyle, weight: int) -> _Font | None:
    """
    Takes some font constraints and tries to find the most fitting (system) font.
    """
    size = int(size)
    bold = weight > 500
    cache_key = (family, size, style, bold)
    if font := font_cache.get(cache_key):
        return font
    italic = style.value == "italic"
    if family == "system-ui":
        font = _SysFont(None, size, bold=bold, italic=italic)  # type: ignore
    else:
        # if not (_font := registered_fonts.get(family)):
        #
        _font = match_font(family, bold=bold, italic=italic)
        if _font is None:
            log_error("Failed to find font", family, size, weight)
            return None
        font = _Font(_font, size)
    font.italic = style.value == "oblique"
    font_cache[cache_key] = font
    return font


"""
Metrics = tuple[int, int, int, int, int]

def valid_font(fonts: list[_Font], char: str) -> tuple[_Font, Metrics]:
    \"""
    Returns the first font from the list of fonts that can render the char.
    \"""
    assert fonts
    for font in fonts:
        if metrics := font.metrics(char)[0]:
            return (font, metrics)
    raise RuntimeError(f"No font could be found for {char}")
"""


def valid_font(fonts: list[_Font], char: str) -> _Font:
    """
    Returns the first font from the list of fonts that can render the char.
    """
    assert fonts
    for font in fonts:
        # TODO: this doesn't actually work
        if font.metrics(char)[0]:
            return font
    log_error_once(f"No font could be found for {char}")
    return fonts[-1]  # cheating
    raise RuntimeError(f"No font could be found for {char}")


# class Font:
#     whitespace: Metrics

#     @abstractmethod
#     def metrics(self, text: str) -> list[tuple[str, tuple[_Font, Metrics]]]:
#         ...


@dataclass()
class Font:
    """
    A CSS Font
    """

    families: list[str]
    _size: float
    _style: FontStyle
    _weight: int
    color: ColorValue
    fonts: list[_Font] = field(default_factory=list)

    def __post_init__(self):
        families = []
        for fam in self.families:
            if new_fams := generic_font_families.get(fam):
                families += new_fams
            else:
                families.append(fam)
        # fmt: off
        families += [
            "Segoe UI", "Berlin Sans FB", "Lucida Sans",
            "MS Reference Sans Serif", "Segoe UI Emoji"
        ]
        # fmt: on
        self.families[:], self.fonts[:] = zip(
            *(
                (fam, font)
                for fam in families
                if (font := find_font(fam, self._size, self._style, self._weight))
                is not None
            )
        )
        self.color = Color(self.color)

    def _fonts_for_chars(self, text: str):
        i = 0
        while i < len(text):
            c = text[i]
            font = valid_font(self.fonts, c)
            string = c + "".join(
                takewhile(lambda c: valid_font(self.fonts, c) == font, text[i + 1 :])
            )
            i += len(string)
            yield string, font

    @cached_property
    def linesize(self):
        return self.fonts[0].get_linesize()

    def size(self, text: str):
        return sum_tuples(
            font.size(substr) for substr, font in self._fonts_for_chars(text)
        ) or (0, 0)

    def draw(self, surf: Surface, pos: Coordinate, text: str):
        x, y = pos
        for sub, font in self._fonts_for_chars(text):
            draw_text(surf, sub, font, self.color, topleft=(x, y))
            x += font.size(sub)[0]

    def render(self, text: str) -> Surface:
        surf = Surface(self.size(text), flags=pg.SRCALPHA)
        surf.fill("transparent")
        self.draw(surf, (0, 0), text)
        return surf
