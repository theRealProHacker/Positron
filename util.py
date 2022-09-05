"""
Utilities for all kinds of needs (funcs, regex, etc...) 
"""

import asyncio
import logging
import mimetypes
import os
import re
import socket
import time
from contextlib import contextmanager, redirect_stdout, suppress
from dataclasses import dataclass
from functools import cache, partial
from os.path import abspath, dirname
from types import FunctionType
from typing import Any, Callable, Iterable, Sequence
from urllib.error import URLError
from urllib.parse import urlparse

import pygame as pg
import pygame.freetype as freetype
import requests
import tldextract
from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

from config import all_units, g
from own_types import (V_T, Auto, AutoLP, AutoLP4Tuple, BugError, Cache, Color,
                       Dimension, Event, Float4Tuple, Length, OpenMode,
                       OpenModeReading, OpenModeWriting, Percentage, Rect,
                       Surface, Vector2, _XMLElement)

mimetypes.init()


def noop(*args, **kws):
    """A no operation function"""
    return None


################## Element Calculation ######################
@dataclass
class Calculator:
    """
    A calculator is for calculating the values of AlP attributes (width, height, border-width, etc.)
    It only needs the AlP value, a percentage value and an auto value. If latter are None then they will raise an Exception
    if a Percentage or Auto are encountered respectively
    """

    default_perc_val: float | None

    def __call__(
        self,
        value: AutoLP,
        auto_val: float | None = None,
        perc_val: float | None = None,
    ) -> float:
        """
        This helper function takes a value, an auto_val
        and the perc_value and returns a Number
        if the value is Auto then the auto_value is returned
        if the value is a Length that is returned
        if the value is a Percentage the Percentage is multiplied with the perc_value
        """
        perc_val = make_default(perc_val, self.default_perc_val)
        if value is Auto:
            assert auto_val is not None, BugError("This attribute cannot be Auto")
            return auto_val
        elif isinstance(value, Length):
            return not_neg(value)
        elif isinstance(value, Percentage):
            assert perc_val is not None, BugError(
                "This attribute cannot be a percentage"
            )
            return not_neg(perc_val * value)
        raise TypeError

    def _multi(self, values: Iterable[AutoLP], *args):
        return tuple(self(val, *args) for val in values)

    # only relevant for typing
    def multi2(self, values: tuple[AutoLP, AutoLP], *args) -> tuple[float, float]:
        return self._multi(values, *args)

    def multi4(self, values: AutoLP4Tuple, *args) -> Float4Tuple:
        return self._multi(values, *args)


####################################################################


########################## FileWatcher #############################
class FileWatcher(FileSystemEventHandler):
    """
    A FileWatcher is really just a watchdog Eventhandler that holds a set of files to be watched.
    If any file changes, the app is asked to restart by setting the `g["reload"]` flag and sending a
    Quit Event to the Event Queue
    """

    def __init__(self):
        self.last_hit = time.monotonic()  # this doesn't need to be extremely accurate
        self.files = Cache[str]()
        self.dirs = set[str]()

    def add_file(self, file: str):
        file = abspath(file)
        file = self.files.add(file)
        new_dir = dirname(file)
        if not new_dir in self.dirs:
            self.dirs.add(new_dir)
            ob = Observer()
            ob.schedule(self, new_dir)
            ob.start()
        return file

    def on_modified(self, event: FileSystemEvent):
        logging.debug(f"File modified: {event.src_path}")
        if event.src_path in self.files and (t := time.monotonic()) - self.last_hit > 1:
            g["reload"] = True
            pg.event.clear(eventtype=pg.QUIT)
            pg.event.post(Event(pg.QUIT))
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


def get_tag(elem: _XMLElement) -> str:
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


def consume_list(l: list):
    """
    Consume a list by removing all elements
    """
    while l:
        yield l.pop()
####################################################################

