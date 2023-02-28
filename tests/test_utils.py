import io

import positron.utils as util
import positron.utils.colors as color_utils
import positron.utils.regex as regex_utils
from positron.types import Color
from positron.utils.aio import _make_new_filename


# https://stackoverflow.com/a/70016047/15046005
pytest_plugins = ("pytest_asyncio",)


def test_func():
    l = ["one", "two", "three"]
    assert "".join(util.join(*l, div=", ")) == ", ".join(l)

    assert util.tup_replace((1, 2, 2, 2, 4), (2, 4), 3) == (1, 2, 3, 4)

    assert util.in_bounds(3, 4, 5) == 4

    assert util.ensure_suffix("test-box", "-box") == "test-box"
    assert util.ensure_suffix("test", "-box") == "test-box"

    l = [*range(10)]
    for i, x in enumerate(util.consume_list(l)):
        assert x == i
        assert len(l) == 9 - i

    assert util.abs_div(-1 / 2) == -2
    assert util.abs_div(3 / 4) == util.abs_div(4 / 3)

    # just like abs(3-4) == abs(4-3)
    def closest_to(pivot, *xs):  # these are all positive numbers definitely
        return min(
            xs, key=lambda x: util.abs_div(x / pivot)
        )  # the one with the smallest distance to the pivot wins

    closest_to(300, 150, 450) == 450


def test_fs():
    assert _make_new_filename("example.exe") == "example (2).exe"
    assert _make_new_filename("example(1)(2).exe") == "example(1)(3).exe"
    buffer = io.StringIO()
    util.print_once("hello", file=buffer)
    util.print_once("hello", file=buffer)
    assert buffer.getvalue() == "hello\n"


def test_colors():
    assert color_utils.hsl2rgb(0, 1, 0.5) == Color("red")
    assert color_utils.hwb2rgb(0, 0, 0) == Color("red")


def test_regex():
    # finds the period followed by the two spaces and not by the single space.
    # But the regex has to be flipped (First the space, then the period)
    assert (
        regex_utils.rev_groups(r"\s*\.", "I like the rain. But not the sun.  ")[0]
        == ".  "
    )
    # here the idea is to only replace the last x matches
    assert (
        regex_utils.rev_sub(
            r"(\d+)", "123, 124, 124", lambda groups: str(int(groups[0]) + 1), 1
        )
        == "123, 124, 125"
    )


async def test_async():
    # from https://developer.mozilla.org/en-US/docs/Web/HTTP/Basics_of_HTTP/Data_URLs#syntax
    assert await util.fetch_txt("data:,Hello%2C%20World%21") == "Hello, World!"
    assert (
        await util.fetch_txt("data:text/plain;base64,SGVsbG8sIFdvcmxkIQ==")
        == "Hello, World!"
    )
    assert (
        await util.fetch_txt("data:text/html,<script>alert('hi');</script>")
        == "<script>alert('hi');</script>"
    )

    def func(a):
        return a

    async def afunc(b):
        return b

    def kwfunc(a, b=2, d="123"):
        return a, b, d

    def kwargsfunc(a, b, d="123", **kwargs):
        return a, b, d, kwargs

    assert await util.acall(func, 1, 2) == 1
    assert await util.acall(afunc, 1, 2) == 1
    assert await util.acall(kwfunc, 1, d=3) == (1, 2, 3)
    assert await util.acall(kwargsfunc, 1, 2, d=3, e=4) == (1, 2, 3, {"e": 4})
