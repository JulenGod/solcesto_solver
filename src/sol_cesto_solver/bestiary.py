"""Sol Cesto bestiary: monster roster, stats, abilities, and inter-monster links.

Compiled from the wiki (early-access content, 3 biomes). This is the *domain
model* behind species identification: once a cell's creature is classified
(see the planned species classifier), this table says what it does — including
the relationships between monsters ("intelligence") that break the naive
per-cell math, e.g. killing a Fledgling buffs a Hawk, or a Drummer buffing its
neighbours.

`key` matches the reference-sprite filename stem in references/monsters/.
`damage` is a string because some monsters vary it ("3+", "1/4").
`relations` lists the keys of other monsters this one interacts with.
"""
from dataclasses import dataclass, field
from typing import Literal

Attack = Literal["strength", "magic", "varies"]


@dataclass(frozen=True)
class MonsterInfo:
    key: str
    name: str
    biome: str
    attack: Attack
    damage: str
    special: bool
    ability: str
    relations: tuple[str, ...] = field(default_factory=tuple)


_MONSTERS: tuple[MonsterInfo, ...] = (
    # --- Dungeon (biome 1) ---
    MonsterInfo("slime", "Slime", "dungeon", "magic", "1", False, ""),
    MonsterInfo("red_coyote", "Red Coyote", "dungeon", "strength", "3", False, ""),
    MonsterInfo("living_book", "Living Book", "dungeon", "magic", "3", False,
                "Strongest magic monster in the dungeon."),
    MonsterInfo("tomato_monster", "Tomato Monster", "dungeon", "strength", "4", False,
                "Strongest strength monster in the dungeon."),
    MonsterInfo("drummer", "Drummer", "dungeon", "magic", "2", True,
                "Increases horizontally-adjacent monsters' stats by 1."),
    MonsterInfo("switching_rabbit", "Switching Rabbit", "dungeon", "varies", "2", True,
                "Swaps between strength and magic every turn."),
    MonsterInfo("wizard", "Wizard", "dungeon", "magic", "3", True,
                "Destroys a random bonus tile each turn."),
    # --- Mushroom Forest (biome 2) ---
    MonsterInfo("fledgling", "Fledgling", "mushroom_forest", "strength", "1", True,
                "Killing it powers up Hawks on the board.", ("hawk",)),
    MonsterInfo("snake", "Snake", "mushroom_forest", "magic", "3", False, ""),
    MonsterInfo("white_coyote", "White Coyote", "mushroom_forest", "strength", "4", False,
                "Strongest strength monster here."),
    MonsterInfo("bee", "Bee", "mushroom_forest", "magic", "3", False,
                "Only appears on floors with a Hive Monster.", ("hive_monster",)),
    MonsterInfo("hedgehog", "Hedgehog", "mushroom_forest", "strength", "1/4", True,
                "Swaps between 1 and 4 strength every turn."),
    MonsterInfo("hawk", "Hawk", "mushroom_forest", "strength", "3+", True,
                "Gains +1 strength each time a Fledgling is killed.", ("fledgling",)),
    MonsterInfo("firefly", "Firefly", "mushroom_forest", "magic", "2", True,
                "On death, lights up a 3x3 area (reveals tiles in dark rooms)."),
    MonsterInfo("hive_monster", "Hive Monster", "mushroom_forest", "magic", "3", True,
                "Fills empty tiles with Bees each turn.", ("bee",)),
    # --- Ocean (biome 3) ---
    MonsterInfo("crab", "Crab", "ocean", "strength", "3", False, ""),
    MonsterInfo("starfish", "Starfish", "ocean", "magic", "2", False, ""),
    MonsterInfo("fish_monster", "Fish Monster", "ocean", "strength", "5", False,
                "The strongest monster in the game."),
    MonsterInfo("tadpole", "Tadpole", "ocean", "strength", "2", True,
                "Increases its strength by 1 each turn."),
    MonsterInfo("black_hole", "Black Hole", "ocean", "magic", "4", True,
                "Attracts you — raises the chance you land on it."),
    MonsterInfo("cursed_strawberry", "Cursed Strawberry", "ocean", "magic", "2", True,
                "Makes strawberries (heals) toxic."),
    MonsterInfo("mimic", "Mimic", "ocean", "magic", "3", True,
                "Pretends to be a chest and attracts you like a chest."),
)

# Traps (not attackers, but landing on them hurts/affects you).
_TRAPS: tuple[MonsterInfo, ...] = (
    MonsterInfo("spikes", "Spikes", "dungeon", "varies", "1", True,
                "Deals 1 damage when you land there."),
    MonsterInfo("poisonous_mushroom", "Poisonous Mushroom", "mushroom_forest", "varies", "1", True,
                "Gives 1 poison; at 3 poison you die. Resets each floor."),
    MonsterInfo("clam", "Clam", "ocean", "varies", "0", True,
                "Bounces you onto a random tile."),
    MonsterInfo("toxic_strawberry", "Toxic Strawberry", "ocean", "varies", "1", True,
                "Takes 1 HP."),
)

BESTIARY: dict[str, MonsterInfo] = {m.key: m for m in (*_MONSTERS, *_TRAPS)}
