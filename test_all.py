import pygame as pg
import pytest
from pytest import raises

import util
from Box import Box
from Element import (AndSelector, ClassSelector, DirectChildSelector,
                     HasAttrSelector, IdSelector, TagSelector, parse_selector,
                     sngl_p, rel_p, matches)
from J import J
from own_types import Color
from Style import color, join_styles, remove_important, split_units
from WeakCache import FrozenDCache


def test_style_computing():
    assert split_units("3px") == (3, "px")
    assert split_units("0") == (0, "")
    assert split_units("70%") == (70, "%")

    assert color("rgb(120,120,120)", {}) == Color(*(120,) * 3)
    assert color("rgba(120,120,120,120)", {}) == Color(*(120,) * 4)
    assert color("currentcolor", {"color": Color("blue")}) == Color("blue")
    with pytest.raises(ValueError):
        split_units("blue")


def test_css():
    assert remove_important(
        join_styles({"color": ("red", False)}, {"color": ("blue", False)})
    ) == {"color": "red"}
    assert remove_important(
        join_styles({"color": ("red", False)}, {"color": ("blue", True)})
    ) == {"color": "blue"}
    # TODO: Add some more complex tests


def test_selector_parsing():
    for x in ("#id", ".class", "[target]"):
        assert sngl_p.match(x)

    for x in (" ", " > ", "+", "~ "):
        assert rel_p.match(x)
    
    assert matches("p > ", rel_p) == ("p", ">")

    selector = parse_selector("a#hello.dark[target]")
    assert selector == AndSelector(
        (
            TagSelector("a"),
            IdSelector("hello"),
            ClassSelector("dark"),
            HasAttrSelector("target"),
        )
    )
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
    box = Box("content-box", border=(3,) * 4, width=500, height=150, content_width=True)
    assert box.content_box == pg.Rect(0, 0, 500, 150), box.content_box

    box.set_pos((0, 0))
    assert box.content_box == pg.Rect(3, 3, 500, 150), box.content_box
    assert box.outer_box == pg.Rect(0, 0, 500 + 6, 150 + 6), box.outer_box


def test_J():
    with raises(AttributeError):  # should raise because g["root"] is None
        J("somevalidselector")


def test_util():
    tests = {
        # https://developer.mozilla.org/en-US/docs/Web/CSS/integer#examples
        "integer": {
            True: ["12", "+123", "-456", "0", "+0", "-0", "00"],
            False: ["12.0", "12.", "+---12", "ten", "_5", r"\35", "\4E94", "3e4"],
        },
        # https://developer.mozilla.org/en-US/docs/Web/CSS/number#examples
        "number": {
            True: [
                "12",
                "4.01",
                "-456.8",
                "0.0",
                "+0.0",
                "-0.0",
                ".60",
                "10e3",
                "-3.4e-2",
            ],
            False: ["12.", "+-12.2", "12.1.1"],
        },
        # https://developer.mozilla.org/en-US/docs/Web/CSS/dimension
        "dimension": {
            True: ["12px", "1rem", "1.2pt", "2200ms", "5s", "200hz"],
            False: ["12 px", '12"px"'],  # ,"3sec"]
        },
    }
    for name, val in tests.items():
        for b,items in val.items():
            for x in items:
                assert bool(util.check_regex(name,x)) is b


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
