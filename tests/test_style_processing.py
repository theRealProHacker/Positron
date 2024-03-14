from positron.Style import process_property


def test_overflow():
    result = [("overflow-x", "scroll"), ("overflow-y", "scroll")]
    assert process_property("overflow", "scroll scroll") == result
    assert process_property("overflow", "scroll") == result
