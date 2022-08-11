import re
from contextlib import contextmanager
from copy import copy
from dataclasses import dataclass
from functools import cache, reduce
from itertools import chain, takewhile
from tokenize import single_quoted
from typing import Any, Callable, Iterable, Iterator, Mapping, Protocol, Type, cast

import cssutils
import tinycss
import pygame as pg

from Box import Box, make_box
from config import g
from own_types import (Auto, AutoNP4Tuple, BugError, Color, Dimension, Float4Tuple, Font,
                       FontStyle, ReadChain, Rect, Surface, Vector2, _XMLElement,
                       computed_value, style_computed, style_input)
from StyleComputing import abs_default_style, get_style, priority, style_attrs, postprocess
from util import (Calculator, bc_getter, fetch_src, get_tag, inset_getter,
                  log_error, rect_lines, watch_file, bs_getter, directions, bw_getter, bw_setter)

""" More useful links for further development
https://developer.mozilla.org/en-US/docs/Web/CSS/image
https://developer.mozilla.org/en-US/docs/Web/CSS/CSS_Box_Model/Mastering_margin_collapsing
"""

########################## Specificity and Rules #############################
# class Rule(TypedDict):
#     selector: 'Selector'
Rule = Mapping[str, Any] # A Rule is just a dict with a selector key joined with a style_input dict
def rule_style(rule):
    return {k:v for k,v in rule.items() if k != 'selector'}

Spec = tuple[int, int, int]

def add_specs(t1: Spec, t2: Spec) -> Spec:
    id1,cls1,tag1 = t1
    id2,cls2,tag2 = t2
    return id1+id2, cls1+cls2, tag1+tag2

sum_specs: Callable[[Iterable[Spec]],Spec] = lambda specs: reduce(add_specs, specs)

################################# Globals ###################################

@cache
def get_font(family: list[str], size: float, style: FontStyle, weight: int) -> Font:
    font = pg.font.match_font(
        name=family,
        italic=style.value == "italic",
        bold=weight > 500,  # we don't support actual weight TODO
    )
    if font is None:
        log_error("Failed to find font", family, style, weight)
    font: Font = Font(font, int(size))
    if (
        style.value == "oblique"
    ):  # TODO: we don't support oblique with an angle, we just fake the italic
        font.italic = True
    return font


def process_style(
    elem: "Element", val: str, key: str, p_style: style_computed = None
) -> computed_value:
    p_style = p_style if p_style is not None else elem.cstyle

    def redirect(new_val: str):
        return process_style(elem, new_val, key, p_style)

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
                redirect("inherit")
                if attr.inherits
                else redirect(get_style(elem.tag)[key])
            )
    return (
        valid
        if (valid := attr.convert(val, p_style)) is not None
        else redirect("unset")
    )

calculator = Calculator(None)


def calc_inset(inset: AutoNP4Tuple, width: float, height: float) -> Float4Tuple:
    return calculator.multi2(inset[:2], 0, height) + calculator.multi2(
        inset[2:], 0, width
    )


########################## Element ########################################

