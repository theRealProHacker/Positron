import os
import webbrowser
from enum import auto
from typing import Callable
from urllib.parse import parse_qsl, urlparse

import pygame as pg

import config
import Element
import util
from config import g
from own_types import V_T, Enum, Event

LOADPAGE = pg.event.custom_type()
URL = str


######################### History ##########################################


class UrlLookupResult(Enum):
    Internal = auto()  # The URL was handled internally and resolved to an html file
    Browser = auto()  # The URL was opened in a browser
    Invalid = auto()  # The URL was invalid


class History(list[V_T]):
    """
    A generalized History of things. Subclasses list for maximum usability
    """

    cur = -1

    @property
    def current(self):
        # TODO: What should we do when the history is empty?
        return self[self.cur]

    # Navigation
    def back(self):
        self.cur = max(0, self.cur - 1)

    def can_go_back(self) -> bool:
        return bool(self.cur)

    def forward(self):
        self.cur = min(len(self) - 1, self.cur + 1)

    def can_go_forward(self) -> bool:
        return bool(self.cur - len(self) + 1)

    def add_entry(self, entry: V_T):
        self.cur += 1
        self[:] = [*self[: self.cur], entry]

    # overrides
    def clear(self):
        super().clear()
        del self.cur


############################# Site navigation ############################

routes: dict[str, Callable] = {}
history = History[URL]()
visited_links: dict[URL, UrlLookupResult] = {}


def add_route(route: str):
    if not isinstance(route, str):
        raise ValueError("route must be a String")

    def inner(route_func: Callable):
        routes[route] = route_func
        return route_func

    return inner


def goto(url: URL, **kwargs: str) -> UrlLookupResult:
    """
    Make the browser display a different page if it is a registered route or open the page
    Raises a KeyError if the route is invalid.
    """
    status = visited_links.get(url, UrlLookupResult.Internal)
    if status == UrlLookupResult.Invalid:
        return status  # we already reported that the url is invalid
    elif status == UrlLookupResult.Internal:
        parsed_result = urlparse(url)
        route = parsed_result.path
        try:
            callback = routes[route]
        except KeyError:  # no registered route
            if os.path.isfile(path := os.path.abspath(route)):

                def callback(**kwargs):
                    load_dom(path, **kwargs)

            else:
                status = UrlLookupResult.Browser
        if status == UrlLookupResult.Internal:
            pg.event.post(
                Event(
                    LOADPAGE,
                    url=url,
                    callback=callback,
                    kwargs=dict(parse_qsl(parsed_result.query)) | kwargs,
                    target=parsed_result.fragment,
                )
            )
            visited_links[url] = status
            return status
    if not webbrowser.open_new_tab(url):
        status = UrlLookupResult.Invalid
        util.log_error(f"Invalid route: {url!r}")
    visited_links[url] = status
    return status


def back():
    history.back()
    goto(history.current)


def forward():
    history.forward()
    goto(history.current)


def push(url: URL):
    """
    Opens the url and pushes it onto the history if it is navigated on.
    """
    if goto(url) == UrlLookupResult.Internal:
        history.add_entry(url)


def get_url() -> URL:
    return history.current


def reload():
    # TODO: API for full reload
    goto(history.current)


def load_dom(file: str, *args, **kwargs):
    html = config.jinja_env.from_string(util.File(file).read()).render(*args, **kwargs)
    g["root"] = Element.HTMLElement.from_string(html)
    config.file_watcher.add_file(file, reload)


async def aload_dom(url: str):
    html = await config.jinja_env.from_string(await util.fetch_txt(url)).render_async()
    g["root"] = Element.HTMLElement.from_string(html)


##########################################################################
