import html5lib
import pygame as pg

import util
from config import g
from own_types import Vector2, Surface
from Element import Element, create_element

# abstract

pg.init()
W,H = DIM = Vector2((g["W"],g["H"]))
screen = pg.display.set_mode(DIM)

def show_image(surf: Surface):
    rect = surf.get_rect(center = DIM/2)
    screen.blit(surf, rect)

def main():
    clock = pg.time.Clock()

    example_html = util.readf("example.html")
    parsedTree = html5lib.parse(example_html)
    tree = create_element(parsedTree)
    util.print_tree(tree)
    g["root"] = tree

    tree.compute()
    tree.layout() # the first element doesn't need any input

    print(tree.select_one("body").box.content)

    p = tree.select_one("p")
    print(p.box.outer)
    print(p.box.content)

    time_sum = frames = 0
    end = False
    while True:
        for event in pg.event.get():
            if event.type == pg.QUIT:
                end = True
        if end: break

        time_sum += clock.tick(30)
        frames += 1

        screen.fill("white")
        tree.draw(screen, (0,0))
        pg.display.flip()
    time_sum /= 1000 # seconds
    mean_time = time_sum/frames
    print(f"Mean time/frame: {mean_time}")
    print(f"FPS: {1/mean_time}")

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

main()
