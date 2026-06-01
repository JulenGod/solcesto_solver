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
from .species import identify_species
from .state import Cell, CellContent, Door, GameState, Player

TEMPLATES_DIR = Path(__file__).resolve().parents[2] / "templates"

BADGE_ICON_THRESHOLD = 0.60
# Secondary treasure cue: a chest's gold pile (bottom of the cell). Treasure piles
# score ~0.72–0.91; monsters / slimes / hover-preview bubbles score ≤0.33, so 0.55
# separates them cleanly and rescues chests whose "?" badge is too dark to match.
GOLDPILE_THRESHOLD = 0.55
DRUMMER_BUFF = 1  # a Drummer raises each horizontally-adjacent monster's shown damage by 1
DIGIT_THRESHOLD = 0.85
# Each on-screen number uses a different font, so we match each region against only
# its own font's templates (below) to avoid cross-contamination, and give the HP
# heart its own looser threshold (its two stacked "5"s vary in size with perspective).
HP_DIGIT_THRESHOLD = 0.55
STAT_DIGIT_THRESHOLD = 0.70
HUD_DIGIT_THRESHOLD = 0.76  # door "0/5" + gold counter; high enough that the bar-like
#                             "1" stops matching spuriously (e.g. a "0" mis-read as "01")

# Every template was cropped from one 2552px-wide screenshot. cv2.matchTemplate is
# NOT scale-invariant, so a capture at a different window size would fail to match.
# We rescale templates by how much the current capture differs from that source
# width, and try a few nearby scales to absorb aspect-ratio / rounding drift. This
# makes detection work at any window size or display scaling.
TEMPLATE_SOURCE_WIDTH = 2552

