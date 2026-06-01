"""Tests for equipped-teeth detection in the HUD mouth."""
from pathlib import Path

import cv2

from sol_cesto_solver.teeth_vision import read_teeth

FIXTURES = Path(__file__).parent / "fixtures"


def test_reads_the_three_equipped_teeth():
    img = cv2.imread(str(FIXTURES / "teeth_windowed.png"))
    teeth = read_teeth(img)
    assert len(teeth) == 3
    # All in the upper row, three adjacent columns.
    assert {(t.row, t.col) for t in teeth} == {(0, 1), (0, 2), (0, 3)}
    colors = {t.color for t in teeth}
    assert "red" in colors    # strawberry tooth
    assert "blue" in colors   # magic tooth
    # Identity is deferred, so every tooth is unread -> the overlay must warn.
    assert all(t.species is None for t in teeth)
    assert all(t.color is not None for t in teeth)


def test_empty_mouth_reads_no_teeth():
    # In this capture the mouth is empty (plain cream teeth); the gold frame and a
    # transient Steam overlay must NOT be mistaken for teeth.
    img = cv2.imread(str(FIXTURES / "screenshot_windowed.png"))
    assert read_teeth(img) == []
