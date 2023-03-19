from __future__ import annotations
from abc import abstractmethod

# fmt: off
import asyncio
import math
import re
from collections import defaultdict, deque
from contextlib import suppress
from dataclasses import dataclass
from functools import cache, partial
from itertools import chain, islice
from operator import add, mul, sub, truediv
from typing import (Any, Callable, Generic, Iterable, Literal, Mapping,
                    Protocol, TypeVar, Union, cast, overload)

import positron.Media as Media
import positron.Selector as Selector
import tinycss
import tinycss.token_data

from positron.utils.func import map_dvals
from .config import (abs_angle_units, abs_border_width, abs_font_size,
                    abs_font_weight, abs_length_units, abs_resolution_units,
                    abs_time_units, cursors, g, rel_font_size,
                    rel_length_units)
from .types import (V_T, Angle, Auto, AutoType, BugError, Color, CompStr,
                       CSSDimension, Drawable, Float4Tuple, FontStyle, Length,
                       LengthPerc, Number, Percentage, Resolution, Sentinel,
                       Str4Tuple, StrSent, Time, frozendict)
from .style.itemgetters import *
from .style.MediaQuery import *
from .style.Parser import Parser, parse_important, set_curr_file
from .utils import (consume_list, fetch_txt, find_index, group_by_bool,
                  in_bounds, log_error, make_default, noop, print_once,
                  tup_replace)
from .utils.colors import hsl2rgb, hwb2rgb
from .utils.regex import (GeneralParser, get_groups, match_bracket, re_join,
                         split_value, whitespace_re)

# fmt: on

# Typing

CompValue = Any
CompValue_T = TypeVar("CompValue_T", bound=CompValue, covariant=True)

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
StyleRule = tuple[Selector.Selector, Style]
Rule = Union[AtRule, StyleRule]

CalcTypes = float, CSSDimension
CalcType = Union[type[float], type[CSSDimension]]
CalcValue = float | CSSDimension
Operator = Callable[[CalcValue, CalcValue], CalcValue]

ParseResult = Union[CalcValue, "BinOp"]
ParseResult_T = TypeVar("ParseResult_T", bound=ParseResult)


def is_real_str(x):
    """
    Returns whether x is a real str and not computed
    """
    return isinstance(x, str) and not isinstance(x, CompStr)


def ensure_comp(x: CompValue_T | str) -> CompValue_T | CompStr:
    return CompStr(x) if isinstance(x, str) else x


# css func should be used if there is a single css function expected
# get_css_func should be used if there a several css functions expected
def css_func(value: str, name: str, delimiter=","):
    if value.startswith(name + "(") and value.endswith(")"):
        inside = value[len(name) + 1 : -1]
        if delimiter:
            return re.split(rf"\s*{re.escape(delimiter)}\s*", inside)
        else:
            return [inside]


def get_css_func(posses: Iterable[str] | str = ""):
    _posses: str = (
        ident_re
        if not posses
        else re_join(*posses)
        if isinstance(posses, Iterable)
        else str
    )
    pattern = re.compile(rf"({_posses})\((.*)\)")

    def inner(value: str) -> None | tuple[str, list[str]]:
        if match := pattern.fullmatch(value):
            name, _args = match.groups()
            args = re.split(r"\s*,\s*", _args)
            return name, args
        return None

    return inner


def remove_quotes(value: str):
    for quote in ("'", '"'):
        if value.startswith(quote) and value.endswith(quote):
            return value[1:-1]
    return value


def split_units(attr: str) -> tuple[float, str]:
    """Split a dimension or percentage into a tuple of number and the "unit" """
    match = dim_pattern.fullmatch(attr)
    num, unit = match.groups()  # type: ignore # Raises AttributeError
    return float(num), unit.lower()


def is_custom(k: str):
    return k.startswith("--")


