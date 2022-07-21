from copy import copy
import re
from collections import ChainMap, defaultdict
from contextlib import contextmanager, suppress
from functools import cache
from itertools import chain
from typing import Any, Iterable, NamedTuple, Type

import pygame as pg
from pygame import Vector2

import own_css_parser as css
from Box import Box, empty_box, is_box_empty, make_box
from config import g
from own_types import (Auto, Color, ComputeError, Dimension, FontStyle, Normal,
                       Number, Percentage, Sentinel, StyleAttr, _XMLElement,
                       computed_value, style_computed, style_input)
from style_cache import safe_style
from util import get_tag, inset_getter, log_error, rect_lines, split_units

""" More useful links for further development
https://developer.mozilla.org/en-US/docs/Web/CSS/image
https://developer.mozilla.org/en-US/docs/Web/CSS/CSS_Box_Model/Mastering_margin_collapsing
"""
################################# Globals ###################################

################################# shared methods (could also be classmethods in theory) ##################
@cache
def get_font(family: list[str], size: Number, style: FontStyle, weight: int)->pg.font.Font:
    font = pg.font.match_font(
        name = family,
        italic = style.value == "italic", 
        bold = weight > 500 # we don't support actual weight TODO
    )
    if font is None:
        log_error("Failed to find font", family, style, weight)
    font = pg.font.Font(font, int(size))
    if style.value == "oblique": # TODO: we don't support oblique with an angle, we just fake the italic
        font.italic = True
    return font

################################## Style Data ################################
# To add a new style key, document it, add it here and then implement it in the draw or layout methods

style_keys: dict[str, StyleAttr] = {
    "color":StyleAttr("canvastext"), 
    "font-weight": StyleAttr("normal"),
    "font-family":StyleAttr("Arial"),
    "font-size":StyleAttr("medium"), 
    "font-style":StyleAttr("normal"),
    "line-height": StyleAttr("normal", False),
    "word-spacing": StyleAttr("normal", False),
    "display":StyleAttr("inline"),
    "background-color": StyleAttr("transparent"),
    "width":StyleAttr("auto", isinherited = False),
    "height":StyleAttr("auto", isinherited = False),
    "position": StyleAttr("static", isinherited = False),
    "box-sizing": StyleAttr("content-box", isinherited = False),
    **dict.fromkeys(g["inset-keys"],StyleAttr("0", False)),
    **dict.fromkeys(g["margin-keys"], StyleAttr("0", False)),
    **dict.fromkeys(g["padding-keys"], StyleAttr("0", False)),
    **dict.fromkeys(g["border-width-keys"], StyleAttr("medium", False)),
}

""" The default style for a value (just like "unset") """
absolute_default_style = {
    **{k:"inherit" if v.isinherited else v.initial for k,v in style_keys.items()},
}

element_styles: dict[str, dict[str, Any]] = defaultdict(dict,{
    "html": g["global_stylesheet"],
    "head": {
        "display": "none",
    },
    "h1": {
        "font-size":"30px"
    },
    "p":{
        "display": "block",
        "margin-top": "1em",
        "margin-bottom": "1em",
    }
})

@cache
def get_style(tag: str)->style_input:
    return ChainMap(absolute_default_style, element_styles[tag])

