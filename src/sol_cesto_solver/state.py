"""Structured representation of the Sol Cesto game state.

We deliberately classify cells by their **badge** (the static UI element that
sits in the corner of the cell), not by the underlying creature sprite — the
sprites animate and vary between monster types, but the badge icon (red sword,
blue wand, red heart, gold "?") is stable UI that always means the same thing.
"""
from typing import Literal

from pydantic import BaseModel, Field

CellContent = Literal[
    "physical",   # Red sword badge: defeated cleanly if player.sword >= value.
    "magic",      # Blue wand badge: defeated cleanly if player.magic >= value.
    "heal",       # Red heart badge: restores `value` HP (typically a strawberry).
    "treasure",   # Gold "?" sparkle: unknown reward (chest, gold pile, etc.).
    "empty",      # No badge detected — either truly empty, or a UI state we
                  # can't read (e.g. cell hidden by a preview overlay).
]


class Cell(BaseModel):
    """A single tile on the 4x4 board."""

    content: CellContent
    value: int | None = None   # damage requirement (physical/magic), heal amount, or None.
    species: str | None = None  # identified monster key (best-effort); None if unsure.
    buffed: bool = False        # shown damage is raised by an adjacent Drummer (+1).


class ToothSlot(BaseModel):
    """An equipped Tooth shown in the top-left "mouth" (a devil-statue run modifier).

    Only occupied slots are reported. `color` is a coarse dominant-colour hint
    (red/blue/gold/dark/...) to help label the tooth; `species` is the resolved
    Tooth key once identification is wired up. While `species` is None the overlay
    flags the tooth as unread so it can be labelled on the fly.
    """

    row: int
    col: int
    color: str | None = None
    species: str | None = None


class Player(BaseModel):
    """The player's stats: current/max HP and the two attack stats."""

    hp: int
    max_hp: int
    sword: int = 0
    magic: int = 0


class Door(BaseModel):
    """Exit progress shown on the right-panel door: clear `required` tiles to open it.

    `cleared` is how many you've broken so far (the top number of the "0/5" badge),
    `required` is the total needed (the bottom number). Either may be None if the
    digit couldn't be read.
    """

    cleared: int | None = None
    required: int | None = None


class Modifiers(BaseModel):
    """Per-content modifiers from the player's book (the bottom-left 2x3 grid).

    The attack/heal/treasure/trap values are **landing-probability biases** stored
    as fractions: e.g. physical = 0.30 (shown in-game as "+30%") makes physical
    cells weigh 1.30 vs 1.0 for the rest, before the row is renormalised — which is
    why the per-cell "25%" shifts. `gold_multiplier` scales gold gained (x1, x2, …)
    and does NOT affect landing odds. None means that entry couldn't be read.
    """

    physical: float | None = None   # sword icon
    magic: float | None = None       # wand icon
    heal: float | None = None        # heart icon (strawberry cells)
    treasure: float | None = None    # chest icon
    trap: float | None = None        # spikes icon (trap cells)
    gold_multiplier: float | None = None  # coin icon


class GameState(BaseModel):
    """Full game state: the 4x4 board, the player, and run-level counters."""

    board: list[list[Cell]]
    player: Player
    gold: int | None = None   # current gold (the frog's counter); None if unread.
    door: Door | None = None  # exit progress; None if unread.
    modifiers: Modifiers = Field(default_factory=Modifiers)  # landing/reward biases.
    teeth: list[ToothSlot] = Field(default_factory=list)  # equipped teeth (occupied slots).
    items: list[str] = Field(default_factory=list)  # held consumable item keys (see items.py).
