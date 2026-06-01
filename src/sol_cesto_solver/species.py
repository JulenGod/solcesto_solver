"""Best-effort monster species identification (classic features + kNN).

The badge already tells us the attack class (physical/magic) and damage; that
narrows the candidate species a lot (often to one). Among the candidates we pick
the nearest reference sprite by a simple color+shape feature — no ML dependency.

A distance gate keeps it honest: on a settled board the right species scores a
low distance, but mid-animation / transition frames score high, so we return
None ("unknown") rather than guess. Reference features are precomputed from the
wiki sprites into data/species_refs.npz (see scripts/build_species_refs.py); the
raw sprites themselves are kept out of the repo (game assets).
"""
import re
from functools import cache
from pathlib import Path

import cv2
import numpy as np

from .bestiary import BESTIARY

REFS_FILE = Path(__file__).resolve().parent / "data" / "species_refs.npz"

# Traps aren't attackers, so a physical/magic badge cell is never one of these.
TRAPS = {"spikes", "poisonous_mushroom", "clam", "toxic_strawberry"}

# Above this feature distance the match is too weak to trust (e.g. an animating
# tile), so we report the species as unknown instead of guessing.
SPECIES_MAX_DISTANCE = 1.1


def species_features(cell_bgr: np.ndarray) -> np.ndarray:
    """Color (HSV histogram) + coarse shape of a cell's creature region.

    The top ~30% (the badge bubble) is dropped so it doesn't dominate; colour is
    weighted over shape since the monsters are strongly colour-coded.
    """
    h = cell_bgr.shape[0]
    crop = cell_bgr[int(h * 0.30):, :]
    crop = cv2.resize(crop, (64, 64))
    hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
    hist = cv2.calcHist([hsv], [0, 1], None, [12, 8], [0, 180, 0, 256])
    hist = cv2.normalize(hist, hist).flatten()
    gray = cv2.resize(cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY), (16, 16)).flatten().astype(np.float32)
    gray /= np.linalg.norm(gray) + 1e-6
    return np.concatenate([hist * 2.0, gray * 0.5])


def _damage_matches(damage: str, value: int | None) -> bool:
    if value is None:
        return True
    nums = {int(x) for x in re.findall(r"\d+", damage)}
    if not nums:
        return True
    if damage.endswith("+"):
        return value >= min(nums)
    return value in nums


def candidate_species(content: str, value: int | None) -> list[str]:
    """Monster keys whose attack class and damage are consistent with the badge."""
    want = {"physical": "strength", "magic": "magic"}.get(content)
    out = []
    for key, m in BESTIARY.items():
        if key in TRAPS:
            continue
        if m.attack != "varies" and want and m.attack != want:
            continue
        if not _damage_matches(m.damage, value):
            continue
        out.append(key)
    return out


@cache
def _load_refs() -> tuple[list[str], np.ndarray]:
    if not REFS_FILE.exists():
        return [], np.empty((0, 0), dtype=np.float32)
    data = np.load(REFS_FILE, allow_pickle=False)
    return list(data["labels"]), data["features"]


def identify_species(cell_bgr: np.ndarray, content: str, value: int | None) -> str | None:
    """Nearest candidate species for a cell, or None if too uncertain / no refs."""
    labels, features = _load_refs()
    if not labels:
        return None
    candidates = set(candidate_species(content, value))
    feat = species_features(cell_bgr)

    best_key, best_dist = None, SPECIES_MAX_DISTANCE
    for label, ref in zip(labels, features, strict=True):
        if candidates and label not in candidates:
            continue
        dist = float(np.linalg.norm(feat - ref))
        if dist < best_dist:
            best_dist, best_key = dist, label
    return best_key
