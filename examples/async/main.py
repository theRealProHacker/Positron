from positron import *
import time
import asyncio

from random import randint

def sync_click():
    time.sleep(10)
    return randint(0, 100)

async def async_click():
    await asyncio.sleep(10)
    return randint(0, 100)

async def sync_async_click():
    await asyncio.to_thread(time.sleep, 10)
    return randint(0, 100)

@route("/")
def main():
    load_dom("index.html")

    input = SingleJ("input")

    @SingleJ("#button").on("click")
    async def _():
        input._elem.value = "Loading ..."
        r = await sync_async_click()
        input._elem.value = f"Done! {r}"

set_config(
    fps = 30,
)

set_cwd(__file__)
run("/")
