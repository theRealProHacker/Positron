"""
This is an emulation of the accesskey HTML attribute
We map from the key button to the id 
"""

from util import create_task
from main import *


@route("/")
async def index():
    load_dom("index.html")

    actions = {
        "k": "#first",
        "l": "#second",
    }

    @J("html").on("keydown")
    def _(event: Event):
        if (id := actions.get(event.code.strip())) is not None:
            create_task(J(id).click())


def main():
    runSync()