class Element:
    box: Box = Box.empty()
    display: str  # the used display state. Is set before layout
    tag: str
    attrs: dict
    istyle: style_input  # inline style
    estyle: style_input  # external style
    cstyle: style_computed  # computed_style
    children: list["Element"]
    focus: bool = False

    def __init__(self, tag: str, attrs: dict[str, str], parent: "Element"):
        self.children = []
        self.parent = parent
        self.tag = tag
        self.attrs = attrs
        # parse element style and update default
        self.istyle = postprocess(dict(cssutils.parseStyle(attrs.get("style", ""))))
        self.estyle = {}

    def is_block(self) -> bool:
        """
        Returns whether an element is a block.
        Includes side effects (as a feature) that automatically adjusts false inline elements to block layout
        """
        self.display = self.cstyle["display"]  # type: ignore
        if self.display != "none":
            any_child_block = any([child.is_block() for child in self.children])
            if any_child_block:  # set all children to blocked
                for child in self.real_children:
                    child.display = "block"
                self.display = "block"
        return self.display == "block"

    def get_height(self) -> float:
        if self.box.height == -1:  # sentinel: height not set yet
            assert self.parent != self, self
            return self.parent.get_height()
        else:
            return self.box.height

    ####################################  Main functions ######################################################
    @cache
    def matches(self, selector: 'Selector'):
        return selector(self)

    def collide(self, pos: Dimension) -> Iterable["Element"]:
        """
        The idea of this function is to get which elements were hit for focus, hover and mouse events
        """
        rv: list[Iterable[Element]] = []
        # check which children were hit
        if self.children:
            rv = [c.collide(pos) for c in reversed(self.children)]
        # check if we were hit and add us if so
        if self.box.border_box.collidepoint(pos):
            rv.append([self])
        return chain(*rv)

    def compute(self):
        """ 
        Assembles the input style and then converts it into the Elements computed style.
        It then computes all the childrens styles
        """
        input_style = ReadChain(self.estyle, self.istyle, get_style(self.tag))
        prioritates = priority(input_style)
        parent_style = self.parent.cstyle
        style: style_computed = {}
        for key in input_style & style_attrs.keys():
            val = input_style[key]
            new_val = process_style(self, val, key, parent_style)
            assert (
                new_val is not None
            ), f"Style {key} was set to None. Which should never happen."
            style[key] = new_val
            if key in ("color","fontsize"):
                parent_style[key] = new_val
        # corrections
        bw_setter(style, tuple(
            0 if _style in ("none", "hidden") else width
            for _style, width in zip(bs_getter(style), bw_getter(style))
        ))
        for key, value in zip(directions, bs_getter(style)):
            if value in ("none", "hidden"):
                style[key] = 0
        self.cstyle = g["cstyles"].safe(style)
        for child in self.children:
            child.compute()

    def layout(self, width: float) -> None:  # !
        """
        Gets the width it has available
        The input width is the width the child should take if its width is Auto

        Layouts the childrens elements and sets used values for not fully resolved style-attributes.
        Also sets the box property which determines the positioning of every element

        Layout uses attributes like:
        top, bottom, left, right
        margin, padding, border-width,
        width, height, (display),
        """
        if self.display == "none":
            self.box = Box("content-box")
            return
        self.box, set_height = make_box(
            width, self.cstyle, self.parent.box.width, self.parent.get_height()
        )
        if any(c.display == "block" for c in self.children):
            with self.layout_children() as height:
                set_height(height)
        else:  # all children are inline
            # Algorithmic idea
            # convert our children to a list of (text, style) tuples and
            # lay it out with perfect knowledge about our own width
            # save this list
            # then in the draw function we can use it
            set_height(0)

    @contextmanager
    def layout_children(self):
        inner: Rect = self.box.content_box
        x_pos = inner.x
        y_cursor = inner.y
        children = self.real_children
        flow = [
            child
            for child in children
            if child.cstyle["position"] in ("static", "relative", "sticky")
        ]
        no_flow = [
            child
            for child in children
            if child.cstyle["position"] in ("absolute", "fixed")
        ]
        for child in flow:
            child.layout(inner.width)
            # calculate the position
            top, bottom, left, right = calc_inset(
                inset_getter(self.cstyle), self.box.width, self.box.height
            )
            inset: tuple[float, float] = (
                (0, 0)
                if child.cstyle["position"] == "sticky"
                else (bottom - top, right - left)
            )
            cx, cy = Vector2(x_pos, y_cursor) + inset
            child.box.set_pos((cx, cy))
            y_cursor += child.box.outer_box.height
        yield y_cursor
        for child in no_flow:
            child.layout(inner.width)
            # calculate position
            top, bottom, left, right = calc_inset(
                inset_getter(self.cstyle), self.box.width, self.box.height
            )
            cy: float = (
                top
                if top is not Auto
                else self.get_height() - bottom
                if bottom is not Auto
                else 0
            )
            cx: float = (
                left
                if left is not Auto
                else inner.width - right
                if right is not Auto
                else 0
            )
            child.box.set_pos((cx, cy))

    def draw(self, screen: Surface, pos: Dimension):
        # https://web.dev/howbrowserswork/#the-painting-order
        if self.display == "none":
            return
        style = self.cstyle
        draw_box = copy(self.box)
        x_off, y_off = pos
        draw_box.x += x_off
        draw_box.y += y_off
        # Now x and y represent the real position on the canvas (before it was the position in the content_box of the parent)
        border_box: Rect = draw_box.border_box
        colors = bc_getter(style)
        # 1. draw background:
        pg.draw.rect(screen, style["background-color"], border_box)  # type: ignore[arg-type]
        # 2. draw background-image
        # TODO
        # 3. draw border
        if any(draw_box.border):
            assert any(b=="solid" for b in bs_getter(style))
            if (
                (bw := draw_box.border[0])
                and all(w == bw for w in draw_box.border)
                and (bc := colors[0])
                and all(c == bc for c in colors)
            ):  # the most common case (border-width and -color are uniform)
                pg.draw.rect(screen, bc, border_box, int(bw))
            else:  # every line has to be drawn individually but we have no border-radii
                for line, width, color in zip(
                    rect_lines(border_box), draw_box.border, colors
                ):
                    pg.draw.line(screen, color, *line, int(width))  # type: ignore # TODO: kill mypy for not letting me use *
        # 4. draw children
        for c in self.real_children:
            c.draw(screen, draw_box.content_box.topleft)
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
        attrs = [f'{k} = "{v}"' for k, v in self.attrs.items()]
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

    ############################## Helpers #####################################
    def iter_parents(self) -> Iterator["Element"]:
        """Iterates over the elements parents *excluding* itself"""
        while True:
            self = self.parent
            yield self
            if type(self) is HTMLElement:
                break

    def iter_children(self) -> Iterator["Element"]:
        """Iterates over all children *including* this element"""
        for x in chain(
            [self],
            *(
                c.iter_children()
                for c in self.children
                if not isinstance(c, TextElement)
            ),
        ):
            yield x

    @property
    def real_children(self):
        return [c for c in self.children if not isinstance(c, (TextElement, MetaElement))]

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

    def compute(self):
        super().compute()

    def layout(self):
        self.box = Box(t="content-box", width=g["W"], height=g["H"])
        # all children correct their display
        assert self.is_block()
        # the maximum width is g["W"] # we might also add a scrollable window in the future. Then any overflowed element will still be viewable
        with self.layout_children():
            pass

    def draw(self, screen, pos):
        for c in self.children:
            c.draw(screen, pos)


