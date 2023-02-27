from __future__ import annotations

import os
import webbrowser
from dataclasses import dataclass, field
from enum import auto
from typing import Any, Callable
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

import pygame as pg

import positron.config as config
import positron.Element as Element
import positron.util as util
from positron.config import g
from positron.types import V_T, Enum, Event

LOADPAGE = pg.event.custom_type()


__all__ = ["URL", "history", "back", "forward", "push", "get_url", "reload"]


@dataclass(frozen=True)
class URL:
    route: str  # aka path
    kwargs: dict[str, Any] = field(default_factory=dict)  # aka query
    target: str = ""  # aka fragment
    scheme: str = ""
    netloc: str = ""
    params: str = ""

    def __str__(self):
        query = urlencode(self.kwargs)
        return urlunparse(
            (self.scheme, self.netloc, self.route, self.params, query, self.target)
        )

    def __hash__(self) -> int:
        # we want to hash like our counterpart strings
        return hash(str(self))

    def __eq__(self, other):
        if not isinstance(other, (URL, str)):
            raise NotImplemented
        return str(self) == str(other)


AnyURL = URL | str


def make_url(url: AnyURL) -> URL:
    if isinstance(url, URL):
        return url
    parsed = urlparse(url)
    return URL(
        parsed.path,
        dict(parse_qsl(parsed.query)),
        parsed.fragment,
        parsed.scheme,
        parsed.netloc,
        parsed.params,
    )


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
visited_links: dict[AnyURL, UrlLookupResult] = {}


def add_route(route: str):
    if not isinstance(route, str):
        raise ValueError("route must be a String")

    def inner(route_func: Callable):
        routes[route] = route_func
        return route_func

    return inner


def goto(url: AnyURL) -> UrlLookupResult:
    """
    Make the browser display a different page if it is a registered route
    or try to open the page in the default webbrowser.

    Example:

    goto("google.com") -> UrlLookupResult.Browser
    will open the users browser with the given URL

    goto("/") -> UrlLookupResult.Internal
    will navigate to the route "/" if possible but without pushing it onto the history

    goto("index.html") -> UrlLookupResult.Internal
    will open the file index.html in the cwd if possible
    """
    status = visited_links.get(url, UrlLookupResult.Internal)
    if status == UrlLookupResult.Invalid:
        return status  # we already reported that the url is invalid
    elif status == UrlLookupResult.Internal:
        _url = make_url(url)
        callback = routes.get(_url.route)
        if callback is None and os.path.isfile(path := os.path.abspath(_url.route)):

            def callback(**kwargs):
                load_dom(path, **kwargs)

        elif callback is None:
            status = UrlLookupResult.Browser
        # only post if still Internal
        if status == UrlLookupResult.Internal:
            pg.event.post(Event(LOADPAGE, url=_url, callback=callback))
    if status == UrlLookupResult.Browser:
        if not webbrowser.open_new_tab(str(url)):
            status = UrlLookupResult.Invalid
            util.log_error(f"Invalid route: {url!r}")
    visited_links[url] = status
    return status


def back():
    """
    Navigates back if possible
    """
    history.back()
    goto(history.current)


def forward():
    """
    Navigates forward if possible
    """
    history.forward()
    goto(history.current)


def push(url: str | URL):
    """
    Opens the url and pushes it onto the history if it is actually navigated to.
    """
    if goto(url) == UrlLookupResult.Internal:
        history.add_entry(make_url(url))


def get_url() -> URL:
    """
    Get the current URL
    """
    return history.current


def reload():
    """
    Reloads the current dom
    """
    # TODO: API for full reload
    goto(history.current)


def load_dom_frm_str(html: str, *args, **kwargs):
    """
    Loads the dom from the given html or jinja markup
    """
    html = config.jinja_env.from_string(html).render(*args, **kwargs)
    g["root"] = Element.HTMLElement.from_string(html)


async def aload_dom_frm_str(html: str, *args, **kwargs):
    """
    Loads the dom from the given html or jinja markup asynchronously
    """
    html = config.jinja_env.from_string(html).render(*args, **kwargs)
    g["root"] = Element.HTMLElement.from_string(html)


def load_dom(file: str, *args, **kwargs):
    """
    Loads the dom from a file
    """
    html = config.jinja_env.from_string(util.File(file).read()).render(*args, **kwargs)
    g["root"] = Element.HTMLElement.from_string(html)
    config.file_watcher.add_file(file, reload)


async def aload_dom(url: AnyURL):
    """
    Loads the dom from any url asynchronously
    """
    response = await util.fetch(str(url))
    kwargs = make_url(url).kwargs if response.type == util.ResponseType.File else {}
    html = await config.jinja_env.from_string(response.text).render_async(**kwargs)
    g["root"] = Element.HTMLElement.from_string(html)


##########################################################################
