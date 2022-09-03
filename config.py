""" Any global variables are stored here"""
from concurrent.futures import ThreadPoolExecutor
from typing import Any
from queue import Queue
from own_types import Color, Cache, FrozenDCache

# This problem is proof that typing in python doesn't work
# For typing GlobalDict needs access to Element (a Protocol doesn't make sense, because the Protocol would just be
# a copy of the Element class. So you would have two copies of the same class just for typing)
# But Element itself needs access to config and to util, which needs access to config
# The only solution would be to import everything into one file
# But even then Box would also need to be in that file because it depends on util and Element depends on Box
# So we would end up in one big file where every change had to be noted in different places all over a 1000s of lines long file
# My advice to anyone trying to use typing in python: shoot yourself before it's too late


g: dict[str, Any] = {
    # User settable
    "W": 900,                       # int
    "H": 600,                       # int
    "window_bg": Color("white"),    # Color
    "resizable": True,              # bool
    "frameless": False,             # bool
    "allow_screen_saver": True,
    "default_font_size": 16,        # float
    # reserved
    "root": None,                   # the html element
    "file_watcher": None,           # the file watcher
    "screen": None,                 # pg.Surface
    "global_sheet": None,           # SourceSheet() # Is added in Style.py
    "tasks": []
}

def reset_config():
    global g
    # TODO: split cstyles into two styles. inherited and not inherited
    g.update({
        "lang": "",                 # str # this is set in Element.py by the HTMLElement
        "title": "",                # str # this is set in Element.py by the title element
        "recompute": True,          # bool 
        "reload": False,            # bool
        "cstyles": FrozenDCache(),  # FrozenDCache[computed_style] # the style cache
        "css_sheets": Cache(),      # Cache[SourceSheet] # a list of external css SourceSheets
        "css_dirty": False,         # bool
        "css_sheet_len": 0,         # int
        "loader_queue" : Queue(),    # Queue[tuple[str,callback]]
    })
    g["global_sheet"].clear()
# main must reset

def add_sheet(sheet: Any):
    g["css_sheets"].add(sheet)
    g["global_sheet"] += sheet
    g["css_dirty"] = True

def watch_file(file: str) -> str:
    """Add the file to the watched files. The caller has to hold on to the file until it shouldn't be watched anymore"""
    return g["file_watcher"].add_file(file)

################################ constant data ########################

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
