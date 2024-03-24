"""
The main file that runs the browser
"""

import asyncio
import logging
import os
from contextlib import redirect_stdout, suppress
from typing import overload
from weakref import WeakSet

import aiohttp
import jinja2

with open(os.devnull, "w") as f, redirect_stdout(f):
    import pygame as pg

import positron.config as config
import positron.Style as Style  # isort:skip
import positron.Element as Element
import positron.Media as Media
import positron.Selector as Selector
import positron.utils as util
import positron.utils.clipboard

from .config import default_style_sheet, g
from .EventManager import EventManager, _Event
from .J import SingleJ
from .modals.Alert import Alert
from .types import Color, ColorValue, FrozenDCache, Surface
from .utils.Console import Console
from .utils.FileWatcher import FileWatcher
from .utils.Navigator import LOADPAGE, URL, push

# setup
pg.init()

CLOCK = pg.time.Clock()
""" The global pygame clock """

# TODO: find a better way for applying style to elements depending on their state
default_sheet = Style.parse_sheet(default_style_sheet)
""" The default ua-sheet """

config.jinja_env = jinja2.Environment(
    loader=jinja2.loaders.FileSystemLoader("."), enable_async=True
)
config.file_watcher = FileWatcher()
config.event_manager = EventManager()


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


@overload
def set_config():
    ...


@overload
def set_config(
    *,
    width: int | None = None,
    height: int | None = None,
    bg_color: ColorValue | None = None,
    resizable: bool | None = None,
    frameless: bool | None = None,
    screen_saver: bool | None = None,
    icon: None | Media.Image = None,
    title: str | None = None,
    default_font_size: int | None = None,
    key_delay: int | None = None,
    key_repeat: int | None = None,
    fps: float | None = None,
):
    ...


def set_config(**kwargs):
    if (icon := kwargs.get("icon")) is not None:
        if icon.is_loading:

            def on_icon_loaded(future: asyncio.Future[Surface]):
                with suppress(Exception):
                    pg.display.set_icon(future.result())

            task = icon.loading_task
            task.sync = True
            task.add_done_callback(on_icon_loaded)
        elif icon.is_loaded:
            pg.display.set_icon(icon.surf)

    m2g = {"width": "W", "height": "H", "fps": "FPS"}
    g.update(
        {
            key: v
            for k, v in kwargs.items()
            if (key := m2g.get(k, k)) in g and v is not None
        }
    )

    g["bg_color"] = Color(g["bg_color"])

    flags = pg.RESIZABLE * g["resizable"] | pg.NOFRAME * g["frameless"]
    config.screen = pg.display.set_mode((g["W"], g["H"]), flags)
    pg.display.set_allow_screensaver(g["screen_saver"])
    pg.key.set_repeat(g["key_delay"], g["key_repeat"])


def _set_title():
    head = g["root"].children[0]
    assert isinstance(head, Element.MetaElement)
    titles = [title.text for title in head.children if title.tag == "title"]
    pg.display.set_caption(titles[-1] if titles else g["title"])


async def _load_page(event):
    url: URL = event.url
    _reset_config()
    config.event_manager.reset()
    try:
        await util.acall(event.callback, **url.kwargs)
    except Exception as e:
        util.log_error(f"Error in event route ({url})", e)
        # put (f"404.html?failed_url={url}") into a simulated event
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


async def main(route: str):
    """The main function that includes the main event-loop"""
    push(route)
    root: Element.HTMLElement
    if not hasattr(config, "screen"):
        set_config()
    positron.utils.clipboard.init()
    while True:
        if pg.event.peek(pg.QUIT):
            return
        if load_events := pg.event.get(LOADPAGE):
            # XXX: We only need to consider the last load event
            await _load_page(load_events[-1])
        root = g["root"]
        await util.gather_tasks(config.tasks)
        if root:
            if g["css_dirty"] or g["css_sheet_len"] != len(g["css_sheets"]):
                root.apply_style(Style.SourceSheet.join(g["css_sheets"]))
                g["css_dirty"] = False
                g["css_sheet_len"] = len(g["css_sheets"])

            root.compute()
            root.layout()

            config.screen.fill(g["bg_color"])
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
        if root:
            await config.event_manager.handle_events(
                pg.event.get(exclude=(pg.QUIT, LOADPAGE))
            )


async def arun(route: str = "/"):
    """
    Runs the application

    ```py
    await arun("/")
    ```
    """
    logging.info("Starting")
    # XXX: these need to be here because they require a running event loop
    config.event_loop = asyncio.get_running_loop()
    config.default_task = util.create_task(asyncio.sleep(0), True)
    config.tasks.append(Console(globals()))
    config.aiosession = aiohttp.ClientSession()
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


def run(route: str = "/"):
    """
    Runs the application synchronously

    ```py
    run("/")
    ```
    """
    asyncio.run(arun(route))


def alert(title: str, msg: str, can_escape: bool = False):
    """
    Adds an alert to the screen displaying the text.
    The user can only continue when he presses the OK-Button on the Alert
    """
    config.event_manager.modals.append(Alert(title, msg, can_escape))


class Event(_Event):
    # this is the only difference to EventManager._Event
    target: SingleJ  # type: ignore
    related_target: SingleJ  # type: ignore
