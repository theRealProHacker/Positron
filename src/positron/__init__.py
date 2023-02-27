from positron.main import Event, pg, run, runSync, set_mode  # isort:skip
import positron.main as main

import positron.util
import positron.utils.Navigator as Navigator
import positron.config

from .EventManager import EventManager
from .J import J, SingleJ
from .utils.Navigator import aload_dom, load_dom

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
    # J
    "J",
    "SingleJ",
    # browser interaction
    "set_title",
    "URL",
    "Event",
    "event_manager",
    "Navigator",
    # for routes and running
    "route",
    "load_dom",
    "aload_dom",
    "set_cwd",
    "run",
    "runSync",
    "set_mode",
]

# things that should be exported but not in __all__
watch_file = positron.config.file_watcher.add_file
alert = main.alert
aload_dom_frm_str = Navigator.aload_dom_frm_str
load_dom_frm_str = Navigator.load_dom_frm_str


del pg
