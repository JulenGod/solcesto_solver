"""Command-line interface: capture -> recognize -> recommend -> print JSON."""
import argparse
import json
import sys
import time
from pathlib import Path

import cv2
import numpy as np

from .capture import CaptureError, ImageReadError, capture, find_window
from .decision import recommend_row
from .grid import detect_board, load_calibration, save_calibration, save_debug_overlay
from .recognition import recognize_state


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="sol-cesto-solver",
        description="Detect Sol Cesto game state from the live game window.",
    )
    parser.add_argument(
        "--window",
        default="Sol Cesto",
        help="Game window title to find; case- and space-insensitive substring "
        "(default: %(default)s).",
    )
    parser.add_argument(
        "--watch",
        type=float,
        metavar="SECONDS",
        help="Re-capture every SECONDS instead of running once.",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Save debug-grid.png alongside the JSON output, with the grid overlaid.",
    )
    parser.add_argument(
        "--from-file",
        type=Path,
        metavar="PNG",
        help="Load a PNG instead of capturing the live window.",
    )
    parser.add_argument(
        "--mimic-chance",
        type=float,
        default=0.0,
        metavar="P",
        help=(
            "Probability that a chest is actually a mimic (0.0-1.0). Treasure cells "
            "get penalised in the row-recommendation accordingly. Default 0 (early "
            "levels). Raise on later levels where mimics start appearing."
        ),
    )
    parser.add_argument(
        "--overlay",
        action="store_true",
        help=(
            "Show a live, click-through overlay on top of the game that frames the "
            "board and highlights the recommended row. Windows only; the game must "
            "run windowed / borderless (not exclusive fullscreen). Ctrl-C to stop."
        ),
    )
    return parser


def _grab_image(args: argparse.Namespace) -> np.ndarray:
    if args.from_file is not None:
        image = cv2.imread(str(args.from_file))
        if image is None:
            raise ImageReadError(f"could not read image: {args.from_file}")
        return image
    bounds = find_window(args.window)
    return capture(bounds)


def _run_once(args: argparse.Namespace) -> int:
    try:
        image = _grab_image(args)
    except CaptureError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2

    h, w = image.shape[:2]
    layout = load_calibration((w, h)) or detect_board(image)
    save_calibration(layout)

    state = recognize_state(image, layout)
    recommendation = recommend_row(state, mimic_chance=args.mimic_chance)

    output = {
        "state": state.model_dump(),
        "recommendation": recommendation.model_dump(),
    }
    print(json.dumps(output, indent=2))

    if args.debug:
        save_debug_overlay(image, layout, "debug-grid.png", state, recommendation)
        print("wrote debug-grid.png", file=sys.stderr)

    return 0


def _run_overlay(args: argparse.Namespace) -> int:
    """Drive the live on-screen overlay until the user stops it."""
    if args.from_file is not None:
        print("error: --overlay needs the live game window; drop --from-file", file=sys.stderr)
        return 2

    # Imported lazily: tkinter is only needed for the overlay, and this keeps the
    # CLI importable (and the JSON modes working) on machines without a display.
    from .overlay import Overlay

    try:
        overlay = Overlay()
    except Exception as e:  # noqa: BLE001 - report any GUI/Win32 failure to the user
        print(f"error: could not create overlay window: {e}", file=sys.stderr)
        return 2

    def poll():
        try:
            bounds = find_window(args.window)
            image = capture(bounds)
        except CaptureError:
            return None  # game window gone/minimized -> overlay clears this tick
        h, w = image.shape[:2]
        layout = load_calibration((w, h)) or detect_board(image)
        save_calibration(layout)
        state = recognize_state(image, layout)
        recommendation = recommend_row(state, mimic_chance=args.mimic_chance)
        return bounds, layout, recommendation

    interval = args.watch if args.watch is not None else 1.0
    print(f"overlay running (refresh every {interval:.1f}s). Ctrl-C to stop.", file=sys.stderr)
    overlay.run(poll, interval=interval)
    return 0


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)

    if args.overlay:
        return _run_overlay(args)

    if args.watch is None:
        return _run_once(args)

    try:
        while True:
            _run_once(args)
            time.sleep(args.watch)
    except KeyboardInterrupt:
        print("\nstopped", file=sys.stderr)
        return 0
