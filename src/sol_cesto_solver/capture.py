"""Capture the Sol Cesto game window."""
from dataclasses import dataclass

import numpy as np
import pygetwindow as gw
from mss import mss


class WindowNotFoundError(Exception):
    """Raised when the Sol Cesto window cannot be located or captured."""


@dataclass(frozen=True)
class WindowBounds:
    left: int
    top: int
    width: int
    height: int

    @property
    def size(self) -> tuple[int, int]:
        return (self.width, self.height)


def find_window(title_hint: str = "Sol Cesto") -> WindowBounds:
    """Locate a visible window whose title contains `title_hint` (case-insensitive).

    Picks the largest match if several windows qualify. Raises WindowNotFound if
    no candidate exists, or all candidates are minimized/zero-sized.
    """
    needle = title_hint.lower()
    candidates = [w for w in gw.getAllWindows() if needle in w.title.lower()]
    if not candidates:
        raise WindowNotFoundError(f"No window with title containing {title_hint!r}.")

    visible = [w for w in candidates if w.width > 0 and w.height > 0 and not w.isMinimized]
    if not visible:
        raise WindowNotFoundError(f"Window matching {title_hint!r} is minimized or zero-sized.")

    w = max(visible, key=lambda w: w.width * w.height)
    return WindowBounds(left=w.left, top=w.top, width=w.width, height=w.height)


def capture(bounds: WindowBounds) -> np.ndarray:
    """Grab the pixels inside `bounds` and return them as a BGR numpy array."""
    region = {
        "left": bounds.left,
        "top": bounds.top,
        "width": bounds.width,
        "height": bounds.height,
    }
    with mss() as sct:
        shot = sct.grab(region)
    # mss returns BGRA; drop alpha so OpenCV gets BGR.
    return np.asarray(shot)[:, :, :3].copy()
