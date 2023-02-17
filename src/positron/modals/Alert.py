"""
There are three types of alerts:

1. Alert: A title, message and an OK-Button
2. Confirm: Ask the user for confirmation on something: 
    "Are you sure you want to delete these files forever?"
    -> Returns a bool
3. Prompt: Displays an Input Field with Ok and Cancel
    -> None on cancel, a String on Ok
"""

from positron.config import g
from positron.modals.Modal import Modal
from positron.types import Rect, Surface


class Alert(Modal):
    rect = Rect(0, 0, max(g["W"], 175), max(g["H"], 500))

    def __init__(self, title: str, msg: str, can_escape: bool):
        self.title = title
        self.msg = msg
        self.can_escape = can_escape

    def layout(self, rect: Rect):
        """
        Layouts the alert by calculating its expected rect and then centering it in the screen
        """
        height = 0
        # TODO: layout title
        # TODO: layout msg
        # TODO: layout button
        height += 500
        width = max(rect.width // 3, 175)
        rect = Rect(0, 0, width, height)

    def draw(self, surf: Surface):
        ...
