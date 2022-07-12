
################################################ types #################################################################
from dataclasses import dataclass
from numbers import Number
from typing import Literal, Mapping
from pygame import Vector2D

class ComputeError(Exception):
    pass

@dataclass
class Length:
    value: float

@dataclass
class Percentage:
    value: float

    def __mul__(self, other):
        return other * self.value * 0.01

def make_default(value, default):
    """ 
    If the value is None this returns the given default value
    Otherwise it returns the value
    """
    return default if value is None else value
class FontStyle:
    def __init__(self, value: Literal["normal", "italic", "oblique"], oblique_angle: float|None = None):
        assert value in ("normal", "italic", "oblique")
        self.value = value
        self.oblique_angle = float(make_default(oblique_angle, 14)) if value == "oblique" else None

    def __hash__(self):
        return hash(f"{self.value} {self.oblique_angle}")

style_input = Mapping[str, str]
computed_value = str | Number | FontStyle | Length | Percentage
style_computed = Mapping[str, computed_value]

Dimension = tuple[Number, Number] | Vector2D
NumTuple4 = tuple[Number, Number, Number, Number]


@dataclass
class StyleAttr:
    initial: str
    inherited: bool = True
