# Style computing is not thread safe and doesn't need to be. Maybe add a global lock?
# fmt: off
import abc
import math
import re
from abc import ABC
from collections import defaultdict, deque
from contextlib import contextmanager, suppress
from dataclasses import dataclass
from functools import cache, partial
from itertools import chain, islice
from operator import itemgetter, add, sub, mul, truediv
from typing import (Any, Callable, Generic, Iterable, Literal, Mapping, Protocol, Type, TypeVar, Union,
                    overload)

import tinycss

from config import (abs_border_width, abs_font_size, abs_font_weight,
                    abs_length_units, g, rel_font_size, rel_length_units)
import Media
from own_types import (CO_T, V_T, Auto, AutoLP, AutoLP4Tuple, AutoType, BugError, Color, Drawable, Float4Tuple,
                       FontStyle, Length, LengthPerc,
                       Number, Percentage, Sentinel, Str4Tuple, StrSent,
                       frozendict, CompStr)
from util import (GeneralParser, dec_re, fetch_txt, find, find_index, get_groups, group_by_bool, log_error, make_default,
                  noop, print_once, re_join, tup_replace)
# fmt: on

# Typing

CompValue = Any  # | float | Percentage | Sentinel | FontStyle | Color | tuple[Drawable, ...] | CompStr but not a normal str

# A Value is the actual value together with whether the value is set as important
# A Property corresponds to a css-property with a name and a value
InputValue = tuple[str, bool]
InputProperty = tuple[str, InputValue]
InputStyle = list[InputProperty]
Value = tuple[str | CompValue, bool]
Property = tuple[str, Value]
ResolvedStyle = dict[str, str | CompValue]
Style = dict[str, Value]
FullyComputedStyle = Mapping[str, CompValue]
StyleRule = tuple[str, Style]
"""
A Style with a Selector (as a String)
Example:
p {
    color: red !important;
} -> ('p', {'color': ('red', 'True')})
"""

MediaValue = tuple[int, int]  # just the window size right now
Rule = Union["AtRule", "StyleRule"]

CompValue_T = TypeVar("CompValue_T", bound=CompValue, covariant=True)


def is_real_str(x):
    """
    Returns whether x is a real str and not computed
    """
    return isinstance(x, str) and not isinstance(x, CompStr)


def ensure_comp(x: CompValue_T | str) -> CompValue_T | CompStr:
    return CompStr(x) if isinstance(x, str) else x


def match_bracket(s: Iterable):
    """
    Searchs for a matching bracket
    If not found then returns None else it returns the index of the matching bracket
    """
    brackets = 0
    for i, c in enumerate(s):
        if c == ")":  # closing bracket
            if not brackets:
                return i
            else:
                brackets -= 1
        elif c == "(":  # opening bracket
            brackets += 1


def split_value(s: str) -> list[str]:
    rec = True
    result = []
    curr_string = ""
    brackets = 0
    for c in s:
        is_w = re.match(r"\s", c)
        if rec and not brackets and is_w:
            rec = False
            result.append(curr_string)
            curr_string = ""
        if not is_w:
            rec = True
            curr_string += c
        elif brackets:
            curr_string += c
        if c == "(":
            brackets += 1
        elif c == ")":
            assert brackets
            brackets -= 1
    if rec:
        result.append(curr_string)
    return result


#################### Itemgetters/setters ###########################

# https://stackoverflow.com/questions/54785148/destructuring-dicts-and-objects-in-python
class T4Getter(Protocol[CO_T]):
    def __call__(self, input: FullyComputedStyle) -> tuple[CO_T, CO_T, CO_T, CO_T]:
        ...


class itemsetter(Generic[V_T]):
    def __init__(self, keys: tuple[str, ...]):
        self.keys = keys

    def __call__(self, map: dict, values: tuple[V_T, ...]) -> None:
        for key, value in zip(self.keys, values):
            map[key] = value


directions = ("top", "right", "bottom", "left")
corners = ("top-left", "top-right", "bottom-right", "bottom-left")

# fmt: off
inset_keys = directions
marg_keys: Str4Tuple = tuple(f"margin-{k}" for k in directions)     # type: ignore[assignment]
pad_keys: Str4Tuple = tuple(f"padding-{k}" for k in directions)     # type: ignore[assignment]
bs_keys: Str4Tuple = tuple(f"border-{k}-style" for k in directions) # type: ignore[assignment]
bw_keys: Str4Tuple = tuple(f"border-{k}-width" for k in directions) # type: ignore[assignment]
bc_keys: Str4Tuple = tuple(f"border-{k}-color" for k in directions) # type: ignore[assignment]
br_keys: Str4Tuple = tuple(f"border-{k}-radius" for k in corners)   # type: ignore[assignment]

