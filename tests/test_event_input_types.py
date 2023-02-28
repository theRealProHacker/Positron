from positron.events.InputType import *


def test_insert():
    # user presses the "d" button after already having typed "abc"
    insert = Insert("d", 3, EditingMethod.Normal, "abc")
    assert insert.after == "abcd"


def test_delete():
    # user presses backspace after already having typed "abc"
    delete_back_space = Delete(
        3, Delete.What.Content, Delete.Direction.Back, before="abc"
    )
    assert delete_back_space.after == "ab"
    # we can change anything about the Delete but its after attribute is cached
    delete_back_space.pos = 1
    assert delete_back_space.after == "ab"

    delete_word_backword = Delete(
        3, Delete.What.Word, Delete.Direction.Back, before="abc"
    )
    assert delete_word_backword.after == ""


def test_editing_ctx():
    x = EditingContext("")

    x.add_entry(("1", 1, None))
    x.add_entry(("1", 0, None))
    x.add_entry(("21", 1, None))
    x.add_entry(("21", 2, None))

    assert x.peek_back() == ("1", 0, None)
    x.back()
    assert x.current == ("1", 0, None)

    assert x.peek_for() == ("21", 1, None)
    x.forward()
    assert x.current == ("21", 1, None)