# https://docs.python.org/3/library/re.html#simulating-scanf
dec_re = r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?"
ident_re = (
    r"-*\w[-\w\d]*"  # a digit can only come after a letter and one letter is minimum
)
hex_pattern = re.compile(r"#([\da-f]{1,2})([\da-f]{1,2})([\da-f]{1,2})([\da-f]{1,2})?")
number_pattern = re.compile(dec_re)
# units
units_map: dict[str, type[CSSDimension]] = {
    "%": Percentage,
    **dict.fromkeys(chain(abs_length_units, rel_length_units), Length),
    **dict.fromkeys(abs_angle_units, Angle),
}
unit_re = re_join(*units_map)
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
_reversed_op_map = {v: k for k, v in op_map.items()}
op_re = re.compile(re_join(*op_map))
# calc literals
literal_map = {
    "pi": math.pi,
    "e": math.e,
    # I don't understand why you would need these. Like, you're not gonna make an element with a font-size of NaN or -infinity
    # "infinity": float("inf"),
    # "-infinity": float("-inf"),
    # "NaN": float("nan"),
}
literal_re = re.compile(re_join(*literal_map))
no_intrinsic_type = frozenset({Percentage, float})


######################### Calculation ##############################
@dataclass
class Calculator:
    default_perc_val: float | None = None

    def __call__(
        self,
        value: AutoType | ParseResult,
        auto_val: float | None = None,
        perc_val: float | None = None,
    ) -> float:
        """
        This helper function takes a value, an auto_val
        and the perc_value and returns a Number
        if the value is Auto then the auto_value is returned
        if the value is a Length or similar that is returned
        if the value is a Percentage the Percentage is multiplied with the perc_value
        """
        if isinstance(value, float):
            return value
        elif value is Auto:
            assert auto_val is not None, BugError("This attribute cannot be Auto")
            return auto_val
        elif isinstance(value, Percentage):
            perc_val = make_default(perc_val, self.default_perc_val)
            assert perc_val is not None, BugError(
                "This attribute cannot be a percentage"
            )
            return value.resolve(perc_val)
        elif isinstance(value, CSSDimension):
            return value.value
        elif isinstance(value, BinOp):
            new_value = type(value)(
                self(value.left, auto_val, perc_val),
                value.op,
                self(value.right, auto_val, perc_val),
            )
            rv = new_value.resolve()
            assert isinstance(rv, float), BugError(
                f"Calculator couldn't resolve BinOp, {value}, {auto_val}, {perc_val}"
            )
            return rv
        elif value is None:
            raise ValueError
        raise BugError(f"Unsupported type in calc, {value} {value.__class__.__name__}")

    def _multi(self, values: Iterable[AutoType | ParseResult], *args):
        return tuple(self(val, *args) for val in values)

    # only relevant for typing
    def multi2(
        self, values: tuple[AutoType | ParseResult, AutoType | ParseResult], *args
    ) -> tuple[float, float]:
        return self._multi(values, *args)

    # I would love a syntax like tuple[MyType,2]->tuple[MyType,MyType], and ... just means unspecified
    def multi4(
        self,
        values: tuple[
            AutoType | ParseResult,
            AutoType | ParseResult,
            AutoType | ParseResult,
            AutoType | ParseResult,
        ],
        *args,
    ) -> Float4Tuple:
        return self._multi(values, *args)


calculator = Calculator()
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


@dataclass
class BinOp:
    left: CalcValue
    op: Operator
    right: CalcValue

    def resolve(self) -> ParseResult:
        try:
            return self.op(self.left, self.right)
        except ValueError:
            return self

    @abstractmethod
    def get_type(self) -> CalcType:
        ...

    def __repr__(self):
        return f"{self.left}{_reversed_op_map[self.op]}{self.right}"


@dataclass(unsafe_hash=True, repr=False)
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


@dataclass(unsafe_hash=True, repr=False)
class MulOp(BinOp):
    left: CalcValue
    op: Operator
    right: CalcValue

    def get_type(self):
        return (
            ltype
            if (ltype := get_type(self.left)) is not float
            else get_type(self.right)
        )


def get_type(x: ParseResult) -> CalcType:
    if isinstance(x, BinOp):
        return x.get_type()
    return type(x)


