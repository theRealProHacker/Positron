"""
Handles everything revolving Selectors. 
Includes parsing (text->Selector) and matching
"""

from dataclasses import dataclass
from functools import cache, cached_property, reduce
import re
from typing import Callable, Iterable, Protocol, Union
from own_types import BugError, Element_P
from util import get_groups


########################## Specificity and Rules #############################
Spec = tuple[int, int, int]


def add_specs(t1: Spec, t2: Spec) -> Spec:
    """
    Cumulate two Specificities
    """
    id1, cls1, tag1 = t1
    id2, cls2, tag2 = t2
    return (id1 + id2, cls1 + cls2, tag1 + tag2)


sum_specs: Callable[[Iterable[Spec]], Spec] = lambda specs: reduce(add_specs, specs)

################################# Selectors #######################################
# https://www.w3.org/TR/selectors-3/

Selector = Union["SingleSelector", "CompositeSelector"]


class SingleSelector(Protocol):
    spec: Spec

    def __call__(self, elem: Element_P) -> bool:
        ...

    def __hash__(self) -> int:
        return super().__hash__()


@dataclass(frozen=True, slots=True)
class TagSelector:
    tag: str
    spec = 0, 0, 1
    __call__ = lambda self, elem: elem.tag == self.tag
    __str__ = lambda self: self.tag  # type: ignore[attr-defined]


@dataclass(frozen=True, slots=True)
class IdSelector:
    id: str
    spec = 1, 0, 0
    __call__ = lambda self, elem: elem.attrs.get("id") == self.id
    __str__ = lambda self: "#" + self.id  # type: ignore[attr-defined]


@dataclass(frozen=True, slots=True)
class ClassSelector:
    cls: str
    spec = 0, 1, 0
    __call__ = lambda self, elem: elem.attrs.get("class") == self.cls
    __str__ = lambda self: "." + self.cls  # type: ignore[attr-defined]


@dataclass(frozen=True, slots=True)
class HasAttrSelector:
    name: str
    spec = 0, 1, 0
    __call__ = lambda self, elem: self.name in elem.attrs
    __str__ = lambda self: f"[{self.name}]"  # type: ignore[attr-defined]


# the validator takes the soll value and the is value
def make_attr_selector(sign: str, validator):
    sign = re.escape(sign)
    regex = re.compile(
        rf'\[{s}(\w+){s}{sign}={s}"(\w+)"{s}\]|\[{s}(\w+){s}{sign}={s}(\w+){s}\]'
    )

    @dataclass(frozen=True, slots=True)
    class AttributeSelector:
        name: str
        value: str
        spec = 0, 1, 0

        def __call__(self, elem: Element_P):
            return (value := elem.attrs.get(self.name)) is not None and validator(
                self.value, value
            )

        def __str__(self):
            return f'[{self.name}{sign}="{self.value}"]'

    return regex, AttributeSelector


@dataclass(frozen=True, slots=True)
class AnySelector:
    spec = 0, 0, 0

    def __call__(self, elem):
        return True

    def __str__(self):
        return "*"


@dataclass(frozen=True, slots=True)
class NeverSelector:
    spec: Spec
    s: str

    def __call__(self, elem):
        return False

    def __str__(self):
        return self.s


################################## Composite Selectors ###############################
class CompositeSelector:
    selectors: tuple[Selector, ...]
    spec: cached_property[Spec]

    def __call__(self, elem: Element_P) -> bool:
        ...

    def __hash__(self) -> int:
        return super().__hash__()


joined_specs = lambda self: sum_specs(f.spec for f in self.selectors)


@dataclass(frozen=True, slots=True)
class AndSelector(CompositeSelector):
    selectors: tuple[Selector, ...]
    spec = cached_property(joined_specs)
    __call__ = lambda self, elem: all(sel(elem) for sel in self.selectors)
    __str__ = lambda self: "".join(str(s) for s in self.selectors)  # type: ignore[attr-defined]


@dataclass(frozen=True, slots=True)
class OrSelector(CompositeSelector):
    selectors: tuple[Selector, ...]
    spec = cached_property(joined_specs)
    __call__ = lambda self, elem: any(sel(elem) for sel in self.selectors)
    __str__ = lambda self: ", ".join(str(s) for s in self.selectors)  # type: ignore[attr-defined]


