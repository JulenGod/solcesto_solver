"""Tests for the overlay's pure geometry and panel-text helpers.

The Tkinter window itself isn't tested (no display on CI); these cover the
coordinate math and text formatting that feed it.
"""
import types

from sol_cesto_solver.decision import CellOutcome, Recommendation, RowEvaluation
from sol_cesto_solver.grid import GridLayout
from sol_cesto_solver.overlay import (
    board_rect,
    cell_label,
    cell_rect,
    format_panel_lines,
    hud_lines,
    panel_anchor,
    row_highlight_rect,
    teeth_line,
)
from sol_cesto_solver.state import Cell, Door, GameState, Modifiers, Player, ToothSlot


def _layout() -> GridLayout:
    # cell_h = 600 // 4 = 150, cell_w = 800 // 4 = 200
    return GridLayout(
        board_x=100, board_y=20, board_w=800, board_h=600, window_w=1200, window_h=700
    )


def _window(left: int = 50, top: int = 30):
    # Duck-typed stand-in for capture.WindowBounds (left/top is all we read).
    return types.SimpleNamespace(left=left, top=top, width=1200, height=700)


# --- geometry --------------------------------------------------------------

def test_board_rect_offsets_by_window_origin():
    assert board_rect(_window(50, 30), _layout()) == (150, 50, 800, 600)


def test_row_highlight_rect_row_zero_sits_at_board_top():
    assert row_highlight_rect(_window(50, 30), _layout(), 0) == (150, 50, 800, 150)


def test_row_highlight_rect_steps_down_by_cell_height():
    # Row 2 -> board_top + 2 * cell_h = 50 + 300.
    assert row_highlight_rect(_window(50, 30), _layout(), 2) == (150, 350, 800, 150)


def test_panel_anchor_sits_just_right_of_board():
    x, y = panel_anchor(_window(50, 30), _layout(), margin=24)
    assert x == 150 + 800 + 24
    assert y == 50


# --- panel text ------------------------------------------------------------

def _recommendation() -> Recommendation:
    def ev(row: int, exp: float) -> RowEvaluation:
        return RowEvaluation(
            row=row,
            expected_hp_change=exp,
            worst_case_hp_change=exp,
            cells=[
                CellOutcome(col=i, landing_probability=0.25, hp_change=0.0)
                for i in range(4)
            ],
        )

    return Recommendation(
        best_row=1, rows=[ev(0, -0.5), ev(1, 0.0), ev(2, -0.25), ev(3, 0.0)]
    )


def test_panel_lines_mark_only_the_best_row():
    lines = format_panel_lines(_recommendation())
    best_line = next(line for line in lines if "Row 1" in line)
    other_line = next(line for line in lines if "Row 0" in line)
    assert best_line.lstrip().startswith("►")
    assert not other_line.lstrip().startswith("►")


def test_panel_lines_cover_every_row_and_a_verdict():
    lines = format_panel_lines(_recommendation())
    assert sum(1 for line in lines if "Row" in line) == 4
    assert any("Pick row 1" in line for line in lines)


def test_panel_lines_show_signed_expected_values():
    joined = " ".join(format_panel_lines(_recommendation()))
    assert "-0.50" in joined
    assert "+0.00" in joined
    assert "-0.25" in joined


# --- per-cell labels + HUD ---------------------------------------------------

def test_cell_rect_indexes_into_the_board():
    # _layout(): cell_w=200, cell_h=150; window origin (50,30); board offset (100,20).
    # row 1, col 2 -> x = 50+100+2*200 = 550, y = 30+20+1*150 = 200.
    assert cell_rect(_window(50, 30), _layout(), 1, 2) == (550, 200, 200, 150)


def test_cell_label_formats_by_content():
    assert cell_label(Cell(content="physical", value=3)) == "phys 3"
    assert cell_label(Cell(content="magic", value=1)) == "mag 1"
    assert cell_label(Cell(content="heal", value=1)) == "heal 1"
    assert cell_label(Cell(content="treasure")) == "treasure"
    assert cell_label(Cell(content="empty")) == ""
    assert cell_label(Cell(content="physical", value=None)) == "phys ?"


def test_hud_lines_include_stats_gold_door_and_pick():
    board = [[Cell(content="empty") for _ in range(4)] for _ in range(4)]
    state = GameState(
        board=board,
        player=Player(hp=4, max_hp=5, sword=2, magic=1),
        gold=7,
        door=Door(cleared=2, required=5),
        modifiers=Modifiers(physical=0.30),
    )
    text = "\n".join(hud_lines(state, _recommendation()))
    assert "HP 4/5" in text
    assert "GOLD 7" in text
    assert "DOOR 2/5" in text
    assert "swd+30%" in text
    assert "Pick row 1" in text


# --- teeth notification ------------------------------------------------------

def test_teeth_line_says_none_when_no_teeth():
    assert teeth_line([]) == "TEETH none"


def test_teeth_line_warns_about_unidentified_teeth():
    teeth = [ToothSlot(row=0, col=1, color="red"), ToothSlot(row=0, col=2, color="blue")]
    line = teeth_line(teeth)
    assert line.startswith("!!")  # the "!!" marker makes the overlay draw it in red
    assert "2/2 UNREAD" in line
    assert "red" in line and "blue" in line


def test_teeth_line_is_quiet_once_all_identified():
    teeth = [ToothSlot(row=0, col=1, color="red", species="strawberry_tooth")]
    line = teeth_line(teeth)
    assert not line.startswith("!!")
    assert line == "TEETH 1 ok"
