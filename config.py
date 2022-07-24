""" Any global variables are stored here"""
from dataclasses import dataclass
from typing import Any
from own_types import FontStyle, Auto, Normal, Color
directions = ("top", "bottom", "left", "right")

# This problem is proof that typing in python doesn't work
# For typing GlobalDict needs access to Element (a Protocol doesn't make sense, because the Protocol would just be 
# a copy of the Element class. So you would have two copies of the same class just for typing)
# But Element itself needs access to config and to util, which needs access to config
# The only solution would be to import everything into one file
# But even then Box would also need to be in that file because it depends on util and Element depends on Box
# So we would end up in one big file where every change had to be noted in different places all over a 1000s of lines long file
# My advice to anyone trying to use typing in python: shoot yourself before its too late
# The solution to 
@dataclass
class _GClass:
    W: int = 900

_g = _GClass()
 

g: Any = {
    "W":900,
    "H":600,
    "root":None, # this is set in main.py and is the html element
    "lang":None, # this is set in Element.py by the HTMLElement
    "title":None, # this is set in Element.py by the title element
    "global_stylesheet": {
        "font-family":"Arial",
        "font-size": "16px",
        "color": "black",
        "display": "inline",
        "background-color": "white",
    },
    # just like global stylesheet but computed
    "head_comp_style": {
        "font-weight": 400,
        "font-family": "Arial",
        "font-size": 16,
        "font-style": None, # set by Element.py because we don't have access to the FontStyle type
        "color": Color("black"),
        "display": "block",
        "background-color": Color("white"),
        "position" : "fixed",
        "width": Auto,
        "height": Auto,
        "top":0,
        "left":0,
        "bottom":0,
        "right":0,
        **{f"margin-{k}": 0 for k in ["top", "right", "bottom", "left"]},
        **{f"padding-{k}": 0 for k in ["top", "right", "bottom", "left"]},
        **{f"border-{k}-width": 2 for k in ["top", "right", "bottom", "left"]},
        "box-sizing": "content-box",
        "line-height": Normal,
        "word-spacing": Normal,
        "font-style" : FontStyle("normal"),
    },
    # pg.Rect
    "side-keys": tuple(f"mid{k}" for k in directions),
    # padding
    "padding-keys": tuple(f"padding-{k}" for k in directions),
    # margin
    "margin-keys": tuple(f"margin-{k}" for k in directions),
    # border
    "border-width-keys": tuple(f"border-{k}-width" for k in directions),
    # inset
    "inset-keys": directions,
    # font-size
    "default_font_size": 16,
    "abs_font-size":{
        "xx-small": -3,
        "x-small": -2,
        "small": -1,
        "medium": 0,
        "large": 1,
        "x-large": 2,
        "xx-large": 3,
        "xxx-large": 4
    },
    "rel_font_size" : {
        "smaller": -1,
        "larger": 1
    },
    # font_weight
    "abs_fw_kws" : {
        "normal": 400,
        "bold": 700,
    },
    # border-width
    "abs_border_width": {
        # copied from firefox
        "thin":1,
        "medium":3,
        "thick": 5
    },
    # units
    "all_units" : {
        # length https://developer.mozilla.org/en-US/docs/Web/CSS/length
        "cap",
        "ch",
        "em",
        "ex",
        "ic",
        "lh",
        "rem",
        "rlh",
        "vh",
        "vw",
        "vmax",
        "vmin",
        "vb",
        "vi",
        "px",
        "cm",
        "mm",
        "Q",
        "in",
        "pc",
        "pt",
        # time https://developer.mozilla.org/en-US/docs/Web/CSS/time
        "s",
        "ms",
        # freq https://developer.mozilla.org/en-US/docs/Web/CSS/frequency
        "hz",
        "khz",
        # resolution https://developer.mozilla.org/en-US/docs/Web/CSS/resolution
        "dpi",
        "dpcm",
        "dppx",
        "x",
    },
    "abs_length_units":{
        "px":1,
        "cm":37.8,
        "mm":3.78,
        "Q":0.945,
        "in":96,
        "pc":16,
        "pt":4/3,
    },
}


# reveal_type(_g.W) # -> int