@dataclass(frozen=True, slots=True)
class DirectChildSelector(CompositeSelector):
    selectors: tuple[Selector, ...]
    spec = cached_property(joined_specs)

    def __call__(self, elem: Element_P):
        chain = [elem, *elem.iter_anc()]
        if len(chain) != len(self.selectors):
            return False
        return all(sel(elem) for parent, sel in zip(chain, self.selectors))

    __str__ = lambda self: " > ".join(str(s) for s in self.selectors)  # type: ignore[attr-defined]


@dataclass(frozen=True, slots=True)
class ChildSelector(CompositeSelector):
    selectors: tuple[Selector, Selector]
    spec = cached_property(joined_specs)

    def __call__(self, elem: Element_P):
        own_sel, p_sel = self.selectors
        if not own_sel(elem):
            return False
        return any(p_sel(p) for p in elem.iter_anc())

    __str__ = lambda self: " ".join(str(s) for s in self.selectors)  # type: ignore[attr-defined]


########################################## Parser #######################################################
s = r"\s*"
sngl_p = re.compile(
    r"((?:\*|(?:#\w+)|(?:\.\w+)|(?:\[\s*\w+\s*\])|(?:\[\s*\w+\s*[~|^$*]?=\s*\w+\s*\])|(?:\w+)))$"
)
rel_p = re.compile(r"\s*([>+~ ])\s*$")  # pretty simple

attr_sel_data = [
    ("", lambda soll, _is: soll == _is),
    ("~", lambda soll, _is: soll in _is.split()),
    ("|", lambda soll, _is: soll == _is or _is.startswith(soll + "-")),
    ("^", lambda soll, _is: _is.startswith(soll)),
    ("$", lambda soll, _is: _is.endswith(soll)),
    ("*", lambda soll, _is: soll in _is),
]
attr_patterns: list[tuple[re.Pattern, type[Selector]]] = [
    (re.compile(r"\[(\w+)\]"), HasAttrSelector),
    *(make_attr_selector(sign, validator) for sign, validator in attr_sel_data),
]


def matches(s: str, pattern: re.Pattern):
    """
    Takes a string and a pattern and returns the reststring and the capture
    """
    if not ((match := pattern.search(s)) and (length := len(match.group()))):
        return None
    if not (groups := [g for g in match.groups() if g]):
        return None
    return (s[:-length], groups[0])


class InvalidSelector(ValueError):
    pass


@cache
def parse_selector(s: str) -> Selector:
    s = start = s.strip()
    if not s:
        raise InvalidSelector("Empty selector")
    if "," in s:
        return OrSelector(tuple(parse_selector(x) for x in s.split(",")))
    else:
        singles: list[str] = []
        # do-while-loop
        while True:
            if match := matches(s, sngl_p):
                s, subsel = match
                singles.insert(0, subsel)
                if not s:  # recursive anker
                    return proc_singles(singles)
            elif match := matches(s, rel_p):
                s, rel = match
                if not s or not singles:
                    raise InvalidSelector(
                        f"Relative selectors are not padded by single selectors: ({rel},{start})"
                    )
                sngl_selector = proc_singles(singles)
                match rel:
                    case " ":
                        return ChildSelector((parse_selector(s), sngl_selector))
                    case ">":
                        return DirectChildSelector((parse_selector(s), sngl_selector))
                    case "+":
                        raise NotImplementedError("+ is not implemented yet")
                    case "~":
                        raise NotImplementedError("~ is not implemented yet")
                    case _:
                        raise BugError(f"Invalid relative selector ({rel})")
            else:
                raise InvalidSelector(f"Couldn't match '{s}'")


def proc_singles(groups: list[str]) -> Selector:
    """
    Merge several selectors into one
    """
    if len(groups) == 1:
        return proc_single(groups[0])
    return AndSelector(tuple(proc_single(s) for s in groups))


def proc_single(s: str) -> Selector:
    """
    Create a single selector from a string
    """
    if s == "*":
        return AnySelector()
    elif s[0] == "#":
        return IdSelector(s[1:])
    elif s[0] == ".":
        return ClassSelector(s[1:])
    elif s[0] == "[":
        for pattern, selector in attr_patterns:
            if (groups := get_groups(s, pattern)) is not None:
                return selector(*groups)
        raise BugError(f"Invalid attribute selector: {s}")
    elif s[0] == ":":  # pseudoclass
        raise RuntimeError("Pseudoclasses are not supported yet")
    else:
        return TagSelector(s)