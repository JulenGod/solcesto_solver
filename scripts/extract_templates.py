"""Interactive helper to cut icon and digit templates from a Sol Cesto frame.

Usage:
    poetry run python scripts/extract_templates.py <frame.png>

Controls (inside the window):
    * Click-drag   select a rectangle (drawn in green).
    * 'f'          cycle the digit FONT: badge -> hp -> stat -> door -> gold.
    * 0-9          save the crop as that digit in the active font
                   (badge -> N.png, otherwise -> N_<font>.png).
    * 'p' / 'l'    save the crop as percent / slash in the active font.
    * 'i'          prompt (in the terminal) for an icon name -> templates/icons/<name>.png.
    * ESC          quit.

Why the font matters: each on-screen number uses a different font, and template
matching isn't font-agnostic. Saving a gold digit as e.g. 7_gold.png is what lets
the detector read the frog's gold counter; 1_door.png feeds the door "X/5" badge.
Pair this with scripts/train_capture.py, which collects frames while you play.
"""
import sys
from pathlib import Path

import cv2

ROOT = Path(__file__).resolve().parent.parent
TEMPLATES = ROOT / "templates"

# Must match the suffixes recognised by SYMBOL_NAMES / _digit_subset in recognition.py.
FONTS = ("badge", "hp", "stat", "door", "gold")


def _suffix(name: str, font: str) -> str:
    """badge keeps the bare name (e.g. '7'); other fonts get a suffix ('7_gold')."""
    return name if font == "badge" else f"{name}_{font}"


def _save_crop(image, start, end, path: Path) -> bool:
    if start is None or end is None:
        print("no selection")
        return False
    x1, y1 = min(start[0], end[0]), min(start[1], end[1])
    x2, y2 = max(start[0], end[0]), max(start[1], end[1])
    if x2 - x1 < 2 or y2 - y1 < 2:
        print("selection too small")
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(path), image[y1:y2, x1:x2])
    print(f"saved {path.relative_to(ROOT)}")
    return True


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 1

    image = cv2.imread(str(Path(sys.argv[1])))
    if image is None:
        print(f"could not read {sys.argv[1]}")
        return 1

    state = {"start": None, "end": None, "drawing": False, "font_idx": 0}

    def on_mouse(event, x, y, _flags, _param):
        if event == cv2.EVENT_LBUTTONDOWN:
            state["start"], state["end"], state["drawing"] = (x, y), (x, y), True
        elif event == cv2.EVENT_MOUSEMOVE and state["drawing"]:
            state["end"] = (x, y)
        elif event == cv2.EVENT_LBUTTONUP:
            state["end"], state["drawing"] = (x, y), False

    window = "extract"

    def refresh_title() -> None:
        font = FONTS[state["font_idx"]]
        controls = "f=font  0-9=digit  p=%  l=/  i=icon  ESC=quit"
        cv2.setWindowTitle(window, f"extract  [font: {font}]  {controls}")

    cv2.namedWindow(window, cv2.WINDOW_NORMAL)
    cv2.setMouseCallback(window, on_mouse)
    refresh_title()

    while True:
        display = image.copy()
        if state["start"] and state["end"]:
            cv2.rectangle(display, state["start"], state["end"], (0, 255, 0), 2)
        cv2.imshow(window, display)

        key = cv2.waitKey(20) & 0xFF
        if key == 27:  # ESC
            break
        if key == 255:
            continue

        ch = chr(key)
        font = FONTS[state["font_idx"]]
        if ch == "f":
            state["font_idx"] = (state["font_idx"] + 1) % len(FONTS)
            refresh_title()
            print(f"font -> {FONTS[state['font_idx']]}")
        elif ch.isdigit():
            _save_crop(image, state["start"], state["end"],
                       TEMPLATES / "digits" / f"{_suffix(ch, font)}.png")
        elif ch == "p":
            _save_crop(image, state["start"], state["end"],
                       TEMPLATES / "digits" / f"{_suffix('percent', font)}.png")
        elif ch == "l":
            _save_crop(image, state["start"], state["end"],
                       TEMPLATES / "digits" / f"{_suffix('slash', font)}.png")
        elif ch == "i":
            cv2.destroyWindow(window)
            name = input("icon name (e.g. sword, magic, heart, question): ").strip()
            cv2.namedWindow(window, cv2.WINDOW_NORMAL)
            cv2.setMouseCallback(window, on_mouse)
            refresh_title()
            if name:
                _save_crop(image, state["start"], state["end"], TEMPLATES / "icons" / f"{name}.png")

    cv2.destroyAllWindows()
    return 0


if __name__ == "__main__":
    sys.exit(main())
