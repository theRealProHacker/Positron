"""
A small calculator app
"""

from contextlib import suppress

from math_evaluator import calc

from main import *


@route("/")
async def index():
    load_dom("index.html")

    input = SingleJ("#input")
    result = SingleJ("#result")

    def put_result():
        with suppress(SyntaxError):
            result._elem.value = str(calc(input._elem.value))

    @J("button").on("click")
    def _(event: Event):
        # TODO: make text and value public
        text = event.target._elem.text.strip()
        if text == "C":
            input._elem.value = input._elem.value[:-1]
        else:
            input._elem.value += text
        put_result()

    input.on("input")(put_result)
