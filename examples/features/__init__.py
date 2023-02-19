from main import *


@route("/")  # the index route
def startpage():
    load_dom("example.html")

    colors = ["red", "green", "yellow", "royalblue"]

    @J("button").on("click")
    def _(event: Event):
        color = colors.pop(0)
        colors.append(color)
        event.target.set_style("background-color", color)


def main():
    runSync("/#link")
