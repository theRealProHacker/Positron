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
from itertools import chain
from typing import Iterable, Sequence


import pygame as pg

import positron.Box as Box
import positron.config as config
import positron.Media as Media
import positron.Style as Style
import positron.utils as util
import positron.utils.markdown as md
import positron.utils.Navigator as Navigator
import positron.utils.rounded as rounded_box
from positron.events.InputType import EditingContext
from positron.modals.ContextMenu import EasyTextButton, MenuItem
from positron.utils.clipboard import put_clip

from .config import add_sheet, cursors, g, input_type_check_res
from .element.ElementAttribute import *
from .element.Parser import get_tag
from .element.Parser import parse as parse_html
from .events.InputType import *
from .Style import (SourceSheet, bs_getter, bw_keys, calculator, has_prio,
                    is_custom, pack_longhands, parse_file, parse_sheet)
from .types import (Auto, AutoType, Color, Coordinate, Cursor, DisplayType,
                    Drawable, Element_P, Leaf_P, Length, Number, Percentage,
                    Rect, Surface, frozendict)
from .utils import log_error, make_default
from .utils.fonts import Font

# fmt: on


################################# Globals ###################################


word_re = re.compile(r"[^\s]+")
########################## Element ########################################
# common operations on Elements. TODO
# def find_first_common_ancestor()


