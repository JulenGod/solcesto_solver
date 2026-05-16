"""Command-line interface: capture -> recognize -> recommend -> print JSON."""
import argparse
import json
import sys
import time
from pathlib import Path

import cv2
import numpy as np

from .capture import WindowNotFoundError, capture, find_window
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
        help="Substring of the game window title (default: %(default)s).",
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
    return parser


def _grab_image(args: argparse.Namespace) -> np.ndarray:
    if args.from_file is not None:
        image = cv2.imread(str(args.from_file))
        if image is None:
            raise WindowNotFoundError(f"could not read image: {args.from_file}")
        return image
    bounds = find_window(args.window)
    return capture(bounds)


def _run_once(args: argparse.Namespace) -> int:
    try:
        image = _grab_image(args)
    except WindowNotFoundError as e:
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
        save_debug_overlay(image, layout, "debug-grid.png")
        print("wrote debug-grid.png", file=sys.stderr)

    return 0


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)

    if args.watch is None:
        return _run_once(args)

    try:
        while True:
            _run_once(args)
            time.sleep(args.watch)
    except KeyboardInterrupt:
        print("\nstopped", file=sys.stderr)
        return 0
