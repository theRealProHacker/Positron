import pytest
import pygame as pg
from Box import Box
from StyleComputing import split_units, color
from own_types import Color
from CSS import join_styles, remove_important


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
    from Element import (
        sngl_p,
        parse_selector,
        AndSelector,
        TagSelector,
        ClassSelector,
        HasAttrSelector,
        IdSelector,
        DirectChildSelector,
        matches,
        RT
    )

    for x in ("#id", ".class", "[target]"):
        assert sngl_p.match(x)
    for x in (">",):
        assert matches(x) == ('',RT.Rel,'>')

    selector = parse_selector("a#hello.dark[target]")
    assert selector == AndSelector(
        (
            TagSelector("a"),
            IdSelector("hello"),
            ClassSelector("dark"),
            HasAttrSelector("target"),
        )
    )
    selector = parse_selector("div>a#hello.dark[target]")
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
    box = Box(
        "content-box",
        border = (3,)*4,
        width = 500,
        height = 150,
        content_width = True
    )
    assert box.content_box == pg.Rect(
        0,0, 500, 150
    ), box.content_box

    box.set_pos((0,0))
    assert box.content_box == pg.Rect(
        3,3, 500, 150
    ), box.content_box
    assert box.outer_box == pg.Rect(
        0,0, 500+6, 150+6
    ), box.outer_box
