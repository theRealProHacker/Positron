from positron.element.layout.text_align import left, right, center, justify

text = [1, 2, 3, 1, 2]


def test_left():
    assert left(10, text) == [0, 1, 3, 6, 7]


def test_right():
    assert right(10, text) == [1, 2, 4, 7, 8]


def test_center():
    assert center(10, text) == [0.5, 1.5, 3.5, 6.5, 7.5]


def test_justify():
    assert justify(10, text) == [0, 1.25, 3.5, 6.75, 8]
