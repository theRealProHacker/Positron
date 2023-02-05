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
import config
import Element
import jinja2
import Media
import Selector
import Style
import util

# a lot for exports
# fmt: off
import utils.Navigator as Navigator
from config import default_style_sheet, g, set_mode
from EventManager import EventManager
from J import J, SingleJ
from modals.Alert import Alert
from own_types import FrozenDCache
from utils.Console import Console
from utils.FileWatcher import FileWatcher
from utils.Navigator import LOADPAGE, URL, add_route, aload_dom, load_dom, push

# fmt: on

route = add_route
set_title = pg.display.set_caption
__all__ = [
    # for routes
    "route",
    "load_dom",
    "aload_dom",
    # J
    "J",
    "SingleJ",
    # browser interaction
    "alert",
    "set_title",
    "URL",
    # run
    "run",
    # navigation
    "Navigator",
]

# setup
pg.init()
logging.basicConfig(level=logging.INFO)

CLOCK = pg.time.Clock()
""" The global pygame clock """

# TODO: find a better way for applying style to elements depending on their state
default_sheet = Style.parse_sheet(default_style_sheet)
""" The default ua-sheet """


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


def _set_title():
    head = g["root"].children[0]
    assert isinstance(head, Element.MetaElement)
    titles = [title.text for title in head.children if title.tag == "title"]
    if titles:
        pg.display.set_caption(titles[-1])


async def main(route: str):
    """The main function that includes the main event-loop"""
    push(route)
    root: Element.HTMLElement
    if not hasattr(config, "screen"):
        await set_mode()
    while True:
        if pg.event.peek(pg.QUIT):
            return
        if load_events := pg.event.get(LOADPAGE):
            event = load_events[-1]  # XXX: We only need to consider the last load event
            url: URL = event.url
            _reset_config()
            try:
                await util.call(event.callback, **url.kwargs)
            except Exception as e:
                util.log_error(f"Error in event route ({url})", e)
                # put (f"404.html?failed_url={event.url}") into a simulated event
                raise
            if url.target:
                with suppress(Selector.InvalidSelector, RuntimeError):
                    g["target"] = SingleJ("#" + url.target)._elem
            logging.info(f"Going To: {url}")
            _set_title()
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


if __name__ == "__main__":
    asyncio.run(run("/#link"))
