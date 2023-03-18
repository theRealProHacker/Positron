"""
# Overflow tools

Overflow values can be:
- scroll:   clip and scroll
- hidden:   clip and scroll but not for user (show no scroll-bar and no wheel scroll)
- clip:     clip and no scroll
- visible:  don't clip and no scroll
"""

from contextlib import contextmanager, nullcontext
from dataclasses import dataclass

from positron.types import Surface, Rect
from positron.utils.func import in_bounds
from positron.utils.pg import surf_clip


@dataclass(frozen=True)
class Overflow:
    scroll: bool = True
    user_scroll: bool = True
    clip: bool = True

    @contextmanager
    def clip_surf(self, surf: Surface, clip: Rect):
        inner_ctx = surf_clip(surf, clip) if self.clip else nullcontext()
        with inner_ctx:
            yield

    def calc_scroll(self, scroll: float, max_scroll: float) -> float:
        if not self.scroll:
            return 0
        return in_bounds(scroll, 0, max_scroll)


overflow = {
    "scroll": Overflow(),
    "hidden": Overflow(user_scroll=False),
    "clip": Overflow(scroll=False, user_scroll=False),
    "visible": Overflow(scroll=False, user_scroll=False, clip=False),
}
