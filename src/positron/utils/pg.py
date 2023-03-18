"""
Utilities for all kinds of needs (funcs, regex, etc...) 

This module should slowly be dissolved into utils sub modules
"""

from contextlib import contextmanager
import numpy as np
import pygame as pg

# fmt: off
from positron.types import Color, ColorValue, Coordinate, Font, Rect, Surface, Vector2

# fmt: on

############################# Pygame related #############################

pg.init()


def draw_rect(surf: Surface, color: ColorValue, rect: Rect, **kwargs):
    """
    Draws a better rect than default pygame (handles transparent colors)
    """
    surf.blit(get_rect(rect, color, **kwargs), rect)


def get_rect(rect: Rect, color: ColorValue, **kwargs):
    color = Color(color)
    drawn_rect = Surface(rect.size)
    drawn_rect.fill(color)
    if color.a != 255:
        drawn_rect.set_alpha(color.a)
    return drawn_rect


def surf_opaque(surf: Surface) -> bool:
    """
    Returns whether the given Surface is fully opaque
    """
    return bool(np.all(pg.surfarray.array_alpha(surf) == 255))


def text_surf(text: str, font: Font, color: Color):
    color = Color(color)
    text_surf = font.render(text, True, color)
    if color.a != 255:
        text_surf.set_alpha(color.a)
    return text_surf


def draw_text(surf: Surface, text: str, font: Font, color, **kwargs):
    color = Color(color)
    if color.a:
        text_surf = font.render(text, True, color)
        dest = text_surf.get_rect(**kwargs)
        if color.a != 255:
            text_surf.set_alpha(color.a)
        surf.blit(text_surf, dest)


class Dotted:
    def __init__(
        self,
        dim,
        color,
        dash_size: int = 10,
        dash_width: int = 2,
        start_pos: Coordinate = (0, 0),
    ):
        self.dim = Vector2(dim)
        self.color = Color(color)
        self.dash_size = dash_size
        self.dash_width = dash_width
        self.start_pos = Vector2(start_pos)

    @classmethod
    def from_rect(cls, rect: Rect, **kwargs):
        return cls(rect.size, **kwargs, start_pos=rect.topleft)

    def draw_at(self, surf: Surface, pos):
        pos = Vector2(pos)
        vec = self.dim.normalize() * self.dash_size
        for i in range(int(self.dim.length() // self.dash_size // 2)):
            _pos = pos + vec * i * 2
            pg.draw.line(surf, self.color, _pos, _pos + vec, self.dash_width)

    def draw(self, surf: Surface):
        return self.draw_at(surf, self.start_pos)

    def draw_rect(self, surf: Surface):
        rect = Rect(*self.start_pos, *self.dim)
        for line in rect.sides:
            pos = Vector2(line[0])
            dim = line[1] - pos
            Dotted(dim, self.color, self.dash_size, self.dash_width, pos).draw(surf)


def draw_lines(surf: Surface, points, *args, **kwargs):
    points = [Vector2(point) for point in points]
    dlines = [
        Dotted(points[i + 1] - points[i], *args, **kwargs, start_pos=points[i])  # type: ignore
        for i in range(len(points) - 1)
    ]
    for dline in dlines:
        dline.draw(surf)


@contextmanager
def surf_clip(surf: Surface, clip: Rect):
    """
    Sets the surfaces clip in a context manager.
    """
    original_clip = surf.get_clip()
    surf.set_clip(clip)
    try:
        yield
    finally:
        surf.set_clip(original_clip)
