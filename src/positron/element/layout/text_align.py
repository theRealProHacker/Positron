"""
Text align

Should support:

left, right, center, justify

"""

from typing import Iterable, Protocol


class TextAlign(Protocol):
    def __call__(self, max_width: float, widths: list[float]) -> list[float]:
        """
        Aligns a text
        """


def space_left(max_width, widths):
    return max_width - sum(widths)


def _left(widths):
    acc = 0
    for w in widths:
        yield acc
        acc = acc + w


def left(max_width, widths):
    return [*_left(widths)]


def right(max_width, widths):
    l = [*_left(widths)]
    rem = space_left(max_width, widths)
    return [x + rem for x in l]


def center(max_width, widths):
    l = [*_left(widths)]
    rem = space_left(max_width, widths) / 2
    return [x + rem for x in l]
    return [x + rem for x, width in zip(l, widths)]


def justify(max_width, widths):
    l = [*_left(widths)]
    rem = space_left(max_width, widths) / (len(l) - 1)
    return [x + rem * i for i, x in enumerate(l)]


def align_by(alignment, max_width: float, widths: list[float]) -> list[float]:
    return globals()[alignment](max_width, widths)
