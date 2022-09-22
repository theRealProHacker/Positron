"""
This module is responsible for parsing HTML to `Elements`
"""
import lxml.html.html5parser as html5

import Element
from util import get_tag
from own_types import BugError

elem_type_map: dict[str, type[Element.Element]] = {
    "html": Element.HTMLElement,
    "img": Element.ImgElement,
    "audio": Element.AudioElement,
    "br": Element.BrElement,
    "title": Element.TitleElement,
    "link": Element.LinkElement,
    "style": Element.StyleElement,
    "comment": Element.CommentElement,
}


def lxml_to_element(lxml_elem, parent: Element.Element | None) -> Element.Element:
    elem: Element.Element
    tag = get_tag(lxml_elem)
    type_ = elem_type_map.get(tag, Element.Element)
    children: list[Element.Element | Element.TextElement] = []
    text = (lxml_elem.text or "").strip()
    if type_ is Element.HTMLElement:
        elem = Element.HTMLElement("html", {}, None)
    else:
        assert parent is not None
        if issubclass(type_, Element.MetaElement):
            elem = type_(lxml_elem.attrib, text, parent)
        else:
            elem = type_(tag, lxml_elem.attrib, parent)
    children = []
    if text:
        children.append(Element.TextElement(text, elem))
    for _c in lxml_elem:
        c = lxml_to_element(_c, parent=elem)
        children.append(c)
        if _text := (_c.tail or "").strip():
            children.append(Element.TextElement(_text, elem))
    elem.children = children
    assert isinstance(elem, Element.Element)
    return elem


parser = html5.HTMLParser()


def parse_dom(html: str) -> Element.HTMLElement:
    _root = html5.document_fromstring(html, parser=parser)
    root = lxml_to_element(_root, parent=None)
    assert type(root) is Element.HTMLElement, BugError(
        f"root is not an HTMLElement, {_root} {root}"
    )
    return root
