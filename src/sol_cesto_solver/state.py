"""Structured representation of the Sol Cesto game state.

We deliberately classify cells by their **badge** (the static UI element that
sits in the corner of the cell), not by the underlying creature sprite — the
sprites animate and vary between monster types, but the badge icon (red sword,
blue wand, red heart, gold "?") is stable UI that always means the same thing.
"""
from typing import Literal

from pydantic import BaseModel

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


class GameState(BaseModel):
    """Full game state: the 4x4 board, the player, and run-level counters."""

    board: list[list[Cell]]
    player: Player
    gold: int | None = None   # current gold (the frog's counter); None if unread.
    door: Door | None = None  # exit progress; None if unread.
