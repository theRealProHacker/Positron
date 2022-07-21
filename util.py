from dataclasses import dataclass
from numbers import Number
import re
from contextlib import contextmanager, redirect_stdout, suppress
from functools import cache, partial
from typing import Iterable, Literal, TypeVar, Callable, Any
from config import g
from operator import itemgetter, attrgetter
from own_types import _XMLElement, Auto, Sentinel, Percentage, Color, computed_value

import pygame as pg
import pygame.freetype as freetype


def noop(*args, **kws):
    return None

# This should work for most use cases like __add__, __iadd__ and compare operations
class MutableFloat:
    value: float
    def __init__(self, value):
        self.set(value)
    def set(self, value):
        self.value = float(value)
    forbidden = {
        "__new__", "__init__", "__getattribute__", "__getattr__", "__setattr__", "__delattr__",
        "__dir__", "__class__", "__init_subclass__", "__subclasshook__"
    }
    for name in float().__dir__():
        if name in forbidden or not name.startswith("__"): continue
        func = getattr(float, name)
        if not callable(func): continue
        change = "if type(x) is float: self.value=x" if name.startswith("__i") else ""
        s = f"""
def {name}(self, *args, **kwargs):
    args = [arg.value if type(arg) is MutableFloat else arg for arg in args]
    x = float.{name}(self.value, *args, **kwargs)
    {change}
    return x
        """.strip()
        exec(s)

################## Acceptor #################################

# An acceptor is just a function that gets a string and either returns False or a computed_value
AcceptorType = TypeVar("AcceptorType", bound = computed_value)
Acceptor = Callable[[str], Literal[False]|computed_value]
def acc_frm_dict(d: dict[str, AcceptorType])->Callable[[str], (Literal[False]|AcceptorType)]:
    def inner(val: str):
        if val in d:
            return d[val]
        return False
    return inner

def length(val: str):
    if val[-2:] == "px":
        return float(val[:-2])
    return False


################## Element Calculation ######################
snp = Sentinel|Number|Percentage
@dataclass
class Calculator:
    default_perc_val: Number
    def __call__(
        self,
        value: snp,
        auto_val: Number|None = None,
        perc_val: Number|None = None
    )->Number:
        """
        This helper function takes a value, an auto_val
        and the perc_value and returns a Number
        if the value is Auto then the auto_value is returned
        if the value is a Number that is returned
        if the value is a Percentage the Percentage is multiplied with the perc_value
        """
        perc_val = make_default(perc_val, self.default_perc_val)
        if value is Auto:
            if auto_val is None:
                raise ValueError("This attribute cannot be auto")
            return auto_val
        elif isinstance(value, Number):
            return not_neg(value)
        elif isinstance(value, Percentage):
            return not_neg(perc_val * value) # raises ValueError if perc_val is None
        raise TypeError

    def multi(self, values: Iterable[snp], *args)->tuple[Number,...]:
        return tuple(self(val, *args) for val in values)

################## Value Correction #########################

Var = TypeVar("Var")
def make_default(value: Var|None, default: Var)->Var:
    """ 
    If the `value` is None this returns `default` else it returns `value`
    """
    return default if value is None else value

def in_bounds(x: Number, lower: Number, upper: Number)->Number:
    x = max(lower, x)
    x = min(upper, x)
    return x

not_neg = lambda x: max(0,x)

def get_tag(elem: _XMLElement)->str:
    try:
        return elem.tag.removeprefix("{http://www.w3.org/1999/xhtml}")
    except AttributeError:
        print(elem)
        return "error"

def ensure_suffix(s: str, suf: str)->str:
    return s if s.endswith(suf) else s + suf

##################### Itemgetters ##########################
# https://stackoverflow.com/questions/54785148/destructuring-dicts-and-objects-in-python
inset_getter: Callable[[dict], tuple[Number, ...]]    = itemgetter(*g["inset-keys"]) # type: ignore[misc]
pad_getter: Callable[[dict], tuple[Number, ...]]      = itemgetter(*g["padding-keys"]) # type: ignore[misc]
bw_getter: Callable[[dict], tuple[Number, ...]]       = itemgetter(*g["border-width-keys"]) # type: ignore[misc]
mrg_getter: Callable[[dict], tuple[Number, ...]]      = itemgetter(*g["margin-keys"]) # type: ignore[misc]
rs_getter: Callable[[pg.Rect], tuple[Number, ...]]    = attrgetter(*g["side-keys"]) # type: ignore[misc]

####################### I/O #################################

def readf(path: str):
    with open(path, 'r', encoding="utf-8") as file:
        return file.read()

@contextmanager
def clog_error():
    with open("error.log","a", encoding="utf-8") as file:
        with redirect_stdout(file):
            yield

def log_error(*messages, **kwargs):
    with clog_error():
        print(*messages, **kwargs)

@cache
def print_once(t: str):
    print(t)

def print_tree(tree, indent = 0):
    if not hasattr(tree, "children") or not tree.children:
        return print(" "*indent, f"<{tree.tag}/>")
    print(" "*indent, f"<{tree.tag}>")
    with suppress(AttributeError):
        for child in tree.children:
            print_tree(child, indent+2)
    print(" "*indent, f"</{tree.tag}>")

def print_parsed_tree(tree, indent = 0, with_text = False):
    text = "with " + tree.text if with_text and tree.text else ""
    tag = get_tag(tree)
    if not tree:
        return print(" "*indent, f"<{tag}/>", text)
    print(" "*indent, f"<{tag}>", text)
    with suppress(AttributeError):
        for child in tree:
            print_parsed_tree(child, indent+2)
    print(" "*indent, f"</{tag}>")

