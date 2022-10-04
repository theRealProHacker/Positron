"""
An EventManager takes pygame events and handles them correctly. 
"""
from collections import defaultdict
from enum import IntEnum
from functools import partial
import time
from typing import Any, Callable, Generic
from weakref import WeakKeyDictionary

import pygame as pg

import Element
from own_types import K_T, V_T
import util
from config import g, set_mode


class KeyLocation(IntEnum):
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
    location: KeyLocation = KeyLocation.INVALID
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
    "click": {
        "bubbles": True,
        "attrs": ("pos", "mods", "button", "buttons", "detail"),
    },
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
    "online": {},
    "offline": {},
    "resize": {"attrs": ("size",)},
    # window events
    **{k.lower(): {} for k in dir(pg) if k.startswith("WINDOW")},
}
for x in ("windowmoved", "windowsizechanged"):
    supported_events[x]["attrs"] = ("x", "y")


class defaultweakdict(Generic[K_T, V_T], defaultdict[K_T, V_T], WeakKeyDictionary):  # type: ignore
    pass


class EventManager:
    callbacks: defaultdict[str, defaultweakdict[Element.Element, list[CallbackItem]]]
    last_click: tuple[float, tuple[int, int]] = (0, (-1, -1))
    click_count: int = 0
    mouse_pos = pg.mouse.get_pos()
    mods: int = pg.key.get_mods()
    drag: None | tuple[tuple[int, int], None | Element.Element] = None
    online = util.is_online()
    keys_down: set[int] = set()
    buttons_down: set[int] = set()

    @property
    def buttons(self):
        sum(2 ** (x - 1) for x in self.buttons_down)

    def __init__(self):
        self.callbacks = defaultdict(partial(defaultweakdict, list))

    async def release_event(
        self, type_: str, target: Element.Element | None = None, **kwargs
    ):
        """
        Release an event with the type_ and the keyword arguments.
        This deals with calling all appropriate callbacks
        """
        # First we get the target, which by default is the root element
        # then we call all callbacks registered on this event_type and target
        # Every callback has a number of times it will be executed.
        # This number is decreased and if it falls to 0, the callback is removed.
        target: Element.Element = util.make_default(target, g["root"])
        event = _Event(time.monotonic(), type_, target, kwargs)
        old_callbacks: list[CallbackItem] = self.callbacks[type_][target]
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
        self.callbacks[type_][target] = new_callbacks + old_callbacks
        if (
            not event.cancelled
            and (callback := getattr(target, f"on_{type_}", None)) is not None
        ):
            await util.call(callback, event)
        if (
            event.propagation
            and (event_data := supported_events.get(type_)) is not None
            and event_data.get("bubbles")
            and target.parent is not None
        ):
            await self.release_event(type_, target=target.parent, **kwargs)

    async def handle_events(self, events: list[pg.event.Event]):
        # online, offline
        online = util.is_online()
        if self.online and not online:
            await self.release_event("offline")
        elif not self.online and online:
            await self.release_event("online")
        self.online = online
        # event handling
        root: Element.Element
        # TODO: What is event.window?
        for event in events:
            ########################## Mouse Events ##############################################
            if (_type := pg.event.event_name(event.type).lower()).startswith("mouse"):
                # pygame buttons are 123, css buttons are 012
                # https://developer.mozilla.org/en-US/docs/Web/API/MouseEvent/button#value
                if event.type in (pg.MOUSEBUTTONDOWN, pg.MOUSEBUTTONUP):
                    button = event.button
                root = g["root"]
                _pos = getattr(event, "pos", self.mouse_pos)
                collisions = [root.collide(_pos)]
            if event.type == pg.MOUSEBUTTONDOWN:
                self.buttons_down.add(button)
                for elem in collisions:
                    await self.release_event(
                        "mousedown",
                        target=elem,
                        pos=_pos,
                        mods=self.mods,
                        button=button,
                    )
                self.mouse_down = _pos
            elif event.type == pg.MOUSEBUTTONUP:
                self.buttons_down.remove(button)
                if self.drag:
                    for elem in collisions:
                        await self.release_event(
                            "mouseup",
                            target=elem,
                            pos=_pos,
                            mods=self.mods,
                            buttons=self.buttons,
                        )
                    # dragend/drop
                    pos, dragged_elem = self.drag
                    self.drag = None
                    if dragged_elem is not None:
                        await self.release_event(
                            "dragend", target=dragged_elem, frm=pos, to=event.pos
                        )
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
                    for elem in collisions:
                        await self.release_event(
                            "mouseup",
                            target=elem,
                            pos=event.pos,
                            mods=self.mods,
                            buttons=self.buttons,
                        )
                        await self.release_event(
                            "click" if button == 1 else "auxclick",
                            target=elem,
                            pos=event.pos,
                            mods=self.mods,
                            button=button,
                            buttons=self.buttons,
                            detail=self.click_count,
                        )
                    self.last_click = (time.monotonic(), _pos)
            elif event.type == pg.MOUSEMOTION:
                self.mouse_pos = _pos
                for elem in collisions:
                    await self.release_event(
                        "mousemove",
                        target=elem,
                        pos=_pos,
                        mods=self.mods,
                        buttons=event.buttons,
                    )
                # TODO: hover elements
                for elem in root.iter_desc():
                    hover = elem in collisions
                    if elem.hover and not hover:
                        # mouseleave
                        pass
                    elif not elem.hover and hover:
                        # mouseenter
                        pass
                    elem.hover = hover

                # if not self.drag and self.mouse_down:
                #     # TODO: get the first draggable element colliding with the mouse
                #     self.drag = (self.mouse_down, None)
            elif event.type == pg.MOUSEWHEEL:
                # TODO: What is flipped?
                for elem in collisions:
                    await self.release_event(
                        "wheel",
                        target=elem,
                        pos=_pos,
                        mods=self.mods,
                        buttons=self.buttons,
                        delta=(event.x, event.y),
                    )
                # TODO: emit the scroll event on the first scollable element
            ########################## Keyboard Events ############################################
            # For KeyEvents https://w3c.github.io/uievents/#idl-keyboardevent
            # key: Which key was pressed (str). default "" # just like pg.Event.unicode or "Shift" or "Dead" for example when pressing `
            # code: which code the pressed key corresponds to (str). default "" just like pg.event.key
            # location: the physical location of the key pressed (int). default 0
            # mods: ctrl, shiftkey, altkey, metakey (only MacOS) see pygame documentation
            # repeat: Whether the key was pressed continiously (and not the first time) (bool). default False

            elif event.type == pg.KEYDOWN:
                await self.release_event(
                    "keydown",
                )
                self.mods = event.mod
            elif event.type == pg.KEYUP:
                self.mods = event.mod
            elif event.type == pg.TEXTEDITING:
                # no idea what this even is exactly, cause I don't have any textediting software installed
                pass
            elif event.type == pg.TEXTINPUT:
                if not any(event.type == pg.KEYDOWN for event in events):
                    # repeating KEYDOWN
                    pass
                # text input
                print(event)
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

    def on(
        self,
        __type: str,
        __callback: Callback,
        __repeat: int = -1,
        target: None | Element.Element = None,
    ):
        """
        Register a callback to be called when the events of type __type occur.
        It will be called __repeat many times or infinite times if < 0.
        Also you can give a target to attach to the event.
        The callback will only be called when the target matches the specified
        """
        _target = target if target is not None else g["root"]
        if __repeat:
            self.callbacks[__type.lower()][_target].append((__callback, __repeat))


# @dataclass
# class Key:
#     key: int
#     modifiers: list[int] = field(default_factory=list)


# class Keys:
#     keys: set[Key]

#     def __init__(self, any: Any):
#         if isinstance(any, int):
#             self.keys = {Key(int)}
#         elif isinstance(any, Key):
#             self.keys = {any}
#         elif isinstance(any, Iterable):
#             self.keys = set(any)
#         elif isinstance(any, str):
#             self.keys = self.from_string(any)

#     def from_string(s: str) -> set[Key]:
#         """ """
