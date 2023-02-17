# fmt: off
import io
import math
from operator import sub

import pygame as pg
import pytest
from pytest import raises

import positron.Box as Box
import positron.J as J
import positron.Style as Style
import positron.util as util
import positron.utils.colors as color_utils
import positron.utils.Navigator as Navigator
import positron.utils.regex as regex_utils
from positron.types import Auto, Color, FrozenDCache, Length, Percentage, Rect
from positron.Selector import (AndSelector, ClassSelector, DirectChildSelector,
                      HasAttrSelector, IdSelector, TagSelector, matches,
                      parse_selector, rel_p, sngl_p)
from positron.Style import parse_sheet

# fmt: on

# https://stackoverflow.com/a/70016047/15046005
pytest_plugins = ("pytest_asyncio",)


def test_joint():
    style = Style.remove_importantd(
        Style.parse_inline_style("""margin: calc(100%-30px) auto""")
    )
    assert style == {
        "margin-top": Style.AddOp(Style.Percentage(100), sub, Length(30)),
        "margin-right": Auto,
        "margin-bottom": Style.AddOp(Style.Percentage(100), sub, Length(30)),
        "margin-left": Auto,
    }
    margin = Style.mrg_getter(style)
    assert margin[Box._horizontal] == (Auto, Auto)
    assert Style.Calculator().multi2(margin[Box._vertical], 0, 300) == (
        300 - 30,
        300 - 30,
    )

    style = Style.remove_importantd(
        Style.parse_inline_style(
            """
            margin: 20px auto;padding:10px;border:solid medium;width:200px;height:200px;box-sizing: border-box
            """
        )
    )
    comp_style = {k: Style.compute_style("test", v, k, {}) for k, v in style.items()}
    box, set_height = Box.make_box(900, comp_style, 900, 600)
    assert set_height == util.noop  # height is defined
    mrg_r_l = (900 - 200 - 3 * 2 - 10 * 2) / 2
    assert box == Box.Box(
        "border-box",
        margin=(20, mrg_r_l, 20, mrg_r_l),
        border=(3,) * 4,
        padding=(10,) * 4,
        width=200,
        height=200,
    )


def test_own_types():
    # clock-wise rotation
    assert Rect(0, 0, 400, 400).corners == ((0, 0), (400, 0), (400, 400), (0, 400))


def test_navigator():
    history = Navigator.history
    history.add_entry("Some url")
    history.add_entry("other url")
    assert history == ["Some url", "other url"]
    assert not history.can_go_forward()
    history.back()
    assert not history.can_go_back()
    history.back()
    history.back()
    assert not history.can_go_back()
    assert history.current == "Some url"
    history.forward()
    assert history.current == "other url"

    for url in [
        "https://docs.python.org/3/library/urllib.parse.html#module-urllib.parse",
        "www.google.com/search?query=Python",
    ]:
        assert str(Navigator.make_url(url)) == url
    # XXX: the above does not hold true for any URL. For example:
    url = "/path?"
    assert str(Navigator.make_url(url)) == "/path"


def test_cache():
    test_cache = FrozenDCache()
    style1 = {
        "display": "block",
        "margin-top": "1em",
        "margin-bottom": "1em",
    }
    style2 = style1.copy()

    # 1. Insert dict works
    style3 = test_cache.add(style1)
    assert len(test_cache) == 1
    assert style3 is not style1

    # 2. when adding another element the cache doesn't grow
    style4 = test_cache.add(style2)
    assert len(test_cache) == 1

    # 3. and returns the found value
    style3 is style4

    # 4. when we delete the reference to the cache item, the cache gets cleared
    del style1
    del style2
    style3 = None
    del style4
    assert len(test_cache) == 0


