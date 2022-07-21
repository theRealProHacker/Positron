from copy import copy
from own_types import style_computed, computed_value
from types import MappingProxyType as frozendict

_Key = tuple[tuple[str, computed_value], ...]
cache: dict[_Key, style_computed] = {}

def get_key(d: style_computed)->_Key:
    return (*sorted(d.items(), key = lambda x: x[0]),)

def safe_style(d: style_computed)->style_computed:
    d = copy(d)
    key = get_key(d)
    if key not in cache:
        cache[key] = frozendict(d)
    return cache[key]