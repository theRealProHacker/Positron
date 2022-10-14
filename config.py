""" Any global variables are stored here"""
import math
from typing import Any

import pygame as pg

from own_types import Color, Length

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
    "key_delay": 500,               # int in ms
    "key_repeat": 30,               # int in ms
    # "zoom": 1,                      # float
    "FPS": 60,                      # float
    "jinja_env": None,              # The global jinja Environment
    # reserved
    "root": None,                   # the root HTMLElement
    "route": "",                    # the current route
    "file_watcher": None,           # util.FileWatcher
    "event_manager": None,          # Eventmanager
    "aiosession": None,             # aiohttp.ClientSession
    "jinja_env": None,              # The global jinja Environment
    "event_loop": None,             # asyncio.BaseEventLoop
    "screen": None,                 # pg.Surface
    "default_task": None,           # util.Task
    "tasks": [],                    # list of tasks that are started in synchronous functions
    "visited_links": {}             # dict[str, Literal["browser", "internal", "invalid"]]
}
# fmt: on


def add_sheet(sheet: Any):
    """
    Add a sheet to the global css_sheets
    """
    g["css_sheets"].add(sheet)
    g["css_dirty"] = True


async def set_mode():
    """
    Call this after setting g manually. This will probably change to an API function
    """
    # icon
    if _icon := g["icon"]:
        if await _icon.loading_task is not None:
            pg.display.set_icon(_icon.surf)
    # Display Mode
    flags = pg.RESIZABLE * g["resizable"] | pg.NOFRAME * g["frameless"]
    g["screen"] = pg.display.set_mode((g["W"], g["H"]), flags)
    # Screen Saver
    pg.display.set_allow_screensaver(g["allow_screen_saver"])
    # key repeat
    pg.key.set_repeat(g["key_delay"], g["key_repeat"])


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


default_style_sheet = """
a:visited{
    color: purple
}
input:focus{
    outline: solid rgb(45, 140, 180) medium;
}
"""
