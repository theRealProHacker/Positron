"""
A single source of thruth for types that are used in the other modules.
Instead of importing Rects or Vectors from pygame, import them from here. 
"""
from __future__ import annotations
from contextlib import suppress
from dataclasses import dataclass
from enum import Enum as _Enum
from functools import reduce
from operator import or_

# fmt: off
from typing import (Any, Generator, Generic, Hashable, Iterable, Literal,
                    Mapping, Protocol, Sequence, TypeVar, Union)
# fmt: on
from weakref import WeakValueDictionary

import pygame as pg
from frozendict import FrozenOrderedDict as _frozendict
from pygame.event import Event
from pygame.font import Font
from pygame.math import Vector2 as _Vector2
from pygame.rect import Rect as _Rect
from pygame.surface import Surface


class BugError(AssertionError):
    """A type of error that should never occur. If it occurs, something needs to be fixed. Please report any BugErrors found."""


# Aliases
##########################################################################

Number = int, float  # for isinstance(x, Number)

# a size, vector, or position
Coordinate = Union[tuple[float, float], "Vector2"]
Index = int | slice

DisplayType = Literal["inline", "block", "none"]
StrSent = Union[str, "Sentinel"]
LengthPerc = Union["Length", "Percentage"]
AutoLP = Union["AutoType", "Length", "Percentage"]
AutoLP4Tuple = tuple[AutoLP, AutoLP, AutoLP, AutoLP]
Float4Tuple = tuple[float, float, float, float]
Str4Tuple = tuple[str, str, str, str]
Radii = tuple[
    tuple[int, int], ...
]  # actually we know that these are definitely exactly 4, but we don't care

K_T = TypeVar("K_T", bound=Hashable)
V_T = TypeVar("V_T")
CO_T = TypeVar("CO_T", covariant=True)

LOADPAGE = pg.event.custom_type()


def loadpage_event(**kwargs):
    return Event(LOADPAGE, **kwargs)


############################ Some Classes ##############################
class Drawable(Protocol):
    def draw(self, surf: Surface, pos: Coordinate):
        pass


class Leaf_P(Protocol):
    parent: Element_P


class Element_P(Protocol):
    """
    A Protocol that just represents an Element
    """

    tag: str
    attrs: dict[str, Any]
    parent: Element_P | None
    children: Sequence[Element_P | Leaf_P]

    def iter_anc(self) -> Iterable[Element_P]:
        ...


class Enum(_Enum):
    def __repr__(self):
        return f"{self.__class__.__name__}.{self.name}"


class frozendict(_frozendict):
    def __ror__(self, other):
        return dict(self) | dict(other)

    def items(self):
        return [tuple(item) for item in super().items()]


class ReadChain(Mapping[K_T, V_T]):
    """A Read-Only ChainMap"""

    def __init__(self, *maps: Mapping[K_T, V_T]):
        self.maps = maps  # immutable maps

    def __getitem__(self, key: K_T):
        for mapping in self.maps:
            with suppress(KeyError):
                return mapping[key]  # can't use 'key in mapping' with defaultdict
        raise KeyError(key)

    def dict(self) -> dict[K_T, V_T]:
        return reduce(or_, reversed(self.maps), {})

    def __len__(self) -> int:
        return len(self.dict())

    def __iter__(self):
        return iter(self.dict())

    def __or__(self, other: Mapping[K_T, V_T]):
        return self.dict() | other

    def __ror__(self, other: Mapping[K_T, V_T]):
        return self.dict() | other

    def __contains__(self, key):
        return any(key in m for m in self.maps)

    def __bool__(self):
        return any(self.maps)

    def __repr__(self):
        return f'{self.__class__.__name__}({", ".join(map(repr, self.maps))})'

    def copy(self):
        return self.__class__(*self.maps)

    __copy__ = copy

    def new_child(self, m=None, **kwargs):
        """
        New ReadChain with a new map followed by all previous maps.
        If no map is provided, an empty dict is used.
        Keyword arguments update the map or new empty dict.
        """
        if m is None:
            m = kwargs
        elif kwargs:
            m.update(kwargs)
        return self.__class__(m, *self.maps)

    @property
    def parents(self):
        "New ReadChain from maps[1:]."
        return self.__class__(*self.maps[1:])


