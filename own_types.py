
################################################ types #################################################################
from dataclasses import dataclass
from typing import Any, Callable, Literal, Mapping, TypeVar
import pygame as pg
from pygame import Vector2
from numbers import Number
from xml.etree.ElementTree import Element as _XMLElement

############################ Some Classes ##############################
@dataclass
class Percentage:
    value: Number
    def __mul__(self, other)->Number:
        return other * self.value * 0.01

class FontStyle:
    def __init__(self, value: Literal["normal", "italic", "oblique"], oblique_angle: Number|None = None):
        assert value in ("normal", "italic", "oblique")
        self.value = value
        self.oblique_angle = None if value != "oblique" else \
            14 if oblique_angle is None else oblique_angle

    def __hash__(self):
        return hash(f"{self.value} {self.oblique_angle}")

class Color(pg.Color):
    def __setattr__(self, __name: str, __value: Any) -> None:
        raise TypeError("Color can't be mutated")
    def __hash__(self):
        return hash(int(self))

################## Sentinels ###############

from enum import Enum, auto as _enum_auto
class Sentinel(Enum):
    Auto = _enum_auto()
    Normal = _enum_auto()

Auto = Sentinel.Auto
Normal = Sentinel.Normal

# Type Aliases
Index = int|slice
style_input = Mapping[str, str]
computed_value = Number | Percentage | Sentinel| FontStyle | Color
style_computed = Mapping[str, computed_value]

Dimension = tuple[Number, Number]|Vector2 # type: ignore[misc] #  mypy bug
NumTuple4 = tuple[Number, Number, Number, Number]


###################### Rare classes #################################

class ComputeError(Exception): # TODO: add this to util when moving computation there
    pass

@dataclass
class StyleAttr:
    initial: str
    isinherited: bool = True

if __name__ == '__main__':
    # test sentinels
    print(Auto)
    assert Auto.name.lower() == "auto"
    # test Acceptors