class Element(Element_P):
    """
    The Element represents a general HTML-Element
    """

    # General
    tag: str
    attrs: dict[str, str]
    children: list[Element | TextElement]
    parent: Element | None
    id = GeneralAttribute("id")
    class_list = ClassListAttribute()
    data = DataAttribute()
    contextmenu: tuple[MenuItem, ...] = ()
    scrolly = 0
    overflow = False

    @property
    def max_scroll(self):
        return self.layout_type.height - self.get_height()

    # Style
    istyle: Style.Style = frozendict()  # inline style
    estyle: Style.Style = frozendict()  # external style
    cstyle: Style.FullyComputedStyle  # computed_style
    # Layout + Draw
    box: Box.Box
    line_height: float
    word_spacing: float
    display: DisplayType
    layout_type: layout.Layout
    position: str
    cursor: Cursor

    # Dynamic states
    # https://html.spec.whatwg.org/multipage/semantics-other.html#pseudo-classes
    @property
    def active(self) -> bool:
        return self is config.event_manager.active

    @property
    def focus(self) -> bool:
        return self is config.event_manager.focus

    @property
    def hover(self) -> bool:
        return self is config.event_manager.hover

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

    enabled: bool = Opposite("disabled")
    disabled: bool = BooleanAttribute("disabled")

    read_only: bool = False
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
        self.tag = tag
        self.attrs = attrs
        self.children = children
        self.parent = None
        self.istyle = Style.parse_inline_style(attrs.get("style", ""))

        for c in children:
            self.add_child(c)

    def add_child(self, child: Element | TextElement):
        """
        This is called when a child is added
        (could be before or after)
        """
        child.parent = self

    @classmethod
    def from_parsed(cls, parsed) -> Element:
        """
        Creates an Element from the given parsed tree
        """
        tag = get_tag(parsed)
        type_: type[Element] = elem_type_map.get(tag, Element)
        text = parsed.text or ""
        attrs = dict(parsed.attrib)
        children: list[Element | TextElement] = []
        if text:
            children.append(TextElement(text))
        for _c in parsed:
            c = Element.from_parsed(_c)
            children.append(c)
            if text := _c.tail:
                children.append(TextElement(text))
        return type_(tag, attrs, children)

    ###########################  Main functions ##############################################
    @property
    def input_style(self) -> Style.ResolvedStyle:
        """The total input style. Fused from inline and external style"""
        return Style.remove_importantd(Style.join_styles(self.istyle, self.estyle))

    def apply_style(self, sheet: SourceSheet):
        """
        Applies the given style sheet to the element
        """
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
            if has_prio(key):
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
        self.font = Font(
            [*style["font-family"]],
            fsize,
            style["font-style"],
            style["font-weight"],
            style["color"],
        )
        # https://developer.mozilla.org/en-US/docs/Web/CSS/line-height#values
        lh: AutoType | float | Length | Percentage = style["line-height"]
        self.line_height = (
            lh * fsize
            if isinstance(lh, Number)
            else calculator(lh, auto_val=self.font.linesize, perc_val=fsize)
        )
        # https://developer.mozilla.org/en-US/docs/Web/CSS/word-spacing#values
        wspace = style["word-spacing"]
        default_word_spacing = self.font.size(" ")[0]
        self.word_spacing = default_word_spacing + (
            calculator(wspace, 0, default_word_spacing)
        )
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
        Includes side effects (as a feature) that automatically adjust
        false inline elements to block layout
        """
        if self.display == "none":
            return False
        if any(child.is_block() for child in self.display_children):
            self.display = "block"
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
        if self.display in "none":
            self.layout_type = layout.EmptyLayout()
            return
        parent_size = (
            (self.parent.box.width, self.parent.get_height()) if self.parent else (0, 0)
        )
        self.box, _ = Box.make_box(width, self.cstyle, *parent_size)
        self.layout_inner()
        self.overflow = self.max_scroll > 0
        self.scrolly = util.in_bounds(self.scrolly, 0, self.max_scroll)

    def layout_inner(self):
        children = self.display_children
        # XXX: If an element with display inline appears here
        # It has yielded itself in iter_inline
        # and should have overriden this method anywhay
        if not children or self.display == "inline":
            self.layout_type = layout.EmptyLayout()
        elif any(c.display == "block" for c in children):
            self.layout_type = layout.BlockLayout(self, children)
        else:
            self.layout_type = layout.InlineLayout(self, self.iter_inline())
        self.layout_type.layout(self.box.content_box.width)

    def rel_pos(self, pos: Coordinate):
        """
        Makes the previously relative position to the parent absolute to the screen
        """
        self.box.pos += pos
        self.box.y -= self.scrolly
        self.layout_type.rel_pos(self.box.content_box.topleft)

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
        self.layout_type.draw(surf)

    # Events
    def collide(self, pos: Coordinate) -> Element | None:
        """
        Get which elements were hit by a mouse event at pos
        """
        # TODO: z-index
        if elem := self.layout_type.collide(pos):
            return elem
        if self.box.border_box.collidepoint(pos):
            return self
        return None

    ############################# Default Event Handlers ################################################################

    def on_scroll(self, event):
        self.scrolly = util.in_bounds(self.scrolly + event.delta, 0, self.max_scroll)

    ###############################  API for Elements  ##################################################################
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
            children = "\n".join(c.to_html(indent + 2) for c in self.children)
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
        return ",\n".join(f"{k}: {v}" for k, v in out_style.items())

    def setattr(self, name: str, value):
        """
        Set the elements attribute
        """
        # override for different behaviour
        self.attrs[name] = value
        if name == "style":
            self.istyle = Style.parse_inline_style(value)
        elif name in ("id", "class"):
            pass  # TODO: add and remove element to and from the global map

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
        Iteration over all descendants used in text layout.
        In other words the leafs of the layout tree.
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
        All direct children that are not TextElements
        """
        return [c for c in self.children if not isinstance(c, TextElement)]


class HTMLElement(Element):
    """
    Represents the <html> element
    """

    tag = "html"

    @staticmethod
    def from_string(html: str):
        return HTMLElement.from_parsed(parse_html(html))

    def get_height(self) -> float:
        return self.box.height

    def layout(self):
        self.box = Box.Box(t="content-box", width=g["W"], height=g["H"])
        # all children correct their display
        assert self.is_block()
        self.layout_inner()
        max_scroll = self.layout_type.height - self.box.content_box.height
        self.overflow = max_scroll > 0
        if self.overflow:
            self.scrolly = min(self.scrolly, max_scroll)
        # all children correct their position
        self.rel_pos((0, 0))

    def draw(self, surf: Surface):
        self.draw_content(surf)


