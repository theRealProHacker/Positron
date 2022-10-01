"""
The main file that runs the browser
"""
import asyncio
import logging
import os
from contextlib import redirect_stdout
from typing import Callable

from EventManager import EventManager
from own_types import LOADPAGE, loadpage_event

uses_aioconsole = True
try:
    import aioconsole
except ImportError:
    uses_aioconsole = False
from parse_html import parse_dom

with open(os.devnull, "w") as f, redirect_stdout(f):
    import pygame as pg

import aiohttp

import Media
import util
from config import g, reset_config, set_mode
from Element import HTMLElement, apply_style
from J import J, SingleJ  # for console

# setup
pg.init()
pg.key.start_text_input()
logging.basicConfig(level=logging.INFO)

CLOCK = pg.time.Clock()
DEBUG = True
uses_aioconsole &= DEBUG
routes: dict[str, Callable] = {}


def add_route(route: str):
    if not isinstance(route, str):
        raise ValueError("route must be a String")

    def inner(route_func: Callable):
        routes[route] = route_func

    return inner


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


async def main(route: str) -> str:
    """The main function that includes the main event-loop"""
    if "?" in route:
        route, _args = route.split("?")
        route_kwargs = dict(
            item for arg in _args.split("&") if len(item := arg.split("=")) == 2
        )
    else:
        route_kwargs = {}
    try:
        await util.call(routes[route], **route_kwargs)
        g["route"] = route
        reset_config()
        pg.display.set_caption(g["title"])
        if _icon_srcs := g["icon_srcs"]:
            _icon: Media.Image = Media.Image(_icon_srcs)
            await _icon.loading_task
            if _icon.is_loaded:
                pg.display.set_icon(_icon.surf)
                _icon.unload()
        await util.gather_tasks(g["tasks"])
    except KeyError as e:
        util.log_error(f"Probably unknown route {e.args[0]!r}")
    except Exception as e:
        util.log_error(e)
        # TODO: do something cool like a 404 page, showing the user how to contact the developer
        raise
    if pg.display.get_surface() is None:
        await set_mode()
    while True:
        if pg.event.peek(pg.QUIT):
            return ""
        elif load_events := pg.event.get(LOADPAGE):
            return load_events[-1].route
        tree: HTMLElement = g["root"]
        screen: pg.Surface = g["screen"]
        event_manager: EventManager = g["event_manager"]
        await event_manager.handle_events(pg.event.get())
        # Await the next tick. In this spare time all async tasks can be run.
        await asyncio.to_thread(CLOCK.tick, g["FPS"])
        if g["css_dirty"] or g["css_sheet_len"] != len(
            g["css_sheets"]
        ):  # addition or subtraction (or both)
            apply_style()
            g["recompute"] = True
        if g["recompute"]:
            tree.compute()
            g["recompute"] = False
        tree.layout()

        screen.fill(g["window_bg"])
        tree.draw(screen)
        if DEBUG:
            util.draw_text(
                screen,
                str(round(CLOCK.get_fps())),
                pg.font.SysFont("Arial", 18),
                "black",
                topleft=(20, 20),
            )
        pg.display.flip()


async def run(route: str = "/"):
    """
    Runs the application
    """
    logging.info("Starting")
    g["default_task"] = util.create_task(asyncio.sleep(0), True)
    g["file_watcher"] = util.FileWatcher()
    g["event_manager"] = EventManager()
    g["aiosession"] = aiohttp.ClientSession()
    console_task = (
        asyncio.create_task(Console())
        if uses_aioconsole
        else asyncio.create_task(asyncio.sleep(0))
    )
    try:
        while route := await main(route):
            logging.info("Reloading")
    except asyncio.exceptions.CancelledError:
        return
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


def goto(route: str):
    pg.event.post(loadpage_event(route))


def load_dom(file: str):
    g["root"] = parse_dom(util.File(file).read())


async def aload_dom(url: str):
    g["root"] = parse_dom(await util.fetch_txt(url))


##### User code ########
@add_route("/")  # the index route
def startpage():
    load_dom("example.html")

    # def load_next_page():
    #     goto("/nextpage?firstname=John&lastname=Doe")

    colors = ["red", "green", "lightblue", "yellow"]

    def button_callback(event):
        color = colors.pop(0)
        colors.append(color)
        event.target.set_style("background-color", color)

    J("#button").on("click", button_callback)


# TODO: add jinja support
# @add_route("/nextpage")
# def nextpage(*, firstname: str, lastname: str):
#     load_dom("nextpage.jinja", name=f"{firstname} {lastname}")


if __name__ == "__main__":
    asyncio.run(run())
