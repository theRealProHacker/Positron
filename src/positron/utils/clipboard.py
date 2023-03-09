import pygame as pg
import pygame.scrap as scrap

init = scrap.init


def get_clip() -> str:
    """
    Get the current text value from the clipboard
    """
    # https://www.pygame.org/docs/ref/scrap.html#pygame.scrap.get
    # XXX: Returns bytes|None -> Raises on None
    x: bytes | None = scrap.get(pg.SCRAP_TEXT)  # type: ignore
    if not x:
        return ""
    # byte strings are regularly c-strings and therefore null delimited
    return x.replace(b"\x00", b"").decode()


def put_clip(clip: str):
    """
    Put the current text value into the clipboard
    """
    # https://www.pygame.org/docs/ref/scrap.html#pygame.scrap.put
    # XXX: data needs to be bytes
    scrap.put(pg.SCRAP_TEXT, clip.encode(encoding="ascii"))
