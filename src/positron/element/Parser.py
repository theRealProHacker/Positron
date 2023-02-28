import html5lib


def parse(html: str):
    return html5lib.parse(html)


def get_tag(elem) -> str:
    """
    Get the tag of an _XMLElement or "comment" if the element has no valid tag
    """
    return (
        elem.tag.removeprefix("{http://www.w3.org/1999/xhtml}").lower()
        if isinstance(elem.tag, str)
        else "!comment"
    )
