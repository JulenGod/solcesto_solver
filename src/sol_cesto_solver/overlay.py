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
