"""
An EventManager takes pygame events and handles them correctly. 
"""
import re
import time
from collections import defaultdict
from enum import IntEnum
from typing import Any, Callable
from weakref import WeakKeyDictionary

import pygame as pg

import Element
from own_types import Cursor
import util
from config import g, set_mode


class KeyboardLocation(IntEnum):
    INVALID = 0
    STANDARD = 1
    LEFT = 2
    RIGHT = 3
    NUMPAD = 4


class _Event:
    """
    An internal Event that gets passed to callbacks
    """

    timestamp: float
    type: str
    target: Element.Element
    current_target: Element.Element
    cancelled: bool = False
    propagation: bool = True
    immediate_propagation: bool = True

    # mouse events
    pos: tuple[int, int] = (0, 0)
    mods: int = 0
    button: int = 0
    buttons: int = 0
    detail: int = 0
    delta: tuple[int, int] = (0, 0)
    # for mouseevents relative to events like mouseout
    related_target: Element.Element | None = None
    # keyboard events
    key: str = ""
    code: str = ""
    location: KeyboardLocation = KeyboardLocation.INVALID
    # other
    x: int = 0
    y: int = 0

    def __init__(
        self,
        timestamp: float,
        type_: str,
        target: Element.Element,
        kwargs: dict[str, Any],
    ):
        self.timestamp = timestamp
        self.type = type_
        self.target = target
        self.current_target = target
        self.__dict__.update(kwargs)

    def __str__(self) -> str:
        attrs = ", ".join(f"{k} = {v}" for k, v in self.__dict__.items())
        return f"Event({attrs})"


# Events to implement
# https://w3c.github.io/uievents/
# File dropping can be done by looking for the DROPBEGIN Event.
# Then we can track the mouse position to tell elements, we are currently dragging something.
# Drag links:
#   https://developer.mozilla.org/en-US/docs/Web/API/HTML_Drag_and_Drop_API
#   https://developer.mozilla.org/en-US/docs/Web/API/HTML_Drag_and_Drop_API/Drag_operations#specifying_drop_targets
#   https://developer.mozilla.org/en-US/docs/Web/API/DataTransfer/types
#   https://developer.mozilla.org/en-US/docs/Web/API/HTMLElement/dragstart_event
#   https://developer.mozilla.org/en-US/docs/Web/API/HTMLElement/dragend_event
#   https://html.spec.whatwg.org/multipage/dnd.html#dnd

Callback = Callable
CallbackItem = tuple[Callback, int]

# bubbles: bool = False
# attrs: tuple = ()
supported_events: dict[str, dict[str, Any]] = {
    **dict.fromkeys(
        ("click", "auxclick"),
        {
            "bubbles": True,
            "attrs": ("pos", "mods", "button", "buttons", "detail"),
        },
    ),
    "mousedown": {
        "bubbles": True,
        "attrs": ("pos", "mods", "buttons"),
    },
    "mouseup": {
        "bubbles": True,
        "attrs": ("pos", "mods", "buttons"),
    },
    "mousemove": {
        "bubbles": True,
        "attrs": ("pos", "mods", "buttons"),
    },
    "wheel": {"bubbles": True, "attrs": ("pos", "mods", "buttons", "delta")},
    "keydown": {
        "bubbles": True,
        "attrs": ("key", "code", "pgcode", "location", "mods", "repeat"),
    },
    "online": {},
    "offline": {},
    "resize": {"attrs": ("size",)},
    # window events
    **{k.lower(): {} for k in dir(pg) if k.startswith("WINDOW")},
}
for x in ("windowmoved", "windowsizechanged"):
    supported_events[x]["attrs"] = ("x", "y")

_ctrl_ident_re = re.compile(r"[\w_]+|.")


def ctrl_del(v: str):
    parser = util.GeneralParser(v)
    if not parser.consume(Element.whitespace_re):
        parser.consume(_ctrl_ident_re)
    return parser.x


def ctrl_backspace(v: str):
    parser = util.GeneralParser(v[::-1])
    parser.consume(Element.whitespace_re)
    parser.consume(_ctrl_ident_re)
    return parser.x[::-1]


