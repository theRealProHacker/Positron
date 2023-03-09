######################### Regexes ##################################

import re
from types import FunctionType
from typing import Any, Callable, Iterable

from positron.types import BugError

whitespace_re = re.compile(r"\s+")


def get_groups(s: str, p: re.Pattern) -> list[str] | None:
    """
    Get the matched groups of a match
    """
    if match := p.search(s):
        if groups := [g for g in match.groups() if g]:
            return groups
        else:
            return [match.group()]
    return None


def re_join(*args: str) -> str:
    """
    Example:
    x in ("px","%","em") <-> re.match(re_join("px","%","em"), x)
    """
    return "|".join(re.escape(x) for x in args)


# Reverse regex
r"""
Search or replace in the regex from the end of the string.
The given regex will not be reversed TODO: implement this
To reverse a regex we need to understand which tokens belong together
Examples:
\d -> \d
\d*->\d*
or
(?:\d+) -> (?:\d+)
...
"""


def rev_groups(pattern: re.Pattern | str, s: str):
    _pattern = re.compile(pattern)
    groups = get_groups(s[::-1], _pattern)
    return None if groups is None else [group[::-1] for group in groups]


def rev_sub(
    pattern: re.Pattern | str,
    s: str,
    repl: str | Callable[[list[str]], str],
    count: int = -1,
):
    """
    Subs a regex in reversed mode
    """
    _repl: Any
    if isinstance(repl, str):
        _repl = repl[::-1]
    elif isinstance(repl, FunctionType):

        def _repl(match: re.Match):
            return repl([group[::-1] for group in match.groups()])[::-1]

    else:
        raise TypeError

    return re.sub(pattern, _repl, s[::-1], count)[::-1]


class GeneralParser:
    """
    Really this is a lexer.
    It consumes parts of its x and can then convert these into tokens
    """

    x: str

    def __init__(self, x: str):
        self.x = x

    def consume(self, s: str | re.Pattern[str]) -> str:
        assert s, BugError("Parser with empty consume")
        if isinstance(s, str) and self.x.startswith(s):
            self.x = self.x[len(s) :]
            return s
        elif isinstance(s, re.Pattern):
            if match := s.match(self.x):
                slice_ = match.span()[1]
                result, self.x = self.x[:slice_], self.x[slice_:]
                return result
        return ""


def match_bracket(s: Iterable, opening="(", closing=")"):
    """
    Searchs for a matching bracket
    If not found then returns None else it returns the index of the matching bracket
    """
    brackets = 0
    for i, c in enumerate(s):
        if c == closing:
            if not brackets:
                return i
            else:
                brackets -= 1
        elif c == opening:
            brackets += 1


def split_value(s: str) -> list[str]:
    rec = True
    result = []
    curr_string = ""
    brackets = 0
    for c in s:
        is_w = re.match(r"\s", c)
        if rec and not brackets and is_w:
            rec = False
            result.append(curr_string)
            curr_string = ""
        if not is_w:
            rec = True
            curr_string += c
        elif brackets:
            curr_string += c
        if c == "(":
            brackets += 1
        elif c == ")":
            assert brackets
            brackets -= 1
    if rec:
        result.append(curr_string)
    return result


wb_re = re.compile(r"\b")


def next_wb(string: str, pos: int):
    """
    Find the next word boundary
    """
    if not (match := wb_re.search(string, pos + 1)):
        return max(pos + 1, len(string))
    return match.start()


def prev_wb(string: str, pos: int):
    """
    Find the previos word boundary
    """
    rev_pos = len(string) - pos
    if not (match := wb_re.search(string[::-1], rev_pos + 1)):
        return min(pos - 1, 0)
    return len(string) - match.start()


##########################################################################