ALPGetter = T4Getter[AutoLP]
inset_getter: ALPGetter = itemgetter(*inset_keys)   # type: ignore[assignment]
mrg_getter: ALPGetter = itemgetter(*marg_keys)      # type: ignore[assignment]
pad_getter: ALPGetter = itemgetter(*pad_keys)       # type: ignore[assignment]

bw_getter: T4Getter[int] = itemgetter(*bw_keys)     # type: ignore[assignment]
bc_getter: T4Getter[Color] = itemgetter(*bc_keys)   # type: ignore[assignment]
bs_getter: T4Getter[str] = itemgetter(*bs_keys)     # type: ignore[assignment]
br_getter: T4Getter[tuple[LengthPerc, LengthPerc]] = itemgetter(*br_keys)  # type: ignore[assignment]
# fmt: on
####################################################################


################## Acceptors #################################


class Acceptor(Protocol[CompValue_T]):
    """
    An Acceptor is a Callable that takes a value as a str and a FullyComputedStyle and returns a ComputedValue
    If the Acceptor returns None then the value is invalid
    If the Acceptor raises a KeyError then the value might be valid
    but depends on a value in p_style that doesn't exist
    """

    def __call__(self, value: str, p_style: FullyComputedStyle) -> None | CompValue_T:
        ...


def css_func(value: str, name: str):
    if value.startswith(name + "(") and value.endswith(")"):
        return re.split(r"\s*,\s*", value[len(name) + 1 : -1])


def remove_quotes(value: str):
    for quote in ("'", '"'):
        if value.startswith(quote) and value.endswith(quote):
            return value[1:-1]
    return value


CalcTypes = Percentage, Length, Number
CalcType = Union[Type[Length], Type[Percentage], Type[float]]
no_type_types = frozenset({Percentage,*Number})
CalcValue = Percentage | Length | float  # TODO: add Angle and more
CalcValue_T = TypeVar("CalcValue_T", bound=CalcValue)
Operator = Callable[[CalcValue, CalcValue], CalcValue]


@dataclass
class BinOp(abc.ABC):
    left: CalcValue
    op: Operator
    right: CalcValue

    def resolve(self) -> "_ParseResult":
        try:
            return self.op(self.left, self.right)
        except ValueError:
            return self

    def get_type(self) -> str:
        pass


@dataclass
class AddOp(BinOp):
    left: CalcValue
    op: Operator
    right: CalcValue

    def get_type(self):
        return (
            ltype
            if (ltype := get_type(self.left)) is not Percentage
            else get_type(self.right)
        )


@dataclass
class MulOp(BinOp):
    left: CalcValue
    op: Operator
    right: CalcValue

    def get_type(self):
        return (
            ltype
            if (ltype := get_type(self.left)) is not Number
            else get_type(self.right)
        )


_ParseResult = CalcValue | BinOp
_ParseResult_T = TypeVar("_ParseResult_T", bound=_ParseResult)


def get_type(x: _ParseResult) -> CalcType:
    """
    Returns Number, Percentage or Length
    """
    if isinstance(x, (MulOp, AddOp)):
        return x.get_type()
    for type_ in CalcTypes:
        if isinstance(x, type_):  # type: ignore
            return type_  # type: ignore
    raise BugError(f"Cannot determine type of {x}")


# https://regexr.com/3ag5b
hex_re = re.compile(r"#([\da-f]{1,2})([\da-f]{1,2})([\da-f]{1,2})")
number_pattern = re.compile(dec_re)
units_map: dict[str, CalcType] = {
    "%": Percentage,
    **{k: Length for k in chain(abs_length_units, rel_length_units)},
}
unit_re = re_join(*units_map)
units_pattern = re.compile(unit_re)
dim_pattern = re.compile(rf"({dec_re})({unit_re})")
# operators
_is_high = lambda x: x in ("*", "/")
_is_low = lambda x: x in ("+", "-")
op_map: dict[str, Operator] = {
    "+": add,
    "-": sub,
    "*": mul,
    "/": truediv,
}
op_re = re.compile(re_join(*op_map))
# calc literals
literal_map = {
    "pi": math.pi,
    "e": math.e,
    # I don't understand why you would need these. Like, you're not gonna make an element with a font-size of NaN or -infinity
    "infinity": float("inf"),
    "-infinity": float("-inf"),
    "NaN": float("nan"),
}
literal_re = re.compile(re_join(*literal_map))


