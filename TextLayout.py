from dataclasses import dataclass
from numbers import Number
import pygame as pg
import re
from typing import Literal

font_split_regex = re.compile(r"\s*\,\s*")

def make_default(value, default):
    return default if value is None else value

class FontStyle:
    def __init__(self, value: Literal["normal", "italic", "oblique"], oblique_angle: float|None = None):
        self.value = value
        self.oblique_angle = make_default(oblique_angle, 14) if value == "oblique" else None

@dataclass
class TextDrawItem:
    text: str
    pos: tuple[int, int]

class TextLayout:
    def __init__(self, text: str):
        self.text = text.strip()
        self.draw_items: list[TextDrawItem] = []
    
    @staticmethod
    def get_font(family: str, size: Number, style: FontStyle, weight: int)->None|pg.font.Font:
        font = pg.font.match_font(
            name = font_split_regex.split(family), # this algorithm should be updated
            italic = style.value == "italic", 
            bold = weight >= 700 # we don't support actual weight TODO
        )
        if font is None:
            print("Failed to find font", family, style, weight)
        font = pg.font.Font(font, int(size))
        if style.value == "oblique": # we don't support oblique with an angle, we just fake the italic
            font.italic = True
        return font
    
    def layout(self, width: float):
        # info
        # with word-wrap but not between words if they are too long
        # https://stackoverflow.com/a/46220683/15046005
        # constants
        line_height = 1.5*14 # 1.5 is the factor to the font size. It should be premultiplied by the css algorithm before
        size = 16
        family = "Arial"
        weight = 400
        style = FontStyle("normal")
        word_spacing = "normal" # 3
        # code
        l = self.text.split()
        font = self.get_font(family, size, style, weight)
        self.font = font
        if word_spacing == "normal":
            word_spacing = font.size(" ")[0] # the width of the space character in the font
        if line_height == "normal":
            line_height = 1.2 * size
        xcursor = ycursor = 0.0
        self.draw_items.clear()
        for word in l:
            word_width, _ = font.size(word)
            if xcursor + word_width > width: #overflow
                xcursor = 0
                ycursor += line_height
            self.draw_items.append(TextDrawItem(word,(xcursor, ycursor)))
            xcursor += word_width + word_spacing

    def draw(self, screen: pg.surface.Surface, pos):
        x,y = pos
        color = "black"
        for draw_item in self.draw_items:
            surf = self.font.render(draw_item.text, True, color)
            x_off, y_off = draw_item.pos
            screen.blit(surf, (x+x_off, y+y_off))
        


if __name__ == "__main__":
    import util
    from config import g

    def main():
        pg.init()
        tl = TextLayout("Let's have some fun with text rendering!")
        W,H = DIM = util.Vec2((g["W"],g["H"]))
        screen = pg.display.set_mode(DIM)
        clock = pg.time.Clock()

        while True:
            for event in pg.event.get():
                if event.type == pg.QUIT:
                    return
                elif event.type == pg.MOUSEBUTTONDOWN:
                    return

            clock.tick(60)
            tl.layout(W-100)
            screen.fill("white")
            tl.draw(screen, (50,50))
            pg.display.flip()

    main()

