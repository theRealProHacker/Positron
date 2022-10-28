"""
The Element class and its descendants
"""

# fmt: off
from __future__ import annotations

import asyncio
import operator
import os
import re
from contextlib import suppress
from dataclasses import dataclass, field
from functools import cache, partial
from itertools import chain
from typing import Callable, Iterable, Protocol

import pygame as pg
import lxml.html.html5parser as html5

import Box
import Media
import rounded_box
import Style
import util
from config import add_sheet, cursors, g, input_type_check_res
from ElementAttribute import (BooleanAttribute, ClassListAttribute,
                              DataAttribute, GeneralAttribute, InputValueAttribute,
                              NumberAttribute, Opposite, RangeAttribute, SameAs)
from own_types import (V_T, Auto, AutoLP4Tuple, AutoType, BugError, Color,
                       Coordinate, Cursor, DisplayType, Element_P, Float4Tuple,
                       Font, FontStyle, Leaf_P, Length, Number, Percentage,
                       Rect, Surface, Vector2)
from Style import (FullyComputedStyle, SourceSheet, bs_getter, bw_keys,
                   calculator, has_prio, inset_getter, is_custom,
                   pack_longhands, parse_file, parse_sheet)
from util import (GeneralParser, draw_text, get_tag, goto, group_by_bool, log_error,
                  make_default, text_surf, whitespace_re)

# fmt: on
parser = html5.HTMLParser()

################################# Globals ###################################
class InlineItem(Protocol):
    xpos: float = 0
    ypos: float = 0
    width: float
    height: float

    def rel_pos(self, pos: Coordinate):
        pass

    def draw(self, surf: Surface):
        """
        Draws the InlineItem
        """


@dataclass
class TextDrawItem(InlineItem):
    text: str
    parent: Element
    whitespace: bool = True
    extra_style: FullyComputedStyle = field(default_factory=dict)

    @property
    def pos(self):
        return self.xpos, self.ypos

    def draw(self, surf: Surface):
        style = self.parent.cstyle | dict(self.extra_style)
        draw_text(
            surf,
            self.text,
            self.parent.font,
            style["color"],
            topleft=self.pos,
        )

    def rel_pos(self, pos: Coordinate):
        self.xpos, self.ypos = Vector2(pos) + (self.xpos, self.ypos)

    @property
    def width(self):
        return (
            self.parent.font.size(self.text)[0]
            + self.whitespace * self.parent.word_spacing
        )

    @property
    def height(self):
        return self.parent.line_height


@dataclass
class ElementDrawItem(InlineItem):
    elem: Element

    @property
    def width(self):
        return self.elem.box.outer_box.width

    @property
    def height(self):
        return self.elem.box.outer_box.height

    def rel_pos(self, pos: Coordinate):
        self.xpos, self.ypos = new_pos = Vector2(pos) + (self.xpos, self.ypos)
        self.elem.box.set_pos(new_pos)

    def draw(self, surf: Surface):
        self.elem.draw(surf)


# TODO: Get an actually acceptable font and also give a list of possible fonts
@cache
def get_font(family: list[str], size: float, style: FontStyle, weight: int) -> Font:
    """
    Takes some font constraints and tries to find the most fitting
    """
    _font: str | None = pg.font.match_font(
        name=family,
        italic=style.value == "italic",
        bold=weight > 500,  # we don't support actual weight TODO
    ) or log_error("Failed to find font", family, style, weight)
    font: Font = Font(_font, int(size))
    font.italic = style.value == "oblique"
    return font


def calc_inset(inset: AutoLP4Tuple, width: float, height: float) -> Float4Tuple:
    """
    Calculates the inset data
    top, right, bottom, left -> top, bottom, right, left
    """
    top, right, bottom, left = inset
    return calculator.multi2((top, bottom), 0, height) + calculator.multi2(
        (right, left), 0, width
    )


def set_title():
    head = g["root"].children[0]
    titles = [title.text for title in head.children if title.tag == "title"]
    if titles:
        pg.display.set_caption(titles[-1])


class NotEditable(ValueError):
    pass


word_re = re.compile(r"[^\s]+")
########################## Element ########################################
# common operations on Elements. TODO
# def find_first_common_ancestor()


