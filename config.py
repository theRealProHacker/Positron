""" Any global variables are stored here"""
import math
from typing import Any

import pygame as pg

from own_types import Cache, Color, FrozenDCache, Length, Vector2

# This problem is proof that typing in python doesn't work
# For typing GlobalDict needs access to Element (a Protocol doesn't make sense, because the Protocol would just be
# a copy of the Element class. So you would have two copies of the same class just for typing)
# But Element itself needs access to config and to util, which needs access to config
# The only solution would be to import everything into one file
# But even then Box would also need to be in that file because it depends on util and Element depends on Box
# So we would end up in one big file where every change had to be noted in different places all over a 1000s of lines long file
# My advice to anyone trying to use typing in python: shoot yourself before it's too late

# fmt: off
g: dict[str, Any] = {
    # User settable
    "W": 900,                       # int
    "H": 600,                       # int
    "window_bg": Color("white"),    # Color
    "resizable": True,              # bool
    "frameless": False,             # bool
    "allow_screen_saver": True,     # bool
    "icon": None,                   # None or Image
    "default_font_size": 16,        # float
    "key_repeat": 0,                # float
    "zoom": 1,                      # float
    "FPS": 60,                      # float
    # reserved
    "root": None,                   # the html element
    "route": "",                    # the current route
    "file_watcher": None,           # util.FileWatcher
    "event_manager": None,          # Eventmanager
    "aiosession": None,             # aiohttp.ClientSession
    "screen": None,                 # pg.Surface
    "default_task": None,           # util.Task
    "tasks": []                     # list of tasks that are started in synchronous functions
}

def reset_config():
    global g
    # all of this is route specific
    # TODO: split cstyles into two styles. inherited and not inherited
    g.update({
        "title": "",                # str # the document title. this is set in Element.py by the title element
        "icon_srcs":[],             # list[str] specified icon srcs
        # css
        "recompute": True,          # bool
        "cstyles": FrozenDCache(),  # FrozenDCache[computed_style] # the style cache
        "css_sheets": Cache(),      # Cache[SourceSheet] # a list of external css SourceSheets
        "css_dirty": False,         # bool: does css need to be applied
        "css_sheet_len": 0,         # int
    })
# fmt: on


def add_sheet(sheet: Any):
    """
    Add a sheet to the global css_sheets
    """
    g["css_sheets"].add(sheet)
    g["css_dirty"] = True


def watch_file(file: str) -> str:
    """
    Add the file to the watched files.
    The caller has to hold on to the file until it shouldn't be watched anymore
    """
    return g["file_watcher"].add_file(file)


# def set_mode(mode: dict[str, Any] = {}):
#     g.update(mode)
async def set_mode():
    """
    Call this after setting g manually. This will probably change to an API function
    """
    # icon
    if _icon := g["icon"]:
        if await _icon.loading_task is not None:
            pg.display.set_icon(_icon.surf)
    # Display Mode
    flags = pg.SCALED | pg.RESIZABLE * g["resizable"] | pg.NOFRAME * g["frameless"]
    g["screen"] = pg.display.set_mode((g["W"], g["H"]), flags)
    # Screen Saver
    pg.display.set_allow_screensaver(g["allow_screen_saver"])
    # key repeat
    pg.key.set_repeat(int(g["key_repeat"] or 0.1))


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
    "thin": Length(1),
    "medium": Length(3),
    "thick": Length(5),
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
rel_length_units = {
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
}
abs_angle_units = {
    "deg": 1,
    "grad": 400 / 360,
    # allows for example 1.5πrad or 1.5pirad instead of calc(1.5rad*pi)
    "pirad": 2 / 360,
    "πrad": 2 / 360,
    "rad": 2 * math.pi / 360,
    "turn": 1 / 360,
}
abs_time_units = {"s": 1, "ms": 1 / 1000}
# abs_frequency_units = {
#     "hz": 1,
#     "khz": 1000
# }
abs_resolution_units = {"dpi": 1, "dpcm": 2.54, "x": 96, "dppx": 96}
