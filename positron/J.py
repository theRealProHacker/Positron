from __future__ import annotations

import config
from config import g
from Element import Element
from Selector import Selector, parse_selector
from Style import CompValue, parse_important, process_input
from util import set_context


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
            raise TypeError("query must either be an Element or a selector")

    def on(self, event_type: str, callback, repeat: int = -1):
        def inner_callback(event=None):
            if event is None:
                return callback()
            else:
                with set_context(event, "target", self):
                    callback(event)

        config.event_manager.on(event_type, inner_callback, repeat, target=self._elem)

    def once(self, event_type: str, callback):
        return self.on(event_type, callback, 1)

    def set_style(self, attr: str, value: str | CompValue):
        value, important = parse_important(value)
        self._elem.istyle.update(
            {k: (v, important) for k, v in process_input([(attr, value)]).items()}
        )
        g["recompute"] = True

    def __eq__(self, other):
        return self.elem is other.elem

    def data(
        self,
    ):
        """ """
        return {k[5:]: v for k, v in self._elem.attrs if k.startswith("data-")}


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

    def on(self, event_type: str, callback=None, *, repeat: int = -1):
        """
        Attach an event handler with events of type `event_type`.
        The handler will be called every time the event is emitted but only `repeat` many times

        Examples:

        ```py
        J("a").on("click", print)

        J("input").on("keydown", repeat = 2)
        def _(event):
            print(event.key)
        ```
        """
        if callback is None:

            def inner(callback):
                self.on(event_type, callback, repeat)

            return inner
        for single in self._singles:
            single.on(event_type, callback, repeat)
        return callback

    def once(self, event_type: str, callback=None):
        """
        Attach an event handler to events of type `event_type` to be called only once
        """
        if callback is None:

            def inner(callback):
                self.once(event_type, callback)

            return inner
        for single in self._singles:
            single.on(event_type, callback, 1)
        return callback

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

    def __index__(self, index):
        raise NotImplementedError()
