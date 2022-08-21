from config import g
from Element import Element, Selector, parse_selector


def find_in(elem: Element, selector: Selector) -> Element | None:
    """Breadth first search in element"""
    if elem.matches(selector):
        return elem
    for c in elem.real_children:
        if (found := find_in(c, selector)) is not None:
            return found
    return None


# J is inspired by $ from jQuery and is basically an ElementProxy
class SingleJ:
    """
    This represents a single element in the DOM. The user should not interact with the
    DOM Elements directly, instead they should use this class.
    """

    elem: Element

    def __new__(cls, query: str | Element):
        elem: Element
        if isinstance(query, str):
            if (_elem := find_in(g["root"], parse_selector(query))) is None:
                raise RuntimeError(f"Couldn't find an Element that matches '{query}'")
            elem = _elem
        elif isinstance(query, Element):
            elem = query
        else:
            raise TypeError
        self = super().__new__(cls)
        self.elem = elem
        return self


class J:
    """
    The classic JQuery object that includes all elements that match the query.

    Examples (TODO):
    J("a").on("click", print)
    J("input").on("keydown", lambda event: print(event.key))
    """

    singles: list[SingleJ]

    def __init__(self, query: str):
        # Make a list of matching Elements
        selector = parse_selector(query)
        root: Element = g["root"]
        self.singles = [
            SingleJ(elem) for elem in root.iter_desc() if elem.matches(selector)
        ]

    def __getitem__(self, index):
        return self.singles[index]
