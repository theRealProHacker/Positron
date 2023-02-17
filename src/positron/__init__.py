import pygame as pg

import positron.utils.Navigator as Navigator
from .main import alert, run, runSync, Event
from .utils.Navigator import aload_dom, load_dom, aload_dom_frm_str, load_dom_frm_str
from .EventManager import EventManager


route = Navigator.add_route
set_title = pg.display.set_caption
quit = pg.quit
event_manager: EventManager

__all__ = [
    # for routes
    "route",
    "load_dom",
    "aload_dom",
    "aload_dom_frm_str",
    "load_dom_frm_str",
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