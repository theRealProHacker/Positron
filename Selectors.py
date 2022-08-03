"""
Handles everything revolving Selecetors. 
Includes a Parser (text->Selector)
"""
import re
from contextlib import suppress
from dataclasses import dataclass
from functools import cached_property, reduce
from typing import Any, Callable, Iterable, Iterator, Protocol, Sequence, Type

from util import get_groups
from own_types import Enum, enum_auto

############################# Element ######################################
Element = Any

############################# Specs #########################################
Spec = tuple[int, int, int]

def add_specs(t1: Spec, t2: Spec) -> Spec:
    id1,cls1,tag1 = t1
    id2,cls2,tag2 = t2
    return id1+id2, cls1+cls2, tag1+tag2

sum_specs: Callable[[Iterable[Spec]],Spec] = lambda specs: reduce(add_specs, specs)

############################## Selectors #################################################
# A Selector gets an Element and returns whether it matches that selector
# just ignore all mypy errors here. Mypy is the worst tool ever to have been constructed
class Selector(Protocol):
    spec: Spec
    def __call__(self: Any, elem: Element)->bool:
        ...

@dataclass(frozen=True, slots=True)
class TagSelector:
    tag: str
    spec = 0,0,1
    __call__ = lambda self, elem: elem.tag == self.tag
    __str__ = lambda self: self.tag #type: ignore[attr-defined]

@dataclass(frozen=True, slots=True)
class IdSelector:
    id: str
    spec = 1,0,0
    __call__ = lambda self, elem: elem.attrs.get("id") == self.id
    __str__ = lambda self: "#"+self.id #type: ignore[attr-defined]

@dataclass(frozen=True, slots=True)
class ClassSelector:
    cls: str
    spec = 0,1,0
    __call__ = lambda self, elem: elem.attrs.get("class") == self.cls
    __str__ = lambda self: "."+self.cls #type: ignore[attr-defined]

@dataclass(frozen=True, slots=True)
class HasAttrSelector:
    name: str
    spec = 0,1,0
    __call__ = lambda self, elem: self.name in elem.attrs
    __str__ = lambda self: f'[{self.name}]' #type: ignore[attr-defined]

# the validator takes the soll value and the is value
def make_attr_selector(sign: str, validator):
    regex = re.compile(fr'\[(\w+){sign}="(\w+)"\]')
    @dataclass(frozen=True, slots=True)
    class AttributeSelector:
        name: str
        value: str
        spec = 0,1,0
        def __call__(self, elem: Element):
            return (value:=elem.attrs.get(self.name)) is not None and validator(self.value, value)
        def __str__(self):
            return f'[{self.name}{sign}="{self.value}"]'
    return regex, AttributeSelector

@dataclass(frozen=True, slots=True)
class AnySelector:
    spec = 0,0,0
    def __call__(self, elem: Element): return True
    __str__ = lambda self: "*"

################################## Composite Selectors ###############################
@dataclass(frozen=True, slots=True)
class AndSelector:
    selectors: Sequence[Selector]
    spec = property(lambda self: sum_specs(f.spec for f in self.selectors))
    __call__ = lambda self, elem: all(f(elem) for f in self.selectors)
    __str__ = lambda self: ''.join(str(s) for s in self.selectors) #type: ignore[attr-defined]

@dataclass(frozen=True, slots=True)
class DirectChildSelector:
    selectors: Sequence[Selector]
    def __post_init__(self): assert len(self.selectors) > 1
    spec = cached_property(lambda self: sum_specs(f.spec for f in self.selectors))
    def __call__(self, elem: Element):
        chain = [elem,*elem.iter_parents()]
        if len(chain) != len(self.selectors): return False
        return all(f(parent) for parent, f in zip(chain, self.selectors))
    __str__ = lambda self: " > ".join(str(s) for s in self.selectors) #type: ignore[attr-defined]

@dataclass(frozen=True, slots=True)
class ChildSelector:
    selectors: tuple[Selector, Selector]
    def __post_init__(self): assert len(self.selectors) == 2
    spec = cached_property(lambda self: sum_specs(f.spec for f in self.selectors))
    def __call__(self,elem: Element):
        own_sel, p_sel = self.selectors
        if not own_sel(elem): return False
        return any(p_sel(p) for p in elem.iter_parents())
    __str__ = lambda self: " ".join(str(s) for s in self.selectors) #type: ignore[attr-defined]

########################################## Parser #######################################################

