"""Live on-screen overlay that highlights the recommended row over the game.

The module is split in two layers, mirroring the rest of the codebase:

* **Pure helpers** (`board_rect`, `row_highlight_rect`, `panel_anchor`,
  `format_panel_lines`) — translate a window position + grid layout +
  recommendation into absolute screen coordinates and panel text. No GUI
  dependency, fully unit-tested.
* **The `Overlay` class** (added on top of this layer) — a Tkinter transparent,
  click-through, always-on-top window. GUI code can't run on a headless CI
  runner, so it stays thin and is exercised manually with the game open.

**Windows only**, and only over a game running in *windowed* / *borderless
windowed* mode — exclusive fullscreen bypasses the desktop compositor and would
hide the overlay.
"""
from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    # Type-only imports: keeps this module importable without pulling in the
    # Windows-only capture deps, so the pure helpers are testable anywhere.
    from .capture import WindowBounds
    from .decision import Recommendation
    from .grid import GridLayout

# Pixels between the right edge of the board and the info panel.
PANEL_MARGIN = 24


def board_rect(window: WindowBounds, layout: GridLayout) -> tuple[int, int, int, int]:
    """Absolute screen rect (x, y, w, h) of the whole 4x4 board.

    `layout` coordinates are relative to the captured window, so we offset them
    by the window's top-left corner to get absolute screen pixels.
    """
    return (
        window.left + layout.board_x,
        window.top + layout.board_y,
        layout.board_w,
        layout.board_h,
    )


def row_highlight_rect(
    window: WindowBounds, layout: GridLayout, row: int
) -> tuple[int, int, int, int]:
    """Absolute screen rect (x, y, w, h) of the highlight box around `row`."""
    x = window.left + layout.board_x
    y = window.top + layout.board_y + row * layout.cell_h
    return (x, y, layout.board_w, layout.cell_h)


def panel_anchor(
    window: WindowBounds, layout: GridLayout, margin: int = PANEL_MARGIN
) -> tuple[int, int]:
    """Absolute screen (x, y) for the info panel's top-left, just right of the board."""
    board_x, board_y, board_w, _board_h = board_rect(window, layout)
    return (board_x + board_w + margin, board_y)


def format_panel_lines(recommendation: Recommendation) -> list[str]:
    """Human-readable panel text: one line per row plus a verdict.

    The recommended row is prefixed with a marker; the closing line states the
    pick explicitly.
    """
    lines: list[str] = []
    for ev in recommendation.rows:
        marker = "►" if ev.row == recommendation.best_row else " "
        lines.append(f"{marker} Row {ev.row}   {ev.expected_hp_change:+.2f} HP")
    lines.append("")
    lines.append(f"► Pick row {recommendation.best_row}")
    return lines


def enable_dpi_awareness() -> None:
    """Make the process per-monitor DPI aware (Windows). Best-effort no-op elsewhere.

    Without this, Tkinter draws in *logical* (scaled) pixels while mss/pygetwindow
    report *physical* pixels, so on a display scaled above 100% the overlay lands
    at the wrong place/size — usually off-screen. Must run before the first Tk
    window is created.
    """
    import ctypes

    # Try per-monitor DPI awareness (Win 8.1+), then the older system-DPI call.
    for set_aware in (
        lambda: ctypes.windll.shcore.SetProcessDpiAwareness(2),
        lambda: ctypes.windll.user32.SetProcessDPIAware(),
    ):
        try:
            set_aware()
            return
        except (AttributeError, OSError):
            continue


