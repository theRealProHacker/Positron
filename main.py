"""
The main file that runs the browser
"""
import asyncio
import logging
import os
from contextlib import redirect_stdout

from EventManager import EventManager
from own_types import LOADPAGE, Cache, FrozenDCache

uses_aioconsole = True
try:
    import aioconsole
except ImportError:
    uses_aioconsole = False
from parse_html import parse_dom

with open(os.devnull, "w") as f, redirect_stdout(f):
    import pygame as pg

import aiohttp

import Element
import Media
import Style
import util
from config import g, set_mode
from J import J, SingleJ  # for console

# setup
pg.init()
pg.key.start_text_input()
logging.basicConfig(level=logging.INFO)

CLOCK = pg.time.Clock()
DEBUG = True
uses_aioconsole &= DEBUG
default_sheet = Style.parse_sheet(
    """
a:visited{
    color: purple
}
a:active {
    color: yellow !important;
}
"""
)


def _reset_config():
    # all of this is route specific
    # TODO: split cstyles into two styles. inherited and not inherited
    css_sheets = Cache[Style.SourceSheet]()
    css_sheets.add(default_sheet)
    g.update(
        {
            "icon_srcs": [],  # list[str] specified icon srcs
            # css
            "recompute": True,  # bool
            "cstyles": FrozenDCache(),  # FrozenDCache[computed_style] # the style cache
            "css_sheets": css_sheets,  # a list of used css SourceSheets
            "css_dirty": False,  # bool
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
    The Console takes input asyncronously and executes it. For debugging purposes only
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
        elif load_events := pg.event.get(LOADPAGE):
            try:
                event = load_events[-1]
                _reset_config()
                await util.call(event.callback, **event.kwargs)
                g["route"] = event.url
                if event.target:
                    elem = SingleJ("#" + event.target)
                logging.info(f"Going To: {event.url!r}")
                # get the title
                title: str | None = None
                for head_elem in SingleJ("head")._elem.children:
                    if head_elem.tag == "title":
                        title = head_elem.text
                if title is not None:
                    pg.display.set_caption(title)
                # get the icon
                if _icon_srcs := g["icon_srcs"]:
                    _icon: Media.Image = Media.Image(_icon_srcs)
                    await _icon.loading_task
                    if _icon.is_loaded:
                        pg.display.set_icon(_icon.surf)
                        _icon.unload()
                # await all tasks like style parsing and icon loading in sync mode
                await util.gather_tasks(g["tasks"])
            except Exception as e:
                util.log_error(e)
                # TODO: do something cool like a 404 page, showing the user how to contact the developer
                raise
        root = g["root"]
        screen: pg.Surface = g["screen"]
        event_manager: EventManager = g["event_manager"]
        # if g["css_dirty"] or g["css_sheet_len"] != len(
        #     g["css_sheets"]
        # ):  # addition or subtraction (or both)
        Element.apply_style()
        # g["recompute"] = True
        # if g["recompute"]:
        root.compute()
        # g["recompute"] = False
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
    g["jinja_env"] = None  # TODO
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


def load_dom(file: str):
    g["root"] = parse_dom(util.File(file).read())


async def aload_dom(url: str):
    g["root"] = parse_dom(await util.fetch_txt(url))


##### User code ########
@add_route("/")  # the index route
def startpage():
    load_dom("example.html")

    colors = ["red", "green", "lightblue", "yellow"]

    def button_callback(event):
        color = colors.pop(0)
        colors.append(color)
        event.target.set_style("background-color", color)

    J("button").on("click", button_callback)


@add_route("/secondpage")
def nextpage():
    load_dom("example.jinja")


if __name__ == "__main__":
    asyncio.run(run())
