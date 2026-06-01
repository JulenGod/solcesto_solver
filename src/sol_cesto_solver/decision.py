"""Decision algorithm: pick the row that minimises expected HP loss.

The player chooses a row; their character lands on one of its **uncleared** cells.
A broken tile can't be landed on again, so it drops out and the row renormalises
over what remains (four 25% tiles, clear one, three become ~33%). Landing is
otherwise uniform unless the player's book modifiers bias certain cell types — a
"+30% physical" makes physical cells weigh 1.30 vs 1.0, renormalised across the
row. Each cell heals, damages, or does nothing per its `content`; we compute the
expected HP change for every row and pick the highest (smallest loss, or largest
heal) among rows that still have a tile to break.

Ties are broken first by best worst-case outcome (more defensive), then by
lowest row index (for stability across runs).

`mimic_chance` lets the algorithm be pessimistic about treasures on later levels
where chests might actually be mimics in disguise — a real game mechanic that
we can't see from a single screenshot. With `mimic_chance=0` (default) treasures
are assumed safe.
"""
from pydantic import BaseModel

from .mechanics import (
    TOXIC_HEAL_LOSS,
    BoardContext,
    analyze_board,
    landing_attraction,
    species_hp_adjustment,
)
from .state import Cell, GameState, Modifiers, Player

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


class ItemAdvice(BaseModel):
    """A suggested use of a consumable the player is holding (see items.py)."""

    item: str    # item key
    detail: str  # human-readable suggestion


class Recommendation(BaseModel):
    """Final pick plus the per-row breakdown that justifies it.

    The door fields frame the pick around the level objective: you must break
    `required` tiles to open the exit, so the goal isn't pure avoidance — you
    have to keep clearing tiles, as cheaply as possible, until the door opens.
    """

    best_row: int
    rows: list[RowEvaluation]
    tiles_remaining: int | None = None     # tiles still to break to open the door
    door_open: bool = False                # objective already met (can exit)
    best_case_hp_to_open: float | None = None  # HP change if you clear the cheapest remaining tiles
    item_advice: list[ItemAdvice] = []     # suggested item plays given what you're holding


def evaluate_cell(
    cell: Cell,
    player: Player,
    mimic_chance: float = 0.0,
    ctx: BoardContext | None = None,
) -> float:
    """HP change if the player lands on this cell. Negative = HP lost.

    `ctx` carries cross-cell mechanics (see mechanics.py): a Cursed Strawberry
    turns heals toxic, and killing a Fledgling buffs every Hawk. When omitted the
    cell is scored in isolation (the original per-cell behaviour).
    """
    change = _content_hp_change(cell, player, mimic_chance, ctx)
    if ctx is not None and cell.species:
        change += species_hp_adjustment(cell, ctx)
    return change


def _content_hp_change(
    cell: Cell, player: Player, mimic_chance: float, ctx: BoardContext | None
) -> float:
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
            if ctx is not None and ctx.heals_toxic:
                return -TOXIC_HEAL_LOSS  # a Cursed Strawberry makes every heal toxic
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


def _landing_bias(content: str, modifiers: Modifiers | None) -> float:
    """The landing-probability bias for a cell of this content (0 if none).

    gold_multiplier is a reward scaler, not a landing bias, so it's excluded.
    """
    if modifiers is None:
        return 0.0
    by_content = {
        "physical": modifiers.physical,
        "magic": modifiers.magic,
        "heal": modifiers.heal,
        "treasure": modifiers.treasure,
        "trap": modifiers.trap,
    }
    return by_content.get(content) or 0.0


def landing_probabilities(cells: list[Cell], modifiers: Modifiers | None = None) -> list[float]:
    """Per-cell landing probability for a row.

    Cleared tiles (content 'empty') can't be landed on again, so they get zero
    weight and the row renormalises over the remaining tiles — clearing one of
    four 25% tiles leaves three at ~33%. Each remaining cell weighs
    (1 + its content modifier + its species' landing attraction): an attracting
    monster like a Black Hole or Mimic pulls harder than a plain tile. A
    fully-cleared row returns all zeros.
    """
    if not cells:
        return []
    weights = [
        0.0 if c.content == "empty"
        else max(0.0, 1.0 + _landing_bias(c.content, modifiers) + landing_attraction(c))
        for c in cells
    ]
    total = sum(weights)
    if total <= 0:
        return [0.0] * len(cells)
    return [w / total for w in weights]