class Overlay:
    """A transparent, click-through, always-on-top Tkinter overlay (Windows).

    Draws a thin frame around the detected board and a thick highlight around
    the recommended row, refreshing on a timer. The window is *click-through*:
    a Win32 ``WS_EX_TRANSPARENT`` extended style lets mouse input pass straight
    to the game underneath, so the overlay never blocks play.

    Renders only over a *windowed* / *borderless windowed* game — exclusive
    fullscreen bypasses the desktop compositor and would hide the overlay.

    GUI code, so it isn't covered by the unit tests (CI has no display); the
    drawing coordinates it relies on are tested via the pure helpers above.
    """

    KEY_COLOR = "magenta"     # chroma key: these pixels become fully transparent
    BOARD_COLOR = "#39FF14"   # board frame (neon green)
    ROW_COLOR = "#FFD400"     # recommended row (bright yellow)
    BOARD_WIDTH = 3
    ROW_WIDTH = 6

    def __init__(self) -> None:
        # Must precede the first Tk window so Tk matches the physical-pixel
        # coordinates that mss/pygetwindow report (fixes scaled displays).
        enable_dpi_awareness()

        import tkinter as tk

        self._running = False
        self._poll = None
        self._interval_ms = 1000

        self.root = tk.Tk()
        self.root.overrideredirect(True)        # no title bar or borders
        self.root.attributes("-topmost", True)  # stay above the game
        self.root.attributes("-transparentcolor", self.KEY_COLOR)
        self.root.config(bg=self.KEY_COLOR)

        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        self.root.geometry(f"{screen_w}x{screen_h}+0+0")

        self.canvas = tk.Canvas(self.root, bg=self.KEY_COLOR, highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)

        self._enable_click_through()

    def _enable_click_through(self) -> None:
        """Add WS_EX_LAYERED | WS_EX_TRANSPARENT so clicks fall through to the game."""
        import ctypes
        from ctypes import wintypes

        gwl_exstyle = -20
        ws_ex_layered = 0x00080000
        ws_ex_transparent = 0x00000020

        user32 = ctypes.windll.user32
        user32.GetParent.restype = wintypes.HWND
        user32.GetParent.argtypes = [wintypes.HWND]
        user32.GetWindowLongW.restype = wintypes.LONG
        user32.GetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int]
        user32.SetWindowLongW.restype = wintypes.LONG
        user32.SetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int, wintypes.LONG]

        # Tk wraps the toplevel in a parent frame on Windows; the parent HWND is
        # the one whose extended style we must flip for click-through to work.
        hwnd = user32.GetParent(self.root.winfo_id())
        style = user32.GetWindowLongW(hwnd, gwl_exstyle)
        user32.SetWindowLongW(hwnd, gwl_exstyle, style | ws_ex_layered | ws_ex_transparent)

    def _draw(self, window: WindowBounds, layout: GridLayout, rec: Recommendation) -> None:
        bx, by, bw, bh = board_rect(window, layout)
        self.canvas.create_rectangle(
            bx, by, bx + bw, by + bh, outline=self.BOARD_COLOR, width=self.BOARD_WIDTH
        )
        rx, ry, rw, rh = row_highlight_rect(window, layout, rec.best_row)
        self.canvas.create_rectangle(
            rx, ry, rx + rw, ry + rh, outline=self.ROW_COLOR, width=self.ROW_WIDTH
        )

    def _tick(self) -> None:
        if not self._running:
            return
        result = self._poll() if self._poll is not None else None
        self.canvas.delete("all")
        if result is not None:
            self._draw(*result)
        self.root.after(self._interval_ms, self._tick)

    def run(self, poll, interval: float = 1.0) -> None:
        """Start the refresh loop and block until the window is closed.

        `poll` is a zero-arg callable returning ``(window, layout, recommendation)``,
        or ``None`` when the game window can't be read (the overlay then clears).
        """
        self._poll = poll
        self._interval_ms = max(100, int(interval * 1000))
        self._running = True
        self._tick()
        try:
            self.root.mainloop()
        except KeyboardInterrupt:
            self.stop()

    def stop(self) -> None:
        """Tear down the window. Safe to call more than once."""
        self._running = False
        with contextlib.suppress(Exception):
            self.root.destroy()
