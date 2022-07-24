import re
from collections import ChainMap, defaultdict
from contextlib import suppress
from dataclasses import dataclass
from functools import cache
from typing import Generic, Protocol, TypedDict

from config import g
from own_types import (Auto, AutoType, Color, ComputedValue_T, ComputedValue_T1, FontStyle, Normal, NormalType, NumPerc,
                       Number, Percentage, Sentinel, style_computed, computed_value)
from util import noop, dec_re


split_units_pattern = re.compile(fr"({dec_re})(\w*)")
def split_units(attr: str)->tuple[float, str]:
    """ Split a dimension or percentage into a tuple of number and the "unit" """
    match = split_units_pattern.fullmatch(attr.strip())
    num, unit = match.groups() # type: ignore
    return float(num), unit


################## Acceptor #################################

class Acceptor(Protocol[ComputedValue_T]):
    def __call__(self,value: str, p_style: style_computed)->None|ComputedValue_T:
        ...

def set2dict(s):
    return {
        x if isinstance(x, str) else x.name.lower():x 
        for x in s
    }

def _length(dimension: tuple[float, str], p_style):
    """ 
    Gets a dimension (a tuple of a number and any unit)
    and returns a pixel value as a Number
    Raises ValueError or TypeError if something is wrong with the input.

    See: https://developer.mozilla.org/en-US/docs/Web/CSS/length
    """
    num, s = dimension # Raises ValueError if dimension has not exactly 2 entries
    if num == 0: 
        return 0 # we don't even have to look at the unit. Especially because the unit might be the empty string
    abs_length: dict[str, float] = g["abs_length_units"]
    w: int = g["W"]
    h: int = g["H"]
    rv: float
    match num,s:
        # source:
        # https://developer.mozilla.org/en-US/docs/Learn/CSS/Building_blocks/Values_and_units
        # absolute values first--------------------------------------
        case x, key if key in abs_length:
            rv = abs_length[key] * x
        # now relative values --------------------------------------
        case x, "em":
            rv = p_style["font-size"]*x
        case x, "rem":
            rv = g["root"]._style["font-size"]*x
        # view-port-relative values --------------------------------------
        case x, "vw":
            rv = x*0.01*w
        case x, "vh":
            rv = x*0.01*h
        case x, "vmin":
            rv = x*0.01*min(w,h)
        case x, "vmax":
            rv = x*0.01*max(w,h)
        # TODO: ex, ic, ch, ((lh, rlh, cap)), (vb, vi, sv*, lv*, dv*)
        # See: https://developer.mozilla.org/en-US/docs/Web/CSS/length#relative_length_units_based_on_viewport
        case x,s if isinstance(x, Number) and isinstance(s, str):
            raise ValueError(f"{s} is not an accepted unit")
        case _:
            raise TypeError()
    return rv

def color(value: str, p_style):
    with suppress(ValueError):
        return Color(value)

def font_size(value: str, p_style):
    abs_kws: dict[str, int] = g["abs_font_size"]
    rel_kws: dict[str, int] = g["rel_font_size"]
    if value in abs_kws:
        return g["default_font_size"] * 1.2 ** abs_kws[value]
    p_size: float = p_style["font-size"]
    if value in rel_kws:
        return  p_size* 1.2 ** rel_kws[value]
    else:
        return length_percentage(value, p_style, p_size) 

def font_weight(value: str, p_style):
    """ 
    Gets any fontweight value and calculates the computed value or None
    https://drafts.csswg.org/css-fonts/#relative-weights
    """
    p_size: float = p_style["font-weight"]
    if value == "lighter":
        if p_size < 100:
            return p_size
        elif  p_size < 550:
            return 100
        elif p_size < 700:
            return 400
        elif p_size <= 1000:
            return 700
        else:
            raise ValueError
    elif value == "bolder":
        if p_size < 350:
            return 400
        elif p_size < 550:
            return 700
        elif p_size < 900:
            return 900
        else:
            return p_size
    else:
        with suppress(ValueError):
            n = float(value)
            if 0 < n <= 1000:
                return n
            
def font_style(value: str, p_style):
    # FontStyle does the most for us
    split = value.split()[:2]
    with suppress(AssertionError):
        return FontStyle(*split) # type: ignore

def length(value: str, p_style):
    with suppress(ValueError):
        return _length(split_units(value), p_style)

def length_percentage(value: str, p_style, mult: float|None = None):
    with suppress(ValueError):
        num, unit = split_units(value)
        if unit == "%":
            return Percentage(num) if mult is None else mult*Percentage(num)
        else:
            return _length((num, unit), p_style)

################################## Style Data ################################
# To add a new style key, document it, add it here and then implement it in the draw or layout methods

