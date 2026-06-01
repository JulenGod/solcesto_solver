"""Save a raw screenshot of the SolCesto client area, for debugging detection.

Captures the *client* area (content only, no title bar/borders) of the game
window so you can inspect exactly what the detector sees — no grid overlay,
no chips. Windows only.

Usage:
    poetry run python scripts/grab_capture.py [output.png]   # default: debug-raw.png
"""
import ctypes
import sys
from ctypes import wintypes
from pathlib import Path

import cv2
import numpy as np
import pygetwindow as gw
from mss import mss


def main() -> int:
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("debug-raw.png")

    windows = [w for w in gw.getAllWindows() if "solcesto" in w.title.lower().replace(" ", "")]
    if not windows:
        print("SolCesto window not found — is the game open?")
        return 1

    w = windows[0]
    hwnd = w._hWnd
    rect = wintypes.RECT()
    ctypes.windll.user32.GetClientRect(hwnd, ctypes.byref(rect))
    origin = wintypes.POINT(0, 0)
    ctypes.windll.user32.ClientToScreen(hwnd, ctypes.byref(origin))
    region = {"left": origin.x, "top": origin.y, "width": rect.right, "height": rect.bottom}

    with mss() as sct:
        shot = sct.grab(region)
    cv2.imwrite(str(out), np.asarray(shot)[:, :, :3])
    print(f"saved {out} ({region['width']}x{region['height']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
