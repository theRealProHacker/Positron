""" Any global variables are stored here"""
from typing import Any
from WeakCache import Cache

# This problem is proof that typing in python doesn't work
# For typing GlobalDict needs access to Element (a Protocol doesn't make sense, because the Protocol would just be
# a copy of the Element class. So you would have two copies of the same class just for typing)
# But Element itself needs access to config and to util, which needs access to config
# The only solution would be to import everything into one file
# But even then Box would also need to be in that file because it depends on util and Element depends on Box
# So we would end up in one big file where every change had to be noted in different places all over a 1000s of lines long file
# My advice to anyone trying to use typing in python: shoot yourself before it's too late


g: Any = {
    "W": 900,       # int
    "H": 600,       # int
    "root": None,   # the html element
    "screen": None, # pg.Surface
    "default_font_size": 16 # float
}

def reset_config():
    global g
    g.update({
        "lang": "",  # str # this is set in Element.py by the HTMLElement
        "title": "",  # str # this is set in Element.py by the title element
        "cstyles": Cache(), # Cache[computed_style] # the style cache
        "css_rules": Cache(), # Cache[Rule] # a list of external css rules
        "css_rules_dirty": False, # bool 
    })
# main must reset


# constant data

# font-size
abs_font_size = {
    "xx-small": -3,
    "x-small": -2,
    "small": -1,
    "medium": 0,
    "large": 1,
    "x-large": 2,
    "xx-large": 3,
    "xxx-large": 4,
}
rel_font_size = {"smaller": -1, "larger": 1}
# font_weight
abs_font_weight = {
    "normal": 400,
    "bold": 700,
}
# border-width
abs_border_width = {
    # copied from firefox
    "thin": 1,
    "medium": 3,
    "thick": 5,
}
# units
all_units = {
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
}
abs_length_units = {
    "px": 1,
    "cm": 37.8,
    "mm": 3.78,
    "Q": 0.945,
    "in": 96,
    "pc": 16,
    "pt": 4 / 3,
}
