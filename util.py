import re
from contextlib import contextmanager, redirect_stdout, suppress
from dataclasses import dataclass
from functools import cache, partial, total_ordering
from operator import attrgetter, itemgetter
from typing import Any, Callable, Iterable, TypeVar

import pygame as pg
import pygame.freetype as freetype

from config import g
from own_types import (SNP, Auto, AutoNP, AutoNP4Tuple, Color, Dimension, Number, Rect, Color, Surface, Vector2, Percentage, _XMLElement, Float4Tuple, SNP4Tuple, style_computed)


def noop(*args, **kws):
    return None

@total_ordering
@dataclass
class MutableFloat:
    value: float
    def __init__(self, value):
        self.set(value)
    def set(self, value):
        self.value = float(value)
    def __lt__(self, *args, **kwargs):
        args = [arg.value if type(arg) is MutableFloat else arg for arg in args]
        x = float.__lt__(self.value, *args, **kwargs)
        return x
    def __eq__(self, *args, **kwargs):
        args = [arg.value if type(arg) is MutableFloat else arg for arg in args]
        x = float.__eq__(self.value, *args, **kwargs)
        return x
    def __add__(self, *args, **kwargs):
        args = [arg.value if type(arg) is MutableFloat else arg for arg in args]
        x = float.__add__(self.value, *args, **kwargs)
        return x
    def __radd__(self, *args, **kwargs):
        args = [arg.value if type(arg) is MutableFloat else arg for arg in args]
        x = float.__radd__(self.value, *args, **kwargs)
        return x
    def __sub__(self, *args, **kwargs):
        args = [arg.value if type(arg) is MutableFloat else arg for arg in args]
        x = float.__sub__(self.value, *args, **kwargs)
        return x
    def __rsub__(self, *args, **kwargs):
        args = [arg.value if type(arg) is MutableFloat else arg for arg in args]
        x = float.__rsub__(self.value, *args, **kwargs)
        return x
    def __mul__(self, *args, **kwargs):
        args = [arg.value if type(arg) is MutableFloat else arg for arg in args]
        x = float.__mul__(self.value, *args, **kwargs)
        return x
    def __rmul__(self, *args, **kwargs):
        args = [arg.value if type(arg) is MutableFloat else arg for arg in args]
        x = float.__rmul__(self.value, *args, **kwargs)
        return x
    def __mod__(self, *args, **kwargs):
        args = [arg.value if type(arg) is MutableFloat else arg for arg in args]
        x = float.__mod__(self.value, *args, **kwargs)
        return x
    def __rmod__(self, *args, **kwargs):
        args = [arg.value if type(arg) is MutableFloat else arg for arg in args]
        x = float.__rmod__(self.value, *args, **kwargs)
        return x
    def __divmod__(self, *args, **kwargs):
        args = [arg.value if type(arg) is MutableFloat else arg for arg in args]
        x = float.__divmod__(self.value, *args, **kwargs)
        return x
    def __rdivmod__(self, *args, **kwargs):
        args = [arg.value if type(arg) is MutableFloat else arg for arg in args]
        x = float.__rdivmod__(self.value, *args, **kwargs)
        return x
    def __pow__(self, *args, **kwargs):
        args = [arg.value if type(arg) is MutableFloat else arg for arg in args]
        x = float.__pow__(self.value, *args, **kwargs)
        return x
    def __rpow__(self, *args, **kwargs):
        args = [arg.value if type(arg) is MutableFloat else arg for arg in args]
        x = float.__rpow__(self.value, *args, **kwargs)
        return x
    def __neg__(self, *args, **kwargs):
        args = [arg.value if type(arg) is MutableFloat else arg for arg in args]
        x = float.__neg__(self.value, *args, **kwargs)
        return x
    def __pos__(self, *args, **kwargs):
        args = [arg.value if type(arg) is MutableFloat else arg for arg in args]
        x = float.__pos__(self.value, *args, **kwargs)
        return x
    def __abs__(self, *args, **kwargs):
        args = [arg.value if type(arg) is MutableFloat else arg for arg in args]
        x = float.__abs__(self.value, *args, **kwargs)
        return x
    def __bool__(self, *args, **kwargs):
        args = [arg.value if type(arg) is MutableFloat else arg for arg in args]
        x = float.__bool__(self.value, *args, **kwargs)
        return x
    def __int__(self, *args, **kwargs):
        args = [arg.value if type(arg) is MutableFloat else arg for arg in args]
        x = float.__int__(self.value, *args, **kwargs)
        if type(x) is float: self.value=x        
        return x
    def __float__(self, *args, **kwargs):
        args = [arg.value if type(arg) is MutableFloat else arg for arg in args]
        x = float.__float__(self.value, *args, **kwargs)
        return x
    def __floordiv__(self, *args, **kwargs):
        args = [arg.value if type(arg) is MutableFloat else arg for arg in args]
        x = float.__floordiv__(self.value, *args, **kwargs)
        return x
    def __rfloordiv__(self, *args, **kwargs):
        args = [arg.value if type(arg) is MutableFloat else arg for arg in args]
        x = float.__rfloordiv__(self.value, *args, **kwargs)
        return x
    def __truediv__(self, *args, **kwargs):
        args = [arg.value if type(arg) is MutableFloat else arg for arg in args]
        x = float.__truediv__(self.value, *args, **kwargs)
        return x
    def __rtruediv__(self, *args, **kwargs):
        args = [arg.value if type(arg) is MutableFloat else arg for arg in args]
        x = float.__rtruediv__(self.value, *args, **kwargs)
        return x
    def __trunc__(self, *args, **kwargs):
        args = [arg.value if type(arg) is MutableFloat else arg for arg in args]
        x = float.__trunc__(self.value, *args, **kwargs)
        return x
    def __floor__(self, *args, **kwargs):
        args = [arg.value if type(arg) is MutableFloat else arg for arg in args]
        x = float.__floor__(self.value, *args, **kwargs)
        return x
    def __ceil__(self, *args, **kwargs):
        args = [arg.value if type(arg) is MutableFloat else arg for arg in args]
        x = float.__ceil__(self.value, *args, **kwargs)
        return x
    def __round__(self, *args, **kwargs):
        args = [arg.value if type(arg) is MutableFloat else arg for arg in args]
        x = float.__round__(self.value, *args, **kwargs)
        return x


