"""
Limited support for media queries:

Basically just screen size.
"""

from abc import ABC
from dataclasses import dataclass
from enum import Enum
from operator import eq, ge, le
from typing import Any, Callable

from tinycss.css21 import ImportRule as TinyImportRule
from tinycss.css21 import PageRule as TinyPageRule
from tinycss.css21 import ParseError
from tinycss.token_data import ContainerToken, Token, TokenList

from config import g
from util import find_index

MediaValue = tuple[int, int]  # just the window size right now


def get_media() -> MediaValue:
    return g["W"], g["H"]


############################# Types #######################################
class AtRule(ABC):
    pass


class ImportRule(TinyImportRule, AtRule):
    pass


class PageRule(TinyPageRule, AtRule):
    pass


class MediaClause:
    def matches(self, media: MediaValue):
        ...


@dataclass
class NotRule(MediaClause):
    subrule: MediaClause

    def matches(self, media):
        return not self.subrule.matches(media)


@dataclass
class AndRule(MediaClause):
    subrules: list[MediaClause]

    def matches(self, media):
        return all(rule.matches(media) for rule in self.subrules)


@dataclass
class OrRule(MediaClause):
    subrules: list[MediaClause]

    def matches(self, media):
        return any(rule.matches(media) for rule in self.subrules)


class Dimension(Enum):
    Width = 0
    Height = 1


CompareFunc = Callable[[Any, Any], Any]  # really to bool but typeshed broken


@dataclass
class DimensionRule(MediaClause):
    val: float
    dim: Dimension
    comp_func: CompareFunc

    def matches(self, media: MediaValue):
        media_val = media[self.dim.value]
        return self.comp_func(media_val, self.val)


def parse_media_clause_prop(property: Token, value: Token) -> MediaClause:
    # TODO: regex (min-|max-|)(width|height)
    if value.unit == "px":
        match property.value:
            case "min-width":
                return DimensionRule(value.value, Dimension.Width, ge)
    raise ParseError("Invalid media clause")


def parse_media_clause(tokens: TokenList) -> MediaClause:
    """
    raises IndexError on failure
    """
    original = tokens
    media_clause: MediaClause
    # remove whitespace
    while (i := find_index(tokens, key=lambda x: x.type == "S")) is not None:
        tokens.pop(i)
    # brackets (containers)
    while (
        i := find_index(tokens, key=lambda x: isinstance(x, ContainerToken))
    ) is not None:
        tokens[i] = parse_media_clause(tokens[i].content)
    # find colons:
    while (
        i := find_index(tokens, key=lambda x: hasattr(x, "type") and x.type == ":")
    ) is not None:
        property = tokens[i - 1]
        value = tokens[i + 1]
        tokens[i - 1 : i + 2] = [parse_media_clause_prop(property, value)]
    match tokens:
        case [media_clause] if isinstance(media_clause, MediaClause):
            return media_clause
    raise ParseError(f"Couldn't parse MediaClause: {original}")


class MediaRule(AtRule):
    """
    This represents an @media-Rule

    In contrast to MediaClause it includes the actual style contents as well as the MediaClause
    that decides whether the MediaRules content will be applied
    """

    def __init__(self, media_clause_tokens: TokenList, content):
        # content: Style.SourceSheet
        self.media_clause = parse_media_clause(media_clause_tokens)
        self.content = content

    def matches(self, media: MediaValue):
        """Whether a MediaRule matches a Media"""
        return self.media_clause.matches(media)


__all__ = [
    "MediaValue",
    "get_media",
    "AtRule",
    "ImportRule",
    "MediaRule",
    "PageRule",
]