class AnchorElement(Element):
    """
    <a>
    """

    tag = "a"

    @property
    def href(self) -> str | None:
        return self.attrs.get("href")

    @property
    def link(self):
        return self.href and self.href not in Navigator.visited_links

    @property
    def visited(self):
        return self.href and self.href in Navigator.visited_links

    @property
    def all_link(self):
        return "href" in self.attrs

    def on_click(self):
        if self.href:
            Navigator.push(self.href)
        else:
            log_error("Anchor without href clicked")

    # def on_auxclick(self):
    #     # Always new tab?
    #     if self.href:
    #         Navigator.push(self.href)
    #     else:
    #         log_error("Anchor without href alt-clicked")

    def on_drag_start(self):
        pass

    @property
    def contextmenu(self):
        if not self.href or Navigator.make_url(self.href).is_internal:
            return ()

        @EasyTextButton("Copy link")
        def copy_link():
            if self.href:
                put_clip(self.href)

        return (copy_link,)


class MarkdownElement(Element):
    tag = "md"

    def __init__(
        self, tag: str, attrs: dict[str, str], children: list[Element | TextElement]
    ):
        super().__init__(tag, attrs, children)
        if (src := attrs.get("src")) is not None and md.enabled:
            self.src = src
            if os.path.isfile(src):
                config.file_watcher.add_file(src, self.reload_src)
            util.create_task(util.fetch_txt(src), True, self.parse_callback)

    def parse_callback(self, future: asyncio.Future[str]):
        """
        What should happen when new markdown arrives
        """
        with suppress(Exception):
            markdown = future.result()
            html = md.to_html(markdown)
            html_element = HTMLElement.from_string(html)
            self.children = html_element.children[1].children
            for c in self.children:
                self.add_child(c)

    def reload_src(self):
        util.create_task(util.fetch_txt(self.src), True, self.parse_callback)


class MetaElement(Element):
    """
    A MetaElement is an Element thats sole purpose is conveying information
    to the runtime and is not for display or interaction.
    It has no style, the display is "none"

    Examples for MetaElements are:
    `title`, `link`, `style`
    """

    display: DisplayType = "none"

    def compute(self):
        pass


class StyleElement(MetaElement):
    """
    The <style> Element

    It can be used in two seperate ways:

    By specifiying the src attribute a style sheet can be linked.
    When the linked stylesheet is changed, the style sheet
    will hot reload using the new content.

    Additionally, css can be inserted directly into the style element.
    """

    tag = "style"
    src: str
    inline_sheet: SourceSheet | None = None
    src_sheet: SourceSheet | None = None

    def __init__(
        self, tag: str, attrs: dict[str, str], children: list[Element | TextElement]
    ):
        super().__init__(tag, attrs, children)
        if (src := attrs.get("src")) is not None:
            self.src = src
            if os.path.isfile(src):
                config.file_watcher.add_file(src, self.reload_src)
            util.create_task(parse_file(src), True, self.parse_callback)
        if self.text.strip():
            self.inline_sheet = parse_sheet(self.text)
            add_sheet(self.inline_sheet)

    def parse_callback(self, future: asyncio.Future[SourceSheet]):
        with suppress(Exception):
            self.src_sheet = future.result()
            add_sheet(self.src_sheet)

    def reload_src(self):
        g["css_sheets"].remove(self.src_sheet)
        util.create_task(parse_file(self.src), True, self.parse_callback)


class CommentElement(MetaElement):
    tag = "!comment"

    def to_html(self, indent=0):
        return f"{' '*indent}<!--{self.text}-->"

    def __repr__(self):
        return self.to_html()


