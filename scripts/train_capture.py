"""Auto-collect game frames while you play, for building new templates.

Play a "training" run with this open: it grabs the game window every --interval
seconds and keeps only frames that changed meaningfully (so you get roughly one
image per distinct board / counter value, not hundreds of duplicates). Afterwards,
cut the new digit templates from captures/ with scripts/extract_templates.py
(use the 'f' key there to tag the gold / door / hp / stat font).

This is the practical way to widen digit coverage: a single screenshot only ever
shows a few values, but a whole run scrolls through many gold amounts, door
progress steps, HP totals, and monster strengths.

Usage:
    poetry run python scripts/train_capture.py
    poetry run python scripts/train_capture.py --interval 1.0 --max-frames 200
"""
import argparse
import time
from pathlib import Path

import cv2
import numpy as np

from sol_cesto_solver.capture import CaptureError, capture, find_window
from sol_cesto_solver.overlay import enable_dpi_awareness

ROOT = Path(__file__).resolve().parent.parent


def _changed(prev: np.ndarray | None, frame: np.ndarray, threshold: float) -> bool:
    """True if `frame` differs enough from `prev` to be worth saving."""
    if prev is None or prev.shape != frame.shape:
        return True
    return float(np.mean(cv2.absdiff(prev, frame))) > threshold


def main() -> int:
    parser = argparse.ArgumentParser(description="Collect changed game frames while you play.")
    parser.add_argument("--window", default="Sol Cesto", help="Game window title substring.")
    parser.add_argument("--interval", type=float, default=1.5, help="Seconds between grabs.")
    parser.add_argument(
        "--max-frames", type=int, default=0, help="Stop after N frames (0 = until Ctrl-C)."
    )
    parser.add_argument(
        "--min-change", type=float, default=3.0,
        help="Mean per-pixel difference needed to treat a frame as new.",
    )
    parser.add_argument("--out", default=str(ROOT / "captures"), help="Output directory.")
    args = parser.parse_args()

    enable_dpi_awareness()  # capture physical pixels on scaled displays
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    existing = len(list(out.glob("capture_*.png")))
    print(f"capturing to {out} every {args.interval}s (Ctrl-C to stop)")

    saved = 0
    prev: np.ndarray | None = None
    try:
        while args.max_frames == 0 or saved < args.max_frames:
            try:
                frame = capture(find_window(args.window))
            except CaptureError as e:
                print(f"  waiting for game window… ({e})")
                time.sleep(args.interval)
                continue
            if _changed(prev, frame, args.min_change):
                path = out / f"capture_{existing + saved:04d}.png"
                cv2.imwrite(str(path), frame)
                prev = frame
                saved += 1
                print(f"  saved {path.name}  (new this run: {saved})")
            time.sleep(args.interval)
    except KeyboardInterrupt:
        pass

    print(f"done — saved {saved} new frame(s) to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
