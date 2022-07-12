
from abc import ABC, abstractmethod
from numbers import Number

from own_types import NumTuple4, Dimension, Percentage

from pygame.rect import Rect

@ABC
class Box:
    x: Number
    y: Number
    def __init__(
        self,
        pos: Dimension,
        margin: NumTuple4,
        border: NumTuple4,
        padding: NumTuple4,
        size: Dimension
    ):
        self.x, self.y = pos
        self.margin = margin
        self.border = border
        self.padding = padding
        self.width, self.height = size # we want to activate the width and height properties of the subclasses

    # margin
    @property
    def margin(self):
        return self._mt, self._mb, self._mr, self._ml

    @margin.setter
    def _(self, margin: NumTuple4):
        self._mt, self._mb, self._mr, self._ml = margin

    # convenience
    @property
    def margin_horizontal(self)->Dimension:
        return self.margin[2:]

    @property
    def margin_vertical(self)->Dimension:
        return self.margin[:2]

    # border
    @property
    def border(self):
        return self._bt, self._bb, self._br, self._bl

    @border.setter
    def _(self, border: NumTuple4):
        self._bt, self._bb, self._br, self._bl = border

    # convenience
    @property
    def border_horizontal(self)->Dimension:
        return self.border[2:]

    @property
    def border_vertical(self)->Dimension:
        return self.border[:2]

    #padding
    @property
    def padding(self):
        return self._pt, self._pb, self._pr, self._pl

    @padding.setter
    def _(self, padding: NumTuple4):
        self._pt, self._pb, self._pr, self._pl = padding

    # convenience
    @property
    def padding_horizontal(self)->Dimension:
        return self.padding[2:]

    @property
    def padding_vertical(self)->Dimension:
        return self.padding[:2]

    #width
    @property
    def width(self)->Number:
        return self._width

    @width.setter
    def _(self, width: Number):
        self._width = width

    # height
    @property
    def height(self)->Number:
        return self._height

    @height.setter
    def _(self, height: Number):
        self._height = height

    # to be implemented
    @abstractmethod
    @property
    def margin_box(self)->Rect:
        ...

    @abstractmethod
    @property
    def border_box(self)->Rect:
        ...

    @abstractmethod
    @property
    def content_box(self)->Rect:
        ...

class ContentBox(Box):
    @property
    def margin_box(self): 
        width = self.width \
            + self.margin_horizontal \
            + self.border_horizontal \
            + self.padding_horizontal
        height = self.height \
            + self.margin_vertical \
            + self.border_vertical \
            + self.padding_vertical

        return Rect(
            self.x,
            self.y,
            width,
            height
        )

    @property
    def border_box(self):
        width = self.width \
            + self.border_horizontal \
            + self.padding_horizontal
        height = self.height \
            + self.border_vertical \
            + self.padding_vertical

        return Rect(
            self.x,
            self.y,
            width,
            height
        )

    @property
    def content_box(self):
        return Rect(
            self.x,
            self.y,
            self.width,
            self.height
        )

class BorderBox(Box):
    @property
    def margin_box(self):
        width = self.width + self.margin_horizontal
        height = self.height + self.margin_vertical

        return Rect(
            self.x,
            self.y,
            width,
            height
        )

    @property
    def border_box(self):
        return Rect(
            self.x,
            self.y,
            self.width,
            self.height
        )

    @property
    def content_box(self):
        width = self.width \
            - self.border_horizontal \
            - self.padding_horizontal
        height = self.height \
            - self.border_vertical \
            - self.padding_vertical
        return Rect(
            self.x,
            self.y,
            max(width,0),
            max(height,0)
        )

box_types: dict[str, Box] = {
    "content-box": ContentBox,
    "border-box": BorderBox,
}

str_Num_Perc = str|Number|Percentage
snp_box = tuple[str_Num_Perc, str_Num_Perc, str_Num_Perc, str_Num_Perc]

def make_box(
    box_sizing: str,
    x: Number,
    y: Number,
    margin: snp_box,
    border: NumTuple4,
    padding: snp_box,
    

)->Box:
    """
    Makes a box from input

    Returns a Box

    Raises KeyError if box_sizing is not valid

    """
    box = box_types[box_sizing]
    return box(
        (x,y),

    )