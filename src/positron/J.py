"""
jQuery similar idea

Allows for things like

```py
J('#my-form input[name="email"]').on("input")
def do_something_awesome():
    ...
```

```py
J("#my-form").submit()
```
"""

from __future__ import annotations

import asyncio
from functools import partial, wraps
from inspect import isfunction
from typing import Any, Callable
from contextlib import nullcontext

import positron.config as config
import positron.utils as util
from .config import g
from positron.Element import Element
from .Selector import Selector, parse_selector
from .Style import CompValue, parse_important, process_input
from .utils.func import set_context
from .EventManager import supported_events


def find_in(elem: Element, selector: Selector) -> Element | None:
    """Breadth first search in element"""
    if selector(elem):
        return elem
    for c in elem.real_children:
        if (found := find_in(c, selector)) is not None:
            return found
    return None


# J is inspired by jQuery and is basically an ElementProxy
class SingleJ:
    """
    This represents a single element in the DOM. The user should not interact with the
    DOM Elements directly, instead they should use this class.
    """

    _elem: Element

    def __init__(self, query: str | Element):
        if isinstance(query, str):
            if (_elem := find_in(g["root"], parse_selector(query))) is None:
                raise RuntimeError(f"Couldn't find an Element that matches '{query}'")
            self._elem = _elem
        elif isinstance(query, Element):
            self._elem = query
        else:
            raise TypeError(
                f"query must either be an Element or a selector. Is {type(query)}"
            )

    def on(self, event_type: str, callback=None, repeat: int = -1):
        if callback is None:
            return partial(self.on, event_type, repeat=repeat)

        def inner_callback(event):
            related_target_cm = (
                set_context(event, "related_target", SingleJ(event.related_target))
                if event.related_target is not None
                else nullcontext()
            )
            with set_context(event, "target", self), related_target_cm:
                util.call(callback, event)

        config.event_manager.on(event_type, inner_callback, repeat, target=self._elem)

    def once(self, event_type: str, callback=None):
        return self.on(event_type, callback, 1)

    def set_style(self, attr: str, value: str | CompValue):
        value, important = parse_important(value)
        self._elem.istyle.update(
            {k: (v, important) for k, v in process_input([(attr, value)]).items()}
        )
        g["recompute"] = True

    def __eq__(self, other):
        return self._elem is other._elem

    def data(self, key: str, value: str | None = None) -> str:
        """
        Set or get the data corresponding to the key
        """
        attr = f"data-{key}"
        if value is not None:
            self._elem.attrs[attr] = value
        return self._elem.attrs[attr]


# IDEA: inherit from UserList?
# IDEA: toggle for all kinds of stuff (classes, attributes, event handlers and so on)
class J:
    """
    The classic JQuery object that includes all elements that match the query.

    """

    _singles: list[SingleJ]

    def __init__(self, query: str | list[SingleJ]):
        # Make a list of matching Elements
        if isinstance(query, str):
            selector = parse_selector(query)
            root: Element = g["root"]
            self._singles = [
                SingleJ(elem) for elem in root.iter_desc() if selector(elem)
            ]
        else:
            self._singles = query

    def __getitem__(self, index):
        return self._singles[index]

    def on(self, event_type: str, callback=None, repeat: int = -1):
        """
        Attach an event handler with events of type `event_type`.
        The handler will be called every time the event is emitted but only `repeat` many times

        Examples:

        ```py
        J("a").on("click", print)

        @J("input").on("keydown", repeat = 2)
        def _(event):
            print(event.key)
        ```
        """
        if callback is None:
            return partial(self.on, event_type, repeat=repeat)
        for single in self._singles:
            single.on(event_type, callback, repeat)
        return callback

    def once(self, event_type: str, callback=None):
        """
        Attach an event handler to events of type `event_type` to be called only once

        Examples:

        ```py
        J("input").once("keydown", print)

        J("input").once("keydown")
        def _(event):
            print(event.key)
        ```
        """
        return self.on(event_type, callback, 1)

    # __getattr__ examples
    data: Callable[[str, str | None], list[str]]

    def __getattr__(self, __name: str) -> Any:
        if __name.startswith("__"):
            raise AttributeError
        # XXX: for whatever reason getattr(SingleJ, __name) will always raise ???
        if hasattr(SingleJ, __name) and isfunction(val := getattr(SingleJ, __name)):
            # redirect to singles
            @wraps(val)
            def inner(*args, **kwargs):
                return [
                    getattr(single, __name)(*args, **kwargs) for single in self._singles
                ]

            return inner
        elif __name in supported_events:
            # activate event
            def event_emitter(**kwargs):
                # TODO: what happens with the kwargs? For example with the mouse position on click
                # Possibly we have to implement all these methods individually or at least more specific than this
                # Or at least document this
                return asyncio.wait(
                    [
                        config.event_manager.release_event(
                            __name, single._elem, **kwargs
                        )
                        for single in self._singles
                    ]
                )

            event_emitter.__name__ = __name
            return event_emitter
        raise AttributeError

    def __and__(self, other: J):
        """
        J("div") & J(".red") gives you all .red divs. Equivalent to J("div.red")
        """
        return J(list(set(self._singles) & set(other._singles)))

    def __or__(self, other: J):
        """
        J("p") | J("div") gives you all ps and all divs. Equivalent to J("p, div")
        """
        return J(list(set(self._singles) | set(other._singles)))
