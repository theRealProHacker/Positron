from config import g
from Element import Element
from Selector import Selector, parse_selector
from Style import CompValue, parse_important, process_input


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
                event.target = self
                return callback(event)

        g["event_manager"].on(event_type, inner_callback, repeat, target=self._elem)

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

    def data(self):
        return {k[5:]: v for k, v in self._elem.attrs if k.startswith("data-")}


class J:
    """
    The classic JQuery object that includes all elements that match the query.

    Examples:
    J("a").on("click", print)
    J("input").on("keydown", lambda event: print(event.key))
    """

    _singles: list[SingleJ]

    def __init__(self, query: str):
        # Make a list of matching Elements
        selector = parse_selector(query)
        root: Element = g["root"]
        self._singles = [SingleJ(elem) for elem in root.iter_desc() if selector(elem)]

    def __getitem__(self, index):
        return self._singles[index]

    def on(self, event_type: str, callback, repeat: int = -1):
        for single in self._singles:
            single.on(event_type, callback, repeat)

    def once(self, event_type: str, callback):
        for single in self._singles:
            single.on(event_type, callback, 1)
