"""Tests for the detection pipeline."""
from pathlib import Path

import cv2
import numpy as np
import pytest

from sol_cesto_solver.grid import COLS, ROWS, detect_board
from sol_cesto_solver.state import GameState

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def _blank_image(width: int = 1920, height: int = 1080) -> np.ndarray:
    return np.zeros((height, width, 3), dtype=np.uint8)


def test_grid_layout_has_positive_cells():
    layout = detect_board(_blank_image())
    assert layout.cell_w > 0
    assert layout.cell_h > 0


def test_grid_first_and_last_cell_bounds():
    layout = detect_board(_blank_image())

    x0, y0, _, _ = layout.cell_rect(0, 0)
    assert x0 == layout.board_x
    assert y0 == layout.board_y

    x_last, y_last, _, _ = layout.cell_rect(ROWS - 1, COLS - 1)
    assert x_last == layout.board_x + (COLS - 1) * layout.cell_w
    assert y_last == layout.board_y + (ROWS - 1) * layout.cell_h


def test_crop_returns_cell_sized_slice():
    img = _blank_image()
    layout = detect_board(img)
    crop = layout.crop_cell(img, 0, 0)
    assert crop.shape[0] == layout.cell_h
    assert crop.shape[1] == layout.cell_w


@pytest.mark.skipif(
    not (FIXTURES_DIR / "screenshot.png").exists(),
    reason="Sample screenshot missing (run scripts/bootstrap_icons_from_screenshot.py).",
)
def test_recognize_state_on_bundled_screenshot():
    """End-to-end smoke test: run the full pipeline against the bundled sample.

    Asserts the structure plus a handful of cells we know by visual inspection,
    so a regression in either the detector or the templates flips this test red.
    """
    from sol_cesto_solver.recognition import recognize_state

    image = cv2.imread(str(FIXTURES_DIR / "screenshot.png"))
    layout = detect_board(image)
    state = recognize_state(image, layout)

    assert isinstance(state, GameState)
    assert len(state.board) == ROWS
    for row in state.board:
        assert len(row) == COLS

    # Known-true cells from the bundled screenshot.
    assert state.board[0][0].content == "physical"
    assert state.board[0][0].value == 3
    assert state.board[0][1].content == "magic"
    assert state.board[0][1].value == 1
    assert state.board[0][3].content == "treasure"
    assert state.board[2][0].content == "heal"
    assert state.board[2][0].value == 1
    assert state.board[3][0].content == "treasure"

    # Player stats from the bundled screenshot.
    assert state.player.hp == 5
    assert state.player.max_hp == 5
    assert state.player.sword == 2
    assert state.player.magic == 1
