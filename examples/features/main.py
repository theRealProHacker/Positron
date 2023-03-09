from positron import *
from positron import quit
import positron.config as config


@route("/")  # the index route
async def startpage():
    await aload_dom("first.html")

    i = 0
    colors = ["red", "green", "yellow", "royalblue"]
    alignments = ["left", "right", "center", "justify"]

    @J("button").on("click")
    def _(event: Event):
        nonlocal i
        event.target.set_style("text-align", alignments[i])
        event.target.set_style("background-color", colors[i])
        i = (i + 1) % len(colors)

    @J("html").on("keydown")
    async def _(event: Event):
        if event.code == "escape":
            quit()


config.password_replace_char = "*"
set_cwd(__file__)
set_mode(title="Features")
run("/#link")
