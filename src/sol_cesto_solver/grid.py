"""4x4 board calibration and cell extraction."""
import json
from dataclasses import asdict, dataclass
from pathlib import Path

import cv2
import numpy as np

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


def save_debug_overlay(image: np.ndarray, layout: GridLayout, output_path: str) -> None:
    """Write a copy of `image` with the grid drawn on top, for visual verification."""
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

    for r in range(ROWS):
        for c in range(COLS):
            x = layout.board_x + c * layout.cell_w + 6
            y = layout.board_y + r * layout.cell_h + 22
            cv2.putText(
                debug,
                f"r{r}c{c}",
                (x, y),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (255, 255, 255),
                1,
                cv2.LINE_AA,
            )

    cv2.imwrite(output_path, debug)