def test_style_computing():
    # Helpers
    assert Style.match_bracket("3px+(5*12px))+(5px+6px)") == len("3px+(5*12px))") - 1
    assert Style.css_func("rgb(255, 255, 255)", "rgb") == ["255", "255", "255"]
    assert Style.split_units("3px") == (3, "px")
    assert Style.split_units("70%") == (70, "%")
    with pytest.raises(AttributeError):
        Style.split_units("blue")
    assert Style.split_value("solid rgb(11, 18, 147) 3px") == [
        "solid",
        "rgb(11, 18, 147)",
        "3px",
    ]

    # Acceptors
    assert Style.number("120") == 120
    assert Style.length("120px") == Length(120)
    assert Style.color("rgba(120, 120, 120, 1)", {}) == Color(*(120,) * 3, 255)
    assert Style.color("currentcolor", {"color": Color("blue")}) == Color("blue")
    assert Style.color("#c0ffee", {}) == Color(192, 255, 238)
    # https://developer.mozilla.org/en-US/docs/Web/CSS/color#making_text_red
    inputs = [
        "red",
        "#f00",
        "#ff0000ff",
        "rgb(255,0,0)",
        "rgb(100%, 0%, 0%)",
        "hsl(0, 100%, 50%)",
        "hwb(0 0% 0% / 1)",
        "rgb(calc(50%*pi), 0, 0)",  # 50%*pi is clamped to 100%
        "hsl(0πrad 100% 50%)",
    ]
    assert util.all_equal([Style.color(i, {}) for i in inputs])

    # Calc
    assert Style.AddOp(Percentage(100), sub, Length(30)).get_type() == Length
    assert Style.length("3px") == Length(3)
    assert Style.length("calc(3px)") == Length(3)
    assert Style.length("calc(3*5)") is None
    assert Style.length("calc(3px*calc(5+3))") == Length(24)
    assert Style.length("calc(pi*(1+e)*1px)") == Length(math.pi + math.e * math.pi)
    assert Style.length_percentage("calc(100% -30px)") == Style.AddOp(
        Percentage(100), sub, Length(30)
    )
    with raises(KeyError):
        Style.style_attrs["width"].accept("var(--my-width)", {})

    with raises(KeyError):
        Style.style_attrs["width"].accept("3em", {})  # em accesses font-size
    # TODO
    with raises(AssertionError):
        assert Style.split_value(
            """oblique 10px 'Courier New' , Courier , monospace"""
        ) == [
            "oblique",
            "10px",
            "'Courier New' , Courier , monospace",
        ]

    assert Style.is_valid("border-width", "medium") is not None
    assert Style.is_valid("border-style", "solid") is not None
    assert Style.is_valid("border-color", "black") is not None
    assert dict(Style.process_property("border", "solid")) == {
        "border-style": Style.CompStr("solid")
    }
    # https://developer.mozilla.org/en-US/docs/Web/CSS/margin#syntax
    assert Style.process_dir(["1em"]) == ["1em", "1em", "1em", "1em"]
    assert Style.process_dir("5% auto".split()) == ["5%", "auto", "5%", "auto"]
    assert dict(Style.process_property("margin", "1em auto 2em")) == {
        "margin-top": "1em",
        "margin-right": "auto",
        "margin-bottom": "2em",
        "margin-left": "auto",
    }
    assert dict(Style.process_property("margin", "2px 1em 0 auto")) == {
        "margin-top": "2px",
        "margin-right": "1em",
        "margin-bottom": "0",
        "margin-left": "auto",
    }
    """ https://developer.mozilla.org/en-US/docs/Web/CSS/border-radius#syntax
    border-radius: 1em/5em;

    /* It is equivalent to: */
    border-top-left-radius:     1em 5em;
    border-top-right-radius:    1em 5em;
    border-bottom-right-radius: 1em 5em;
    border-bottom-left-radius:  1em 5em;
    """
    assert dict(Style.process_property("border-radius", "1em/5em")) == {
        "border-top-left-radius": "1em 5em",
        "border-top-right-radius": "1em 5em",
        "border-bottom-right-radius": "1em 5em",
        "border-bottom-left-radius": "1em 5em",
    }
    # precalculates values that are definitely always the same
    assert Style.process_property("width", "15px") == Length(15)


def test_selector_parsing():
    for x in ("#id", ".class", "[target]"):
        assert sngl_p.match(x)

    for x in (" ", " > ", "+", "~ "):
        assert rel_p.match(x)

    assert matches("p > ", rel_p) == ("p", ">")

    selector = parse_selector("div > a#hello.dark[target]")
    assert selector == DirectChildSelector(
        (
            TagSelector("div"),
            AndSelector(
                (
                    TagSelector("a"),
                    IdSelector("hello"),
                    ClassSelector("dark"),
                    HasAttrSelector("target"),
                )
            ),
        )
    )


def test_boxes():
    Box.mutate_tuple((1, 2), 3, 0) == (3, 2)
    box = Box.Box(
        "content-box", border=(3,) * 4, width=500, height=150, outer_width=True
    )
    assert box.content_box == pg.Rect(0, 0, 500 - 6, 150), box.content_box

    box.set_pos((0, 0))
    assert box.content_box == pg.Rect(3, 3, 500 - 6, 150), box.content_box
    assert box.outer_box == pg.Rect(0, 0, 500, 150 + 6), box.outer_box

    box = Box.Box(
        "content-box",
        (
            0,
            20,
        )
        * 2,
        (3,) * 4,
        (10,) * 4,
        100,
        100,
        outer_width=True,
    )
    assert box.width == 100 - 2 * (20 + 3 + 10)


def test_J():
    with raises(AttributeError):  # should raise because g["root"] is None
        J.SingleJ("somevalidselector")


def test_util():
    assert util.tup_replace((1, 2, 2, 2, 4), (2, 4), 3) == (1, 2, 3, 4)
    assert util.in_bounds(3, 4, 5) == 4
    assert util.ensure_suffix("test-box", "-box") == "test-box"
    assert util.ensure_suffix("test", "-box") == "test-box"
    l = [*range(10)]
    for i, x in enumerate(util.consume_list(l)):
        assert x == i
        assert len(l) == 9 - i
    assert util._make_new_filename("example.exe") == "example (2).exe"
    assert util._make_new_filename("example(1)(2).exe") == "example(1)(3).exe"
    buffer = io.StringIO()
    util.print_once("hello", file=buffer)
    util.print_once("hello", file=buffer)
    assert buffer.getvalue() == "hello\n"
    # Colors
    assert color_utils.hsl2rgb(0, 1, 0.5) == Color("red")
    assert color_utils.hwb2rgb(0, 0, 0) == Color("red")
    # Regex
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
    assert util.abs_div(-1 / 2) == -2
    assert util.abs_div(3 / 4) == util.abs_div(4 / 3)

    # just like abs(3-4) == abs(4-3)
    def closest_to(pivot, *xs):  # these are all positive numbers definitely
        return min(
            xs, key=lambda x: util.abs_div(x / pivot)
        )  # the one with the smallest distance to the pivot wins

    closest_to(300, 150, 450) == 450


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


def test_media_queries():
    sheet = Style.parse_sheet(
        """
        @media (max-width: 600px) {}
        """
    )
    rule = sheet[0]
    assert isinstance(rule, Style.MediaRule)
    assert rule.matches((500, 300))
    assert not rule.matches((700, 700))


if __name__ == "__main__":
    pytest.main()
