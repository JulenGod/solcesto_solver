"""Tests for the row-recommendation algorithm.

Note on fillers: a cleared tile reads as content 'empty' and can't be landed on
again, so tests use `treasure` (landable, 0 HP at mimic_chance 0) as the neutral
"safe tile", and reserve 'empty' for genuinely-cleared cells.
"""
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


def _safe() -> Cell:
    """A landable tile that costs no HP (treasure, mimic_chance 0)."""
    return Cell(content="treasure")


def _state(rows: list[list[Cell]], player: Player | None = None) -> GameState:
    return GameState(board=rows, player=player or _player())


# ---------------------------------------------------------------------------
# evaluate_cell
# ---------------------------------------------------------------------------

def test_physical_no_damage_when_sword_meets_threat():
    assert evaluate_cell(Cell(content="physical", value=2), _player(sword=2)) == 0.0


def test_physical_takes_difference_when_sword_lacks():
    assert evaluate_cell(Cell(content="physical", value=5), _player(sword=2)) == -3.0


def test_magic_uses_magic_stat_not_sword():
    assert evaluate_cell(Cell(content="magic", value=4), _player(sword=10, magic=1)) == -3.0


def test_heal_returns_positive_hp_change():
    assert evaluate_cell(Cell(content="heal", value=2), _player(hp=3, max_hp=5)) == 2.0


def test_heal_capped_by_room_to_max_hp():
    assert evaluate_cell(Cell(content="heal", value=5), _player(hp=4, max_hp=5)) == 1.0


def test_treasure_is_neutral_without_mimic_chance():
    assert evaluate_cell(Cell(content="treasure"), _player()) == 0.0


def test_treasure_is_penalised_when_mimic_chance_is_set():
    assert evaluate_cell(Cell(content="treasure"), _player(), mimic_chance=0.5) == -0.5


def test_empty_cell_is_neutral():
    assert evaluate_cell(Cell(content="empty"), _player()) == 0.0


def test_cell_with_no_value_is_neutral():
    assert evaluate_cell(Cell(content="physical", value=None), _player()) == 0.0


# ---------------------------------------------------------------------------
# evaluate_row
# ---------------------------------------------------------------------------

def test_row_assigns_uniform_landing_probability():
    cells = [_safe() for _ in range(4)]
    result = evaluate_row(0, cells, _player())
    assert all(o.landing_probability == 0.25 for o in result.cells)


def test_row_expected_is_weighted_mean_of_cell_outcomes():
    # One cell does -4 HP, three are neutral -> expected = -1.0.
    cells = [Cell(content="physical", value=6), _safe(), _safe(), _safe()]
    result = evaluate_row(2, cells, _player(sword=2))
    assert result.row == 2
    assert result.expected_hp_change == -1.0
    assert result.worst_case_hp_change == -4.0


# ---------------------------------------------------------------------------
# cleared tiles can't be landed on again
# ---------------------------------------------------------------------------

def test_cleared_cells_are_not_landable():
    # Three live tiles + one cleared -> the cleared tile is skipped and the rest
    # share the row at ~1/3 each (four 25% tiles, break one, three at 33%).
    cells = [_safe(), _safe(), _safe(), Cell(content="empty")]
    probs = landing_probabilities(cells)
    assert probs[3] == 0.0
    assert probs[0] == pytest.approx(1 / 3)
    assert sum(probs) == pytest.approx(1.0)


def test_fully_cleared_row_has_zero_landing():
    assert landing_probabilities([Cell(content="empty") for _ in range(4)]) == [0.0, 0.0, 0.0, 0.0]


def test_recommend_skips_fully_cleared_rows():
    # A cleared row looks "free" but makes no progress, so a playable (costly) row
    # must be chosen over it.
    cleared = [Cell(content="empty") for _ in range(4)]
    playable = [Cell(content="physical", value=5) for _ in range(4)]  # -3 each
    rec = recommend_row(_state([cleared, playable], _player(sword=2)))
    assert rec.best_row == 1


