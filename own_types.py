from __future__ import annotations
from dataclasses import dataclass
from functools import reduce
from typing import Any, Generator, Iterator, Literal, Mapping, TypeVar, Union, Protocol
from xml.etree.ElementTree import Element as _XMLElement
from enum import Enum as _Enum, auto as enum_auto
from operator import or_

import pygame as pg
from pygame.math import Vector2 as _Vector2
from pygame.surface import Surface
from pygame.font import Font
from pygame.rect import Rect
from pygame.event import Event

class BugError(RuntimeError):
    """ A type of error that should never occur. If it occurs it needs to be fixed."""

# Abstract Protocols
def Screen(Protocol):
    def blit(self, __surf: Surface):
        ...

K_T = TypeVar("K_T")
V_T = TypeVar("V_T")
############################ Some Classes ##############################

class Enum(_Enum):
    def __repr__(self):
        return f"{self.__class__.__name__}.{self.name}"


class ReadChain(Mapping[K_T,V_T]):
    """ A Read-Only ChainMap"""
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

@dataclass(frozen=True)
class Percentage:
    value: float
    def __mul__(self, other: float)->float:
        return other * self.value * 0.01
    def __rmul__(self, other: float)->float:
        return other * self.value * 0.01

class FontStyle:
    value: Literal["normal", "italic", "oblique"]
    angle: float
    def __init__(self, value: Literal["normal", "italic", "oblique"], angle: str|None = None):
        assert value in ("normal", "italic", "oblique")
        self.value = value
        self.angle = 14 if angle is None else float(angle)

    def __hash__(self):
        return hash(f"{self.value}@{self.angle}")

class Color(pg.Color):
    def __setattr__(self, __name: str, __value: Any) -> None:
        raise TypeError("Color can't be mutated")
    def __hash__(self):
        return hash(int(self))

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

Index = int|slice
style_input = dict[str, str]
computed_value = float | Percentage | Sentinel| FontStyle | Color | str
style_computed = Mapping[str, computed_value]

Number = int, float

NumPerc = float|Percentage
AutoNP = float|Percentage|AutoType
AutoNP4Tuple = tuple[AutoNP, AutoNP, AutoNP, AutoNP]
SNP = Sentinel|float|Percentage
SNP_T = TypeVar("SNP_T",bound = SNP, covariant=True)

SNP4Tuple = tuple[SNP, SNP, SNP, SNP]
Float4Tuple = tuple[float, float, float, float]

if __name__ == '__main__':
    # test sentinels
    print(Auto)
    assert Auto.name.lower() == "auto"
    # test Acceptors
