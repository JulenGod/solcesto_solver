"""Precompute monster reference features into data/species_refs.npz.

Reads the labelled sprites in references/monsters/ (kept local — game assets),
runs the same feature extractor the detector uses, and saves the feature matrix
+ labels. Re-run this whenever you add reference sprites or change the feature.

Usage:
    poetry run python scripts/build_species_refs.py
"""
from pathlib import Path

import cv2
import numpy as np

from sol_cesto_solver.species import REFS_FILE, species_features

ROOT = Path(__file__).resolve().parent.parent
REF_DIR = ROOT / "references" / "monsters"


def main() -> int:
    if not REF_DIR.is_dir():
        print(f"missing {REF_DIR} — download the wiki sprites there first")
        return 1

    labels, feats = [], []
    for path in sorted(REF_DIR.glob("*")):
        img = cv2.imread(str(path))
        if img is None:
            continue
        labels.append(path.stem)
        feats.append(species_features(img))

    if not labels:
        print("no reference images found")
        return 1

    REFS_FILE.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        REFS_FILE, labels=np.array(labels), features=np.array(feats, dtype=np.float32)
    )
    print(f"wrote {REFS_FILE} with {len(labels)} species")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
