"""
A contextmenu is what pops up, when you right click
"""
from own_types import Rect, Surface


class MenuElement:
    width: int
    height: int


class ContextMenu(list[MenuElement]):
    """
    The ContextMenu is a list of MenuElements
    """

    rect: Rect
    w: int

    @property
    def h(self):
        return sum(item.height for item in self)

    def set_rect(self, **kwargs):
        """
        Example: `set_rect(top=100)`
        """
        for k, v in kwargs:
            setattr(self.rect, k, v)

    def draw(self, surf: Surface):
        pass
