"""
Utilities for all kinds of needs (funcs, regex, etc...) 
"""

import logging
import re
from contextlib import contextmanager, redirect_stdout, suppress
from dataclasses import dataclass
from functools import cache, partial, reduce
from operator import attrgetter, itemgetter
from threading import Thread
from typing import Any, Callable, Coroutine, Generic, Iterable, Protocol, TypeVar

import pygame as pg
import pygame.freetype as freetype

from config import all_units, g
from own_types import (Auto, AutoNP, AutoNP4Tuple, Color, Dimension,
                       Float4Tuple, Number, Percentage, Rect, StyleComputed,
                       Surface, Vector2, _XMLElement)


def noop(*args, **kws):
    """A no operation function"""
    return None

@contextmanager
def no_ctx(*args, **kws):
    """An empty context manager"""
    yield


################## g Manipulations ##########################
def watch_file(file: str) -> str:
    """Add the file to the watched files"""
    return g["file_watcher"].add_file(file)


####################################################################

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


####################################################################

########################## Misc #########################
class StoppableThread(Thread):
    """ A general StoppableThread. It can be stopped with thread.stop()"""
    daemon = True
    def __init__(self, coro_make: Callable[[],Coroutine]):
        """ The coro_make is a Function that returns a Coroutine """
        Thread.__init__(self)
        self.coro = coro_make()
        self.running: bool = True

    def run(self):
        logging.debug("Started "+self.__class__.__name__)
        while self.running:
            self.coro.__next__()
        self.coro.close()
        logging.debug("Finished "+self.__class__.__name__)
    
    def stop(self):
        self.running = False
        return self
        

Var = TypeVar("Var")

# TODO: Add Typing with overloads and typing variables:
# Something like:
# (a: (x)->y, b: (y)->z) -> (x)->z
def compose(*funcs):
    def _compose(f, g):
        return lambda x : f(g(x))
              
    return reduce(_compose, funcs, lambda x : x)

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
        elem.tag.removeprefix("{http://www.w3.org/1999/xhtml}").lower()
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


def group_by_bool(
    l: Iterable[Var], key: Callable[[Var], bool]
) -> tuple[list[Var], list[Var]]:
    true = []
    false = []
    for x in l:
        if key(x):
            true.append(x)
        else:
            false.append(x)
    return true, false


def find(__iterable: Iterable[Var], key: Callable[[Var], bool]):
    for x in __iterable:
        if key(x):
            return x


####################################################################

#################### Itemgetters/setters ###########################

directions = ("top", "bottom", "left", "right")
corners = ("top-left", "top-right", "bottom-left", "bottom-right")

# Rect
side_keys = tuple(f"mid{k}" for k in directions)
# style
pad_keys = tuple(f"padding-{k}" for k in directions)
marg_keys = tuple(f"margin-{k}" for k in directions)
bs_keys = tuple(f"border-{k}-style" for k in directions)
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
    def __call__(self, input: StyleComputed) -> Output_T:
        ...


class T4Getter(Protocol[Output_T]):
    def __call__(
        self, input: StyleComputed
    ) -> tuple[Output_T, Output_T, Output_T, Output_T]:
        ...


_T = TypeVar("_T")


class itemsetter(Generic[_T]):
    def __init__(self, keys: tuple[str, ...]):
        self.keys = keys

    def __call__(self, map: Any, values: tuple[_T, ...]) -> None:
        for key, value in zip(self.keys, values):
            map[key] = value


FGetter = GeneralGetter[Rect, Float4Tuple]
rs_getter: FGetter = attrgetter(*side_keys)  # type: ignore[assignment]

ANPGetter = T4Getter[AutoNP]
inset_getter: ANPGetter = itemgetter(*inset_keys)  # type: ignore[assignment]
pad_getter: ANPGetter = itemgetter(*pad_keys)  # type: ignore[assignment]
bw_getter: ANPGetter = itemgetter(*bw_keys)  # type: ignore[assignment]
bw_setter = itemsetter[str](bw_keys)
mrg_getter: ANPGetter = itemgetter(*marg_keys)  # type: ignore[assignment]

bc_getter: T4Getter[Color] = itemgetter(*bc_keys)  # type: ignore[assignment]
bs_getter: T4Getter[str] = itemgetter(*bs_keys)  # type: ignore[assignment]

####################################################################

############################## I/O #################################


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
def print_once(*args):
    print(*args)


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


####################################################################

######################### Regexes ##################################
def compile(patterns: Iterable[str | re.Pattern]):
    return [re.compile(p) for p in patterns]


def get_groups(s: str, p: re.Pattern) -> list[str] | None:
    if (match := p.search(s)) and (groups := [g for g in match.groups() if g]):
        return groups
    return None


def re_join(*args: str) -> str:
    return "|".join(re.escape(x) for x in args)


def replace_all(s: str, olds: list[str], new: str) -> str:
    pattern = re.compile(re_join(*olds))
    return pattern.sub(new, s)


# https://docs.python.org/3/library/re.html#simulating-scanf
int_re = r"[+-]?\d+"
pos_int_re = r"+?\d+"
# dec_re = rf"(?:{int_re})?(?:\.\d+)?(?:e{int_re})?"
dec_re = r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?"
# pos_dec_re = rf"(?:{pos_int_re})?(?:\.\d+)?(?:e{int_re})?"
units_re = re_join(*all_units)

regexes: dict[str, re.Pattern] = {
    k: re.compile(x)
    for k, x in {
        "integer": int_re,
        "number": dec_re,
        "percentage": rf"{dec_re}\%",
        "dimension": rf"(?:{dec_re})(?:\w+)",  # TODO: Use actual units
    }.items()
}


IsFunc = Callable[[str], re.Match | None]
is_integer: IsFunc
is_number: IsFunc


def check_regex(name: str, to_check: str):
    """
    Checks if the given regex matches the given string and returns the match or None if it doesn't match
    KeyError if the regex specified doesn't exist
    """
    return regexes[name].fullmatch(to_check.strip())


for key, value in regexes.items():
    globals()[f"is_{key}"] = partial(check_regex, key)

####################################################################

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
