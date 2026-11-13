"""Copy inputs from ../momentum_research into data/ and build data/panel.parquet."""

import argparse
import logging

from mlfactors.data import build_panel, copy_inputs

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--skip-copy", action="store_true", help="reuse the inputs already in data/"
    )
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    if not args.skip_copy:
        copy_inputs()
    build_panel()
