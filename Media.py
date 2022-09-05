"""
This file includes Media classes like Image, Video or Audio
"""
import asyncio
import os
import time

import pygame as pg

from config import g
from own_types import Dimension, Surface
import util

image_cache: dict[str, "Image"] = {}

async def prefetch_image(url):
    file = await util.download(url)
    # The image isn't loaded into memory
    image_cache[url] = Image(file.name, load=False)

class Image:
    """
    Represents a (still) Image. Can either be in a state of loading, loaded or unloaded
    """
    loading_task: util.Task
    def __new__(cls, url: str, load: bool = True, sync: bool = False, *args, **kwargs):
        if (image := image_cache.get(url)) is None:
            image_cache[url] = image = super().__new__(cls)
        elif load and not image.is_loaded: # the image is already in the cache but not loaded
            image.init_load()
        elif sync: 
            image.loading_task.sync = True
        return image
        
    def __init__(self, url: str, load: bool = True, sync: bool = False):
        self.url = url
        self.surf = None
        self.unloaded = True
        if load:
            self.init_load()
            self.loading_task.sync = sync
        self.last_used = time.monotonic()

    @property
    def is_loaded(self):
        return self.surf is not None

    @property
    def size(self):
        return self.surf.get_size()

    async def async_load(self):
        try:
            self.url = (await util.download(self.url)).name
            self.surf = await asyncio.to_thread(pg.image.load,self.url)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            util.log_error(e)
            # TODO: Use fallbacks

    def init_load(self):
        """
        Start loading the image into memory. But instantly return the `Image`. 
        You only need to call this if you init with `load=false` or unload the image
        """
        if not self.is_loaded:
            self.loading_task = util.create_task(self.async_load())
            g["tasks"].append(self.loading_task)
        self.unloaded = False
        self.last_used = time.monotonic()
        return self

    def unload(self):
        """
        Unload the image from memory (to save RAM). 
        This could for example be used when the image is not visible anymore.
        """
        self.loading_task.cancel()
        self.surf = None
        self.unloaded = True
        return self

    def draw(self, screen: Surface, pos: Dimension):
        if self.surf is not None:
            screen.blit(self.surf, pos)
        elif self.unloaded:
            self.init_load()
        self.last_used = time.monotonic()

    def __repr__(self):
        return f"Image({self.url})"


class Audio:
    sound: pg.mixer.Sound

    def __init__(self, url: str, load: bool = True, autoplay: bool = True, loop: bool = False):
        self.url = url
        self.autoplay = autoplay
        self.loop = loop
        self.unloaded = False
        if autoplay or load:
            self.init_load()
        self.last_used = time.monotonic()

    async def async_load(self):
        try:
            print("Loading audio")
            self.url = (await util.download(self.url)).name
            print("Loading audio")
            self.sound = await asyncio.to_thread(pg.mixer.Sound,self.url)
            print("Loading audio")
        except asyncio.CancelledError:
            pass
        except Exception as e:
            util.log_error(e)
            # TODO: use fallbacks

    def init_load(self):
        self.loading_task = asyncio.create_task(self.async_load())
        self.loading_task.add_done_callback(self.on_loaded)
        self.unloaded = False
        self.last_used = time.monotonic()
        return self

    def play(self):
        self.sound.play(
            -1 * self.loop,
        )

    def stop(self):
        self.sound.stop()

    def on_loaded(self, future: asyncio.Future):
        assert future.done()
        if self.autoplay:
            self.play()
