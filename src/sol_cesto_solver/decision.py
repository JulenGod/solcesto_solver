"""Decision algorithm: pick the row that minimises expected HP loss.

The player chooses a row; their character lands with uniform probability on one
of the cells in that row. Each cell heals, damages, or does nothing depending
on its `content`. We compute the expected HP change for every row and pick the
highest one (i.e. the smallest loss, or the largest heal).

Ties are broken first by best worst-case outcome (more defensive), then by
lowest row index (for stability across runs).

`mimic_chance` lets the algorithm be pessimistic about treasures on later levels
where chests might actually be mimics in disguise — a real game mechanic that
we can't see from a single screenshot. With `mimic_chance=0` (default) treasures
are assumed safe.
"""
from pydantic import BaseModel

from .state import Cell, GameState, Player

# When a treasure turns out to be a mimic, assume a moderate HP loss. We don't
# have data on mimic stats — this is a placeholder until the user supplies a
# mid-game screenshot with a revealed mimic.
_ASSUMED_MIMIC_LOSS = 1.0


class CellOutcome(BaseModel):
    """What happens if the player lands on a specific cell."""

    col: int
    landing_probability: float
    hp_change: float  # negative = damage taken, positive = healing


class RowEvaluation(BaseModel):
    """Evaluation of picking a particular row."""

    row: int
    expected_hp_change: float
    worst_case_hp_change: float
    cells: list[CellOutcome]


class Recommendation(BaseModel):
    """Final pick plus the per-row breakdown that justifies it."""

    best_row: int
    rows: list[RowEvaluation]


def evaluate_cell(cell: Cell, player: Player, mimic_chance: float = 0.0) -> float:
    """HP change if the player lands on this cell. Negative = HP lost."""
    match cell.content:
        case "physical":
            if cell.value is None:
                return 0.0
            return float(-max(0, cell.value - player.sword))
        case "magic":
            if cell.value is None:
                return 0.0
            return float(-max(0, cell.value - player.magic))
        case "heal":
            if cell.value is None:
                return 0.0
            room = player.max_hp - player.hp
            return float(min(cell.value, room))
        case "treasure":
            if mimic_chance > 0:
                return -mimic_chance * _ASSUMED_MIMIC_LOSS
            return 0.0
        case "empty":
            return 0.0
    return 0.0


def evaluate_row(
    row_index: int,
    cells: list[Cell],
    player: Player,
    mimic_chance: float = 0.0,
) -> RowEvaluation:
    """Expected HP change if the player picks this row."""
    landing_p = 1.0 / len(cells) if cells else 0.0
    outcomes = [
        CellOutcome(
            col=i,
            landing_probability=landing_p,
            hp_change=evaluate_cell(c, player, mimic_chance),
        )
        for i, c in enumerate(cells)
    ]
    expected = sum(o.hp_change * o.landing_probability for o in outcomes)
    worst = min((o.hp_change for o in outcomes), default=0.0)
    return RowEvaluation(
        row=row_index,
        expected_hp_change=expected,
        worst_case_hp_change=worst,
        cells=outcomes,
    )


def recommend_row(state: GameState, mimic_chance: float = 0.0) -> Recommendation:
    """Pick the row that maximises expected HP change.

    Tiebreakers (in order): better worst-case, then lower row index.
    """
    rows = [
        evaluate_row(r, cells, state.player, mimic_chance)
        for r, cells in enumerate(state.board)
    ]
    best = max(
        rows,
        key=lambda e: (e.expected_hp_change, e.worst_case_hp_change, -e.row),
    )
    return Recommendation(best_row=best.row, rows=rows)
