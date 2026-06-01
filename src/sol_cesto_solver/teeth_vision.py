"""Detect equipped Teeth in the top-left "mouth" of the Sol Cesto HUD.

Teeth sit in a fixed 2x6 dentition under the player's eyes. An empty slot is a
plain cream tooth; an equipped one is strongly coloured (strawberry red, magic
blue, golden, a dark metal tooth, ...). We classify each slot by how much of its
interior is *not* the cream colour: a real tooth fills ~0.9-1.0 of its interior,
while the gold panel frame and transient OS overlays only bleed in ~0.6, so a
0.70 cut separates them cleanly (validated on real captures).

Identifying *which* tooth each one is, is deferred — `read_teeth` returns the
occupied slots with `species=None` and a coarse colour hint, and the overlay
flags them as unread so they can be labelled on the fly.
"""
import cv2
import numpy as np

from .state import ToothSlot

# Mouth bounding box as fractions of the client area (calibrated on 2401x1371).
TEETH_REGION = (0.008, 0.303, 0.188, 0.407)  # x0, y0, x1, y1
TEETH_ROWS = 2
TEETH_COLS = 6
CELL_INSET = 0.22          # ignore each slot's outer border (black outline / gaps)
OCCUPIED_THRESHOLD = 0.70  # min non-cream fraction of a slot interior to be a tooth


def _cream_mask(hsv: np.ndarray) -> np.ndarray:
    """Boolean mask of the pale-cream colour of an empty tooth."""
    h, s, v = hsv[..., 0], hsv[..., 1], hsv[..., 2]
    return (h >= 18) & (h <= 40) & (s >= 10) & (s <= 110) & (v >= 170)


def _color_hint(interior_hsv: np.ndarray, noncream: np.ndarray) -> str:
    """Coarse colour name for an occupied tooth, to help label it."""
    colored = noncream & (interior_hsv[..., 1] > 60)
    pts = interior_hsv[colored]
    if pts.shape[0] < 0.05 * noncream.size:
        return "dark"  # non-cream but desaturated -> a dark/grey tooth
    hue = float(np.median(pts[:, 0]))
    if hue < 10 or hue >= 170:
        return "red"
    if hue < 22:
        return "orange"
    if hue < 33:
        return "gold"
    if hue < 85:
        return "green"
    if hue < 130:
        return "blue"
    return "purple"


def read_teeth(image: np.ndarray) -> list[ToothSlot]:
    """Return the occupied tooth slots in the mouth (empty slots are skipped)."""
    h, w = image.shape[:2]
    x0, y0, x1, y1 = (
        int(TEETH_REGION[0] * w), int(TEETH_REGION[1] * h),
        int(TEETH_REGION[2] * w), int(TEETH_REGION[3] * h),
    )
    strip = image[y0:y1, x0:x1]
    if strip.size == 0:
        return []
    hsv = cv2.cvtColor(strip, cv2.COLOR_BGR2HSV)
    sh, sw = strip.shape[:2]

    teeth: list[ToothSlot] = []
    for r in range(TEETH_ROWS):
        for c in range(TEETH_COLS):
            cx0, cx1 = int(c / TEETH_COLS * sw), int((c + 1) / TEETH_COLS * sw)
            cy0, cy1 = int(r / TEETH_ROWS * sh), int((r + 1) / TEETH_ROWS * sh)
            iw, ih = cx1 - cx0, cy1 - cy0
            ix0, ix1 = cx0 + int(CELL_INSET * iw), cx1 - int(CELL_INSET * iw)
            iy0, iy1 = cy0 + int(CELL_INSET * ih), cy1 - int(CELL_INSET * ih)
            interior = hsv[iy0:iy1, ix0:ix1]
            if interior.size == 0:
                continue
            noncream = ~_cream_mask(interior)
            if float(noncream.mean()) >= OCCUPIED_THRESHOLD:
                teeth.append(ToothSlot(row=r, col=c, color=_color_hint(interior, noncream)))
    return teeth
