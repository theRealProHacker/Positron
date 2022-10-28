"""
A contextmenu is what pops up, when you right click on something
"""
from dataclasses import dataclass
import pygame as pg
from typing import Literal
from own_types import Coordinate, Rect, Surface, Font
from util import draw_text

Orientation = Literal["vertical", "horizontal"]


DEF_FONT: Font = pg.font.SysFont("Arial", 16)


class MenuElement:
    w: int
    h: int
    def draw(self, surf: Surface, pos: Coordinate):
        ...


@dataclass
class Divider(MenuElement):
    length: int = 300
    width: int = 1
    orient: Literal["vertical", "horizontal"] = "vertical"

    @property
    def w(self):
        return self.length if self.orient == "vertical" else self.width

    @property
    def h(self):
        return self.length if self.orient == "horizontal" else self.width

    def draw(self, surf: Surface, pos: Coordinate):
        rect = Rect(pos, (self.w, self.h))
        pg.draw.rect(surf, "black", rect)


@dataclass
class Text(MenuElement):
    text: str
    w: int = 300
    h: int = 20

    def draw(self, surf: Surface, pos: Coordinate):
        draw_text(surf, self.text, DEF_FONT, "black", topleft=pos)


class ContextMenu(list[MenuElement]):
    """
    A ContextMenu is a list of MenuElements
    """

    # TODO: investigate native windows/linux/max contextmenus
    # TODO: What is the default width of a context-menu?

    rect: Rect

    def __init__(self, val):
        super().__init__(val)
        self.rect = Rect((0, 0), (300, sum(item.h for item in self)))

    def fit_into_rect(self, rect: Rect, pos: Coordinate):
        """
        Tries to fit this contextmenu into a rect at pos
        """
        w, h = self.rect.size
        x, y = pos
        down = y + h <= rect.bottom or y - h < rect.top
        kwargs = {"top" if down else "bottom": y, "left": x}
        print(kwargs)
        self.set_rect(**kwargs)
        self.rect.right = min(self.rect.right, rect.right)

    def set_rect(self, **kwargs):
        """
        Example: `set_rect(top=100)`
        """
        for k, v in kwargs.items():
            setattr(self.rect, k, v)

    def draw(self, surf: Surface):
        pg.draw.rect(surf, "black", self.rect, width=1)
        x, y = self.rect.topleft
        for item in self:
            item.draw(surf, (x, y))
            y += item.h
