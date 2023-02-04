"""
The main file that runs the browser
"""
import asyncio
import logging
import os
from contextlib import redirect_stdout, suppress
from weakref import WeakSet

with open(os.devnull, "w") as f, redirect_stdout(f):
    import pygame as pg

import aiohttp
import jinja2

import config
import Element
import Media
import Selector
import Style
import util
from config import default_style_sheet, g, set_mode
from EventManager import EventManager
from J import J, SingleJ
from modals.Alert import Alert
from own_types import Event, FrozenDCache
from utils.Console import Console
from utils.FileWatcher import FileWatcher

# a lot for exports
# fmt: off
from utils.Navigator import (LOADPAGE, add_route, aload_dom, back, forward,
                             get_url, load_dom, push, reload)
# fmt: on

# setup
pg.init()
logging.basicConfig(level=logging.INFO)

CLOCK = pg.time.Clock()

# TODO: find a better way for applying style to elements depending on their state
default_sheet = Style.parse_sheet(default_style_sheet)


def _reset_config():
    # all of this is route specific
    # TODO: split cstyles into two styles. inherited and not inherited
    # # css_sheets = Cache[Style.SourceSheet]()
    css_sheets = WeakSet[Style.SourceSheet]()
    css_sheets.add(default_sheet)
    g.update(
        {
            "target": None,  # the target of the url fragment
            "icon_srcs": [],  # list[str] specified icon srcs
            # css
            "recompute": True,  # bool
            "cstyles": FrozenDCache(),  # FrozenDCache[computed_style] # the style cache
            "css_sheets": css_sheets,  # a list of used css SourceSheets
            "css_dirty": True,  # bool
            "css_sheet_len": 1,  # int
        }
    )


async def main(route: str):
    """The main function that includes the main event-loop"""
    push(route)
    root: Element.HTMLElement
    if not hasattr(config, "screen"):
        await set_mode()
    while True:
        if pg.event.peek(pg.QUIT):
            return
        event: Event | None = None
        while load_events := pg.event.get(LOADPAGE):
            event = load_events[-1]  # XXX: We only need to consider the last load event
            _reset_config()
            try:
                await util.call(event.callback, **event.kwargs)
            except Exception as e:
                util.log_error(f"Error in event route ({event.url!r})", e)
                event = None
                # goto(f"404.html?failed_url={event.url}")
                raise
        if event is not None:
            if event.target:
                with suppress(Selector.InvalidSelector):
                    g["target"] = SingleJ("#" + event.target)._elem
            logging.info(f"Going To: {event.url!r}")
            Element.set_title()
            # get the icon
            if _icon_srcs := g["icon_srcs"]:
                _icon: Media.Image = Media.Image(_icon_srcs)
                await _icon.loading_task
                if _icon.is_loaded:
                    pg.display.set_icon(_icon.surf)
                    _icon.unload()
            config.event_manager.modals.clear()

        root = g["root"]
        await util.gather_tasks(config.tasks)
        if g["css_dirty"] or g["css_sheet_len"] != len(g["css_sheets"]):
            root.apply_style(Style.SourceSheet.join(g["css_sheets"]))
            g["css_dirty"] = False
            g["css_sheet_len"] = len(g["css_sheets"])
        root.compute()
        root.layout()

        config.screen.fill(g["window_bg"])
        root.draw(config.screen)
        config.event_manager.draw(config.screen)
        if config.DEBUG:
            util.draw_text(
                config.screen,
                str(round(CLOCK.get_fps())),
                pg.font.SysFont("Arial", 18),
                "black",
                topleft=(20, 20),
            )
        pg.display.flip()
        await asyncio.to_thread(CLOCK.tick, g["FPS"])
        await config.event_manager.handle_events(
            pg.event.get(exclude=(pg.QUIT, LOADPAGE))
        )


async def run(route: str = "/"):
    """
    Runs the application
    """
    logging.info("Starting")
    config.aiosession = aiohttp.ClientSession()
    config.jinja_env = jinja2.Environment(loader=jinja2.loaders.FileSystemLoader("."))
    config.event_loop = asyncio.get_running_loop()
    config.file_watcher = FileWatcher()
    config.event_manager = EventManager()
    config.default_task = util.create_task(asyncio.sleep(0), True)
    config.tasks.append(Console())
    try:
        await main(route)
    except asyncio.exceptions.CancelledError:
        pass
    finally:
        logging.info("Exiting")
        pg.quit()
        await config.aiosession.close()
        for task in config.tasks:
            task.cancel()
        await asyncio.gather(*config.tasks, util.delete_created_files())
        await asyncio.sleep(1)


def alert(title: str, msg: str, can_escape: bool = False):
    """
    Adds an alert to the screen displaying the text.
    The user can only continue when he presses the OK-Button on the Alert
    """
    config.event_manager.modals.append(Alert(title, msg, can_escape))


route = add_route
__all__ = [
    "route",
    "load_dom",
    "aload_dom",
    "J",
    "SingleJ",
    "alert",
    "run",
    "reload",
    "push",
    "back",
    "forward",
    "get_url",
]


##### User code (only using exports) ########
@route("/")  # the index route
def startpage():
    load_dom("example.html")

    colors = ["red", "green", "yellow", "royalblue"]

    @J("button").on("click")
    def _(event):
        color = colors.pop(0)
        colors.append(color)
        event.target.set_style("background-color", color)


@route("/secondpage")
def nextpage():
    load_dom("example.jinja")


if __name__ == "__main__":
    asyncio.run(run("/#link"))