####################### Regexes ##################################
def re_join(*args: str)->str:
    return "|".join(re.escape(x) for x in args)

def replace_all(s: str, olds: list[str], new: str)->str:
    pattern = re.compile(re_join(*olds))
    return pattern.sub(new, s)


int_re = r"[+-]?\d*"
dec_re = fr"(?:{int_re})?(?:\.\d+)?(?:e{int_re})?"
units_re = re_join(*g["all_units"])  # type: ignore[misc]

split_units_pattern = re.compile(fr"({dec_re})(\w*)")
def split_units(attr: str)->tuple[float, str]:
    """ Split a dimension or percentage into a tuple of number and the "unit" """
    match = split_units_pattern.fullmatch(attr.strip())
    # -> Raises ValueError if the string can't be splitted
    num, unit = match.groups()  # type: ignore[union-attr]
    return float(num), unit

regexes: dict[str, re.Pattern] = {k:re.compile(x) for k,x in {
        "integer": int_re,
        "number": dec_re,
        "percentage": fr"{dec_re}\%",
        "dimension": fr"(?:{dec_re})(?:\w*)", #TODO: Use actual units
    }.items()
}

def check_regex(name: str, to_check: str):
    """
    Checks if the given regex matches the given string and returns the match or None if it doesn't match
    KeyError if the regex specified doesn't exist
    """
    return regexes[name].fullmatch(to_check.strip())

for key, value in regexes.items():
    globals()[f"is_{key}"] = partial(check_regex, key)

########################## Test ####################################
def test():
    assert split_units("3px") == (3, "px")
    assert split_units("0") == (0, "")
    with suppress(ValueError): # anything that should return a ValueError in here
        split_units("blue")
        print("Split units test failed")

    tests = {
        # https://developer.mozilla.org/en-US/docs/Web/CSS/integer#examples
        "integer": {
            "true": ["12","+123","-456","0","+0","-0", "00"],
            "false": ["12.0","12.","+---12","ten","_5",r"\35","\4E94", "3e4"]  
        },
        # https://developer.mozilla.org/en-US/docs/Web/CSS/number#examples
        "number": {
            "true": ["12","4.01","-456.8","0.0","+0.0","-0.0",".60","10e3","-3.4e-2"],
            "false": ["12.","+-12.2","12.1.1"]
        },
        # https://developer.mozilla.org/en-US/docs/Web/CSS/dimension
        "dimension": {
            "true": ["12px","1rem","1.2pt","2200ms","5s","200hz"],
            "false": ["12 px", "12\"px\""]#,"3sec"]
        }
    }
    glob = globals()
    for k, val in tests.items():
        func = glob["is_"+k]
        for true in val["true"]:
            assert func(true)
        for false in val["false"]:
            assert not func(false)



############################# Pygame related #############################

pg.init()

def rect_lines(rect: pg.Rect):
    """
    Makes bounding lines from the rect.
    First top then bottom, left, right
    The lines grow: line[0] <= line[1]
    """
    return (
        (rect.topleft, rect.topright),
        (rect.bottomleft, rect.bottomright),
        (rect.topleft, rect.bottomleft),
        (rect.topright, rect.bottomright),
    )

def draw_text(
    surf: pg.surface.Surface,
    text:str,
    fontname:str|None,
    size:int,
    color,
    **kwargs
):
    font: Any = freetype.SysFont(fontname, size) # type: ignore[arg-type]
    color = Color(color)
    dest: pg.Rect = font.get_rect(str(text)) 
    for k,val in kwargs.items():
        with suppress(AttributeError):
            setattr(dest, k, val)
    font.render_to(surf, dest=dest, fgcolor = color) 

class Dotted:
    def __init__(
        self,
        dim,
        color,
        dash_size: int = 10,
        dash_width: int = 2,
        start_pos = (0,0)
    ):
        self.dim = pg.Vector2(dim)
        self.color = Color(color)
        self.dash_size = dash_size
        self.dash_width = dash_width
        self.start_pos = pg.Vector2(start_pos)
    
    @classmethod
    def from_rect(cls, rect: pg.rect.Rect, **kwargs):
        return cls(rect.size, **kwargs, start_pos = rect.topleft)

    def draw_at(self, surf: pg.surface.Surface, pos):
        pos = pg.Vector2(pos)
        vec = self.dim.normalize()*self.dash_size
        for i in range(int(self.dim.length()//self.dash_size//2)):
            _pos = pos + vec*i*2
            pg.draw.line(
                surf,
                self.color,
                _pos,
                _pos + vec,
                self.dash_width
            )

    def draw(self, surf: pg.Surface):
        return self.draw_at(surf, self.start_pos)

    def draw_rect(self, surf: pg.Surface):
        rect = pg.Rect(*self.start_pos, *self.dim)
        for line in rect_lines(rect):
            pos = pg.Vector2(line[0])
            dim = line[1] - pos
            Dotted(
                dim, self.color, self.dash_size, self.dash_width, pos
            ).draw(surf)

def draw_lines(surf: pg.surface.Surface, points, *args, **kwargs):
    points = [pg.Vector2(point) for point in points]
    dlines = [
        Dotted(points[i+1]-points[i], *args, **kwargs|{"start_pos": points[i]})
        for i in range(len(points)-1)
    ]
    for dline in dlines:
        dline.draw(surf)
