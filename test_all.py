import pygame as pg
import pytest
from pytest import raises

import Box
import Element
import J
import Style
import util
from Element import (AndSelector, ClassSelector, DirectChildSelector,
                     HasAttrSelector, IdSelector, TagSelector,
                     parse_selector, rel_p, sngl_p)
from own_types import Color, Length, FrozenDCache, Rect, Auto


def test_joint():
    style = Style.remove_important(Style.parse_inline_style("""margin: 0 auto"""))
    assert style == {
        "margin-top":"0",
        "margin-right": "auto",
        "margin-bottom":"0",
        "margin-left": "auto"
    }
    comp_style = {
        k:Element.process_style("test", v, k, {}) for k,v in style.items()
    }
    assert comp_style == {
        "margin-top": Length(0),
        "margin-right": Auto,
        "margin-bottom":Length(0),
        "margin-left": Auto
    }
    margin = Style.mrg_getter(comp_style)
    assert margin[Box._horizontal] == (Auto, Auto)
    assert margin[Box._vertical] == (Length(0), Length(0))

    style = Style.remove_important(
        Style.parse_inline_style("""
        margin: 20px auto;padding:10px;border:solid medium;width:200px;height:200px;box-sizing: border-box
        """)
    )
    comp_style = {
        k:Element.process_style("test", v, k, {}) for k,v in style.items()
    }
    box,set_height = Box.make_box(900,comp_style,900,600)
    assert set_height == util.noop # height is defined
    mrg_r_l = (900-200-3*2-10*2)/2
    assert box == Box.Box(
        "border-box",
        margin = (20,mrg_r_l,20,mrg_r_l),
        border = (3,)*4,
        padding = (10,)*4,
        width = 200,
        height = 200,
    )
    

def test_own_types():
    # clock-wise rotation
    assert Rect(0,0,400,400).corners == (
        (0,0), (400,0), (400,400), (0,400)
    )

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
    assert Style.split_units("3px") == (3, "px")
    assert Style.split_units("0")   == (0, "")
    assert Style.split_units("70%") == (70, "%")
    with pytest.raises(AttributeError):
        Style.split_units("blue")
        
    assert Style.length("3px", {})  == Length(3)

    assert Style.color("rgb(120,120,120)", {})      == Color(*(120,) * 3)
    assert Style.color("rgba(120,120,120,120)", {}) == Color(*(120,) * 4)
    assert Style.color("currentcolor", {"color": Color("blue")}) == Color("blue")
    assert Style.color("#fff", {}) == Style.color("#ffffff", {}) == Color("white")
    assert Style.color("#000", {}) == Style.color("#000000", {}) == Color("black")

    assert Style.split("solid rgb(11, 18, 147) 3px") == [
        "solid",
        "rgb(11,18,147)",
        "3px",
    ]
    # TODO
    with raises(AssertionError):
        assert Style.split("""oblique 10px 'Courier New' , Courier      
        , monospace;""") == [
            "oblique",
            "10px",
            "'Courier New',Courier,monospace",
        ]

    # TODO: Add some more complex tests
    assert Style.remove_important(
        Style.join_styles({"color": ("red", False)}, {"color": ("blue", False)})
    ) == {"color": "red"}
    assert Style.remove_important(
        Style.join_styles({"color": ("red", False)}, {"color": ("blue", True)})
    ) == {"color": "blue"}

    # https://developer.mozilla.org/en-US/docs/Web/CSS/margin#syntax
    assert Style.process_dir(
        ["1em"]
    ) == ['1em', '1em', '1em', '1em']
    assert Style.process_dir(
        "5% auto".split()
    ) == ['5%', 'auto', '5%', 'auto']
    assert Style.process_property(
        "margin", "1em auto 2em"
    ) == {
        "margin-top": "1em",
        "margin-right": "auto",
        "margin-bottom": "2em",
        "margin-left": "auto",
    }
    assert Style.process_property(
        "margin", "2px 1em 0 auto"
    ) == {
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
    assert Style.process_property(
        "border-radius", "1em/5em"
    ) == {
        "border-top-left-radius": "1em 5em",
        "border-top-right-radius": "1em 5em",
        "border-bottom-right-radius": "1em 5em",
        "border-bottom-left-radius": "1em 5em",
    }
    assert Style.is_valid("border-width", "medium")
    assert Style.is_valid("border-style", "solid")
    assert Style.is_valid("border-color", "black")
    assert Style.process_property("border", "solid") == {
        "border-style": "solid"
    }



def test_selector_parsing():
    for x in ("#id", ".class", "[target]"):
        assert sngl_p.match(x)

    for x in (" ", " > ", "+", "~ "):
        assert rel_p.match(x)

    assert Element.matches("p > ", rel_p) == ("p", ">")

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
    box = Box.Box("content-box", border=(3,) * 4, width=500, height=150, content_width=True)
    assert box.content_box == pg.Rect(0, 0, 500, 150), box.content_box

    box.pos = (0,0)
    assert box.content_box == pg.Rect(3, 3, 500, 150), box.content_box
    assert box.outer_box == pg.Rect(0, 0, 500 + 6, 150 + 6), box.outer_box


def test_J():
    with raises(AttributeError):  # should raise because g["root"] is None
        J.SingleJ("somevalidselector")


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
                "12.",
            ],
            False: ["+-12.2", "12.1.1"],
        },
        # https://developer.mozilla.org/en-US/docs/Web/CSS/dimension
        "dimension": {
            True: ["12px", "1rem", "1.2pt", "2200ms", "5s", "200hz"],
            False: ["12 px", '12"px"'],  # ,"3sec"]
        },
    }
    for name, val in tests.items():
        for b, items in val.items():
            for x in items:
                assert bool(util.check_regex(name, x)) is b


if __name__ == "__main__":
    for k, v in globals().items():
        if k.startswith("test_"):
            v()