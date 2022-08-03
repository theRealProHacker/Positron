"""
A simple inline css parser
"""

from own_types import style_input
# from Selectors import Parser

directions = ["top", "right", "bottom", "left"]

def parse_single(input: str)->style_input:
    # we remove any leading and trailing brackets
    input = input.strip().removeprefix("{").removesuffix("}").lower()

    # Note that from this parsing method we can be sure that any css value is always stripped.
    return {
        array[0].strip():array[1].strip() for element in input.split(";")
        if len((array:=element.split(":")))==2
    }

all_keys = [
    "display",
    # TODO: extend this
]
def postprocess(d: style_input):
    # TODO: all: ...
    # TODO: font
    # TODO: border-radii
    all = {}
    for k in d:
        if k == "all":
            all = dict.fromkeys(
                all_keys,
                d["all"]
            )
        elif all:
            all[k] = d[k]
    if all:
        d = all

    dirs_fallbacks = {
        "right": "top",
        "bottom": "top",
        "left": "right"
    }
    dir_shorthands = [
        ("margin", "margin-{}"),
        ("padding", "padding-{}"),
        ("border-width", "border-{}-width"),
        ("border-color", "border-{}-color"),
        ("border-style", "border-{}-style"),
        ("inset", "{}")
    ]
    for sh in dir_shorthands:
        name, fstring = sh
        # if x is empty then nothing happens else four elements are injected
        if name in d:
            arr: list[str] = d.pop(name).split() # Beispiel: margin: 10px 30px -> [10px, 30px]
            _res = dict(zip(directions, arr))
            # Now we fill in the missing arguments
            for k,v in dirs_fallbacks.items():
                if k not in _res:
                    _res[k] = _res[v]
            d.update({
                fstring.format(k):v for k,v in _res.items()
            })

    return d

def inline(input: str)->style_input:
    return postprocess(parse_single(input))

# def handle_rule(rule: cssutils.css.CSSStyleRule):
#     parser = Parser(rule.selectorText)
#     return (
#         parser.run(),
#         parse_single(rule.style),
#         parser.specificity
#     )

# def parse(s: str):
#     parsed: cssutils.css.CSSStyleSheet = cssutils.parseString(s)
#     return [
#         handle_rule(rule)
#         for rule in parsed.cssRules
#     ]


if __name__ == "__main__":
    from pprint import pprint
    assert (res:=parse_single("""{
        background-color: #000000;
        font-weight: bold;
        color: #000000;
        background-color: #ffffff;
    }""")) == {
        "background-color":"#ffffff",
        "font-weight":"bold",
        "color":"#000000",
    }, res

    assert (res:=parse_single("""
    {
        margin: 3px
    }
    """)) == {
        "margin-top": "30px",
        "margin-right": "10px",
        "margin-bottom": "20px",
        "margin-left": "10px",
    }, res

    