# Maps badge-icon template filename stem to the cell's content type.
# Multiple stems can map to the same content (useful for visual variants — e.g. a
# "sword_alt" template if the icon ever renders slightly differently).
BADGE_TO_CONTENT: dict[str, CellContent] = {
    "sword": "physical",
    "magic": "magic",
    "heart": "heal",
    "question": "treasure",
    "question_dark": "treasure",  # the "?" badge on a shadowed/darker chest
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
    # *_door / *_gold: right-panel HUD readouts — the door "0/5" and the gold counter.
    "0_door": "0", "1_door": "1", "2_door": "2", "3_door": "3", "4_door": "4",
    "5_door": "5", "6_door": "6", "7_door": "7", "8_door": "8", "9_door": "9",
    "slash_door": "/",
    "0_gold": "0", "1_gold": "1", "2_gold": "2", "3_gold": "3", "4_gold": "4",
    "5_gold": "5", "6_gold": "6", "7_gold": "7", "8_gold": "8", "9_gold": "9",
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


def _scaled(template: np.ndarray, scale: float) -> np.ndarray:
    """Resize a template by `scale` (>0). Returns the original if scale ≈ 1."""
    if abs(scale - 1.0) < 1e-3:
        return template
    h, w = template.shape[:2]
    new_w, new_h = max(1, round(w * scale)), max(1, round(h * scale))
    interp = cv2.INTER_AREA if scale < 1.0 else cv2.INTER_LINEAR
    return cv2.resize(template, (new_w, new_h), interpolation=interp)


def _scale_candidates(base_scale: float) -> tuple[float, ...]:
    """A few scales bracketing the resolution-derived `base_scale`."""
    return tuple(base_scale * f for f in (0.85, 0.92, 1.0, 1.08, 1.15))


def _best_icon(
    image: np.ndarray,
    templates: dict[str, np.ndarray],
    threshold: float,
    base_scale: float,
) -> str | None:
    """Return the highest-scoring template name above `threshold`, or None.

    Each template is matched at several scales around `base_scale`, keeping the
    best score (matchTemplate is not scale-invariant).
    """
    best_name: str | None = None
    best_score = threshold
    for name, tpl in templates.items():
        for scale in _scale_candidates(base_scale):
            scaled = _scaled(tpl, scale)
            if scaled.shape[0] > image.shape[0] or scaled.shape[1] > image.shape[1]:
                continue
            result = cv2.matchTemplate(image, scaled, cv2.TM_CCOEFF_NORMED)
            _, score, _, _ = cv2.minMaxLoc(result)
            if score > best_score:
                best_score = float(score)
                best_name = name
    return best_name


def _scan_digits(
    image: np.ndarray,
    templates: dict[str, np.ndarray],
    threshold: float,
    base_scale: float,
) -> str:
    """Find every digit/symbol match above threshold, NMS in 2D, read top-down + L-to-R.

    Each template is matched at several scales around `base_scale`. Reading order
    matters: HP on the heart is stacked vertically ("5" / "/" / "5"), while "25%"
    badges are horizontal. Sorting by (y, x) handles both.
    """
    detections: list[tuple[int, int, str, float]] = []

    for name, tpl in templates.items():
        char = SYMBOL_NAMES.get(name, name)
        for scale in _scale_candidates(base_scale):
            scaled = _scaled(tpl, scale)
            if scaled.shape[0] > image.shape[0] or scaled.shape[1] > image.shape[1]:
                continue
            result = cv2.matchTemplate(image, scaled, cv2.TM_CCOEFF_NORMED)
            ys, xs = np.where(result >= threshold)
            for y, x in zip(ys, xs, strict=False):
                detections.append((int(x), int(y), char, float(result[y, x])))

    # 2D NMS: drop weaker detections that overlap a kept one in BOTH x and y.
    # Radius scales with the capture so cross-scale duplicates collapse cleanly.
    detections.sort(key=lambda d: -d[3])
    kept: list[tuple[int, int, str]] = []
    nms_radius = max(3, round(6 * base_scale))
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
    goldpile_templates: dict[str, np.ndarray],
    digit_templates: dict[str, np.ndarray],
    base_scale: float,
) -> Cell:
    """Identify the cell by its badge icon, with the gold pile as a chest fallback.

    Scans the top half for a badge (sword/magic/heart/question) and reads the
    digit next to it. A shadowed chest can fail the "?" match, so when no badge is
    found we check the bottom half for the chest's gold pile — a robust treasure
    cue that monsters and the hover-preview bubbles don't have.
    """
    h, w = cell_image.shape[:2]

    # Badges and their "?" sparkles live in the top half of the cell.
    top_region = cell_image[: max(1, h // 2), :]

    badge_name = _best_icon(top_region, badge_icon_templates, BADGE_ICON_THRESHOLD, base_scale)
    content: CellContent = BADGE_TO_CONTENT.get(badge_name or "", "empty")

    if content == "empty" and goldpile_templates:
        bottom_region = cell_image[h // 2:, :]
        if _best_icon(bottom_region, goldpile_templates, GOLDPILE_THRESHOLD, base_scale):
            content = "treasure"

    value: int | None = None
    if content in {"physical", "magic", "heal"}:
        digit_text = _scan_digits(top_region, digit_templates, DIGIT_THRESHOLD, base_scale)
        digits = [c for c in digit_text if c.isdigit()]
        if digits:
            value = int(digits[0])

    # Best-effort species ID for monsters (badge already gives class + damage).
    species = None
    if content in {"physical", "magic"}:
        species = identify_species(cell_image, content, value)

    return Cell(content=content, value=value, species=species)


def drummer_buffed_positions(board: list[list[Cell]]) -> set[tuple[int, int]]:
    """Board positions horizontally adjacent to a Drummer (shown damage is +1)."""
    cols = len(board[0]) if board else 0
    buffed: set[tuple[int, int]] = set()
    for r, row in enumerate(board):
        for c, cell in enumerate(row):
            if cell.species == "drummer":
                for nc in (c - 1, c + 1):
                    if 0 <= nc < cols:
                        buffed.add((r, nc))
    return buffed


def recognize_board(
    image: np.ndarray,
    layout: GridLayout,
    badge_icon_templates: dict[str, np.ndarray],
    goldpile_templates: dict[str, np.ndarray],
    digit_templates: dict[str, np.ndarray],
    base_scale: float,
) -> list[list[Cell]]:
    """Recognize all 16 cells of the 4x4 board, then correct Drummer-buffed cells."""
    board = [
        [
            recognize_cell(
                layout.crop_cell(image, r, c),
                badge_icon_templates,
                goldpile_templates,
                digit_templates,
                base_scale,
            )
            for c in range(COLS)
        ]
        for r in range(ROWS)
    ]

    # Second pass: a Drummer raises its horizontal neighbours' shown damage by +1.
    # Re-identify those at their true base value and flag them; the displayed value
    # still drives the HP maths (it's what actually hits you).
    for r, c in drummer_buffed_positions(board):
        cell = board[r][c]
        if cell.content in {"physical", "magic"} and cell.value is not None:
            crop = layout.crop_cell(image, r, c)
            base_species = identify_species(crop, cell.content, cell.value - DRUMMER_BUFF)
            board[r][c] = cell.model_copy(update={"species": base_species, "buffed": True})

    return board


def recognize_player(
    image: np.ndarray,
    hp_digits: dict[str, np.ndarray],
    stat_digits: dict[str, np.ndarray],
    base_scale: float,
) -> Player:
    """Read HP, sword and magic from fixed regions of the right-side UI panel.

    HP/sword/magic detection is best-effort: it needs digit templates in the right
    font, and the side panel only fits on-screen when the whole game window is
    visible. The CLI exposes --sword/--magic/--hp/--max-hp to override these.
    """
    h, w = image.shape[:2]

    # "5/5" sits over the red heart in the top-right side panel.
    hp_region = image[int(h * 0.02):int(h * 0.22), int(w * 0.83):int(w * 0.99)]
    hp_text = _scan_digits(hp_region, hp_digits, HP_DIGIT_THRESHOLD, base_scale)
    hp_parsed = _parse_hp(hp_text)
    if hp_parsed is None:
        # The slash on the heart is tiny and diagonal, so we usually just get the two
        # digits. HP is "current/max" with current <= max, so taking (min, max) is
        # robust to the stacked digits being detected out of order.
        nums = sorted(int(c) for c in hp_text if c.isdigit())
        if len(nums) >= 2:
            hp_parsed = (nums[0], nums[-1])
    hp, max_hp = hp_parsed if hp_parsed else (0, 0)

    # Sword + magic numbers sit next to their icons in the lower-right side panel.
    stats_region = image[int(h * 0.32):int(h * 0.43), int(w * 0.88):w]
    stats_text = _scan_digits(stats_region, stat_digits, STAT_DIGIT_THRESHOLD, base_scale)
    digits = [c for c in stats_text if c.isdigit()]
    sword = int(digits[0]) if digits else 0
    magic = int(digits[1]) if len(digits) > 1 else 0

    return Player(hp=hp, max_hp=max_hp, sword=sword, magic=magic)


def _digit_subset(digits: dict[str, np.ndarray], kind: str) -> dict[str, np.ndarray]:
    """Select the templates for one font: 'badge' (cells), 'hp', or 'stat'.

    Each on-screen number uses a distinct font; matching a region only against its
    own font avoids false positives (e.g. a cell's "3" leaking into the HP read).
    """
    if kind == "hp":
        return {k: v for k, v in digits.items() if k.endswith("_hp")}
    if kind == "stat":
        return {k: v for k, v in digits.items() if k.endswith("_stat")}
    if kind == "door":
        return {k: v for k, v in digits.items() if k.endswith("_door")}
    if kind == "gold":
        return {k: v for k, v in digits.items() if k.endswith("_gold")}
    # 'badge': bare digits plus the % / / symbols on cell badges.
    return {k: v for k, v in digits.items() if k.isdigit() or k in ("percent", "slash")}


def recognize_hud(
    image: np.ndarray,
    door_digits: dict[str, np.ndarray],
    gold_digits: dict[str, np.ndarray],
    base_scale: float,
) -> tuple[int | None, Door | None]:
    """Read the gold counter and door (exit) progress from the right-side panel.

    Best-effort, like the player stats: needs the side panel on screen and digit
    templates in the HUD fonts. Returns (gold, Door|None) with None for anything
    that couldn't be read.
    """
    h, w = image.shape[:2]

    # Door "X/Y" badge: stacked vertically in the medallion on the locked door.
    door_region = image[int(h * 0.57):int(h * 0.66), int(w * 0.885):int(w * 0.918)]
    door_text = _scan_digits(door_region, door_digits, HUD_DIGIT_THRESHOLD, base_scale)
    door_nums = [c for c in door_text if c.isdigit()]
    door = None
    if door_nums:
        required = int(door_nums[-1]) if len(door_nums) >= 2 else None
        door = Door(cleared=int(door_nums[0]), required=required)

    # Gold counter on the frog's sign, lower-right; read left-to-right.
    gold_region = image[int(h * 0.86):int(h * 0.94), int(w * 0.88):int(w * 0.95)]
    gold_scan = _scan_digits(gold_region, gold_digits, HUD_DIGIT_THRESHOLD, base_scale)
    gold_text = "".join(c for c in gold_scan if c.isdigit())
    gold = int(gold_text) if gold_text else None

    return gold, door


def recognize_state(image: np.ndarray, layout: GridLayout) -> GameState:
    """Run the full detection pipeline and return a GameState."""
    icon_templates = load_templates("icons")
    # The gold pile is matched in the cell's bottom half (chest fallback), not as a
    # top-of-cell badge, so keep it out of the badge set.
    goldpile_templates = {k: v for k, v in icon_templates.items() if k == "goldpile"}
    badge_icon_templates = {k: v for k, v in icon_templates.items() if k != "goldpile"}
    digit_templates = load_templates("digits")

    # All templates came from a TEMPLATE_SOURCE_WIDTH-wide screenshot; rescale them
    # to this capture's width so matchTemplate works at any window size.
    base_scale = image.shape[1] / TEMPLATE_SOURCE_WIDTH

    gold, door = recognize_hud(
        image,
        _digit_subset(digit_templates, "door"),
        _digit_subset(digit_templates, "gold"),
        base_scale,
    )

    return GameState(
        board=recognize_board(
            image, layout, badge_icon_templates, goldpile_templates,
            _digit_subset(digit_templates, "badge"), base_scale,
        ),
        player=recognize_player(
            image,
            _digit_subset(digit_templates, "hp"),
            _digit_subset(digit_templates, "stat"),
            base_scale,
        ),
        gold=gold,
        door=door,
    )
