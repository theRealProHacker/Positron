"""
This file includes Media classes like Image, Video or Audio
"""
import asyncio
import logging
import time
from weakref import WeakValueDictionary

import pygame as pg

import util
from own_types import Coordinate, Surface
from config import g


surf_cache = WeakValueDictionary[str, Surface]()


async def load_surf(url: str):
    """
    Loads a surf. To save RAM surfs are cached in a surf_cache
    """
    # TODO: be able to activate and deactivate surface caching
    if (surf := surf_cache.get(url)) is None:
        file = await util.download(url)
        surf_cache[url] = surf = await asyncio.to_thread(pg.image.load, file)  # type: ignore[assignment]
    return surf


# to avoid None checks
_default_surf = Surface((0, 0))


class Image:
    """
    Represents a single image with multiple sources
    """

    _surf: Surface
    _loading_task: util.Task | None

    def __init__(
        self,
        urls: list[str] | str,
        load: bool = True,
        sync: bool = False,
    ):
        """
        Initialize the image from the urls
        sync specifies that the image should load before the page is drawn the first time
        load specifies that the image should be loaded right away
        """
        self.urls = urls if isinstance(urls, list) else [urls]
        self.url = self.urls[0]
        self.surf = _default_surf
        self._loading_task = None
        if load or sync:
            self.init_load()
            self.loading_task.sync = sync

    @property
    def surf(self):
        """
        Getting the images surf automatically starts loading it if it isn't loaded
        """
        if self._surf is _default_surf:
            self.init_load()
        return self._surf

    @surf.setter
    def surf(self, surf: Surface):
        self._surf = surf

    @property
    def loading_task(self) -> util.Task:
        return (
            self._loading_task if self._loading_task is not None else g["default_task"]
        )

    @loading_task.setter
    def loading_task(self, task: util.Task):
        self._loading_task = task

    async def load_urls(self):
        """
        Continuously try loading images. If all fail returns None
        """
        for url in self.urls:
            self.url = url
            try:
                self.surf = await load_surf(url)
                logging.debug(f"Loaded Image: {url!r}")
                return self.surf
            except asyncio.CancelledError:
                logging.debug(f"Cancelled loading image: {url!r}")
                break
            except Exception as e:
                util.log_error_once(f"Couldn't load image: {url!r}. Reason: {str(e)}")

    def init_load(self):
        """
        Initialize loading the image
        """
        if not self.is_loading:
            first_load = self.loading_task is None
            self.loading_task = util.create_task(self.load_urls())
            if first_load:
                self.loading_task.add_done_callback(self._on_loaded)

    def unload(self):
        """
        Unloads the image by destroying
        the loaded image and the current loading task
        """
        self.surf = _default_surf
        self.loading_task.cancel()

    def _on_loaded(self, future: asyncio.Future[Surface]):
        """
        The default on_loaded callback.
        If you want to add your own callback do:
        ```python
        if image.is_loading:
            image.loading_task.add_done_callback(your_callback)
        ```
        """
        pass

    def draw(self, surf: Surface, pos: Coordinate):
        """
        Draw the image to the given surface.
        If the surf is unloaded, loading will automatically start
        """
        surf.blit(self.surf, pos)

    @property
    def is_loading(self):
        """Whether the images surf is being loaded currently"""
        return self._loading_task is not None and not self.loading_task.done()

    @property
    def is_loaded(self):
        """Whether the images surf is loaded and ready to draw"""
        return self._surf is not _default_surf

    @property
    def is_unloaded(self):
        """Whether the images surf is unloaded (neither loading nor loaded)"""
        return not (self.is_loaded or self.is_loading)


# TODO: stream audio directly from the internet
# https://stackoverflow.com/a/46782229/15046005
class Audio:
    sound: pg.mixer.Sound | None
    loading_task: util.Task | None

    def __init__(
        self, url: str, load: bool = True, autoplay: bool = True, loop: bool = False
    ):
        self.url = url
        self.autoplay = autoplay
        self.loop = loop
        self.sound = None
        self.loading_task = None
        if autoplay or load:
            self.init_load()
        self.last_used = time.monotonic()

    async def async_load(self):
        try:
            self.url = (await util.download(self.url)).name
            self.sound = await asyncio.to_thread(pg.mixer.Sound, self.url)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            util.log_error(e)
            # TODO: use fallbacks

    def init_load(self):
        self.loading_task = asyncio.create_task(self.async_load())
        self.loading_task.add_done_callback(self.on_loaded)
        self.last_used = time.monotonic()
        return self

    def play(self):
        if self.is_loaded:
            self.sound.play(
                -1 * self.loop,
            )

    def stop(self):
        self.sound.stop()

    def on_loaded(self, future: asyncio.Future):
        assert future.done()
        if self.autoplay:
            self.play()

    @property
    def is_loading(self):
        """Whether the images surf is being loaded currently"""
        return self.loading_task is not None and not self.loading_task.done()

    @property
    def is_loaded(self):
        """Whether the images surf is loaded and ready to draw"""
        return self.sound is not None

    @property
    def is_unloaded(self):
        """Whether the images surf is unloaded (neither loading nor loaded)"""
        return not (self.is_loaded or self.is_loading)
