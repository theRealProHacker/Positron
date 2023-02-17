"""
A small calculator app
"""

from contextlib import suppress

from positron import *
from math_evaluator import calc


@route("/")
async def index():
    load_dom("index.html")

    input = SingleJ("#input")
    result = SingleJ("#result")

    @input.on("input")
    def _():
        if not input._elem.value:
            result._elem.value = ""
            return
        with suppress(SyntaxError):
            result._elem.value = str(calc(input._elem.value))


set_cwd(__file__)
runSync("/")