class EventManager:
    callbacks: defaultdict[str, WeakKeyDictionary[Element.Element, list[CallbackItem]]]
    last_click: tuple[float, tuple[int, int]] = (0, (-1, -1))
    click_count: int = 0
    mouse_pos = pg.mouse.get_pos()
    mods: int = pg.key.get_mods()
    online = util.is_online()
    keys_down: set[int] = set()
    buttons_down: set[int] = set()
    cursor: Any = Cursor()

    drag: Element.Element | None = None
    focus: Element.Element | None = None
    active: Element.Element | None = None
    hover: Element.Element | None = None

    @property
    def buttons(self):
        sum(2 ** (x - 1) for x in self.buttons_down)

    def __init__(self):
        self.callbacks = defaultdict(WeakKeyDictionary)

    def change(self, name: str, value: Any) -> bool:
        if getattr(self, name) == value:
            return False
        else:
            setattr(self, name, value)
            return True

    async def release_event(
        self, type_: str, target: Element.Element | None = None, **kwargs
    ):
        """
        Release an event with the type_ and the keyword arguments.
        This deals with calling all appropriate callbacks
        """
        # First we get the target, which by default is the root element
        # then we call all callbacks
        target: Element.Element = target or g["root"]
        event = _Event(time.monotonic(), type_, target, kwargs)
        await self.call_callbacks(event)
        if supported_events.get(type_, {}).get("bubbles"):
            while event.propagation and (parent := event.current_target.parent):
                event.current_target = parent
                await self.call_callbacks(event)

    async def call_callbacks(self, event: _Event):
        # Every callback has a number of times it will be executed.
        # This number is decreased and if it falls to 0, the callback is removed.
        old_callbacks: list[CallbackItem] = self.callbacks[event.type].get(
            event.current_target, []
        )
        new_callbacks: list[CallbackItem] = []
        for callback, repeat in util.consume_list(old_callbacks):
            try:
                await util.call(callback, event)
            except Exception as e:
                util.log_error(f"Exception in callback: {e}")
            if repeat != 1:
                new_callbacks.append((callback, repeat - 1))
            # MDN: "If stopImmediatePropagation is invoked during one such call[back], no remaining listeners will be called."
            if not event.immediate_propagation:
                break
        self.callbacks[event.type][event.current_target] = new_callbacks + old_callbacks
        # the default action if defined
        if (
            not event.cancelled
            and (callback := getattr(event.current_target, f"on_{event.type}", None))
            is not None
        ):
            await util.call(callback, event)

    async def handle_events(self, events: list[pg.event.Event]):
        # online, offline
        online = util.is_online()
        if self.change("online", online):
            await self.release_event("online" if online else "offline")
        # event handling
        root: Element.Element
        # TODO: What is event.window? Can we just ignore it?
        async def edit(func):
            try:
                if self.focus:
                    self.focus.editcontent(func)
                    await self.release_event("input", self.focus)  # TODO: kwargs
            except Element.NotEditable:
                pass

        for event in events:
            ########################## Mouse Events ##############################################
            if (_type := pg.event.event_name(event.type).lower()).startswith("mouse"):
                # pygame buttons are 123, css buttons are 012
                # https://developer.mozilla.org/en-US/docs/Web/API/MouseEvent/button#value
                if event.type in (pg.MOUSEBUTTONDOWN, pg.MOUSEBUTTONUP):
                    button = event.button
                root = g["root"]
                _pos = getattr(event, "pos", self.mouse_pos)
                hov_elem = root.collide(_pos) or root
                # assert hov_elem is not None TODO: why does this fail sometimes if `or root` is removed above
                if self.change("hover", hov_elem):
                    # TODO: mouseenter, mouseleave
                    # TODO: mouseover, mouseout
                    g["css_dirty"] = True  # :hover
                cursor = hov_elem.cursor
                if self.change("cursor", cursor):
                    pg.mouse.set_cursor(cursor)
            if event.type == pg.MOUSEBUTTONDOWN:
                self.buttons_down.add(button)
                await self.release_event(
                    "mousedown",
                    target=hov_elem,
                    pos=_pos,
                    mods=self.mods,
                    button=button,
                    buttons=self.buttons,
                )
                if button == 1:
                    if self.change("active", hov_elem):
                        g["css_dirty"] = True
                    # FIXME: This is ad-hoc focus
                    # https://html.spec.whatwg.org/multipage/interaction.html#focusable-area
                    if self.change("focus", hov_elem):
                        g["css_dirty"] = True  # :focus
                        await self.release_event("focus", hov_elem)
                self.mouse_down = _pos
            elif event.type == pg.MOUSEBUTTONUP:
                self.buttons_down.remove(button)
                await self.release_event(
                    "mouseup",
                    target=hov_elem,
                    pos=_pos,
                    mods=self.mods,
                    button=button,
                    buttons=self.buttons,
                )
                if self.drag:
                    # dragend/drop
                    # TODO: emit more drag events
                    await self.release_event(
                        "dragend",
                        target=self.drag,
                    )
                    self.drag = None
                else:
                    # click
                    # there is no current drag and the primary mouse button goes down
                    last_click_time, last_click_pos = self.last_click
                    if not (
                        time.monotonic() - last_click_time <= 0.5
                        and last_click_pos == _pos
                    ):
                        self.click_count = 0
                    self.click_count += 1
                    if hov_elem is self.active or button != 1:
                        await self.release_event(
                            "click" if button == 1 else "auxclick",
                            target=hov_elem,
                            pos=event.pos,
                            mods=self.mods,
                            button=button,
                            buttons=self.buttons,
                            detail=self.click_count,
                        )
                        if button == 3:
                            pass  # TODO: contextmenu
                    self.active = None
                    g["css_dirty"] = True
                    self.last_click = (time.monotonic(), _pos)
            elif event.type == pg.MOUSEMOTION:
                self.mouse_pos = _pos
                await self.release_event(
                    "mousemove",
                    target=hov_elem,
                    pos=_pos,
                    mods=self.mods,
                    buttons=event.buttons,
                )
                # if not self.drag and self.mouse_down:
                #     # TODO: get the first draggable element colliding with the mouse
            elif event.type == pg.MOUSEWHEEL:
                # TODO: What is event.flipped?
                await self.release_event(
                    "wheel",
                    target=hov_elem,
                    pos=_pos,
                    mods=self.mods,
                    buttons=self.buttons,
                    delta=(event.x, event.y),
                )
                # TODO: emit the scroll event on the first scrollable element
            ########################## Keyboard Events ############################################
            # For KeyEvents https://w3c.github.io/uievents/#idl-keyboardevent
            # key: Which key was pressed (str). default "" # just like pg.Event.unicode or "Shift" or "Dead" for example when pressing `
            # code: which code the pressed key corresponds to (str). default "" just like pg.event.key
            # location: the physical location of the key pressed (KeyboardLocation). default INVALID
            # mods: ctrl, shiftkey, altkey, metakey (only MacOS). see pygame documentation
            # repeat: Whether the key was pressed continuously (and not the first time) (bool). default False

            elif event.type == pg.KEYDOWN:
                await self.release_event(
                    "keydown",
                    target=self.focus,
                    key=event.unicode,
                    code=pg.key.name(event.key),
                    pgcode=event.key,  # inofficial
                    # TODO: location
                    mods=event.mod,
                    # TODO: repeat = event.key in self.pressed_keys
                )
                if event.key == pg.K_BACKSPACE:
                    await edit(
                        ctrl_backspace if event.mod & pg.KMOD_CTRL else lambda v: v[:-1]
                    )
                elif event.key == pg.K_DELETE:
                    await edit(
                        ctrl_del if event.mod & pg.KMOD_CTRL else lambda v: v[1:]
                    )
                self.mods = event.mod
            elif event.type == pg.KEYUP:
                self.mods = event.mod
            elif event.type == pg.TEXTEDITING:
                # TODO: composition start
                pass
            elif event.type == pg.TEXTINPUT:
                # TODO: composition end (and start before if not started already)
                await edit(lambda v: v + event.text)
            ########################## Window Events ##############################################
            elif event.type == pg.WINDOWRESIZED:
                g["W"] = event.x
                g["H"] = event.y
                await set_mode()
                g["css_dirty"] = True
                await self.release_event("resize", size=(event.x, event.y))
            elif _type.startswith("window"):
                await self.release_event(_type, **event.__dict__)
            elif event.type == pg.ACTIVEEVENT:
                # whether the mouse is active on the window
                pass
        # TODO: mouseover, -leave, -enter and -exit

    def on(
        self,
        __type: str,
        __callback: Callback,
        __repeat: int = -1,
        target: None | Element.Element = None,
        path: None | str = None,
    ):
        """
        Register a callback to be called when the events of type __type occur.
        It will be called __repeat many times or infinite times if < 0.
        Also you can give a target to attach to the event.
        The callback will only be called when the target matches the specified
        if you want to hook into a file-modified event set path to the path that
        should be observed.
        """
        __type = __type.lower()
        _target = target if target is not None else g["root"]
        if __repeat:
            self.callbacks[__type][_target] = [
                *self.callbacks[__type].get(_target, []),
                (__callback, __repeat),
            ]
        if __type == "file-modified":
            if path is None:
                raise ValueError(
                    "You must set path when hooking into a file-modified event"
                )
            g["file_watcher"].add_file(path)
