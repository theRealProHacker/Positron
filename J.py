from config import g
from Element import Element, parse_selector, Selector

def find_in(elem: Element, selector: Selector)->Element|None:
    """Breadth first search in element"""
    if elem.matches(selector): 
        return elem
    for c in elem.real_children:
        find_in(c, selector)
    return None

# J is inspired by $ from jQuery and is basically an ElementProxy
class J:
    _elem: Element
    def __new__(cls, query: str|Element):
        if isinstance(query,str):
            selector = parse_selector(query)
            root: Element = g["root"]
            elem = find_in(root, selector)
            if elem is None:
                return None
            else:
                self = super().__new__(cls)
                self._elem = elem
                return self
        elif isinstance(query, Element):
            self._elem = query
        else:
            raise TypeError
