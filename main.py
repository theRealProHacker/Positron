"""
The main file that runs the browser
"""

import asyncio
import re
import aioconsole
import logging
import os
import time
from contextlib import redirect_stdout
from os.path import abspath, dirname

with open(os.devnull, "w") as f, redirect_stdout(f):
    import pygame as pg

import html5lib
from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

import util
from config import g, reset_config
from Element import HTMLElement, apply_rules, create_element
from own_types import Event, Surface, Vector2, Cache
from Style import SourceSheet
from J import SingleJ, J

did_set_mode = False
running = False
reload = False

CLOCK = pg.time.Clock()
# These aren't actually constant
W: float
H: float
DIM: Vector2
SCREEN: Surface


# def set_mode(mode: dict[str, Any] = {}):
#     g.update(mode)
def set_mode():
    global SCREEN, DIM, W, H, did_set_mode
    did_set_mode = True
    # Display Mode
    W, H = DIM = Vector2((g["W"], g["H"]))
    flags = 0 | pg.RESIZABLE * g["resizable"] | pg.NOFRAME * g["frameless"]
    g["screen"] = SCREEN = pg.display.set_mode(DIM, flags)
    # Screen Saver
    pg.display.set_allow_screensaver(g["allow_screen_saver"])

# Setup
pg.init()
logging.basicConfig(level=logging.INFO)


async def run(file: str):
    global reload
    logging.info("Starting")
    if not did_set_mode:
        set_mode()
    try:
        await main(file)
        while reload:
            logging.info("Reloading")
            reload = False
            await main(file)
    finally:
        pg.quit()
        logging.info("Exiting")


async def tick(time: int):
    """ Await the next tick. In this spare time all async tasks can be run. """
    # https://youtu.be/GpqAQxH1Afc?t=833
    await asyncio.to_thread(CLOCK.tick, time)


async def main(file: str):
    global running
    if running:
        raise RuntimeError("Already running")
    running = True
    reset_config()
    g["file_watcher"] = OwnHandler()
    file = g["file_watcher"].add_file(file)

    html = util.fetch_src(file)
    parsed = html5lib.parse(html)
    tree: HTMLElement = create_element(parsed)
    logging.debug(tree.to_html())
    pg.display.set_caption(g["title"])
    g["root"] = tree

    while True:
        end = False
        for event in pg.event.get():
            if event.type == pg.QUIT:
                end = True
            elif event.type == pg.WINDOWRESIZED:
                g["W"] = event.x
                g["H"] = event.y
                g["recompute"] = True
        if end: break
        if g["css_dirty"] or g["css_sheet_len"] != len(g["css_sheets"]):
            apply_style()
            g["recompute"] = True
        if g["recompute"]:
            tree.compute()
            tree.layout()
            g["recompute"] = False

        await tick(30)

        SCREEN.fill(g["window_bg"])
        tree.draw(SCREEN, (0, 0))
        pg.display.flip()
    running = False


class OwnHandler(FileSystemEventHandler):
    def __init__(self):
        self.last_hit = time.monotonic()  # this doesn't need to be extremely accurate
        self.files = Cache[str]()
        self.dirs = set[str]()

    def add_file(self, file: str):
        file = abspath(file)
        file = self.files.add(file)
        new_dir = dirname(file)
        if not new_dir in self.dirs:
            self.dirs.add(new_dir)
            ob = Observer()
            ob.schedule(self, new_dir)
            ob.start()
        return file

    def on_modified(self, event: FileSystemEvent):
        logging.debug(f"File modified: {event.src_path}")
        if event.src_path in self.files and (t := time.monotonic()) - self.last_hit > 1:
            global reload
            reload = True
            pg.event.clear(eventtype=pg.QUIT)
            pg.event.post(Event(pg.QUIT))
            self.last_hit = t


def show_image(surf: Surface):
    rect = surf.get_rect(center=DIM / 2)
    SCREEN.blit(surf, rect)


def apply_style():
    g["global_sheet"] = SourceSheet.join(g["css_sheets"])
    g["css_dirty"] = True
    g["css_sheet_len"] = len(g["css_sheets"])
    apply_rules(g["root"], g["global_sheet"].all_rules)

def e(q: str):
    return SingleJ(q).elem

async def Console():
    while True:
        try:
            x = await aioconsole.ainput(">>> ")
            try:
                r = eval(x)
                if r is not None:
                    print(r)
            except SyntaxError:
                exec(x)
        except asyncio.exceptions.CancelledError:
            break
        except Exception as e:
            print(e)

async def async_main():
    task = asyncio.create_task(Console())
    await run("example.html")
    task.cancel()
    await task


if __name__ == "__main__":
    asyncio.run(async_main())

