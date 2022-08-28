import re
from abc import ABC
from collections import defaultdict
from contextlib import contextmanager, suppress
from dataclasses import dataclass
from functools import cache
from itertools import chain
from operator import itemgetter
from typing import (Generic, Iterable, Mapping, Protocol, TypeVar, cast,
                    overload)

import tinycss

from config import (abs_border_width, abs_font_size, abs_font_weight,
                    abs_length_units, g, rel_font_size)
from own_types import (V_T, Auto, AutoLP, AutoType, Color, CompValue,
                       FontStyle, Length, LengthPerc, Normal, NormalType,
                       Number, Percentage, Sentinel, StyleComputed, StyleInput,
                       frozendict)
from util import dec_re, fetch_src, get_groups, group_by_bool, log_error, noop

#################### Itemgetters/setters ###########################

# https://stackoverflow.com/questions/54785148/destructuring-dicts-and-objects-in-python
Output_T = TypeVar("Output_T", covariant=True)


class T4Getter(Protocol[Output_T]):
    def __call__(
        self, input: StyleComputed
    ) -> tuple[Output_T, Output_T, Output_T, Output_T]:
        ...


class itemsetter(Generic[V_T]):
    def __init__(self, keys: tuple[str, ...]):
        self.keys = keys

    def __call__(self, map: dict, values: tuple[V_T, ...]) -> None:
        for key, value in zip(self.keys, values):
            map[key] = value


directions = ("top", "right", "bottom", "left")
corners = ("top-left", "top-right", "bottom-right", "bottom-left")

pad_keys = tuple(f"padding-{k}" for k in directions)
marg_keys = tuple(f"margin-{k}" for k in directions)
bs_keys = tuple(f"border-{k}-style" for k in directions)
bw_keys = tuple(f"border-{k}-width" for k in directions)
bc_keys = tuple(f"border-{k}-color" for k in directions)
br_keys = tuple(f"border-{k}-radius" for k in corners)
inset_keys = directions

ALPGetter = T4Getter[AutoLP]
inset_getter: ALPGetter = itemgetter(*inset_keys)  # type: ignore[assignment]
mrg_getter: ALPGetter = itemgetter(*marg_keys)  # type: ignore[assignment]
pad_getter: ALPGetter = itemgetter(*pad_keys)  # type: ignore[assignment]

bw_getter: T4Getter[int] = itemgetter(*bw_keys)  # type: ignore[assignment]
bc_getter: T4Getter[Color] = itemgetter(*bc_keys)  # type: ignore[assignment]
bs_getter: T4Getter[str] = itemgetter(*bs_keys)  # type: ignore[assignment]
br_getter: T4Getter[tuple[LengthPerc, LengthPerc]] = itemgetter(*br_keys)  # type: ignore[assignment]

####################################################################


################## Acceptors #################################


CompValue_T = TypeVar("CompValue_T", bound=CompValue, covariant=True)


class Acceptor(Protocol[CompValue_T]):
    def __call__(self, value: str, p_style: StyleComputed) -> None | CompValue_T:
        ...


# https://regexr.com/3ag5b
hex_re = re.compile(r"#([\da-f]{1,2})([\da-f]{1,2})([\da-f]{1,2})")
# Melody
rgb_re = re.compile(rf"rgba?\(({dec_re}),({dec_re}),({dec_re})(?:,({dec_re}),?)?\)")


