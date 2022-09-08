# fmt: off
import re
from abc import ABC
from collections import defaultdict
from contextlib import contextmanager, suppress
from dataclasses import dataclass
from functools import cache
from itertools import chain
from operator import itemgetter
from typing import (Any, Generic, Iterable, Literal, Mapping, Protocol, TypeVar, Union,
                    overload)

import tinycss

from config import (abs_border_width, abs_font_size, abs_font_weight,
                    abs_length_units, g, rel_font_size)
import Media
from own_types import (CO_T, V_T, Auto, AutoLP, AutoType, BugError, Color, Drawable,
                       FontStyle, Length, LengthPerc, Normal, NormalType,
                       Number, Percentage, Sentinel, Str4Tuple, StrSent,
                       frozendict)
from util import (dec_re, fetch_txt, get_groups, group_by_bool, log_error,
                  noop, print_once)
# fmt: on

# Typing
class CompStr(str):
    def __repr__(self) -> str:
        return f"CompStr({self})"


CompValue = Any  # | float | Percentage | Sentinel | FontStyle | Color | tuple[Drawable, ...] | CompStr but not a normal str
# A Value is the actual value together with whether the value is set as important
InputValue = tuple[str, bool]
Value = tuple[str | CompValue, bool]
InputProperty = tuple[str, InputValue]
Property = tuple[str, Value]
InputStyle = list[InputProperty]
Style = dict[str, Value]
ResolvedStyle = dict[str, str | CompValue]  # Style without important
FullyComputedStyle = Mapping[str, CompValue]
StyleRule = tuple[str, Style]
"""
A style with a selector
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


@overload
def ensure_comp(x: str) -> CompStr:  # type: ignore
    ...


@overload
def ensure_comp(x: V_T) -> V_T:
    ...


def ensure_comp(x) -> CompValue:
    return CompStr(x) if is_real_str(x) else x


def split_value(s: str) -> list[str]:
    """
    This function is for splitting css values that include functions
    """
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
    def __call__(self, value: str, p_style: FullyComputedStyle) -> None | CompValue_T:
        ...


def css_func(value: str, name: str) -> list[str] | None:
    if value.startswith(name + "(") and value.endswith(")"):
        return re.split(r"\s*,\s*", value.removeprefix(name + "(").removesuffix(")"))


def remove_quotes(value: str):
    for quote in ("'", '"'):
        if (
            len(new_val := value.removeprefix(quote).removesuffix(quote))
            == len(value) - 2
        ):
            return new_val
    return new_val


# https://regexr.com/3ag5b
hex_re = re.compile(r"#([\da-f]{1,2})([\da-f]{1,2})([\da-f]{1,2})")
split_units_pattern = re.compile(rf"({dec_re})(\w+|%)")


def split_units(attr: str) -> tuple[float, str]:
    """Split a dimension or percentage into a tuple of number and the "unit" """
    if attr == "0":
        return (0, "")
    match = split_units_pattern.fullmatch(attr.strip())
    num, unit = match.groups()  # type: ignore # Raises AttributeError
    return float(num), unit


def background_image(value: str, p_style) -> tuple[Drawable, ...]:
    # TODO: element, gradients, and more
    arr = split_value(value)
    result: list[Drawable] = []
    for v in arr:
        if args := css_func(v, "url"):
            result.append(Media.Image([remove_quotes(args[0])]))
        else:
            raise NotImplementedError("background-image only supports urls right now")
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
            return Color(*map(round, (r, g, b, a*255)))
        elif groups := get_groups(value.lower(), hex_re):
            return Color(*map(lambda x: int(x * (2 // len(x)), 16), groups))
        return Color(value)


def number(value: str, p_style):
    # This is so much simpler than actually doing regex matches and then still parsing as a float
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
        if unit == "%":
            return Percentage(num) if mult is None else Length(mult * Percentage(num))
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
    kws: Mapping[str, StrSent | CompValue_T]
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

    def __repr__(self) -> str:
        return f"StyleAttr(initial={self.initial}, kws={self.kws}, accept={self.accept.__name__}, inherits={self.inherits})"

    def set2dict(self, s: set[StrSent]) -> Mapping[str, CompValue_T | StrSent]:
        return {x if isinstance(x, str) else x.value: x for x in s}

    def accept(
        self, value: str, p_style: FullyComputedStyle
    ) -> CompValue_T | CompStr | Sentinel | None:
        kw = self.kws.get(value)
        return ensure_comp(kw if kw is not None else self.acc(value, p_style))


####### Helpers ########

# we don't want copies of these (memory) + better readibility
auto: dict[str, AutoType] = {"auto": Auto}
normal: dict[str, NormalType] = {"normal": Normal}

AALP = StyleAttr(
    "auto",
    auto,
    length_percentage,
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


def no_change(value: str, p_style) -> str:
    return value


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


@overload
def remove_important(style: list[Property]) -> list[tuple[str, str]]:
    ...


@overload
def remove_important(style: Style) -> ResolvedStyle:
    ...


def remove_important(
    style: list[Property] | Style,
) -> ResolvedStyle | list[tuple[str, str]]:
    """
    Remove the information whether a value in the style is important
    """
    d, t = (style, list) if isinstance(style, list) else (style.items(), dict)
    return t((k, v[0]) for k, v in d)


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


def parse_inline_style(s: str) -> Style:
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
    return False


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


def process_input(d: list[tuple[str, str]]):
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
        lambda x: process_input(remove_important(x)),
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
            return (
                valid
                if (valid := attr.accept(val, p_style)) is not None
                or print_once("Uncomputable property found:", key, val)
                else redirect("unset")
            )


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
