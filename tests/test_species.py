"""Tests for the species-identification prefilter logic (image-free)."""
from sol_cesto_solver.species import _damage_matches, candidate_species


def test_damage_matches_exact_and_variants():
    assert _damage_matches("3", 3)
    assert not _damage_matches("3", 2)
    assert _damage_matches("3+", 4)      # "3 or more"
    assert not _damage_matches("3+", 2)
    assert _damage_matches("1/4", 1)     # swaps between 1 and 4
    assert _damage_matches("1/4", 4)
    assert not _damage_matches("1/4", 2)
    assert _damage_matches("3", None)    # unknown value -> don't exclude


def test_candidates_exclude_traps():
    for content in ("physical", "magic"):
        cands = candidate_species(content, 1)
        assert "spikes" not in cands
        assert "clam" not in cands


def test_magic_one_resolves_to_slime_only():
    # Only the Slime is magic with damage 1, so the prefilter alone identifies it.
    assert candidate_species("magic", 1) == ["slime"]


def test_physical_three_includes_the_imp_and_excludes_magic_monsters():
    cands = candidate_species("physical", 3)
    assert "red_coyote" in cands       # the pink imp (strength 3)
    assert "slime" not in cands        # magic monster, wrong class
    assert "living_book" not in cands  # magic
