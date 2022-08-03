"""
Utilities for all kinds of needs (funcs, regex, etc...) 
"""

import re
from contextlib import contextmanager, redirect_stdout, suppress
from dataclasses import dataclass
from functools import cache, partial
from operator import attrgetter, itemgetter
from typing import Any, Iterable, Protocol, TypeVar

import pygame as pg
import pygame.freetype as freetype

from config import all_units
from own_types import (
    Auto,
    AutoNP,
    AutoNP4Tuple,
    Color,
    Dimension,
    Float4Tuple,
    Number,
    Percentage,
    Rect,
    Surface,
    Vector2,
    _XMLElement,
    style_computed,
)


def noop(*args, **kws):
    return None


################## Element Calculation ######################
# This calculates values that have to be calculated after being computed
@dataclass
class Calculator:
    """
    A calculator is for calculating the values of ANP attributes (width, height, border-width, etc.)
    It only needs the ANP value, a percentage value and an auto value. If latter are None then they will raise an Exception
    """

    default_perc_val: float | None

    def __call__(
        self,
        value: AutoNP,
        auto_val: float | None = None,
        perc_val: float | None = None,
    ) -> float:
        """
        This helper function takes a value, an auto_val
        and the perc_value and returns a Number
        if the value is Auto then the auto_value is returned
        if the value is a Number that is returned
        if the value is a Percentage the Percentage is multiplied with the perc_value
        """
        perc_val = make_default(perc_val, self.default_perc_val)
        if value is Auto:
            assert auto_val is not None, "This attribute cannot be Auto"
            return auto_val
        elif isinstance(value, Number):
            return not_neg(value)
        elif isinstance(value, Percentage):
            assert perc_val is not None, f"This attribute cannot be a percentage"
            return not_neg(perc_val * value)
        raise TypeError

    def _multi(self, values: Iterable[AutoNP], *args) -> tuple[float, ...]:
        return tuple(self(val, *args) for val in values)

    # only relevant for typing
    def multi2(self, values: tuple[AutoNP, AutoNP], *args) -> tuple[float, float]:
        return self._multi(values, *args)  # type: ignore

    def multi4(self, values: AutoNP4Tuple, *args) -> Float4Tuple:
        return self._multi(values, *args)  # type: ignore


################## Value Correction #########################

Var = TypeVar("Var")


def make_default(value: Var | None, default: Var) -> Var:
    """
    If the `value` is None this returns `default` else it returns `value`
    """
    return default if value is None else value


def in_bounds(x: float, lower: float, upper: float) -> float:
    x = max(lower, x)
    x = min(upper, x)
    return x


not_neg = lambda x: max(0, x)


def get_tag(elem: _XMLElement) -> str:
    return (
        elem.tag.removeprefix("{http://www.w3.org/1999/xhtml}")
        if isinstance(elem.tag, str)
        else "comment"
    )


def ensure_suffix(s: str, suf: str) -> str:  # Could move to Box.py
    return s if s.endswith(suf) else s + suf


def all_equal(l):
    if len(l) < 2:
        return True
    x, *rest = l
    return all(x == r for r in rest)


##################### Itemgetters ##########################

directions = ("top", "bottom", "left", "right")

# Rect
side_keys = tuple(f"mid{k}" for k in directions)
# style
pad_keys = tuple(f"padding-{k}" for k in directions)
marg_keys = tuple(f"margin-{k}" for k in directions)
bw_keys = tuple(f"border-{k}-width" for k in directions)
bc_keys = tuple(f"border-{k}-color" for k in directions)
inset_keys = directions

# https://stackoverflow.com/questions/54785148/destructuring-dicts-and-objects-in-python
Input_T = TypeVar("Input_T", covariant=True)
Output_T = TypeVar("Output_T", covariant=True)


class GeneralGetter(Protocol[Input_T, Output_T]):
    def __call__(input: Input_T) -> Output_T:
        ...


class Getter(Protocol[Output_T]):
    def __call__(self, input: style_computed) -> Output_T:
        ...


class T4Getter(Protocol[Output_T]):
    def __call__(
        self, input: style_computed
    ) -> tuple[Output_T, Output_T, Output_T, Output_T]:
        ...


FGetter = GeneralGetter[Rect, Float4Tuple]
rs_getter: FGetter = attrgetter(*side_keys)  # type: ignore[assignment]

ANPGetter = T4Getter[AutoNP]
inset_getter: ANPGetter = itemgetter(*inset_keys)  # type: ignore[assignment]
pad_getter: ANPGetter = itemgetter(*pad_keys)  # type: ignore[assignment]
bw_getter: ANPGetter = itemgetter(*bw_keys)  # type: ignore[assignment]
mrg_getter: ANPGetter = itemgetter(*marg_keys)  # type: ignore[assignment]

bc_getter: T4Getter[Color] = itemgetter(*bc_keys)  # type: ignore[assignment]

####################### I/O #################################


def fetch_src(src: str):
    # right now this is just a relative or absolute path to the cwd
    return readf(src)


def readf(path: str):
    with open(path, "r", encoding="utf-8") as file:
        return file.read()


@contextmanager
def clog_error():
    with open("error.log", "a", encoding="utf-8") as file:
        with redirect_stdout(file):
            yield


def log_error(*messages, **kwargs):
    with clog_error():
        print(*messages, **kwargs)


@cache
def print_once(t: str):
    print(t)


def print_tree(tree, indent=0):
    if not hasattr(tree, "children") or not tree.children:
        return print(" " * indent, f"<{tree.tag}/>")
    print(" " * indent, f"<{tree.tag}>")
    with suppress(AttributeError):
        for child in tree.children:
            print_tree(child, indent + 2)
    print(" " * indent, f"</{tree.tag}>")


