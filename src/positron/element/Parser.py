import html5lib


def parse(html: str):
    return html5lib.parse(html)
