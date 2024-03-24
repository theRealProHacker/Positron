"""
This file includes Media classes like Image, Video or Audio
"""

import asyncio
from contextlib import suppress
import logging
from pathlib import Path
from typing import Any
from weakref import WeakValueDictionary

import pygame as pg

import positron.config as config
import positron.utils as util
from positron.types import Coordinate, Surface

surf_cache = WeakValueDictionary[str, Surface]()


async def load_surf(url: str):
    """
    Loads a surf. To save RAM surfs are cached in a surf_cache
    """
    # TODO: be able to activate and deactivate surface caching
    if (surf := surf_cache.get(url)) is None:
        file = await util.download(url)
        surf_cache[url] = surf = await asyncio.to_thread(pg.image.load, file)
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
            self._loading_task
            if self._loading_task is not None
            else config.default_task
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
                util.log_error_once(f"Couldn't load image: {url!r}. Reason: {e}")

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
        the loaded surface and the current loading task
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
        if (exception := future.exception()) is not None:
            util.log_error_once(
                f"Couldn't load image with urls: {self.urls} and exception {type(exception)}: {exception}"
            )

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


def LinearGradient(Image):
    """
    A LinearGradient takes any number of colors and an angle
    """
    """
    https://stackoverflow.com/questions/726549/algorithm-for-additive-color-mixing-for-rgb-values
    https://www.pygame.org/wiki/GradientCode
    https://stackoverflow.com/questions/40589624/generating-colour-image-gradient-using-numpy
    """
    # TODO


# TODO: stream audio directly from the internet
# https://stackoverflow.com/a/46782229/15046005
class Audio:
    sound: pg.mixer.Sound | None = None
    loading_task: util.Task | None = None
    is_playing: bool = False
    volume: float = 1.0
    """
    Volume between 0 and 1
    volume*muted gives the actual volume
    """

    def __init__(
        self,
        url: str,
        load: bool = True,
        autoplay: bool = True,
        loop: bool = False,
        muted: bool = False,
    ):
        self.url = url
        self.autoplay = autoplay
        self.loop = loop - 1
        self.muted = muted

        if autoplay or load:
            self.init_load()
        # self.last_used = time.monotonic()

    async def _async_load(self):
        try:
            self.url = await util.download(self.url)
            self.sound = await asyncio.to_thread(pg.mixer.Sound, self.url)
            self._set_volume()
        except asyncio.CancelledError:
            pass
        except Exception as e:
            util.log_error(e)
            # TODO: use fallbacks

    def _on_loaded(self, future: asyncio.Future):
        assert future.done()
        if self.autoplay:
            self.play()

    def init_load(self):
        self.loading_task = util.create_task(self._async_load())
        self.loading_task.add_done_callback(self._on_loaded)
        # self.last_used = time.monotonic()
        return self

    def play(self):
        if self.is_loaded:
            self.is_playing = True
            self.sound.play(-1 * self.loop)

    def stop(self):
        if self.is_loaded:
            self.is_playing = False
            self.sound.stop()

    def toggle(self):
        if self.is_playing:
            self.stop()
        else:
            self.play()

    def _set_volume(self):
        if self.sound:
            self.sound.set_volume(self.volume * (not self.muted))

    @property
    def is_loading(self):
        """Whether the audio is being loaded currently"""
        return self.loading_task is not None and not self.loading_task.done()

    @property
    def is_loaded(self):
        """Whether the audio is fully loaded"""
        return self.sound is not None

    @property
    def is_unloaded(self):
        """Whether the audio is unloaded (neither loading nor loaded)"""
        return not (self.is_loaded or self.is_loading)

    def __setattr__(self, name: str, value: Any) -> None:
        super().__setattr__(name, value)
        if name in ("muted", "volume"):
            self._set_volume()

    def __del__(self):
        with suppress(pg.error):
            self.stop()


class FileAudio(Audio):
    """
    This Audio implementation uses the fact, that we can't stream audio from the network anyway
    to only allow file audio. It always loads the sound synchronously.
    """

    def __init__(
        self,
        url: str,
        load: bool = True,
        autoplay: bool = True,
        loop: bool = False,
        muted: bool = False,
    ):
        if not Path(url).exists():
            util.log_error_once(
                f"Audio sources need to be local files. '{url}' could not be found locally. "
            )
        super().__init__(url, load, autoplay, loop, muted)

    def init_load(self):
        self.sound = pg.mixer.Sound(self.url)
        self.is_loaded = True
        self.is_unloaded = False
        if self.autoplay:
            self.play()

    def play(self):
        if not self.is_loaded:
            self.init_load()
        self.is_playing = True
        self.sound.play(-1 * self.loop)

    def stop(self):
        self.is_playing = False
        if self.is_loaded:
            self.sound.stop()


class MusicAudio(Audio):
    """
    This Audio implementation uses the pygame music module
    """

    is_loading = False
    is_unloaded = True
    is_loaded = False

    def __init__(
        self,
        url: str,
        load: bool = True,
        autoplay: bool = True,
        loop: bool = False,
        muted: bool = False,
    ):
        if not Path(url).exists():
            util.log_error_once(
                f"Audio sources need to be local files. '{url}' could not be found locally. "
            )
        super().__init__(url, load, autoplay, loop, muted)

    def init_load(self):
        if pg.mixer.music.get_busy():
            pg.mixer.music.stop()
        pg.mixer.music.load(self.url)
        self.is_loaded = True
        self.is_unloaded = False
        if self.autoplay:
            self.play()

    def unload(self):
        self.is_loaded = False
        self.is_unloaded = True
        self.is_playing = False
        pg.mixer.music.unload()

    def play(self):
        if not self.is_loaded:
            self.init_load()
        if self.is_playing:
            pg.mixer.music.unpause()
        else:
            pg.mixer.music.play(-1 * self.loop)
        self.is_playing = True

    def stop(self):
        if self.is_playing:
            pg.mixer.music.pause()
        self.is_playing = False

    def seek(self, pos: float):
        """
        Seeks to the given position in seconds
        """
        path = Path(self.url)
        if path.suffix == ".mp3":
            pg.mixer.music.rewind()
            pg.mixer.music.set_pos(pos)
        else:
            pg.mixer.music.set_pos(pos)

    def _set_volume(self):
        pg.mixer.music.set_volume(self.volume * (not self.muted))


# class _Audio:
#     """
#     An Audio media that uses PyAudio under the hood
#     """
#     player: vlc.MediaPlayer
#     is_playing = False
#     is_loaded = False

#     def __init__(self, url: str, load: bool = True, autoplay: bool = True, loop: bool = False, muted: bool = False):
#         self.url = url
#         self.autoplay = autoplay
#         self.loop = loop
#         self.muted = muted
#         self.volume = 1.0
#         self.player = instance.media_player_new()

#         if load:
#             self.load()

#     def load(self):
#         """
#         Loads the audio file
#         """
#         if (window := pg.display.get_wm_info().get("window")):
#             if platform.system() == "Linux":
#                 self.mediaplayer.set_xwindow(window)
#             elif platform.system() == "Windows":
#                 self.mediaplayer.set_hwnd(window)
#             elif platform.system() == "Darwin":
#                 self.mediaplayer.set_nsobject(window)


#         self.is_loaded = True

#     def play(self):
#         """
#         Start playing
#         """
#         if not self.is_loaded:
#             self.load()
#         self.audio.
#         self.is_playing = True

#     def pause(self):
#         ...
#         self.is_playing = False

#     ... # setters

# TODO: Video: This is going to be insanely difficult and it might be that we can never implement this