# ---------------------------------------------------------------------------
# recommend_row
# ---------------------------------------------------------------------------

def test_recommends_the_safest_row():
    deadly = [Cell(content="physical", value=10) for _ in range(4)]
    safe = [_safe() for _ in range(4)]
    rec = recommend_row(_state([deadly, safe, deadly, deadly]))
    assert rec.best_row == 1


def test_prefers_healing_row_over_neutral_when_wounded():
    neutral = [_safe() for _ in range(4)]
    healing = [Cell(content="heal", value=2) for _ in range(4)]
    rec = recommend_row(_state([neutral, healing, neutral, neutral], _player(hp=2)))
    assert rec.best_row == 1


def test_tiebreak_prefers_better_worst_case():
    risky = [Cell(content="physical", value=5), _safe(), _safe(), _safe()]
    safe = [_safe() for _ in range(4)]
    rec = recommend_row(_state([risky, safe], _player(sword=2)))
    assert rec.best_row == 1

    # Same expected value (0), different worst-case: row_no_risk wins on worst-case.
    row_no_risk = [_safe() for _ in range(4)]
    row_balanced = [
        Cell(content="physical", value=3),  # -1
        Cell(content="heal", value=1),       # +1 (room = 1 for the player below)
        _safe(),
        _safe(),
    ]
    player = Player(hp=4, max_hp=5, sword=2, magic=0)
    rec = recommend_row(_state([row_balanced, row_no_risk], player))
    assert rec.best_row == 1


def test_tiebreak_falls_back_to_lowest_row_index():
    same = [_safe() for _ in range(4)]
    rec = recommend_row(_state([same, same, same, same]))
    assert rec.best_row == 0


def test_mimic_chance_penalises_treasure_rows():
    treasure = [Cell(content="treasure") for _ in range(4)]
    # A landable, zero-cost row that is NOT treasure (so mimic risk doesn't touch it).
    safe = [Cell(content="physical", value=0) for _ in range(4)]
    state = _state([treasure, safe])

    rec_safe = recommend_row(state, mimic_chance=0.0)
    assert rec_safe.best_row == 0  # tie on expected -> lowest row index

    rec_risky = recommend_row(state, mimic_chance=0.5)
    assert rec_risky.best_row == 1  # treasure row now penalised


def test_recommendation_contains_per_row_breakdown():
    cells = [_safe() for _ in range(4)]
    rec = recommend_row(_state([cells, cells, cells, cells]))
    assert [r.row for r in rec.rows] == [0, 1, 2, 3]
    assert all(len(r.cells) == 4 for r in rec.rows)


# ---------------------------------------------------------------------------
# landing probabilities (book modifiers)
# ---------------------------------------------------------------------------

def test_landing_probabilities_uniform_without_modifiers():
    assert landing_probabilities([_safe() for _ in range(4)]) == [0.25, 0.25, 0.25, 0.25]


def test_modifier_biases_landing_toward_matching_cells():
    cells = [Cell(content="physical", value=3), _safe(), _safe(), _safe()]
    probs = landing_probabilities(cells, Modifiers(physical=0.30))
    # Weights 1.3, 1, 1, 1 -> total 4.3.
    assert probs[0] == pytest.approx(1.3 / 4.3)
    assert probs[1] == pytest.approx(1.0 / 4.3)
    assert sum(probs) == pytest.approx(1.0)


def test_recommend_accounts_for_landing_bias():
    risky = [Cell(content="physical", value=5), _safe(), _safe(), _safe()]
    safe = [_safe() for _ in range(4)]
    state = GameState(
        board=[risky, safe],
        player=Player(hp=5, max_hp=5, sword=2, magic=0),
        modifiers=Modifiers(physical=2.0),
    )
    rec = recommend_row(state)
    assert rec.best_row == 1
    # physical weight 3 of total 6 -> p=0.5; expected = 0.5 * -3 = -1.5.
    assert rec.rows[0].expected_hp_change == pytest.approx(-1.5)


