"""Interactive helper to extract icon and digit templates from a Sol Cesto screenshot.

Usage:
    poetry run python scripts/extract_templates.py <screenshot.png>

Controls inside the OpenCV window:
    * Click and drag to select a rectangle (drawn in green).
    * Press a digit 0-9 -> saves the crop as templates/digits/<digit>.png
    * Press 'p'         -> saves as templates/digits/percent.png  (for "%")
    * Press 'l'         -> saves as templates/digits/slash.png    (for "/")
    * Press 'i'         -> terminal prompts for an icon name, saves to templates/icons/<name>.png
    * Press ESC         -> quit.
"""
import sys
from pathlib import Path

import cv2

ROOT = Path(__file__).resolve().parent.parent
TEMPLATES = ROOT / "templates"


def _save_crop(image, start, end, path: Path) -> bool:
    if start is None or end is None:
        print("no selection")
        return False
    x1, y1 = min(start[0], end[0]), min(start[1], end[1])
    x2, y2 = max(start[0], end[0]), max(start[1], end[1])
    if x2 - x1 < 2 or y2 - y1 < 2:
        print("selection too small")
        return False
    crop = image[y1:y2, x1:x2]
    path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(path), crop)
    print(f"saved {path.relative_to(ROOT)}")
    return True


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 1

    image_path = Path(sys.argv[1])
    image = cv2.imread(str(image_path))
    if image is None:
        print(f"could not read {image_path}")
        return 1

    state = {"start": None, "end": None, "drawing": False}

    def on_mouse(event, x, y, _flags, _param):
        if event == cv2.EVENT_LBUTTONDOWN:
            state["start"] = (x, y)
            state["end"] = (x, y)
            state["drawing"] = True
        elif event == cv2.EVENT_MOUSEMOVE and state["drawing"]:
            state["end"] = (x, y)
        elif event == cv2.EVENT_LBUTTONUP:
            state["end"] = (x, y)
            state["drawing"] = False

    window = "extract templates  (0-9 digit | p % | l / | i icon | ESC quit)"
    cv2.namedWindow(window, cv2.WINDOW_NORMAL)
    cv2.setMouseCallback(window, on_mouse)

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
        if ch.isdigit():
            _save_crop(image, state["start"], state["end"], TEMPLATES / "digits" / f"{ch}.png")
        elif ch == "p":
            _save_crop(image, state["start"], state["end"], TEMPLATES / "digits" / "percent.png")
        elif ch == "l":
            _save_crop(image, state["start"], state["end"], TEMPLATES / "digits" / "slash.png")
        elif ch == "i":
            cv2.destroyWindow(window)
            name = input("icon name (e.g. slime, monster, chest, strawberry, gold): ").strip()
            cv2.namedWindow(window, cv2.WINDOW_NORMAL)
            cv2.setMouseCallback(window, on_mouse)
            if name:
                _save_crop(image, state["start"], state["end"], TEMPLATES / "icons" / f"{name}.png")

    cv2.destroyAllWindows()
    return 0


if __name__ == "__main__":
    sys.exit(main())
