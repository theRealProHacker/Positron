enabled = True
try:
    import mistune
except ImportError:
    enabled = False


def to_html(markdown: str)->str:
    return mistune.html(markdown)