class MetaElement(Element):
    """
    A MetaElement is an Element that's sole purpose is conveying information
    to the runtime and is not for display or interaction.
    It has no style, the display is "none" 
    """

    tag: str
    display = "none"

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

    def __init__(self, attrs: dict[str, str], txt: str, parent: "Element"):
        super().__init__(attrs, txt, parent)
        self.rules: list[Rule] = []
        self.src = attrs.get("src")
        if self.src is not None:
            self.reg_rules(fetch_src(attrs["src"]))
            watch_file(self.src)
        if txt:
            self.reg_rules(txt)

    def reg_rules(self, src: str):
        """Register a set of new rules from the given string"""
        rules: cssutils.css.CSSRuleList = cssutils.parseString(src).cssRules
        newRules: list[Rule] = [
            postprocess(dict(rule.style))|{"selector": parse_selector(rule.selectorText)}
            for rule in rules
        ]
        g["css_rules_dirty"] |= bool(newRules)
        self.rules.extend(
            [g["css_rules"].safe(rule) for rule in newRules]
        )

    def delete(self):
        if self.src is not None:
            pass # TODO: remove the file from watched files

class TitleElement(MetaElement):
    tag = "title"

    def __init__(self, attrs: dict[str, str], txt: str, parent: "Element"):
        super().__init__(attrs, txt, parent)
        g["title"] = txt


class CommentElement(MetaElement):
    tag = "!comment"

    def to_html(self, indent = 0):
        return f"{' '*indent}<!--{self.text}-->"

    def __repr__(self):
        return self.to_html()


class IMGElement(Element):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # eg fetch the image and save a reference in this element

    def layout(self, width):
        pass


@dataclass(slots=True)
class TextDrawItem:
    text: str
    pos: Dimension


font_split_regex = re.compile(r"\s*\,\s*")


class TextElement:
    """Special element that can't be accessed from HTML directly but represent any raw text"""

    text: str
    parent: Element
    style: style_computed
    font: pg.font.Font
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
        case _:
            new = Element(tag, elem.attrib, parent)  # type: ignore[arg-type]

    children = [create_element(e, new) for e in elem]
    # insert Text Element at the top
    if text:
        children.insert(0, TextElement(text, new))
    new.children = children
    return new