class Calc(Acceptor[CalcValue | BinOp], GeneralParser):
    _accepts: frozenset[CalcType]
    default_type: CalcType|None
    def __init__(self, *types):
        self._accepts = frozenset(types)
        try:
            self.default_type = next(iter(self._accepts.difference(no_type_types)))
        except StopIteration:
            self.default_type = None

    def accepts_type(self, x):
        return x in self._accepts

    def acc(self, value: str, p_style):
        try:
            number, unit = split_units(value)
        except ValueError:
            return None
        if not unit and self.default_type is not None:
            _type = self.default_type
        else:
            _type = units_map[unit]
            if not self.accepts_type(_type):
                return None
        if _type in no_type_types:
            return _type(number)
        elif _type is Length:
            return _length((number, unit), p_style)

    def __call__(self, value: str, p_style: FullyComputedStyle):
        acc = partial(self.acc, p_style=p_style)
        if args := css_func(value, "calc"):
            # lexer
            self.x = args[0]
            stack = deque[str | CalcValue_T | float | BinOp]()
            while self.x:
                start_x = self.x
                if self.consume("(") or self.consume("calc("):
                    stack.append("(")
                elif self.consume(")"):
                    stack.append(")")
                elif dimension := self.consume(dim_pattern):
                    if (result := acc(dimension)) is not None:
                        stack.append(result)
                    else:
                        return None
                # operator has priority over dimension if the last value was a dimension
                if operator := self.consume(op_re):
                    stack.append(operator)
                elif literal := self.consume(literal_re):
                    stack.append(literal_map[literal])
                elif number := self.consume(number_pattern):
                    stack.append(float(number))
                elif self.consume(re.compile(r"\s+")):
                    pass
                elif start_x == self.x:
                    return None  # found no valid character
            try:
                if self.accepts_type(
                    get_type(rv := self.parse(stack)) # type: ignore
                ):  # run-time type checking
                    return rv
            except (ValueError, IndexError, ZeroDivisionError):
                return None
        else:
            return acc(value)

    def parse(self, d: Iterable[str | _ParseResult_T]) -> _ParseResult_T:
        """
        Parses the tokens
        Raises ValueError, IndexError or ZeroDivisionError on failure
        """
        # parser
        t: tuple[str | _ParseResult_T, ...] = tuple(d)
        while "(" in t or ")" in t:
            start_i = t.index("(")
            end_i = match_bracket(islice(iter(t), start_i + 1, None)) + start_i + 1
            t = tup_replace(t, (start_i, end_i + 1), self.parse(t[start_i + 1 : end_i]))
        while (op_i := find_index(t, _is_high)) is not None:
            slice_ = op_i - 1, op_i + 2
            l_val, op, r_val = t[slice(*slice_)]
            if (
                not isinstance(op, str)
                or isinstance(l_val, str)
                or isinstance(r_val, str)
            ):
                raise ValueError
            t = tup_replace(
                t, slice_, MulOp(left=l_val, op=op_map[op], right=r_val).resolve()  # type: ignore
            )
        while (op_i := find_index(t, _is_low)) is not None:
            slice_ = op_i - 1, op_i + 2
            l_val, op, r_val = t[slice(*slice_)]
            if (
                not isinstance(op, str)
                or isinstance(l_val, str)
                or isinstance(r_val, str)
            ):
                raise ValueError
            l_type, r_type = type(l_val), type(r_val)
            if not l_type is r_type and not (
                l_type is Percentage or r_type is Percentage
            ):
                raise ValueError
            t = tup_replace(
                t, slice_, AddOp(left=l_val, op=op_map[op], right=r_val).resolve()  # type: ignore
            )
        assert len(t) == 1 and not isinstance(t[0], str), BugError(
            f"calc_parsing failed, {d}->{t}"
        )
        return t[0]


def split_units(attr: str) -> tuple[float, str]:
    """Split a dimension or percentage into a tuple of number and the "unit" """
    if attr == "0":
        return (0, "")
    match = dim_pattern.fullmatch(attr.strip())
    num, unit = match.groups()  # type: ignore # Raises AttributeError
    return float(num), unit


def no_change(value: str, p_style) -> str:
    return value


def background_image(value: str, p_style) -> tuple[Drawable, ...]:
    # TODO: element, gradients, and more
    arr = split_value(value)
    result: list[Drawable] = []
    for v in arr:
        if args := css_func(v, "url"):
            result.append(Media.Image([remove_quotes(args[0])]))
        else:
            log_error("background-image only supports urls right now", v)
    return tuple(result)


