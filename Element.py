"""
This file contains most of the code around the Element class
This includes:
- Creating Elements from a parsed tree
- Different Element types
- Computing, layouting and drawing the Elements
- CSS-Selectors
"""

import re
from dataclasses import dataclass
from functools import cache, cached_property, reduce
from itertools import chain
from typing import Any, Callable, Iterable, Protocol, Type, Union

import pygame as pg

import rounded_box
import Style
import Media
import Box
from config import add_sheet, g, watch_file
from own_types import (Auto, AutoLP4Tuple, BugError, CompValue, Dimension,
                       DisplayType, Float4Tuple, Font, FontStyle, Normal,
                       NormalType, Number, Percentage, Rect, StyleComputed,
                       StyleInput, Surface, _XMLElement)
from Style import (SourceSheet, StyleRule, abs_default_style, bc_getter,
                   br_getter, bs_getter, bw_keys, get_style, inset_getter,
                   pack_longhands, parse_file, parse_sheet, prio_keys,
                   style_attrs)
from util import (Calculator, get_groups, get_tag, group_by_bool, log_error,
                  print_once)

""" More useful links for further development
https://developer.mozilla.org/en-US/docs/Web/CSS/image
"""

########################## Specificity and Rules #############################
Spec = tuple[int, int, int]


def add_specs(t1: Spec, t2: Spec) -> Spec:
    id1, cls1, tag1 = t1
    id2, cls2, tag2 = t2
    return (id1 + id2, cls1 + cls2, tag1 + tag2)


sum_specs: Callable[[Iterable[Spec]], Spec] = lambda specs: reduce(add_specs, specs)

################################# Globals ###################################


@dataclass(frozen=True, slots=True)
class TextDrawItem:
    text: str
    element: "Element"
    xpos: float

    @property
    def height(self):
        return self.element.line_height


class Line(tuple[TextDrawItem]):
    @property
    def height(self):
        return max([0, *(item.height for item in self)])


# TODO: Get an actually acceptable font
@cache
def get_font(family: list[str], size: float, style: FontStyle, weight: int) -> Font:
    font = pg.font.match_font(
        name=family,
        italic=style.value == "italic",
        bold=weight > 500,  # we don't support actual weight TODO
    ) or log_error("Failed to find font", family, style, weight)
    font: Font = Font(font, int(size))
    font.italic = style.value == "oblique"
    return font


def process_style(tag: str, val: str, key: str, p_style: StyleComputed) -> CompValue:
    def redirect(new_val: str):
        return process_style(tag, new_val, key, p_style)

    assert isinstance(val, str), val
    attr = style_attrs[key]
    ######################################## global style attributes ####################################################
    # Best and most concise explanation I could find: https://css-tricks.com/inherit-initial-unset-revert/
    match val:
        case "inherit":
            return p_style[key]
        case "initial":
            return redirect(attr.initial)
        case "unset":
            return redirect(abs_default_style[key])
        case "revert":
            return (
                redirect("inherit") if attr.inherits else redirect(get_style(tag)[key])
            )
    return (
        valid
        if (valid := attr.convert(val, p_style)) is not None or print_once("Uncomputable property found:" ,key, val)
        else redirect("unset")
    )


calculator = Calculator(None)
"""
The main shared calculator with no default percentage_val
"""


def calc_inset(inset: AutoLP4Tuple, width: float, height: float) -> Float4Tuple:
    return calculator.multi2(inset[:2], 0, height) + calculator.multi2(
        inset[2:], 0, width
    )


########################## Element ########################################


