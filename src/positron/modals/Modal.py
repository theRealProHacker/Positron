"""
Modals are special UI-Elements that are on top of the DOM. Examples are:

- Fullscreen Mode
- Alert or Prompt
- Context Menu

For this we hold a list of modals that are displayed in config. 
They all have the following API:

- They must have a draw method
- They must have a rect
- They must have a boolean attribute can_escape that says whether 
    the user can escape the modal by clicking besides the modal (default: False)
- They can optionally specify event handlers like onclick, onhover, onactive and similar.
"""

from typing import Protocol

from positron.types import Rect, Surface


class Modal(Protocol):
    rect: Rect
    can_escape: bool = False

    def draw(self, surf: Surface):
        pass
