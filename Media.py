"""
This file includes Media classes like Image, Video or Audio
"""
import asyncio
import os
import time

import pygame as pg

from own_types import Dimension, Surface
import util


# class Media:
#     def __init__(self, url: str):
#         self.url = url

#     @property
#     def is_loaded(self)->bool:
#         return True

#     def init_load(self):
#         return self
    
#     def unload(self):
#         return self

#     def draw(self, screen: Surface, pos: Dimension):
#         pass

image_cache: dict[str, "Image"] = {}

def save_ram():
    for image in image_cache.values():
        if time.monotonic() - image.last_used > 1: # not used for more than 1 second
            image.unload()

async def prefetch_image(url):
    file = await util.download(url)
    # The image isn't loaded into memory
    image_cache[url] = Image(file.name, load=False)

class Image:
    """
    Represents a (still) Image. Can either be in a state of loading, loaded or unloaded
    """
    def __new__(cls, url: str, load: bool = True):
        if (image := image_cache.get(url)) is None:
            image_cache[url] = image = super().__new__(cls)
        elif load and not image.is_loaded:
            image.init_load()
        return image
        
    def __init__(self, url: str, load: bool = True):
        self.url = url
        self.surf = None
        self.unloaded = False
        if load:
            self.init_load()
        self.last_used = time.monotonic()

    @property
    def is_loaded(self):
        return self.surf is not None

    @property
    def size(self):
        return self.surf.get_size()

    async def async_load(self):
        try:
            self.url = (await util.download(self.url, os.environ["TEMP"])).name
            self.surf = await asyncio.to_thread(pg.image.load,self.url)
            return self.surf
        except asyncio.CancelledError:
            pass
        except Exception as e:
            util.log_error(e)

    def init_load(self):
        """
        Start loading the image into memory. But instantly return the `Image`. 
        You only need to call this if you init with `load=false` or unload the image
        """
        if not self.is_loaded:
            self.loading_task = asyncio.create_task(self.async_load())
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


# class GIF(Media):
#     def __init__(self, path: str):
#         self.path = path
#         self.gif = pg.image.load(path)
#     def draw(self, screen, pos):
#         screen.blit(self.gif, pos)
