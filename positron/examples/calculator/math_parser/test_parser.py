from pytest import raises
from .explicit import calc as explicit_calc
from .implicit import calc as implicit_calc


def calc_test(calc):
    assert calc("1+4") == 5
    assert calc("-4-2") == -6
    assert calc("-3*-5") == 15
    assert calc("20/-4") == -5
    assert calc("2*3+5") == 11
    assert calc("2*(3+5)") == 16
    ...
    for error in [
        "not True",
        "2//3",
        "nonsense",
        "print('I\\'m a hacker')",
        "this is a syntax error",
    ]:
        with raises(SyntaxError):
            calc(error)


def test():
    for calc in (explicit_calc, implicit_calc):
        calc_test(calc)


if __name__ == "__main__":
    test()
