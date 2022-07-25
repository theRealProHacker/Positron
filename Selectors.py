import re
from contextlib import suppress
from typing import Any, Callable, Iterable, Iterator, Protocol

from own_types import Enum, enum_auto

############################## Selectors #################################################
# A Selector is a function that gets an Element and returns whether it matches that selector

class Element(Protocol): 
    tag: str
    attrs: dict[str, Any]

    def iter_parents(self)->Iterator['Element']:
        ...

Selector = Callable[[Element], bool]

def tag_selector(tag: str)->Selector:
    def inner(elem: Element):
        return elem.tag == tag
    return inner

def id_selector(id_: str)->Selector:
    def inner(elem: Element):
        return elem.attrs.get("id") == id_
    return inner

def class_selector(cls: str)->Selector:
    def inner(elem: Element):
        return elem.attrs.get("class") == cls
    return inner

def any_selector(elem: Element):
    return True

# Composite selectors
def and_selector(selectors: Iterable[Selector]):
    def inner(elem: Element):
        return all(f(elem) for f in selectors)
    return inner

def direct_child_selector(selectors: tuple[Selector, Selector]):
    assert len(selectors) > 1, "Takes at least two selectors" # Right now it only takes two selectors
    def inner(elem: Element):
        try:
            parent = elem.iter_parents()
            return all(f(next(parent)) for f in selectors)
        except StopIteration:
            return False
    return inner

def any_child_selector(selectors: tuple[Selector, Selector]):
    assert len(selectors) == 2, "Takes two selectors"
    def inner(elem: Element):
        own_sel, p_sel = selectors
        if not own_sel(elem): return False
        return any(p_sel(p) for p in elem.iter_parents())
    return inner



########################################## Parser #######################################################

# we parse from behind which will make most things easier

# has to start with the tag, then a single id, then any number of classes or *
sngl_p = re.compile(r"(\w*)?(\#\w*)?(\.\w*)*$|\*$")
rel_p = re.compile(r"\s*(?:(>)|( ))\s*$")

class RT(Enum):
    Single = enum_auto
    Rel = enum_auto

ResultItem = tuple[RT, list[str]]
ResultType = list[ResultItem]
class Parser:
    def __repr__(self):
        return f"{self.__class__.__name__}({self.s})"

    def __init__(self, s: str):
        self.s = s.strip()
        self.result: ResultType = []

    def run(self):
        start = self.s
        try:
            self.rule()
            assert not self.s # nothing should be left of the input
            return process(self.result)
        except Exception:
            print(f"Couldn't parse {start}") #TODO: make debug
            raise ValueError(f"Couldn't parse {start}")

    def rule(self):
        r"""
        single_rule = #id | .class | tag
        _rel_rule = ' ', >
        rel_rule = \s*_rel_rule\s*
        rule = single_rule | [rule][rel_rule][single_rule]
        """
        self.single_rule()
        with suppress(AssertionError, ValueError):
            self.rel_rule()
            self.rule()
        self.result.reverse() # we parsed from behind but appended to the list
        return self

    def matches(self, pattern: re.Pattern, as_: RT):
        match = pattern.search(self.s)
        assert match and (length := match.end() - match.start())
        groups = [g for g in match.groups() if g]
        self.result.append((as_, groups))
        self.s = self.s[:-length]

    def single_rule(self):
        self.matches(sngl_p, RT.Single)

    def rel_rule(self):
        self.matches(rel_p, RT.Rel)
    
def process(p: ResultType):
    match p:
        case [*rest,(RT.Rel, rel), (RT.Single, single)]:
            return proc_rel(rel[0], proc_singles(single), process(rest))
        case [(RT.Single, single),]:
            return proc_singles(single)
    raise RuntimeError("Process failed")

def proc_rel(rel: str, s1, s2):
    match rel:
        case " ":
            return any_child_selector((s1,s2))
        case ">":
            return direct_child_selector((s1,s2))
    raise RuntimeError(f"Invalid rel found {rel}")

def proc_singles(groups: list[str]):
    return and_selector(
        proc_single(s) for s in groups
    )

def proc_single(s: str)->Selector:
    if s == "*":
        return any_selector
    match s[0]:
        case "#":
            return id_selector(s[1:])
        case ".":
            return class_selector(s[1:])
        case _:
            return tag_selector(s)

def test():
    assert (sngl_p.match("#id"))
    assert (sngl_p.match(".class"))
    assert rel_p.match(" ").group(0) == " "
    # assert rel_p.match("    ").group(0) == " "
    assert rel_p.search(" > ").group(1) == ">"

print(Parser("tag #id .class").rule().result)
