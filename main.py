"""
The main file that runs the browser
"""

import os
import time
from contextlib import redirect_stdout
import logging

with open(os.devnull, "w") as f,redirect_stdout(f):
    import pygame as pg

from os.path import abspath, dirname

import html5lib
from watchdog.events import (DirModifiedEvent, FileModifiedEvent,
                             FileSystemEventHandler)
from watchdog.observers import Observer

import util
from config import g, reset_config
from Element import Element, HTMLElement, apply_rules, create_element
from own_types import Event, Surface, Vector2


class OwnHandler(FileSystemEventHandler):
    def __init__(self, file: str):
        self.file = abspath(file)
        self.last_hit = time.monotonic() # this doesn't need to be accurate
        dir = dirname(self.file)
        # the handler creates its own observer, which might seem weird, but its perfect
        ob = Observer()
        ob.schedule(self, dir)
        ob.start()

    def on_modified(self, event: FileModifiedEvent|DirModifiedEvent):
        if event.src_path == self.file and (t:=time.monotonic())-self.last_hit > 2:
            global reload
            reload = True
            pg.event.post(Event(pg.QUIT))
            self.last_hit = t

def show_image(surf: Surface):
    rect = surf.get_rect(center = DIM/2)
    SCREEN.blit(surf, rect)

pg.init()
W,H = DIM = Vector2((g["W"],g["H"]))
SCREEN = pg.display.set_mode(DIM, pg.RESIZABLE)
g["screen"] = SCREEN
CLOCK = pg.time.Clock()
logging.basicConfig(level=logging.INFO)

running = False
reload = False

def run(file: str):
    global reload
    OwnHandler(file)
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
    if running: raise RuntimeError("Already running")
    running = True
    reset_config()

    html = util.readf(file)
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

        if end: break
        if g["css_rules_dirty"]:
            apply_rules(tree, g["css_rules"])
        if recompute:
            tree.compute()
            tree.layout()

        CLOCK.tick(30)

        SCREEN.fill("white")
        tree.draw(SCREEN, (0,0))
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
    </html>""".strip()
    parsedTree = html5lib.parse(example_html)
    tree: Element = create_element(parsedTree, parent = None)
    print(tree.to_html())
    g["root"] = tree
    # now compute and assert 
    tree.compute()
    tree.layout()

run("example.html")