def apply_rules(elem: "Element", rules: list[Rule]):
    l = [rule for rule in rules if rule["selector"](elem)]
    l.sort(key=lambda rule: rule["selector"].spec, reverse=True) # highest selector first
    elem.estyle = dict(ReadChain(*(rule_style(rule) for rule in l)))
    for c in elem.real_children:
        apply_rules(c, rules)


EmptyElement = Element("empty", {}, HTMLElement("html", {}, None))
EmptyElement.parent = None  # type: ignore

################################### Rest is commentary in nature #########################################


class InlineElement(Element):
    """This is the interface of an element with display = "inline" """

################################# Selectors #######################################
"""
Handles everything revolving Selectors. 
Includes a Parser (text->Selector)
"""
from typing import Sequence
from contextlib import suppress 
from functools import cached_property
from own_types import Enum, enum_auto
from util import get_groups

class Selector(Protocol):
    spec: Spec|cached_property[Spec]
    def __call__(self: Any, elem: Element)->bool:
        ...
    def __hash__(self) -> int:
        return super().__hash__()

@dataclass(frozen=True, slots=True)
class TagSelector:
    tag: str
    spec = 0,0,1
    __call__ = lambda self, elem: elem.tag == self.tag
    __str__ = lambda self: self.tag #type: ignore[attr-defined]

@dataclass(frozen=True, slots=True)
class IdSelector:
    id: str
    spec = 1,0,0
    __call__ = lambda self, elem: elem.attrs.get("id") == self.id
    __str__ = lambda self: "#"+self.id #type: ignore[attr-defined]

@dataclass(frozen=True, slots=True)
class ClassSelector:
    cls: str
    spec = 0,1,0
    __call__ = lambda self, elem: elem.attrs.get("class") == self.cls
    __str__ = lambda self: "."+self.cls #type: ignore[attr-defined]

@dataclass(frozen=True, slots=True)
class HasAttrSelector:
    name: str
    spec = 0,1,0
    __call__ = lambda self, elem: self.name in elem.attrs
    __str__ = lambda self: f'[{self.name}]' #type: ignore[attr-defined]

# the validator takes the soll value and the is value
def make_attr_selector(sign: str, validator):
    sign = re.escape(sign)
    regex = re.compile(fr'\[{s}(\w+){s}{sign}={s}"(\w+)"{s}\]|\[{s}(\w+){s}{sign}={s}(\w+){s}\]')
    @dataclass(frozen=True, slots=True)
    class AttributeSelector:
        name: str
        value: str
        spec = 0,1,0
        def __call__(self, elem: Element):
            return (value:=elem.attrs.get(self.name)) is not None and validator(self.value, value)
        def __str__(self):
            return f'[{self.name}{sign}="{self.value}"]'
    return regex, AttributeSelector

@dataclass(frozen=True, slots=True)
class AnySelector:
    spec = 0,0,0
    def __call__(self, elem: Element): return True
    __str__ = lambda self: "*"

@dataclass(frozen=True, slots=True)
class NeverSelector:
    spec: Spec
    s: str
    def __call__(self, elem: Element): return False
    def __str__(self): return self.s

################################## Composite Selectors ###############################
class CompositeSelector(Selector):
    selectors: Sequence[Selector]

joined_specs = lambda self: sum_specs(f.spec for f in self.selectors)
@dataclass(frozen=True, slots=True)
class AndSelector:
    selectors: tuple[Selector,...]
    spec = cached_property(joined_specs)
    __call__ = lambda self, elem: all(elem.matches(sel) for sel in self.selectors)
    __str__ = lambda self: ''.join(str(s) for s in self.selectors) #type: ignore[attr-defined]

@dataclass(frozen=True, slots=True)
class OrSelector:
    selectors: tuple[Selector,...]
    spec = cached_property(joined_specs)
    __call__ = lambda self, elem: any(elem.matches(sel) for sel in self.selectors)
    __str__ = lambda self: ', '.join(str(s) for s in self.selectors) #type: ignore[attr-defined]

