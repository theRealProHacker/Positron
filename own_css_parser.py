
from contextlib import suppress


directions = ["top", "right", "bottom", "left"]

def parse(input: str):
    if not input:
        return {}
    # we remove any leading and trailing brackets
    input = input.strip().removeprefix("{").removesuffix("}").lower()

    result = {}

    ################################### The actual parsing ###########################
    for element in input.split(";"):
        array = element.split(":")
        with suppress(ValueError):
            key, value = array
            result[key.strip()] = value.strip()
    # Note that from this parsing method we can be sure that any css value is always stripped.
    
    ################################## Shorthand expansion ############################
    # TODO: all: ...
    # TODO: font
    # TODO: border

    dirs_fallbacks = {
        "right": "top",
        "bottom": "top",
        "left": "right"
    }
    dir_shorthands = [
        ("margin", "margin-{}"),
        ("padding", "padding-{}"),
        ("border-width", "border-{}-width"),
    ]
    for sh in dir_shorthands:
        name, fstring = sh
        # if x is empty then nothing happens else four elements are injected
        if name in result:
            arr: list[str] = result.pop(name).split() # Beispiel: margin: 10px 30px -> [10px, 30px]
            _res = dict(zip(directions, arr))
            # Now we fill in the missing arguments
            for k,v in dirs_fallbacks.items():
                if k not in _res:
                    _res[k] = _res[v]
            result.update({
                fstring.format(k):v for k,v in _res.items()
            })

    return result


if __name__ == "__main__":
    from pprint import pprint
    assert (res:=parse("""{
        background-color: #000000;
        font-weight: bold;
        color: #000000;
        background-color: #ffffff;
    }""")) == {
        "background-color":"#ffffff",
        "font-weight":"bold",
        "color":"#000000",
    }, res

    assert (res:=parse("""
    margin: 30px 10px 20px;
    """)) == {
        "margin-top": "30px",
        "margin-right": "10px",
        "margin-bottom": "20px",
        "margin-left": "10px",
    }, res

    