"""Tests for cross-cell monster mechanics."""
from sol_cesto_solver.mechanics import (
    ATTRACT_WEIGHT,
    BoardContext,
    analyze_board,
    landing_attraction,
    species_hp_adjustment,
)
from sol_cesto_solver.state import Cell


def test_analyze_board_counts_hawks_and_detects_cursed_strawberry():
    board = [
        [
            Cell(content="physical", value=3, species="hawk"),
            Cell(content="physical", value=1, species="fledgling"),
        ],
        [
            Cell(content="magic", value=2, species="cursed_strawberry"),
            Cell(content="empty"),
        ],
    ]
    ctx = analyze_board(board)
    assert ctx.hawks == 1
    assert ctx.heals_toxic is True


def test_analyze_board_default_when_nothing_special():
    board = [[Cell(content="magic", value=1, species="slime")]]
    assert analyze_board(board) == BoardContext(hawks=0, heals_toxic=False)


def test_landing_attraction_only_for_attracting_species():
    black_hole = Cell(content="magic", value=4, species="black_hole")
    assert landing_attraction(black_hole) == ATTRACT_WEIGHT
    assert landing_attraction(Cell(content="treasure", species="mimic")) == ATTRACT_WEIGHT
    assert landing_attraction(Cell(content="magic", value=1, species="slime")) == 0.0
    assert landing_attraction(Cell(content="empty")) == 0.0


def test_fledgling_penalty_scales_with_hawk_count():
    fledgling = Cell(content="physical", value=1, species="fledgling")
    assert species_hp_adjustment(fledgling, BoardContext(hawks=2)) == -2.0
    assert species_hp_adjustment(fledgling, BoardContext(hawks=0)) == 0.0
    # A Hawk itself isn't penalised, only the Fledgling that buffs it.
    hawk = Cell(content="physical", value=3, species="hawk")
    assert species_hp_adjustment(hawk, BoardContext(hawks=2)) == 0.0
