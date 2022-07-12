from collections import defaultdict, ChainMap
from contextlib import suppress
from dataclasses import dataclass
from functools import cache
from numbers import Number
import re
from typing import Any, Iterable, Literal, Sequence
from xml.etree.ElementTree import Element as _XMLElement
# https://stackoverflow.com/questions/54785148/destructuring-dicts-and-objects-in-

import pygame as pg
from util import (
    log_error, make_default, split_units, 
    pad_getter, mrg_getter, bw_getter, rs_getter,
    get_tag
)
from pg_util import Dotted, draw_text
import own_css_parser as css # type: ignore
from config import g
from own_types import ComputeError, Percentage, StyleAttr, FontStyle, style_input, style_computed, Dimension

""" More useful links for further development
https://developer.mozilla.org/en-US/docs/Web/CSS/image
https://developer.mozilla.org/en-US/docs/Web/CSS/CSS_Box_Model/Mastering_margin_collapsing
"""
################################# Globals ###################################


################################## Style Data ################################
# To add a new style key, document it, add it here and then implement it in the draw or layout methods
# Idea: Move this to config.g
style_keys = {
    "font-weight": StyleAttr("normal"),
    "font-family":StyleAttr("Arial"),
    "font-size":StyleAttr("medium"), 
    "font-style":StyleAttr("normal"),
    "line-height":StyleAttr("normal"),
    "color":StyleAttr("canvastext"), 
    "display":StyleAttr("inline"),
    "background-color": StyleAttr("transparent"),
    "width":StyleAttr("auto", inherited = False),
    "height":StyleAttr("auto", inherited = False),
    "position": StyleAttr("static", inherited = False),
    "top": StyleAttr("0", inherited = False),
    "bottom": StyleAttr("0", inherited = False),
    "left": StyleAttr("0", inherited = False),
    "right": StyleAttr("0", inherited = False),
    "box-sizing": StyleAttr("content-box", inherited = False),
    **dict.fromkeys(g["margin-keys"], StyleAttr("0", False)),
    **dict.fromkeys(g["padding-keys"], StyleAttr("0", False)),
    **dict.fromkeys(g["border-width-keys"], StyleAttr("medium", False)),
    "line-height": StyleAttr("normal", False),
    "word-spacing": StyleAttr("normal", False),
}

""" The default style for a value, when nothing is set (just like "unset") """
absolute_default_style = {
    **{k:"inherit" if v.inherited else v.initial for k,v in style_keys.items()},
}

