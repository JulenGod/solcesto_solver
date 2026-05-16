"""Template matching for badge icons and digits.

We don't template-match the creature sprites — they animate (different frames at
different times) and there are many monster variants. Instead we match the
**badge icons** that overlay the corner of each cell: red sword, blue wand,
red heart, gold "?". These are static UI elements and are identical across all
monster types of the same attack class.
"""
from functools import cache
from pathlib import Path

import cv2
import numpy as np

from .grid import COLS, ROWS, GridLayout
from .state import Cell, CellContent, GameState, Player

TEMPLATES_DIR = Path(__file__).resolve().parents[2] / "templates"

BADGE_ICON_THRESHOLD = 0.60
DIGIT_THRESHOLD = 0.85
# HP digits on the heart vary in size between the two "5"s (perspective styling),
# so the lower one often matches the upper-extracted template at ~0.65–0.70.
# Looser threshold is safe here because the HP region contains only digits and "/".
HP_DIGIT_THRESHOLD = 0.60

# Maps badge-icon template filename stem to the cell's content type.
# Multiple stems can map to the same content (useful for visual variants — e.g. a
# "sword_alt" template if the icon ever renders slightly differently).
BADGE_TO_CONTENT: dict[str, CellContent] = {
    "sword": "physical",
    "magic": "magic",
    "heart": "heal",
    "question": "treasure",
}

# Digit templates whose stems aren't directly usable as characters.
# Multiple stems can map to the same character — useful when the same digit is
# rendered differently in the badges (small white on dark) vs the HP heart (chunky
# light-on-red). Add new variant templates without breaking existing ones.
SYMBOL_NAMES = {
    "percent": "%",
    "slash": "/",
    "slash_hp": "/",
    # *_hp variants: chunky font used on the HP heart ("5/5").
    "0_hp": "0", "1_hp": "1", "2_hp": "2", "3_hp": "3", "4_hp": "4",
    "5_hp": "5", "6_hp": "6", "7_hp": "7", "8_hp": "8", "9_hp": "9",
    # *_stat variants: large stylised font next to the sword and magic icons.
    "0_stat": "0", "1_stat": "1", "2_stat": "2", "3_stat": "3", "4_stat": "4",
    "5_stat": "5", "6_stat": "6", "7_stat": "7", "8_stat": "8", "9_stat": "9",
}


@cache
def load_templates(subdir: str) -> dict[str, np.ndarray]:
    """Load all PNGs from `templates/<subdir>/`. Cached after first call."""
    folder = TEMPLATES_DIR / subdir
    templates: dict[str, np.ndarray] = {}
    if not folder.is_dir():
        return templates
    for png in folder.glob("*.png"):
        img = cv2.imread(str(png), cv2.IMREAD_COLOR)
        if img is not None and img.size > 0:
            templates[png.stem] = img
    return templates


def _best_icon(
    image: np.ndarray,
    templates: dict[str, np.ndarray],
    threshold: float,
) -> str | None:
    """Return the highest-scoring template name above `threshold`, or None."""
    best_name: str | None = None
    best_score = threshold
    for name, tpl in templates.items():
        if tpl.shape[0] > image.shape[0] or tpl.shape[1] > image.shape[1]:
            continue
        result = cv2.matchTemplate(image, tpl, cv2.TM_CCOEFF_NORMED)
        _, score, _, _ = cv2.minMaxLoc(result)
        if score > best_score:
            best_score = float(score)
            best_name = name
    return best_name


def _scan_digits(
    image: np.ndarray,
    templates: dict[str, np.ndarray],
    threshold: float,
) -> str:
    """Find every digit/symbol match above threshold, NMS in 2D, read top-down + L-to-R.

    Reading order matters: HP on the heart is stacked vertically ("5" / "/" / "5"),
    while "25%" badges are laid out horizontally. Sorting by (y, x) gets both right:
    digits at very different y values are read top-to-bottom; digits at the same y
    fall back to left-to-right.
    """
    detections: list[tuple[int, int, str, float]] = []

    for name, tpl in templates.items():
        if tpl.shape[0] > image.shape[0] or tpl.shape[1] > image.shape[1]:
            continue
        result = cv2.matchTemplate(image, tpl, cv2.TM_CCOEFF_NORMED)
        ys, xs = np.where(result >= threshold)
        char = SYMBOL_NAMES.get(name, name)
        for y, x in zip(ys, xs, strict=False):
            detections.append((int(x), int(y), char, float(result[y, x])))

    # 2D NMS: drop weaker detections that overlap a kept one in BOTH x and y.
    detections.sort(key=lambda d: -d[3])
    kept: list[tuple[int, int, str]] = []
    nms_radius = 6
    for x, y, ch, _ in detections:
        if all(abs(x - kx) > nms_radius or abs(y - ky) > nms_radius for kx, ky, _ in kept):
            kept.append((x, y, ch))

    kept.sort(key=lambda k: (k[1], k[0]))
    return "".join(ch for _, _, ch in kept)


