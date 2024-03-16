from operator import itemgetter
from typing import Any, Generic, Mapping, Protocol

from positron.types import CO_T, V_T, AutoLP, Color, LengthPerc, Str4Tuple

#################### Itemgetters/setters ###########################

CompValue = Any
FullyComputedStyle = Mapping[str, CompValue]


# https://stackoverflow.com/questions/54785148/destructuring-dicts-and-objects-in-python
class T4Getter(Protocol[CO_T]):
    def __call__(self, input: FullyComputedStyle) -> tuple[CO_T, CO_T, CO_T, CO_T]:
        ...


class itemsetter(Generic[V_T]):
    def __init__(self, keys: tuple[str, ...]):
        self.keys = keys

    def __call__(self, map: dict, values: tuple[V_T, ...]) -> None:
        for key, value in zip(self.keys, values):
            map[key] = value


directions = ("top", "right", "bottom", "left")
corners = ("top-left", "top-right", "bottom-right", "bottom-left")

# fmt: off
inset_keys = directions
marg_keys: Str4Tuple = tuple(f"margin-{k}" for k in directions)     # type: ignore[assignment]
pad_keys: Str4Tuple = tuple(f"padding-{k}" for k in directions)     # type: ignore[assignment]
bs_keys: Str4Tuple = tuple(f"border-{k}-style" for k in directions) # type: ignore[assignment]
bw_keys: Str4Tuple = tuple(f"border-{k}-width" for k in directions) # type: ignore[assignment]
bc_keys: Str4Tuple = tuple(f"border-{k}-color" for k in directions) # type: ignore[assignment]
br_keys: Str4Tuple = tuple(f"border-{k}-radius" for k in corners)   # type: ignore[assignment]

ALPGetter = T4Getter[AutoLP]
inset_getter: ALPGetter = itemgetter(*inset_keys)   # type: ignore[assignment]
mrg_getter: ALPGetter = itemgetter(*marg_keys)      # type: ignore[assignment]
pad_getter: ALPGetter = itemgetter(*pad_keys)       # type: ignore[assignment]

bw_getter: ALPGetter = itemgetter(*bw_keys)         # type: ignore[assignment]
bc_getter: T4Getter[Color] = itemgetter(*bc_keys)   # type: ignore[assignment]
bs_getter: T4Getter[str] = itemgetter(*bs_keys)     # type: ignore[assignment]
br_getter: T4Getter[tuple[LengthPerc, LengthPerc]] = itemgetter(*br_keys)  # type: ignore[assignment]
# fmt: on
####################################################################

__all__ = [
    "directions",
    "inset_keys",
    "marg_keys",
    "pad_keys",
    "bs_keys",
    "bw_keys",
    "bc_keys",
    "br_keys",
    "inset_getter",
    "mrg_getter",
    "pad_getter",
    "bw_getter",
    "bc_getter",
    "bs_getter",
    "br_getter",
]
