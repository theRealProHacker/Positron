from contextlib import contextmanager
from typing import Callable, Iterable, Sequence, TypeVar

import pygame as pg

# fmt: off
from positron.types import CO_T, K_T, V_T, Index


########################## Misc #########################
def noop(*args, **kws):
    """A no operation function"""
    return None


def make_default(value: V_T | None, default: V_T) -> V_T:
    """
    If the `value` is None this returns `default` else it returns `value`

    `make_default(age, 0)`
    """
    return default if value is None else value


def in_bounds(x: float, lower: float, upper: float) -> float:
    """
    Make `x` be between lower and upper
    """
    x = max(lower, x)
    x = min(upper, x)
    return x


def not_neg(x: float):
    """
    return the maximum of x and 0
    """
    return max(0, x)


def abs_div(x):
    """
    Return the absolute of a fraction.
    Just like `abs(x*-1)` is `(x*1)`, `abs_div(x**-1)` is `(x**1)`.
    Or in other words just like abs is the 'distance' to 0 (the neutral element of addition) using addition,
    abs_div is the distance to 1 (the neutral element of multiplication) using multiplication.
    """
    # or exp(abs(ln(x)))
    return 1 / x if x < 1 else x


def get_tag(elem) -> str:
    """
    Get the tag of an _XMLElement or "comment" if the element has no valid tag
    """
    return (
        elem.tag.removeprefix("{http://www.w3.org/1999/xhtml}").lower()
        if isinstance(elem.tag, str)
        else "!comment"
    )


def ensure_suffix(s: str, suf: str) -> str:
    """
    Ensures that `s` definitely ends with the suffix `suf`
    """
    return s if s.endswith(suf) else s + suf


def all_equal(l: Sequence):
    """
    Return whether all the elements in the list are equal
    """
    if len(l) < 2:
        return True
    x, *rest = l
    return all(x == r for r in rest)


def group_by_bool(
    l: Iterable[V_T], key: Callable[[V_T], bool]
) -> tuple[list[V_T], list[V_T]]:
    """
    Group a list into two lists depending on the bool value given by the key
    """
    true = []
    false = []
    for x in l:
        if key(x):
            true.append(x)
        else:
            false.append(x)
    return true, false


def find(__iterable: Iterable[V_T], key: Callable[[V_T], bool]):
    """
    Find the first element in the iterable that is accepted by the key
    """
    for x in __iterable:
        if key(x):
            return x


def find_index(__iterable: Iterable[V_T], key: Callable[[V_T], bool]):
    """
    Find the first elements index in the iterable that is accepted by the key
    """
    for i, x in enumerate(__iterable):
        if key(x):
            return i


def consume_list(l: list[V_T]):
    """
    Consume a list by removing all elements
    """
    while l:
        yield l.pop(0)


def consume_dict(d: dict[K_T, V_T]):
    """
    Consume a dict by removing all items
    """
    while d:
        yield d.popitem()


V_T2 = TypeVar("V_T2")


def map_dvals(d: dict[K_T, V_T], func: Callable[[V_T], V_T2]) -> dict[K_T, V_T2]:
    return {k: func(v) for k, v in d.items()}


# tuple mutations
def mutate_tuple(tup: tuple, val, slicing: Index)->tuple:
    """
    Mutate a tuple given the tuple, a slicing and the value to fill into that slicing
    Example:
        ```python
        t = (1,2)
        mutate_tuple(t, 3, 0) == (3,2)
        ```
    """
    l = list(tup)
    l[slicing] = val
    return tuple(l)


def tup_replace(
    t: tuple[CO_T, ...], slice_: int | tuple[int, int], elem
) -> tuple[CO_T, ...]:
    """
    Replace the part of the tuple given by slice with `elem`
    """
    if isinstance(slice_, int):
        return *t[:slice_], elem, *t[slice_:]
    elif isinstance(slice_, tuple):
        start, stop = slice_
        return *t[:start], elem, *t[stop:]
    return



def nice_number(num: complex) -> str:
    """
    Try to simplify the number as small as possible

    1.0 -> 1

    1.0+0.0j ->1
    """
    if isinstance(num, complex) and num.imag == 0:
        return nice_number(num.real)
    elif isinstance(num, float) and num.is_integer():
        return str(int(num))
    else:
        return str(num)


@contextmanager
def set_context(obj, name: str, value):
    """
    A context in which the objects attribute name is set to value
    """
    old_value = getattr(obj, name)
    try:
        setattr(obj, name, value)
        yield
    finally:
        setattr(obj, name, old_value)


####################################################################
