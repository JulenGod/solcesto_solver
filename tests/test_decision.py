"""Tests for the row-recommendation algorithm."""
import pytest

from sol_cesto_solver.decision import (
    evaluate_cell,
    evaluate_row,
    landing_probabilities,
    recommend_row,
)
from sol_cesto_solver.state import Cell, Door, GameState, Modifiers, Player


def _player(hp: int = 5, max_hp: int = 5, sword: int = 2, magic: int = 1) -> Player:
    return Player(hp=hp, max_hp=max_hp, sword=sword, magic=magic)


# ---------------------------------------------------------------------------
# evaluate_cell
# ---------------------------------------------------------------------------

def test_physical_no_damage_when_sword_meets_threat():
    cell = Cell(content="physical", value=2)
    assert evaluate_cell(cell, _player(sword=2)) == 0.0


def test_physical_takes_difference_when_sword_lacks():
    cell = Cell(content="physical", value=5)
    assert evaluate_cell(cell, _player(sword=2)) == -3.0


def test_magic_uses_magic_stat_not_sword():
    cell = Cell(content="magic", value=4)
    assert evaluate_cell(cell, _player(sword=10, magic=1)) == -3.0


def test_heal_returns_positive_hp_change():
    cell = Cell(content="heal", value=2)
    assert evaluate_cell(cell, _player(hp=3, max_hp=5)) == 2.0


def test_heal_capped_by_room_to_max_hp():
    cell = Cell(content="heal", value=5)
    # Only 1 HP missing -> heal is capped at 1.
    assert evaluate_cell(cell, _player(hp=4, max_hp=5)) == 1.0


def test_treasure_is_neutral_without_mimic_chance():
    assert evaluate_cell(Cell(content="treasure"), _player()) == 0.0


def test_treasure_is_penalised_when_mimic_chance_is_set():
    # 50% chance of being a mimic with assumed 1 HP loss => -0.5 expected.
    assert evaluate_cell(Cell(content="treasure"), _player(), mimic_chance=0.5) == -0.5


def test_empty_cell_is_neutral():
    assert evaluate_cell(Cell(content="empty"), _player()) == 0.0


def test_cell_with_no_value_is_neutral():
    # Value missing (e.g. detector couldn't read the badge digit) -> assume safe.
    assert evaluate_cell(Cell(content="physical", value=None), _player()) == 0.0


# ---------------------------------------------------------------------------
# evaluate_row
# ---------------------------------------------------------------------------

def test_row_assigns_uniform_landing_probability():
    cells = [Cell(content="empty") for _ in range(4)]
    result = evaluate_row(0, cells, _player())
    assert all(o.landing_probability == 0.25 for o in result.cells)


def test_row_expected_is_weighted_mean_of_cell_outcomes():
    # One cell does -4 HP, three are neutral -> expected = -1.0
    cells = [
        Cell(content="physical", value=6),
        Cell(content="empty"),
        Cell(content="empty"),
        Cell(content="empty"),
    ]
    result = evaluate_row(2, cells, _player(sword=2))
    assert result.row == 2
    assert result.expected_hp_change == -1.0
    assert result.worst_case_hp_change == -4.0


# ---------------------------------------------------------------------------
# recommend_row
# ---------------------------------------------------------------------------

def _state(rows: list[list[Cell]], player: Player | None = None) -> GameState:
    return GameState(board=rows, player=player or _player())


def test_recommends_the_safest_row():
    deadly = [Cell(content="physical", value=10) for _ in range(4)]
    safe = [Cell(content="empty") for _ in range(4)]
    rec = recommend_row(_state([deadly, safe, deadly, deadly]))
    assert rec.best_row == 1


def test_prefers_healing_row_over_neutral_when_wounded():
    neutral = [Cell(content="empty") for _ in range(4)]
    healing = [Cell(content="heal", value=2) for _ in range(4)]
    player = _player(hp=2)  # plenty of room to heal
    rec = recommend_row(_state([neutral, healing, neutral, neutral], player))
    assert rec.best_row == 1


def test_tiebreak_prefers_better_worst_case():
    # Row 0 has one big risk (-3 worst), three empties -> exp = -0.75.
    # Row 1 has all empties -> exp = 0.
    # No actual tie, but illustrates that exp wins over worst when they disagree.
    risky = [
        Cell(content="physical", value=5),  # -3 HP with sword=2
        Cell(content="empty"),
        Cell(content="empty"),
        Cell(content="empty"),
    ]
    safe = [Cell(content="empty") for _ in range(4)]
    rec = recommend_row(_state([risky, safe], _player(sword=2)))
    assert rec.best_row == 1

    # Now: rows with the same expected value but different worst-case.
    row_no_risk = [Cell(content="empty") for _ in range(4)]
    row_balanced = [
        Cell(content="physical", value=3),  # -1
        Cell(content="heal", value=1),       # +1 (room=1 in player below)
        Cell(content="empty"),
        Cell(content="empty"),
    ]
    player = Player(hp=4, max_hp=5, sword=2, magic=0)
    # Both rows expect 0; row_no_risk has worst 0, row_balanced has worst -1.
    rec = recommend_row(_state([row_balanced, row_no_risk], player))
    assert rec.best_row == 1


