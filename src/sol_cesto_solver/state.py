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


class Player(BaseModel):
    """The player's stats and inventory."""

    hp: int
    max_hp: int
    sword: int = 0
    magic: int = 0
    inventory: list[str] = Field(default_factory=list)
    modifiers: dict[str, float] = Field(default_factory=dict)


class GameState(BaseModel):
    """Full game state: 4x4 board plus the player."""

    board: list[list[Cell]]
    player: Player