def print_parsed_tree(tree, indent=0, with_text=False):
    text = "with " + tree.text if with_text and tree.text else ""
    tag = get_tag(tree)
    if not tree:
        return print(" " * indent, f"<{tag}/>", text)
    print(" " * indent, f"<{tag}>", text)
    with suppress(AttributeError):
        for child in tree:
            print_parsed_tree(child, indent + 2)
    print(" " * indent, f"</{tag}>")


####################### Regexes ##################################
def compile(patterns: Iterable[str | re.Pattern]):
    return [re.compile(p) for p in patterns]


def get_groups(s: str, p: re.Pattern):
    if match := p.search(s):
        return [group for group in match.groups() if group and isinstance(group, str)]


def re_join(*args: str) -> str:
    return "|".join(re.escape(x) for x in args)


def replace_all(s: str, olds: list[str], new: str) -> str:
    pattern = re.compile(re_join(*olds))
    return pattern.sub(new, s)


# https://docs.python.org/3/library/re.html#simulating-scanf
int_re = r"[+-]?\d+"
dec_re = rf"(?:{int_re})?(?:\.\d+)?(?:e{int_re})?"
units_re = re_join(*all_units)

regexes: dict[str, re.Pattern] = {
    k: re.compile(x)
    for k, x in {
        "integer": int_re,
        "number": dec_re,
        "percentage": rf"{dec_re}\%",
        "dimension": rf"(?:{dec_re})(?:\w*)",  # TODO: Use actual units
    }.items()
}


def check_regex(name: str, to_check: str):
    """
    Checks if the given regex matches the given string and returns the match or None if it doesn't match
    KeyError if the regex specified doesn't exist
    """
    return regexes[name].fullmatch(to_check.strip())


for key, value in regexes.items():
    globals()[f"is_{key}"] = partial(check_regex, key)

########################## Test ####################################
def test():
    tests = {
        # https://developer.mozilla.org/en-US/docs/Web/CSS/integer#examples
        "integer": {
            "true": ["12", "+123", "-456", "0", "+0", "-0", "00"],
            "false": ["12.0", "12.", "+---12", "ten", "_5", r"\35", "\4E94", "3e4"],
        },
        # https://developer.mozilla.org/en-US/docs/Web/CSS/number#examples
        "number": {
            "true": [
                "12",
                "4.01",
                "-456.8",
                "0.0",
                "+0.0",
                "-0.0",
                ".60",
                "10e3",
                "-3.4e-2",
            ],
            "false": ["12.", "+-12.2", "12.1.1"],
        },
        # https://developer.mozilla.org/en-US/docs/Web/CSS/dimension
        "dimension": {
            "true": ["12px", "1rem", "1.2pt", "2200ms", "5s", "200hz"],
            "false": ["12 px", '12"px"'],  # ,"3sec"]
        },
    }
    glob = globals()
    for k, val in tests.items():
        func = glob["is_" + k]
        for true in val["true"]:
            assert func(true)
        for false in val["false"]:
            assert not func(false)


############################# Pygame related #############################

pg.init()


def add2Rect(rect: Rect, tuple_or_rect: Float4Tuple):
    x, y, w, h = tuple_or_rect
    return Rect(rect.x + x, rect.y + y, rect.w + w, rect.h + h)


def rect_lines(rect: Rect):
    """
    Makes bounding lines from the rect.
    First top then bottom, left, right
    The lines grow: line[0] <= line[1]
    """
    return (
        (rect.topleft, rect.topright),
        (rect.bottomleft, rect.bottomright),
        (rect.topleft, rect.bottomleft),
        (rect.topright, rect.bottomright),
    )


def draw_text(
    surf: Surface, text: str, fontname: str | None, size: int, color, **kwargs
):
    font: Any = freetype.SysFont(fontname, size)  # type: ignore[arg-type]
    color = Color(color)
    dest: Rect = font.get_rect(str(text))
    for k, val in kwargs.items():
        with suppress(AttributeError):
            setattr(dest, k, val)
    font.render_to(surf, dest=dest, fgcolor=color)


class Dotted:
    def __init__(
        self,
        dim,
        color,
        dash_size: int = 10,
        dash_width: int = 2,
        start_pos: Dimension = (0, 0),
    ):
        self.dim = Vector2(dim)
        self.color = Color(color)
        self.dash_size = dash_size
        self.dash_width = dash_width
        self.start_pos = Vector2(start_pos)

    @classmethod
    def from_rect(cls, rect: Rect, **kwargs):
        return cls(rect.size, **kwargs, start_pos=rect.topleft)

    def draw_at(self, surf: Surface, pos):
        pos = Vector2(pos)
        vec = self.dim.normalize() * self.dash_size
        for i in range(int(self.dim.length() // self.dash_size // 2)):
            _pos = pos + vec * i * 2
            pg.draw.line(surf, self.color, _pos, _pos + vec, self.dash_width)

    def draw(self, surf: Surface):
        return self.draw_at(surf, self.start_pos)

    def draw_rect(self, surf: Surface):
        rect = Rect(*self.start_pos, *self.dim)
        for line in rect_lines(rect):
            pos = Vector2(line[0])
            dim = line[1] - pos
            Dotted(dim, self.color, self.dash_size, self.dash_width, pos).draw(surf)


def draw_lines(surf: Surface, points, *args, **kwargs):
    points = [Vector2(point) for point in points]
    dlines = [
        Dotted(points[i + 1] - points[i], *args, **kwargs, start_pos=points[i])  # type: ignore
        for i in range(len(points) - 1)
    ]
    for dline in dlines:
        dline.draw(surf)
