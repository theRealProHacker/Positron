""" Any global variables are stored here"""
from own_types import FontStyle, Auto, Normal, Color
directions = ("top", "bottom", "left", "right")

g: dict[str, int|None|dict|tuple|set] = {
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
    "abs_kws" : {
        "normal": 400,
        "bold": 700,
    },
    # colors
    "sys_colors":{
        "canvas-text":"black"
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
    "absolute_length_units":{
        "px":1,
        "cm":37.8,
        "mm":3.78,
        "Q":0.945,
        "in":96,
        "pc":16,
        "pt":4/3,
    },
}