class Vector2(_Vector2):
    def __iter__(self) -> Generator[float, None, None]:
        yield self.x
        yield self.y

    def __add__(self, other: Coordinate | _Vector2) -> "Vector2":
        other: Vector2 = Vector2(other)
        return Vector2(self.x + other.x, self.y + other.y)

    def __sub__(self, other: Coordinate | _Vector2) -> "Vector2":
        other: Vector2 = Vector2(other)
        return Vector2(self.x - other.x, self.y - other.y)

    def __mul__(self, other: float) -> "Vector2":  # type: ignore [override]
        return Vector2(self.x * other, self.y * other)


class Rect(_Rect):
    @property
    def corners(self):
        """clock-wise"""
        return (
            self.topleft,
            self.topright,
            self.bottomright,
            self.bottomleft,
        )

    @property
    def sides(self):
        return (
            (self.topleft, self.topright),
            (self.bottomleft, self.bottomright),
            (self.topleft, self.bottomleft),
            (self.topright, self.bottomright),
        )

    @staticmethod
    def from_span(point1: Coordinate, point2: Coordinate):
        """
        Rect from two points.
        """
        x1, y1 = point1
        x2, y2 = point2
        rect = Rect((x1, y1), (x2 - x1, y2 - y1))
        rect.normalize()
        return rect


CSSDimension_T = TypeVar("CSSDimension_T", bound="CSSDimension")


@dataclass(frozen=True)
class CSSDimension:
    value: float

    def __add__(self: CSSDimension_T, other: CSSDimension_T) -> CSSDimension_T:
        if not isinstance(other, self.__class__):
            raise ValueError
        return self.__class__(self.value + float(other))

    def __sub__(self: CSSDimension_T, other: CSSDimension_T) -> CSSDimension_T:
        if not isinstance(other, self.__class__):
            raise ValueError
        return self.__class__(self.value - float(other))

    def __mul__(self: CSSDimension_T, other: float) -> CSSDimension_T:
        if not isinstance(other, Number):
            if self.value == 0:
                return self.__class__(0)
            raise ValueError
        return self.__class__(self.value * other)

    def __rmul__(self: CSSDimension_T, other: float) -> CSSDimension_T:
        if not isinstance(other, Number):
            if self.value == 0:
                return self.__class__(0)
            raise ValueError
        return self.__class__(self.value * other)

    def __div__(self: CSSDimension_T, other: float) -> CSSDimension_T:
        if not isinstance(other, Number):
            raise ValueError
        return self.__class__(self.value / other)

    def __int__(self):
        return int(self.value)

    def __float__(self):
        return self.value

    def __repr__(self):
        return f"{self.__class__.__name__}({self.value})"


@dataclass(frozen=True, repr=False)
class Percentage(CSSDimension):
    value: float

    def resolve(self, num: float):
        """
        Resolves the Percentage with the given number
        The number should be equivalent to 100%
        """
        if not isinstance(num, Number):
            raise ValueError
        return self.value * num * 0.01


@dataclass(frozen=True, repr=False)
class Length(CSSDimension):
    value: float


@dataclass(frozen=True, repr=False)
class Angle(CSSDimension):
    value: float


@dataclass(frozen=True, repr=False)
class Time(CSSDimension):
    value: float


@dataclass(frozen=True)
class Resolution(CSSDimension):
    value: float


@dataclass(frozen=True)
class FontStyle:
    value: Literal["normal", "italic", "oblique"]
    angle: float

    def __init__(
        self, value: Literal["normal", "italic", "oblique"], angle: str | None = None
    ):
        assert value in ("normal", "italic", "oblique")
        object.__setattr__(self, "value", value)
        object.__setattr__(self, "angle", 14 if angle is None else float(angle))