# maybe tag, maybe id, any number of class selectors or alternatively just a *
sngl_p = re.compile(
    fr'''(\w+)?
(#\w+)?
(\.\w+)*
(\[\w+\])*
(\[\w+[~|^$*]?="\w+"\])*$
|\*$'''.replace("\n",""))
rel_p = re.compile(r"\s*([> ])\s*$")

class RT(Enum):
    """The ResultType. Either a single element or a relationship between elements"""
    Single = enum_auto
    Rel = enum_auto

ResultItem = tuple[RT, list[str]]
Result = list[ResultItem]
# TODO: Replace Parser with a parse function
class Parser:
    """
    `run`ning the Parser generates a `Selector`
    """
    def __repr__(self):
        return f"{self.__class__.__name__}(s={self.s}, result={self.result})"
    def __init__(self, s: str):
        self.s = s.strip()
    def run(self)->Selector:
        start = self.s
        self.result: Result = []
        try:
            self.rule()
            assert not self.s # nothing should be left of the input
            self.result.reverse() # we parsed from behind but appended to the list
            return process(self.result)
        except (AssertionError, ValueError):
            print(f"Couldn't parse {start}")
            raise ValueError(f"Couldn't parse {start}")

    def rule(self):
        r"""
        rule = single_rule | [rule][rel_rule][single_rule]
        """
        self.single_rule()
        if not self.s: return self
        with suppress(AssertionError, ValueError):
            self.rel_rule()
            self.rule()
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
    
def process(p: Result):
    """Converts the Result into a Selector"""
    match p:
        case [*rest,(RT.Rel, rel), (RT.Single, single)]:
            op = rel[0]
            assert len(rel) == 1, rel # TODO: ditch this
            assert op in (" ",">"),f"Invalid rel found {rel}"
            if " " == op:
                return ChildSelector((process(rest),proc_singles(single)))
            elif ">" == op:
                return DirectChildSelector([process(rest),proc_singles(single)])
        case [(RT.Single, single),]:
            return proc_singles(single)
    raise RuntimeError("Process failed")

def proc_singles(groups: list[str]):
    if len(groups) == 1: return proc_single(groups[0])
    return AndSelector([proc_single(s) for s in groups])

attr_sel_data = [
    ("", lambda soll,_is: soll==_is),
    ("~", lambda soll,_is: soll in _is.split()),
    ("|", lambda soll,_is: soll==_is or _is.startswith(soll+"-")),
    ("^", lambda soll,_is: _is.startswith(soll)),
    ("$", lambda soll,_is: _is.endswith(soll)),
    ("*", lambda soll,_is: soll in _is),
]
attr_sels = [make_attr_selector(sign, validator) for sign,validator in attr_sel_data]
attrmatches: list[tuple[re.Pattern,Type[Selector]]] = [
    (re.compile(r'\[(\w+)\]'),HasAttrSelector),
    *attr_sels
]

def proc_single(s: str):
    if s == "*":
        return AnySelector()
    elif s[0] == "#":
        return IdSelector(s[1:])
    elif s[0] == ".":
        return ClassSelector(s[1:])
    elif s[0] == "[":
        for pattern, selector in attrmatches:
            if (groups:=get_groups(s, pattern)) is not None:
                return selector(*groups)
    elif s[0] == ":": # pseudoclass
        raise RuntimeError("Pseudoclasses not supported yet")
    return TagSelector(s)

def test():
    for x in (
        "#id",
        ".class",
        "a#hello.dark[target]"
    ):
        assert sngl_p.match(x)
    parser = Parser("a#hello.dark[target]")
    selector = parser.run()
    assert parser.result == [
        (RT.Single, ["a","#hello",".dark","[target]"]),
    ]
    assert selector == AndSelector( # this wasn't possible when Selectors were just functions
        [
            TagSelector("a"),
            IdSelector("hello"),
            ClassSelector("dark"),
            HasAttrSelector("target")
        ]
    )
    parser = Parser("div>a#hello.dark[target]")
    selector = parser.run()
    assert parser.result == [
        (RT.Single, ["div"]),
        (RT.Rel, [">"]),
        (RT.Single, ["a","#hello",".dark","[target]"]),
    ]
    assert selector == DirectChildSelector(
        [
            TagSelector("div"),
            AndSelector(
                [
                    TagSelector("a"),
                    IdSelector("hello"),
                    ClassSelector("dark"),
                    HasAttrSelector("target")
                ]
            )
        ]
    )

if __name__ == "__main__":
    # for vscode debugger
    test()