"""Bootstrap icon templates from screenshot.png by cropping known cell positions.

Convenience helper for first-time setup: extracts a starter set of icon templates
from the bundled `screenshot.png`, using hand-picked cells where each icon appears
cleanly (no overlays). Lets you run `sol-cesto-solver --from-file screenshot.png`
and see real recognition without going through the interactive extractor first.

For digits and any icons not covered here, use:
    poetry run python scripts/extract_templates.py screenshot.png
"""
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
TEMPLATES = ROOT / "templates"
SCREENSHOT = ROOT / "screenshot.png"

# Keep in sync with src/sol_cesto_solver/grid.py
LEFT_RATIO = 0.215
TOP_RATIO = 0.03
BOARD_W_RATIO = 0.57
BOARD_H_RATIO = 0.94


def _crop_cell_region(
    image: np.ndarray,
    row: int,
    col: int,
    x0: float,
    y0: float,
    x1: float,
    y1: float,
) -> np.ndarray:
    """Crop a sub-region of cell (row, col), using fractional coords inside the cell."""
    h, w = image.shape[:2]
    bx = int(w * LEFT_RATIO)
    by = int(h * TOP_RATIO)
    bw = int(w * BOARD_W_RATIO)
    bh = int(h * BOARD_H_RATIO)
    cw = bw // 4
    ch = bh // 4
    cx = bx + col * cw
    cy = by + row * ch
    return image[cy + int(ch * y0):cy + int(ch * y1), cx + int(cw * x0):cx + int(cw * x1)].copy()


def _crop_image_region(
    image: np.ndarray,
    x0: float,
    y0: float,
    x1: float,
    y1: float,
) -> np.ndarray:
    """Crop a sub-region of the full image using fractional image coords."""
    h, w = image.shape[:2]
    return image[int(h * y0):int(h * y1), int(w * x0):int(w * x1)].copy()


def _save(image: np.ndarray, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(path), image)
    print(f"  {path.relative_to(ROOT)}  ({image.shape[1]}x{image.shape[0]})")


def main() -> int:
    if not SCREENSHOT.exists():
        print(f"missing {SCREENSHOT}")
        return 1
    img = cv2.imread(str(SCREENSHOT))
    if img is None:
        print(f"could not read {SCREENSHOT}")
        return 1

    print("extracting badge-icon templates from screenshot.png:")
    # Tight crops on JUST the coloured icon (not the gray badge background).
    # The gray bg is identical across all badges and would dominate the match
    # score, drowning out the red-vs-blue colour signal that distinguishes
    # physical from magic.
    #
    # Red sword icon, from row 0 col 0. Coords cover the curved blade only.
    _save(
        _crop_cell_region(img, 0, 0, 0.14, 0.17, 0.30, 0.30),
        TEMPLATES / "icons" / "sword.png",
    )
    # Blue magic wand, from row 0 col 1.
    _save(
        _crop_cell_region(img, 0, 1, 0.14, 0.17, 0.30, 0.30),
        TEMPLATES / "icons" / "magic.png",
    )
    # Red heart from strawberry badge (row 2 col 0).
    _save(
        _crop_cell_region(img, 2, 0, 0.13, 0.19, 0.24, 0.30),
        TEMPLATES / "icons" / "heart.png",
    )
    # Gold "?" sparkle from a treasure cell (closed chest, row 0 col 3).
    # The sparkle sits in the top-LEFT of the cell, same area as the standard badge.
    _save(
        _crop_cell_region(img, 0, 3, 0.02, 0.12, 0.22, 0.32),
        TEMPLATES / "icons" / "question.png",
    )

    print()
    print("extracting digit templates from screenshot.png:")
    # "3" digit alone — from sword badge top-left of monster cell row 0 col 0.
    _save(
        _crop_cell_region(img, 0, 0, 0.24, 0.07, 0.34, 0.21),
        TEMPLATES / "digits" / "3.png",
    )
    # "1" digit alone — from magic badge top-left of slime cell row 0 col 1.
    _save(
        _crop_cell_region(img, 0, 1, 0.24, 0.07, 0.34, 0.21),
        TEMPLATES / "digits" / "1.png",
    )
    # "2", "5", "%" — from the "25%" badge top-right of preview row 1 col 0.
    _save(
        _crop_cell_region(img, 1, 0, 0.76, 0.08, 0.84, 0.21),
        TEMPLATES / "digits" / "2.png",
    )
    _save(
        _crop_cell_region(img, 1, 0, 0.83, 0.08, 0.91, 0.21),
        TEMPLATES / "digits" / "5.png",
    )
    _save(
        _crop_cell_region(img, 1, 0, 0.90, 0.08, 0.99, 0.21),
        TEMPLATES / "digits" / "percent.png",
    )
    # The HP "5/5" on the red heart uses a chunkier font than the small "25%" badge.
    # We extract one "5_hp" — the same template matches both 5s. The slash between
    # them is tiny and diagonal, so we don't try to template-match it: recognition.py
    # falls back to "first digit / last digit" when no "/" is found in the hp region.
    _save(
        _crop_image_region(img, 0.850, 0.040, 0.871, 0.080),
        TEMPLATES / "digits" / "5_hp.png",
    )

    # Sword "2" and magic "1" from the stat bar (large stylised font). Mapped via
    # "_stat" suffix.
    _save(
        _crop_image_region(img, 0.927, 0.345, 0.952, 0.395),
        TEMPLATES / "digits" / "2_stat.png",
    )
    _save(
        _crop_image_region(img, 0.965, 0.345, 0.990, 0.395),
        TEMPLATES / "digits" / "1_stat.png",
    )

    print()
    print("done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