def process_style(elem: 'Element', val: str, key: str, parent_style: style_computed)->computed_value:
    def redirect(new_val):
        return process_style(elem, new_val, key, parent_style)
    attr = style_keys[key]
    ######################################## global style attributes ####################################################
    # Best and most concise explanation I could find: https://css-tricks.com/inherit-initial-unset-revert/ (probably the same at mdn)
    if "inherit" == val: #----------------------------- inherit ----------------------------------------------------
        return parent_style[key]
    elif "initial" == val: #--------------------------- initial ---------------------------------------------------------------------------------
        return redirect(attr.initial)
    elif "unset" == val: #----------------------------- unset ---------------------------------------------------------------------------------
        return redirect(absolute_default_style[key])
    elif "revert" == val: #---------------------------- revert -------------------------------------------------------------------------------
        if attr.isinherited:
            return redirect("inherit")
        else:
            return redirect(get_style(elem.tag)[key])
    ############### length_percentage_keyword helper ####################
    def length_percentage(*kws: Sentinel)->Sentinel|Percentage|Number:
        _kws: dict[str, Sentinel] = {value.name.lower():value for value in kws}
        if (sentinel:=_kws.get(val)) is not None:
            return sentinel
        with suppress(ValueError): # percentage or unit
            num, unit = split_units(val)
            if unit == "%":
                return Percentage(num)
            else:
                return elem.calc_length((num, unit))
        raise ComputeError
    try:
        match key:
            case "font-weight": #----------------------------- font-weight -------------------------------------------------------------------------------
                return elem.calc_fontweight(val)
            case "font-family": #----------------------------- font-family -------------------------------------------------------------------------------
                return val
            case "font-size": #----------------------------- font-size -------------------------------------------------------------------------------
                abs_kws = g["abs_font_size"]
                rel_kws = g["rel_font_size"]
                if val in abs_kws:
                    return g["default_font_size"] * 1.2 ** abs_kws[val]
                elif val in rel_kws:
                    return parent_style[key] * 1.2 ** rel_kws[val]
                else:
                    with suppress(ValueError): # percentage or unit
                        num, unit = split_units(val)
                        if unit == '%':
                            return parent_style[key] * 0.01 * num
                        else:
                            return elem.calc_length((num, unit))
            case "font-style": #----------------------------- font-style -------------------------------------------------------------------------------
                with suppress(ValueError, AssertionError, TypeError):
                    return FontStyle(*val.split()) # the FontStyle __init__ does the most for us by raising an Error if the input is wrong
            case "color": #---------------------------------- color -------------------------------------------------------------------------------
                with suppress(ValueError):
                    return elem.calc_color(val)
            case "display": #----------------------------- display -------------------------------------------------------------------------------
                if val in ("none", "inline", "block"):
                    return val
            case "background-color": #----------------------------- background-color -------------------------------------------------------------------------------
                with suppress(ValueError):
                    return elem.calc_color(val)
            case "width": #----------------------------- width -------------------------------------------------------------------------------
                return length_percentage(Auto)
            case "height": #----------------------------- height -------------------------------------------------------------------------------
                return length_percentage(Auto)
            case "position":
                if val in ("static","rel","abs","fix","sticky"):
                    return val
            case orient if orient in ("left", "right", "top", "bottom"):
                return length_percentage(Auto)
            case "box-sizing":
                if val in ("content-box", "border-box"):
                    return val
            case margin if margin in {f"margin-{k}"for k in css.directions}:
                return length_percentage(Auto)
            case padding if padding in {f"padding-{k}"for k in css.directions}:
                return length_percentage(Auto)
            case border_width if border_width in {f"border-{k}-width" for k in css.directions}:
                abs_kws = g["abs_border_width"]
                if val in abs_kws:
                    return abs_kws[val]
                return length_percentage()
            case "line-height":
                return length_percentage(Normal)
            case "word-spacing":
                return length_percentage(Normal)
    except ComputeError:
        pass
    # unset the value if not returned yet
    return redirect("unset")

########################## Element ########################################
def create_element(elem: _XMLElement, parent: Type["Element"]|None = None):
    """ Create an element """
    tag = get_tag(elem)
    if tag == "html":
        new = HTMLElement(tag, elem.attrib, [])
        new.children = [create_element(e, new) for e in elem]
        if elem.text is not None and elem.text.strip():
            new.children.insert(0, TextElement(elem.text.strip(), new))
        return new
    assert parent is not None
    new = Element(
        get_tag(elem),
        elem.attrib,
        [], # we initialize children later
        parent
    )
    new.children = [create_element(e, new) for e in elem]
    # insert Text Element at the top
    if elem.text is not None and elem.text.strip():
        new.children.insert(0, TextElement(elem.text.strip(), new))
    return new

