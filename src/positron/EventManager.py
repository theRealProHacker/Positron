"""
An EventManager takes pygame events and handles them correctly. 

The EventManager is responsible for handling the following:
- event handling, propagation and callback calling
- mouse, keyboard and other input sources
- hover, focus and other element states
- modals
"""

import time
from collections import defaultdict
from dataclasses import dataclass
from itertools import count
from typing import Any, Callable, Sequence
from weakref import WeakKeyDictionary

import pygame as pg

import positron.config as config
import positron.utils.aio as autils
from positron.utils.func import join

from .config import ALT_MB, MAIN_MB, MIDDLE_MB, g
from .Element import AnchorElement, Element, HTMLElement, InputElement
from .events.InputType import *
from .modals import *
from .types import Cursor, Surface
from .utils.clipboard import get_clip, put_clip

UIElem = Element | Modal


class _Event:
    """
    An Event that gets passed to callbacks
    """

    timestamp: float
    type: str
    target: UIElem
    current_target: Element
    cancelled: bool = False
    """ A cancelled event is almost like an event that never happened """
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
    related_target: UIElem | None = None
    # keyboard events
    key: str = ""
    code: str = ""
    # other
    x: int = 0
    y: int = 0

    def __init__(
        self, timestamp: float, type_: str, target: UIElem | None = None, **kwargs: Any
    ):
        self.timestamp = timestamp
        self.type = type_
        target = target or g["root"]
        self.target = target
        self.current_target = target  # type: ignore
        self.__dict__.update(kwargs)

    def __str__(self) -> str:
        attrs = ", ".join(f"{k} = {v}" for k, v in self.__dict__.items())
        return f"Event({attrs})"


# Events to implement
# https://w3c.github.io/uievents/
# File dropping can be done by looking for the DROPBEGIN Event.
# Then we can track the mouse position to tell elements, we are
# currently dragging something over.
# Drag links:
#   https://developer.mozilla.org/en-US/docs/Web/API/HTML_Drag_and_Drop_API
#   https://developer.mozilla.org/en-US/docs/Web/API/HTML_Drag_and_Drop_API/Drag_operations#specifying_drop_targets
#   https://developer.mozilla.org/en-US/docs/Web/API/DataTransfer/types
#   https://developer.mozilla.org/en-US/docs/Web/API/HTMLElement/dragstart_event
#   https://developer.mozilla.org/en-US/docs/Web/API/HTMLElement/dragend_event
#   https://html.spec.whatwg.org/multipage/dnd.html#dnd

Callback = Callable
CallbackItem = tuple[Callback, int]


@dataclass
class EventData:
    bubbles: bool = False
    attrs: tuple = ()


supported_events: dict[str, EventData] = {
    ### Mouse Events
    **dict.fromkeys(
        ("click", "auxclick", "contextmenu"),
        EventData(bubbles=True, attrs=("pos", "mods", "button", "buttons", "detail")),
    ),
    **dict.fromkeys(
        ("mousedown", "mouseup", "mousemove"),
        EventData(bubbles=True, attrs=("pos", "mods", "buttons")),
    ),
    "wheel": EventData(bubbles=True, attrs=("pos", "mods", "buttons", "delta")),
    **dict.fromkeys(
        ("focus", "blur"),
        EventData(attrs=("related_target",)),
    ),
    ### Keyboard Events
    "keydown": EventData(
        bubbles=True, attrs=("key", "code", "pgcode", "mods", "repeat")
    ),
    "beforeinput": EventData(attrs=("input_type",)),
    "input": EventData(),
    # Global Events
    "online": EventData(),
    "offline": EventData(),
    "resize": EventData(attrs=("size",)),
    # Window Events
    **dict.fromkeys(
        (k.lower() for k in dir(pg) if k.startswith("WINDOW")), EventData()
    ),
    "windowmoved": EventData(attrs=("x", "y")),
    "windowsizechanged": EventData(attrs=("x", "y")),
}


