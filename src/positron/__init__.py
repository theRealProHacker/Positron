from .main import Event, alert, pg, run, runSync, set_mode  # isort:skip

import positron.utils.Navigator as Navigator

from .EventManager import EventManager
from .J import J, SingleJ
from .utils.Navigator import aload_dom, aload_dom_frm_str, load_dom, load_dom_frm_str

route = Navigator.add_route
set_title = pg.display.set_caption
quit = pg.quit
event_manager: EventManager = main.event_manager
URL = Navigator.URL


def set_cwd(file: str):
    """
    Usage:
    `set_cwd(__file__)` to set the current working directory to the directory of the current file.
    """
    import os

    os.chdir(os.path.dirname(file))


__all__ = [
    # for routes
    "route",
    "load_dom",
    "aload_dom",
    "aload_dom_frm_str",
    "load_dom_frm_str",
    "set_cwd",
    # J
    "J",
    "SingleJ",
    # browser interaction
    "alert",
    "set_title",
    "URL",
    "Event",
    "event_manager",
    # run
    "run",
    "runSync",
    "set_mode",
    # navigation
    "Navigator",
]

del pg
