"""4x4 board calibration and cell extraction."""
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import cv2
import numpy as np

if TYPE_CHECKING:
    from .decision import Recommendation
    from .state import GameState

ROWS = 4
COLS = 4

CACHE_DIR = Path.home() / ".sol-cesto-solver"
CALIBRATION_FILE = CACHE_DIR / "calibration.json"


@dataclass(frozen=True)
class GridLayout:
    """Where the board sits inside the captured image, plus derived cell rectangles."""

    board_x: int
    board_y: int
    board_w: int
    board_h: int
    window_w: int
    window_h: int

    @property
    def cell_w(self) -> int:
        return self.board_w // COLS

    @property
    def cell_h(self) -> int:
        return self.board_h // ROWS

    def cell_rect(self, row: int, col: int) -> tuple[int, int, int, int]:
        """Return (x, y, w, h) for the cell at (row, col)."""
        x = self.board_x + col * self.cell_w
        y = self.board_y + row * self.cell_h
        return (x, y, self.cell_w, self.cell_h)

    def crop_cell(self, image: np.ndarray, row: int, col: int) -> np.ndarray:
        """Slice the image to extract the cell at (row, col)."""
        x, y, w, h = self.cell_rect(row, col)
        return image[y:y + h, x:x + w]


# Board proportions measured from a typical Sol Cesto screenshot. If the board
# doesn't line up in --debug mode, hand-edit ~/.sol-cesto-solver/calibration.json.
_LEFT_RATIO = 0.215
_TOP_RATIO = 0.03
_BOARD_W_RATIO = 0.57
_BOARD_H_RATIO = 0.94


def detect_board(image: np.ndarray) -> GridLayout:
    """Heuristic detection of the board area using fixed proportions of the window."""
    h, w = image.shape[:2]
    return GridLayout(
        board_x=int(w * _LEFT_RATIO),
        board_y=int(h * _TOP_RATIO),
        board_w=int(w * _BOARD_W_RATIO),
        board_h=int(h * _BOARD_H_RATIO),
        window_w=w,
        window_h=h,
    )


def load_calibration(window_size: tuple[int, int]) -> GridLayout | None:
    """Load cached calibration if it matches the current window size, else None."""
    if not CALIBRATION_FILE.exists():
        return None
    try:
        data = json.loads(CALIBRATION_FILE.read_text())
    except (json.JSONDecodeError, OSError):
        return None
    if (data.get("window_w"), data.get("window_h")) != window_size:
        return None
    try:
        return GridLayout(**data)
    except TypeError:
        return None


def save_calibration(layout: GridLayout) -> None:
    """Persist calibration to disk for reuse on subsequent captures."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    CALIBRATION_FILE.write_text(json.dumps(asdict(layout), indent=2))


def save_debug_overlay(
    image: np.ndarray,
    layout: GridLayout,
    output_path: str,
    state: "GameState | None" = None,
    recommendation: "Recommendation | None" = None,
) -> None:
    """Write a copy of `image` with the grid overlaid, for visual verification.

    If `state` is given, each cell is labelled with its detected `content` and
    `value` instead of the bare `r{r}c{c}` coordinate.

    If `recommendation` is given, the recommended row is highlighted with a
    thicker yellow border.
    """
    debug = image.copy()

    cv2.rectangle(
        debug,
        (layout.board_x, layout.board_y),
        (layout.board_x + layout.board_w, layout.board_y + layout.board_h),
        (0, 0, 255),
        2,
    )

    for r in range(1, ROWS):
        y = layout.board_y + r * layout.cell_h
        cv2.line(
            debug,
            (layout.board_x, y),
            (layout.board_x + layout.board_w, y),
            (0, 255, 0),
            1,
        )
    for c in range(1, COLS):
        x = layout.board_x + c * layout.cell_w
        cv2.line(
            debug,
            (x, layout.board_y),
            (x, layout.board_y + layout.board_h),
            (0, 255, 0),
            1,
        )

    # Per-cell classification chips: a coloured rectangle near the bottom of
    # each cell with the detected content + value. Background colour codes the
    # type so the image reads at a glance even when scaled down for thumbnails.
    content_bg = {
        "physical": (40, 40, 220),    # red
        "magic":    (220, 80, 40),    # blue
        "heal":     (140, 80, 220),   # pink/magenta
        "treasure": (40, 200, 220),   # gold
        "empty":    (110, 110, 110),  # gray
    }
    for r in range(ROWS):
        for c in range(COLS):
            if state is not None:
                cell = state.board[r][c]
                label = cell.content
                if cell.value is not None:
                    label += f" {cell.value}"
                bg_color = content_bg.get(cell.content, (90, 90, 90))
            else:
                label = f"r{r}c{c}"
                bg_color = (90, 90, 90)

            font_scale = 1.3
            font_thickness = 3
            (tw, th), baseline = cv2.getTextSize(
                label, cv2.FONT_HERSHEY_SIMPLEX, font_scale, font_thickness
            )
            pad_x, pad_y = 18, 14
            chip_w, chip_h = tw + 2 * pad_x, th + 2 * pad_y + baseline

            cell_x = layout.board_x + c * layout.cell_w
            cell_y = layout.board_y + r * layout.cell_h
            chip_x = cell_x + (layout.cell_w - chip_w) // 2
            chip_y = cell_y + layout.cell_h - chip_h - 18

            cv2.rectangle(
                debug,
                (chip_x, chip_y),
                (chip_x + chip_w, chip_y + chip_h),
                bg_color,
                -1,
            )
            cv2.rectangle(
                debug,
                (chip_x, chip_y),
                (chip_x + chip_w, chip_y + chip_h),
                (255, 255, 255),
                2,
            )
            cv2.putText(
                debug,
                label,
                (chip_x + pad_x, chip_y + pad_y + th),
                cv2.FONT_HERSHEY_SIMPLEX,
                font_scale,
                (255, 255, 255),
                font_thickness,
                cv2.LINE_AA,
            )

    if recommendation is not None:
        r = recommendation.best_row
        y_top = layout.board_y + r * layout.cell_h
        y_bot = layout.board_y + (r + 1) * layout.cell_h
        cv2.rectangle(
            debug,
            (layout.board_x, y_top),
            (layout.board_x + layout.board_w, y_bot),
            (0, 255, 255),  # bright yellow accent
            5,
        )

    cv2.imwrite(output_path, debug)
