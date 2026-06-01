"""Capture the Sol Cesto game window.

**Platform: Windows only.** This module depends on `pygetwindow` to find the
Sol Cesto window by title. `pygetwindow` officially supports Windows; on Linux
and macOS it either fails to import or returns nothing useful. The recognition
and decision modules are platform-agnostic and can run on any OS using a saved
PNG via the CLI's ``--from-file`` flag.
"""
from dataclasses import dataclass

import numpy as np
import pygetwindow as gw
from mss import mss


class CaptureError(Exception):
    """Base class for anything that prevents us from obtaining an image."""


class WindowNotFoundError(CaptureError):
    """The game window could not be located, was minimized, or had zero size."""


class ImageReadError(CaptureError):
    """A PNG/image file could not be read (bad path, unsupported format, …)."""


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
    # Normalise away case and spaces so the default "Sol Cesto" still matches the
    # actual window title "SolCesto" (also "sol_cesto", etc.). Spaces only — keeping
    # hyphens avoids matching unrelated windows like "...sol-cesto-solver - VS Code".
    needle = title_hint.lower().replace(" ", "")
    candidates = [w for w in gw.getAllWindows() if needle in w.title.lower().replace(" ", "")]
    if not candidates:
        raise WindowNotFoundError(f"No window with title containing {title_hint!r}.")

    visible = [w for w in candidates if w.width > 0 and w.height > 0 and not w.isMinimized]
    if not visible:
        raise WindowNotFoundError(f"Window matching {title_hint!r} is minimized or zero-sized.")

    w = max(visible, key=lambda w: w.width * w.height)
    return _bounds_for_window(w)


def _bounds_for_window(w) -> WindowBounds:
    """Prefer the client area (content only) over the full window rect.

    Capturing the client area excludes the title bar/borders, so the captured
    image matches the content-only coordinate system the detector is tuned on.
    Falls back to the window rect when the client rect can't be read (and that
    fallback is what the unit tests' fake windows exercise).
    """
    hwnd = getattr(w, "_hWnd", None)
    if hwnd:
        client = _client_bounds(int(hwnd))
        if client is not None:
            return client
    return WindowBounds(left=w.left, top=w.top, width=w.width, height=w.height)


def _client_bounds(hwnd: int) -> WindowBounds | None:
    """Screen-space bounds of a window's client area, via Win32. None on failure."""
    try:
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.windll.user32
        user32.GetClientRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
        user32.ClientToScreen.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.POINT)]

        rect = wintypes.RECT()
        origin = wintypes.POINT(0, 0)
        if not user32.GetClientRect(hwnd, ctypes.byref(rect)):
            return None
        if not user32.ClientToScreen(hwnd, ctypes.byref(origin)):
            return None
        if rect.right <= 0 or rect.bottom <= 0:
            return None
        return WindowBounds(left=origin.x, top=origin.y, width=rect.right, height=rect.bottom)
    except (OSError, AttributeError):
        return None


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
