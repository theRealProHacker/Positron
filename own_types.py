from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Generator, Literal, Mapping, TypeVar, Union, Protocol
from xml.etree.ElementTree import Element as _XMLElement
from enum import Enum as _Enum, auto as enum_auto

import pygame as pg
from pygame.math import Vector2 as _Vector2
from pygame.surface import Surface
from pygame.font import Font
from pygame.rect import Rect
from pygame.event import Event

# Abstract Protocols
def Screen(Protocol):
    def blit(self, __surf: Surface):
        ...

############################ Some Classes ##############################

class Enum(_Enum):
    def __repr__(self):
        return f"{self.__class__.__name__}.{self.name}"


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

x,y = Vector2(0,0)

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

################## Sentinels ###################
class Sentinel(Enum):
    Auto = enum_auto()
    Normal = enum_auto()

# Type Aliases
AutoType = Literal[Sentinel.Auto]
NormalType = Literal[Sentinel.Normal]

Auto: AutoType = Sentinel.Auto
Normal: NormalType = Sentinel.Normal


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
