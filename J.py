from config import g
from Element import Element
from Selectors import Parser, Selector

def find_in(elem: Element, selector: Selector):
    if selector(elem):
        return elem
    for c in elem.iter_children():
        if selector(c):
            return c
    return None

# J is inspired by $ (jQuery) and is basically an ElementProxy
class J:
    _elem: Element
    def __new__(cls, query: str|Element):
        if isinstance(query,str):
            selector = Parser(query).run()
            root: Element = g["root"]
            elem = find_in(root, selector)
            if elem is None:
                return None
            else:
                self = super().__new__(cls)
                self._elem = elem
        else:
            self._elem = query

def test():
    from pytest import raises
    with raises(AttributeError): # should raise because g["root"] is None
        J("something")