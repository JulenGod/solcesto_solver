"""Sanity checks for the bestiary data."""
from sol_cesto_solver.bestiary import BESTIARY


def test_has_core_monsters():
    for key in ("slime", "hawk", "fledgling", "mimic", "fish_monster", "wizard"):
        assert key in BESTIARY


def test_relations_reference_known_keys():
    for monster in BESTIARY.values():
        for related in monster.relations:
            assert related in BESTIARY, f"{monster.key} links to unknown {related!r}"


def test_hawk_fledgling_relationship_is_bidirectional():
    assert "fledgling" in BESTIARY["hawk"].relations
    assert "hawk" in BESTIARY["fledgling"].relations


def test_specials_are_flagged():
    # A few known special monsters (have abilities / interactions).
    for key in ("hawk", "drummer", "mimic", "black_hole", "hive_monster"):
        assert BESTIARY[key].special is True
    # And a couple of plain ones.
    assert BESTIARY["slime"].special is False
    assert BESTIARY["crab"].special is False