@dataclass(frozen=True, slots=True)
class DirectChildSelector:
    selectors: tuple[Selector, ...]
    spec = cached_property(joined_specs)
    def __call__(self, elem: Element):
        chain = [elem,*elem.iter_parents()]
        if len(chain) != len(self.selectors): return False
        return all(parent.matches(sel) for parent, sel in zip(chain, self.selectors))
    __str__ = lambda self: " > ".join(str(s) for s in self.selectors) #type: ignore[attr-defined]

@dataclass(frozen=True, slots=True)
class ChildSelector:
    selectors: tuple[Selector, Selector]
    spec = cached_property(joined_specs)
    def __call__(self,elem: Element):
        own_sel, p_sel = self.selectors
        if not own_sel(elem): return False
        return any(p.matches(p_sel) for p in elem.iter_parents())
    __str__ = lambda self: " ".join(str(s) for s in self.selectors) #type: ignore[attr-defined]

########################################## Parser #######################################################
s = r'\s*'
sngl_p = re.compile(r"((?:\*|(?:#\w+)|(?:\.\w+)|(?:\[\s*\w+\s*\])|(?:\[\s*\w+\s*[~|^$*]?=\s*\w+\s*\])|(?:\w+)))$")
rel_p = re.compile(r"\s*([> +~])\s*$") # pretty simple

attr_sel_data= [
    ("", lambda soll,_is: soll==_is),
    ("~", lambda soll,_is: soll in _is.split()),
    ("|", lambda soll,_is: soll==_is or _is.startswith(soll+"-")),
    ("^", lambda soll,_is: _is.startswith(soll)),
    ("$", lambda soll,_is: _is.endswith(soll)),
    ("*", lambda soll,_is: soll in _is),
]
attr_patterns: list[tuple[re.Pattern, Type[Selector]]] = [
    (re.compile(r'\[(\w+)\]'),HasAttrSelector),
    *(make_attr_selector(sign, validator) for sign,validator in attr_sel_data)
]

def matches(s: str, pattern: re.Pattern):
    match = pattern.search(s)
    if not (match and (length := match.end() - match.start())):
        return None
    groups: list[str] = [stripped for g in match.groups()
        if isinstance(g, str) and (stripped:=g.strip())]
    if not groups: return None
    return (s[:-length], groups[0])

InvalidSelector = ValueError("Invalid Selector")
def parse_selector(s: str) -> Selector:
    s = s.strip()
    if not s: raise BugError("Empty selector")
    if "," in s:
        return cast(Selector,
            OrSelector(tuple(parse_selector(x) for x in s.split(",")))
        )
    else:
        singles: list[str] = []
        # do-while-loop
        while True:
            if (match:=matches(s, sngl_p)):
                s, subsel = match
                singles.insert(0,subsel)
                if not s: # recursive anker
                    return proc_singles(singles)
            elif (match:=matches(s, rel_p)):
                s, subsel = match
                if not s:
                    raise InvalidSelector
                return get_rel(subsel)(
                    (
                        parse_selector(s),
                        proc_singles(singles)
                    )
                )
            else:
                raise InvalidSelector

def get_rel(rel: str)->Type[Selector]:
    """ Get the relative selector class of a character"""
    match rel:
        case " ":
            return ChildSelector
        case ">":
            return DirectChildSelector
        case "+":
            raise NotImplementedError("+ is not implemented yet")
        case "~":
            raise NotImplementedError("~ is not implemented yet")
        case "_":
            raise BugError("Invalid relative selector")
    raise BugError("Invalid relative selector")

def proc_singles(groups: list[str])->Selector:
    if len(groups) == 1: return proc_single(groups[0])
    return AndSelector(tuple(proc_single(s) for s in groups))

def proc_single(s: str)->Selector:
    if s == "*":
        return AnySelector()
    elif s[0] == "#":
        return IdSelector(s[1:])
    elif s[0] == ".":
        return ClassSelector(s[1:])
    elif s[0] == "[":
        for pattern, selector in attr_patterns:
            if (groups:=get_groups(s, pattern)) is not None:
                return selector(*groups)
        raise BugError(f"Invalid attribute selector: {s}")
    elif s[0] == ":": # pseudoclass
        raise RuntimeError("Pseudoclasses are not supported yet")
    else:
        return TagSelector(s)