element_styles: dict[str, dict[str, Any]] = defaultdict(dict,{
    "html": {
        "display": "none"
    },
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
def get_style(tag: str)->dict:
    return absolute_default_style | element_styles[tag]

def create_element(elem: _XMLElement, parent: "Element"):
    """ Create an element """
    tag = get_tag(elem)
    if tag == "html":
        return HTMLElement(elem)
    assert isinstance(parent, Element) # only the HTML element can have no valid parent
    new = Element(
        get_tag(elem),
        elem.attrib,
        [], # we initialize children here
        parent
    )
    new.children = [create_element(e, new) for e in elem]
    # insert Text Element at the top
    if elem.text is not None and elem.text.strip():
        new.children.insert(0, TextElement(elem.text.strip(), new))
    return new


class Element:
    x: Number # after layout its set to the location of the element in its parent, in draw its then the actual position of the element on the surface
    y: Number # dito
    width: Number|None # width of the element
    _height: Number|None # the private height of the element
    display: str|None # the used display state. Is set before layout

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
            element_styles.get(self.tag,{})
        )

    def is_block(self):
        """ 
        Returns whether an element is a block. 
        Includes side effects (as a feature) that automatically adjusts false inline elements to block layout 
        """
        if not self._style["display"] == "none":
            children = [c for c in self.children if c._style["display"] != "none"]
            any_child_block = any(child.is_block() for child in children)
            if any_child_block: # set all children to blocked
                for child in children:
                    child.display = "block"
                self._style["display"] = "block"
        self.display = self._style["display"] # true if we are block and all children are inline or if any child is block
        return self.display == "block"

    """
    Attribute calculation helpers
    """
    def calc_color(self, color: str)->pg.Color:
        #TODO: implement more color values
        if color in g["sys_colors"]:
            return g["sys_colors"][color]
        if color == "transparent":
            return pg.Color(0,0,0,0)
        return pg.Color(color) # standard colors like "blue", "green", "white" or "black" are all supported

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
        if not isinstance(x, Number):
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

    def calc_fontweight(self, fontsize: str)->Number:
        """ 
        Gets any fontweight value and calculates the computed value
        https://drafts.csswg.org/css-fonts/#relative-weights
        """
        abs_kws = {
            "normal": 400,
            "bold": 700,
        }
        fs = fontsize.casefold()
        if (val:=abs_kws[fs]) is not None:
            return val
        elif fs == "lighter":
            p_size = self.parent._style["font-size"]
            if p_size < 100:
                return p_size
            elif  p_size < 550:
                return 100
            elif p_size <= 1000:
                return 700
            else:
                raise ValueError
        elif fs == "bolder":
            p_size = self.parent._style["font-size"]
            if p_size < 350:
                return 400
            elif p_size < 550:
                return 700
            elif p_size < 900: # TODO: Check specifications for >= 900
                return p_size
        else:
            try:
                n = float(fs)
            except ValueError:
                n = -1
            if not 0 < n <= 1000:
                # TODO: error logging
                return abs_kws["normal"]
            return n

    """
    Main functions: collide, compute, layout, draw
    """
    def collide(self, pos: Dimension):
        """
        The idea of this function is to get which elements were hit for focus, hover and mouse events
        """
        # the list of elements that were hit
        rv: list[Element] = []
        # check which children were hit
        if self.children:
            ccollisions: list[list[Element]] = [collide for c in reversed(self.children) if (collide:=c.collide(pos))]
            if ccollisions:
                for cc in ccollisions:
                    rv += cc
        # check if we were hit and add us if so
        if self.rect.collidepoint(pos):
            rv.append(self)
        return rv

    def process_style(self, val: str, key: str, parent_style: style_computed)->Number|Percentage|str :
        def redirect(new_val):
            return self.process_style(val=new_val, key = key, parent_style = parent_style)
        attr = style_keys[key]
        ######################################## global style attributes ####################################################
        # Best and most concise explanation I could find: https://css-tricks.com/inherit-initial-unset-revert/ (probably the same at mdn)
        if "inherit" == val: #----------------------------- inherit ----------------------------------------------------
            return parent_style[key]
        elif "initial" == val: #----------------------------- initial ---------------------------------------------------------------------------------
            return redirect(attr.initial)
        elif "unset" == val: #----------------------------- unset ---------------------------------------------------------------------------------
            return redirect(absolute_default_style[key])
        elif "revert" == val: #----------------------------- revert -------------------------------------------------------------------------------
            if attr.inherited:
                return redirect("initial")
            else:
                return redirect(get_style(self.tag)[key])
        def length_percentage(*kws):
            if val in kws:
                return val
            with suppress(ValueError): # percentage or unit
                num, unit = split_units(val)
                if unit == "%":
                    return Percentage(num)
                else:
                    return self.calc_length((num, unit))
            raise ComputeError
        try:
            match key:
                case "font-weight": #----------------------------- font-weight -------------------------------------------------------------------------------
                    return self.calc_fontweight(val)
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
                                return self.calc_length((num, unit))
                case "font-style": #----------------------------- font-style -------------------------------------------------------------------------------
                    with suppress(ValueError, AssertionError, TypeError):
                        return FontStyle(*val.split()) # the FontStyle __init__ does the most for us by raising an Error if the input is wrong
                case "color": #---------------------------------- color -------------------------------------------------------------------------------
                    with suppress(ValueError):
                        return self.calc_color(val)
                case "display": #----------------------------- display -------------------------------------------------------------------------------
                    if val in ("none", "inline", "block"):
                        return val
                case "background-color": #----------------------------- background-color -------------------------------------------------------------------------------
                    with suppress(ValueError):
                        return self.calc_color(val)
                case "width": #----------------------------- width -------------------------------------------------------------------------------
                    return length_percentage("auto")
                case "height": #----------------------------- height -------------------------------------------------------------------------------
                    return length_percentage("auto")
                case "position":
                    if val in ("static","rel","abs","fix","sticky"):
                        return val
                case orient if orient in ("left", "right", "top", "bottom"):
                    return length_percentage("auto")
                case "box-sizing":
                    if val in ("content-box", "border-box"):
                        return val
                case margin if margin in {f"margin-{k}"for k in css.directions}:
                    return length_percentage("auto")
                case padding if padding in {f"padding-{k}"for k in css.directions}:
                    return length_percentage("auto")
                case border_width if border_width in {f"border-{k}-width" for k in css.directions}:
                    abs_kws = g["abs_border_width"]
                    if val in abs_kws:
                        return abs_kws[val]
                    return length_percentage("auto")
                case "line-height":
                    return length_percentage("normal")
                case "word-spacing":
                    return length_percentage("normal")
            raise ComputeError
        except ComputeError:
            # unset the value
            try:
                return redirect("unset")
            except RecursionError:
                print(key, val, attr)
                return 0

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
        # First reset used values to 0 or None!!!
        self.x = self.y = 0
        self.width = self.height = None
        self.display = None # we do this so that if we use display, an error is raised
        parent_style = self.parent._style
        style: style_computed = {}

        for key in self.style.keys() & style_keys: # all implemented style attributes in this style
            val = self.style[key]
            if key not in style:
                style[key] = self.process_style(val, key, parent_style)
                assert style[key] is not None,"Style was set to None. Which should never happen."
        self._style.update(style)
        for child in self.children:
            child.compute()

    @property
    def height(self)->Number:
        if self._height is not None:
            return self._height
        else:
            return self.parent.height

    @height.setter
    def _(self, other):
        self._height = other

    def layout(self, width: Number)->Number:
        """
        Gets the width it has available

        Layouts the childrens elements and sets used values for before not fully resolved style-attributes
        Side effects include:
        - Sets childrens x and y
        - sets own width (used width)
        - sets own height (used height)
        The input width is the width the child should take if its width is "auto"

        Returns the used height
        """
        # inside of here we can assume that display, x and y are set
        def calc_dim(
            value: str|Number|Percentage, 
            auto_val: Number|None = None, 
            perc_val = "width"
        ):
            if isinstance(perc_val, str):
                perc_val = make_default(perc_val, getattr(self.parent, perc_val))
            if value == "auto":
                if auto_val is None:
                    raise ValueError("This attribute cannot be 'auto'")
                return auto_val
            # TODO: if style["box-model"] == "border-box" then these values have to be converted to margin-box
            elif isinstance(value, Number):
                return value
            elif isinstance(value, Percentage):
                return perc_val * value

        def merge_horizontal_margin(mrg_h: tuple[str|Number|Percentage, str|Number|Percentage], avail: Number)->Dimension:
            match mrg_h:
                case ("auto", "auto"):
                    return (avail/2,)*2
                case ("auto", x):
                    x = calc_dim(x, Exception)
                    return ((avail-x),x)
                case (x, "auto"):
                    x = calc_dim(x, Exception)
                    return (x, (avail-x))
                case (x,y):
                    x = calc_dim(x, Exception)
                    y = calc_dim(y, Exception)
                    return x,y
            raise RuntimeError(f"Invalid margin found {mrg_h}")

        assert self.display is not None
        if self.display == "none":
            return 0
        style = self._style

        # basically there are three possibilities:
        # 1. we are a block ourselves and every child is a block too
        # 2. we are a block ourselves and every child is inline
        # 3. we are inline and every child is inline too
        
        # 1. block containing blocks
        if any(c.display == "block" for c in self.children):
            # load padding, border and margin
            self.width = calc_dim(style["width"],width)
            pad_t, pad_b, pad_r, pad_l = *(calc_dim(val, 0) for val in pad_getter(style)),
            bw_t, bw_b, bw_r, bw_l = *(calc_dim(val) for val in bw_getter(style)),
            mrgs = mrg_getter(style)
            mrg_t, mrg_b = *(calc_dim(val, 0) for val in mrgs[:2]), # vertical margins
            mrg_l, mrg_r = merge_horizontal_margin(mrgs[2:]) # horizontal margins
            y_cursor = mrg_t + bw_t + pad_t # the starting y cursor is obviously after margin, border and padding
            x_pos = mrg_l + bw_l + pad_l # and the same is for the x_pos
            inner_width = self.width - mrg_l - mrg_r - bw_r - bw_l - pad_r - pad_l
            for child in self.children:
                child.x, child.y = x_pos, y_cursor
                ycursor += child.layout(inner_width)
            self.height = calc_dim(
                self.style["height"], 
                ycursor + pad_b + bw_b + mrg_b,
                "height"
            )
            return self.height
        else: # all children are inline
            # convert our children to a list of (text, style) tuples and 
            # lay it out with perfect knowledge about our own width
            # save this list
            # then in the draw function we can use it
            pass

    def draw(self, screen: pg.surface.Surface, pos: Dimension):
        x_off, y_off = pos
        self.x += x_off
        self.y += y_off
        # Now x and y represent the real position on the canvas
        style = self._style
        #draw background:
        pg.draw.rect(screen, style["background-color"], self.rect)
        # TODO: draw border
        # draw children
        for c in self.children:
            c.draw(screen, (self.x, self.y))

    """
    I/O for Elements
    """
    def show_box_model(self, size)->pg.surface.Surface:
        # TODO: actually finish this
        size = pg.Vector2(size)
        totw, toth = size
        surf = pg.Surface(size)
        # margin
        rect = pg.rect.Rect(0,0,*size)
        pg.draw.rect(
            surf,
            "lightyellow",
            rect
        )
        Dotted.from_rect(
            rect, color = "lightgrey"
        ).draw_rect(surf)
        # margin_nums
        rect = pg.rect.Rect(0,0,*size*0.8)
        rect.center = size/2
        for point, margin in zip(rs_getter(rect), mrg_getter(self._style)):
            draw_text(
                surf, str(margin), "MonoLisa",
                12, "grey", center = point
            )
        
    @property
    def text(self):
        return " ".join(c.text for c in self.children)

    def to_html(self, indent=0):
        """Convert the element back to html"""
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
            return f"{indentation}<{body}\>" # self-closing tag

    def __repr__(self):
        return f"<{self.tag}>"

class HTMLElement(Element):
    width: Number = g["W"]
    _height: Number = g["H"]
    def __init__(self, elem: _XMLElement):
        super().__init__(elem, parent = self)
        self._style = g["head_comp_style"]
        if "lang" in self.attrs:
            g["lang"] = self.attrs["lang"]

    def compute(self):
        for child in self.children:
            child.compute()
        
    def layout(self):
        self.x = 0
        self.y = 0
        self.display = "block"
        self.is_block() # here this means all children wil now know their display
        super().layout(g["W"])
        self.height = max(g["H"], self.height)

class IMGElement(Element):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # eg fetch the image and save a reference in this element

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

@dataclass
class TextDrawItem:
    text: str
    pos: Dimension

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
        # return self.display == "block"
        # The above is more True, but it doesn't really matter anyway, because we will only be a block after our parent already knows that we are a block
        return False

    def __init__(self, text: str, parent: Element):
        self.text = text
        self.parent = parent

    def compute(self):
        pass

    def layout(self, width: float)->Dimension:
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
        return xcursor, ycursor

    def draw(self, surface: pg.surface.Surface):
        style = self.parent._style

    def to_html(self, indent=0):
        return " "*indent+self.text

    def __repr__(self):
        return f"<{self.tag}>"


"""
Rest is commentary in nature
"""

class InlineElement(Element):
    """ This is the interface of an element with display = "inline" """