class LinkElement(MetaElement):
    """
    The <link> element (https://developer.mozilla.org/en-US/docs/Web/HTML/Element/link)

    It is mainly used for style sheets. However, Positron developers should use the <style> element.
    The second use case are linked icons. In the real world, many different devices and screen sizes require different
    icon sizes.

    With Positron, this is not needed as pygame icons should always be as close to 32x32, but will likely be scaled
    automatically. Also, most apps will have a single global icons and don't need to set their icon in html.

    Attributes

    Implemented:
        - rel:
            The relationship between this document and the linked document.
            Can be either stylesheet or icon as mentioned above.
            The behaviour of the LinkElement is mainly defined by this attribute.
            This means, adding more values increases the complexity the most.
        - href: The hyper reference to the linked document.
    Might implement:
        - `rel = preload` with `as = the content type` (on request):
            The linked document should be preloaded so that it is availably asap.
            This attribute is likely not that useful.
        - prefetch (experimental): Similar to `rel = preload`
        - media (on request):
            This element is only active when the given media query is True.
            This behavious is probably costly and difficult to implement and doesn't add too much value.
    Will not implement in the near future:
        - type & sizes (experimental):
            The mime-type of the linked document and the size of linked icons. Not useful as mentioned above.
            The mime-type is guessed from the file-extension anyway.
        - title: The title of the linked style sheet. Just not useful
    """

    tag = "link"
    src_sheet: SourceSheet

    def __init__(
        self, tag: str, attrs: dict[str, str], children: list[Element | TextElement]
    ):
        super().__init__(tag, attrs, children)
        self.rel = attrs.get("rel")
        self.src = attrs.get("href")
        if self.src:
            match self.rel:
                case "stylesheet":
                    if os.path.exists(self.src):
                        config.file_watcher.add_file(self.src, self.hot_reload)
                    util.create_task(parse_file(self.src), True, self.parse_callback)
                case "icon":
                    g["icon_srcs"].append(self.src)

    def parse_callback(self, future: asyncio.Future):
        """
        The callback for when a stylesheet is finished parsing.

        If we already had a stylesheet, we update it directly,
        else we create a new one and add it to the global sheet set
        """
        try:
            if not hasattr(self, "src_sheet"):
                self.src_sheet = future.result()
                add_sheet(self.src_sheet)
            else:
                self.src_sheet[:] = future.result()
        except Exception as e:
            log_error(e)

    def hot_reload(self):
        """
        Handles the hot reload by updating the style sheet
        """
        util.create_task(parse_file(self.src), True, self.parse_callback)


class ReplacedElement(Element):
    """
    A ReplacedElement is basically just an Element that is self responsible for its layout and drawing.

    ReplacedElements are mostly highly dynamic elements like:
    <audio>, <video>, <img>, <button>, <input>, <progress>, <meter>, and so on
    """

    def rel_pos(self, pos: Coordinate):
        self.box.pos += pos

    def iter_inline(self):
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
                # XXX: "auto" is synonymous with "async"
                sync=attrs.get("decoding", "async") == "sync",
            )
        except (KeyError, ValueError):
            self.image = None
        self.__dict__["display_children"] = []

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
        # TODO: Automatically adjust width to height and height to width
        # To respect aspect ratio
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
        self.layout_type = layout.EmptyLayout()
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

    @property
    def contextmenu(self):
        if not self.image.is_loaded:
            return ()

        @EasyTextButton("Open image")
        def open_image():
            util.task_in_thread(os.startfile, os.path.abspath(self.image.url))

        return (open_image,)


