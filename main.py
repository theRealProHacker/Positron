import pygame as pg
import util
from Element import Element, create_element
import html5lib
from config import g
# abstract

pg.init()
W,H = DIM = pg.Vector2((g["W"],g["H"]))
screen = pg.display.set_mode(DIM)

def show_image(surf: pg.Surface):
    rect = surf.get_rect(center = DIM/2)
    screen.blit(surf, rect)

def main():
    clock = pg.time.Clock()

    example_html = util.readf("example.html")
    parsedTree = html5lib.parse(example_html)
    tree = create_element(parsedTree)
    util.print_tree(tree)
    g["root"] = tree

    while True:
        for event in pg.event.get():
            if event.type == pg.QUIT:
                return
            elif event.type == pg.MOUSEBUTTONDOWN:
                return

        clock.tick(1)

        tree.compute()
        tree.layout() # the first element doesn't need any input
        screen.fill("white")
        tree.draw(screen, (0,0)) # actually draws/paints to the screen
        pg.display.flip()

# main()

def test():
    # setup code
    example_html = """
    <html>
        <head>
            <p style="color: green">My example Text GgOT</p>
        </head>
        <body style="background-color: lightblue">
            <p style="color: green; width: auto">My example Text GgOT</p>
            Text
            <p>now a paragraph</p>
            and Text again  
        </body>
    </html>""".strip()
    parsedTree = html5lib.parse(example_html)
    util.print_parsed_tree(parsedTree, with_text=True)
    tree: Element = create_element(parsedTree, parent = None)
    print(tree.to_html())
    # util.print_tree(tree)
    # print(tree.to_html())
    # g["root"] = tree
    # # now compute and assert 
    # tree.compute()
    # assert len(tree.children) == 2 # head and body
    # elem = tree.children[1]
    # assert elem.tag == "body"
    # assert len(elem.children) == 3 # two ps and one text elements
    # elem = elem.children[0]
    # assert elem.tag == "p"
    # assert elem._style["width"] == "auto"
    # assert elem.text == "My example Text GgOT"
    # elem = tree.children[0]
    # util.print_tree(elem)

test()