"""
The main file that runs the browser
"""
import asyncio
import logging
import os
from contextlib import redirect_stdout

uses_aioconsole = True
try:
    import aioconsole
except ImportError:
    uses_aioconsole = False
import html5lib

with open(os.devnull, "w") as f, redirect_stdout(f):
    import pygame as pg

import util
from config import g, reset_config, watch_file
from Element import HTMLElement, apply_rules, create_element
from J import J, SingleJ
from own_types import Surface, Vector2
from Style import SourceSheet

# setup
pg.init()
logging.basicConfig(level=logging.INFO)

did_set_mode = False
running = False

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
    flags = pg.SCALED | pg.RESIZABLE * g["resizable"] | pg.NOFRAME * g["frameless"]
    g["screen"] = SCREEN = pg.display.set_mode(DIM, flags)
    # Screen Saver
    pg.display.set_allow_screensaver(g["allow_screen_saver"])


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


async def tick(time: int):
    """Await the next tick. In this spare time all async tasks can be run."""
    # https://youtu.be/GpqAQxH1Afc?t=833
    await asyncio.to_thread(CLOCK.tick, time)


async def main(file: str):
    """The main function that includes the main event-loop"""
    global running
    if running:
        raise RuntimeError("Already running")
    running = True
    reset_config()
    g["file_watcher"] = util.FileWatcher()
    file = watch_file(file)

    html = util.fetch_txt(file)
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
        if end:
            break
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
        pg.display.flip()  # TODO: only update the actually changed areas
    running = False

async def run(file: str):
    logging.info("Starting")
    if not did_set_mode:
        set_mode()
    if uses_aioconsole:
        task = asyncio.create_task(Console())
    try:
        await main(file)
        while g["reload"]:
            logging.info("Reloading")
            await main(file)
    finally:
        if uses_aioconsole:
            task.cancel()
            await task
        pg.quit()
        logging.info("Exiting")


async def async_main():
    await run("example.html")


if __name__ == "__main__":
    asyncio.run(async_main())
