"""Sol Cesto "Teeth": the run modifiers offered by the devil statues.

Compiled from the wiki. Two families:

* **Stone** teeth shift spawn/reward *probabilities* (more/less chance of a
  strength/magic monster, strawberry, chest, trap; money multipliers; …), each
  with an upside and a downside.
* **Metal** teeth are conditional *combat* effects — mostly "weaken (-1 for 1
  turn)" triggered by killing monsters, landing on strawberries/chests, floor
  start, etc. These are the source of the temporary -1 attack debuff.

This is the domain model the decision algorithm will read once it knows which
teeth the player has equipped. `key` is "<statue><number>", e.g. "metal1".
Percentages are kept as the wiki's text ranges; structured parsing can come with
the algorithm that consumes them.
"""
from dataclasses import dataclass
from typing import Literal

Statue = Literal["stone", "metal"]


@dataclass(frozen=True)
class Tooth:
    statue: Statue
    number: int
    effects: tuple[str, ...]

    @property
    def key(self) -> str:
        return f"{self.statue}{self.number}"


_STONE: tuple[Tooth, ...] = (
    Tooth("stone", 1, ("Reduce strength-monster chance by 28-32%", "-2 HP (cannot kill you)")),
    Tooth("stone", 2, (
        "Reduce magic-monster chance by 28-33%",
        "Reduce strawberry chance by 8-15%",
    )),
    Tooth("stone", 3, (
        "Increase strawberry chance by 22-28%",
        "Increase strength-monster chance by 7-14%",
    )),
    Tooth("stone", 4, ("Money multiplier +1", "Increase either-monster chance by 27-33%")),
    Tooth("stone", 5, ("Reduce trap chance by 37-42%", "Reduce chest chance by 12-19%")),
    Tooth("stone", 6, ("Reduce strength-monster chance by 16-24%", "Reduce chest chance by 5-11%")),
    Tooth("stone", 7, ("Reduce magic-monster chance by 16-21%", "Reduce chest chance by 7-12%")),
    Tooth("stone", 8, (
        "Increase strawberry chance by 46-53%",
        "-1 max HP (only lowers current HP if at max)",
    )),
    Tooth("stone", 9, ("Money multiplier +1", "+1 move needed to unlock the door")),
    Tooth("stone", 10, ("Reduce trap chance by 16-23%", "Increase either-monster chance by 6-10%")),
    Tooth("stone", 11, ("Increase chest chance by 17-23%", "Increase trap chance by 5-18%")),
    Tooth("stone", 12, (
        "Reduce strength-monster chance by 17-23%",
        "Increase magic-monster chance by 3-10%",
    )),
    Tooth("stone", 13, (
        "Reduce magic-monster chance by 16-22%",
        "Increase strength-monster chance by 5-10%",
    )),
    Tooth("stone", 14, (
        "Increase chest chance by 48-53%",
        "+1 move required to restore Sun Power",
    )),
    Tooth("stone", 15, ("Golden ant gives +17-24 coins", "Ant speed multiplier +1.5")),
    Tooth("stone", 16, ("Healing also gives +1 coin", "Merchant has 20% fewer strawberries")),
    Tooth("stone", 17, ("Strawberries heal +1 more", "Reduce strawberry chance by 39-49%")),
)

_METAL: tuple[Tooth, ...] = (
    Tooth("metal", 1, ("Killing 2 strength monsters weakens all magic monsters (-1 for 1 turn)",)),
    Tooth("metal", 2, ("Killing 2 magic monsters weakens all strength monsters (-1 for 1 turn)",)),
    Tooth("metal", 3, ("Killing 3 monsters weakens 3 random monsters (-1 for 1 turn)",)),
    Tooth("metal", 4, (
        "Landing on a strawberry weakens cardinally-adjacent monsters (-1 for 1 turn)",
    )),
    Tooth("metal", 5, ("Opening 1 chest disables 1 random trap",)),
    # metal 6 is marked W.I.P. on the wiki — omitted until it's documented.
    Tooth("metal", 7, (
        "First move of each floor weakens the whole vertical column (-1 for 1 turn)",
    )),
    Tooth("metal", 8, ("At the start of each floor, weaken 3 random monsters (-1 for 1 turn)",)),
    Tooth("metal", 9, (
        "First move of each floor weakens the whole horizontal row (-1 for 1 turn)",
    )),
    Tooth("metal", 10, (
        "Landing on a chest weakens cardinally-adjacent monsters (-1 for 1 turn)",
    )),
    Tooth("metal", 11, ("Heal 1 HP every 2nd floor",)),
    Tooth("metal", 12, ("Every 2nd HP healed, 1 random monster dies",)),
    Tooth("metal", 13, ("Heal 1 HP every 2nd item used",)),
    Tooth("metal", 14, ("Each item used turns a random tile into a bonus tile",)),
    Tooth("metal", 15, (
        "Killing a monster with an ability weakens all monsters without abilities (-1 for 1 turn)",
    )),
    Tooth("metal", 16, ("Every 2nd chest opened weakens all monsters (-1 for 1 turn)",)),
)

TEETH: dict[str, Tooth] = {t.key: t for t in (*_STONE, *_METAL)}
