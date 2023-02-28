"""
https://rawgit.com/w3c/input-events/v1/index.html#interface-InputEvent-Attributes

Generally, there are three kinds of editable elements:

1. Input Elements
2. TextArea Elements
3. Any elements that have contenteditable set to true

We currently only care about input elements. 
Also we only support plain text, so no copying of lists
or any formatting.

cursor positions are always equal to the position of the character after the cursor
|0123 -> 0
012|3 -> 3
"""
import re
from dataclasses import dataclass
from typing import Protocol
from enum import auto

from positron.types import Enum
import positron.utils as utils
from positron.utils.History import History as _History
from positron.utils.regex import GeneralParser, whitespace_re


__all__ = [
    # "Void",
    "Insert",
    "Delete",
    "History",
    "EditingMethod",
    "InputType",
    "EditingContext",
]


class InputType(Protocol):
    before: str
    after: str


class EditingMethod(Enum):
    """
    This Enum answers the question of how plain text was inserted, deleted or replaced
    """

    Normal = auto()
    """ Normal is anything else but the below """
    CutPaste = auto()
    """ Ctrl+V/Ctrl+X """
    DnD = auto()
    """ Drag and Drop with the mouse """


class ApplyDescriptor:
    def __get__(self, obj, type=None) -> str:
        apply = getattr(obj, "apply")
        rv = apply(getattr(obj, "before"))
        setattr(obj, "after", rv)
        return rv


# @dataclass
# class Void:
#     before: str

#     def __post_init__(self):
#         self.after = self.before


@dataclass
class Insert:
    """
    User presses a letter, space, enter or similar

    The type of .pos determines whether this is a Replace operation or a real Insert.

    A real Insert is when pos is an int. A Replace is when pos is a selection (tuple[int, int])

    To check this use `is_insert` and `is_replace` which are mutually exclusive.
    """

    content: str
    pos: int | tuple[int, int]
    method: EditingMethod

    @property
    def start(self):
        return self.pos if isinstance(self.pos, int) else self.pos[0]

    @property
    def end(self):
        return self.pos if isinstance(self.pos, int) else self.pos[1]

    def apply(self, text: str) -> str:
        return "".join([*text[: self.start], *self.content, *text[self.end :]])

    def is_insert(self) -> bool:
        return isinstance(self.pos, int)

    def is_replace(self) -> bool:
        return isinstance(self.pos, tuple)

    before: str
    after = ApplyDescriptor()


_ctrl_ident_re = re.compile(r"[\w_]+|.")


# TODO: Probably join Delete into Insert. A Delete is technically just a Replace with content="".


@dataclass
class Delete:
    class Direction(Enum):
        """
        In which direction the deletion happened
        """

        Unspecified = auto()
        For = auto()
        Back = auto()
        Entire = auto()

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
    dir: Direction = Direction.Unspecified
    method: EditingMethod = EditingMethod.Normal

    def apply(self, text: str):
        match self.what:
            case Delete.What.Content:
                if isinstance(self.pos, tuple):
                    frm, to = self.pos
                else:
                    frm = to = self.pos
                    match self.dir:
                        case Delete.Direction.Back:
                            frm -= 1
                        case Delete.Direction.For:
                            to += 1
                        case _:
                            raise NotImplementedError
                return text[:frm] + text[to:]
            case Delete.What.Word:
                assert isinstance(self.pos, int)
                if self.dir == Delete.Direction.For:
                    # "rea|dy, set, go" -> "rea, set, go"
                    parser = GeneralParser(text[self.pos :])
                    if not parser.consume(whitespace_re):
                        parser.consume(_ctrl_ident_re)
                    return parser.x
                elif self.dir == Delete.Direction.Back:
                    # "rea|dy, set, go" -> "dy, set, go"
                    parser = GeneralParser(text[: self.pos][::-1])
                    parser.consume(whitespace_re)
                    parser.consume(_ctrl_ident_re)
                    return parser.x[::-1]
            case _:
                raise NotImplementedError

    before: str = ""
    after = ApplyDescriptor()


@dataclass
class History:
    """
    Ctrl+Z, Ctrl+Y
    """

    class Type(Enum):
        Undo = auto()
        Redo = auto()

    type: Type
    before: str
    after: str

    @classmethod
    def from_history(cls, type: Type, history: _History):
        after = history.peek_back() if type == History.Type.Undo else history.forward()
        return cls(type, history.current, after[0])

    def execute(self, history: _History):
        if self.type == History.Type.Undo:
            history.back()
        else:
            history.forward()


# class Format:
#   (this is in the far future)
#   things like Ctrl+b (bold), Ctrl+i (italic)

Selection = tuple[int, int] | None


class EditingContext(_History[tuple[str, int, Selection]]):
    """
    An editing context is for every editable element.

    It stores a history of the states the input element was in.

    This includes the value of the input, the cursor and the current selection

    An important invariant that must be uphold is that if there is a selection, the cursor position
    is a boundary of that selection: cursor in selection.

    The other important invariant is that selection[0] < selection[1]. Yeah, that is a strict greater!
    """

    @property
    def value(self):
        return self.current[0]

    @property
    def cursor(self):
        return self.current[1]

    @property
    def selection(self):
        return self.current[2]

    @staticmethod
    def clean_selection(selection):
        match selection:
            case (start, end) if start > end:
                return (end, start)
            case (start, end) if start < end:
                return selection
            case _:
                return None

    def peek_back(self):
        value = self.value
        for x in self[: self.cur][::-1]:
            if x[0] != value:
                return x
        return self.current

    def peek_for(self):
        value = self.value
        for x in utils.after(self, self.cur):
            if x[0] != value:
                return x
        return x

    def back(self):
        value = self.value
        for i in range(self.cur)[::-1]:
            if self[i][0] != value:
                self.cur = i
                return

    def forward(self):
        value = self.value
        while self.current[0] == value and self.cur < len(self) - 1:
            super().forward()

    def __init__(self, value: str = ""):
        self.add_entry((value, 0, None))


"""


class EditingContext:
    \"""
    An editing context is for every editable element.

    It stores a history of the states the input element was in.

    This includes the value of the input, the cursor and the current selection

    An important invariant that must be uphold is that if there is a selection, the cursor position
    is a boundary of that selection: cursor in selection.

    The other important invariant is that selection[0] < selection[1]. Yeah, that is a strict greater!
    \"""

    @property
    def value(self):
        return self.history.current[0]

    @property
    def cursor(self):
        return self.history.current[1]

    @property
    def selection(self):
        return self.history.current[2]

    @staticmethod
    def clean_selection(selection):
        match selection:
            case (start, end) if start > end:
                return (end, start)
            case (start, end) if start < end:
                return selection
            case _:
                return None

    history: _History[tuple[str, int, Selection]]

    def add_entry(self, entry: tuple[str, int, Selection]):
        if entry != self.history.current:
            self.history.add_entry(entry)
        
    def peek_back(self):
        value = self.value
        for x in self.history[:self.history.cur][::-1]:
            if x[0] != value:
                return x
        return self.history.current

    def peek_for(self):
        value = self.value
        h = self.history
        for x in utils.after(h, h.cur):
            if x[0] != value:
                return x
        return self.current

    def back(self):
        value = self.value
        h = self.history
        for i in range(h.cur)[::-1]:
            if h[i][0] != value:
                self.history.cur = i
                return

    def forward(self):
        value = self.value
        h = self.history
        while h.current[0]==value and h.cur < len(h)-1:
            h.forward()


    def __init__(self, value: str = ""):
        self.history = _History()
        self.history.add_entry((value, 0, None))


"""
