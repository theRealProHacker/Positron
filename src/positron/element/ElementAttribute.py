"""
An Element Attribute is an attribute that is set on an Element.
For example the NumberAttribute. It allows to get and set an attribute as a number but always sets it as a string in the actual attrs. 
"""
from __future__ import annotations

# from keyword import iskeyword
from contextlib import suppress
from dataclasses import dataclass, field
from typing import Any, Iterable, Protocol

import positron.types as types
import positron.util as util
from positron.config import input_type_check_res

# def set_attrs(elem: own_types.Element_P, attrs: Iterable[Attribute]):
#     for attr in attrs:
#         name = f"{attr.attr}_" if iskeyword(attr.attr) else attr.attr
#         setattr(elem, name, attr)


@dataclass
class Opposite:
    attr: str

    def __get__(self, obj, type=None) -> bool:
        return not getattr(obj, self.attr)


@dataclass
class SameAs:
    attr: str

    def __get__(self, obj, type=None) -> bool:
        return getattr(obj, self.attr)


class Attribute(Protocol[types.V_T]):
    """
    The base class for all attributes.
    Automatically returns the default if it cannot be found
    when getting the attribute from the elements attrs
    """

    attr: str
    default: types.V_T

    def get_default(self, elem):
        return self.default

    def _get(self, elem: types.Element_P) -> types.V_T:
        ...

    def __get__(self, elem: types.Element_P, type=None) -> types.V_T:
        if self.attr not in elem.attrs:
            return self.get_default(elem)
        return self._get(elem)

    def __set__(self, elem: types.Element_P, value: types.V_T):
        ...

    def __delete__(self, elem: types.Element_P):
        del elem.attrs[self.attr]


@dataclass
class GeneralAttribute(Attribute[str]):
    """
    Just passes the dict value up.
    """

    attr: str
    default: str = ""

    def _get(self, elem):
        return elem.attrs[self.attr]

    def __set__(self, elem, value):
        elem.attrs[self.attr] = value


@dataclass
class RangeAttribute(Attribute[str]):
    """
    Only allows the attribute to be in a specific range.
    """

    attr: str
    range: set[str] = frozenset()
    default: str = ""

    def __post_init__(self):
        self.range.add(self.default)

    def correct(self, x: Any):
        return x if x in self.range else self.default

    def _get(self, elem):
        return self.correct(elem.attrs[self.attr])

    def __set__(self, elem, value):
        elem.attrs[self.attr] = self.correct(value)


@dataclass
class NumberAttribute(Attribute[float]):
    attr: str
    default: float = 0

    def _get(self, elem: types.Element_P):
        with suppress(ValueError):
            return float(elem.attrs[self.attr])
        return self.default

    def __set__(self, elem: types.Element_P, value: float):
        elem.attrs[self.attr] = util.nice_number(value)


@dataclass
class BooleanAttribute(Attribute[bool]):
    """
    Get the boolean of an attribute.
    Example:
    ```py
    attr=BooleanAttribute("disabled")
    ```
    ```html
    <input> -> false
    <input disabled> -> true
    <input disabled="something"> -> true
    <input disabled="false"> -> false
    ```
    """

    attr: str
    default: bool = False

    def _get(self, elem):
        return elem.attrs[self.attr] != "false"

    def __set__(self, elem, value):
        elem.attrs[self.attr] == str(value).lower()


@dataclass
class ClassListAttribute(Attribute[Iterable[str]]):
    attr: str = "class"
    default: set[str] = field(default_factory=set)

    def _get(self, elem):
        return set(elem.attrs[self.attr].split())

    def __set__(self, elem, value):
        elem.attrs[self.attr] = " ".join(value)


@dataclass
class DataAttribute(Attribute[dict[str, str]]):
    attr: str = "data"  # this isn't actually True
    default: dict[str, str] = field(default_factory=dict)

    def _get(self, elem):
        return {k[5:]: v for k, v in elem.attrs.items() if k.startswith("data-")}

    def __set__(self, elem, value: dict[str, str]):
        for k, v in value.items():
            elem.attrs[f"data-{k}"] = v


# # Very specialized Attributes
# @dataclass
# class InputTypeAttribute(RangeAttribute):
#     attr: str = "type"
#     default: str = "text"
#     # TODO: think about what needs to happen if the elements type changes


@dataclass
class InputValueAttribute(Attribute[str | float]):
    attr: str = "value"

    def get_default(self, elem):
        if elem.type == "number":
            return 0
        elif elem.type in input_type_check_res:
            return ""
        elif elem.type in ("checkbox", "radio"):
            return "on"
        else:
            raise NotImplementedError

    def _get(self, elem):
        if elem.type == "number":
            try:
                return float(elem.attrs[self.attr])
            except ValueError:
                return self.get_default(elem)
        else:
            return elem.attrs[self.attr]

    def __set__(self, elem, value: str | float):
        elem.attrs[self.attr] = (
            util.nice_number(value) if isinstance(value, types.Number) else value
        )


__all__ = [
    "BooleanAttribute",
    "ClassListAttribute",
    "DataAttribute",
    "GeneralAttribute",
    "InputValueAttribute",
    "NumberAttribute",
    "Opposite",
    "RangeAttribute",
    "SameAs",
]
