import argparse
from collections.abc import Sequence

from .legacy_cli import main as legacy_main
from .tui import main as tui_main


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Korix terminal control plane")
    parser.add_argument(
        "--legacy-cli",
        action="store_true",
        help="Run the original prompt-based Korix interface.",
    )
    args = parser.parse_args(argv)

    if args.legacy_cli:
        legacy_main()
        return
    tui_main()
