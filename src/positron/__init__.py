from positron.main import Event, alert, pg, arun, run, set_config
import positron.config
import positron.events.InputType as InputType
import positron.utils.Navigator as Navigator

from .EventManager import EventManager
from .J import J, SingleJ
from .Media import Image
from .utils.aio import create_file as create_file
from .utils.Navigator import aload_dom, aload_dom_frm_str, load_dom, load_dom_frm_str


def quit():
    import pygame as pg

    pg.event.post(pg.event.Event(pg.QUIT))


route = Navigator.add_route
event_manager: EventManager = positron.config.event_manager
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
    "alert",
    "URL",
    "Event",
    "event_manager",
    "Image",
    "InputType",
    # run
    "arun",
    "run",
    "set_config",
    "load_dom",
    "aload_dom",
    "load_dom_frm_str",
    "aload_dom_frm_str",
    "set_cwd",
    "route",
]

# things that should be exported but not in __all__
watch_file = positron.config.file_watcher.add_file

del pg