def color(value: str, p_style):
    if value == "currentcolor":
        return p_style["color"]
    with suppress(ValueError):
        if args := css_func(value, "rgb"):
            r, g, b = map(float, args)
            return Color(*map(round, (r, g, b)))
        elif args := css_func(value, "rgba"):
            r, g, b, a = map(float, args)
            return Color(*map(round, (r, g, b, a * 255)))
        elif groups := get_groups(value.lower(), hex_re):
            return Color(*map(lambda x: int(x * (2 // len(x)), 16), groups))
        return Color(value)


def number(value: str, p_style):
    if not re.match(dec_re, value):  # Just to avoid non decimal input
        return None
    with suppress(ValueError):
        return float(value)


def font_size(value: str, p_style):
    if value in abs_font_size:
        return g["default_font_size"] * 1.2 ** abs_font_size[value]
    p_size: float = p_style["font-size"]
    if value in rel_font_size:
        return p_size * 1.2 ** rel_font_size[value]
    else:
        return length_percentage(value, p_style, p_size)


def font_weight(value: str, p_style):
    # https://drafts.csswg.org/css-fonts/#relative-weights
    p_size: float = p_style["font-weight"]
    if value == "lighter":
        if p_size < 100:
            return p_size
        elif p_size < 550:
            return 100
        elif p_size < 700:
            return 400
        elif p_size <= 1000:
            return 700
        else:
            raise ValueError
    elif value == "bolder":
        if p_size < 350:
            return 400
        elif p_size < 550:
            return 700
        elif p_size < 900:
            return 900
        else:
            return p_size
    else:
        with suppress(ValueError):
            n = float(value)
            if 0 < n <= 1000:
                return n


def font_style(value: str, p_style):
    # FontStyle does the most for us
    split = value.split()[:2]
    with suppress(AssertionError):
        return FontStyle(*split)  # type: ignore


def _length(dimension: tuple[float, str], p_style):
    """
    Gets a dimension (a tuple of a number and any unit)
    and returns a pixel value as a Number
    Raises ValueError or TypeError if something is wrong with the input.

    See: https://developer.mozilla.org/en-US/docs/Web/CSS/length
    """
    num, s = dimension  # Raises ValueError if dimension has not exactly 2 entries
    if num == 0:
        return Length(
            0
        )  # we don't even have to look at the unit. Especially because the unit might be the empty string
    abs_length: dict[str, float] = abs_length_units
    w: int = g["W"]
    h: int = g["H"]
    rv: float
    match num, s:
        # source:
        # https://developer.mozilla.org/en-US/docs/Learn/CSS/Building_blocks/Values_and_units
        # absolute values first--------------------------------------
        case x, key if key in abs_length:
            rv = abs_length[key] * x
        # now relative values --------------------------------------
        case x, "em":
            rv = p_style["font-size"] * x
        case x, "rem":
            rv = g["root"]._style["font-size"] * x
        # view-port-relative values --------------------------------------
        case x, "vw":
            rv = x * 0.01 * w
        case x, "vh":
            rv = x * 0.01 * h
        case x, "vmin":
            rv = x * 0.01 * min(w, h)
        case x, "vmax":
            rv = x * 0.01 * max(w, h)
        # TODO: ex, ic, ch, ((lh, rlh, cap)), (vb, vi, sv*, lv*, dv*)
        # See: https://developer.mozilla.org/en-US/docs/Web/CSS/length#relative_length_units_based_on_viewport
        case x, s if isinstance(x, Number) and isinstance(s, str):
            raise ValueError(f"'{s}' is not an accepted unit")
        case _:
            raise TypeError()
    return Length(rv)


def length(value: str, p_style):
    with suppress(AttributeError):
        return _length(split_units(value), p_style)


def length_percentage(value: str, p_style, mult: float | None = None):
    with suppress(AttributeError):
        num, unit = split_units(value)
        if (
            unit == "%"
        ):  # this resolves the Percentage automatically if it can already be resolved
            return Percentage(num) if mult is None else Length(mult * num * 0.01)
        else:
            return _length((num, unit), p_style)


def border_radius(value: str, p_style):
    arr = value.split()
    if (_len := len(arr)) > 2:
        return
    lpx, lpy = map(lambda x: length_percentage(x, p_style), arr * (2 // _len))
    if lpx is not None and lpy is not None:
        return (lpx, lpy)


T1 = TypeVar("T1", bound=CompValue)
T2 = TypeVar("T2", bound=CompValue)


def combine_accs(acc1: Acceptor[T1], acc2: Acceptor[T2]) -> Acceptor[T1 | T2]:
    def inner(value: str, p_style):
        result1 = acc1(value, p_style)
        return result1 if result1 is not None else acc2(value, p_style)

    return inner


################################## Style Data ################################
# To add a new style key, document it, add it here and then implement it in the draw or layout methods


@dataclass
class StyleAttr(Generic[CompValue_T]):
    initial: str
    kws: Mapping[str, Sentinel | CompStr | CompValue_T]
    acc: Acceptor[CompValue_T]
    inherits: bool

    def __init__(
        self,
        initial: str,
        kws: set[StrSent] | Mapping[str, CompValue_T] = {},
        acc: Acceptor[CompValue_T] = noop,
        inherits: bool = None,
    ):
        """
        If the kws are a set then they are automatically converted into a dict
        Inherits as specified or if the acceptor is length_percentage
        """
        self.initial = initial
        self.kws = self.set2dict(kws) if isinstance(kws, set) else kws
        self.acc = acc
        inherits = acc is not length_percentage if inherits is None else inherits
        self.inherits = (
            inherits if inherits is not None else acc is not length_percentage
        )

    def set2dict(
        self, s: set[StrSent]
    ) -> Mapping[str, CompValue_T | Sentinel | CompStr]:
        return {x if isinstance(x, str) else x.value: ensure_comp(x) for x in s}

    def accept(
        self, value: str, p_style: FullyComputedStyle
    ) -> CompValue_T | CompStr | Sentinel | None:
        # insert all vars
        value = re.sub(r"var\(([-\d]*)\)", lambda match: p_style[match.group(1)], value)
        return (
            kw if (kw := self.kws.get(value)) is not None else self.acc(value, p_style)
        )


####### Helpers ########

# we don't want copies of these (memory) + better readibility
auto: dict[str, AutoType] = {"auto": Auto}
normal: dict[str, AutoType] = {"normal": Auto}  # normal is internally mapped to Auto

AALP = StyleAttr(
    "auto",
    auto,
    Calc(Length, Percentage),
)

BorderWidthAttr: StyleAttr[int] = StyleAttr(
    "medium",
    abs_border_width,
    lambda value, p_style: int(x)
    if (x := length_percentage(value, p_style)) is not None
    else None,
    inherits=False,
)
BorderStyleAttr: StyleAttr[str] = StyleAttr(
    "none",
    {
        "none",  # implemented
        "hidden",  # partially implemented
        "dotted",
        "dashed",
        "solid",  # implemented
        "double",
        "groove",
        "ridge",
        "inset",
        "outset",
    },
    inherits=False,
)
BorderColorAttr: StyleAttr[Color] = StyleAttr("currentcolor", acc=color, inherits=False)
BorderRadiusAttr: StyleAttr[LengthPerc] = StyleAttr(
    "0", acc=border_radius, inherits=False
)


prio_keys = {"color", "font-size"}  # currentcolor and 1em for example


style_attrs: dict[str, StyleAttr[CompValue]] = {
    "color": StyleAttr("canvastext", acc=color),
    "font-weight": StyleAttr("normal", abs_font_weight, font_weight),
    "font-family": StyleAttr("Arial", acc=no_change),
    "font-size": StyleAttr("medium", acc=font_size),
    "font-style": StyleAttr("normal", acc=font_style),
    "line-height": StyleAttr(
        "normal", normal, combine_accs(number, length_percentage), True
    ),
    "word-spacing": StyleAttr("normal", normal, length_percentage, True),
    "display": StyleAttr("inline", {"inline", "block", "none"}),
    "background-color": StyleAttr("transparent", acc=color),
    "background-image": StyleAttr("none", {"none": tuple()}, background_image, False),
    "width": AALP,
    "height": AALP,
    "position": StyleAttr(
        "static", {"static", "relative", "absolute", "sticky", "fixed"}
    ),
    "box-sizing": StyleAttr("content-box", {"content-box", "border-box"}),
    **{key: AALP for key in chain(inset_keys, pad_keys, marg_keys)},
    **{key: BorderWidthAttr for key in bw_keys},
    **{key: BorderStyleAttr for key in bs_keys},
    **{key: BorderColorAttr for key in bc_keys},
    **{key: BorderRadiusAttr for key in br_keys},
    "outline-width": BorderWidthAttr,
    "outline-style": BorderStyleAttr,
    "outline-color": BorderColorAttr,
    "outline-offset": StyleAttr("0", acc=length, inherits=False),
}

abs_default_style: dict[str, str] = {
    k: "inherit" if v.inherits else v.initial for k, v in style_attrs.items()
}
""" The default style for a value (just like "unset") """

element_styles: dict[str, dict[str, str]] = defaultdict(
    dict,
    {
        "html": {
            **{k: attr.initial for k, attr in style_attrs.items() if attr.inherits},
            "display": "block",
        },
        # special elements
        "head": {
            "display": "none",
        },
        "span": {"display": "inline"},
        "img": {"display": "block"},
        "h1": {
            "font-size": "2em",
            "margin-top": ".67em",
            "margin-bottom": ".67em",
            "margin-right": "0",
            "margin-left": "0",
        },
        # "p": {
        #     "display": "block",
        #     "margin-top": "1em",
        #     "margin-bottom": "1em",
        # },
    },
)


@cache
def get_style(tag: str) -> ResolvedStyle:
    return abs_default_style | element_styles[tag]


###########################  CSS-Parsing ############################
Parser = tinycss.CSS21Parser()


current_file: str | None = None  # TODO: not thread-safe (but we probably don't care)


@contextmanager
def set_curr_file(file: str):
    global current_file
    current_file = file
    try:
        yield
    finally:
        current_file = None


############################# Types #######################################
class AtRule(ABC):
    pass


class ImportRule(tinycss.css21.ImportRule, AtRule):
    pass


class MediaRule(AtRule):
    def __init__(self, media: list[str], rules: "SourceSheet"):
        self.media = media
        self.rules = rules

    def matches(self, media: "MediaValue"):
        """Whether a MediaRule matches a Media"""
        return True  # TODO


class PageRule(tinycss.css21.PageRule, AtRule):
    pass


def join_styles(style1: Style, style2: Style) -> Style:
    """
    Join two styles. Prefers the first
    """
    fused = dict(style1)
    for k, v in style2.items():
        if k not in fused or (is_imp(v) and not is_imp(fused[k])):
            fused[k] = v
    return fused


def is_imp(t: Value):
    return t[1]


IMPORTANT = " !important"


def parse_important(s: str) -> InputValue:
    return (s[: -len(IMPORTANT)], True) if s.endswith(IMPORTANT) else (s, False)


def remove_importantd(style: dict[str, tuple[V_T, bool]]) -> dict[str, V_T]:
    """
    Remove the information whether a value in the style is important (dicts)
    """
    return {k: v[0] for k, v in style.items()}


def remove_importantl(
    style: list[tuple[str, tuple[V_T, bool]]]
) -> list[tuple[str, V_T]]:
    """
    Remove the information whether a value in the style is important (lists)
    """
    return [(k, v[0]) for k, v in style]


def add_important(style: ResolvedStyle, imp: bool) -> Style:
    """
    Add the information whether a value in the style is important
    """
    return {k: (v, imp) for k, v in style.items()}


def get_media() -> MediaValue:
    return g["W"], g["H"]


class SourceSheet(list[Rule]):
    """
    A list of AtRules or StyleRules.
    Represents a sheet from a source file.
    """

    _last_media_rules: tuple[MediaValue, list[StyleRule]] | None = None

    @property
    def all_rules(self) -> list[StyleRule]:
        current_media = get_media()
        if self._last_media_rules is not None:
            lastmedia, lastrules = self._last_media_rules
            if lastmedia == current_media:
                return lastrules
        rv: list[StyleRule] = []
        for rule in self:
            if isinstance(rule, MediaRule) and rule.matches(current_media):
                rv.extend(rule.rules.all_rules)
            elif isinstance(rule, tuple):  # Just a regular StyleRule
                rv.append(rule)
        self._last_media_rules = (current_media, rv)
        return rv

    def __add__(self, other):
        return type(self)([*self, *other])

    def __hash__(self):
        return hash(tuple(self))

    @classmethod
    def join(cls, sheets: Iterable["SourceSheet"]):
        return cls(chain.from_iterable(sheets))

    def append(self, __object) -> None:
        raise ValueError("Immutable List")

    def extend(self, __iterable) -> None:
        raise ValueError("Immutable List")

    def __setitem__(self, __i, __v):
        raise ValueError("Immutable List")

    def __delitem__(self, __i) -> None:
        raise ValueError("Immutable List")


g["global_sheet"] = SourceSheet()

############################### Parsing functions #######################################


def parse_inline_style(s: str):
    """
    Parse a style string. For example an inline style.
    Self-written right now
    """
    if not s:
        return {}
    data = s.removeprefix("{").removesuffix("}").strip().split(";")
    pre_parsed = [
        (_split[0], parse_important(":".join(_split[1:])))
        for value in data
        if len(_split := tuple(key.strip() for key in value.split(":"))) >= 2
        or log_error(f"CSS: Invalid style declaration ({value})")
    ]
    return process(pre_parsed)


def parse_file(source: str) -> SourceSheet:
    """
    Parses a file.
    It sets the current_file globally which is just for debugging purposes.
    """
    with set_curr_file(source):
        data = fetch_txt(source)
        return parse_sheet(data)


def parse_sheet(source: str) -> SourceSheet:
    """
    Parses a whole css sheet
    """
    tiny_sheet: tinycss.css21.Stylesheet = Parser.parse_stylesheet(source)
    return SourceSheet(handle_rule(rule) for rule in tiny_sheet.rules)


def handle_rule(
    rule: tinycss.css21.RuleSet
    | tinycss.css21.ImportRule
    | tinycss.css21.MediaRule
    | tinycss.css21.PageRule
    | tinycss.css21.AtRule,
) -> Rule:
    """
    Converts a tinycss rule into an appropriate Rule
    """
    if isinstance(rule, tinycss.css21.RuleSet):
        return (
            rule.selector.as_css(),
            frozendict(
                process(
                    [
                        (decl.name, (decl.value.as_css().strip(), bool(decl.priority)))
                        for decl in rule.declarations
                    ]
                )
            ),
        )
    elif isinstance(rule, tinycss.css21.MediaRule):
        assert rule.at_keyword == "@media"
        return MediaRule(
            rule.media, SourceSheet(handle_rule(rule) for rule in rule.rules)
        )
    else:
        raise NotImplementedError("Not implemented AtRule: " + type(rule).__name__)


###########################  CSS Processing #########################
from pygame.colordict import THECOLORS

THECOLORS.update({"canvastext": (0, 0, 0, 255), "transparent": (0, 0, 0, 0)})

GlobalValue = Literal["inherit", "initial", "unset", "revert"]
global_values = ("inherit", "initial", "unset", "revert")
dir_shorthands: dict[str, Str4Tuple] = {
    "margin": marg_keys,
    "padding": pad_keys,
    "border-width": bw_keys,
    "border-style": bs_keys,
    "border-color": bc_keys,
    "border-radius": br_keys,
    "inset": inset_keys,
}
# smart shorthands are when the split depends on the values
smart_shorthands = {
    "border": {
        "border-width",
        "border-style",
        "border-color",
    },
    **{
        f"border-{k}": {
            f"border-{k}-width",
            f"border-{k}-style",
            f"border-{k}-color",
        }
        for k in directions
    },
    "outline": {"outline-width", "outline-style", "outline-color"},
}

# we cache resolvable initial values
initial_value_cache: dict[str, str | CompValue] = {
    # we could put stuff in here that we know about
    # For example border-style: CompStr("none")
}


@overload
def is_valid(key: str, value: GlobalValue) -> str | CompValue:
    ...


@overload
def is_valid(key: str, value: str) -> None | str | CompValue:
    ...


def is_valid(key: str, value: str) -> None | str | CompValue:
    """
    Checks whether the given CSS property is valid
    If this returns None the CSS property is invalid
    else this could already resolve the computed value
    or at least return a (maybe further resolved) input value (a str)
    """
    global initial_value_cache, abs_default_style, style_attrs, dir_shorthands
    if value == "inherit":
        return value
    elif (attr := style_attrs.get(key)) is not None:
        if value == "initial":
            if (new_value := initial_value_cache.get(key)) is None:
                new_value = initial_value_cache[key] = is_valid(key, attr.initial)
            return new_value
        elif value == "unset":
            return is_valid(key, abs_default_style[key])
        elif value == "revert":
            return "inherit" if attr.inherits else "revert"
        with suppress(KeyError):
            return attr.accept(value, p_style={})
        # TODO: probably add a check that the KeyError was really raised on the p_style, if not raise a BugError
        return value
    elif (keys := dir_shorthands.get(key)) is not None:
        return is_valid(keys[0], value)
    else:
        return CompStr(value)


def process_dir(value: list[str]):
    """
    Takes a split direction shorthand and returns the 4 resulting values
    """
    _len = len(value)
    assert _len <= 4, f"Too many values: {len(value)}/4"
    return value + value[1:2] if _len == 3 else value * (4 // _len)


# IDEA: cache this
def process_property(key: str, value: str) -> list[tuple[str, str]] | CompValue | str:
    """
    Processes a single Property
    If this returns a single value it is final
    If this returns a list all keys should be reprocessed
    """
    # We do a little style hickup here by using assertions instead of normal raises or Error type returns,
    # but I think that is fine
    # TODO: font
    arr = split_value(value)
    if key == "all":
        assert len(arr) == 1
        assert (
            value in global_values
        ), "'all' can only set global values eg. 'all: unset'"
        return [(key, value) for key in style_attrs]
    elif key == "border-radius" and "/" in value:
        x_y = re.split(r"\s*/\s*", value, 1)
        return list(
            zip(
                br_keys,
                (
                    f"{x} {y}"
                    for x, y in zip(*map(lambda s: process_dir(s.split()), x_y))
                ),
            )
        )
    elif (keys := dir_shorthands.get(key)) is not None:
        return list(zip(keys, process_dir(arr)))
    elif (shorthand := smart_shorthands.get(key)) is not None:
        assert len(arr) <= len(
            shorthand
        ), f"Too many values: {len(arr)}, max {len(shorthand)}"
        if len(arr) == 1 and (global_value := arr[0]) in global_values:
            return dict.fromkeys(shorthand, global_value)
        _shorthand = shorthand.copy()
        result: list[tuple[str, str]] = []
        for sub_value in arr:
            for k in _shorthand:
                if is_valid(k, sub_value) is not None:
                    break
            else:  # no-break
                raise AssertionError(f"Invalid value found in shorthand 'sub_value'")
            _shorthand.remove(k)
            result.append((k, sub_value))
        return result
    else:
        assert key in style_attrs, "Unknown Property"
        assert (new_val := is_valid(key, value)) is not None, "Invalid Value"
        return new_val


def process_input(d: list[tuple[str, str]]) -> dict[str, CompValue]:
    """
    Unpacks shorthands and filters and reports invalid declarations
    """
    done: dict[str, CompValue] = {}
    todo: list[tuple[str, str]] = d
    while todo:
        _todo = todo
        todo = []
        for k, v in _todo:
            try:
                processed = process_property(k, v)
                if isinstance(processed, list):
                    todo.extend(processed)
                else:
                    done[k] = processed
            except BugError:
                raise
            except AssertionError as e:
                reason = e.args[0] if e.args else "Invalid Property"
                log_error(f"CSS: {reason} ({k}: {v})")
    return done


def process(d: InputStyle) -> Style:
    """
    Take an InputStyle and process it into a Style
    """
    imp, nimp = map(
        lambda x: process_input(remove_importantl(x)),
        group_by_bool(d, lambda t: is_imp(t[1])),
    )
    return add_important(nimp, False) | add_important(imp, True)


def compute_style(
    tag: str, val: str | CompValue, key: str, p_style: FullyComputedStyle
) -> CompValue:
    """
    Takes a tag, a property (value and key) and a style from which to inherit and returns a CompValue
    """

    def redirect(new_val: str):
        return compute_style(tag, new_val, key, p_style)

    if not is_real_str(val):
        return val
    attr = style_attrs[key]
    match val:
        case "inherit":
            return p_style[key]
        case "initial":
            raise BugError("This case shouldn't happen")
            return redirect(attr.initial)
        case "unset":
            raise BugError("This case shouldn't happen")
            return redirect(abs_default_style[key])
        case "revert":
            return (
                redirect("inherit") if attr.inherits else redirect(get_style(tag)[key])
            )
        case _:
            try:
                return (
                    valid
                    if (valid := attr.accept(val, p_style)) is not None
                    or print_once("Uncomputable property found:", key, val)
                    else redirect("unset")
                )
            except KeyError:
                print_once("Uncomputable property found:", key, val)
                return redirect("unset")


################## Element Calculation ######################
@dataclass
class Calculator:
    """
    A calculator is for calculating the values of AlP attributes (width, height, border-width, etc.)
    It only needs the AlP value, a percentage value and an auto value. If latter are None then they will raise an Exception
    if a Percentage or Auto are encountered respectively
    """

    default_perc_val: float | None = None

    def __call__(
        self,
        value: AutoLP | BinOp | float,
        auto_val: float | None = None,
        perc_val: float | None = None,
    ) -> float:
        """
        This helper function takes a value, an auto_val
        and the perc_value and returns a Number
        if the value is Auto then the auto_value is returned
        if the value is a Length that is returned
        if the value is a Percentage the Percentage is multiplied with the perc_value
        """
        if isinstance(value, float):
            return value
        elif value is Auto:
            assert auto_val is not None, BugError("This attribute cannot be Auto")
            return auto_val
        elif isinstance(value, Length):
            return value.value
        elif isinstance(value, Percentage):
            perc_val = make_default(perc_val, self.default_perc_val)
            assert perc_val is not None, BugError(
                "This attribute cannot be a percentage"
            )
            return value.resolve(perc_val)
        elif isinstance(value, BinOp):
            value.left = self(value.left, auto_val, perc_val)
            value.right = self(value.right, auto_val, perc_val)
            rv = value.resolve()
            assert isinstance(rv, float), BugError(
                f"Calculator couldn't resolve BinOp, {value}, {auto_val}, {perc_val}"
            )
            return rv
        raise TypeError

    def _multi(self, values: Iterable[AutoLP], *args):
        return tuple(self(val, *args) for val in values)

    # only relevant for typing
    def multi2(self, values: tuple[AutoLP, AutoLP], *args) -> tuple[float, float]:
        return self._multi(values, *args)

    def multi4(self, values: AutoLP4Tuple, *args) -> Float4Tuple:
        return self._multi(values, *args)


####################################################################


def pack_longhands(d: ResolvedStyle | FullyComputedStyle) -> ResolvedStyle:
    """Pack longhands back into their shorthands for readability"""
    d: dict[str, str] = {k: str(v).removesuffix(".0") for k, v in d.items()}
    for shorthand, keys in dir_shorthands.items():
        if not all(f in d for f in keys):
            continue
        longhands = [d.pop(f) for f in keys]
        match longhands:
            case [w, x, y, z] if w == x == y == z:  # 0
                d[shorthand] = w
            case [w1, x1, w2, x2] if w1 == w2 and x1 == x2:  # 0 1
                d[shorthand] = f"{w1} {x1}"
            case [w, x1, y, x2] if x1 == x2:  # 0 1 2
                d["shorthand"] = f"{w} {x1} {y}"
            case _:
                d["shorthand"] = " ".join(longhands)
    return d
