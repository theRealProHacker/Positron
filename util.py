"""
Utilities for all kinds of needs (funcs, regex, etc...) 
"""

import asyncio
import binascii
import errno
import logging
import mimetypes
import os
import re
import socket
import sys
import time
import uuid
from contextlib import contextmanager, redirect_stdout
from dataclasses import dataclass
from functools import cache
from types import FunctionType
from typing import Callable, Coroutine, Iterable, Literal, Sequence, TypeVar
from urllib.parse import parse_qsl, unquote_plus, urlparse
import webbrowser

import aiofiles
import aiofiles.os
import aiofiles.ospath as aospath
import aiohttp
import numpy as np
import pygame as pg
from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

# fmt: off
from config import g
from own_types import (CO_T, K_T, V_T, BugError, Color, Coordinate,
                       Font, Index, OpenMode, OpenModeReading, OpenModeWriting,
                       Rect, Surface, Vector2, loadpage_event)

# fmt: on

mimetypes.init()


def noop(*args, **kws):
    """A no operation function"""
    return None


########################## FileWatcher #############################
class FileWatcher(FileSystemEventHandler):
    """
    A FileWatcher is really just a watchdog Eventhandler that holds a set of files to be watched.
    If any file changes, the app is asked to restart by setting the `g["reload"]` flag and sending a
    Quit Event to the Event Queue
    """

    def __init__(self):
        self.last_hit = time.monotonic()  # this doesn't need to be extremely accurate
        self.files = set[str]()
        self.dirs = set[str]()

    def add_file(self, file: str):
        file = os.path.abspath(file)
        file = self.files.add(file)
        new_dir = os.path.dirname(file)
        if not new_dir in self.dirs:
            self.dirs.add(new_dir)
            ob = Observer()
            ob.schedule(self, new_dir)
            ob.start()
        return file

    def on_modified(self, event: FileSystemEvent):
        logging.debug(f"File modified: {event.src_path}")
        if event.src_path in self.files and (t := time.monotonic()) - self.last_hit > 1:
            g["event_manager"].release_event("file_modified", path=event.src_path)
            pg.event.post(goto(g["route"]))  # reload the current page
            self.last_hit = t


#########################################################

########################## Misc #########################


def get_dpi():  # TODO
    return pg.display.get_display_sizes()[0]


def make_default(value: V_T | None, default: V_T) -> V_T:
    """
    If the `value` is None this returns `default` else it returns `value`
    """
    return default if value is None else value


def in_bounds(x: float, lower: float, upper: float) -> float:
    """
    Make `x` be between lower and upper
    """
    x = max(lower, x)
    x = min(upper, x)
    return x


def not_neg(x: float):
    """
    return the maximum of x and 0
    """
    return max(0, x)


def abs_div(x):
    """
    Return the absolute of a fraction.
    Just like `abs(x*-1)` is `(x*1)`, `abs_div(x**-1)` is `(x**1)`.
    Or in other words just like abs is the 'distance' to 0 (the neutral element of addition) using addition,
    abs_div is the distance to 1 (the neutral element of multiplication) using multiplication.
    """
    return 1 / x if x < 1 else x


def get_tag(elem) -> str:
    """
    Get the tag of an _XMLElement or "comment" if the element has no valid tag
    """
    return (
        elem.tag.removeprefix("{http://www.w3.org/1999/xhtml}").lower()
        if isinstance(elem.tag, str)
        else "comment"
    )


def ensure_suffix(s: str, suf: str) -> str:
    """
    Ensures that `s` definitely ends with the suffix `suf`
    """
    return s if s.endswith(suf) else s + suf


def all_equal(l: Sequence):
    """
    Return whether all the elements in the list are equal
    """
    if len(l) < 2:
        return True
    x, *rest = l
    return all(x == r for r in rest)


def group_by_bool(
    l: Iterable[V_T], key: Callable[[V_T], bool]
) -> tuple[list[V_T], list[V_T]]:
    """
    Group a list into two lists depending on the bool value given by the key
    """
    true = []
    false = []
    for x in l:
        if key(x):
            true.append(x)
        else:
            false.append(x)
    return true, false


