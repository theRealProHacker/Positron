"""
https://rawgit.com/w3c/input-events/v1/index.html#interface-InputEvent-Attributes

Generally, there are three kinds of editable elements:

1. Input Elements
2. TextArea Elements
3. Any elements that have contenteditable set to true

We currently only care about input elements. 
Also we only support plain text, so no copying of lists
or any formatting.

However, we do want to support a History for every editing
context. Every InputElement must have an EditingContext that
remembers its history, and maybe other things like the 
current cursor position in that EditingContext

cursor positions are always equal to the position of the character after the cursor
|0123 -> 0
012|3 -> 3
"""
import re
from dataclasses import dataclass
from typing import Protocol
from enum import auto

from positron.types import Enum
from positron.utils.History import History as _History
from positron.utils.regex import GeneralParser, whitespace_re


__all__ = ["Insert", "Replace", "Delete", "History", "EditingMethod", "InputType"]


class InputType(Protocol):
    before: str
    after: str


class EditingMethod(Enum):
    """
    This Enum answers the question of how plain text was inserted, deleted or replaced
    """

    Normal = auto()
    """ Normal is anything else but the below """
    Cut = auto()
    """ Ctrl+X """
    Paste = auto()
    """ Ctrl+V """
    DnD = auto()
    """ Drag and Drop with the mouse """


class ApplyDescriptor:
    # def __new__(self, *args) -> str:
    #     ...
    def __get__(self, obj, type=None) -> str:
        apply = getattr(obj, "apply")
        rv = apply(getattr(obj, "before"))
        setattr(obj, "after", rv)
        return rv


@dataclass
class Insert:
    """
    User presses a letter, space, enter or similar
    """

    content: str
    pos: int
    method: EditingMethod

    def apply(self, text: str) -> str:
        return "".join([*text[: self.pos], *self.content, *text[self.pos :]])

    before: str
    after = ApplyDescriptor()


@dataclass
class Replace:
    """
    User selects text and then inserts other text.
    This will delete the selected text and also insert the new text
    """

    content: str
    range: tuple[int, int]
    method: EditingMethod

    def apply(self, text: str) -> str:
        start, end = self.range
        return "".join([*text[:start], *self.content, *text[end:]])

    before: str
    after = ApplyDescriptor()


_ctrl_ident_re = re.compile(r"[\w_]+|.")


@dataclass
class Delete:
    class Direction(Enum):
        """
        In which direction the deletion happened
        """

        unspecified = auto()
        forward = auto()
        backward = auto()
        entire = auto()

    class What(Enum):
        """
        Describes what is deleted
        """

        Content = auto()
        """
        Anything that is not included in the other Whats
        """
        Word = auto()
        """
        Ctrl+Backspace or Ctrl+Del depending on delete direction
        """
        SoftLine = auto()
        HardLine = auto()
        """
        Shift+Del
        """

    # int or range depending on thing
    pos: int | tuple[int, int]
    what: What
    dir: Direction

    def apply(self, text: str):
        match self.what:
            case Delete.What.Content:
                if isinstance(self.pos, int):
                    if self.dir == Delete.Direction.backward:
                        return text[: self.pos-1] + text[self.pos :]
                    elif self.dir == Delete.Direction.forward:
                        return text[: self.pos] + text[self.pos+1 :]
                    else:
                        raise NotImplementedError
                else:
                    raise NotImplementedError
            case Delete.What.Word:
                assert isinstance(self.pos, int)
                if self.dir == Delete.Direction.forward:
                    # "rea|dy, set, go" -> "rea, set, go"
                    parser = GeneralParser(text[self.pos :])
                    if not parser.consume(whitespace_re):
                        parser.consume(_ctrl_ident_re)
                    return parser.x
                elif self.dir == Delete.Direction.backward:
                    # "rea|dy, set, go" -> "dy, set, go"
                    parser = GeneralParser(text[: self.pos][::-1])
                    parser.consume(whitespace_re)
                    parser.consume(_ctrl_ident_re)
                    return parser.x[::-1]
            case _:
                raise NotImplementedError

    before: str
    after = ApplyDescriptor()


@dataclass
class History:
    """
    Ctrl+z, Ctrl+Y
    """

    class Type(Enum):
        Undo = auto()
        Redo = auto()

    type: Type
    before: str
    after: str


# class Format (this is in the far future)
# things like Ctrl+b (bold), Ctrl+i (italic)


class EditingContext:
    """
    An editing context is special for every editable element.
    """

    his: _History[str]

    def __init__(self, value: str):
        self.his = _History([value])
