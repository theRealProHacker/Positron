from dataclasses import dataclass
from typing import Literal

from pygame import Vector2
from pygame.rect import Rect

from config import directions
from own_types import Number

# in this file we still use "auto"

t_inset = Number|Literal["auto"]

@dataclass
class Child:
    name: str
    position: str
    outer: Rect
    top: t_inset
    bottom: t_inset
    left: t_inset
    right: t_inset
    def __repr__(self):
        return f"<{self.name}>"

def set_child(child: Child, position: tuple[int,int]):
    print(f"Set {child} at {position}")

def get_rel_inset(child: Child):
    x: Number = child.left if child.left != "auto" else\
        -child.right if child.right != "auto" else 0
    y: Number = child.top if child.top != "auto" else\
        -child.bottom if child.bottom != "auto" else 0
    return Vector2(x,y)

def get_abs_inset(outer_rect: Rect, child: Child):
    x: Number = 0
    if child.left != "auto":
        x = child.left
    elif child.right != "auto":
        x = outer_rect.width - child.right - child.outer.width
    y:Number = 0
    if child.top != "auto":
        y = child.top
    elif child.bottom != "auto":
        y = outer_rect.height - child.bottom - child.outer.height
    return (x,y)

def layout(bounding: Rect, children: list[Child]):
    # in this method we have a bounding rect and then we have a list of elements
    ypos = 0
    flow = lambda child: child.position in ("static", "relative", "sticky")
    no_flow = lambda child: child.position in {"absolute", "fixed"}
    flow_children = [child for child in children if flow(child)]
    no_flow_children = [child for child in children if no_flow(child)]
    for child in flow_children:
        set_child(child, tuple(get_rel_inset(child)+(0, ypos)))
        ypos += child.outer.height
    
    for child in no_flow_children:
        set_child(child, get_abs_inset(bounding, child))

def test():
    bounding = Rect(
        0, 0, 1000, 2096
    )
    defaultdict = dict.fromkeys(directions, "auto")
    children = [
        Child("div1", "relative", Rect(0,0,300,200), **defaultdict|{"top": 30}),
        Child("div2", "relative", Rect(0,0,300,200), **defaultdict|{"left": 50}),
        Child("div3", "fixed", Rect(0,0,300,200), **defaultdict|{"bottom": 300}),
    ]
    layout(bounding, children)
    

test()
