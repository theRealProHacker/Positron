"""
A key logger application.
Prints all relevant metadata of a keydown event to the console on every keydown.
Helpful for understanding the different keydown event attributes. 
"""

from positron import *


@route("/")
async def index():
    await aload_dom_frm_str("")

    @J("html").on("keydown")
    def _(event):
        print("Key:", event.key)
        print("Code:", event.code)
        print("Pygame Code:", event.pgcode)
        print("Modifiers:", event.mods)


set_cwd(__file__)
run("/")
