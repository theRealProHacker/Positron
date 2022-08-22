from __future__ import annotations
from dataclasses import dataclass
from functools import reduce
from typing import Any, Generator, Literal, Mapping, TypeVar, Union, TypeVar, Hashable, Protocol, Generic, Iterable
from xml.etree.ElementTree import Element as _XMLElement
from enum import Enum as _Enum, auto as enum_auto
from operator import or_
from weakref import WeakValueDictionary

import pygame as pg
from pygame.math import Vector2 as _Vector2
from pygame.surface import Surface
from pygame.rect import Rect as _Rect
from pygame.font import Font
from pygame.event import Event
from frozendict import FrozenOrderedDict as _frozendict

class BugError(AssertionError):
    """ A type of error that should never occur. If it occurs it needs to be fixed."""

# Abstract Protocols
class Screen(Protocol):
    def blit(self, __surf: Surface):
        ...

K_T = TypeVar("K_T", bound=Hashable)
V_T = TypeVar("V_T")
############################ Some Classes ##############################

class Enum(_Enum):
    def __repr__(self):
        return f"{self.__class__.__name__}.{self.name}"


class frozendict(_frozendict):
    def __ror__(self, other):
        return dict(self)|dict(other)
    
    def items(self):
        return [tuple(item) for item in super().items()]


class ReadChain(Mapping[K_T,V_T]):
    """ A Read-Only ChainMap """
    # partially copied from the original ChainMap
    def __init__(self, *maps: Mapping[K_T,V_T]):
        self.maps = maps # immutable maps

    def __getitem__(self, key: K_T):
        for mapping in self.maps:
            try:
                return mapping[key]     # can't use 'key in mapping' with defaultdict
            except KeyError:
                pass
        raise KeyError(key)

    def dict(self)->dict[K_T,V_T]:
        return reduce(or_, reversed(self.maps), {})

    def __len__(self) -> int:
        return len(self.dict())
    def __iter__(self):
        return iter(self.dict())
    def __or__(self, other: Mapping[K_T,V_T]):
        return self.dict() | other
    def __ror__(self, other: Mapping[K_T,V_T]):
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
        '''New ReadChain with a new map followed by all previous maps.
        If no map is provided, an empty dict is used.
        Keyword arguments update the map or new empty dict.
        '''
        if m is None:
            m = kwargs
        elif kwargs:
            m.update(kwargs)
        return self.__class__(m, *self.maps)

    @property
    def parents(self):
        'New ReadChain from maps[1:].'
        return self.__class__(*self.maps[1:])

Dimension = Union[tuple[float, float],'Vector2']

class Vector2(_Vector2):
    def __iter__(self)->Generator[float, None, None]:
        yield self.x
        yield self.y

    def __add__(self, other: Dimension|_Vector2)->'Vector2':
        other: Vector2 = Vector2(other)
        return Vector2(
            self.x + other.x,
            self.y + other.y
        )
    
    def __sub__(self, other: Dimension|_Vector2)->'Vector2':
        other: Vector2 = Vector2(other)
        return Vector2(
            self.x - other.x,
            self.y - other.y
        )

    def __mul__(self, other: float)->'Vector2': # type: ignore [override]
        return Vector2(
            self.x*other,
            self.y*other
        )

class Rect(_Rect):
    @property
    def corners(self):
        return (
            self.topleft,
            self.topright,
            self.bottomleft,
            self.bottomright
        )

@dataclass(frozen=True)
class Percentage:
    value: float
    def __mul__(self, other: float)->float:
        return other * self.value * 0.01
    def __rmul__(self, other: float)->float:
        return other * self.value * 0.01
    def __repr__(self):
        return str(self.value).removesuffix(".0")+"%"

@dataclass(frozen=True)
class FontStyle:
    value: Literal["normal", "italic", "oblique"]
    angle: float
    def __init__(self, value: Literal["normal", "italic", "oblique"], angle: str|None = None):
        assert value in ("normal", "italic", "oblique")
        object.__setattr__(self, "value", value)
        object.__setattr__(self, "angle", 14 if angle is None else float(angle))


class Color(pg.Color):
    def __setattr__(self, __name: str, __value: Any) -> None:
        raise TypeError("Color can't be mutated")
    def __hash__(self):
        return hash(int(self))

class Length(float):
    def __repr__(self):
        return f"Length({super().__repr__()})"

################################################

################## Sentinels ###################
class Sentinel(Enum):
    Auto = enum_auto()
    Normal = enum_auto()

# Type Aliases
AutoType = Literal[Sentinel.Auto]
NormalType = Literal[Sentinel.Normal]

Auto: AutoType = Sentinel.Auto
Normal: NormalType = Sentinel.Normal

#################################################

############################# WeakRefCache ###############################


class weakstr(str):
    pass

redirect: dict[type,type] = {
    str: weakstr
}


class Cache(Generic[K_T]): # The Cache is a set like structure but it uses a dict underneath
    def __init__(self, l: Iterable[K_T] = []):
        self.cache = WeakValueDictionary[int,K_T]()
        for val in l:
            self.add(val)
    def add(self, val: K_T)->K_T:
        if (new_type:= redirect.get(type(val))) is not None:
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
##########################################################################


Index = int|slice
StyleInput = dict[str, str]
CompValue = Any # | float | Percentage | Sentinel| FontStyle | Color | str
StyleComputed = Mapping[str, CompValue]

Number = int, float

DisplayType = Literal['inline','block','none']
NumPerc = float|Percentage
AutoNP = float|Percentage|AutoType
AutoNP4Tuple = tuple[AutoNP, AutoNP, AutoNP, AutoNP]
SNP = Sentinel|float|Percentage
SNP_T = TypeVar("SNP_T",bound = SNP, covariant=True)

SNP4Tuple = tuple[SNP, SNP, SNP, SNP]
Float4Tuple = tuple[float, float, float, float]
