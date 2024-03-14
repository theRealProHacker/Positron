"""
Components are small drawables that can be used all over the place
"""

from dataclasses import dataclass

from pygame.sprite import Sprite

from positron.types import Color, ColorValue, Rect, Surface, Vector2
from positron.utils import draw_line, draw_polygon


class Component(Sprite):
    rect: Rect


@dataclass
class PlayButton(Component):
    """
    A classical Play(▶)/Pause(⏸)-Button
    """

    playing: bool = True
    color: ColorValue = Color("black")

    # config
    paused_line_width = 5

    def __post_init__(self):
        self.rect = Rect((0, 0, 50, 50))

    def draw(self, surf: Surface):
        if self.playing:
            # draw two lines in the center of the rect
            height = self.rect.height
            distance = max(10, self.rect.width)
            draw_line(
                surf,
                self.color,
                Vector2(distance / 2, height / 2) + self.rect.center,
                Vector2(distance / 2, -height / 2) + self.rect.center,
                self.paused_line_width,
            )
            draw_line(
                surf,
                self.color,
                Vector2(-distance / 2, height / 2) + self.rect.center,
                Vector2(-distance / 2, -height / 2) + self.rect.center,
                self.paused_line_width,
            )
        else:
            r = min(self.rect.width, self.rect.height) * 0.5
            vectors = (Vector2(), Vector2(), Vector2())
            for i, angle in enumerate((0, 120, 240)):
                vectors[i].from_polar((r, angle))
            draw_polygon(surf, self.color, [self.rect.center + v for v in vectors])