class AudioElement(ReplacedElement):
    tag = "audio"

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
        form, list
    TODO:
        accept -> file
        max, min, step
    """

    tag = "input"
    # fmt: off
    type = EnumeratedAttribute("type", range = {
        "text", "tel", "password", "number", "email", "url", "search",
        "checkbox", "radio", "slider",
        "file", "color", "hidden"
    }, default="text")
    # fmt: on
    value = InputValueAttribute()

    @property
    def _value(self) -> str:
        return self.attrs.get("value", "")

    maxlength = NumberAttribute("maxlength", default=float("inf"))
    minlength = NumberAttribute("minlength")
    multiple = BooleanAttribute("multiple")
    # States
    changed: bool = False
    checked: bool = False

    @property
    def blank(self):
        return not self.attrs.get("value")  # value is either not set or empty.

    # TODO: Does the input need to have a placeholder set for this to fire?
    placeholder_shown: bool = SameAs("blank")

    @property
    def valid(self):
        if self.disabled or self.read_only:
            return True
        type_ = self.type
        value = self._value
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
            for constraint, op in (
                ("max", operator.gt),
                ("min", operator.lt),
            ):
                if constr := self.attrs.get(constraint):
                    with suppress(ValueError):
                        if op(float(value), float(constr)):
                            return False
        return True

    @property
    def read_only(self):
        return "readonly" in self.attrs

    invalid: bool = Opposite("valid")
    required = BooleanAttribute("required")
    optional: bool = Opposite("required")

    def __init__(self, *args):
        super().__init__(*args)
        if "checked" in self.attrs:
            self.checked = True
        self.editing_ctx = EditingContext(self.attrs.get("value", ""))
        self.scrollx = 0

    def compute(self):
        super().compute()
        if self.cstyle["cursor"] is Auto:
            self.cursor = cursors["text"]  # TODO: change this for other input types
        if self.type == "hidden":
            self.display = "none"

    def layout(self, width: float):
        self.layout_type = layout.EmptyLayout()
        if not self.parent:
            self.display = "none"
            return
        type_ = self.type
        self.box, set_height = Box.make_box(
            width, self.cstyle, self.parent.box.width, self.parent.get_height()
        )
        if (
            _size := self.attrs.get("size", config.default_text_input_size)
        ).isnumeric():
            avrg_letter_width = self.font.size(
                config.password_replace_char
                if type_ == "password"
                else config.ch_unit_char
            )[0]
            self.box.set_width(int(_size) * avrg_letter_width, "content-box")
        set_height(self.line_height)
        if self.type == "number":
            # XXX: catch any scrolls
            self.overflow = True 

    def draw_content(self, surf: Surface):
        if self.type in input_type_check_res:
            text: str = self.attrs.get("value") or self.attrs.get("placeholder", "")  # type: ignore
            if not self.placeholder_shown and self.type == "password":
                text = config.password_replace_char * len(text)
            text_rect = self.box.content_box
            cursorw = self.font.size(text[: self.editing_ctx.cursor])[0]
            if self.focus:
                cursor_draw_w = min(cursorw, text_rect.w)
                pg.draw.line(
                    surf,
                    "black",  # TODO: cursor color
                    (text_rect.x + cursor_draw_w, text_rect.y),
                    (text_rect.x + cursor_draw_w, text_rect.y + text_rect.height),
                )
                selection = self.editing_ctx.selection
                if selection:
                    upto_w = self.font.size(text[: selection[0]])[0]
                    selection_size = self.font.size(text[selection[0] : selection[1]])
                    util.draw_rect(
                        surf,
                        config.selection_color,  # TODO: selection color
                        Rect(text_rect.x + upto_w, text_rect.y, *selection_size),
                        border_radius=30,
                    )
            color = Color(self.cstyle["color"])
            if self.placeholder_shown:
                # XXX: what is happening below corresponds to the ::placeholder pseudo-element
                # but we can't make this happen with pure css
                color.a = int(config.placeholder_opacity * color.a)
            self.font.color = color
            render_h = self.font.size(text)[1]
            # we do this to only render the part of the text that we need to render
            rendered_text = self.font.render(text)
            surf.blit(
                rendered_text,
                text_rect,
                area=Rect(
                    # self.scrollx,
                    max(0, cursorw - text_rect.w),
                    0,
                    text_rect.w,
                    render_h,
                ),
            )
        else:
            util.print_once("Disallowed input type: {self.type}")

    @staticmethod
    def _sanitize_number(num: str):
        """
        Sanitizes an input to be a valid number input.

        Removes any "-" except for an optional one at position 0.
        also removes every "." but the first one.
        """
        if not num:
            return num
        prepend = "-" if num[0] == "-" else ""
        sanitized = "".join(c for c in num if c in "0123456789.")
        if sanitized.count(".") >= 2:
            part = sanitized.split(".")
            sanitized = "".join([part[0], ".", *part[1:]])
        return prepend + sanitized

    def sanitize_input(self, type: InputType):
        # TODO: A lot of thinking on how to sanitize user input with numbers,
        # but this looks pretty solid at the moment
        if self.type == "number" and isinstance(type, Insert) and type.content:
            old_apply = type.apply

            def new_apply(text: str) -> str:
                result = self._sanitize_number(old_apply(text))
                if Style.number_pattern.match(result) or Style.number_pattern.match(
                    result + "0"
                ):  # -0 and .0
                    return result
                else:
                    return text

            type.apply = new_apply  # type: ignore

    def setattr(self, name: str, value):
        if name == "value":
            if self.type == "number":
                value = self._sanitize_number(value)
        super().setattr(name, value)

    def on_wheel(self, event):
        if self.type == "number":
            self.value += event.delta[1]


class MeterElement(ReplacedElement):
    """
    <meter>
    Attributes:
    - value
    - min/max
    - low/high/optimum (ignored currently)
    """

    value = NumberAttribute("value")
    _min = NumberAttribute("min", 0)
    _max = NumberAttribute("max", 1)
    low = NumberAttribute("low", float("-inf"))
    high = NumberAttribute("high", float("inf"))

    def draw(self, surf: Surface):
        if self.display == "none":
            return

        style = dict(self.cstyle)
        box = self.box
        border_rect = box.border_box
        radii = rounded_box.radii_frm_(border_rect, style)
        # background
        bg_img: Sequence[Drawable] = style["background-image"]
        bg_color: Color = style["background-color"]
        bg_size = border_rect.size
        bg_surf = Surface(bg_size, pg.SRCALPHA)
        bg_surf.fill(bg_color)
        for drawable in bg_img:
            drawable.draw(bg_surf, (0, 0))
        # meter bar
        value = self.value - self._min
        full_bar = self._max - self._min
        if value and full_bar:
            color = Color("green")
            rect = Rect(border_rect)
            rect.topleft = (0, 0)
            rect.width = int(rect.width * value / full_bar)
            util.draw_rect(bg_surf, color, rect)
        rounded_box.round_surf(bg_surf, bg_size, radii)
        surf.blit(bg_surf, border_rect.topleft)
        # border
        rounded_box.draw_rounded_border(
            surf, border_rect, Style.bc_getter(style), box.border, radii
        )
        # draw the outline
        rounded_box.draw_outline(surf, self.box, style)


class BrElement(ReplacedElement):
    """
    <br>: a line break
    """

    tag = "br"

    def layout(self, given_width):
        self.box = Box.Box("content-box", width=given_width, height=self.line_height)
        # TODO

    def draw(self, *args):
        pass


class TextElement(Leaf_P):
    """Special element that represents any raw text"""

    text: str
    parent: Element
    tag: str = "Text"
    display: DisplayType = "inline"
    # inline_items: list[TextDrawItem]
    # position: str = "static"

    def is_block(self):
        return False

    def __init__(self, text: str):
        self.text = text

    # def collide(self, pos: Coordinate):
    #     assert self.display == "block"
    #     if self.box.border_box.collidepoint(pos):
    #         return self.parent

    def compute(self):
        pass

    # def layout(self, width: float) -> None:
    #     assert self.display == "block"
    #     self.box = Box.Box("content-box", width=width)
    #     xpos: float = 0
    #     ypos: float = 0
    #     current_line: list[TextDrawItem] = []
    #     items: list[TextDrawItem] = []

    #     def line_break(explicit: None | Element = None):
    #         nonlocal xpos, ypos  # , current_line, items
    #         xpos = 0
    #         for item in current_line:
    #             item.ypos = ypos
    #         items.extend(current_line)
    #         line_height = max((item.height for item in current_line), default=0)
    #         ypos += line_height or getattr(explicit, "line_height", 0)
    #         current_line.clear()

    #     def add_item(item: TextDrawItem):
    #         nonlocal xpos  # , current_line
    #         item_width = item.width
    #         if xpos + item_width > width:
    #             line_break()
    #         item.xpos = xpos
    #         item.ypos = ypos
    #         current_line.append(item)
    #         xpos += item_width

    #     parser = GeneralParser(self.text.lstrip())
    #     while parser.x:
    #         if word := parser.consume(word_re):
    #             has_whitespace = bool(parser.consume(whitespace_re))
    #             add_item(TextDrawItem(word, self.parent, whitespace=has_whitespace))
    #     line_break()
    #     self.box.height = ypos
    #     self.inline_items = items

    # def rel_pos(self, pos: Coordinate):
    #     if hasattr(self, "box"):
    #         self.box.pos += Vector2(pos)

    # def draw(self, surf: Surface):
    #     assert self.display == "block"
    #     for item in self.inline_items:
    #         item.draw(surf)

    def to_html(self, indent=0):
        return " " * indent + self.text

    def __repr__(self):
        return f"<Text: '{self.text}'>"


elem_type_map: dict[str, type[Element]] = {
    **dict.fromkeys(("head", "title"), MetaElement),
    "html": HTMLElement,
    "img": ImageElement,
    "audio": AudioElement,
    "br": BrElement,
    "link": LinkElement,
    "style": StyleElement,
    "!comment": CommentElement,
    "meter": MeterElement,
    "a": AnchorElement,
    "input": InputElement,
    "md": MarkdownElement,
}


import positron.element.layout as layout