class Element(Element_P):
    """
    The Element represents a general HTML-Element
    """

    # General
    tag: str = ""
    attrs: dict[str, str]
    children: list[Element | TextElement]
    parent: Element | None
    id = GeneralAttribute("id")
    class_list = ClassListAttribute()
    data = DataAttribute()
    # Style
    istyle: Style.Style  # inline style
    estyle: Style.Style  # external style
    cstyle: Style.FullyComputedStyle  # computed_style
    # Layout + Draw
    box: Box.Box
    line_height: float
    word_spacing: float
    display: DisplayType
    layout_type: DisplayType
    position: str
    cursor: Cursor
    # Not always present
    inline_items: list[InlineItem]  # only if layout_type is "inline"
    # Dynamic states https://html.spec.whatwg.org/multipage/semantics-other.html#pseudo-classes
    @property
    def active(self) -> bool:
        return self is g["event_manager"].active

    @property
    def focus(self) -> bool:
        return self is g["event_manager"].focus

    @property
    def hover(self) -> bool:
        return self is g["event_manager"].hover

    @property
    def target(self) -> bool:
        return self is g["target"]

    defined: bool = True

    @property
    def empty(self) -> bool:
        return not self.children and self.text.isspace()

    # <a>, <area>
    visited: bool = False
    link: bool = False
    all_link: bool = False  # TODO: do we really need this? Isn't `[href]` sufficient?
    # input elements and their associated form elements
    changed: bool = False  # Not on spec but an extremely cool suggestion
    enabled: bool = False
    disabled: bool = False
    checked: bool = False
    blank: bool = False
    placeholder_shown: bool = False
    valid: bool = False
    invalid: bool = False
    required: bool = False
    optional: bool = False

    @property
    def first_child(self):
        return self.parent and self.parent.children and self.parent.children[0] is self

    @property
    def last_child(self):
        return self.parent and self.parent.children and self.parent.children[-1] is self

    @property
    def only_child(self):
        return self.parent and len(self.parent.children) == 1

    def __init__(
        self, tag: str, attrs: dict[str, str], children: list[Element | TextElement]
    ):
        if self.tag:
            assert self.tag == tag
        else:
            self.tag = tag
        self.attrs = attrs
        self.children = children
        self.parent = None
        self.istyle = Style.parse_inline_style(attrs.get("style", ""))

        for c in children:
            c.parent = self

    @classmethod
    def from_lxml(cls, lxml) -> Element:
        tag = get_tag(lxml)
        type_: type[Element] = elem_type_map.get(tag, Element)
        text = lxml.text or ""
        attrs = dict(lxml.attrib)
        children: list[Element | TextElement] = []
        if text:
            children.append(TextElement(text))
        for _c in lxml:
            c = Element.from_lxml(_c)
            children.append(c)
            if text := _c.tail:
                children.append(TextElement(text))
        return type_(tag, attrs, children)

    def set_attr(self, name: str, value: str):
        self.attrs[name] = value
        if name == "style":
            self.istyle = Style.parse_inline_style(value)
        elif name in ("id", "class"):
            pass  # TODO: add and remove element to and from the global map

    ####################################  Main functions ######################################################
    @property
    def input_style(self) -> Style.ResolvedStyle:
        """The total input style. Fused from inline and external style"""
        return Style.remove_importantd(Style.join_styles(self.istyle, self.estyle))

    def apply_style(self, sheet: SourceSheet):
        # Alternatives:
        # 1. CSSOM as a tree (this is how most browsers do it and probably the best way)
        # 2.
        # elems = [*self.iter_desc()]
        # def get_elems(selector, elems):
        #     match selector:
        #         case Selector.IdSelector(id):
        #             return g["id_map"][id] | elems
        #         ...
        # for selector, style in rules:
        #     for elem in get_elems(selector, elems):
        #         elem.estyle = Style.join_styles(elem.estyle, style)
        # 3. (current)
        # sort all rules by the selectors specificities
        rules = sorted(
            sheet.all_rules,
            key=lambda rule: rule[0].spec,
        )
        for elem in self.iter_desc():
            # chain all matching styles and sort their properties by importance
            elem.estyle = dict(
                sorted(
                    chain.from_iterable(
                        style.items() for selector, style in rules if selector(elem)
                    ),
                    key=lambda t: Style.is_imp(t[1]),
                )
            )

    def compute(self):
        """
        Assembles the input style and then converts it into the Elements computed style.
        It then computes all the childrens styles
        """
        input_style = Style.get_style(self.tag) | self.input_style
        parent_style = (
            dict(self.parent.cstyle)
            if self.parent
            else {
                "font-size": g["default_font_size"],
                "color": "black",
            }
        )
        # inherit any custom properties from parent
        for k, v in parent_style.items():
            if is_custom(k):
                input_style.setdefault(k, v)
        # compute keys
        keys = sorted(input_style.keys(), key=has_prio, reverse=True)
        style: Style.FullyComputedStyle = {}
        for key in keys:
            val = input_style[key]
            new_val = Style.compute_style(self.tag, val, key, parent_style)
            style[key] = new_val
            if has_prio:
                parent_style[key] = new_val
        # corrections
        for bw_key, bstyle in zip(bw_keys, bs_getter(style)):
            if bstyle in ("none", "hidden"):
                style[bw_key] = Length(0)
        if style["outline-style"] in ("none", "hidden"):
            style["outline-width"] = Length(0)
        self.display = str(style["display"])
        # fonts
        fsize: float = style["font-size"]
        self.font = get_font(
            style["font-family"], fsize, style["font-style"], style["font-weight"]
        )
        # https://developer.mozilla.org/en-US/docs/Web/CSS/line-height#values
        lh: AutoType | float | Length | Percentage = style["line-height"]
        self.line_height = (
            lh * fsize
            if isinstance(lh, Number)
            else calculator(lh, auto_val=self.font.get_linesize(), perc_val=fsize)
        )
        # https://developer.mozilla.org/en-US/docs/Web/CSS/word-spacing#values
        wspace = style["word-spacing"]
        wspace: float | Percentage = Percentage(100) if wspace is Auto else wspace
        d_ws = self.font.size(" ")[0]
        self.word_spacing = (calculator(wspace, 0, d_ws)) + d_ws
        self.position = str(style["position"])
        cursor: Cursor | AutoType = style["cursor"]
        self.cursor = (
            (Cursor() if self.parent is None else self.parent.cursor)
            if cursor is Auto
            else cursor
        )
        # style sharing and child computing
        self.cstyle = g["cstyles"].add(style)
        for child in self.children:
            child.compute()

    def is_block(self) -> bool:
        """
        Returns whether an element is a block.
        Includes side effects (as a feature) that automatically adjust false inline elements to block layout
        """
        children = self.display_children
        if self.display != "none":
            if any(
                [child.is_block() for child in children]
            ):  # set all children to block
                self.display = "block"
                for child in children:
                    child.display = "block"
        self.layout_type = self.display
        return self.display == "block"

    def get_height(self) -> float:
        """
        Gets the known height
        """
        # -1 is a sentinel for height not set yet
        return (
            self.box.height
            if self.box.height != -1
            else self.parent.get_height()
            if self.parent is not None
            else 0
        )

    def layout(self, width: float) -> None:
        """
        Layout an element. Gets the width it has available
        """
        self.layout_type = self.display
        if self.display == "none":
            return
        style = self.cstyle
        parent_size = (
            (self.parent.box.width, self.parent.get_height()) if self.parent else (0, 0)
        )
        self.box, set_height = Box.make_box(width, style, *parent_size)
        self.layout_children(set_height)

    def layout_children(self, set_height: Callable[..., None]):
        """
        We layout the children.
        """
        children = self.display_children
        if not children:
            set_height(0)
        elif any(c.display == "inline" for c in children):
            self.layout_type = "inline"
            width = self.box.content_box.width
            xpos: float = 0
            ypos: float = 0
            current_line: list[InlineItem] = []
            items: list[InlineItem] = []

            def line_break(explicit: None | Element = None):
                nonlocal xpos, ypos  # , current_line, items
                xpos = 0
                for item in current_line:
                    item.ypos = ypos
                items.extend(current_line)
                line_height = max((item.height for item in current_line), default=0)
                ypos += line_height or getattr(explicit, "line_height", 0)
                current_line.clear()

            def add_item(item: InlineItem):
                nonlocal xpos  # , current_line
                item_width = item.width
                if xpos + item_width > width:
                    line_break()
                item.xpos = xpos
                item.ypos = ypos
                current_line.append(item)
                xpos += item_width

            for elem in self.iter_inline():
                if isinstance(elem, TextElement):
                    c = elem.parent
                    parser = GeneralParser(elem.text.lstrip())
                    while parser.x:
                        if word := parser.consume(word_re):
                            has_whitespace = bool(parser.consume(whitespace_re))
                            add_item(TextDrawItem(word, c, whitespace=has_whitespace))
                else:
                    elem.layout(width)
                    add_item(ElementDrawItem(elem))
            line_break()
            set_height(ypos)
            self.inline_items = items
        else:
            inner: Rect = self.box.content_box
            x_pos = inner.x
            y_cursor = inner.y
            # https://developer.mozilla.org/en-US/docs/Web/CSS/CSS_Box_Model/Mastering_margin_collapsing
            flow, no_flow = group_by_bool(
                children,
                lambda x: x.position in ("static", "relative", "sticky"),
            )
            for child in flow:
                child.layout(inner.width)
                # top, bottom, right, left = calc_inset(
                #     inset_getter(c.cstyle), self.box.width, self.box.height
                # )
                child.box.set_pos(
                    # (
                    #     (x_pos, y_cursor)
                    #     if child.position == "sticky"
                    #     else (bottom - top + x_pos, right - left + y_cursor)
                    # )
                    (x_pos, y_cursor)
                )
                y_cursor += child.box.outer_box.height
            set_height(y_cursor)
            for child in no_flow:
                child.layout(inner.width)
                # calculate position
                top, bottom, right, left = calc_inset(
                    inset_getter(self.cstyle), self.box.width, self.box.height
                )
                child.box.set_pos(
                    (
                        (
                            top
                            if top is not Auto
                            else self.get_height() - bottom
                            if bottom is not Auto
                            else 0
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

    def rel_pos(self, pos: Coordinate):
        self.box.pos += pos
        content_pos = self.box.content_box.topleft
        items: list[Element | TextElement] | list[InlineItem] = (
            self.display_children if self.layout_type == "block" else self.inline_items
        )
        for item in items:
            item.rel_pos(content_pos)

    def draw(self, surf: Surface):
        """
        Draws the element to the `surf`
        """
        if self.display == "none":
            return
        style = self.cstyle
        # https://web.dev/howbrowserswork/#the-painting-order
        # 1.+2.+3.
        rounded_box.draw_bg_and_border(surf, self.box, style)
        # 4.
        self.draw_content(surf)
        # 5.
        rounded_box.draw_outline(surf, self.box, style)

    def draw_content(self, surf: Surface):
        # concept: the children should already know, where they belong
        items: list[Element | TextElement] | list[InlineItem] = (
            self.children if self.layout_type == "block" else self.inline_items
        )
        for item in items:
            item.draw(surf)

    # Events
    def collide(self, pos: Coordinate) -> Element | None:
        """
        The idea of this function is to get which elements were hit by a mouse event
        """
        # TODO: z-index
        # TODO: collide should only return a single Element, which parents can later be iterated over.
        if self.layout_type == "block":
            for c in self.display_children:
                if target := c.collide(pos):
                    return target
        elif self.layout_type == "inline":
            for item in reversed(self.inline_items):
                if isinstance(item, ElementDrawItem):
                    if target := item.elem.collide(pos):
                        return target
                elif isinstance(item, TextDrawItem):
                    if Rect(item.pos, (item.width, item.height)).collidepoint(
                        pos  # type: ignore
                    ):
                        return item.parent
        if self.box.border_box.collidepoint(pos):
            return self
        return None

    def editcontent(self, func: Callable[[str], str]):
        if self.attrs.get("contenteditable", "false") == "false":
            raise NotEditable
        # TODO: change own text if contenteditable set to True.

    def delete(self):
        self.deleted = True
        self.parent = None
        for c in self.children:
            c.delete()
        self.children.clear()

    ###############################  I/O for Elements  ##################################################################
    @property
    def text(self):
        """All the text in the element"""
        return " ".join(c.text for c in self.children)

    def to_html(self, indent=0):
        """Convert the element back to formatted html"""
        # TODO: handle differently depending on display block or inline
        attrs = [f'{k}="{v}"' for k, v in self.attrs.items()]
        indentation = " " * indent
        body = f"{self.tag} {' '.join(attrs)}".strip()
        if self.children:
            children = f"\n".join(c.to_html(indent + 2) for c in self.children)
            return f"""{indentation}<{body}>
{children}
{indentation}</{self.tag}>"""
        else:
            return f"{indentation}<{body}></{self.tag}>"  # self-closing tag

    __repr__ = to_html

    def __str__(self):
        return f"<{self.tag}>"

    def style_repr(self):
        """
        Represents the elements style in a nice way for debugging
        """
        out_style = pack_longhands(
            {
                k: f"{_in}->{_out}" if _in != (_out := self.cstyle[k]) else str(_in)
                for k, _in in self.input_style.items()
            }
        )
        for k, v in out_style.items():
            print(f"{k}: {v}")

    ############################## Helpers #####################################
    def iter_anc(self) -> Iterable[Element]:
        """Iterates over all ancestors *excluding* this element"""
        elem = self
        while (parent := elem.parent) is not None:
            yield parent
            elem = parent
            elem = parent

    def iter_desc(self) -> Iterable[Element]:
        """Iterates over all descendants *including* this element"""
        yield self
        yield from chain.from_iterable(
            c.iter_desc() for c in self.children if not isinstance(c, TextElement)
        )

    def iter_siblings(self) -> Iterable[Element]:
        """
        Iterates over siblings including self
        """
        if self.parent:
            yield from (
                c for c in self.parent.children if not isinstance(c, TextElement)
            )

    def iter_inline(self) -> Iterable[Element | TextElement]:
        """
        Alternative iteration over all descendants
        used in text layout.
        Shouldn't be called out of this context.
        """
        if self.display == "none":
            return
        for c in self.display_children:
            if isinstance(c, TextElement):
                yield c
            else:
                yield from c.iter_inline()

    @property
    def display_children(self):
        return [child for child in self.children if child.display != "none"]

    @property
    def real_children(self):
        """
        All direct children that are not MetaElements or TextElements
        """
        return [
            c for c in self.children if not isinstance(c, (TextElement, MetaElement))
        ]


class HTMLElement(Element):
    """
    Represents the exact <html> element
    """

    tag = "html"

    @classmethod
    def from_string(cls, html: str):
        _root = html5.document_fromstring(html, parser=parser)
        print(type(_root))
        return cls.from_lxml(_root)

    def get_height(self) -> float:
        return self.box.height

    def layout(self):
        self.box = Box.Box(t="content-box", width=g["W"], height=g["H"])
        # all children correct their display
        assert self.is_block()
        super().layout_children(partial(setattr, self.box, "height"))
        # all children correct their position
        super().rel_pos((0, 0))

    def draw(self, screen):
        for c in self.children:
            c.draw(screen)


class AnchorElement(Element):
    """
    <a>
    """

    @property
    def link(self):
        return (href := self.attrs.get("href")) and href not in g["visited_links"]

    @property
    def visited(self):
        return (href := self.attrs.get("href")) and href in g["visited_links"]

    @property
    def all_link(self):
        return "href" in self.attrs

    def on_click(self):
        if href := self.attrs.get("href"):
            goto(href)
        else:
            log_error("Anchor without href clicked")

    def on_auxclick(self):
        # Always new tab?
        if href := self.attrs.get("href"):
            goto(href)
        else:
            log_error("Anchor without href alt-clicked")

    def on_drag_start(self):
        pass


class MetaElement(Element):
    """
    A MetaElement is an Element thats sole purpose is conveying information
    to the runtime and is not for display or interaction.
    It has no style, the display is "none"

    Examples for MetaElements are:
    `title`, `link`, `style` and also `meta` or `script` (not implemented)
    """

    display: DisplayType = "none"

    def compute(self):
        pass


class StyleElement(MetaElement):
    tag = "style"
    inline_sheet: SourceSheet | None = None
    src_sheet: SourceSheet | None = None

    def __init__(
        self, tag: str, attrs: dict[str, str], children: list[Element | TextElement]
    ):
        super().__init__(tag, attrs, children)
        if (src := attrs.get("src")) is not None:
            if os.path.isfile(src):
                g["event_manager"].on("file-modified", self.reload_src, path=src)
            util.create_task(parse_file(src), True, self.parse_callback)
        if self.text:
            self.inline_sheet = parse_sheet(self.text)
            add_sheet(self.inline_sheet)

    def parse_callback(self, future: asyncio.Future):
        with suppress(Exception):
            self.src_sheet = future.result()
            add_sheet(self.src_sheet)

    def reload_src(self, event):
        g["css_sheets"].remove(self.src_sheet)
        util.create_task(parse_file(event.path), True, self.parse_callback)


class CommentElement(MetaElement):
    tag = "!comment"

    def to_html(self, indent=0):
        return f"{' '*indent}<!--{self.text}-->"

    def __repr__(self):
        return self.to_html()


class LinkElement(MetaElement):
    # attrs: rel, href, (media, disabled, sizes, title)
    tag = "link"
    src_sheet: SourceSheet | None = None

    def __init__(
        self, tag: str, attrs: dict[str, str], children: list[Element | TextElement]
    ):
        super().__init__(tag, attrs, children)
        # https://developer.mozilla.org/en-US/docs/Web/HTML/Element/link
        # TODO:
        # media -> depends on media query support
        rel = attrs.get("rel")
        src = attrs.get("href")
        if rel == "stylesheet" and src:
            # TODO: disabled ?
            # TODO: title ?
            g["event_manager"].on("file-modified", self.on_change, path=src)
            util.create_task(parse_file(src), True, self.parse_callback)
        elif rel == "icon" and src:
            # TODO: sizes ?
            g["icon_srcs"].append(src)

    def parse_callback(self, future: asyncio.Future):
        with suppress(Exception):
            self.src_sheet = future.result()
            add_sheet(self.src_sheet)

    def on_change(self, event):
        g["css_sheets"].remove(self.src_sheet)
        util.create_task(parse_file(event.path), True, self.parse_callback)


class ReplacedElement(Element):
    def iter_inline(self) -> Iterable[Element | TextElement]:
        yield self


class ImageElement(ReplacedElement):
    # attrs: src, loading, decoding, width, height
    size: None | tuple[int, int]
    given_size: tuple[int | None, int | None]
    image: Media.Image | None

    def __init__(
        self, tag: str, attrs: dict[str, str], children: list[Element | TextElement]
    ):
        # https://developer.mozilla.org/en-US/docs/Web/HTML/Element/img
        # TODO:
        # source element
        # usemap: points to a map
        # urls = [] # TODO: actually fetch the images depending on the srcset and sizes
        super().__init__(tag, attrs, children)
        try:
            self.image = Media.Image(
                attrs["src"],
                load=attrs.get("loading", "eager") != "lazy",
                # "auto" is synonymous with "async"
                sync=attrs.get("decoding", "async") == "sync",
            )
        except (KeyError, ValueError):
            self.image = None

    @staticmethod
    def crop_image(surf: Surface, to_size: Coordinate):
        """
        Makes an image fit the `to_size`
        """
        # TODO: don't just scale but also cut out, because scaling might ruin the image
        if surf.get_size() == to_size:
            pass
        return pg.transform.scale(surf, to_size)

    def layout(self, width):
        if self.display == "none" or self.image is None:
            return
        # the width and height are determined in the following order
        # 1. css-box-properties if not Auto
        # 2. width and height attributes set on the image
        # 3. The elements intrinsic size
        intrw, intrh = (
            self.image.surf.get_size() if self.image.is_loaded else (None, None)
        )
        w = make_default(
            int(w) if (w := self.attrs.get("width")) is not None else None,
            make_default(intrw, 0),
        )
        h = make_default(
            int(h) if (h := self.attrs.get("height")) is not None else None,
            make_default(intrh, 0),
        )
        self.box, set_height = Box.make_box(
            w, self.cstyle, self.parent.box.width, self.parent.get_height()
        )
        set_height(h)

    def draw(self, surf: Surface):
        if self.image is None:
            return
        super().draw(surf)

    def draw_content(self, surf: Surface):
        assert self.image is not None
        if self.image.is_loaded:
            surf.blit(
                self.crop_image(self.image.surf, (self.box.width, self.box.height)),
                self.box.pos,
            )


class AudioElement(ReplacedElement):
    # attrs: src, preload, loop, (autoplay, controls, muted, preload)
    def __init__(
        self, tag: str, attrs: dict[str, str], children: list[Element | TextElement]
    ):
        # https://developer.mozilla.org/en-US/docs/Web/HTML/Element/audio
        # TODO:
        # autoplay: right now autoplay is always on
        # controls: both draw and event handling
        # muted: right now muted is always off
        # preload: probably not gonna implement fully (is only a hint)
        super().__init__(tag, attrs, children)
        try:
            self.audio = Media.Audio(
                attrs["src"],
                load=attrs.get("preload", "auto") not in ("none", "metadata"),
                autoplay=True,
                loop="loop" in attrs,
            )
        except (KeyError, ValueError):
            self.image = None


class InputElement(ReplacedElement):
    """
    attributes
    TODO:
        disabled, form, list, readonly, autofocus?
    TODO:
        accept -> file
        max, min, step
    """

    # fmt: off
    type = RangeAttribute("type", range = {
        "text", "tel", "password", "number", "email", "url", "search",
        "checkbox", "radio",
        "file", "color", "hidden"
    }, default="text")
    value = InputValueAttribute()
    # fmt: on
    maxlength = NumberAttribute("maxlength", default=float("inf"))
    minlength = NumberAttribute("minlength")
    multiple = BooleanAttribute("multiple")
    # States
    changed: bool = False
    checked: bool = False
    enabled: bool = Opposite("disabled")
    disabled: bool = BooleanAttribute("disabled")

    @property
    def blank(self):
        return not self.attrs.get("value")  # value is either not set or empty.

    placeholder_shown: bool = SameAs(
        "blank"
    )  # TODO: Does the input need to have a placeholder set for this to fire?

    @property
    def valid(self):
        type_ = self.type
        value = self.attrs.get("value", "")
        if (default_pattern := input_type_check_res.get(type_)) is not None:
            if not value:
                return not self.required
            elif len(value) > self.maxlength:
                return False
            elif len(value) < self.minlength:
                return False
            values = (
                [value]
                if not (type_ in ("email", "file") and self.multiple)
                else re.split(r"\s*,\s*", value)
            )
            if (pattern := self.attrs.get("pattern")) is not None and any(
                not re.fullmatch(pattern, value) for value in values
            ):
                return False
            if not all(default_pattern.fullmatch(value) for value in values):
                return False
        if type_ == "number":
            value = value or "0"
            for constraint, op in [
                ("max", operator.gt),
                ("min", operator.lt),
            ]:
                if constr := self.attrs.get(constraint):
                    with suppress(ValueError):
                        if op(float(value), float(constr)):
                            return False
        return True

    invalid: bool = Opposite("valid")
    required = BooleanAttribute("required")
    optional: bool = Opposite("required")

    def __init__(self, *args):
        super().__init__(*args)
        if "checked" in self.attrs:
            self.checked = True

    def collide(self, pos: Coordinate) -> Element | None:
        return self if self.box.border_box.collidepoint(pos) else None

    def compute(self):
        super().compute()
        if self.cstyle["cursor"] is Auto:
            self.cursor = cursors["text"]  # TODO: change this for other input types
        if self.type == "hidden":
            self.display = "none"

    def layout(self, width: float):
        if not self.parent:
            self.display = "none"
            self.layout_type = "none"
            return
        type_ = self.type
        self.layout_type = "inline"
        self.box, set_height = Box.make_box(
            width, self.cstyle, self.parent.box.width, self.parent.get_height()
        )
        if (_size := self.attrs.get("size", "20")).isnumeric():
            # "0" from the ch unit
            # fmt: off
            avrg_letter_width = self.font.metrics(
                "•" if type_ == "password" else "0"
            )[0][4]
            # fmt: on
            self.box.set_width(int(_size) * avrg_letter_width, "content-box")
        set_height(self.line_height)

    def draw_content(self, surf: Surface):
        if self.type in input_type_check_res:
            text: str = self.attrs.get("value") or self.attrs.get("placeholder", "")  # type: ignore
            if not self.placeholder_shown and self.type == "password":
                text = "•" * len(text)
            # what is happening below corresponds to the ::placeholder pseudo-element
            color = Color(self.cstyle["color"])
            if self.placeholder_shown:
                color.a = int(0.4 * color.a)
            rendered_text = text_surf(text, self.font, color)
            rendered_rect = rendered_text.get_rect()
            text_rect = self.box.content_box
            window_l = (rendered_rect.right - text_rect.w) * (
                rendered_rect.w > text_rect.w and not self.placeholder_shown
            )
            surf.blit(
                rendered_text,
                text_rect,
                area=Rect(
                    window_l, 0, min(rendered_rect.w, text_rect.w), rendered_rect.bottom
                ),
            )
        else:
            raise BugError("Disallowed input type")

    def editcontent(self, func: Callable[[str], str]):
        self.changed = True
        g["css_dirty"] = True
        # TODO: don't allow invalid character inputs (eg. no letters in type=number)
        self.attrs["value"] = func(self.attrs.get("value", ""))

    def on_wheel(self, event):
        if self.type == "number":
            self.value += event.delta[1]


class BrElement(ReplacedElement):
    """
    <br>: a line break
    """

    def layout(self, given_width):
        self.box = Box.Box("content-box", width=given_width, height=self.line_height)
        self.inline_items = [TextDrawItem("", self)]

    def draw(self, *args):
        pass


class TextElement(Leaf_P):
    """Special element that represents any raw text"""

    text: str
    parent: Element
    inline_items: list[TextDrawItem]
    tag: str = "Text"
    display: DisplayType = "inline"
    position: str = "static"

    def is_block(self):
        return False

    def __init__(self, text: str):
        self.text = text

    def collide(self, pos: Coordinate):
        assert self.display == "block"
        if self.box.border_box.collidepoint(pos):
            return self.parent

    def compute(self):
        pass

    def layout(self, width: float) -> None:
        assert self.display == "block"
        self.box = Box.Box("content-box", width=width)
        xpos: float = 0
        ypos: float = 0
        current_line: list[TextDrawItem] = []
        items: list[TextDrawItem] = []

        def line_break(explicit: None | Element = None):
            nonlocal xpos, ypos  # , current_line, items
            xpos = 0
            for item in current_line:
                item.ypos = ypos
            items.extend(current_line)
            line_height = max((item.height for item in current_line), default=0)
            ypos += line_height or getattr(explicit, "line_height", 0)
            current_line.clear()

        def add_item(item: TextDrawItem):
            nonlocal xpos  # , current_line
            item_width = item.width
            if xpos + item_width > width:
                line_break()
            item.xpos = xpos
            item.ypos = ypos
            current_line.append(item)
            xpos += item_width

        parser = GeneralParser(self.text.lstrip())
        while parser.x:
            if word := parser.consume(word_re):
                has_whitespace = bool(parser.consume(whitespace_re))
                add_item(TextDrawItem(word, self.parent, whitespace=has_whitespace))
        line_break()
        self.box.height = ypos
        self.inline_items = items

    def rel_pos(self, pos: Coordinate):
        if hasattr(self, "box"):
            self.box.pos += Vector2(pos)

    def draw(self, surf: Surface):
        assert self.display == "block"
        for item in self.inline_items:
            item.draw(surf)

    def to_html(self, indent=0):
        return " " * indent + self.text

    def __repr__(self):
        return f"<Text: '{self.text}'>"


meta_elements = {"head", "title"}

elem_type_map: dict[str, type[Element]] = {
    **{k: MetaElement for k in meta_elements},
    "html": HTMLElement,
    "img": ImageElement,
    "audio": AudioElement,
    "br": BrElement,
    "link": LinkElement,
    "style": StyleElement,
    "comment": CommentElement,
    "a": AnchorElement,
    "input": InputElement,
}