def color(value: str, p_style):
    if value == "currentcolor":
        return p_style["color"]
    with suppress(ValueError):
        if (groups := get_groups(value, rgb_re)) is not None:
            return Color(*map(lambda x: round(float(x)), groups))
        elif (groups := get_groups(value, hex_re)) is not None:
            return Color(*map(lambda x: int(x * (2 // len(x)), 16), groups))
        return Color(value)


def number(value: str, p_style):
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


split_units_pattern = re.compile(rf"({dec_re})(\w+|%)")


def split_units(attr: str) -> tuple[float, str]:
    """Split a dimension or percentage into a tuple of number and the "unit" """
    if attr == "0":
        return (0, "")
    match = split_units_pattern.fullmatch(attr.strip())
    num, unit = match.groups()  # type: ignore # Raises AttributeError
    return float(num), unit


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
    match value.split():
        case [x]:
            lpx = length_percentage(x, p_style)
            if lpx is not None:
                return (lpx, lpx)
        case [x, y]:
            lpx, lpy = length_percentage(x, p_style), length_percentage(y, p_style)
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

StrSent = str | Sentinel


@dataclass
class StyleAttr(Generic[CompValue_T]):
    initial: str
    kws: Mapping[str, CompValue_T]
    accept: Acceptor[CompValue_T]
    inherits: bool

    def __init__(
        self,
        initial: str,
        kws: set[StrSent] | Mapping[str, CompValue_T] = {},
        acc: Acceptor[CompValue_T] = noop,
        inherits: bool = None,
    ):
        self.initial = initial
        self.kws = self.set2dict(kws) if isinstance(kws, set) else kws
        self.accept = acc
        inherits = acc is not length_percentage if inherits is None else inherits
        self.inherits = (
            inherits if inherits is not None else acc is not length_percentage
        )

    def __repr__(self) -> str:
        return f"StyleAttr(initial={self.initial}, kws={self.kws}, accept={self.accept.__name__}, inherits={self.inherits})"  # type: ignore

    def set2dict(self, s: set) -> Mapping[str, CompValue_T]:
        return {x if isinstance(x, str) else x.name.lower(): x for x in s}

    def convert(self, value: str, p_style: StyleComputed) -> CompValue_T | None:
        kw = self.kws.get(value)
        return kw if kw is not None else self.accept(value, p_style)


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
    "0", cast(dict[str, Length], {}), border_radius, inherits=False
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
}

abs_default_style = {
    k: "inherit" if v.inherits else v.initial for k, v in style_attrs.items()
}
""" The default style for a value (just like "unset") """
# https://trac.webkit.org/browser/trunk/Source/WebCore/css/html.css
# https://hg.mozilla.org/mozilla-central/file/tip/layout/style/res/html.css
# https://www.w3schools.com/cssref/css_default_values.asp

element_styles = defaultdict(
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
        "span": {"display": "inline"}
        # "h1": {"font-size": "2em"},
        # "p": {
        #     "display": "block",
        #     "margin-top": "1em",
        #     "margin-bottom": "1em",
        # },
    },
)


@cache
def get_style(tag: str):
    return abs_default_style | element_styles[tag]


###########################  CSS-Parsing ############################


############################# Types #######################################
class AtRule(ABC):
    pass


class ImportRule(tinycss.css21.ImportRule, AtRule):
    pass


class MediaRule(AtRule):
    def __init__(self, media: list[str], rules: "SourceSheet"):
        self.media = media
        self.rules = rules

    def matches(self, media: "Media"):
        """Whether a MediaRule matches a Media"""
        return True  # TODO


class PageRule(tinycss.css21.PageRule, AtRule):
    pass


Media = tuple[int, int]  # just the window size right now
Value = tuple[str, bool]  # actual value + important
Property = tuple[str, Value]
Style = dict[str, tuple[str, bool]]
StyleRule = tuple[str, Style]
"""
A style with a selector
Example:
p {
    color: red !important;
} -> (p, {color: (red, True)})
"""
StyleSheet = dict[str, Style]
Rule = AtRule | StyleRule


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


def parse_important(s: str) -> Value:
    return (s[: -len(IMPORTANT)], True) if s.endswith(IMPORTANT) else (s, False)


@overload
def remove_important(style: list[Property]) -> list[tuple[str, str]]:
    ...


@overload
def remove_important(style: Style) -> StyleInput:
    ...


def remove_important(
    style: list[Property] | Style,
) -> StyleInput | list[tuple[str, str]]:
    """
    Remove the information whether a value in the style is important
    """
    d, t = (style, list) if isinstance(style, list) else (style.items(), dict)
    return t((k, v[0]) for k, v in d)


def add_important(style: StyleInput, imp: bool) -> Style:
    """
    Add the information whether a value in the style is important
    """
    return {k: (v, imp) for k, v in style.items()}


def get_media() -> Media:
    return g["W"], g["H"]


class SourceSheet(list[Rule]):
    """
    A list of AtRules or StyleRules.
    Represents a sheet from a source file.
    """

    _last_media_rules: tuple[Media, list[StyleRule]] | None = None

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
    data = s.removeprefix("{").removesuffix("}").strip().lower().split(";")
    pre_parsed = [
        (_split[0], parse_important(_split[1]))
        for value in data
        if len(_split := tuple(key.strip() for key in value.split(":"))) == 2
        or log_error(f"CSS: Invalid style declaration ({value})")
    ]
    return process(pre_parsed)


Parser = tinycss.CSS21Parser()


current_file: str | None = None  # TODO: not thread-safe


@contextmanager
def set_curr_file(file: str):
    global current_file
    current_file = file
    try:
        yield
    finally:
        current_file = None


def parse_file(source: str) -> SourceSheet:
    """
    Parses a file.
    It sets the current_file globally which is just for debugging purposes.
    """
    with set_curr_file(source):
        data = fetch_src(source)
        return parse_sheet(data)


def parse_sheet(source: str) -> SourceSheet:
    """
    Parses a whole css sheet
    """
    tiny_sheet: tinycss.css21.Stylesheet = Parser.parse_stylesheet(source.lower())
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

colors = {"currentcolor", *THECOLORS}
global_values = frozenset({"inherit", "initial", "unset", "revert"})

dir_fallbacks = {"right": "top", "bottom": "top", "left": "right"}
dir_shorthands: dict[str, tuple[str, ...]] = {
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
}


def process(d: list[Property] | Style) -> Style:
    itr = d if isinstance(d, list) else d.items()
    imp, nimp = map(
        process_input, map(remove_important, group_by_bool(itr, lambda t: is_imp(t[1])))
    )
    return add_important(nimp, False) | add_important(imp, True)


def process_input(d: list[tuple[str, str]]) -> StyleInput:
    """
    Unpacks shorthands and filters and reports invalid declarations
    """
    done: dict[str, str] = {}

    def inner(d: Iterable[tuple[str, str]]):
        for key, value in d:
            try:
                done.update(process_property(key, value))
            except AssertionError as e:
                reason = e.args[0] if e.args else "Invalid Property"
                log_error(f"CSS: {reason} ({key}: {value})")

    inner(d)
    while True:
        _done, todo = group_by_bool(done.items(), lambda item: item[0] in style_attrs)
        done = dict(_done)
        if not todo:
            break
        inner(todo)
    return done


def is_valid(name: str, value: str):
    """
    Checks whether the given CSS property is valid
    """
    if value in global_values:
        return True
    elif (attr := style_attrs.get(name)) is not None:
        with suppress(KeyError):
            return value in attr.kws or attr.accept(value, {}) is not None
        return True
    elif (keys := dir_shorthands.get(name)) is not None:
        return is_valid(keys[0], value)
    return False


def split(s: str):
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
        if c == "(":
            brackets += 1
        elif c == ")":
            assert brackets
            brackets -= 1
    if rec:
        result.append(curr_string)
    return result


def process_dir(value: list[str]):
    assert len(value) <= 4, f"Too many values: {len(value)}/4"
    match value:
        case [x, y, z]:
            return [x, y, z, y]
        case v:
            return v * (4 // len(v))


def process_property(key: str, value: str) -> dict[str, str]:
    """Processes a single Property, by unpacking shorthands"""
    # TODO: font
    # TODO: outline
    arr = split(value)
    if key == "all":
        assert len(arr) == 1
        assert value in global_values
        return dict.fromkeys(style_attrs, value)
    elif key == "border-radius" and "/" in value:
        x_y = re.split(r"\s*/\s*", value, 1)
        return dict(
            zip(
                br_keys,
                (
                    " ".join(item)
                    for item in zip(*map(lambda s: process_dir(s.split()), x_y))
                ),
            )
        )
    elif (keys := dir_shorthands.get(key)) is not None:
        return dict(zip(keys, process_dir(arr)))
    elif (shorthand := smart_shorthands.get(key)) is not None:
        assert len(arr) <= len(
            shorthand
        ), f"Too many values: {len(arr)}, max {len(shorthand)}"
        if len(arr) == 1 and arr[0] in global_values:
            return {k: arr[0] for k in shorthand}  # global value for all keys
        result = {k: v for v in arr for k in shorthand if is_valid(k, v)}
        left = set(arr).difference(result.values())
        assert not left, f"Invalid value(s): {', '.join(left)}"
        return result
    else:
        assert len(arr) == 1 or len(arr) == 2 and key in br_keys
        value = arr[0]
        assert key in style_attrs, "Unknown Property"
        assert is_valid(key, value), "Invalid Value"
        return {key: value}


def pack_longhands(d: StyleComputed) -> StyleInput:
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
