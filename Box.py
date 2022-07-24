
from collections import ChainMap
from collections.abc import Iterable
from contextlib import suppress
from functools import partial
from itertools import chain
from typing import TYPE_CHECKING, Any, Callable, Mapping

import pygame as pg
from pygame.rect import Rect

from own_types import AutoNP, Float4Tuple, Auto, Dimension, Index, style_computed, Number
import own_types as _o
from util import (Calculator, Dotted, MutableFloat, bw_getter, draw_text,
                  ensure_suffix, mrg_getter, noop, not_neg, pad_getter,
                  rs_getter)

l = [("border", "padding"),("margin",)]
box_types = [
    "content-box",
    "border-box",
    "outer-box",
]

def box_sizing(name: str):
    _name = ensure_suffix(name, "-box")
    assert _name in box_types, f"{name} is not a box-sizing"
    return _name


_indices: dict[str, Index] = {
    "top": 0,
    "bottom": 1,
    "left": 2,
    "right": 3,
}

part_slices: Mapping[str, Index] = ChainMap(_indices,{ 
    "horizontal": slice(2, None),
    "vertical": slice(None, 2)
})

guess_slicing: dict[str, Index] = {
    k: part_slices[v] for k,v in [
        ("x", "left"),
        ("y", "top"),
        ("width", "horizontal"),
        ("height", "vertical")
    ]
}

def _sum(*args: float)->float:
    """ This function can take a single value or an iterable and returns a single Number"""
    if len(args) == 1:
        x = args[0]
        if isinstance(x, Number):
            return x
        elif isinstance(x, Iterable):
            return sum(x)
    else:
        return sum(args)
    raise TypeError

def _convert(box: 'Box', frm: str, to: str, part: Index)->float:
    if frm == to:
        return 0
    _frm = box_types.index(frm)
    _to = box_types.index(to)
    if _frm > _to: # we are converting from a bigger box to a smaller box
        return -_convert(box, to, frm, part)
    lookup_chain = [*chain(*l[_frm:_to])]
    return sum(
        _sum(getattr(box, name)[part]) for name in lookup_chain
    )

def convert(box: 'Box', attr: str, frm: str|None = None, to: str|None = None, value: float|None = None)->float:
    value = getattr(box, attr) if value is None else value
    part = guess_slicing[attr]
    _frm = box.t if frm is None else frm
    _to = box.t if to is None else to
    converted = _convert(box, _frm, _to, part)
    if type(part) is int: # single value (x,y)
        return value - converted
    assert type(part) is slice
    return not_neg(value + converted)

def mutate_tuple(tup: tuple, val, slicing: Index):
    l = list(tup)
    l[slicing] = val
    return tuple(l)

class Box:
    __slots__ = ['t', 'x', 'y', 'width', 'height', 'margin', 'border', 'padding']
    def __init__(
        self,
        t: str,
        margin: tuple[float,...] = (0,)*4,
        border: tuple[float,...] = (0,)*4,
        padding: tuple[float,...] = (0,)*4,
        width: float = 0,
        height: float = 0,
        pos: Dimension = (0,0),
        outer_width: bool = False
    ):
        self.t = box_sizing(t)
        self.margin = margin 
        self.border = border
        self.padding = padding
        self.x, self.y = pos
        self.width = width if not outer_width else convert(self, "width", "outer-box", value = width)
        self.height = height

    @staticmethod
    def empty():
        return Box("content-box")

    def is_empty(self):
        return Box.empty() == self

    @property
    def pos(self):
        return self.x, self.y

    def set_pos(self, pos: tuple[float, float], t: str = "outer-box"):
        _t = box_sizing(t)
        for attr, val in zip(("x","y"), pos):
            self._set(attr, val, _t)

    def __eq__(self, other):
        assert isinstance(other, Box), other
        return self.outer_box == other.outer_box

    def __copy__(self):
        return Box(
            self.t,
            self.margin,
            self.border,
            self.padding,
            self.width, self.height,
            self.pos
        )

    def __repr__(self):
        if self.is_empty():
            return "<EmptyBox>"
        else:
            return f"<Box {tuple(self.outer_box)}>"

    def _set(self, attr: str, value: Any, t: str = "outer"):
        _t = box_sizing(t)
        setattr(self, attr, convert(self, attr, frm = _t, value = value))

    def _box(self, t: str)->Rect:
        _t = box_sizing(t)
        return Rect(
            convert(self, "x", to = _t),
            convert(self, "y", to = _t),
            convert(self, "width", to = _t),
            convert(self, "height", to = _t)
        )

    def __getattr__(self, name: str):
        """
        Enables special member access, like padding_top, or margin_vertical
        """
        with suppress(AssertionError):
            match name.split("_"):
                case [prop]:
                    return self._box(prop)
                case prop, part if part == "box":
                    return self._box(prop)
                case prop, part if prop == "set":
                    return partial(self._set, part)
                case prop, part if part in part_slices:
                    slicing = part_slices[part]
                    return getattr(self,prop)[slicing]
        raise AttributeError(name)

    def __setattr__(self, name: str, value: Any) -> None:
        """ Enables things like self.margin_horizontal = (0,)*2"""
        split = name.split("_")
        if len(split) == 2:
            print(f"Setting {name} in Box")
            prop, part = split
            slicing = part_slices[part]
            new_val = mutate_tuple(getattr(self, prop), value, slicing)
            setattr(self, prop, new_val)
        else:
            return super().__setattr__(name, value)


