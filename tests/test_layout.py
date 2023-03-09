import positron.config as config
import positron.main
from positron.Box import Box, make_box
from positron.Element import HTMLElement
from positron.Style import parse_sheet
from positron.element.layout import BlockLayout


def test_p():
    """
    Tests very basic text layout of a paragraph of text.
    """
    text = """
        <p>
            Lorem, ipsum dolor sit amet consectetur adipisicing elit. Ex veritatis at natus voluptates quos neque autem rerum! Voluptate nihil numquam, molestias commodi, libero fuga facilis magni, placeat labore pariatur enim!
        <p>
    """

    # XXX: To make sure this test works even if settings are
    # altered default style of <p> is altered
    style_sheet = parse_sheet(
        """
        p {
            all: unset
            margin: "1em 0"
        }
        """
    )
    # config.g["default_font_size"] = 16
    positron.main._reset_config()

    html = HTMLElement.from_string(text)
    body = html.children[1]
    p = body.children[0]

    html.apply_style(style_sheet)
    html.compute()

    # html.layout()
    html.box = Box(t="content-box", width=500, height=500)
    html_size = (500, 500)
    assert html.box.width, html.box.height == html_size
    assert html.box.outer_box == html.box.content_box

    # html.layout_inner()
    html.layout_type = BlockLayout(html, [body])
    assert html.layout_type.items == [body]

    # body.layout()
    body.box, _ = make_box(500, body.cstyle, *html_size)
    # should take all available space
    assert body.box.width == 500

    # body.layout_inner()

    # html.rel_pos((0,0))


test_p()