def is_focusable(elem: UIElem) -> bool:
    """
    Whether a UIElem is focusable
    """
    return (
        not isinstance(elem, Element)
        or isinstance(elem, (AnchorElement, InputElement))
        and not elem.disabled
    )


class EventManager:
    callbacks: defaultdict[str, WeakKeyDictionary[UIElem, list[CallbackItem]]]
    modals: list[Modal]
    # Event handling
    last_click: tuple[float, tuple[int, int]] = (0, (-1, -1))
    click_count: int = 0
    is_composing: bool = False
    mouse_pos: tuple[int, int]
    mods: int
    keys_down: set[int]
    buttons_down: set[int]
    cursor: Any = Cursor()
    online: bool

    drag: UIElem | None = None
    focus: UIElem | None = None
    active: UIElem | None = None
    hover: UIElem | None = None

    @property
    def buttons(self):
        sum(2 ** (x - 1) for x in self.buttons_down)

    def __init__(self):
        self.callbacks = defaultdict(WeakKeyDictionary)
        self.modals = []
        self.mouse_pos = pg.mouse.get_pos()
        self.mods = pg.key.get_mods()
        # TODO: get the actual keys down right now
        self.keys_down = set()
        self.buttons_down = {
            i + 1 for (i, bool) in enumerate(pg.mouse.get_pressed()) if bool
        }
        self.online = autils.is_online()

    def reset(self):
        # XXX: we don't update some things like mouse_pos
        # because they are route unspecific
        self.callbacks = defaultdict(WeakKeyDictionary)
        self.modals.clear()
        self.last_click = (0, (-1, -1))
        self.click_count = 0
        self.cursor = Cursor()
        self.drag = None
        self.focus = None
        self.active = None
        self.hover = None

    def change(self, name: str, value: Any) -> bool:
        """
        A very handy method that sets self.{name} to value and returns whether it changed
        """
        if getattr(self, name) == value:
            return False
        else:
            setattr(self, name, value)
            return True
        # for fun: use that setattr always returns None
        # return getattr(self, name) != value and (setattr(self, name, value) or True)

    def release(self, event: _Event):
        # Modal
        if not isinstance(event.target, Element):
            if (
                callback := getattr(event.current_target, f"on_{event.type}", None)
            ) is not None:
                autils.call(callback, event)
            return
        # Elements
        self.call_callbacks(event)
        if supported_events.get(event.type, EventData()).bubbles:
            while (
                event.immediate_propagation
                and event.propagation
                and (parent := event.current_target.parent)
            ):
                event.current_target = parent
                self.call_callbacks(event)

    def release_event(self, type_: str, target: UIElem | None = None, **kwargs):
        """
        Release an event with the type_ and the given kwargs.
        This deals with calling all appropriate callbacks
        """
        # First we get the target, which by default is the root element
        # then we call all callbacks
        event = _Event(time.monotonic(), type_, target, **kwargs)
        self.release(event)
        # Not cancellable default actions
        if type_ == "focus":
            self.focus = event.target
            g["css_dirty"] = True  # :focus
        elif type_ == "blur" and self.focus == event.target:
            self.focus = event.related_target
        # Some default default actions ;)
        if event.cancelled:
            return event
        return event

    def call_callbacks(self, event: _Event):
        """
        Calls all callbacks that are registered for the events target and type.

        Every callback has a number of times it will be executed.
        This number is decreased and if it falls to 0, the callback is removed.
        """
        callbacks = [
            (callback, repeat - 1)
            for (callback, repeat) in self.callbacks[event.type].get(
                event.current_target, []
            )
            if repeat != 1
        ]
        self.callbacks[event.type][event.current_target] = callbacks
        for callback, _ in callbacks:
            try:
                # print(f"Called {callback=} on {event.target=}")
                autils.call(callback, event)
            except Exception as e:
                autils.log_error(f"Exception in callback: {e}")
            # MDN: "If stopImmediatePropagation is invoked during one such call[back], no remaining listeners will be called."
            if not event.immediate_propagation:
                break
        # if the event was not cancelled the default action is called if defined on the element
        if (
            not event.cancelled
            and (
                elem_callback := getattr(event.current_target, f"on_{event.type}", None)
            )
            is not None
        ):
            autils.call(elem_callback, event)

    async def handle_events(self, events: list[pg.event.Event]):
        # online, offline
        online = autils.is_online()
        if self.change("online", online):
            self.release_event("online" if online else "offline")
        # event handling
        root: HTMLElement
        hov_elem: UIElem

        # TODO: What is event.window? Can we just ignore it?
        for event in events:
            ########################## Mouse Events ##############################################
            if (_type := pg.event.event_name(event.type).lower()).startswith("mouse"):
                if event.type in (pg.MOUSEBUTTONDOWN, pg.MOUSEBUTTONUP):
                    button = event.button
                root = g["root"]
                _pos = getattr(event, "pos", self.mouse_pos)
                for modal in self.modals:
                    if modal.rect.collidepoint(_pos):
                        hov_elem = modal
                        break
                else:
                    hov_elem = root.collide(_pos) or root
                    cursor = hov_elem.cursor
                    if self.change("cursor", cursor):
                        pg.mouse.set_cursor(cursor)
                if self.change("hover", hov_elem):
                    # TODO: mouseenter, mouseleave
                    # TODO: mouseover, mouseout
                    g["css_dirty"] = True  # :hover
            if event.type == pg.MOUSEBUTTONDOWN:
                self.buttons_down.add(button)
                self.mouse_down = _pos
                mouse_down_event = self.release_event(
                    "mousedown",
                    target=hov_elem,
                    pos=_pos,
                    mods=self.mods,
                    button=button,
                    buttons=self.buttons,
                )
                if not mouse_down_event.cancelled and button == MAIN_MB:
                    if self.change("active", hov_elem):
                        g["css_dirty"] = True
                        # FIXME: This is ad-hoc focus
                        # https://html.spec.whatwg.org/multipage/interaction.html#focusable-area
                        # The specs define focusable areas not as elements but as special objects.
                        # A good example are the controls of a <video> element.
                        # The question is of course how we implement this.
                        if self.focus != hov_elem:
                            if is_focusable(hov_elem):
                                self.release_event(
                                    "focus", hov_elem, related_target=self.focus
                                )
                                self.release_event(
                                    "blur", self.focus, related_target=hov_elem
                                )
                            else:
                                self.release_event("blur", self.focus)

            elif event.type == pg.MOUSEBUTTONUP:
                self.buttons_down.remove(button)
                self.release_event(
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
                    self.release_event(
                        "dragend",
                        target=self.drag,
                    )
                    self.drag = None
                    continue
                # click
                # there is no current drag and the primary mouse button goes down
                last_click_time, last_click_pos = self.last_click
                self.last_click = (time.monotonic(), _pos)
                if not (
                    time.monotonic() - last_click_time <= 0.5 and last_click_pos == _pos
                ):
                    self.click_count = 0
                self.click_count += 1
                if hov_elem is self.active or button != 1:
                    if self.release_event(
                        "click" if button == MAIN_MB else "auxclick",
                        target=hov_elem,
                        pos=_pos,
                        mods=self.mods,
                        button=button,
                        buttons=self.buttons,
                        detail=self.click_count,
                    ).cancelled:
                        continue
                    # remove modals that are escapable and don't overlap with the mouse position
                    self.modals = [
                        modal
                        for modal in self.modals
                        if not modal.can_escape or modal.rect.collidepoint(_pos)
                    ]
                    if (
                        button == ALT_MB
                        and isinstance(hov_elem, Element)
                        and not self.release_event(
                            "contextmenu",
                            target=hov_elem,
                            pos=_pos,
                            mods=self.mods,
                            button=button,
                            buttons=self.buttons,
                            detail=self.click_count,
                        ).cancelled
                    ):
                        menus: dict[str, Sequence[MenuItem]] = {}
                        for anc in [hov_elem, *hov_elem.iter_anc()]:
                            if cm := anc.contextmenu:
                                menus.setdefault(anc.tag, cm)
                        default_ctx_menu = [
                            BackButton(),
                            ForwardButton(),
                            Divider(),
                            ReloadButton(),
                        ]
                        self.modals.append(
                            ContextMenu(
                                join(*menus.values(), default_ctx_menu, div=Divider())
                            ).fit_into_rect(
                                config.screen.get_rect(), _pos  # type: ignore
                            )
                        )
                self.active = None
                g["css_dirty"] = True
            elif event.type == pg.MOUSEMOTION:
                self.mouse_pos = _pos
                self.release_event(
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
                self.release_event(
                    "wheel",
                    target=hov_elem,
                    pos=_pos,
                    mods=self.mods,
                    buttons=self.buttons,
                    delta=(event.x, event.y),
                )
                # TODO: emit the scroll event on the first scrollable element
            ############################    Keyboard Events    ########################
            elif event.type in (pg.KEYDOWN, pg.TEXTINPUT):
                if event.type == pg.KEYDOWN:
                    self.mods = event.mod
                    keydown_event = self.release_event(
                        "keydown",
                        target=self.focus or g["root"],
                        key=event.unicode,
                        code=pg.key.name(event.key),
                        pgcode=event.key,  # inofficial api
                        mods=event.mod,
                        repeat=event.key in self.keys_down,
                    )
                    self.keys_down.add(event.key)
                    if keydown_event.cancelled:
                        continue

                elem = self.focus
                if not isinstance(elem, InputElement):
                    continue
                input_type: InputType
                value, pos, selection = elem.editing_ctx.current
                max_pos = len(value)
                if event.type == pg.KEYDOWN:
                    # TODO: tab -> go to next focusable area
                    # TODO: enter -> click a focused <a> or <button>,
                    #                submit the form of an <input> and definitely loose focus
                    # Select All
                    if event.mod & pg.KMOD_CTRL and event.key == pg.K_a:
                        elem.editing_ctx.add_entry((value, max_pos, (0, pos)))
                        continue
                    # Deleting
                    if event.key in (pg.K_BACKSPACE, pg.K_DELETE):
                        if selection is not None:
                            dir = (
                                Delete.Direction.For
                                if selection[0] == pos
                                else Delete.Direction.For
                            )
                            input_type = Delete(
                                selection,
                                Delete.What.Content,
                                dir,
                                before=value,
                            )
                        else:
                            what = (
                                Delete.What.Word
                                if event.mod & pg.KMOD_CTRL
                                else Delete.What.Content
                            )
                            dir = (
                                Delete.Direction.Back
                                if event.key == pg.K_BACKSPACE
                                else Delete.Direction.For
                            )
                            input_type = Delete(
                                pos,
                                what,
                                dir,
                                before=value,
                            )
                        selection = None
                    # Undo, Redo
                    elif event.mod & pg.KMOD_CTRL and event.key in (pg.K_z, pg.K_y):
                        input_type = History.from_history(
                            History.Type.Undo
                            if event.key == pg.K_z
                            else History.Type.Redo,
                            elem.editing_ctx,
                        )
                    # Copy/Cut/Paste
                    elif (
                        event.mod & pg.KMOD_CTRL
                        and event.key
                        in (
                            pg.K_v,
                            pg.K_x,
                            pg.K_c,
                        )
                        or event.key == pg.K_INSERT
                    ):
                        if event.key == pg.K_INSERT:
                            event.key = pg.K_v
                        selection = selection or (0, pos)
                        method = EditingMethod.CutPaste
                        if event.key != pg.K_v:
                            put_clip(value[slice(*selection)])
                        if event.key == pg.K_c:
                            continue
                        if event.key == pg.K_v:
                            input_type = Insert(get_clip(), pos, method, value)
                        else:
                            input_type = Delete(
                                selection,
                                Delete.What.Content,
                                method=method,
                                before=value,
                            )
                        selection = None
                    # Cursor Movement
                    elif event.key in (pg.K_LEFT, pg.K_RIGHT, pg.K_END, pg.K_HOME):
                        # TODO: Skip a whole word when pressing ctrl
                        old_pos = pos
                        if event.key == pg.K_LEFT:
                            pos = max(0, pos - 1)
                        elif event.key == pg.K_RIGHT:
                            pos = min(max_pos, pos + 1)
                        elif event.key == pg.K_HOME:
                            pos = 0
                        else:
                            pos = max_pos
                        if event.mod & pg.KMOD_SHIFT:
                            match selection:
                                case None:
                                    selection = (old_pos, pos)
                                case (start, end) if end == old_pos:  # type: ignore
                                    selection = (start, pos)
                                case (start, end) if start == old_pos:  # type: ignore
                                    selection = (pos, end)
                            selection = EditingContext.clean_selection(selection)
                        else:
                            selection = None
                        elem.editing_ctx.add_entry((value, pos, selection))
                        continue
                    else:
                        continue
                elif event.type == pg.TEXTINPUT:
                    input_type = Insert(
                        event.text, pos, EditingMethod.Normal, before=value
                    )

                if elem.read_only:
                    continue
                elem.sanitize_input(input_type)
                if self.release_event("beforeinput", input_type=input_type).cancelled:
                    continue
                elem.attrs["value"] = input_type.after
                if isinstance(input_type, History):
                    input_type.execute(elem.editing_ctx)
                else:
                    if isinstance(input_type, Insert):
                        pos = input_type.start + len(input_type.content)
                    elif isinstance(input_type, Delete):
                        # XXX: Get the first position in which before and after differ
                        pos = len(input_type.after)
                        for i, before_c, after_c in zip(
                            count(), input_type.before, input_type.after
                        ):
                            if before_c != after_c:
                                pos = i
                                break
                    # Unreal selections become None
                    elem.editing_ctx.add_entry((input_type.after, pos, None))
                self.release_event("input", elem)
            elif event.type == pg.KEYUP:
                self.release_event(
                    "keyup",
                    target=self.focus or g["root"],
                    key=event.unicode,
                    code=pg.key.name(event.key),
                    pgcode=event.key,  # inofficial api
                    mods=event.mod,
                    # TODO: repeat = event.key in self.pressed_keys
                )
                self.mods = event.mod
            elif event.type == pg.TEXTEDITING:
                # TODO: composition start
                # self.is_composing = True
                pass
            ########################## Window Events ##############################################
            elif event.type == pg.WINDOWRESIZED:
                g["W"] = event.x
                g["H"] = event.y
                g["css_dirty"] = True
                self.release_event("resize", size=(event.x, event.y))
            elif _type.startswith("window"):
                self.release_event(_type, **event.__dict__)

    def on(
        self,
        __type: str,
        __callback: Callback,
        __repeat: int = -1,
        target: None | UIElem = None,
    ):
        """
        Register a callback to be called when the events of the given type occur.
        It will be called repeat many times or infinite times if < 0.
        Also you can give a target to attach to the event.
        The callback will only be called when the target matches the specified
        """
        if __type not in supported_events:
            raise ValueError(f"Event type {__type!r} is not supported")
        __type = __type.lower()
        _target = target if target is not None else g["root"]
        if __repeat:
            self.callbacks[__type][_target] = [
                *self.callbacks[__type].get(_target, []),
                (__callback, __repeat),
            ]

    def draw(self, surf: Surface):
        for modal in self.modals:
            modal.draw(surf)
