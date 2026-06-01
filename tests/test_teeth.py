"""Tests for the Teeth run-modifier roster."""
from sol_cesto_solver.teeth import TEETH


def test_roster_counts():
    stone = [t for t in TEETH.values() if t.statue == "stone"]
    metal = [t for t in TEETH.values() if t.statue == "metal"]
    assert len(stone) == 17
    assert len(metal) == 15  # 16 are listed; metal 6 is W.I.P. and omitted
    assert len(TEETH) == 32


def test_keys_are_formatted_and_unique():
    assert TEETH["metal1"].key == "metal1"
    assert TEETH["stone17"].key == "stone17"
    keys = [t.key for t in TEETH.values()]
    assert len(keys) == len(set(keys))


def test_metal1_is_the_kill_two_strength_weaken():
    # The user's example: "kill 2 strength monsters -> weaken the rest."
    effect = TEETH["metal1"].effects[0].lower()
    assert "2 strength" in effect
    assert "weaken" in effect


def test_every_tooth_has_at_least_one_effect():
    assert all(t.effects for t in TEETH.values())