def find(__iterable: Iterable[V_T], key: Callable[[V_T], bool]):
    """
    Find the first element in the iterable that is accepted by the key
    """
    for x in __iterable:
        if key(x):
            return x


def find_index(__iterable: Iterable[V_T], key: Callable[[V_T], bool]):
    """
    Find the first elements index in the iterable that is accepted by the key
    """
    for i, x in enumerate(__iterable):
        if key(x):
            return i


def consume_list(l: list[V_T]):
    """
    Consume a list by removing all elements
    """
    while l:
        yield l.pop(0)


def consume_dict(d: dict[K_T, V_T]):
    """
    Consume a dict by removing all items
    """
    while d:
        yield d.popitem()

V_T2 = TypeVar("V_T2")
def map_dvals(d: dict[K_T, V_T], func: Callable[[V_T],V_T2])->dict[K_T, V_T2]:
    return {
        k: func(v) for k,v in d.items()
    }


# tuple mutations
def mutate_tuple(tup: tuple, val, slicing: Index):
    """
    Mutate a tuple given the tuple, a slicing and the value to fill into that slicing
    Example:
        ```python
        t = (1,2)
        mutate_tuple(t, 3, 0) == (3,2)
        ```
    """
    l = list(tup)
    l[slicing] = val
    return tuple(l)


def tup_replace(
    t: tuple[CO_T, ...], slice_: int | tuple[int, int], elem
) -> tuple[CO_T, ...]:
    """
    Replace the part of the tuple given by slice with `elem`
    """
    if isinstance(slice_, int):
        return *t[:slice_], elem, *t[slice_:]
    elif isinstance(slice_, tuple):
        start, stop = slice_
        return *t[:start], elem, *t[stop:]
    return


async def call(callback, *args, **kwargs):
    """
    TODO: actually look at the functions definition and match them to the given arguments
    """
    try:
        rv = callback(*args, **kwargs)
    except TypeError:
        rv = callback()
    if isinstance(callback, Coroutine):
        rv = await rv
    return rv


####################################################################

