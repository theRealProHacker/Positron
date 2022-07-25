from copy import copy
from weakref import WeakValueDictionary
from frozendict import frozendict as _frozendict

class frozendict(_frozendict): # to make the weakref work
    pass

from own_types import computed_value, style_computed

_Key = tuple[tuple[str, computed_value], ...]
cache: WeakValueDictionary[_Key, style_computed] = WeakValueDictionary()

def get_key(d: style_computed)->_Key:
    return (*sorted(d.items(), key = lambda x: x[0]),)

def safe_style(d: style_computed)->style_computed:
    d = copy(d)
    key = get_key(d)
    if key not in cache:
        frz = frozendict(d) # we need to hold this reference until we return
        cache[key] = frz
    return cache[key]


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
    # 1. Insert dict works
    style3 = safe_style(style1)
    assert len(cache) == 1

    # 2. when adding another element the cache doesn't grow
    style4 = safe_style(style2)
    assert len(cache) == 1
    # 3. and returns the found value
    style3 is style4

    # 4. when we delete the reference to the cache item, the cache gets cleared
    style3 = None
    del style4
    assert not cache