def test_tiebreak_falls_back_to_lowest_row_index():
    same = [Cell(content="empty") for _ in range(4)]
    rec = recommend_row(_state([same, same, same, same]))
    assert rec.best_row == 0


def test_mimic_chance_penalises_treasure_rows():
    treasure = [Cell(content="treasure") for _ in range(4)]
    empty = [Cell(content="empty") for _ in range(4)]
    state = _state([treasure, empty])

    # No mimic risk -> tie on expected, fall back to lowest row index.
    rec_safe = recommend_row(state, mimic_chance=0.0)
    assert rec_safe.best_row == 0

    # With mimic risk, treasure rows are penalised.
    rec_risky = recommend_row(state, mimic_chance=0.5)
    assert rec_risky.best_row == 1


def test_recommendation_contains_per_row_breakdown():
    cells = [Cell(content="empty") for _ in range(4)]
    rec = recommend_row(_state([cells, cells, cells, cells]))
    assert [r.row for r in rec.rows] == [0, 1, 2, 3]
    assert all(len(r.cells) == 4 for r in rec.rows)


# ---------------------------------------------------------------------------
# landing probabilities (book modifiers)
# ---------------------------------------------------------------------------

def test_landing_probabilities_uniform_without_modifiers():
    cells = [Cell(content="empty") for _ in range(4)]
    assert landing_probabilities(cells) == [0.25, 0.25, 0.25, 0.25]


def test_modifier_biases_landing_toward_matching_cells():
    cells = [
        Cell(content="physical", value=3),
        Cell(content="empty"),
        Cell(content="empty"),
        Cell(content="empty"),
    ]
    probs = landing_probabilities(cells, Modifiers(physical=0.30))
    # Weights 1.3, 1, 1, 1 -> total 4.3.
    assert probs[0] == pytest.approx(1.3 / 4.3)
    assert probs[1] == pytest.approx(1.0 / 4.3)
    assert sum(probs) == pytest.approx(1.0)


def test_recommend_accounts_for_landing_bias():
    # A row with one nasty physical hit becomes much worse when physical landings
    # are heavily biased, so the safe row wins and the expected value reflects it.
    risky = [
        Cell(content="physical", value=5),  # -3 HP with sword 2
        Cell(content="empty"),
        Cell(content="empty"),
        Cell(content="empty"),
    ]
    safe = [Cell(content="empty") for _ in range(4)]
    player = Player(hp=5, max_hp=5, sword=2, magic=0)
    state = GameState(board=[risky, safe], player=player, modifiers=Modifiers(physical=2.0))
    rec = recommend_row(state)
    assert rec.best_row == 1
    # physical weight 3 of total 6 -> p=0.5; expected = 0.5 * -3 = -1.5.
    assert rec.rows[0].expected_hp_change == pytest.approx(-1.5)


# ---------------------------------------------------------------------------
# door / route objective
# ---------------------------------------------------------------------------

def test_reports_tiles_remaining_from_door():
    cells = [Cell(content="empty") for _ in range(4)]
    state = GameState(board=[cells, cells], player=_player(), door=Door(cleared=2, required=5))
    rec = recommend_row(state)
    assert rec.tiles_remaining == 3
    assert rec.door_open is False


def test_flags_open_door_when_objective_met():
    cells = [Cell(content="empty") for _ in range(4)]
    state = GameState(board=[cells, cells], player=_player(), door=Door(cleared=5, required=5))
    rec = recommend_row(state)
    assert rec.tiles_remaining == 0
    assert rec.door_open is True
    assert rec.best_case_hp_to_open is None  # nothing left to clear


def test_best_case_hp_to_open_sums_cheapest_remaining_tiles():
    # Costs with sword 2: empty 0, physical(3) -1, physical(4) -2, physical(5) -3.
    row = [
        Cell(content="empty"),
        Cell(content="physical", value=3),
        Cell(content="physical", value=4),
        Cell(content="physical", value=5),
    ]
    state = GameState(
        board=[row],
        player=Player(hp=9, max_hp=9, sword=2, magic=0),
        door=Door(cleared=0, required=2),
    )
    rec = recommend_row(state)
    # The two cheapest tiles are the empty (0) and the -1 -> best case -1.
    assert rec.best_case_hp_to_open == pytest.approx(-1.0)


def test_no_door_leaves_route_fields_empty():
    cells = [Cell(content="empty") for _ in range(4)]
    rec = recommend_row(GameState(board=[cells], player=_player()))
    assert rec.tiles_remaining is None
    assert rec.door_open is False
    assert rec.best_case_hp_to_open is None
