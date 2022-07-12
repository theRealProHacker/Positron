import re
from contextlib import contextmanager, redirect_stdout, suppress
from functools import cache, partial
from config import g
from operator import itemgetter, attrgetter
from xml.etree.ElementTree import Element as _XMLElement

################## Value Correction #########################
def make_default(value, default):
    """ 
    If the value is None this returns `default`
    Otherwise it returns `value`
    """
    return default if value is None else value

def in_bounds(x, lower, upper):
    x = max(lower, x)
    x = min(upper, x)
    return x

@cache
def get_tag(elem: _XMLElement):
    return elem.tag.removeprefix("{http://www.w3.org/1999/xhtml}")


##################### Itemgetters ##########################
pad_getter = itemgetter(*g["padding-keys"])
bw_getter  = itemgetter(*g["border-width-keys"])
mrg_getter = itemgetter(*g["margin-keys"])
rs_getter = attrgetter(*g["side-keys"])

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

class Tree:
    tag: str
    text: str|None
    children: list["Tree"]

def print_tree(tree: Tree, indent = 0):
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
def re_join(*args: str):
    return "|".join(re.escape(x) for x in args)

def replace_all(s: str, olds: list[str], new: str):
    pattern = re.compile(re_join(*olds))
    return pattern.sub(new, s)


int_re = r"[+-]?\d*" 
dec_re = fr"(?:{int_re})?(?:\.\d+)?(?:e{int_re})?"
units_re = re_join(*g["all_units"])

split_units_pattern = re.compile(fr"({dec_re})(\w*)")
def split_units(attr: str)->tuple[float, str]:
    """ Split a dimension or percentage into a tuple of number and the "unit" """
    match = split_units_pattern.fullmatch(attr.strip())
    num, unit = match.groups()
    return float(num), unit

regexes = {
    "integer": int_re,
    "number": dec_re,
    "percentage": fr"{dec_re}\%",
    "dimension": fr"(?:{dec_re})(?:\w*)", #TODO: Use actual units with regex join
}
regexes: dict[str, re.Pattern] = {k:re.compile(x) for k,x in regexes.items()}

def check_regex(name: str, to_check: str)->re.Match|None:
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
