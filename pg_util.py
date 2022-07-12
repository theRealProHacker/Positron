from contextlib import suppress
import pygame as pg
import pygame.freetype as freetype

pg.init()

def draw_text(
    surf: pg.surface.Surface,
    text:str,
    fontname:str|None,
    size:int,
    color,
    **kwargs
):
    font = freetype.SysFont(fontname, size)
    color = pg.Color(color)
    dest = font.get_rect(str(text))
    for k,val in kwargs.items():
        with suppress(AttributeError):
            setattr(dest, k, val)
    font.render_to(surf, dest=dest, fgcolor = color)

class Dotted:
    def __init__(
        self,
        dim,
        color,
        dash_size: float = 10,
        dash_width: float = 2,
        start_pos = (0,0)
    ):
        self.dim = pg.Vector2(dim)
        self.color = pg.Color(color)
        self.dash_size = dash_size
        self.dash_width = dash_width
        self.start_pos = pg.Vector2(start_pos)
    
    @classmethod
    def from_rect(cls, rect: pg.rect.Rect, **kwargs):
        return cls(rect.size, **kwargs, start_pos = rect.topleft)

    def draw_at(self, surf: pg.surface.Surface, pos):
        pos = pg.Vector2(pos)
        vec = self.dim.normalize()*self.dash_size
        for i in range(int(self.dim.length()//self.dash_size//2)):
            _pos = pos + vec*i*2
            pg.draw.line(
                surf,
                self.color,
                _pos,
                _pos + vec,
                self.dash_width
            )

    def draw(self, surf):
        return self.draw_at(surf, self.start_pos)

    def draw_rect(self, surf):
        start = self.start_pos
        end = start + self.dim
        x,y = self.dim
        for pos, dim in [
            (start,(0, y)), # left
            (start,(x, 0)), # top
            (end, (-x, 0)), # bottom
            (end, (0, -y)), # right
        ]:
            Dotted(dim, self.color, self.dash_size, self.dash_width, pos)\
                .draw(surf)


def draw_lines(surf: pg.surface.Surface, points, *args, **kwargs):
    points = [pg.Vector2(point) for point in points]
    lines = [
        Dotted(points[i+1]-points[i], *args, **kwargs, start_pos=points[i])
        for i in range(len(points)-1)
    ]
    for line in lines:
        line.draw(surf)