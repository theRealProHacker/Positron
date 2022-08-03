from copy import copy
from weakref import WeakSet
from frozendict import FrozenOrderedDict as _frozendict


class frozendict(_frozendict):  # to make the weakref work
    pass


class Cache(WeakSet[frozendict]):
    def safe(self, d: dict) -> frozendict:
        frz = frozendict(copy(d))  # we need to hold this reference until we return
        self.add(frz)
        return frz


def test():
    test_cache = Cache()
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
    style3 = test_cache.safe(style1)
    assert len(test_cache) == 1

    # 2. when adding another element the cache doesn't grow
    style4 = test_cache.safe(style2)
    assert len(test_cache) == 1
    # 3. and returns the found value
    style3 is style4

    # 4. when we delete the reference to the cache item, the cache gets cleared
    style3 = None
    del style4
    assert not test_cache