def evaluate_row(
    row_index: int,
    cells: list[Cell],
    player: Player,
    mimic_chance: float = 0.0,
    modifiers: Modifiers | None = None,
    ctx: BoardContext | None = None,
) -> RowEvaluation:
    """Expected HP change if the player picks this row."""
    probs = landing_probabilities(cells, modifiers)
    outcomes = [
        CellOutcome(
            col=i,
            landing_probability=probs[i],
            hp_change=evaluate_cell(c, player, mimic_chance, ctx),
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


def _best_case_hp_to_open(
    state: GameState, tiles_remaining: int, mimic_chance: float, ctx: BoardContext | None = None
) -> float:
    """Best-case HP change to open the door: clear the `tiles_remaining` cheapest tiles.

    You can't choose the exact tile (landing is random), so this is an optimistic
    floor — the HP you'd lose if you managed to break the least costly tiles on the
    board. The realistic cost is higher; the per-turn `best_row` is the practical move.
    """
    costs = sorted(
        (evaluate_cell(cell, state.player, mimic_chance, ctx)
         for row in state.board for cell in row
         if cell.content != "empty"),  # already-cleared tiles can't be cleared again
        reverse=True,  # least loss (0 / heals) first, biggest loss last
    )
    return float(sum(costs[:tiles_remaining]))


def _worst_landable_cell(
    board: list[list[Cell]], player: Player, mimic_chance: float, ctx: BoardContext | None
) -> tuple[int, int, Cell, float] | None:
    """The single most damaging landable cell: (row, col, cell, hp_change<0), or None."""
    worst: tuple[int, int, Cell, float] | None = None
    for r, row in enumerate(board):
        for c, cell in enumerate(row):
            if cell.content == "empty":
                continue
            change = evaluate_cell(cell, player, mimic_chance, ctx)
            if change < 0 and (worst is None or change < worst[3]):
                worst = (r, c, cell, change)
    return worst


def advise_items(
    state: GameState,
    rows: list[RowEvaluation],
    best: RowEvaluation | None = None,
    ctx: BoardContext | None = None,
    mimic_chance: float = 0.0,
) -> list[ItemAdvice]:
    """Suggest useful plays for the consumables the player is holding.

    `best` is the row the recommendation actually picks; bubble advice keys off it
    (it blocks the hit you'd otherwise take). These are opportunity hints, not a
    multi-turn solve: each item costs a turn, so the call on whether to spend it
    stays with the player. We only surface an item when the board gives it
    something to do (a deadly row to bomb, a monster to arrow, a hit to bubble,
    a wound to heal).
    """
    held = state.items
    if not held:
        return []

    advice: list[ItemAdvice] = []
    player = state.player
    worst_row = min(rows, key=lambda e: e.expected_hp_change) if rows else None
    worst_cell = _worst_landable_cell(state.board, player, mimic_chance, ctx)
    has_threat = worst_cell is not None

    if "bomb" in held and worst_row is not None and worst_row.expected_hp_change < 0:
        exp = worst_row.expected_hp_change
        advice.append(ItemAdvice(
            item="bomb", detail=f"Bomb row {worst_row.row} (worst row, exp {exp:+.1f} HP)",
        ))
    if "cluster_bomb" in held and has_threat:
        advice.append(ItemAdvice(
            item="cluster_bomb", detail="Cluster bomb clears one random monster on every row"
        ))
    if "arrow" in held and worst_cell is not None:
        r, c, cell, loss = worst_cell
        advice.append(ItemAdvice(
            item="arrow",
            detail=f"Arrow the {cell.species or cell.content} at row {r} col {c} ({loss:+.1f} HP)",
        ))
    if "ice_cube" in held and has_threat:
        advice.append(
            ItemAdvice(item="ice_cube", detail="Ice cube: -1 to every monster for 2 turns")
        )
    if "bubble" in held and best is not None and best.worst_case_hp_change < 0:
        wc = best.worst_case_hp_change
        advice.append(ItemAdvice(
            item="bubble", detail=f"Bubble blocks the next hit (best row worst-case {wc:+.1f} HP)",
        ))
    if player.hp < player.max_hp:
        for heal_item in ("strawberry_juice", "egg"):
            if heal_item in held:
                advice.append(ItemAdvice(item=heal_item, detail="Heals 1 HP"))
                break

    return advice


def recommend_row(state: GameState, mimic_chance: float = 0.0) -> Recommendation:
    """Recommend the row to play toward opening the door with the least HP loss.

    Each turn breaks one tile, so the practical move is the row with the smallest
    expected HP loss (it makes the cheapest progress). Tiebreakers (in order):
    better worst-case, then lower row index. The door fields report how far the
    objective is and an optimistic HP estimate for the whole route.
    """
    ctx = analyze_board(state.board)
    rows = [
        evaluate_row(r, cells, state.player, mimic_chance, state.modifiers, ctx)
        for r, cells in enumerate(state.board)
    ]
    # You can only make progress on rows that still have an uncleared tile; a
    # fully-cleared row looks "free" (0 cost) but can't be played.
    playable = [
        ev for ev, cells in zip(rows, state.board, strict=True)
        if any(c.content != "empty" for c in cells)
    ]
    best = max(
        playable or rows,
        key=lambda e: (e.expected_hp_change, e.worst_case_hp_change, -e.row),
    )

    tiles_remaining: int | None = None
    door_open = False
    best_case: float | None = None
    door = state.door
    if door is not None and door.required is not None and door.cleared is not None:
        tiles_remaining = max(0, door.required - door.cleared)
        door_open = tiles_remaining == 0
        if tiles_remaining > 0:
            best_case = _best_case_hp_to_open(state, tiles_remaining, mimic_chance, ctx)

    return Recommendation(
        best_row=best.row,
        rows=rows,
        tiles_remaining=tiles_remaining,
        door_open=door_open,
        best_case_hp_to_open=best_case,
        item_advice=advise_items(state, rows, best, ctx, mimic_chance),
    )
