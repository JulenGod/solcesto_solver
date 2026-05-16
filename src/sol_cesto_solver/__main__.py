"""Entry point so `python -m sol_cesto_solver` works."""
import sys

from .cli import main

if __name__ == "__main__":
    sys.exit(main())
