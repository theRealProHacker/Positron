"""
Maybe useful trash
"""

# from OwnTypes
# class ReadChain(Mapping[K_T, V_T]):
#     """A Read-Only ChainMap"""

#     def __init__(self, *maps: Mapping[K_T, V_T]):
#         self.maps = maps  # immutable maps

#     def __getitem__(self, key: K_T):
#         for mapping in self.maps:
#             with suppress(KeyError):
#                 return mapping[key]  # can't use 'key in mapping' with defaultdict
#         raise KeyError(key)

#     def dict(self) -> dict[K_T, V_T]:
#         return reduce(or_, reversed(self.maps), {})

#     def __len__(self) -> int:
#         return len(self.dict())

#     def __iter__(self):
#         return iter(self.dict())

#     def __or__(self, other: Mapping[K_T, V_T]):
#         return self.dict() | other

#     def __ror__(self, other: Mapping[K_T, V_T]):
#         return self.dict() | other

#     def __contains__(self, key):
#         return any(key in m for m in self.maps)

#     def __bool__(self):
#         return any(self.maps)

#     def __repr__(self):
#         return f'{self.__class__.__name__}({", ".join(map(repr, self.maps))})'

#     def copy(self):
#         return self.__class__(*self.maps)

#     __copy__ = copy

#     def new_child(self, m=None, **kwargs):
#         """
#         New ReadChain with a new map followed by all previous maps.
#         If no map is provided, an empty dict is used.
#         Keyword arguments update the map or new empty dict.
#         """
#         if m is None:
#             m = kwargs
#         elif kwargs:
#             m.update(kwargs)
#         return self.__class__(m, *self.maps)

#     @property
#     def parents(self):
#         "New ReadChain from maps[1:]."
#         return self.__class__(*self.maps[1:])