class Color(pg.Color):
    def __hash__(self):
        return hash(int(self))

    def __repr__(self):
        return f"Color{super().__repr__()}"


class CompStr(str):
    def __repr__(self) -> str:
        return f"CompStr({self})"


################################################

################## Sentinels ###################
class Sentinel(Enum):
    Auto = "auto"
    Normal = "normal"


# Type Aliases
AutoType = Literal[Sentinel.Auto]
NormalType = Literal[Sentinel.Normal]

Auto: AutoType = Sentinel.Auto
Normal: NormalType = Sentinel.Normal

#################################################

############################# WeakRefCache ###############################
# used for weak referencing strings. TODO: Check whether that actually makes sense
redirect: dict[type, type] = {str: type("weakstr", (str,), {})}


class Cache(
    Generic[K_T]
):  # The Cache is a set like structure but it uses a dict underneath
    def __init__(self, l: Iterable[K_T] = []):
        self.cache = WeakValueDictionary[int, K_T]()
        for val in l:
            self.add(val)

    def add(self, val: K_T) -> K_T:
        if (new_type := redirect.get(type(val))) is not None:
            val = new_type(val)
        key = hash(val)
        if key not in self.cache:
            self.cache[key] = val
        return self.cache[key]

    def __bool__(self):
        return bool(self.cache)

    def __len__(self):
        return len(self.cache)

    def __repr__(self):
        return repr(set(self.cache.values()))

    def __contains__(self, value: K_T) -> bool:
        return hash(value) in self.cache

    def __iter__(self):
        return self.cache.values()


class FrozenDCache(Cache[frozendict]):
    def add(self, d: dict) -> frozendict:
        frz = frozendict(d)
        return super().add(frz)


######################### Copied from _typeshed ############################

OpenTextModeUpdating = Literal[
    "r+",
    "+r",
    "rt+",
    "r+t",
    "+rt",
    "tr+",
    "t+r",
    "+tr",
    "w+",
    "+w",
    "wt+",
    "w+t",
    "+wt",
    "tw+",
    "t+w",
    "+tw",
    "a+",
    "+a",
    "at+",
    "a+t",
    "+at",
    "ta+",
    "t+a",
    "+ta",
    "x+",
    "+x",
    "xt+",
    "x+t",
    "+xt",
    "tx+",
    "t+x",
    "+tx",
]
OpenTextModeWriting = Literal["w", "wt", "tw", "a", "at", "ta", "x", "xt", "tx"]
OpenTextModeReading = Literal[
    "r", "rt", "tr", "U", "rU", "Ur", "rtU", "rUt", "Urt", "trU", "tUr", "Utr"
]
OpenTextMode = Union[OpenTextModeUpdating, OpenTextModeWriting, OpenTextModeReading]
OpenBinaryModeUpdating = Literal[
    "rb+",
    "r+b",
    "+rb",
    "br+",
    "b+r",
    "+br",
    "wb+",
    "w+b",
    "+wb",
    "bw+",
    "b+w",
    "+bw",
    "ab+",
    "a+b",
    "+ab",
    "ba+",
    "b+a",
    "+ba",
    "xb+",
    "x+b",
    "+xb",
    "bx+",
    "b+x",
    "+bx",
]
OpenBinaryModeWriting = Literal["wb", "bw", "ab", "ba", "xb", "bx"]
OpenBinaryModeReading = Literal["rb", "br", "rbU", "rUb", "Urb", "brU", "bUr", "Ubr"]
OpenBinaryMode = Union[
    OpenBinaryModeUpdating, OpenBinaryModeReading, OpenBinaryModeWriting
]

OpenModeReading = Union[OpenTextModeReading, OpenBinaryModeReading]
OpenModeWriting = Union[OpenTextModeWriting, OpenBinaryModeWriting]
OpenModeUpdating = Union[OpenTextModeUpdating, OpenBinaryModeUpdating]

OpenMode = Union[OpenTextMode, OpenBinaryMode]
