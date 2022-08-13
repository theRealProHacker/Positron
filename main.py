"""
The main file that runs the browser
"""

import os
import time
from contextlib import redirect_stdout
import logging
from Style import SourceSheet

from WeakCache import Cache

with open(os.devnull, "w") as f, redirect_stdout(f):
    import pygame as pg

from os.path import abspath, dirname

import html5lib
from watchdog.events import DirModifiedEvent, FileModifiedEvent, FileSystemEventHandler
from watchdog.observers import Observer

import util
from config import g, reset_config
from Element import Element, HTMLElement, apply_rules, create_element
from own_types import Event, Surface, Vector2


pg.init()
W, H = DIM = Vector2((g["W"], g["H"]))
SCREEN = pg.display.set_mode(DIM, pg.RESIZABLE)
g["screen"] = SCREEN
CLOCK = pg.time.Clock()
logging.basicConfig(level=logging.INFO)

running = False
reload = False


def run(file: str):
    global reload
    logging.info("Starting")
    try:
        main(file)
        while reload:
            logging.info("Reloading")
            reload = False
            main(file)
    finally:
        pg.quit()


def main(file: str):
    global running
    if running:
        raise RuntimeError("Already running")
    running = True
    reset_config()
    g["file_watcher"] = OwnHandler([file])

    html = util.fetch_src(file)
    parsed = html5lib.parse(html)
    tree: HTMLElement = create_element(parsed)
    logging.debug(tree.to_html())
    pg.display.set_caption(g["title"])
    g["root"] = tree

    tree.compute()
    tree.layout()

    end = False
    recompute = False
    while True:
        for event in pg.event.get():
            if event.type == pg.QUIT:
                end = True
            elif event.type == pg.WINDOWRESIZED:
                g["W"] = event.x
                g["H"] = event.y
                recompute = True

        if end:
            break
        if g["css_dirty"] or g["css_sheet_len"] == len(g["css_sheets"]):
            apply_style()
            recompute = True
        if recompute:
            tree.compute()
            tree.layout()

        CLOCK.tick(30)

        SCREEN.fill("white")
        tree.draw(SCREEN, (0, 0))
        pg.display.flip()
    running = False


def test():
    # setup code
    example_html = """
<html>
    <head>
        <p style="color: green">My example Text GgOT</p>
    </head>
    <body style="background-color: lightblue">
        Text
        <p style="color: green; width: auto">My example Text GgOT</p>
        Text
        <p>now a paragraph</p>
        and Text again
    </body>
</html>"""
    parsedTree = html5lib.parse(example_html)
    tree: Element = create_element(parsedTree, parent=None)
    print(tree.to_html())
    g["root"] = tree
    # now compute and assert
    tree.compute()
    tree.layout()


class OwnHandler(FileSystemEventHandler):
    def __init__(self, files: list[str]):
        self.last_hit = time.monotonic()  # this doesn't need to be extremely accurate
        self.files = Cache[str]()
        self.dirs = set[str]()
        for file in files:
            self.add_file(file)

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

    def on_modified(self, event: FileModifiedEvent | DirModifiedEvent):
        if (
            event.src_path in self.files
            and (t := time.monotonic()) - self.last_hit > 1
        ):
            global reload
            reload = True
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


if __name__ == "__main__":
    run("example.html")
