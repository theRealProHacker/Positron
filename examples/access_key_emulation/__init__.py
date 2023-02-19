"""
This is an emulation of the accesskey HTML attribute
We map from the key button to the id 
"""

from positron.util import create_task
from positron.main import route, load_dom, Event, J


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