class Element:
    box: Box = empty_box()
    display: str # the used display state. Is set before layout

    def __init__(
        self, 
        tag: str,
        attrs: dict,
        children: list['Element'],
        parent: 'Element'
    ):
        self._style: style_computed = {}
        self.parent = parent

        # copy stuff
        self.tag: str = tag
        self.attrs = attrs
        self.children = children

        # parse element style and update default
        self.style: style_input = ChainMap(
            css.parse(self.attrs.get("style","")),
            element_styles.get(self.tag,{}),
            absolute_default_style
        )

    def is_block(self)->bool:
        """ 
        Returns whether an element is a block. 
        Includes side effects (as a feature) that automatically adjusts false inline elements to block layout 
        """
        self.display = self._style["display"]
        if self.display != "none":
            any_child_block = any([child.is_block() for child in self.children])
            if any_child_block: # set all children to blocked
                for child in (c for c in self.children if c.display != "none"):
                    child.display = "block"
                self.display = "block"
        return self.display == "block"

    def get_height(self)->Number:
        if self.box.height == -1: # sentinel: height not set yet
            assert self.parent != self, self
            return self.parent.get_height()
        else:
            return self.box.height

    def set_pos(self, pos: Dimension):
        x,y = pos
        self.box.set_x(x)
        self.box.set_y(y)
    
    ##################################    Attribute calculation helpers ##########################
    def calc_color(self, color: str)->Color:
        # TODO: implement more color values
        if color in g["sys_colors"]:
            return g["sys_colors"][color]
        if color == "transparent":
            return Color(0,0,0,0)
        return Color(color)

    def calc_length(self, dimension: tuple[Number, str])->Number:
        """ 
        Gets a dimension (a tuple of a number and any unit)
        and returns a pixel value as a Number
        Raises ValueError or TypeError if something is wrong with the input.

        See: https://developer.mozilla.org/en-US/docs/Web/CSS/length
        """
        num,s = dimension # Raises ValueError if dimension has not exactly 2 entries
        if num == 0: 
            return 0 # we don't even have to look at the unit. Especially because the unit might be the empty string
        if not isinstance(num, Number):
            num = float(dimension[0]) # cast possible strings
        abs_length = g["absolute_length_units"]
        match num,s:
            # source:
            # https://developer.mozilla.org/en-US/docs/Learn/CSS/Building_blocks/Values_and_units
            # absolute values first--------------------------------------
            case x, key if key in abs_length:
                rv = x * abs_length[key]
            # now relative values --------------------------------------
            case x, "em":
                rv = self.parent._style["font-size"]*x
            case x, "rem":
                rv = g["root"]._style["font-size"]*x
            # view-port-relative values --------------------------------------
            case x, "vw":
                rv = x*0.01*g["W"]
            case x, "vh":
                rv = x*0.01*g["H"]
            case x, "vmin":
                rv = x*0.01*min(g["W"], g["H"])
            case x, "vmax":
                rv = x*0.01*max(g["W"], g["H"])
            # TODO: ex, ic, ch, ((lh, rlh, cap)), (vb, vi, sv*, lv*, dv*)
            # See: https://developer.mozilla.org/en-US/docs/Web/CSS/length#relative_length_units_based_on_viewport
            case x,s if isinstance(x, Number) and isinstance(s, str):
                raise ValueError(f"{s} is not an accepted unit")
            case _:
                raise TypeError()
        return rv

    def calc_fontweight(self, fw: str)->Number:
        """ 
        Gets any fontweight value and calculates the computed value or raises an ComputeError
        https://drafts.csswg.org/css-fonts/#relative-weights
        """
        if (val:=g["abs_kws"][fw]) is not None:
            return val
        elif fw == "lighter":
            p_size = self.parent._style["font-size"]
            if p_size < 100:
                return p_size
            elif  p_size < 550:
                return 100
            elif p_size < 700:
                return 400
            elif p_size <= 1000:
                return 700
            else:
                raise ValueError
        elif fw == "bolder":
            p_size = self.parent._style["font-size"]
            if p_size < 350:
                return 400
            elif p_size < 550:
                return 700
            elif p_size < 900:
                return 900
            else:
                return p_size
        else:
            try:
                n = float(fw)
            except ValueError:
                n = -1
            if not 0 < n <= 1000:
                return g["abs_kws"]["normal"]
            return n

    ####################################  Main functions ######################################################
    
    def select_one(self, tag: str)->'Element':
        if self.tag == tag:
            return self
        for c in self.children:
            select = c.select_one(tag)
            if select:
                return select
        return False

    def collide(self, pos: Dimension)->Iterable['Element']:
        """
        The idea of this function is to get which elements were hit for focus, hover and mouse events
        """
        rv: list[Iterable[Element]] = []
        # check which children were hit
        if self.children:
            rv = [c.collide(pos) for c in reversed(self.children)]
        # check if we were hit and add us if so
        if self.rect.collidepoint(pos):
            rv.append([self])
        return chain(*rv)

    def compute(self):
        """
        https://developer.mozilla.org/en-US/docs/Web/CSS/computed_value
        The computed value of a CSS property is the value that is transferred from parent to child during inheritance. 
        It is calculated from the specified value by:

        1. Handling the special values inherit, initial, revert, revert-layer, and unset.
        2. Doing the computation needed to reach the value described in the "Computed value" line in the property's definition table.

        The computation needed to reach a property's computed value typically involves converting relative values 
        (such as those in em units or percentages) to absolute values. 
        For example, if an element has specified values font-size: 16px and padding-top: 2em, then the computed value of padding-top is 32px (double the font size).

        However, for some properties (those where percentages are relative to something that may require layout to determine, 
        such as width, margin-right, text-indent, and top), percentage-specified values turn into percentage-computed values. 
        Additionally, unitless numbers specified on the line-height property become the computed value, as specified. 
        The relative values that remain in the computed value become absolute when the used value is determined.
        """
        parent_style = self.parent._style
        style: style_computed = {}

        for key,val in self.style.items():
            if key not in style:
                style[key] = process_style(self, val, key, parent_style)
                assert style[key] is not None, "Style was set to None. Which should never happen."
        self._style = safe_style(style)
        for child in self.children:
            child.compute()

    def layout(self, width: Number)->None: # !
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
            width,
            self._style,
            self.parent.box.width,
            self.parent.get_height()
        )
        if any(c.display == "block" for c in self.children):
            with self.layout_children() as height:
                set_height(height)
        else: # all children are inline
            # Algorithmic idea
            # convert our children to a list of (text, style) tuples and 
            # lay it out with perfect knowledge about our own width
            # save this list
            # then in the draw function we can use it
            set_height(0)

    @contextmanager
    def layout_children(self)->Number:
        inner: pg.Rect = self.box.content_box
        x_pos = inner.x
        y_cursor = inner.y
        flow = [child for child in self.children if child._style["position"] in ("static", "relative", "sticky")]
        no_flow = [child for child in self.children if child._style["position"] in ("absolute", "fixed")]
        for child in flow:
            child.layout(inner.width)
            # calculate the position
            top, bottom, left, right = inset_getter(self._style)
            inset: tuple[Number, Number] = (0,0) if child._style["position"] == "sticky" else (bottom-top, right-left)
            pos = Vector2(x_pos, y_cursor) + inset
            child.set_pos(pos)
            y_cursor += child.box.outer_box.height
        yield y_cursor
        for child in no_flow:
            child.layout(inner.width)
            # calculate position
            top, bottom, left, right = inset_getter(self._style)
            y: Number = top if top is not Auto else \
                self.get_height() - bottom if bottom is not Auto else 0
            x: Number = left if left is not Auto else \
                inner.width - right if right is not Auto else 0
            child.set_pos((x,y))

    def draw(self, screen: pg.surface.Surface, pos: Dimension):
        draw_box = copy(self.box)
        x_off, y_off = pos
        draw_box.x += x_off
        draw_box.y += y_off
        # Now x and y represent the real position on the canvas (before it was the position in the content_box of the parent)
        style = self._style
        #draw background:
        border_box: pg.Rect = draw_box.border_box
        pg.draw.rect(screen, style["background-color"], border_box)
        for line, width in zip(rect_lines(border_box), draw_box.border):
            pg.draw.line(screen, "black", *line, width = width) # TODO: implement border-color
        # draw children
        for c in self.children:
            if not isinstance(c, TextElement):
                c.draw(screen, draw_box.content_box.topleft)

    ###############################  I/O for Elements  ##################################################################

    @property
    def text(self):
        return " ".join(c.text for c in self.children)

    def to_html(self, indent=0):
        """Convert the element back to formatted html"""
        attrs = [f"{k} = \"{v}\"" for k,v in self.attrs.items()]
        indentation = " "*indent
        body = f"{self.tag} {' '.join(attrs)}".strip()
        if self.children:
            children = f"\n".join(
                c.to_html(indent+2) for c in self.children
            )
            return f"""{indentation}<{body}>
{children}
{indentation}</{self.tag}>"""
        else:
            return f"{indentation}<{body}></{self.tag}>" # self-closing tag

    def __repr__(self):
        return f"<{self.tag}>"

