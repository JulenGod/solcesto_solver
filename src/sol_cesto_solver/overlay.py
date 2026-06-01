"""Live on-screen overlay that highlights the recommended row over the game.

The module is split in two layers, mirroring the rest of the codebase:

* **Pure helpers** (`board_rect`, `row_highlight_rect`, `cell_rect`, `cell_label`,
  `hud_lines`, `format_panel_lines`) — translate a window position + grid layout +
  game state + recommendation into absolute screen coordinates and overlay text.
  No GUI dependency, fully unit-tested.
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
    from .state import Cell, GameState, ToothSlot

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


def cell_rect(
    window: WindowBounds, layout: GridLayout, row: int, col: int
) -> tuple[int, int, int, int]:
    """Absolute screen rect (x, y, w, h) of a single board cell."""
    x = window.left + layout.board_x + col * layout.cell_w
    y = window.top + layout.board_y + row * layout.cell_h
    return (x, y, layout.cell_w, layout.cell_h)


def cell_label(cell: Cell) -> str:
    """Short label for a cell: 'phys 3', 'mag 1 slime', 'treasure', '' …

    Appends the identified species for monsters when known (e.g. 'phys 3 red_coyote').
    """
    if cell.content == "empty":
        return ""
    if cell.content == "treasure":
        return "treasure"
    value = "?" if cell.value is None else cell.value
    names = {"physical": "phys", "magic": "mag", "heal": "heal"}
    label = f"{names.get(cell.content, cell.content)} {value}"
    if cell.species:
        label += f" {cell.species}"
    if cell.buffed:
        label += " (buf)"
    return label


def _fmt_pct(value: float | None) -> str:
    return "?" if value is None else f"{value * 100:+.0f}%"


def hud_lines(state: GameState, recommendation: Recommendation) -> list[str]:
    """Compact multi-line HUD summarising everything detected, for verification.

    Player stats, gold, door progress and book modifiers, then the per-row
    expected-HP breakdown and the pick (reused from `format_panel_lines`).
    """
    p = state.player
    m = state.modifiers
    door = state.door
    gold = "?" if state.gold is None else state.gold

    if door is None:
        door_str = "DOOR ?"
    else:
        cleared = "?" if door.cleared is None else door.cleared
        required = "?" if door.required is None else door.required
        door_str = f"DOOR {cleared}/{required}"
        if recommendation.door_open:
            door_str += " (OPEN)"
        elif recommendation.tiles_remaining is not None:
            door_str += f" ({recommendation.tiles_remaining} left)"

    summary = [
        f"HP {p.hp}/{p.max_hp}   SWD {p.sword}   MAG {p.magic}",
        f"GOLD {gold}   {door_str}",
        (
            f"MOD swd{_fmt_pct(m.physical)} mag{_fmt_pct(m.magic)} hrt{_fmt_pct(m.heal)} "
            f"chs{_fmt_pct(m.treasure)} spk{_fmt_pct(m.trap)} gld x{m.gold_multiplier or 1}"
        ),
        teeth_line(state.teeth),
        items_line(state.items),
        "",
    ]
    return summary + format_panel_lines(recommendation)


def items_line(items: list[str]) -> str:
    """One-line summary of the consumables the player is holding."""
    if not items:
        return "ITEMS none"
    return f"ITEMS {', '.join(items)}"


def teeth_line(teeth: list[ToothSlot]) -> str:
    """One-line teeth status; warns (``!!`` prefix) when any tooth is unidentified."""
    if not teeth:
        return "TEETH none"
    unread = [t for t in teeth if t.species is None]
    if unread:
        colors = ", ".join(t.color or "?" for t in unread)
        return f"!! TEETH {len(unread)}/{len(teeth)} UNREAD ({colors})"
    return f"TEETH {len(teeth)} ok"


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
    HUD_BG = "#0E0E0C"        # opaque panel behind the HUD text (not the key colour)
    HUD_FG = "#EDEDED"
    HUD_WARN = "#FF6B6B"      # lines starting with "!!" (e.g. unread teeth) draw in red
    CONTENT_COLORS = {        # per-cell label colour by content type
        "physical": "#FF5A5A",
        "magic": "#5AA0FF",
        "heal": "#FF8AD0",
        "treasure": "#FFD400",
    }

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

    def _text(
        self, x: int, y: int, text: str, color: str, size: int, anchor: str = "center"
    ) -> None:
        """Draw text with a black drop-shadow so it stays legible over the game."""
        font = ("Consolas", size, "bold")
        self.canvas.create_text(x + 2, y + 2, text=text, fill="#000000", font=font, anchor=anchor)
        self.canvas.create_text(x, y, text=text, fill=color, font=font, anchor=anchor)

    def _draw_hud(self, lines: list[str]) -> None:
        x0, y0, pad, line_h = 14, 12, 10, 24
        width, height = 600, pad * 2 + line_h * len(lines)
        self.canvas.create_rectangle(
            x0, y0, x0 + width, y0 + height, fill=self.HUD_BG, outline=self.BOARD_COLOR, width=2
        )
        for i, line in enumerate(lines):
            fill = self.HUD_WARN if line.startswith("!!") else self.HUD_FG
            self.canvas.create_text(
                x0 + pad, y0 + pad + i * line_h, text=line, fill=fill,
                font=("Consolas", 13, "bold"), anchor="nw",
            )

    def _draw(
        self, window: WindowBounds, layout: GridLayout, state: GameState, rec: Recommendation
    ) -> None:
        bx, by, bw, bh = board_rect(window, layout)
        self.canvas.create_rectangle(
            bx, by, bx + bw, by + bh, outline=self.BOARD_COLOR, width=self.BOARD_WIDTH
        )

        # Per-cell detected content + value, colour-coded, near the bottom of each cell.
        for r, row in enumerate(state.board):
            for c, cell in enumerate(row):
                label = cell_label(cell)
                if not label:
                    continue
                cx, cy, cw, ch = cell_rect(window, layout, r, c)
                color = self.CONTENT_COLORS.get(cell.content, "#FFFFFF")
                self._text(cx + cw // 2, cy + ch - 24, label, color, 15)

        rx, ry, rw, rh = row_highlight_rect(window, layout, rec.best_row)
        self.canvas.create_rectangle(
            rx, ry, rx + rw, ry + rh, outline=self.ROW_COLOR, width=self.ROW_WIDTH
        )

        self._draw_hud(hud_lines(state, rec))

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

        `poll` is a zero-arg callable returning ``(window, layout, state, recommendation)``,
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
