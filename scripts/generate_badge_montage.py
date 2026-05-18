"""Generate `docs/badges.png` — a 2x2 montage of the four badge types.

The image is intended for social media / the README to make the central design
choice (classify by static badge, not by animated sprite) visually obvious in
one glance. Each badge close-up sits above a colour-coded label band matching
the chip colour used in the debug overlay.

Re-run after you tweak the screenshot or want to regenerate at a different
resolution.
"""
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
SCREENSHOT = ROOT / "tests" / "fixtures" / "screenshot.png"
OUTPUT = ROOT / "docs" / "badges.png"

# Same proportions as src/sol_cesto_solver/grid.py
LEFT_RATIO = 0.215
TOP_RATIO = 0.03
BOARD_W_RATIO = 0.57
BOARD_H_RATIO = 0.94

# Each badge sits in the top-left of its cell. These cell-relative coords
# capture the gray badge background plus the digit, with a little padding.
BADGE_X0, BADGE_Y0, BADGE_X1, BADGE_Y1 = 0.02, 0.03, 0.40, 0.28

# Match the chip colours used in src/sol_cesto_solver/grid.py
COLORS = {
    "physical": (40, 40, 220),
    "magic":    (220, 80, 40),
    "heal":     (140, 80, 220),
    "treasure": (40, 200, 220),
}

# (label, (row, col_in_board)) for each badge sample.
BADGES = [
    ("physical", (0, 0)),
    ("magic",    (0, 1)),
    ("heal",     (2, 0)),
    ("treasure", (0, 3)),
]


def _cell_crop(img: np.ndarray, row: int, col: int) -> np.ndarray:
    h, w = img.shape[:2]
    bx = int(w * LEFT_RATIO)
    by = int(h * TOP_RATIO)
    bw = int(w * BOARD_W_RATIO)
    bh = int(h * BOARD_H_RATIO)
    cw = bw // 4
    ch = bh // 4
    cx = bx + col * cw
    cy = by + row * ch
    return img[
        cy + int(ch * BADGE_Y0):cy + int(ch * BADGE_Y1),
        cx + int(cw * BADGE_X0):cx + int(cw * BADGE_X1),
    ].copy()


def main() -> int:
    if not SCREENSHOT.exists():
        print(f"missing {SCREENSHOT}")
        return 1
    img = cv2.imread(str(SCREENSHOT))

    # Crop each badge and resize to a common, generous size for sharpness.
    common_w, common_h = 580, 360
    crops = []
    for label, (r, c) in BADGES:
        crop = _cell_crop(img, r, c)
        resized = cv2.resize(crop, (common_w, common_h), interpolation=cv2.INTER_LANCZOS4)
        crops.append((label, resized, COLORS[label]))

    # Lay out 2x2 with padding, dark bg, colour band + centred label below each.
    pad = 60
    band_h = 18
    label_h = 100
    tile_h = common_h + band_h + label_h
    canvas_w = common_w * 2 + pad * 3
    canvas_h = tile_h * 2 + pad * 3
    canvas = np.full((canvas_h, canvas_w, 3), 28, dtype=np.uint8)

    positions = [
        (pad, pad),
        (pad + common_w + pad, pad),
        (pad, pad + tile_h + pad),
        (pad + common_w + pad, pad + tile_h + pad),
    ]

    for (x, y), (label, crop_img, bg) in zip(positions, crops, strict=False):
        # Crop
        canvas[y:y + common_h, x:x + common_w] = crop_img

        # Colour band below
        cv2.rectangle(
            canvas,
            (x, y + common_h),
            (x + common_w, y + common_h + band_h),
            bg,
            -1,
        )

        # Centred label
        font_scale = 1.7
        font_thickness = 3
        (tw, th), _ = cv2.getTextSize(
            label, cv2.FONT_HERSHEY_SIMPLEX, font_scale, font_thickness
        )
        text_x = x + (common_w - tw) // 2
        text_y = y + common_h + band_h + th + 24
        cv2.putText(
            canvas,
            label,
            (text_x, text_y),
            cv2.FONT_HERSHEY_SIMPLEX,
            font_scale,
            (255, 255, 255),
            font_thickness,
            cv2.LINE_AA,
        )

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(OUTPUT), canvas)
    print(f"wrote {OUTPUT.relative_to(ROOT)}  ({canvas.shape[1]}x{canvas.shape[0]})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