class HTMLElement(Element):
    def __init__(self, tag: str, attrs: dict, children: list[Element], parent: Element = None):
        assert tag == "html"
        super().__init__(
            "html",
            attrs,
            children,
            parent = self
        )
        self._style: style_computed = g["head_comp_style"]
        self.display = "block"
        # self._style: style_computed = {
        #     k:process_style(self, v, k, {})
        #     for k, v in self.style.items()
        # }
        if "lang" in self.attrs:
            g["lang"] = self.attrs["lang"]

    def compute(self):
        # we don't need to compute our style because its already set
        for child in self.children:
            child.compute()
        
    def layout(self):
        self.box = Box(
            t = "content-box",
            width = g["W"], 
            height = g["H"]
        )
        # all children correct their display
        assert self.is_block()
        # the maximum width is g["W"] # we might also add a scrollable window in the future. Then any overflowed element will still be viewable
        with super().layout_children():
            pass

    def draw(self, screen, pos):
        for c in self.children:
            c.draw(screen, pos)

class IMGElement(Element):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # eg fetch the image and save a reference in this element

    def layout(self, width):
        pass

class TextDrawItem(NamedTuple("TextDrawItem", text=str, pos=Dimension)):
    __slots__ = ()

font_split_regex = re.compile(r"\s*\,\s*")

