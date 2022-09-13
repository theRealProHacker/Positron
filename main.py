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

import aiohttp
import util
from config import g, reset_config, watch_file
from Element import HTMLElement, apply_style, create_element
from J import J, SingleJ  # for console
import Media
from own_types import Surface, Vector2

# setup
pg.init()
logging.basicConfig(level=logging.INFO)

running = False

CLOCK = pg.time.Clock()
# These aren't actually constant
W: float
H: float
DIM: Vector2
SCREEN: Surface


# def set_mode(mode: dict[str, Any] = {}):
#     g.update(mode)
async def set_mode():
    """
    Call this after setting g manually. This will probably change to an API function
    """
    global SCREEN, DIM, W, H
    # Display Mode
    W, H = DIM = Vector2((g["W"], g["H"]))
    flags = pg.SCALED | pg.RESIZABLE * g["resizable"] | pg.NOFRAME * g["frameless"]
    g["screen"] = SCREEN = pg.display.set_mode(DIM, flags)
    # Screen Saver
    pg.display.set_allow_screensaver(g["allow_screen_saver"])
    # icon
    _icon: None | Media.Image
    if _icon := g["icon"]:
        if await _icon.loading_task is not None:
            pg.display.set_icon(_icon.surf)


def e(q: str):
    """
    Helper for the console: Try `e("p")` and you will get the first p element
    """
    return SingleJ(q).elem


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


async def main(file: str):
    """The main function that includes the main event-loop"""
    global running
    tree: HTMLElement
    if running:
        raise RuntimeError("Already running")
    running = True
    reset_config()
    g["file_watcher"] = util.FileWatcher()
    file = watch_file(file)
    html = await util.fetch_txt(file)
    parsed = html5lib.parse(html)
    g["root"] = tree = create_element(parsed)
    logging.debug(tree.to_html())
    pg.display.set_caption(g["title"])
    if _icon_srcs := g["icon_srcs"]:
        _icon: Media.Image = Media.Image(_icon_srcs)
        await _icon.loading_task
        if _icon.is_loaded:
            pg.display.set_icon(_icon.surf)
            _icon.unload()
    await asyncio.gather(
        *(task for task in util.consume_list(g["tasks"]) if task.sync),
        return_exceptions=False,
    )
    await set_mode()
    while True:
        end = False
        for event in pg.event.get():
            if event.type == pg.QUIT:
                end = True
            elif event.type == pg.WINDOWRESIZED:
                g["W"] = event.x
                g["H"] = event.y
                g["css_dirty"] = True
                g["recompute"] = True
        if end:
            break
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

        SCREEN.fill(g["window_bg"])
        tree.draw(SCREEN, (0, 0))
        pg.display.flip()
    running = False


async def run(file: str):
    """
    Runs the application
    """
    logging.info("Starting")
    g["default_task"] = util.create_task(asyncio.sleep(0), True)
    task = (
        asyncio.create_task(Console())
        if uses_aioconsole
        else asyncio.create_task(asyncio.sleep(0))
    )
    try:
        g["aiosession"] = aiohttp.ClientSession()
        await main(file)
        while g["reload"]:
            logging.info("Reloading")
            await main(file)
    except asyncio.exceptions.CancelledError:
        return
    finally:
        await g["aiosession"].close()
        task.cancel()
        await task
        if True:
            await util.delete_created_files()
        pg.quit()
        logging.info("Exiting")
        await asyncio.sleep(3)


async def user_main():
    # User code would come here
    g["icon"] = Media.Image(r"C:\Users\Rashid\Downloads\favicon_io\favicon-16x16.png")
    await run("example.html")


if __name__ == "__main__":
    asyncio.run(user_main())
