"""Sol Cesto consumable Items (compiled from the wiki).

Items are consumables; using one costs a turn. You carry them in "hand" slots
(from 1 up to 6 with upgrades). Several are highly relevant to routing decisions
because they remove threats or change the board: Bomb (clears a row), Arrow
(kills a chosen monster), Ice cube (weakens everything), Bubble (negates the next
hit), Chili (kills adjacent), Hammer (clears traps), Slingshot (stuns), etc.

`cost` is the base shop price (it rises over a run). `key` is a snake_case id.
This is the domain model the decision algorithm reads once it knows which items
the player is holding.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class Item:
    key: str
    name: str
    effect: str
    cost: int


_ITEMS: tuple[Item, ...] = (
    Item("strawberry_juice", "Strawberry juice", "Heals 1 life point", 12),
    Item("arrow", "Arrow", "Destroys a monster of your choice (Knight's power: a column)", 20),
    Item("bubble", "Bubble", "Blocks the next instance of damage (reduced to 0)", 10),
    Item("sun_potion", "Sun potion", "Refills your sun power", 7),
    Item("bomb", "Bomb", "Destroys all monsters on a row (Knight's power: a column)", 22),
    Item("cluster_bomb", "Cluster bomb", "Destroys a random monster on each row", 15),
    Item("hammer", "Hammer", "Destroys all traps (can also stun the merchant)", 12),
    Item("spider_web", "Spider web", "Sends your gold back to the surface", 8),
    Item("dice", "Dice",
         "Generates a new screen (also refreshes shops, statue teeth, blessings)", 5),
    Item("candle", "Candle", "Lights up dark floors (second region)", 8),
    Item("key", "Key", "Opens the gate to the next floor", 17),
    Item("magnet", "Magnet", "Attracts all the coins in chests", 15),
    Item("ice_cube", "Ice cube", "Weakens all monsters (-1 for 2 turns)", 24),
    Item("power_potion", "Power potion",
         "Increases Magic and Strength (+1, +2 upgraded) for 1 turn", 12),
    Item("pile_of_rocks", "Pile of rocks", "Destroys all the tiles beneath your feet", 17),
    Item("seed", "Seed", "Plants a seed that grows into a strawberry after 1 turn", 12),
    Item("chili", "Chili", "Kills cardinally-adjacent monsters (can kill the merchant)", 18),
    Item("egg", "Egg", "Heals 1 life point (hatches into the lizard in the 4th biome)", 12),
    Item("slingshot", "Slingshot", "Stuns a monster for 1 turn", 12),
    Item("toothpaste", "Toothpaste", "Removes the negative effects on one of your teeth", 25),
)

ITEMS: dict[str, Item] = {it.key: it for it in _ITEMS}