def make_box(
    given_width: float,
    style: style_computed,
    parent_width: float,
    parent_height: float
)->tuple[Box, Callable[[float],None]]:
    """
    Makes a box from input. 
    If height is Auto it leaves the boxes height by setting it to a sentinel (-1).
    The caller has to set that height later to an appropriate value by calling the returned function
    Raises KeyError if box_sizing is invalid, or any attributes are missing in style
    """
    calc = Calculator(parent_width)

    # the auto keyword has a special meaning with horizontal margins
    # def merge_horizontal_margin(mrg_h: tuple[AutoNP, AutoNP], avail: float)->tuple[float, float]:
    #     _avail = MutableFloat(avail)
    #     to_do = MutableFloat(0)
    #     def helper(val: AutoNP)->float|None: # type: ignore [return]
    #         if val is not Auto:
    #             value = calc(val)
    #             _avail.set(_avail - value)
    #             return value
    #         to_do.set(to_do + 1)
    #     rv = tuple(helper(x) for x in mrg_h)
    #     if to_do:
    #         split = not_neg(_avail)/to_do
    #         _rv = (split if x is None else x for x in rv)
    #     return _rv # type: ignore

    def merge_horizontal_margin(mrg_h: tuple[AutoNP, AutoNP], avail: float)->tuple[float, float]:
        match mrg_h:
            case _o.Auto, _o.Auto:
                return (avail/2,)*2
            case _o.Auto, x:
                y = calc(x)
                return (avail-y,y)
            case x, _o.Auto:
                y = calc(x)
                return (y, avail-y)
            case default:
                return calc.multi2(default)

    box_sizing: str = style["box-sizing"] # type: ignore

    margin: Float4Tuple
    padding = calc.multi4(pad_getter(style), 0)
    border = calc.multi4(bw_getter(style))
    outer_width = False
    if style["width"] is Auto:
        margin = calc.multi4(mrg_getter(style), 0)
        width = not_neg(given_width - _sum(*margin[2:], *border[2:], *padding[2:]))
        outer_width = True
    else:
        # width is a resolvable value. So margin: auto resolves to all of the remaining space
        width = calc(style["width"]) # type: ignore[arg-type]
        _margin = mrg_getter(style)
        margin =  calc.multi2(_margin[:2], 0) \
            + merge_horizontal_margin(_margin[2:], avail = given_width - _sum(width, *border[2:], *padding[2:]))

    # -1 is a sentinel value to say that the height hasn't yet been specified (height auto)
    height = calc(style["height"], auto_val=-1, perc_val = parent_height) # type: ignore[arg-type]

    box = Box(
        box_sizing,
        margin,
        border,
        padding,
        width,
        height,
        outer_width = outer_width
    )
    set_height: Callable[[float],None] = box.set_height if height == -1 else noop 
    return box, set_height # set_height is the function that should be called when the height is ready to be set

def test():
    assert Box.empty().is_empty()
    box = Box(
        "content-box",
        border = (3,)*4,
        width = 500,
        height = 150,
        outer_width=True # as if the width was the parents inner width
    )
    assert box.width == 500 - 6, box.width
    assert box.height == 150
    assert box.content_box == pg.Rect(
        0,0, 500-6, 150
    ), box.content_box

    box.set_pos((0,0))
    assert box.content_box == pg.Rect(
        3,3, 500-6, 150
    ), box.content_box
    assert box.outer_box == pg.Rect(
        0,0, 500, 150+6
    ), box.outer_box

if __name__ == "__main__":
    test()