class Element:
    # General
    tag: str
    attrs: dict
    children: list[Union["Element", "TextElement"]]
    # Style
    istyle: Style.Style  # inline style
    estyle: Style.Style  # external style
    cstyle: StyleComputed  # computed_style
    # Layout + Draw
    box: Box.Box = Box.Box.empty()
    line_height: float
    white_spacing: float
    display: DisplayType  # the used display state. Is set before layout
    layout_type: DisplayType  # the used layout state. Is set before layout
    # Dynamic states
    focus: bool = False
    hover: bool = False

    def __init__(self, tag: str, attrs: dict[str, str], parent: "Element"):
        self.tag = tag
        self.attrs = attrs
        self.children = []
        self.parent = parent
        # parse element style and update default
        self.istyle = Style.parse_inline_style(attrs.get("style", ""))
        self.estyle = {}

    def is_block(self) -> bool:
        """
        Returns whether an element is a block.
        Includes side effects (as a feature) that automatically adjusts false inline elements to block layout
        """
        self.display = self.cstyle["display"]
        if self.display != "none":
            if len(self.children) == 1 and isinstance(
                elem := self.children[0], TextElement
            ):
                elem.display = self.display
            elif any(
                [child.is_block() for child in self.children]
            ):  # set all children to blocked
                self.display = "block"
                for child in self.real_children:
                    if child.display == "inline":
                        child.display = "block"
        return self.display == "block"

    def get_height(self) -> float:
        # -1 is a sentinel for height not set yet
        return self.box.height if self.box.height != -1 else self.parent.get_height()

    @property
    def input_style(self) -> StyleInput:
        """The total input style. Fused from inline and external style"""
        return Style.remove_important(Style.join_styles(self.istyle, self.estyle))

    ####################################  Main functions ######################################################
    @cache
    def matches(self, selector: "Selector"):
        """Returns whether the given Selector matches the Element, cached"""
        return selector(self)

    def collide(self, pos: Dimension) -> Iterable["Element"]:
        """
        The idea of this function is to get which elements were hit for focus, hover, etc.
        """
        # TODO: z-index
        for x in chain.from_iterable(
            c.collide(pos) for c in reversed(self.real_children)
        ):
            yield x
        if self.box.border_box.collidepoint(pos):
            yield self

    def compute(self):
        """
        Assembles the input style and then converts it into the Elements computed style.
        It then computes all the childrens styles
        """
        input_style = get_style(self.tag) | self.input_style
        keys = sorted(input_style.keys(), key=prio_keys.__contains__, reverse=True)
        parent_style = dict(self.parent.cstyle)
        style: StyleComputed = {}
        for width_key in keys:
            val = input_style[width_key]
            new_val = process_style(self.tag, val, width_key, parent_style)
            assert new_val is not None, BugError(
                f"Style {width_key} was set to None. Which should never happen."
            )
            style[width_key] = new_val
            if width_key in prio_keys:
                parent_style[width_key] = new_val
        # corrections
        """ mdn border-width: 
        absolute length or 0 if border-style is none or hidden
        """
        for width_key, bstyle in zip(bw_keys, bs_getter(style)):
            if bstyle in ("none", "hidden"):
                style[width_key] = 0
        # actual value calculation:
        fsize: float = style["font-size"]
        lh: float | NormalType | Percentage = style["line-height"]
        wspace = style["word-spacing"]
        wspace: float | Percentage = Percentage(100) if wspace is Normal else wspace
        self.font = get_font(
            style["font-family"], fsize, style["font-style"], style["font-weight"]
        )
        self.line_height = (
            lh
            if isinstance(lh, Number)
            else 1.5 * fsize
            if lh is Normal
            else lh * fsize
        )
        self.word_spacing = (
            wspace
            if isinstance(wspace, Number)
            else self.font.size(" ")[0]
            if wspace is Normal
            else self.font.size(" ")[0] * wspace
        )
        self.cstyle = g["cstyles"].add(style)
        for child in self.children:
            child.compute()

    def layout(self, width: float) -> None:  # !
        """
        Layout an element. Gets the width it has available
        """
        if self.display == "none":
            self.layout_type = "none"
            return
        style = self.cstyle
        self.box, set_height = Box.make_box(
            width, style, self.parent.box.width, self.parent.get_height()
        )
        if any(c.display == "block" for c in self.children):
            self.layout_type = "block"
            self.layout_children(set_height)
        else:
            # with word-wrap but not between words if they are too long
            # https://stackoverflow.com/a/46220683/15046005
            self.layout_type = "inline"
            width = self.box.content_box.width
            xpos: float = 0
            current_line: list[TextDrawItem] = []
            lines: list[Line] = []

            def line_break():
                nonlocal xpos
                xpos = 0
                lines.append(Line(current_line))
                current_line.clear()

            for elem in self._text_iter_desc():
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
            lines.append(Line(current_line))
            set_height(sum(line.height for line in lines))
            self.lines = lines

    def layout_children(self, set_height: Callable[[float], None]):
        inner: Rect = self.box.content_box
        x_pos = inner.x
        y_cursor = inner.y
        # https://developer.mozilla.org/en-US/docs/Web/CSS/CSS_Box_Model/Mastering_margin_collapsing
        last_margin = 0  # TODO: Margin collapsing
        flow, no_flow = group_by_bool(
            self.real_children,
            lambda x: x.cstyle["position"] in ("static", "relative", "sticky"),
        )
        for child in flow:
            child.layout(inner.width)
            top, right, bottom, left = calc_inset(
                inset_getter(self.cstyle), self.box.width, self.box.height
            )
            child.box.set_pos(
                (
                    (x_pos, y_cursor)
                    if child.cstyle["position"] == "sticky"
                    else (bottom - top + x_pos, right - left + y_cursor)
                )
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

    def draw(self, surf: Surface, pos: Dimension):
        """
        Draws the element to the `surf` at `pos`
        """
        if self.display == "none":
            return
        style = self.cstyle
        # setup
        draw_box = self.box.copy()
        draw_box.pos += pos
        border_box = draw_box.border_box
        drawing_border = any(draw_box.border)
        # https://web.dev/howbrowserswork/#the-painting-order
        # 1.+ 3. draw background and border:
        if not drawing_border:
            pg.draw.rect(surf, style["background-color"], border_box)
        else:
            rounded_box.draw_box(
                surf,
                border_box,
                style["background-color"],
                bc_getter(style),
                draw_box.border,
                tuple(
                    (
                        int(calculator(brx, perc_val=border_box.width)),
                        int(calculator(bry, perc_val=border_box.height)),
                    )
                    for brx, bry in br_getter(style)
                ),
            )
        # 4. draw children
        if self.layout_type == "block":
            for c in self.real_children:
                c.draw(surf, draw_box.content_box.topleft)
        elif self.layout_type == "inline":
            ypos = 0
            for line in self.lines:
                for item in line:
                    surf = self.font.render(
                        item.text, True, item.element.cstyle["color"]
                    )
                    surf.blit(surf, (draw_box.x + item.xpos, draw_box.y + ypos))
                ypos += line.height
        else:
            raise BugError("Wrong layout_type ({self.layout_type})")

        # 5. draw outline
        # TODO
        pass

    def delete(self):
        pass

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
        out_style = pack_longhands(
            {k: f"'{_in}'->{self.cstyle[k]}" for k, _in in self.input_style.items()}
        )
        print("{")
        for item in out_style.items():
            print(f"\t{': '.join(item)},")
        print("}")

    ############################## Helpers #####################################
    def iter_anc(self) -> Iterable["Element"]:
        """Iterates over all ancestors *excluding* this element"""
        yield self.parent
        for parent in self.parent.iter_anc():
            yield parent

    def iter_desc(self) -> Iterable["Element"]:
        """Iterates over all descendants *including* this element"""
        yield self
        for x in chain.from_iterable(
            c.iter_desc() for c in self.children if not isinstance(c, TextElement)
        ):
            yield x

    def iter_siblings(self) -> Iterable["Element"]:
        for x in self.parent.children:
            if not x is self and not isinstance(x, TextElement):
                yield x
        # return filter(lambda c: not (c is self or isinstance(c, TextElement)),self.parent.children)

    def _text_iter_desc(self) -> Iterable["TextElement"]:
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
                for x in c._text_iter_desc():
                    yield x

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
        if val := attrs.get("style"):
            log_error(f"HTML-Element style was set to {val}")
            del attrs["style"]
        super().__init__("html", attrs, parent=self)
        if "lang" in self.attrs:
            g["lang"] = self.attrs["lang"]
        self.cstyle = {}

    def get_height(self) -> float:
        return self.box.height

    def layout(self):
        self.box = Box.Box(t="content-box", width=g["W"], height=g["H"])
        # all children correct their display
        assert self.is_block()
        self.layout_children(lambda height: setattr(self.box, "height", height))

    def draw(self, screen, pos):
        for c in self.children:
            c.draw(screen, pos)

    def iter_anc(self):
        return []

    def iter_siblings(self) -> Iterable["Element"]:
        return []


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

    def is_block(self):
        return False

    def collide(self):
        return []

    def compute(self):
        pass

    def layout(self, width: float):
        pass

    def draw(self, screen, pos):
        pass


class StyleElement(MetaElement):
    tag = "style"
    inline_sheet: SourceSheet | None = None
    src_sheet: SourceSheet | None = None

    def __init__(self, attrs: dict[str, str], txt: str, parent: "Element"):
        super().__init__(attrs, txt, parent)
        self.src = attrs.get("src")
        if self.src is not None:
            self.src_sheet = parse_file(self.src)
            add_sheet(self.src_sheet)
            self.src = watch_file(self.src)
        if txt:
            self.inline_sheet = parse_sheet(txt)
            add_sheet(self.inline_sheet)


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


class ImgElement(Element):
    size: None|tuple[int, int]
    given_size: tuple[int|None,int|None]
    image: Media.Image|None
    def __init__(self, tag: str, attrs: dict[str, str], parent: "Element"):
        # https://developer.mozilla.org/en-US/docs/Web/HTML/Element/img
        # TODO: 
        # decoding: await the image load before displaying anything if set to sync (other is async)
        # loading: load the image as soon as possible if set to eager (right now) only load if in view if set to lazy
        # sizes and srcset: responsiveness
        # usemap: refers to a map for clicks
        super().__init__(tag, attrs, parent)
        try:
            self.image = Media.Image(attrs["src"])
            self.given_size = (
                int(w) if (w:=attrs.get("width")) is not None else None,
                int(h) if (h:=attrs.get("height")) is not None else None
            )
        except (KeyError, ValueError):
            self.image = None
            self.given_size = (None,None)
        self.size = self.given_size if not None in self.given_size else None # type: ignore # as always mypy is too stupid

    @staticmethod
    def make_dimensions(given_size: tuple[int|None,int|None], intrinsic_size: tuple[int, int])->tuple[int,int]:
        ix,iy = intrinsic_size
        match given_size:
            case [None, None]:
                return ix,iy
            case [x, None]:
                return x, iy * x // ix
            case [None, y]:
                return ix * y // iy, y
            case [x,y]:
                return x,y
        raise ValueError(given_size)

    @staticmethod
    def crop_image(surf: Surface, to_size: Dimension):
        return pg.transform.scale(surf, to_size)

    def layout(self, width):
        if self.cstyle["display"] == "none" or self.image is None:
            return
        if self.image.is_loaded:
            self.size = self.make_dimensions(self.given_size, self.image.size)
        w,h = self.size if self.size is not None else (x or 0 for x in self.given_size)
        self.box = Box.Box(
            self.cstyle["box-sizing"],
            # TODO: add border, margin, padding
            width=w,
            height=h
        )

    def draw(self, surf, pos):
        if self.cstyle["display"] == "none" or self.image is None:
            return
        if self.size is not None and self.image.is_loaded:
            draw_surf = self.crop_image(self.image.surf, self.size)
            surf.blit(draw_surf, self.box.pos + pos)
              


class BrElement(Element):
    def _text_iter_desc(self):
        yield TextElement("\n", self)


font_split_regex = re.compile(r"\s*\,\s*")


class TextElement:
    """Special element that can't be accessed from HTML directly but represents any raw text"""

    text: str
    parent: Element
    tag = "Text"
    display = "inline"

    # Used internally
    _draw_items: list[TextDrawItem]

    def is_block(self):
        return False

    def __init__(self, text: str, parent: Element):
        self.text = text
        self.parent = parent

    def compute(self):
        pass

    def layout(self, width: float) -> None:
        pass
        # style = self.parent.style
        # families = font_split_regex.split(style["font-family"]) # this algorithm should be updated
        # families = [f.removeprefix('"').removesuffix('"') for f in families]
        # font = get_font(
        #     families,
        #     style["font-size"],
        #     style["font-style"],
        #     style["font-weight"]
        # )
        # self.font = font
        # if word_spacing == "normal":
        #     word_spacing = font.size(" ")[0] # the width of the space character in the font
        # if line_height == "normal":
        #     line_height = 1.2 * style["font-size"]
        # xcursor = ycursor = 0.0
        # self._draw_items.clear()
        # l = self.text.split()
        # for word in l:
        #     word_width, _ = font.size(word)
        #     if xcursor + word_width > width: #overflow
        #         xcursor = 0
        #         ycursor += line_height
        #     self._draw_items.append(TextDrawItem(word,(xcursor, ycursor)))
        #     xcursor += word_width + word_spacing
        # # should set a box
        # self.x, self.y = xcursor, ycursor

    def draw(self, surface: pg.surface.Surface):
        for item in self._draw_items:
            match item:
                case word, pos:
                    ...
                case _:
                    raise Exception(item)

    def to_html(self, indent=0):
        return " " * indent + self.text

    def __repr__(self):
        return f"<{self.tag}>"


def create_element(elem: _XMLElement, parent: Element | None = None):
    """Create an element"""
    tag = get_tag(elem)
    assert tag
    text = "" if elem.text is None else elem.text.strip()
    new: Element
    match tag:
        case "html":
            new = HTMLElement(tag, elem.attrib)
        case tag if (
            meta_element := globals().get(tag.capitalize() + "Element")
        ) is not None and issubclass(meta_element, MetaElement):
            # meta_elements don't need their tag, but take their text
            new = meta_element(elem.attrib, text, parent)
        case tag if (
            special_elem := globals().get(tag.capitalize() + "Element")
        ) is not None and issubclass(special_elem, Element):
            # meta_elements don't need their tag, but take their text
            new = special_elem(tag, elem.attrib, parent)
        case _:
            new = Element(tag, elem.attrib, parent)  # type: ignore[arg-type]

    children = [create_element(e, new) for e in elem]
    # insert Text Element at the top
    if text:
        children.insert(0, TextElement(text, new))
    new.children = children
    return new


def reveal_rule(rule: StyleRule):
    selector, style = rule
    return parse_selector(selector), style


def apply_rules(elem: Element, rules: list[StyleRule]):
    # filter not matching selectors and sort by specificity
    sorted_by_sel = sorted(
        (x for rule in rules if elem.matches((x := reveal_rule(rule))[0])),
        key=lambda rule: rule[0].spec,
    )
    # sort by importance
    elem.estyle = dict(
        sorted(
            chain.from_iterable(style.items() for _, style in sorted_by_sel),
            key=lambda t: Style.is_imp(t[1]),
        )
    )
    for c in elem.real_children:
        apply_rules(c, rules)


EmptyElement = Element("empty", {}, HTMLElement("html", {}, None))
EmptyElement.parent = None  # type: ignore

################################### Rest is commentary in nature #########################################


class InlineElement(Element):
    """This is the interface of an element with display = "inline" """


################################# Selectors #######################################
# https://www.w3.org/TR/selectors-3/
"""
Handles everything revolving Selectors. 
Includes parsing (text->Selector)
"""

Selector = Union["SingleSelector", "CompositeSelector"]


class SingleSelector(Protocol):
    spec: Spec

    def __call__(self: Any, elem: Element) -> bool:
        ...

    def __hash__(self) -> int:
        return super().__hash__()


@dataclass(frozen=True, slots=True)
class TagSelector:
    tag: str
    spec = 0, 0, 1
    __call__ = lambda self, elem: elem.tag == self.tag
    __str__ = lambda self: self.tag  # type: ignore[attr-defined]


@dataclass(frozen=True, slots=True)
class IdSelector:
    id: str
    spec = 1, 0, 0
    __call__ = lambda self, elem: elem.attrs.get("id") == self.id
    __str__ = lambda self: "#" + self.id  # type: ignore[attr-defined]


@dataclass(frozen=True, slots=True)
class ClassSelector:
    cls: str
    spec = 0, 1, 0
    __call__ = lambda self, elem: elem.attrs.get("class") == self.cls
    __str__ = lambda self: "." + self.cls  # type: ignore[attr-defined]


@dataclass(frozen=True, slots=True)
class HasAttrSelector:
    name: str
    spec = 0, 1, 0
    __call__ = lambda self, elem: self.name in elem.attrs
    __str__ = lambda self: f"[{self.name}]"  # type: ignore[attr-defined]


# the validator takes the soll value and the is value
def make_attr_selector(sign: str, validator):
    sign = re.escape(sign)
    regex = re.compile(
        rf'\[{s}(\w+){s}{sign}={s}"(\w+)"{s}\]|\[{s}(\w+){s}{sign}={s}(\w+){s}\]'
    )

    @dataclass(frozen=True, slots=True)
    class AttributeSelector:
        name: str
        value: str
        spec = 0, 1, 0

        def __call__(self, elem: Element):
            return (value := elem.attrs.get(self.name)) is not None and validator(
                self.value, value
            )

        def __str__(self):
            return f'[{self.name}{sign}="{self.value}"]'

    return regex, AttributeSelector


@dataclass(frozen=True, slots=True)
class AnySelector:
    spec = 0, 0, 0

    def __call__(self, elem: Element):
        return True

    def __str__(self):
        return "*"


@dataclass(frozen=True, slots=True)
class NeverSelector:
    spec: Spec
    s: str

    def __call__(self, elem: Element):
        return False

    def __str__(self):
        return self.s


################################## Composite Selectors ###############################
class CompositeSelector:
    selectors: tuple[Selector, ...]
    spec: cached_property[Spec]

    def __call__(self: Any, elem: Element) -> bool:
        ...

    def __hash__(self) -> int:
        return super().__hash__()


joined_specs = lambda self: sum_specs(f.spec for f in self.selectors)


@dataclass(frozen=True, slots=True)
class AndSelector(CompositeSelector):
    selectors: tuple[Selector, ...]
    spec = cached_property(joined_specs)
    __call__ = lambda self, elem: all(elem.matches(sel) for sel in self.selectors)
    __str__ = lambda self: "".join(str(s) for s in self.selectors)  # type: ignore[attr-defined]


@dataclass(frozen=True, slots=True)
class OrSelector(CompositeSelector):
    selectors: tuple[Selector, ...]
    spec = cached_property(joined_specs)
    __call__ = lambda self, elem: any(elem.matches(sel) for sel in self.selectors)
    __str__ = lambda self: ", ".join(str(s) for s in self.selectors)  # type: ignore[attr-defined]


@dataclass(frozen=True, slots=True)
class DirectChildSelector(CompositeSelector):
    selectors: tuple[Selector, ...]
    spec = cached_property(joined_specs)

    def __call__(self, elem: Element):
        chain = [elem, *elem.iter_anc()]
        if len(chain) != len(self.selectors):
            return False
        return all(parent.matches(sel) for parent, sel in zip(chain, self.selectors))

    __str__ = lambda self: " > ".join(str(s) for s in self.selectors)  # type: ignore[attr-defined]


@dataclass(frozen=True, slots=True)
class ChildSelector(CompositeSelector):
    selectors: tuple[Selector, Selector]
    spec = cached_property(joined_specs)

    def __call__(self, elem: Element):
        own_sel, p_sel = self.selectors
        if not own_sel(elem):
            return False
        return any(p.matches(p_sel) for p in elem.iter_anc())

    __str__ = lambda self: " ".join(str(s) for s in self.selectors)  # type: ignore[attr-defined]


########################################## Parser #######################################################
s = r"\s*"
sngl_p = re.compile(
    r"((?:\*|(?:#\w+)|(?:\.\w+)|(?:\[\s*\w+\s*\])|(?:\[\s*\w+\s*[~|^$*]?=\s*\w+\s*\])|(?:\w+)))$"
)
rel_p = re.compile(r"\s*([>+~ ])\s*$")  # pretty simple

attr_sel_data = [
    ("", lambda soll, _is: soll == _is),
    ("~", lambda soll, _is: soll in _is.split()),
    ("|", lambda soll, _is: soll == _is or _is.startswith(soll + "-")),
    ("^", lambda soll, _is: _is.startswith(soll)),
    ("$", lambda soll, _is: _is.endswith(soll)),
    ("*", lambda soll, _is: soll in _is),
]
attr_patterns: list[tuple[re.Pattern, Type[Selector]]] = [
    (re.compile(r"\[(\w+)\]"), HasAttrSelector),
    *(make_attr_selector(sign, validator) for sign, validator in attr_sel_data),
]


def matches(s: str, pattern: re.Pattern):
    """
    Takes a string and a pattern and returns the reststring and the capture
    """
    if not ((match := pattern.search(s)) and (length := len(match.group()))):
        return None
    if not (groups := [g for g in match.groups() if g]):
        return None
    return (s[:-length], groups[0])


class InvalidSelector(ValueError):
    pass


@cache
def parse_selector(s: str) -> Selector:
    s = start = s.strip()
    if not s:
        raise BugError("Empty selector")
    if "," in s:
        return OrSelector(tuple(parse_selector(x) for x in s.split(",")))
    else:
        singles: list[str] = []
        # do-while-loop
        while True:
            if match := matches(s, sngl_p):
                s, subsel = match
                singles.insert(0, subsel)
                if not s:  # recursive anker
                    return proc_singles(singles)
            elif match := matches(s, rel_p):
                s, rel = match
                if not s or not singles:
                    raise InvalidSelector(
                        f"Relative selectors are not padded by single selectors: ({rel},{start})"
                    )
                sngl_selector = proc_singles(singles)
                match rel:
                    case " ":
                        return ChildSelector((parse_selector(s), sngl_selector))
                    case ">":
                        return DirectChildSelector((parse_selector(s), sngl_selector))
                    case "+":
                        raise NotImplementedError("+ is not implemented yet")
                    case "~":
                        raise NotImplementedError("~ is not implemented yet")
                    case _:
                        raise BugError(f"Invalid relative selector ({rel})")
            else:
                raise InvalidSelector(f"Couldn't match '{s}'")


def proc_singles(groups: list[str]) -> Selector:
    if len(groups) == 1:
        return proc_single(groups[0])
    return AndSelector(tuple(proc_single(s) for s in groups))


def proc_single(s: str) -> Selector:
    if s == "*":
        return AnySelector()
    elif s[0] == "#":
        return IdSelector(s[1:])
    elif s[0] == ".":
        return ClassSelector(s[1:])
    elif s[0] == "[":
        for pattern, selector in attr_patterns:
            if (groups := get_groups(s, pattern)) is not None:
                return selector(*groups)
        raise BugError(f"Invalid attribute selector: {s}")
    elif s[0] == ":":  # pseudoclass
        raise RuntimeError("Pseudoclasses are not supported yet")
    else:
        return TagSelector(s)
