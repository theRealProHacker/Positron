"""
This file contains most of the code around the Element class
This includes:
- Different Element types
- Computing, layouting and drawing the Elements
"""

from __future__ import annotations
import asyncio
from contextlib import suppress
from dataclasses import dataclass
from functools import cache, partial
from itertools import chain

# fmt: off
from typing import (TYPE_CHECKING, Callable, Iterable, Sequence)

import pygame as pg

import Box
import Media
import rounded_box
import Style
from config import add_sheet, g, watch_file
from own_types import (Auto, AutoLP4Tuple, AutoType, BugError, Color, Coordinate, DisplayType, Drawable, Element_P,
                       Float4Tuple, Font, FontStyle, Length,
                       Number, Percentage, Radii, Rect, Surface)
from Style import (SourceSheet, bc_getter, br_getter, bs_getter, bw_keys, is_custom,
                   get_style, has_prio, inset_getter, pack_longhands, parse_file,
                   parse_sheet, calculator)
from util import create_task, draw_text, group_by_bool, log_error, make_default

# fmt: on

################################# Globals ###################################
@dataclass(frozen=True, slots=True)
class TextDrawItem:
    text: str
    element: "Element"
    xpos: float

    @property
    def height(self):
        return self.element.line_height


@dataclass(frozen=True)
class ElementDrawItem:
    element: "Element"
    xpos: float

    @property
    def height(self):
        return self.element.box.outer_box.height

    @property
    def width(self):
        return self.element.box.outer_box.width


InlineItem = TextDrawItem | ElementDrawItem


class Line(tuple[InlineItem, ...]):
    @property
    def height(self):
        return max([0, *(item.height for item in self)])


# TODO: Get an actually acceptable font and also give a list of possible fonts
@cache
def get_font(family: list[str], size: float, style: FontStyle, weight: int) -> Font:
    """
    Takes some font requirements and tries to find the most fitting
    """
    font = pg.font.match_font(
        name=family,
        italic=style.value == "italic",
        bold=weight > 500,  # we don't support actual weight TODO
    ) or log_error("Failed to find font", family, style, weight)
    font: Font = Font(font, int(size))
    font.italic = style.value == "oblique"
    return font


"""
The main shared calculator with no default percentage_val
"""


def calc_inset(inset: AutoLP4Tuple, width: float, height: float) -> Float4Tuple:
    """
    Calculates the inset data
    """
    top, right, bottom, left = inset
    return calculator.multi2((top, bottom), 0, height) + calculator.multi2(
        (right, left), 0, width
    )


########################## Element ########################################


