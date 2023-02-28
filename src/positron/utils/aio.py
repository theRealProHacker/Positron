"""
This module is explicitly for anything related to asyncio and I/O

This includes

async management,
logging,
downloading files,
fetching data from the web or the file system,

"""

import asyncio
import binascii
import errno
import inspect
import logging
import mimetypes
import os
import re
import socket
import sys
import uuid
from contextlib import asynccontextmanager, redirect_stdout, contextmanager, suppress
from dataclasses import dataclass
from enum import auto
from functools import cache, wraps
from typing import Callable, Literal
from urllib.parse import unquote_plus, urlparse

import positron.config as config
from positron.types import Enum, OpenMode, OpenModeReading, OpenModeWriting
from positron.utils.regex import GeneralParser, rev_sub
from positron.utils.func import group_by_bool

mimetypes.init()


# better aiofiles replacement
def _wrap(func):
    @wraps(func)
    async def inner(*args, **kwargs):
        return await asyncio.to_thread(func, *args, **kwargs)

    return inner


a_isfile = _wrap(os.path.isfile)
aos_remove = _wrap(os.remove)


async def acall(callback, *args, **kwargs):
    """
    Intelligently calls the callback with the given arguments, matching the most args
    """
    sig = inspect.signature(callback)
    _args = args[
        : min(
            len(
                [
                    param
                    for param in sig.parameters.values()
                    if not param.kind is inspect.Parameter.KEYWORD_ONLY
                ]
            ),
            len(args),
        )
    ]
    return await (
        callback(*_args, **kwargs)
        if inspect.iscoroutinefunction(callback)
        else asyncio.to_thread(callback, *_args, **kwargs)
    )


def call(callback, *args, **kwargs):
    """
    Synchronous version of acall
    """
    _args = args
    with suppress(ValueError):
        sig = inspect.signature(callback)
        _args = args[
            : min(
                len(
                    [
                        param
                        for param in sig.parameters.values()
                        if not param.kind is inspect.Parameter.KEYWORD_ONLY
                    ]
                ),
                len(args),
            )
        ]
    rv = callback(*_args, **kwargs)
    if inspect.isawaitable(rv):
        return create_task(rv)
    return rv
    # This below is actually nice but it is less flexible,
    # when it is not known whether callbacks are sync or async when defined (the real problem)
    # return (
    #     create_task(callback(*_args, **kwargs))
    #     if inspect.iscoroutinefunction(callback)
    #     else callback(*_args, **kwargs)
    # )


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
        task = cls(sync, coro, loop=config.event_loop, **kwargs)
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
    config.tasks.append(task)
    return task


def task_in_thread(func, *args, **kwargs):
    """
    Runs the given synchronous task as a thread
    """
    return create_task(asyncio.to_thread(func, *args, **kwargs))


async def gather_tasks(tasks: list[Task]):
    syncs, nosyncs = group_by_bool(tasks, lambda task: task.sync)
    tasks[:] = nosyncs
    if syncs:
        return await asyncio.wait(syncs)


@dataclass(frozen=True, slots=True)
class File:
    """
    A File object can be used to read and write to a file while saving its encoding and mime-type
    """

    name: str
    mime_type: str | None = None
    encoding: str | None = "utf-8"

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

    @asynccontextmanager
    async def aopen(self, mode: OpenMode, *args, **kwargs):
        if self.encoding:
            kwargs.setdefault("encoding", self.encoding)
        with await asyncio.to_thread(open, self.name, mode, *args, **kwargs) as f:
            yield f

    def read(self, mode: OpenModeReading = "r", *args, **kwargs):
        with self.open(mode, *args, **kwargs) as f:
            return f.read()

    aread = _wrap(read)

    def write(self, mode: OpenModeWriting = "w", *args, **kwargs):
        with self.open(mode, *args, **kwargs) as f:
            return f.write()

    awrite = _wrap(write)


def is_online() -> bool:
    # https://www.codespeedy.com/how-to-check-the-internet-connection-in-python/
    own_adress = socket.gethostbyname(socket.gethostname())
    return own_adress != "127.0.0.1"


created_files: set[str] = set()


def _make_new_filename(name):
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
        return create_file(_make_new_filename(file_name))


async def delete_created_files():
    global created_files
    if created_files:
        logging.info(f"Deleting: {created_files}")
        await asyncio.gather(
            *(aos_remove(file) for file in created_files),
            return_exceptions=True,
        )


save_dir = os.environ.get("TEMP") or "."


class ResponseType(Enum):
    HTTP = auto()
    Data = auto()
    File = auto()


# TODO: split up Response in RawResponse and StringResponse
@dataclass
class Response:
    url: str
    content: str | bytes
    type: ResponseType
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


media_type_pattern = re.compile(rf"[\w\-]+\/[\w\-]+(?:\;\w+\=\w+)*")


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


async def fetch(url: str, raw: bool = False) -> Response:
    """
    Fetch an url (into memory)

    Returns a Response or raises a ValueError if the url passed was invalid

    Also it might raise an aiohttp error
    """
    if url.startswith("http"):
        async with config.aiosession.get(url) as response:
            content_type = response.headers.get("content-type", "")
            mime_type, charset = parse_media_type(content_type)
            return Response(
                url=response.url.human_repr(),
                content=await response.read(),
                type=ResponseType.HTTP,
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
        url = url[5:]
        url = re.sub(r"\s*", "", url)  # remove all whitespace
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
            type=ResponseType.Data,
            _charset=charset,
            _mime_type=mime_type,
        )
    else:
        try:
            mode: Literal["rb", "r"] = "rb" if raw else "r"
            content = await File(url).aread(mode)
            return Response(url, content, ResponseType.File)
        except IOError as e:
            code: int = (
                403
                if e.errno == errno.EACCES
                else 404
                if e.errno == errno.ENOENT
                else 400
            )
            return Response(url, "", ResponseType.File, code)


async def download(url: str) -> str:
    """
    Instead of fetching the url into memory, the data is downloaded to a file
    """
    if url.startswith("http"):
        async with config.aiosession.get(url) as resp:
            new_file = create_file(os.path.basename(urlparse(url).path))
            async with File(new_file).aopen("wb") as f:
                async for chunk in resp.content.iter_any():
                    await f.write(chunk)
        return new_file
    elif url.startswith("data"):
        logging.warning(
            "Downloading data URI. This means you are likely putting something into a data uri that is too big (like an image)"
        )
        response = await fetch(url)
        new_file = create_file(uuid.uuid4().hex)
        await File(new_file).awrite(
            "wb" if isinstance(response.content, bytes) else "w"
        )
        return new_file
    else:
        if await a_isfile(url):
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
