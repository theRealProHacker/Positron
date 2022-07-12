from dataclasses import dataclass
from own_types import style_computed
from types import MappingProxyType as frozendict

@dataclass
class CacheEntry:
    style: frozendict[style_computed]
    ref_count: int = 1

cache = {}

def get_key(d: style_computed):
    return (*sorted(d.items(), key = lambda x: x[0]),)

def get_style(d: style_computed):
    """
    Get a style from the cache. This method must only be called in a fashion so that the passed `dict` is not mutated after this function.
    If it is that would break the whole cache. So always call this function like this:
    ```python
    style = {} # the style should normally be filled
    style = get_style(style) # now the reference to the `dict` is gone and the caller only has a copy of the `frozendict`
    ```
    If the caller now tries to set any of the dicts items an Exception will be raised
    """
    key = get_key(d)
    if key in cache:
        cache[key].ref_count += 1
    else:
        cache[key] = CacheEntry(frozendict(d))

    return cache[key].style

def safe_style(d: style_computed):
    """
    Same as get_style

    But it doesn't matter what you do with the dict after you passed it in here. 
    """
    return get_style(d.copy())

def deref(d: style_computed):
    key = get_key(d)
    if key in cache:
        cache[key].ref_count -= 1
        if not cache[key].ref_count:
            del cache[key]
    else:
        raise KeyError("Tried to dereference a style that didn't exist")

def test():
    style1 = {
        "display": "block",
        "margin-top": "1em",
        "margin-bottom": "1em",
    }
    style2 = {
        "margin-bottom": "1em",
        "margin-top": "1em",
        "display": "block",
    }
    style1 = get_style(style1)
    assert style1["display"] == "block"
    assert style1 is get_style(style2)
    assert style1 == style2
    assert len(cache) == 1
    for _ in range(2):
        deref(style2)
    assert len(cache) == 0 # after dereferencing, the cache is empty
    # clearing style3 affects style2_frozen, (bad_behaviour)
    style3 = style2.copy()
    _ = get_style(style3)
    style2_frozen = get_style(style2)
    style3.clear()
    assert len(style2_frozen) == 0
    cache.clear()
    # but not if we use the safe version of get_style
    style3 = style2.copy()
    _ = safe_style(style3)
    style2_frozen = safe_style(style2)
    style3.clear()
    assert style2_frozen == style2

    