class Element(Element_P):
    """
    The Element represents an HTML-Element
    """

    # General
    tag: str
    attrs: dict[str, str]
    children: list[Element | TextElement]
    parent: Element | None
    # Style
    istyle: Style.Style  # inline style
    estyle: Style.Style  # external style
    cstyle: Style.FullyComputedStyle  # computed_style
    # Layout + Draw
    box: Box.Box
    line_height: float
    white_spacing: float
    display: DisplayType
    layout_type: DisplayType
    position: str

    # Dynamic states
    active: bool = False
    focus: bool = False
    hover: bool = False

    def __init__(self, tag: str, attrs: dict[str, str], parent: Element | None):
        self.tag = tag
        self.attrs = attrs
        self.children = []
        if TYPE_CHECKING:
            assert isinstance(parent, Element)
        self.parent = parent
        self.istyle = Style.parse_inline_style(attrs.get("style", ""))

    ####################################  Main functions ######################################################
    def collide(self, pos: Coordinate) -> Iterable[Element]:
        """
        The idea of this function is to get which elements were hit by a mouse event
        """
        # TODO: z-index
        yield from chain.from_iterable(
            c.collide(pos) for c in reversed(self.real_children)
        )
        if hasattr(self, "box") and self.box.border_box.collidepoint(pos):
            yield self

    @property
    def input_style(self) -> Style.ResolvedStyle:
        """The total input style. Fused from inline and external style"""
        return Style.remove_importantd(Style.join_styles(self.istyle, self.estyle))

    @property
    def parent_style(self) -> Style.FullyComputedStyle:
        return dict(self.parent.cstyle) if self.parent else {}

    def compute(self):
        """
        Assembles the input style and then converts it into the Elements computed style.
        It then computes all the childrens styles
        """
        input_style = get_style(self.tag) | self.input_style
        parent_style = self.parent_style
        # inherit any custom properties from parent
        for k, v in parent_style.items():
            if is_custom(k):
                input_style.setdefault(k, v)
        keys = sorted(input_style.keys(), key=has_prio, reverse=True)
        style: Style.FullyComputedStyle = {}
        for key in keys:
            val = input_style[key]
            new_val = Style.compute_style(self.tag, val, key, parent_style)
            style[key] = new_val
            if has_prio:
                parent_style[key] = new_val
        # corrections
        """ mdn border-width: 
        absolute length or 0 if border-style is none or hidden
        """
        for bw_key, bstyle in zip(bw_keys, bs_getter(style)):
            if bstyle in ("none", "hidden"):
                style[bw_key] = Length(0)
        if style["outline-style"] in ("none", "hidden"):
            style["outline-width"] = Length(0)
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
            else calculator(lh, auto_val=1.5 * fsize, perc_val=fsize)
        )
        # https://developer.mozilla.org/en-US/docs/Web/CSS/word-spacing#values
        wspace = style["word-spacing"]
        wspace: float | Percentage = Percentage(100) if wspace is Auto else wspace
        d_ws = self.font.size(" ")[0]
        self.word_spacing = (calculator(wspace, 0, d_ws)) + d_ws
        self.position = str(style["position"])
        self.cstyle = g["cstyles"].add(style)
        for child in self.children:
            child.compute()

    def is_block(self) -> bool:
        """
        Returns whether an element is a block.
        Includes side effects (as a feature) that automatically adjusts false inline elements to block layout
        """
        self.display = self.cstyle["display"]
        if self.display != "none":
            if any(
                [child.is_block() for child in self.children]
            ):  # set all children to block
                self.display = "block"
                for child in self.children:
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

    def rel_pos(self, pos: Coordinate):
        self.box.pos += pos
        for c in self.children:
            c.rel_pos(self.box.content_box.topleft)

    def layout(self, width: float) -> None:
        """
        Layout an element. Gets the width it has available
        """
        assert self.parent is not None
        self.layout_type = self.display
        if self.display == "none":
            return
        style = self.cstyle
        self.box, set_height = Box.make_box(
            width, style, self.parent.box.width, self.parent.get_height()
        )
        self.layout_children(set_height)

    def layout_children(self, set_height: Callable[..., None]):
        if any(c.display == "block" for c in self.children):
            inner: Rect = self.box.content_box
            x_pos = inner.x
            y_cursor = inner.y
            # https://developer.mozilla.org/en-US/docs/Web/CSS/CSS_Box_Model/Mastering_margin_collapsing
            flow, no_flow = group_by_bool(
                self.children,
                lambda x: x.position in ("static", "relative", "sticky"),
            )
            for child in flow:
                child.layout(inner.width)
                # top, right, bottom, left = calc_inset(
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
                top, bottom, left, right = calc_inset(
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

        else:
            # https://stackoverflow.com/a/46220683/15046005
            self.layout_type = "inline"
            width = self.box.content_box.width
            xpos: float = 0
            current_line: list[InlineItem] = []
            lines: list[Line] = []

            def line_break():
                nonlocal xpos
                xpos = 0
                lines.append(Line(current_line))
                current_line.clear()

            for elem in self._text_iter_desc():
                if isinstance(elem, TextElement):
                    c, text = elem.parent, elem.text
                    if text == "\n":
                        line_break()
                        continue
                    for word in text.split():
                        word_width = c.font.size(word)[0]
                        if xpos + word_width > width:
                            line_break()
                        current_line.append(TextDrawItem(word, c, xpos))
                        xpos += word_width + c.word_spacing
                else:
                    elem.layout(width)
                    elem_width = elem.box.outer_box.width
                    if xpos + elem_width > width:
                        line_break()
                    current_line.append(ElementDrawItem(elem, xpos))
                    xpos += elem_width + c.word_spacing
            lines.append(Line(current_line))
            set_height(sum(line.height for line in lines))
            self.lines = lines

    def draw(self, surf: Surface):
        """
        Draws the element to the `surf` at `pos`
        """
        if self.display == "none":
            return
        style = self.cstyle
        # setup
        border_rect = self.box.border_box
        radii: Radii = tuple(
            (
                int(calculator(brx, perc_val=border_rect.width)),
                int(calculator(bry, perc_val=border_rect.height)),
            )
            for brx, bry in br_getter(style)
        )
        # TODO: only recreate the background image if necessary
        # either because a style attribute changed that affects the background image
        # or because a background image finished loading

        # https://web.dev/howbrowserswork/#the-painting-order
        # 1.+2. draw background-color and background-image
        bg_imgs: Sequence[Drawable] = style["background-image"]
        bg_color: Color = style["background-color"]
        bg_size = border_rect.size
        bg_surf = Surface(bg_size, pg.SRCALPHA)
        bg_surf.fill(bg_color)
        for drawable in bg_imgs:
            drawable.draw(bg_surf, (0, 0))
        rounded_box.round_surf(bg_surf, bg_size, radii)
        surf.blit(bg_surf, border_rect.topleft)

        # 3. draw border
        rounded_box.draw_rounded_border(
            surf, border_rect, bc_getter(style), self.box.border, radii
        )

        # 4. draw children
        if self.layout_type == "block":
            for c in self.children:
                c.draw(surf)
        elif self.layout_type == "inline":
            ypos = 0
            for line in self.lines:
                for item in line:
                    item_pos = (self.box.x + item.xpos, self.box.y + ypos)
                    if isinstance(item, TextDrawItem):
                        draw_text(
                            surf,
                            item.text,
                            item.element.font,
                            item.element.cstyle["color"],
                            topleft=item_pos,
                        )
                    else:
                        item.element.draw(surf)
                ypos += line.height
        else:
            raise BugError(f"Wrong layout_type ({self.layout_type})")

        # 5. draw outline
        _out_width = int(calculator(style["outline-width"]))
        _out_off: float = style["outline-offset"].value + _out_width / 2
        rounded_box.draw_rounded_border(
            surf,
            border_rect.inflate(2 * _out_off, 2 * _out_off),
            colors=(style["outline-color"],) * 4,
            widths=(_out_width,) * 4,
            radii=radii,
        )

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

    def __repr__(self):
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

    def iter_desc(self) -> Iterable[Element]:
        """Iterates over all descendants *including* this element"""
        yield self
        yield from chain.from_iterable(
            c.iter_desc() for c in self.children if not isinstance(c, TextElement)
        )

    def iter_siblings(self) -> Iterable[Element]:
        if self.parent:
            yield from (
                x
                for x in self.parent.children
                if x is not self and not isinstance(x, TextElement)
            )

    def _text_iter_desc(self) -> Iterable[Element | TextElement]:
        """
        Alternative iteration over all descendants
        used in text layout.
        Shouldn't be called out of this context.
        """
        if self.display == "none":
            return
        for c in self.children:
            if isinstance(c, TextElement):
                yield c
            else:
                yield from c._text_iter_desc()

    @property
    def real_children(self):
        """
        All direct children that are not MetaElements or TextElements
        """
        return [
            c for c in self.children if not isinstance(c, (TextElement, MetaElement))
        ]


class HTMLElement(Element):
    def __init__(self, tag: str, attrs: dict[str, str], parent: Element = None):
        assert parent is None
        assert tag == "html"
        super().__init__("html", attrs, parent=None)

    def get_height(self) -> float:
        return self.box.height

    @property
    def parent_style(self) -> Style.FullyComputedStyle:
        return {
            "font-size": g["default_font_size"],
            "color": "black"
        }

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


class MetaElement(Element):
    """
    A MetaElement is an Element that's sole purpose is conveying information
    to the runtime and is not for display or interaction.
    It has no style, the display is "none"
    """

    tag: str
    display: DisplayType = "none"

    def __init__(self, attrs: dict[str, str], txt: str, parent: "Element"):
        self.children = []
        self.parent = parent
        self.attrs = attrs
        # parse element style and update default
        self.istyle = {}

    def rel_pos(self, *args):
        pass

    def is_block(self):
        return False

    def collide(self):
        return []

    def compute(self):
        pass

    def layout(self, *args):
        pass

    def draw(self, *args):
        pass


class StyleElement(MetaElement):
    tag = "style"
    inline_sheet: SourceSheet | None = None
    src_sheet: SourceSheet | None = None

    def __init__(self, attrs: dict[str, str], txt: str, parent: "Element"):
        super().__init__(attrs, txt, parent)
        self.src = attrs.get("src")
        if self.src is not None:
            self.src = watch_file(self.src)
            create_task(parse_file(self.src), True, self.parse_callback)
        if txt:
            self.inline_sheet = parse_sheet(txt)
            add_sheet(self.inline_sheet)

    def parse_callback(self, future: asyncio.Future):
        with suppress(Exception):
            self.src_sheet = future.result()
            add_sheet(self.src_sheet)


class TitleElement(MetaElement):
    tag = "title"

    def __init__(self, attrs: dict[str, str], txt: str, parent: "Element"):
        super().__init__(attrs, txt, parent)
        g["title"] = txt


class CommentElement(MetaElement):
    tag = "!comment"

    def to_html(self, indent=0):
        return f"{' '*indent}<!--{self.text}-->"

    def __repr__(self):
        return self.to_html()


class LinkElement(MetaElement):
    tag = "link"

    def __init__(self, attrs: dict[str, str], txt: str, parent: "Element"):
        super().__init__(attrs, txt, parent)
        # https://developer.mozilla.org/en-US/docs/Web/HTML/Element/link
        # TODO:
        # media -> depends on media query support
        match attrs.get("rel"):
            case "stylesheet" if (src := attrs.get("href")):
                # TODO: disabled ?
                # TODO: title ?
                self.src = watch_file(src)
                create_task(parse_file(src), True, self.parse_callback)
            case "icon" if (src := attrs.get("href")):
                # TODO: sizes ?
                g["icon_srcs"].append(src)

    def parse_callback(self, future: asyncio.Future):
        with suppress(Exception):
            self.src_sheet = future.result()
            add_sheet(self.src_sheet)


class ReplacedElement(Element):
    def _text_iter_desc(self) -> Iterable[Element | TextElement]:
        yield self


class ImgElement(ReplacedElement):
    size: None | tuple[int, int]
    given_size: tuple[int | None, int | None]
    image: Media.Image | None
    attrw: int | None
    attrh: int | None

    def __init__(self, tag: str, attrs: dict[str, str], parent: "Element"):
        # https://developer.mozilla.org/en-US/docs/Web/HTML/Element/img
        # TODO:
        # source element
        # usemap: points to a map
        super().__init__(tag, attrs, parent)
        # urls = [] # TODO: actually fetch the images from the srcset and sizes
        try:
            self.image = Media.Image(
                attrs["src"],
                load=attrs.get("loading", "eager") != "lazy",
                # "auto" is synonymous with "async"
                sync=attrs.get("decoding", "async") == "sync",
            )
            self.attrw = int(w) if (w := attrs.get("width")) is not None else None
            self.attrh = int(h) if (h := attrs.get("height")) is not None else None
        except (KeyError, ValueError):
            self.image = None
            self.attrw = self.attrh = None

    @staticmethod
    def crop_image(surf: Surface, to_size: Coordinate):
        """
        Makes an image fit the `to_size`
        """
        # TODO: don't just scale but also cut out, because scaling might destroy the image
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
        intrinsic_size = (
            self.image.surf.get_size() if self.image.is_loaded else (None, None)
        )
        w, h = (
            make_default(attr, make_default(intr, 0))
            for attr, intr in zip((self.attrw, self.attrh), intrinsic_size)
        )
        self.box, set_height = Box.make_box(
            w, self.cstyle, self.parent.box.width, self.parent.get_height()
        )
        set_height(h)

    def draw(self, surf: Surface):
        if self.cstyle["display"] == "none" or self.image is None:
            return
        if self.image.is_loaded:
            surf.blit(
                self.crop_image(self.image.surf, (self.box.width, self.box.height)),
                self.box.pos,
            )
            self.children = []
            self.lines = []
            super().draw(surf)


class AudioElement(ReplacedElement):
    def __init__(self, tag: str, attrs: dict[str, str], parent: "Element"):
        # https://developer.mozilla.org/en-US/docs/Web/HTML/Element/audio
        # TODO:
        # autoplay: right now autoplay is always on
        # controls: both draw and event handling
        # muted: right now muted is always off
        # preload: probably not gonna implement fully (is only a hint)
        # events: ...
        super().__init__(tag, attrs, parent)
        try:
            self.audio = Media.Audio(
                attrs["src"],
                load=attrs.get("preload", "auto") not in ("none", "metadata"),
                autoplay=True,
                loop="loop" in attrs,
            )
        except (KeyError, ValueError):
            self.image = None


class BrElement(ReplacedElement):
    """
    <br>: a line break
    """
    def layout(self, given_width):
        self.box = Box.Box("content-box", width=given_width, height=self.line_height)

class TextElement:
    """Special element that represents any raw text"""

    text: str
    parent: Element
    tag = "Text"
    display = "inline"
    position = "static"

    def is_block(self):
        return False

    def rel_pos(self, pos: Coordinate):
        if hasattr(self, "box"):
            self.box.pos += pos

    def __init__(self, text: str, parent: Element):
        self.text = text
        self.parent = parent

    def compute(self):
        pass

    def layout(self, width: float) -> None:
        assert self.display == "block"
        xpos: float = 0
        current_line: list[tuple[str, float]] = []
        lines: list[list[tuple[str, float]]] = []

        def line_break():
            nonlocal xpos, current_line
            xpos = 0
            lines.append(current_line)
            current_line = []

        for word in self.text.split():
            word_width = self.parent.font.size(word)[0]
            if xpos + word_width > width:
                line_break()
            current_line.append((word, xpos))
            xpos += word_width + self.parent.word_spacing
        lines.append(current_line)
        self.lines = lines
        self.box = Box.Box(
            "content-box", width=width, height=len(lines) * self.parent.line_height
        )

    def draw(self, surf: Surface):
        x, y = self.box.pos
        for i, line in enumerate(self.lines):
            y_pos = i * self.parent.line_height + y
            for word, x_pos in line:
                draw_text(
                    surf,
                    word,
                    self.parent.font,
                    self.parent.cstyle["color"],
                    topleft=(x_pos + x, y_pos),
                )

    def to_html(self, indent=0):
        return " " * indent + self.text

    def __repr__(self):
        return f"<Text: '{self.text}'>"


def apply_style():
    """
    Apply the global SourceSheet to all elements
    """
    joined_sheet = SourceSheet.join(g["css_sheets"])
    g["css_dirty"] = False
    g["css_sheet_len"] = len(g["css_sheets"])
    # sort all rules by the selectors specificities
    rules = sorted(
        joined_sheet.all_rules,
        key=lambda rule: rule[0].spec,
    )
    root: Element = g["root"]
    for elem in root.iter_desc():
        # chain all matching styles and sort them by their importance
        elem.estyle = dict(
            sorted(
                chain.from_iterable(
                    style.items() for selector, style in rules if selector(elem)
                ),
                key=lambda t: Style.is_imp(t[1]),
            )
        )
