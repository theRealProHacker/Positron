from typing import Generic, Iterable
from own_types import K_T, frozendict
from weakref import WeakValueDictionary

class weakstr(str):
    pass

redirect: dict[type,type] = {
    str: weakstr
}


class Cache(Generic[K_T]): # The Cache is a set like structure but it uses a dict underneath
    def __init__(self, l: Iterable[K_T] = []):
        self.cache = WeakValueDictionary[int,K_T]()
        for val in l:
            self.add(val)
    def add(self, val: K_T)->K_T:
        if (new_type:= redirect.get(type(val))) is not None:
            val = new_type(val)
        key = hash(val)
        if key not in self.cache:
            self.cache[key] = val
        return self.cache[key]
    def __bool__(self):
        return bool(self.cache)
    def __len__(self):
        return len(self.cache)
    def __repr__(self):
        return repr(set(self.cache.values()))
    def __contains__(self, value: K_T) -> bool:
        return hash(value) in self.cache
    def __iter__(self):
        return self.cache.values()


class FrozenDCache(Cache[frozendict]):
    def add(self, d: dict) -> frozendict:
        frz = frozendict(d)
        return super().add(frz)