# ---------------------------------------------------------------------------
# door / route objective
# ---------------------------------------------------------------------------

def test_reports_tiles_remaining_from_door():
    cells = [_safe() for _ in range(4)]
    state = GameState(board=[cells, cells], player=_player(), door=Door(cleared=2, required=5))
    rec = recommend_row(state)
    assert rec.tiles_remaining == 3
    assert rec.door_open is False


def test_flags_open_door_when_objective_met():
    cells = [_safe() for _ in range(4)]
    state = GameState(board=[cells, cells], player=_player(), door=Door(cleared=5, required=5))
    rec = recommend_row(state)
    assert rec.tiles_remaining == 0
    assert rec.door_open is True
    assert rec.best_case_hp_to_open is None


def test_best_case_hp_to_open_sums_cheapest_uncleared_tiles():
    # Costs with sword 2: physical(3) -1, physical(4) -2, physical(5) -3. The empty
    # is already cleared, so it's excluded; the two cheapest tiles are -1 and -2.
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
    assert rec.best_case_hp_to_open == pytest.approx(-3.0)


def test_no_door_leaves_route_fields_empty():
    rec = recommend_row(_state([[_safe() for _ in range(4)]]))
    assert rec.tiles_remaining is None
    assert rec.door_open is False
    assert rec.best_case_hp_to_open is None


# ---------------------------------------------------------------------------
# species mechanics (mechanics.py) integration
# ---------------------------------------------------------------------------

def test_black_hole_attracts_extra_landing_probability():
    # A Black Hole pulls harder, so its cell exceeds the uniform 0.25 and the
    # others fall below it.
    cells = [Cell(content="magic", value=4, species="black_hole"), _safe(), _safe(), _safe()]
    probs = landing_probabilities(cells)
    # Weights 2, 1, 1, 1 -> total 5.
    assert probs[0] == pytest.approx(2 / 5)
    assert probs[1] == pytest.approx(1 / 5)
    assert sum(probs) == pytest.approx(1.0)


def test_cursed_strawberry_makes_heals_toxic_in_recommendation():
    from sol_cesto_solver.mechanics import analyze_board

    heal_cell = Cell(content="heal", value=2)
    # Without the curse a heal is good for a wounded player.
    assert evaluate_cell(heal_cell, _player(hp=2), ctx=analyze_board([[heal_cell]])) == 2.0
    # With a Cursed Strawberry on the board the same heal turns toxic (-1).
    cursed = [heal_cell, Cell(content="magic", value=2, species="cursed_strawberry")]
    ctx = analyze_board([cursed])
    assert evaluate_cell(heal_cell, _player(hp=2), ctx=ctx) == -1.0


def test_breaking_a_fledgling_costs_more_when_hawks_are_present():
    from sol_cesto_solver.mechanics import analyze_board

    fledgling = Cell(content="physical", value=1, species="fledgling")
    player = _player(sword=5)  # strong enough that the Fledgling itself deals 0
    # Alone: no face damage and no hidden cost.
    assert evaluate_cell(fledgling, player, ctx=analyze_board([[fledgling]])) == 0.0
    # With two Hawks on the board, killing it buffs both -> -2 hidden cost.
    board = [[fledgling, Cell(content="physical", value=3, species="hawk"),
              Cell(content="physical", value=3, species="hawk")]]
    assert evaluate_cell(fledgling, player, ctx=analyze_board(board)) == -2.0


def test_recommend_avoids_the_fledgling_row_when_hawks_threaten():
    # Both rows look free at face value (player one-shots everything), but breaking
    # the Fledgling row buffs the Hawks, so the plain row is preferred.
    player = _player(sword=5)
    hawk = Cell(content="physical", value=3, species="hawk")
    fledgling_row = [Cell(content="physical", value=1, species="fledgling"), hawk, _safe(), _safe()]
    plain_row = [Cell(content="physical", value=1), _safe(), _safe(), _safe()]
    rec = recommend_row(_state([fledgling_row, plain_row], player))
    assert rec.best_row == 1
