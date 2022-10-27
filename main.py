"""
The main file that runs the browser
"""
import asyncio
import logging
import os
from contextlib import redirect_stdout, suppress
from weakref import WeakSet

uses_aioconsole = True
try:
    import aioconsole
except ImportError:
    uses_aioconsole = False

with open(os.devnull, "w") as f, redirect_stdout(f):
    import pygame as pg

import aiohttp
import jinja2

import Element
import Media
import Selector
import Style
import util
from config import default_style_sheet, default_style_sheet, g, set_mode
from EventManager import EventManager
from J import J, SingleJ  # for console
from own_types import LOADPAGE, BugError, FrozenDCache, Event

# setup
pg.init()
logging.basicConfig(level=logging.INFO)

CLOCK = pg.time.Clock()
DEBUG = True
uses_aioconsole &= DEBUG
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


def e(q: str):
    """
    Helper for console: Try `e("p")` and you will get the first p element
    """
    return SingleJ(q)._elem


async def Console():
    """
    The Console takes input asynchhronously and executes it. For debugging purposes only
    """
    while True:
        try:
            __x_______ = await aioconsole.ainput(">>> ")
            try:
                r = eval(__x_______)
                if r is not None:
                    print(r)
            except SyntaxError:
                exec(__x_______)
        except asyncio.exceptions.CancelledError:
            break
        except Exception as e:
            print("Console error:", e)


async def main(route: str):
    """The main function that includes the main event-loop"""
    util.goto(route)
    root: Element.HTMLElement
    if pg.display.get_surface() is None:
        await set_mode()
    while True:
        if pg.event.peek(pg.QUIT):
            return
        event: Event | None = None
        while load_events := pg.event.get(LOADPAGE):
            event = load_events[-1]
            _reset_config()
            try:
                if hasattr(event, "callback"):
                    await util.call(event.callback, **event.kwargs)
                elif hasattr(event, "path"):
                    load_dom(event.path, **event.kwargs)
                else:
                    raise BugError(f"Invalid LOADPAGE event: {event}")
            except Exception as e:
                util.log_error(f"Error in event route ({event.url!r})", e)
                event = None
                # TODO: do something cool like a 404 page, showing the user how to contact the developer
                raise
        if event is not None:
            g["route"] = event.url
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

        root = g["root"]
        screen: pg.Surface = g["screen"]
        event_manager: EventManager = g["event_manager"]
        await util.gather_tasks(g["tasks"])
        if g["css_dirty"] or g["css_sheet_len"] != len(g["css_sheets"]):
            root.apply_style(Style.SourceSheet.join(g["css_sheets"]))
            g["css_dirty"] = False
            g["css_sheet_len"] = len(g["css_sheets"])
        root.compute()
        root.layout()

        screen.fill(g["window_bg"])
        root.draw(screen)
        if DEBUG:
            util.draw_text(
                screen,
                str(round(CLOCK.get_fps())),
                pg.font.SysFont("Arial", 18),
                "black",
                topleft=(20, 20),
            )
        pg.display.flip()
        await asyncio.to_thread(CLOCK.tick, g["FPS"])
        await event_manager.handle_events(pg.event.get(exclude=(pg.QUIT, LOADPAGE)))


async def run(route: str = "/"):
    """
    Runs the application
    """
    logging.info("Starting")
    g["default_task"] = util.create_task(asyncio.sleep(0), True)
    g["file_watcher"] = util.FileWatcher()
    g["event_manager"] = EventManager()
    g["aiosession"] = aiohttp.ClientSession()
    g["jinja_env"] = jinja2.Environment(loader=jinja2.loaders.FileSystemLoader("."))
    g["event_loop"] = asyncio.get_running_loop()
    console_task = (
        asyncio.create_task(Console())
        if uses_aioconsole
        else asyncio.create_task(asyncio.sleep(0))
    )
    try:
        await main(route)
    except asyncio.exceptions.CancelledError:
        pass
    finally:
        logging.info("Exiting")
        pg.quit()
        await g["aiosession"].close()
        console_task.cancel()
        tasks: list[util.Task] = g["tasks"]
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, console_task, util.delete_created_files())
        await asyncio.sleep(1)


# Exports
add_route = util.add_route
goto = util.goto
reload = util.reload


def load_dom(file: str, *args, **kwargs):
    env: jinja2.Environment = g["jinja_env"]
    html = env.from_string(util.File(file).read()).render(*args, **kwargs)
    g["root"] = Element.HTMLElement.from_string(html)
    manager: EventManager = g["event_manager"]
    manager.on("file-modified", reload, path=file)


async def aload_dom(url: str):
    env: jinja2.Environment = g["jinja_env"]
    html = await env.from_string(await util.fetch_txt(url)).render_async()
    g["root"] = Element.HTMLElement.from_string(html)


##### User code ########
@add_route("/")  # the index route
def startpage():
    load_dom("example.html")

    colors = ["red", "green", "yellow", "royalblue"]

    @J("button").on("click")
    def _(event):
        color = colors.pop(0)
        colors.append(color)
        event.target.set_style("background-color", color)


@add_route("/secondpage")
def nextpage():
    load_dom("example.jinja")


if __name__ == "__main__":
    asyncio.run(run("/#link"))
