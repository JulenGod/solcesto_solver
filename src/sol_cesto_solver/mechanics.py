"""Cross-cell monster mechanics that bend the naive per-cell decision math.

The plain model in ``decision.py`` treats every cell independently. Several
identified species break that assumption (the "intelligence" the bestiary
records):

* **Black Hole** and **Mimic** *attract* you — they raise the chance you land on
  their cell, so a row holding one is riskier than a uniform split suggests.
* A **Cursed Strawberry** anywhere on the board turns every heal (strawberry)
  toxic, so heal cells hurt instead of help.
* Killing a **Fledgling** permanently grants **+1 strength to every Hawk** on the
  board, so breaking that cell carries a hidden future cost.

This module reads the species already attached to cells (see ``species.py`` /
``bestiary.py``) and returns the adjustments ``decision.py`` applies. The exact
magnitudes aren't published, so they're documented heuristics, kept here behind
named constants so they're easy to tune as we learn more.
"""
from dataclasses import dataclass

from .state import Cell

# Extra landing weight for an "attracting" monster, on top of the base 1.0 — so a
# Black Hole pulls ~twice as hard as an ordinary tile before renormalisation.
ATTRACT_WEIGHT = 1.0
_ATTRACTORS = frozenset({"black_hole", "mimic"})

# HP lost when you land on a heal that a Cursed Strawberry has made toxic
# (mirrors the toxic-strawberry trap, which takes 1 HP).
TOXIC_HEAL_LOSS = 1.0


@dataclass(frozen=True)
class BoardContext:
    """Board-wide facts that change how individual cells should be scored."""

    hawks: int = 0            # number of Hawks present (each Fledgling kill buffs them)
    heals_toxic: bool = False  # a Cursed Strawberry is on the board


def analyze_board(board: list[list[Cell]]) -> BoardContext:
    """Summarise the cross-cell mechanics in play on this board."""
    species = [cell.species for row in board for cell in row if cell.species]
    return BoardContext(
        hawks=sum(1 for s in species if s == "hawk"),
        heals_toxic=any(s == "cursed_strawberry" for s in species),
    )


def landing_attraction(cell: Cell) -> float:
    """Extra landing-probability weight if this cell's species attracts you."""
    return ATTRACT_WEIGHT if cell.species in _ATTRACTORS else 0.0


def species_hp_adjustment(cell: Cell, ctx: BoardContext) -> float:
    """Extra HP cost/benefit beyond the cell's face value, from monster relations.

    Negative = a hidden cost. Currently: breaking a Fledgling buffs every Hawk on
    the board by +1 strength, i.e. each Hawk will hit one harder later on.
    """
    if cell.species == "fledgling" and ctx.hawks:
        return -float(ctx.hawks)
    return 0.0
