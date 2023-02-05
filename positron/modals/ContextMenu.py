"""
A contextmenu is what pops up, when you right click on something
"""
from dataclasses import dataclass

import pygame as pg
import utils.Navigator
from own_types import Color, Coordinate, Enum, Font, Rect, Surface, Vector2
from util import draw_text


class Orient(Enum):
    vert = "vertical"
    hrzn = "horizontal"


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
    h: int = 3
    orient: Orient = Orient.hrzn

    @property
    def w(self):
        return self.length

    def draw(self, surf: Surface, pos: Coordinate):
        pg.draw.rect(surf, "grey", Rect(Vector2(0, 1) + pos, (self.w, self.width)))


@dataclass
class TextButton(MenuElement):
    text: str
    w: int = 300
    h: int = 30
    bgcolor: Color = Color("transparent")
    disabled: bool = False

    def draw(self, surf: Surface, pos: Coordinate):
        x, y = pos
        # XXX: transparent will draw as black
        if self.bgcolor != Color("transparent"):
            pg.draw.rect(surf, self.bgcolor, Rect(pos, (self.w, self.h)))
        draw_text(
            surf,
            self.text,
            DEF_FONT,
            "grey" if self.disabled else "black",
            midleft=(x + 20, y + self.h / 2),
        )

    def on_click(self):
        ...


class BackButton(TextButton):
    def __init__(self):
        super().__init__("Back")
        self.disabled = not utils.Navigator.history.can_go_back()

    def on_click(self):
        utils.Navigator.back()


class ForwardButton(TextButton):
    def __init__(self):
        super().__init__("Forward")
        self.disabled = not utils.Navigator.history.can_go_forward()

    def on_click(self):
        utils.Navigator.forward()


class ReloadButton(TextButton):
    def __init__(self):
        super().__init__("Reload")

    def on_click(self):
        utils.Navigator.reload()


class ContextMenu(list[MenuElement]):
    """
    A ContextMenu is a list of MenuElements
    """

    # TODO: investigate native windows/linux/mac contextmenus

    rect: Rect
    can_escape = True
    WIDTH = 300
    hover_elem = None

    def __init__(self, val):
        super().__init__(val)
        self.rect = Rect((0, 0), (self.WIDTH, sum(item.h for item in self) + 10))

    def get_hovered_elem(self, mouse_pos: Coordinate) -> MenuElement | None:
        _, mouse_y = mouse_pos
        _, y = self.rect.topleft
        for item in self:
            y += item.h
            if y > mouse_y:
                return item
        return None

    async def on_click(self):
        if isinstance(self.hover_elem, TextButton) and not self.hover_elem.disabled:
            self.hover_elem.on_click()

    def on_mousemove(self, event):
        hovered_elem = self.get_hovered_elem(event.pos)
        if hovered_elem is not self.hover_elem:
            if isinstance(self.hover_elem, TextButton):
                del self.hover_elem.bgcolor
            if isinstance(hovered_elem, TextButton):
                hovered_elem.bgcolor = Color("grey")
            self.hover_elem = hovered_elem

    def on_mouseleave(self):
        if isinstance(self.hover_elem, TextButton):
            del self.hover_elem.bgcolor
        self.hover_elem = None

    def fit_into_rect(self, rect: Rect, pos: Coordinate):
        """
        Tries to fit this contextmenu into a rect at pos

        We must put the context menu fully visible onto the screen
        """
        h = self.rect.height
        x, y = pos
        down = y + h <= rect.bottom or y - h < rect.top
        kwargs = {"top" if down else "bottom": y, "left": x}
        self.set_rect(**kwargs)
        self.rect.right = min(self.rect.right, rect.right)
        return self

    def set_rect(self, **kwargs):
        """
        Example: `set_rect(top=100)`
        """
        for k, v in kwargs.items():
            setattr(self.rect, k, v)

    def draw(self, surf: Surface):
        pg.draw.rect(surf, "white", self.rect, border_radius=5)
        pg.draw.rect(surf, "grey", self.rect, width=1)
        x, y = self.rect.topleft
        y += 5
        for item in self:
            item.draw(surf, (x, y))
            y += item.h