@dataclass # repr, no hash, eq, asdict 
class StyleAttr(Generic[ComputedValue_T, ComputedValue_T1]):
    initial: str
    kws: dict[str, ComputedValue_T]
    accept: Acceptor[ComputedValue_T1]
    inherits: bool
    def __init__(
        self, 
        initial: str, 
        kws: set[ComputedValue_T] | dict[str, ComputedValue_T] = {}, 
        acc: Acceptor[ComputedValue_T1] = noop, 
        inherits: bool = None
    ):
        self.initial = initial
        if isinstance(kws, set):
            kws: dict[str, ComputedValue_T] = set2dict(kws) # type: ignore[no-redef] # mypy bug: mypy.ini says allow-redefinition = True
            inherits = False # display, box-sizing
        assert isinstance(kws, dict)
        self.kws = kws
        self.accept = acc
        if inherits is None:
            if acc is length_percentage:
                inherits == False
            else:
                inherits == True
        self.inherits = inherits if inherits is not None else acc is not length_percentage

    def convert(self, value: str, p_style: style_computed)->ComputedValue_T|ComputedValue_T1|None:
        kw = self.kws.get(value)
        return kw if kw is not None else self.accept(value, p_style)

class _ColorStyle(TypedDict):
    kws: dict[str, Color]
    acc: Acceptor

_color_style: _ColorStyle = {
    # TODO: implement more color values
    "kws": {
        "canvas-text":Color("black"),
        "transparent":Color(0,0,0,0)
    },
    "acc": color
}

# we don't want copies of these + better readibility
auto = {"auto":Auto}
normal = {"normal":Normal}

def no_change(value: str, p_style)->str:
    return value

Types = StyleAttr[Color,Color]|StyleAttr[float,float]|StyleAttr[ComputedValue_T,str]\
    |StyleAttr[AutoType, NumPerc]|StyleAttr[NormalType, NumPerc]|StyleAttr[str, str]

style_attrs: dict[str, Types] = {
    "color" : StyleAttr("canvastext", **_color_style),
    "font_weight": StyleAttr("normal", g["abs_fw_kws"], font_weight),
    "font_family": StyleAttr("Arial", acc = no_change),
    "font_size": StyleAttr("medium", acc = font_size),
    "font_style": StyleAttr("normal", acc = font_style), 
    "line_height": StyleAttr("normal", normal, length_percentage, True),
    "word_spacing": StyleAttr("normal",normal, length_percentage, True),
    "display": StyleAttr("inline", {"inline", "block", "none"}),
    "background_color": StyleAttr("transparent", **_color_style),
    
    "width":  StyleAttr("auto", auto, length_percentage),
    "height":  StyleAttr("auto", auto, length_percentage),
    "box_sizing": StyleAttr("content-box", {"content-box", "border-box"}),
    # code for generating this in trash.py
    "top":  StyleAttr("auto", auto, length_percentage),
    "bottom": StyleAttr("auto", auto, length_percentage),
    "left": StyleAttr("auto", auto, length_percentage),
    "right": StyleAttr("auto", auto, length_percentage),
    "margin_top": StyleAttr("auto", auto, length_percentage),
    "margin_bottom": StyleAttr("auto", auto, length_percentage),
    "margin_left": StyleAttr("auto", auto, length_percentage),
    "margin_right": StyleAttr("auto", auto, length_percentage),
    "margin_top": StyleAttr("auto", auto, length_percentage),
    "margin_bottom": StyleAttr("auto", auto, length_percentage),
    "margin_left": StyleAttr("auto", auto, length_percentage),
    "margin_right":  StyleAttr("auto", auto, length_percentage),
    "border_top_width":  StyleAttr("medium", auto, length_percentage),
    "border_bottom_width":  StyleAttr("medium", auto, length_percentage),
    "border_left_width":  StyleAttr("medium", auto, length_percentage),
    "border_right_width": StyleAttr("medium", auto, length_percentage), 
}

abs_default_style = {k:"inherit" if v.inherits else v.initial for k,v in style_attrs.items()}
""" The default style for a value (just like "unset") """
    
element_styles: dict[str, dict[str, str]] = defaultdict(dict,{
    "html": g["global_stylesheet"],
    "head": {
        "display": "none",
    },
    "h1": {
        "font-size":"30px"
    },
    "p":{
        "display": "block",
        "margin-top": "1em",
        "margin-bottom": "1em",
    }
})

@cache
def get_style(tag: str):
    return ChainMap(abs_default_style, element_styles[tag])


def test():
    assert split_units("3px") == (3, "px")
    assert split_units("0") == (0, "")
    with suppress(ValueError): # anything that should return a ValueError in here
        split_units("blue")
        print("Split units test failed")
