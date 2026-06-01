"""Tests for the consumable Items roster."""
from sol_cesto_solver.items import ITEMS, parse_item_list


def test_roster_count_and_unique_keys():
    assert len(ITEMS) == 20
    assert len({it.key for it in ITEMS.values()}) == 20


def test_known_items_and_effects():
    assert ITEMS["bomb"].name == "Bomb"
    assert "row" in ITEMS["bomb"].effect
    assert "Weakens all monsters" in ITEMS["ice_cube"].effect
    assert ITEMS["bubble"].effect.lower().startswith("blocks the next")


def test_every_item_has_effect_and_cost():
    assert all(it.effect for it in ITEMS.values())
    assert all(it.cost > 0 for it in ITEMS.values())


def test_parse_item_list_normalises_validates_and_keeps_order():
    known, unknown = parse_item_list("bomb, Ice Cube, ice-cube, banana")
    assert known == ["bomb", "ice_cube", "ice_cube"]  # order and duplicates preserved
    assert unknown == ["banana"]


def test_parse_item_list_handles_empty_and_blank():
    assert parse_item_list("") == ([], [])
    assert parse_item_list("  ,  ") == ([], [])