class Calc(Acceptor[CalcValue | BinOp], GeneralParser):
    _accepts: frozenset[CalcType]
    default_type: CalcType

    def __init__(self, *types):
        self._accepts = frozenset(types)
        intrinsic_type = self._accepts.difference(no_intrinsic_type)
        if (len_ := len(intrinsic_type)) > 1:
            raise BugError("Calc with more than one intrinsic type")
        elif len_ == 1:
            self.default_type = next(iter(intrinsic_type))
        else:
            self.default_type = (
                float
                if float in self._accepts
                else int
                if int in self._accepts
                else Percentage
            )

    def accepts_type(self, x):
        return x in self._accepts

    def acc(self, value: str, p_style):
        if value == "0":
            for type_ in (Length, float):
                if self.accepts_type(type_):
                    return type_(0)
            return None
        try:
            number, unit = split_units(value)
        except AttributeError:
            if self.default_type is float and number_pattern.fullmatch(value):
                return float(value)
            else:
                return None
        _type = units_map[unit]
        if not self.accepts_type(_type):
            return None
        if _type is Percentage:
            return Percentage(number)
        elif _type is Length:
            return _length((number, unit), p_style)
        elif _type is Angle:
            if conversion_factor := abs_angle_units.get(unit):
                return Angle(number * conversion_factor)
        elif _type is Time:
            if conversion_factor := abs_time_units.get(unit):
                return Time(number * conversion_factor)
        elif _type is Resolution:
            if conversion_factor := abs_resolution_units.get(unit):
                return Resolution(number * conversion_factor)

    def __call__(self, value: str, p_style: FullyComputedStyle = {}):
        acc = partial(self.acc, p_style=p_style)
        if args := css_func(value, "calc", ""):
            # lexer
            self.x = args[0]
            stack = deque[str | CalcValue | float | BinOp]()
            while self.x:
                start_x = self.x
                if self.consume("(") or self.consume("calc("):
                    stack.append("(")
                    continue
                elif self.consume(")"):
                    stack.append(")")
                    continue
                # operator has priority over values if the last token was a real value
                elif (
                    stack
                    and not isinstance(stack[-1], str)
                    and (operator := self.consume(op_re))
                ):
                    stack.append(operator)
                elif dimension := self.consume(dim_pattern):
                    if (result := acc(dimension)) is None:
                        return None
                    else:
                        stack.append(result)
                elif literal := self.consume(literal_re):
                    stack.append(literal_map[literal])
                elif number := self.consume(number_pattern):
                    stack.append(float(number))
                elif operator := self.consume(op_re):
                    stack.append(operator)
                elif self.consume(whitespace_re):
                    pass
                elif start_x == self.x:
                    return None  # found no valid character
            try:
                if self.accepts_type(
                    get_type(rv := self.parse(stack))  # type: ignore
                ):  # run-time type checking
                    return rv
            except (ValueError, IndexError, ZeroDivisionError):
                return None
        else:
            return acc(value)

    def parse(self, d: Iterable[str | ParseResult_T]) -> ParseResult_T | BinOp:
        """
        Parses the tokens
        Raises ValueError, IndexError or ZeroDivisionError on failure
        """
        # parser
        t: tuple[str | ParseResult_T, ...] = tuple(d)
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
            if l_type is not r_type and not (
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


def no_change(value: str, p_style) -> str:
    return value


def comma_sep(value: str, p_style) -> tuple[str, ...]:
    return tuple(x.strip().strip('"') for x in value.split(","))


number = cast(Acceptor[float], Calc(float))
length = cast(Acceptor[Length], Calc(Length))
percentage = cast(Acceptor[Percentage], Calc(Percentage))
number_angle = cast(Acceptor[float | Angle], Calc(float, Angle))
number_percentage = cast(Acceptor[float | Percentage | BinOp], Calc(float, Percentage))
length_percentage = cast(Acceptor[LengthPerc | BinOp], Calc(Length, Percentage))


def background_image(value: str, p_style) -> tuple[Drawable, ...]:
    # TODO: element, gradients, and more
    arr = split_value(value)
    result: list[Drawable] = []
    for v in arr:
        if args := css_func(v, "url", ""):
            result.append(Media.Image([remove_quotes(args[0])]))
        else:
            log_error("background-image only supports urls right now", v)
    return tuple(result)


def _handle_rgb(value: str):
    value: float = calculator(number_percentage(value), perc_val=255)  # type: ignore
    if 0 < value <= 1:
        value *= 255
    return int(in_bounds(value, 0, 255))


def _rgb(*rgb: str):
    return Color(*map(_handle_rgb, rgb))


def _hsl(h: str, *sl: str):
    # here we use the built-in pygame hsl converter
    hue: float = calculator(number_angle(h))  # type: ignore
    return hsl2rgb(hue, *(percentage(x).resolve(1) for x in sl))  # type: ignore


def _hwb(h: str, *wb: str):
    hue: float = calculator(number_angle(h))  # type: ignore
    return hwb2rgb(hue, *(percentage(x).resolve(1) for x in wb))  # type: ignore


color_funcs: dict[str, Callable[..., Color]] = {
    "rgb": _rgb,
    "rgba": _rgb,
    "hsl": _hsl,
    "hsla": _hsl,
    "hwb": _hwb,
}
_get_color_func = get_css_func(color_funcs)


def color(value: str, p_style):
    if value == "currentcolor":
        return p_style["color"]
    with suppress(ValueError, TypeError):
        if css_func := _get_color_func(value):  # css_function
            func_name, args = css_func
            if len(args) == 1:
                args = args[0].replace("/", "").split()
            if len(args) == 4:
                *args, a = args
                color = color_funcs[func_name](*args)
                if color is None:
                    return None
                color.a = int(255 * calculator(number_percentage(a), perc_val=1))  # type: ignore
                return color
            else:
                return color_funcs[func_name](*args)
        elif groups := get_groups(
            value.lower(), hex_pattern
        ):  # "#rrggbb" or #"#rgb" but also "#rrggbbaa" and "#rgba"
            return Color(*map(lambda x: int(x * (2 // len(x)), 16), groups))
        return Color(value)


def font_size(value: str, p_style):
    if value in abs_font_size:
        return g["default_font_size"] * 1.2 ** abs_font_size[value]
    p_size: float = p_style["font-size"]
    if value in rel_font_size:
        return p_size * 1.2 ** rel_font_size[value]
    else:
        if (rv := length_percentage(value, p_style)) is None:
            return None
        return calculator(rv, perc_val=p_size)


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
    num, s = dimension
    if num == 0:
        return Length(0)
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
        inherits: bool = False,
    ):
        """
        If the kws are a set then they are automatically converted into a dict
        Inherits as specified or if the acceptor is length_percentage
        """
        self.initial = initial
        self.kws = self.set2dict(kws) if isinstance(kws, set) else kws
        self.acc = acc
        self.inherits = inherits

    def set2dict(
        self, s: set[StrSent]
    ) -> Mapping[str, CompValue_T | Sentinel | CompStr]:
        return {x if isinstance(x, str) else x.value: ensure_comp(x) for x in s}

    def accept(
        self, value: str, p_style: FullyComputedStyle
    ) -> CompValue_T | CompStr | Sentinel | None:
        # insert all vars
        value = re.sub(
            rf"var\(({ident_re})\)", lambda match: p_style[match.group(1)], value
        )
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
    length_percentage,
)
ALP0 = StyleAttr("0", auto, length_percentage)

BorderWidthAttr: StyleAttr[Length] = StyleAttr("medium", abs_border_width, length)
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
)
BorderColorAttr: StyleAttr[Color] = StyleAttr("currentcolor", acc=color)
BorderRadiusAttr: StyleAttr[LengthPerc] = StyleAttr("0", acc=border_radius)
OverflowAttr: StyleAttr[CompStr] = StyleAttr(
    "auto",
    {
        # we only implement overlay scroll bars and only when there actually is an overflow
        "auto": CompStr("scroll"),
        **{
            k: CompStr(k)
            for k in (
                # clip: clipping, no scroll container
                # visible: no clipping
                # hidden: just like scroll but user can't scroll
                "scroll",
                "clip",
                "visible",
                "hidden",
            )
        },
    },
)
overflow_keys = ("overflow-x", "overflow-y")

prio_keys = {"color", "font-size"}  # currentcolor and 1em for example


def has_prio(key: str):
    return key in prio_keys or is_custom(key)


style_attrs: dict[str, StyleAttr[CompValue]] = {
    "color": StyleAttr("canvastext", acc=color, inherits=True),
    "font-weight": StyleAttr("normal", abs_font_weight, font_weight, inherits=True),
    "font-family": StyleAttr("Arial", acc=comma_sep, inherits=True),
    "font-size": StyleAttr("medium", acc=font_size, inherits=True),
    "font-style": StyleAttr("normal", acc=font_style, inherits=True),
    "line-height": StyleAttr("normal", normal, Calc(float, Length, Percentage), True),
    "word-spacing": StyleAttr("normal", normal, length_percentage, True),
    # "vertical-align": ...,
    "text-align": StyleAttr("left", {"left", "right", "center", "justify"}),
    "display": StyleAttr("inline", {"inline", "block", "none"}),
    "background-color": StyleAttr("transparent", acc=color),
    "background-image": StyleAttr("none", {"none": ()}, background_image),
    "width": AALP,  # TODO: max-content, min-content, fit-content
    "height": AALP,
    "position": StyleAttr(
        "static", {"static", "relative", "absolute", "sticky", "fixed"}
    ),
    "box-sizing": StyleAttr("content-box", {"content-box", "border-box"}),
    **{key: ALP0 for key in chain(inset_keys, pad_keys, marg_keys)},
    **{key: BorderWidthAttr for key in bw_keys},
    **{key: BorderStyleAttr for key in bs_keys},
    **{key: BorderColorAttr for key in bc_keys},
    **{key: BorderRadiusAttr for key in br_keys},
    "outline-width": BorderWidthAttr,
    "outline-style": BorderStyleAttr,
    "outline-color": BorderColorAttr,
    "outline-offset": StyleAttr("0", acc=length),
    "cursor": StyleAttr("auto", auto | cursors),
    **dict.fromkeys(overflow_keys, OverflowAttr),
}

abs_default_style: dict[str, str] = {
    k: "inherit" if v.inherits else v.initial for k, v in style_attrs.items()
}
""" The default style for a value (just like "unset") """


# Helpers
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
                rv.extend(rule.content.all_rules)
            elif isinstance(rule, tuple):  # Just a regular StyleRule
                rv.append(rule)
        self._last_media_rules = (current_media, rv)
        return rv

    def __add__(self, other):
        return type(self)([*self, *other])

    def __hash__(self):
        return hash(tuple(self))

    @classmethod
    def join(cls, sheets: Iterable[SourceSheet]):
        return cls(chain.from_iterable(sheets))

    def append(self, __object) -> None:
        raise ValueError("Immutable List")

    def extend(self, __iterable) -> None:
        raise ValueError("Immutable List")

    def __setitem__(self, __i, __v):
        raise ValueError("Immutable List")

    def __delitem__(self, __i) -> None:
        raise ValueError("Immutable List")


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


parse_lock = asyncio.Lock()


async def parse_file(source: str) -> SourceSheet:
    """
    Parses a file from the given source (any url).
    It sets the current_file globally which is just for debugging purposes.
    """
    async with parse_lock:  # with this we ensure that only one css-sheet is ever parsed at the same time
        with set_curr_file(source):
            return parse_sheet(await fetch_txt(source))


def parse_sheet(source: str) -> SourceSheet:
    """
    Parses a whole css sheet
    """
    tiny_sheet: tinycss.css21.Stylesheet = Parser.parse_stylesheet(source)
    for error in tiny_sheet.errors:
        log_error(error)
    return handle_rules(tiny_sheet.rules)


def handle_rules(rules: list):
    return SourceSheet(filter(None, (handle_rule(rule) for rule in rules)))


def handle_rule(
    rule: tinycss.css21.RuleSet
    | tinycss.css21.ImportRule
    | tinycss.css21.MediaRule
    | tinycss.css21.PageRule
    | tinycss.css21.AtRule,
) -> Rule | None:
    """
    Converts a tinycss rule into an appropriate Rule
    """
    if isinstance(rule, tinycss.css21.RuleSet):
        try:
            return (
                Selector.parse_selector(rule.selector.as_css()),
                frozendict(
                    process(
                        [
                            (
                                decl.name,
                                (decl.value.as_css().strip(), bool(decl.priority)),
                            )
                            for decl in rule.declarations
                        ]
                    )
                ),
            )
        except Selector.InvalidSelector:
            log_error("Invalid Selector:", rule.selector.as_css())
            return None
    elif isinstance(rule, tinycss.css21.MediaRule):
        return MediaRule(rule.media, handle_rules(rule.rules))
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
    assert _len <= 4, f"Too many values: {_len}/4"
    return [*value, value[1]] if _len == 3 else value * (4 // _len)


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
    if is_custom(key):
        return CompStr(value)
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
    elif key == "overflow":
        max_len = 2
        split = value.split()
        split_len = len(split)
        assert split_len <= max_len, f"Too many values: {split_len}, max {max_len}"
        return list(zip(overflow_keys, split * (max_len // split_len)))
    elif (keys := dir_shorthands.get(key)) is not None:
        return list(zip(keys, process_dir(arr)))
    elif (shorthand := smart_shorthands.get(key)) is not None:
        assert len(arr) <= len(
            shorthand
        ), f"Too many values: {len(arr)}, max {len(shorthand)}"
        if len(arr) == 1 and (_global := arr[0]) in global_values:
            return [(k, _global) for k in shorthand]
        _shorthand = shorthand.copy()
        result: list[tuple[str, str]] = []
        for sub_value in arr:
            for k in _shorthand:
                if is_valid(k, sub_value) is not None:
                    break
            else:  # no-break
                raise AssertionError(f"Invalid value found in shorthand: {sub_value}")
            _shorthand.remove(k)
            result.append((k, sub_value))
        return result
    else:
        assert key in style_attrs, "Unknown Property"
        assert (new_val := is_valid(key, value)) is not None, "Invalid Value"
        return new_val


def process_input(d: Iterable[tuple[str, str]]) -> dict[str, CompValue]:
    """
    Unpacks shorthands and filters and reports invalid declarations.
    """
    d = list(d)
    done: dict[str, CompValue] = {}
    for k, v in consume_list(d):
        try:
            processed = process_property(k, v)
            if isinstance(processed, list):
                d.extend(processed)
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
        case "unset":
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


def pack_longhands(d: ResolvedStyle | FullyComputedStyle) -> ResolvedStyle:
    """Pack longhands back into their shorthands for readability"""
    d = dict(d)
    for shorthand, keys in dir_shorthands.items():
        if any(f not in d for f in keys):
            continue
        longhands = [str(d.pop(f)) for f in keys]
        match longhands:
            case [w, x, y, z] if w == x == y == z:  # 0
                d[shorthand] = w
            case [w1, x1, w2, x2] if w1 == w2 and x1 == x2:  # 0 1
                d[shorthand] = f"{w1} {x1}"
            case [w, x1, y, x2] if x1 == x2:  # 0 1 2
                d[shorthand] = f"{w} {x1} {y}"
            case _:
                d[shorthand] = " ".join(longhands)
    return d


element_styles: dict[str, dict[str, str]] = defaultdict(
    dict,
    map_dvals(
        {
            "html": {
                **{k: attr.initial for k, attr in style_attrs.items() if attr.inherits},
                "display": "block",
            },
            "head": {
                "display": "none",
            },
            "body": {
                "display": "block",
            },
            "span": {"display": "inline"},
            "h1": {"display": "block", "font-size": "2em", "margin": ".1em 0"},
            "h2": {
                "display": "block",
                "font-size": "1.5em",
                "margin": ".1em 0",
            },
            "div": {
                "display": "block",
            },
            "p": {
                "display": "block",
                "margin": "1em 0",
            },
            "br": {"width": "100%", "height": "1em"},
            "a": {
                "color": "blue",
                "cursor": "pointer",
                # "text-decoration": "underline"
            },
            "center": {"display": "block", "text-align": "center"},
            "button": {"cursor": "pointer", "text-align": "center"},
            "input": {
                "border-style": "solid",
                "border-radius": "3px",
                "outline-offset": "1px",
                "padding": "3px",
            },
            "audio": {
                "border-style": "solid",
                "border-radius": "3px",
                "outline-offset": "1px",
                "padding": "3px",
                "background-color": "grey",
            },
            "meter": {
                "width": "4em",
                "height": "1em",
                "border": "solid medium grey",
                "border-radius": "5px",
            },
            "strong": {"font-weight": "bold"},
        },
        lambda v: process_input(v.items()),
    ),
)


@cache
def get_style(tag: str) -> ResolvedStyle:
    return abs_default_style | element_styles[tag]