################## Element Calculation ######################
# This calculates values that have to be calculated after being computed
@dataclass
class Calculator:
    default_perc_val: float|None
    def __call__(
        self,
        value: AutoNP,
        auto_val: float|None = None,
        perc_val: float|None = None
    )->float:
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
            assert perc_val is not None, f"perc_val must be set"
            return not_neg(perc_val * value) # raises ValueError if perc_val is None
        raise TypeError

    # sometimes this is called with 2-tuples
    def _multi(self, values: Iterable[AutoNP], *args)->tuple[float,...]:
        return tuple(self(val, *args) for val in values)

    def multi2(self, values: tuple[AutoNP, AutoNP], *args)->tuple[float,float]:
        return self._multi(values, *args) # type: ignore

    def multi4(self, values: AutoNP4Tuple, *args)->Float4Tuple:
        return self._multi(values, *args) # type: ignore

################## Value Correction #########################

Var = TypeVar("Var")
def make_default(value: Var|None, default: Var)->Var:
    """ 
    If the `value` is None this returns `default` else it returns `value`
    """
    return default if value is None else value

def in_bounds(x: float, lower: float, upper: float)->float:
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
Getter = Callable[[style_computed], AutoNP4Tuple]
inset_getter: Getter = itemgetter(*g["inset-keys"]) # type: ignore[assignment]
pad_getter: Getter = itemgetter(*g["padding-keys"]) # type: ignore[assignment]
bw_getter: Getter = itemgetter(*g["border-width-keys"]) # type: ignore[assignment]
mrg_getter: Getter = itemgetter(*g["margin-keys"]) # type: ignore[assignment]
rs_getter: Callable[[Rect], Float4Tuple]    = attrgetter(*g["side-keys"]) # type: ignore[assignment]

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
units_re = re_join(*g["all_units"])

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

def rect_lines(rect: Rect):
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
    surf: Surface,
    text:str,
    fontname:str|None,
    size:int,
    color,
    **kwargs
):
    font: Any = freetype.SysFont(fontname, size) # type: ignore[arg-type]
    color = Color(color)
    dest: Rect = font.get_rect(str(text)) 
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
        start_pos: Dimension = (0,0)
    ):
        self.dim = Vector2(dim)
        self.color = Color(color)
        self.dash_size = dash_size
        self.dash_width = dash_width
        self.start_pos = Vector2(start_pos)
    
    @classmethod
    def from_rect(cls, rect: Rect, **kwargs):
        return cls(rect.size, **kwargs, start_pos = rect.topleft)

    def draw_at(self, surf: Surface, pos):
        pos = Vector2(pos)
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

    def draw(self, surf: Surface):
        return self.draw_at(surf, self.start_pos)

    def draw_rect(self, surf: Surface):
        rect = Rect(*self.start_pos, *self.dim)
        for line in rect_lines(rect):
            pos = Vector2(line[0])
            dim = line[1] - pos
            Dotted(
                dim, self.color, self.dash_size, self.dash_width, pos
            ).draw(surf)

def draw_lines(surf: Surface, points, *args, **kwargs):
    points = [Vector2(point) for point in points]
    dlines = [
        Dotted(points[i+1]-points[i], *args, **kwargs, start_pos = points[i]) # type: ignore
        for i in range(len(points)-1)
    ]
    for dline in dlines:
        dline.draw(surf)
