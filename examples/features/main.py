from positron import *


@route("/")  # the index route
def startpage():
    load_dom("first.html")

    colors = ["red", "green", "yellow", "royalblue"]

    @J("button").on("click")
    def _(event: Event):
        color = colors.pop(0)
        colors.append(color)
        event.target.set_style("background-color", color)


set_cwd(__file__)
runSync("/#link")