class TextElement:
    """ Special element that can't be accessed from HTML directly but represent any raw text """
    text: str
    parent: Element
    style: style_computed
    font: pg.font.Font
    tag = "Text"
    display = "inline"

    def is_block(self):
        return False

    def set_pos(self, pos):
        pass

    def __init__(self, text: str, parent: Element):
        self.text = text
        self.parent = parent

    def select_one(self, tag:str):
        return False

    def compute(self):
        pass

    def layout(self, width: float)->None:
        style = self.parent.style
        families = font_split_regex.split(style["font-family"]) # this algorithm should be updated
        families = [f.removeprefix('"').removesuffix('"') for f in families]
        font = get_font(
            families, 
            style["font-size"], 
            style["font-style"], 
            style["font-weight"]
        )
        self.font = font
        if word_spacing == "normal":
            word_spacing = font.size(" ")[0] # the width of the space character in the font
        if line_height == "normal":
            line_height = 1.2 * style["font-size"]
        xcursor = ycursor = 0.0
        self.draw_items.clear()
        l = self.text.split()
        for word in l:
            word_width, _ = font.size(word)
            if xcursor + word_width > width: #overflow
                xcursor = 0
                ycursor += line_height
            self.draw_items.append(TextDrawItem(word,(xcursor, ycursor)))
            xcursor += word_width + word_spacing
        # should set a box
        self.x, self.y = xcursor, ycursor

    def draw(self, surface: pg.surface.Surface):
        for item in self.draw_items:
            word, pos = item

    def to_html(self, indent=0):
        return " "*indent+self.text

    def __repr__(self):
        return f"<{self.tag}>"

################################### Rest is commentary in nature #########################################

class InlineElement(Element):
    """ This is the interface of an element with display = "inline" """
