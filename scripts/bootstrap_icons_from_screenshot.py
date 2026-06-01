"""Seed the templates/ directory from the bundled sample screenshot.

One-time convenience for first-time setup: extracts a starter set of icon and
digit templates from `tests/fixtures/screenshot.png` so you can run
`sol-cesto-solver --from-file tests/fixtures/screenshot.png` and see real
recognition immediately, without going through the interactive extractor first.

WARNING: the cell-relative coordinates hard-coded below are calibrated for the
specific bundled fixture (resolution 2552x1427, game v2026-04). For a different
screenshot (different resolution, different game version, new content types),
use the interactive extractor instead:

    poetry run python scripts/extract_templates.py path/to/your/screenshot.png

Usage:
    poetry run python scripts/bootstrap_icons_from_screenshot.py
    poetry run python scripts/bootstrap_icons_from_screenshot.py path/to/alt.png
"""
import sys
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
TEMPLATES = ROOT / "templates"
DEFAULT_SCREENSHOT = ROOT / "tests" / "fixtures" / "screenshot.png"

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
    screenshot = Path(sys.argv[1]) if len(sys.argv) >= 2 else DEFAULT_SCREENSHOT
    if not screenshot.exists():
        print(f"missing {screenshot}")
        return 1
    img = cv2.imread(str(screenshot))
    if img is None:
        print(f"could not read {screenshot}")
        return 1

    print(f"extracting badge-icon templates from {screenshot.name}:")
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
    print(f"extracting digit templates from {screenshot.name}:")
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
    print(f"extracting HUD templates from {screenshot.name}:")
    # Door medallion digits ("0" and "5" of the "0/5" exit badge) and the frog's
    # gold "0". The slash isn't templated — the X/Y parse uses first/last digit.
    # Add other values with extract_templates.py as they appear in play (save them
    # as e.g. 1_door.png, 7_gold.png).
    _save(
        _crop_image_region(img, 0.899, 0.589, 0.909, 0.607),
        TEMPLATES / "digits" / "0_door.png",
    )
    _save(
        _crop_image_region(img, 0.897, 0.604, 0.910, 0.633),
        TEMPLATES / "digits" / "5_door.png",
    )
    _save(
        _crop_image_region(img, 0.900, 0.890, 0.9115, 0.908),
        TEMPLATES / "digits" / "0_gold.png",
    )

    print()
    print("done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