def _parse_int(s: str) -> int | None:
    try:
        return int(s)
    except (ValueError, TypeError):
        return None


def _parse_hp(s: str) -> tuple[int, int] | None:
    if "/" not in s:
        return None
    parts = s.split("/", 1)
    a, b = _parse_int(parts[0]), _parse_int(parts[1])
    if a is None or b is None:
        return None
    return (a, b)


def recognize_cell(
    cell_image: np.ndarray,
    badge_icon_templates: dict[str, np.ndarray],
    digit_templates: dict[str, np.ndarray],
) -> Cell:
    """Identify the cell by which badge icon overlays it.

    Scans the top half of the cell for a badge icon (sword/magic/heart/question),
    then reads the digit next to it. The creature sprite below is ignored entirely.
    """
    h, w = cell_image.shape[:2]

    # Badges and their "?" sparkles live in the top half of the cell.
    top_region = cell_image[: max(1, h // 2), :]

    badge_name = _best_icon(top_region, badge_icon_templates, BADGE_ICON_THRESHOLD)
    content: CellContent = BADGE_TO_CONTENT.get(badge_name or "", "empty")

    value: int | None = None
    if content in {"physical", "magic", "heal"}:
        digit_text = _scan_digits(top_region, digit_templates, DIGIT_THRESHOLD)
        digits = [c for c in digit_text if c.isdigit()]
        if digits:
            value = int(digits[0])

    return Cell(content=content, value=value)


def recognize_board(
    image: np.ndarray,
    layout: GridLayout,
    badge_icon_templates: dict[str, np.ndarray],
    digit_templates: dict[str, np.ndarray],
) -> list[list[Cell]]:
    """Recognize all 16 cells of the 4x4 board."""
    return [
        [
            recognize_cell(
                layout.crop_cell(image, r, c),
                badge_icon_templates,
                digit_templates,
            )
            for c in range(COLS)
        ]
        for r in range(ROWS)
    ]


def recognize_player(image: np.ndarray, digit_templates: dict[str, np.ndarray]) -> Player:
    """Read HP, sword and magic from fixed regions of the right-side UI panel."""
    h, w = image.shape[:2]

    # "5/5" sits over the red heart in the top-right side panel.
    hp_region = image[int(h * 0.02):int(h * 0.20), int(w * 0.83):int(w * 0.95)]
    hp_text = _scan_digits(hp_region, digit_templates, HP_DIGIT_THRESHOLD)
    hp_parsed = _parse_hp(hp_text)
    if hp_parsed is None:
        # The slash on the heart is tiny and diagonal — easy to miss. If we have at
        # least two digits, assume current = first, max = last.
        hp_digits = [c for c in hp_text if c.isdigit()]
        if len(hp_digits) >= 2:
            hp_parsed = (int(hp_digits[0]), int(hp_digits[-1]))
    hp, max_hp = hp_parsed if hp_parsed else (0, 0)

    # Sword + magic numbers sit on a thin horizontal stat bar above the dungeon door,
    # on the very right edge of the side panel.
    stats_region = image[int(h * 0.34):int(h * 0.40), int(w * 0.92):int(w * 0.99)]
    stats_text = _scan_digits(stats_region, digit_templates, DIGIT_THRESHOLD)
    digits = [c for c in stats_text if c.isdigit()]
    sword = int(digits[0]) if digits else 0
    magic = int(digits[1]) if len(digits) > 1 else 0

    return Player(hp=hp, max_hp=max_hp, sword=sword, magic=magic)


def recognize_state(image: np.ndarray, layout: GridLayout) -> GameState:
    """Run the full detection pipeline and return a GameState."""
    badge_icon_templates = load_templates("icons")
    digit_templates = load_templates("digits")

    return GameState(
        board=recognize_board(image, layout, badge_icon_templates, digit_templates),
        player=recognize_player(image, digit_templates),
    )
