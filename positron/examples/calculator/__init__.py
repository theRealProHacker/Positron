"""
A small calculator app
"""

from main import *
from contextlib import suppress
from .math_parser import calc


@route("/")
async def index():
    load_dom("index.html")

    input = SingleJ("#input")
    result = SingleJ("#result")

    def put_result():
        print("Put result")
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


def main():
    runSync()
