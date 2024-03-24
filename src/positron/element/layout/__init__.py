"""
This is layout utilities for Elements

In flow layout there are two layout modes

An element can either layout its children in a block layout.
This means that all children have display: block.

Or an element can layout its children in an inline layout.
Here all children have display: inline

If in the original DOM, block and layout childrens are mixed, we put the inline layout into virtual display boxes.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Iterable, Protocol, Sequence

import positron.element.layout.text_align as text_align
from positron import Box
from positron.Element import Element, TextElement
from positron.Style import calculator
from positron.style.itemgetters import inset_getter

# fmt: off
from positron.types import Auto, AutoLP4Tuple, Coordinate, Float4Tuple, Rect,Surface
# fmt: on
from positron.utils.func import group_by_bool


def calc_inset(inset: AutoLP4Tuple, width: float, height: float) -> Float4Tuple:
    """
    Calculates the inset data
    top, right, bottom, left -> top, bottom, right, left
    """
    top, right, bottom, left = inset
    return calculator.multi2((top, bottom), 0, height) + calculator.multi2(
        (right, left), 0, width
    )


"""
Inline items are items that can appear in inline text.
Generally there are two inline items.
The most common is text. InlineText contains a single word.
The other less common are Elements.
Every InlineElement is a wrapper over one Element.
"""


class InlineItem:
    rect: Rect
    elem: Element

    # implementation detail
    # available after rel_pos
    abs_rect: Rect

    def layout(self, width: float):
        ...

    def rel_pos(self, pos: Coordinate):
        """
        Makes the position that was relative to the parent layout
        be absolute to the screen
        """

    def draw(self, surf: Surface):
        """
        Draws the InlineItem
        """


@dataclass
class InlineText(InlineItem):
    text: str
    elem: Element
    whitespace: bool = True

    def layout(self, _):
        width = (
            self.elem.font.size(self.text)[0] + self.whitespace * self.elem.word_spacing
        )
        self.rect = Rect((0, 0), (width, self.elem.line_height))

    def draw(self, surf: Surface):
        # _descent = next(iter(self.elem.font._fonts_for_chars(self.text)))[
        #     1
        # ].get_descent()
        # descent = Vector2(0, _descent)
        # rect = Rect(self.abs_rect.topleft, self.elem.font.size(self.text))
        # pg.draw.rect(surf, "black", rect, width=1)
        # pg.draw.line(
        #     surf, "black", descent + rect.bottomleft, descent + rect.bottomright
        # )
        self.elem.font.draw(surf, self.abs_rect.topleft, self.text)

    def rel_pos(self, pos: Coordinate):
        self.abs_rect = self.rect.move(pos)  # type: ignore


@dataclass(init=False)
class InlineElement(InlineItem):
    def __init__(self, element: Element):
        self.elem = element

    def layout(self, width):
        self.elem.layout(width)
        # TODO: difference between box.outer_box (for space reservation)
        # and box.border_box (for collision)
        self.rect = self.elem.box.outer_box

    def rel_pos(self, pos: Coordinate):
        self.abs_rect = self.rect.move(pos)  # type: ignore
        self.elem.box.pos += self.abs_rect.topleft

    def draw(self, surf: Surface):
        self.elem.draw(surf)


"""
Different layout strategies
"""


class Layout:
    """
    A Layout is a way a list of Elements can be layouted

    Currently we only implement flow layout
    which consists of InlineLayout and BlockLayout
    """

    height: float

    def layout(self, width: float):
        ...

    def rel_pos(self, pos):
        ...

    def draw(self, surf: Surface):
        ...

    def collide(self, pos: Coordinate) -> Element | None:
        ...


class EmptyLayout(Layout):
    height = 0


class RealLayoutItems(Protocol):
    def rel_pos(self, pos: Coordinate):
        ...

    def draw(self, surf: Surface):
        ...


class RealLayout(Layout):
    """
    A "real" layout has a list of items and an elem.

    Items need to implement rel_pos and draw.
    """

    elem: Element
    items: Sequence[RealLayoutItems]

    def rel_pos(self, pos):
        for item in self.items:
            item.rel_pos(pos)

    def draw(self, surf: Surface):
        for item in self.items:
            item.draw(surf)

    def __bool__(self):
        return bool(self.items)


@dataclass(init=False)
class InlineLayout(RealLayout):
    elem: Element
    items: Sequence[InlineItem]

    def __init__(self, parent: Element, elems: Iterable[Element | TextElement]):
        self.elem = parent
        items: list[InlineItem] = []
        for elem in elems:
            if isinstance(elem, Element):
                items.append(InlineElement(elem))
            elif isinstance(elem, TextElement):
                text_items = [InlineText(w, elem.parent) for w in elem.text.split()]
                if not text_items:
                    if items and isinstance(last_text_item := items[-1], InlineText):
                        last_text_item.whitespace = True
                    continue
                last_item = text_items[-1]
                if elem.text.endswith(last_item.text):
                    last_item.whitespace = False
                items.extend(filter(None, text_items))
        self.items = items

    def layout(self, width: float):
        x = 0
        y = 0

        current_line: list[InlineItem] = []

        def line_break():
            nonlocal x, y
            if current_line:
                height = max(item.rect.height for item in current_line)
                widths = [item.rect.width for item in current_line]
                alignment = text_align.align_by(
                    self.elem.cstyle["text-align"], width, widths
                )
                assert len(widths) == len(alignment)
                for newx, item in zip(alignment, current_line):
                    item.rect.x = newx
                    item.rect.y = y
                x = 0
                y += height
                current_line.clear()

        for item in self.items:
            item.layout(width)
            if x + item.rect.width > width:
                line_break()
            item.rect.left = x
            x += item.rect.width
            current_line.append(item)

        line_break()
        self.height = y
        box = self.elem.box
        if box.height == -1:
            box.set_height(y, "content")
        return self

    def draw(self, surf: Surface):
        super().draw(surf)
        ...  # TODO: draw outlines

    def collide(self, pos):
        for item in self.items:
            if item.abs_rect.collidepoint(pos):
                return item.elem
        return None


Child = Element | TextElement


def margin_collapsing(last: float, current: float):
    # XXX: There is no float, clear and no negative margins
    return min(last, current)


@dataclass(init=False)
class BlockLayout(RealLayout):
    elem: Element
    items: list[Element | VirtualBlock]

    def __init__(self, elem: Element, children: list[Child]) -> None:
        self.elem = elem
        items = deque[Element | VirtualBlock]()
        children: deque[Child] = deque(children)
        inline_elements = deque[Child]()

        # ugly but okay
        while children:
            while children and children[0].display == "inline":
                inline_elements.append(children.popleft())
            if inline_elements:
                items.append(VirtualBlock(elem, list(inline_elements)))
                inline_elements.clear()
            while children and children[0].display == "block":
                child = children.popleft()
                assert not isinstance(child, TextElement)
                items.append(child)

        self.items = [item for item in items if item]

    def layout(self, width: float):
        box = self.elem.box
        inner: Rect = box.content_box
        # https://developer.mozilla.org/en-US/docs/Web/CSS/CSS_Box_Model/Mastering_margin_collapsing
        flow, no_flow = group_by_bool(
            self.items,
            lambda x: x.position in ("static", "relative", "sticky"),
        )
        y_cursor: float = 0
        last_margin: float = 0
        if flow:
            # margin-collapsing with margin-top of first child
            if not box.padding[Box.top] and not box.border[Box.top]:
                last_margin = box.margin[0]
            for child in flow:
                child.layout(inner.width)
                current_margin = child.box.margin
                # margin collapsing for empty boxes
                if child.box.border_box.height == 0:
                    y_cursor -= margin_collapsing(*current_margin[Box._vertical])  # type: ignore
                y_cursor -= margin_collapsing(last_margin, current_margin[Box.top])
                last_margin = current_margin[Box.bottom]
                child.box.set_pos((0, y_cursor))
                y_cursor += child.box.outer_box.height
        if box.height == -1:
            # margin-collapsing with margin-bottom of last child
            if not box.padding[Box.bottom] and not box.border[Box.bottom]:
                y_cursor -= margin_collapsing(last_margin, box.margin[Box.bottom])
            box.set_height(y_cursor, "content")
        self.height = y_cursor
        for child in no_flow:
            child.layout(inner.width)
            # calculate position
            top, bottom, right, left = calc_inset(
                inset_getter(self.elem.cstyle), box.width, box.height
            )
            child.box.set_pos(
                (
                    (
                        top
                        if top is not Auto
                        else (
                            self.elem.get_height() - bottom if bottom is not Auto else 0
                        )
                    ),
                    (
                        left
                        if left is not Auto
                        else inner.width - right
                        if right is not Auto
                        else 0
                    ),
                )
            )

    def collide(self, pos: Coordinate):
        for item in reversed(self.items):
            if target := item.collide(pos):
                return target


"""
Virtual block
"""


@dataclass(init=False)
class VirtualBlock:
    """
    A VirtualBlock is used to group a list of inline elements into a Block
    (text, <span>, <img>, ...)

    Then layouts and renders them
    """

    display = "block"
    position = "static"

    def __init__(self, parent: Element, elems: list[Element | TextElement]):
        self.elem = parent
        items: list[Element | TextElement] = []
        for item in elems:
            if isinstance(item, Element):
                items.extend(item.iter_inline())
            else:
                items.append(item)
        self.items = [item for item in items if item.text.strip()]

    def layout(self, width: float):
        self.box = Box.Box(
            "content-box",
            width=width,
            height=-1,
        )
        # XXX: We implement the API that InlineLayout needs (box here, rest in the __getattr__)
        self.inline_layout = InlineLayout(self, self.items)  # type: ignore
        self.inline_layout.layout(width)

    def rel_pos(self, pos: Coordinate):
        self.box.pos += pos
        self.inline_layout.rel_pos(self.box.pos)

    def draw(self, surf: Surface):
        self.inline_layout.draw(surf)

    def collide(self, pos: Coordinate):
        return self.inline_layout.collide(pos)

    def __getattr__(self, name: str):
        if name in ("cstyle",):
            return getattr(self.elem, name)
        return NotImplemented

    def __bool__(self):
        return bool(self.items)