############################## I/O #################################
class Task(asyncio.Task):
    def __init__(self, sync: bool = False, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.sync = sync

    @classmethod
    def create(
        cls,
        coro,
        sync: bool = False,
        callback: Callable[[asyncio.Future], None] | None = None,
        **kwargs,
    ):
        task = cls(sync, coro, **kwargs)
        if callback is not None:
            task.add_done_callback(callback)
        return task


def create_task(
    coro,
    sync: bool = False,
    callback: Callable[[asyncio.Future], None] | None = None,
    **kwargs,
):
    """
    This creates a task and adds it to the global task queue
    """
    task = Task.create(coro, sync, callback, **kwargs)
    g["tasks"].append(task)
    return task


async def gather_tasks(tasks: list[Task]):
    return await asyncio.gather(*(task for task in consume_list(tasks) if task.sync))


@dataclass(frozen=True, slots=True)
class File:
    """
    A File object can be used to read and write to a file while saving its encoding and mime-type
    """

    name: str
    mime_type: str | None = None
    encoding: str | None = None

    # TODO: init from file like buffer

    @property
    def ext(self) -> str:
        # if you need both name and ext then use splitext directly
        return os.path.splitext(self.name)[1]

    @contextmanager
    def open(self, mode: OpenMode, *args, **kwargs):
        if self.encoding:
            kwargs.setdefault("encoding", self.encoding)
        with open(self.name, mode, *args, **kwargs) as f:
            yield f

    def read(self, mode: OpenModeReading = "r", *args, **kwargs):
        with self.open(mode, *args, **kwargs) as f:
            return f.read()

    def write(self, mode: OpenModeWriting = "w", *args, **kwargs):
        with self.open(mode, *args, **kwargs) as f:
            return f.write()


def is_online() -> bool:
    # https://www.codespeedy.com/how-to-check-the-internet-connection-in-python/
    own_adress = socket.gethostbyname(socket.gethostname())
    return own_adress != "127.0.0.1"


created_files: set[str] = set()


def _make_new_name(name):
    def lamda(groups: list[str]):
        return f"({int(groups[0]) + 1})"

    if (
        new_name := rev_sub(r"\)(\d+)\(", name, lamda, 1)  # regex is flipped (3)->)3(
    ) != name:
        return new_name
    else:
        name, ext = os.path.splitext(name)
        return f"{name} (2){ext}"


def create_file(file_name: str) -> str:
    """
    Definitely create a new file
    """
    file_name = os.path.abspath(file_name)
    try:
        with open(file_name, "x") as _:
            created_files.add(file_name)
            return file_name
    except FileExistsError:
        return create_file(_make_new_name(file_name))


async def delete_created_files():
    global created_files
    if created_files:
        logging.info(f"Deleting: {created_files}")
        await asyncio.gather(*(aiofiles.os.remove(file) for file in created_files))


save_dir = os.environ.get("TEMP") or "."


@dataclass
class Response:
    url: str
    content: str | bytes
    status: int = 200
    _charset: str = ""  # aka encoding
    _mime_type: str = ""
    _ext: str = ""

    @property
    def israw(self):
        return isinstance(self.content, bytes)

    @property
    def charset(self):
        return self._charset or sys.getdefaultencoding()

    @property
    def text(self):
        if isinstance(self.content, str):
            return self.content
        else:
            return self.content.decode(self.charset)

    @property
    def raw(self):
        if isinstance(self.content, bytes):
            return self.content
        else:
            return self.content.encode(self.charset)

    @property
    def mime_type(self):
        if not self._mime_type:
            self._mime_type = mimetypes.guess_type(self.url, strict=False)
        return self._mime_type

    @property
    def ext(self):
        if not self._ext:
            if self.mime_type:
                self._ext = mimetypes.guess_extension(self.mime_type, strict=False)
            else:
                _, self._ext = os.path.splitext(self.url)
        return self._ext


def parse_media_type(
    media_type: str, mime_type: str = "", charset: str = ""
) -> tuple[str, str]:
    if not media_type:
        return (mime_type, charset)
    arr = media_type.split(";")
    _charset = ""
    _mime_type, *params = arr
    try:
        for param in params:
            name, value = param.split("=")
            if name == "charset":
                charset = value
    except ValueError:
        return (mime_type, charset)
    return _mime_type or mime_type, _charset or charset


media_type_pattern = re.compile(rf"[\w\-]+\/[\w\-]+(?:\;\w+\=\w+)*")


async def fetch(url: str, raw: bool = False) -> Response:
    """
    Fetch an url (into memory)

    Returns a Response or raises a ValueError if the url passed was invalid

    Also it might raise an aiohttp error
    """
    if url.startswith("http"):
        session: aiohttp.ClientSession = g["aiosession"]
        async with session.get(url) as response:
            content_type = response.headers.get("content-type", "")
            mime_type, charset = parse_media_type(content_type)
            return Response(
                url=response.url.human_repr(),
                content=await response.read(),
                status=response.status,
                _charset=charset or response.charset or "",
                _mime_type=mime_type,
            )
    elif url.startswith("data:"):
        # handle data url
        """https://www.rfc-editor.org/rfc/rfc2397#section-2
        dataurl    := "data:" [ mediatype ] [ ";base64" ] "," data
        mediatype  := [ type "/" subtype ] *( ";" parameter )
        data       := *urlchar
        parameter  := attribute "=" value
        """
        url = re.sub(r"\s*", "", url)  # remove all whitespace
        url = url[5:]
        parser = GeneralParser(url)
        media_type = parser.consume(media_type_pattern)
        mime_type, charset = parse_media_type(media_type, "text/plain", "US-ASCII")
        is_base64 = parser.consume(";base64")
        if not parser.consume(","):
            raise ValueError
        content: str | bytes = unquote_plus(parser.x)
        if is_base64:
            # From https://stackoverflow.com/a/39210134/15046005
            content = binascii.a2b_base64(content)
        return Response(
            url,
            content,
            _charset=charset,
            _mime_type=mime_type,
        )
    else:
        try:
            mode: Literal["rb", "r"] = "rb" if raw else "r"
            async with aiofiles.open(url, mode) as f:
                content = await f.read()
            return Response(url, content)
        except IOError as e:
            code: int = (
                403
                if e.errno == errno.EACCES
                else 404
                if e.errno == errno.ENOENT
                else 400
            )
            return Response(url, "", code)


async def download(url: str) -> str:
    """
    Instead of fetching the url into memory, the data is downloaded to a file
    """
    if url.startswith("http"):
        session: aiohttp.ClientSession = g["aiosession"]
        async with session.get(url) as resp:
            new_file = create_file(os.path.basename(urlparse(url).path))
            async with aiofiles.open(new_file, "wb") as f:
                async for chunk in resp.content.iter_any():
                    await f.write(chunk)
        return new_file
    elif url.startswith("data"):
        logging.warning(
            "Downloading data URI. This means you are likely putting something into a data uri that is too big (like an image)"
        )
        response = await fetch(url)
        new_file = create_file(uuid.uuid4().hex)
        mode: Literal["wb", "w"] = "wb" if response.israw else "w"
        async with aiofiles.open(new_file, mode) as f:
            await f.write(response.content)
        return new_file
    else:
        if await aospath.isfile(url):
            return url
        else:
            raise ValueError("Invalid Path")


async def fetch_txt(src: str) -> str:
    return (await fetch(src)).text


_error_logfile = File("error.log", encoding="utf-8")


@contextmanager
def clog_error():
    """
    yields a context to print to the error logfile
    """
    with _error_logfile.open("a") as file:
        with redirect_stdout(file):
            yield


log_error = clog_error()(print)
print_once = cache(print)
log_error_once = cache(log_error)
####################################################################

######################### Regexes ##################################
def get_groups(s: str, p: re.Pattern) -> list[str] | None:
    """
    Get the matched groups of a match
    """
    if match := p.search(s):
        if groups := [g for g in match.groups() if g]:
            return groups
        else:
            return [match.group()]
    return None


def re_join(*args: str) -> str:
    """
    Example:
    x in ("px","%","em") <-> re.match(re_join("px","%","em"), x)
    """
    return "|".join(re.escape(x) for x in args)


# Reverse regex
r"""
Search or replace in the regex from the end of the string.
The given regex will not be reversed TODO: implement this
To reverse a regex we need to understand which tokens belong together
Examples:
\d -> \d
\d*->\d*
or
(?:\d+) -> (?:\d+)
...
"""


def rev_groups(pattern: re.Pattern | str, s: str):
    _pattern = re.compile(pattern)
    groups = get_groups(s[::-1], _pattern)
    return None if groups is None else [group[::-1] for group in groups]


def rev_sub(
    pattern: re.Pattern | str,
    s: str,
    repl: str | Callable[[list[str]], str],
    count: int = -1,
):
    """
    Subs a regex in reversed mode
    """
    if isinstance(repl, str):
        _repl = repl[::-1]
    elif isinstance(repl, FunctionType):

        def _repl(match: re.Match):
            return repl([group[::-1] for group in match.groups()])[::-1]

    else:
        raise TypeError

    return re.sub(pattern, _repl, s[::-1], count)[::-1]


class GeneralParser:
    """
    Really this is a lexer.
    It consumes parts of its x and can then convert these into tokens
    """

    x: str

    def __init__(self, x: str):
        self.x = x

    def consume(self, s: str | re.Pattern[str]) -> str:
        assert s, BugError("Parser with empty consume")
        if isinstance(s, str) and self.x.startswith(s):
            self.x = self.x[len(s) :]
            return s
        elif isinstance(s, re.Pattern):
            if match := s.match(self.x):
                slice_ = match.span()[1]
                result, self.x = self.x[:slice_], self.x[slice_:]
                return result
        return ""


##########################################################################


############################# Colors #####################################
def hsl2rgb(hue: float, sat: float, light: float):
    """
    hue in [0,360]
    sat,light in [0,1]
    """
    hue %= 360
    sat = in_bounds(sat, 0, 1)
    light = in_bounds(light, 0, 1)
    # algorithm from https://www.w3.org/TR/css-color-3/#hsl-color
    def hue2rgb(n):
        k = (n + hue / 30) % 12
        a = sat * min(light, 1 - light)
        return light - a * max(-1, min(k - 3, 9 - k, 1))

    return Color(*(int(x * 255) for x in (hue2rgb(0), hue2rgb(8), hue2rgb(4))))


def hwb2rgb(h: float, w: float, b: float):
    """
    h in [0,360]
    w,b in [0,1]
    """
    h %= 360
    if (sum_ := (w + b)) > 1:
        w /= sum_
        b /= sum_

    rgb = hsl2rgb(h, 1, 0.5)

    return Color(*(round(x * (1 - w - b) + 255 * w) for x in rgb))


# TODO: lab, lch, oklab, oklch, etc. to rgb


##########################################################################

############################# Site navigation ############################

routes: dict[str, Callable] = {}


def add_route(route: str):
    if not isinstance(route, str):
        raise ValueError("route must be a String")

    def inner(route_func: Callable):
        routes[route] = route_func
        return route_func

    return inner


def goto(url: str, **kwargs: str):
    """
    Make the browser display a different page if it is a registered route or open the page
    Raises a KeyError if the route is invalid.
    """
    # TODO:
    visited: dict[str, Literal["browser", "internal", "invalid"]] = g["visited_links"]
    status = visited.get(url, "internal")
    if status == "invalid":
        return  # we already reported that the url is invalid
    elif status == "internal":
        parsed_result = urlparse(url)
        route = parsed_result.path
        try:
            pg.event.post(
                loadpage_event(
                    url=url,
                    callback=routes[route],
                    kwargs=dict(parse_qsl(parsed_result.query)) | kwargs,
                    target=parsed_result.fragment,
                )
            )
        except KeyError:
            status = "browser"
    if status == "browser":
        if not webbrowser.open_new_tab(url):
            status = "invalid"
            log_error(f"Invalid route: {url!r}")
    visited[url] = status


##########################################################################

############################# Pygame related #############################

pg.init()


def surf_opaque(surf: Surface):
    return np.all(pg.surfarray.array_alpha(surf) == 255)


def draw_text(surf: Surface, text: str, font: Font, color, **kwargs):
    color = Color(color)
    if color.a:
        text_surf = font.render(text, True, color)
        dest = text_surf.get_rect(**kwargs)
        if color.a != 255:
            text_surf.set_alpha(color.a)
        surf.blit(text_surf, dest)


class Dotted:
    def __init__(
        self,
        dim,
        color,
        dash_size: int = 10,
        dash_width: int = 2,
        start_pos: Coordinate = (0, 0),
    ):
        self.dim = Vector2(dim)
        self.color = Color(color)
        self.dash_size = dash_size
        self.dash_width = dash_width
        self.start_pos = Vector2(start_pos)

    @classmethod
    def from_rect(cls, rect: Rect, **kwargs):
        return cls(rect.size, **kwargs, start_pos=rect.topleft)

    def draw_at(self, surf: Surface, pos):
        pos = Vector2(pos)
        vec = self.dim.normalize() * self.dash_size
        for i in range(int(self.dim.length() // self.dash_size // 2)):
            _pos = pos + vec * i * 2
            pg.draw.line(surf, self.color, _pos, _pos + vec, self.dash_width)

    def draw(self, surf: Surface):
        return self.draw_at(surf, self.start_pos)

    def draw_rect(self, surf: Surface):
        rect = Rect(*self.start_pos, *self.dim)
        for line in rect.sides:
            pos = Vector2(line[0])
            dim = line[1] - pos
            Dotted(dim, self.color, self.dash_size, self.dash_width, pos).draw(surf)


def draw_lines(surf: Surface, points, *args, **kwargs):
    points = [Vector2(point) for point in points]
    dlines = [
        Dotted(points[i + 1] - points[i], *args, **kwargs, start_pos=points[i])  # type: ignore
        for i in range(len(points) - 1)
    ]
    for dline in dlines:
        dline.draw(surf)