############################## I/O #################################
class Task(asyncio.Task):
    def __init__(self, sync: bool = False, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.sync = sync

def create_task(coro, sync: bool = False, **kwargs):
    return Task(sync, coro)


@dataclass(frozen=True, slots=True)
class File:
    """
    A File object can be used to read and write to a file while saving its encoding and mime-type
    """

    name: str
    mime_type: str | None = None
    encoding: str | None = None

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


# @contextmanager
# def open_temp(path: str, *args, **kwargs):
#     with open(os.path.join(os.environ["TEMP"], path), *args, **kwargs) as f:
#         yield f

# @contextmanager
# def random_file(file_ending: str)->TextIOWrapper:
#     file_name = hex(random.randrange(2**10))[2:]+file_ending
#     # file_name = ''.join(str(random.randrange(0,10)) for _ in range(8))+file_ending
#     try:
#         with open_temp(file_name, "x") as f:
#             yield f
#     except FileExistsError:
#         with random_file(file_ending) as f:
#             yield f


def is_online() -> bool:
    # https://www.codespeedy.com/how-to-check-the-internet-connection-in-python/
    own_adress = socket.gethostbyname(socket.gethostname())
    return own_adress != "127.0.0.1"


def create_file(file_name: str):
    """
    Definitely create a new file
    """
    try:
        with open(file_name, "x") as _:
            return file_name
    except FileExistsError:
        # "file (1)(2)" -> "file (1)(3)"
        def lamda(groups: list[str]):
            return str(int(groups[0])+1)
        if (
            new_name := rev_sub(
                r"\)(\d+)\(", # regex is flipped (3)->)3(
                file_name,
                lamda,
            )
        ) != file_name:
            return create_file(new_name)
        else:
            name, ext = os.path.splitext(file_name)
            return create_file(name + " (2)" + ext)


save_dir = os.environ.get("TEMP") or "."


download_cache: dict[str, File] = {}


async def download(url: str, dir: str = save_dir, fast: bool = True) -> File:
    """
    Downloads a file from the given url as a stream into the given directory

    Raises Request Errors, OSErrors, or URLErrors.
    """
    # TODO: Use Multiprocessing to really improve downloads
    # https://docs.python.org/3/library/asyncio-task.html
    # sleep() always suspends the current task, allowing other tasks to run.
    # Setting the delay to 0 provides an optimized path to allow other tasks to run.
    # This can be used by long-running functions to avoid blocking the event loop
    # for the full duration of the function call.
    if (_url:=download_cache.get(url)) is not None and os.path.exists(_url.name): # this might not be a good idea if the file can be changed
        return _url
    ext: str | None
    mime_type: str | None
    chardet: str | None
    sleep = (not fast) * 0.01
    parse_result = urlparse(url)
    if parse_result.scheme == "file":
        if os.path.exists(path := parse_result.path.removeprefix("/")):
            return File(path)
        else:
            raise URLError("File doesn't exist", url)
    elif parse_result.scheme == "":
        # try to find the file in the current directory
        if os.path.exists(path := parse_result.path):
            return File(path)
        # if that doesn't work, then try https://
        httpurl = url + ("/" if "/" not in url else "")
        with suppress(Exception):
            return await download("https://" + httpurl, dir, fast)
        # if that doesn't work either, try http://
        with suppress(Exception):
            return await download("http://" + httpurl, dir, fast)
        raise URLError("Could not find file or uri: " + url)
    response = requests.get(url, stream=True)
    response.raise_for_status()
    name, ext = os.path.splitext(os.path.basename(parse_result.path))
    name = name or tldextract.extract(parse_result.netloc).domain
    # https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Content-Type
    # TODO: multipart with boundaries
    if (_content_type := response.headers.get("Content-Type")) is not None:
        # https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Content-Type
        content_type = [
            x.strip() for x in _content_type.split(";")
        ]  # we throw away the extra stuff. TODO: use that extra stuff
        chardet_bgn = "chardet="
        match content_type:
            case [mime_type]:
                chardet = mimetypes.guess_type(url)[1]
            case [mime_type, chardet] if chardet.startswith(chardet_bgn):
                chardet = chardet[len(chardet_bgn) :]
            case _:
                raise BugError(f"Unknown content type: {content_type}")
        ext = ext or mimetypes.guess_extension(mime_type)
    else:
        mime_type, chardet = mimetypes.guess_type(url)
    if ext is None:
        raise BugError(
            f"Couldn't guess extension for file: {url}->{name,ext}, Content-Type: {content_type}"
        )
    filename = create_file(os.path.abspath(os.path.join(dir, name + ext)))
    with open(filename, "wb") as f:
        chunk: bytes
        for chunk in response.iter_content():
            f.write(chunk)
            await asyncio.sleep(sleep)
    logging.debug(f"Downloaded {url} into {filename}")
    # TODO: guess mime type and encoding from content if None
    return File(filename, mime_type, chardet)


def sync_download(url: str, dir: str = save_dir) -> File:
    """
    Downloads a file from the given url as a stream into the given directory
    Raises RequestException, OSErrors, or URLErrors.
    """
    # TODO: Use Multiprocessing to really improve downloads
    # TODO: guess mime type and encoding from content if None
    # https://docs.python.org/3/library/asyncio-task.html
    # sleep() always suspends the current task, allowing other tasks to run.
    # Setting the delay to 0 provides an optimized path to allow other tasks to run.
    # This can be used by long-running functions to avoid blocking the event loop
    # for the full duration of the function call.
    with suppress(OSError):
        if os.path.exists(url):
            return File(os.path.abspath(url))
    ext: str | None
    mime_type: str | None
    chardet: str | None
    parse_result = urlparse(url)
    if parse_result.scheme == "file":
        if os.path.exists(path := parse_result.path.removeprefix("/")):
            return File(path)
        else:
            raise URLError("File not found: " + url)
    elif parse_result.scheme in ("http", "https"):
        response = requests.get(url, stream=True)
        response.raise_for_status()
        name, ext = os.path.splitext(os.path.basename(parse_result.path))
        name = name or tldextract.extract(parse_result.netloc).domain
        # https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Content-Type
        # TODO: multipart with boundaries
        if (_content_type := response.headers.get("Content-Type")) is not None:
            # https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Content-Type
            content_type = [
                x.strip() for x in _content_type.split(";")
            ]  # we throw away the extra stuff. TODO: use that extra stuff
            chardet_bgn = "chardet="
            match content_type:
                case [mime_type]:
                    chardet = mimetypes.guess_type(url)[1]
                case [mime_type, chardet] if chardet.startswith(chardet_bgn):
                    chardet = chardet[len(chardet_bgn) :]
                case _:
                    raise BugError(f"Unknown content type: {content_type}")
            ext = ext or mimetypes.guess_extension(mime_type)
        else:
            mime_type, chardet = mimetypes.guess_type(url)
        if ext is None:
            raise BugError(
                f"Couldn't guess extension for file: {url}->{name,ext}, Content-Type: {content_type}"
            )
        filename = os.path.abspath(os.path.join(dir, name + ext))
        with open(filename, "wb") as f:
            chunk: bytes
            for chunk in response.iter_content():
                f.write(chunk)
        logging.debug(f"Downloaded {url} into {filename}")
    elif parse_result.scheme == "":
        # try https:// then http://
        httpurl = url + ("/" if "/" not in url else "")
        with suppress(requests.exceptions.RequestException, OSError, URLError):
            return sync_download("https://" + httpurl, dir)
        with suppress(requests.exceptions.RequestException, OSError, URLError):
            return sync_download("http://" + httpurl, dir)
        raise URLError("Could not find file or uri: " + url)
    else:
        raise URLError("Could not find file or uri: " + url)
    return File(filename, mime_type, chardet)


def fetch_txt(src: str) -> str:
    file: File = sync_download(src)
    return file.read()


# def readf(path: str):
#     with open(path, "r", encoding="utf-8") as file:
#         return file.read()
# use File(path).read() instead


_error_logfile = File("error.log", encoding="utf-8")


@contextmanager
def clog_error():
    """
    yields a context to print to the error logfile
    """
    with _error_logfile.open("a") as file:
        with redirect_stdout(file):
            yield


def log_error(*messages, **kwargs):
    """
    Log an error
    """
    with clog_error():
        print(*messages, **kwargs)


print_once = cache(print)
####################################################################

######################### Regexes ##################################
def compile(patterns: Iterable[str | re.Pattern]):
    """
    Compile a list of patterns
    """
    return [re.compile(p) for p in patterns]


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
    x in ("px","%","em") -> re.match(re_join("px","%","em"), x)
    """
    return "|".join(re.escape(x) for x in args)


# Reverse regex
"""
Search or replace in the regex from the end of the string.
The given regex will not be reversed TODO: implement this
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


# https://docs.python.org/3/library/re.html#simulating-scanf
int_re = r"[+-]?\d+"
pos_int_re = r"+?\d+"
# dec_re = rf"(?:{int_re})?(?:\.\d+)?(?:e{int_re})?"
dec_re = r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?"
# pos_dec_re = rf"(?:{pos_int_re})?(?:\.\d+)?(?:e{int_re})?"
units_re = re_join(*all_units)

regexes: dict[str, re.Pattern] = {
    k: re.compile(x)
    for k, x in {
        "integer": int_re,
        "number": dec_re,
        "percentage": rf"{dec_re}\%",
        "dimension": rf"(?:{dec_re})(?:\w+)",  # TODO: Use actual units
    }.items()
}

# for type checking
IsFunc = Callable[[str], re.Match | None]
is_integer: IsFunc
is_number: IsFunc

for key, regex in regexes.items():
    globals()[f"is_{key}"] = regex.fullmatch
# globals().update(
#     {
#         f"is_{key}": ()
#         for key, regex in regexes.items()
#     }
# )
##########################################################################


############################# Pygame related #############################

pg.init()


def draw_text(
    surf: Surface, text: str, fontname: str | None, size: int, color, **kwargs
):
    font: Any = freetype.SysFont(fontname, size)  # type: ignore[arg-type]
    color = Color(color)
    dest: Rect = font.get_rect(str(text))
    for k, val in kwargs.items():
        with suppress(AttributeError):
            setattr(dest, k, val)
    font.render_to(surf, dest=dest, fgcolor=color)


class Dotted:
    def __init__(
        self,
        dim,
        color,
        dash_size: int = 10,
        dash_width: int = 2,
        start_pos: Dimension = (0, 0),
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
