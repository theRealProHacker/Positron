""" Any global variables are stored here"""
import asyncio
import math
import re
from typing import TYPE_CHECKING, Any

import aiohttp
import jinja2
import pygame as pg
from .types import Color, Cursor, Length, Surface

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
    "default_title": "Positron",
    "default_font_size": 16,        # float
    "key_delay": 500,               # int in ms
    "key_repeat": 30,               # int in ms
    "FPS": 60,                      # float
    # "zoom": 1,                      # float
    # reserved
    "root": None,                   # the root HTMLElement
}

DEBUG = True

# We avoid circular references by using if TYPE_CHECKING
if TYPE_CHECKING:
    from positron.EventManager import EventManager
    from positron.util import Task
    from positron.utils.FileWatcher import FileWatcher
    event_manager: EventManager
    file_watcher: FileWatcher
    default_task: Task
    tasks: list[Task]
tasks = []
jinja_env: jinja2.Environment           # The global jinja Environment used for all html loading
aiosession: aiohttp.ClientSession       # The global aiohttp session used for http requests
event_loop: asyncio.AbstractEventLoop   # The global asyncio event loop
screen: Surface

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
    global screen
    # icon
    if _icon := g["icon"]:
        if await _icon.loading_task is not None:
            pg.display.set_icon(_icon.surf)
    # Display Mode
    flags = pg.RESIZABLE * g["resizable"] | pg.NOFRAME * g["frameless"]
    screen = pg.display.set_mode((g["W"], g["H"]), flags)
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

cursors = {
    "default": Cursor(),
    # the cursor just vanishes by setting the smallest possible size full of zeros
    "none": Cursor((8, 8), (0, 0), (0x00,) * 8, (0x00,) * 8),
    # TODO: context-menu
    # TODO: help
    "pointer": Cursor(pg.SYSTEM_CURSOR_HAND),
    "progress": Cursor(pg.SYSTEM_CURSOR_WAITARROW),
    "wait": Cursor(pg.SYSTEM_CURSOR_WAIT),
    # TODO: cell
    "crosshair": Cursor(pg.SYSTEM_CURSOR_CROSSHAIR),
    "text": Cursor(pg.SYSTEM_CURSOR_IBEAM),
    # TODO: vertical text
    # TODO: alias, copy
    "move": Cursor(pg.SYSTEM_CURSOR_SIZEALL),
    "not-allowed": Cursor(pg.SYSTEM_CURSOR_NO),
    # TODO: grab, grabbing
    # resize arrows are symmetrical
    "n-resize": Cursor(pg.SYSTEM_CURSOR_SIZENS),
    "e-resize": Cursor(pg.SYSTEM_CURSOR_SIZEWE),
    "s-resize": Cursor(pg.SYSTEM_CURSOR_SIZENS),
    "w-resize": Cursor(pg.SYSTEM_CURSOR_SIZEWE),
    "ne-resize": Cursor(pg.SYSTEM_CURSOR_SIZENESW),
    "nw-resize": Cursor(pg.SYSTEM_CURSOR_SIZENWSE),
    "se-resize": Cursor(pg.SYSTEM_CURSOR_SIZENWSE),
    "sw-resize": Cursor(pg.SYSTEM_CURSOR_SIZENESW),
    "ew-resize": Cursor(pg.SYSTEM_CURSOR_SIZEWE),
    "ns-resize": Cursor(pg.SYSTEM_CURSOR_SIZENS),
    "nesw-resize": Cursor(pg.SYSTEM_CURSOR_SIZENESW),
    "nwse-resize": Cursor(pg.SYSTEM_CURSOR_SIZENWSE)
    # TODO: zoom-in and -out
}

input_type_check_res = {
    **dict.fromkeys(("text", "password", "tel", "search"), re.compile(r".*")),
    "number": re.compile(r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?"),
    "email": re.compile(
        r"[\w\d.!#$%&'*+/=?^_`{|}~-]+@[\w\d](?:[\w\d-]{0,61}[\w\d])?(?:\.[\w\d](?:[-\w\d]{0,61}[\w\d])?)*"
    ),
    "url": re.compile(r""),
}

default_style_sheet = """
a:visited{
    color: purple
}
input:focus{
    outline: solid rgb(45, 140, 180) medium;
}
"""
