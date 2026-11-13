"""Leg split and long-only variants (trials 7-9) -> results/long_only/."""

import argparse
import logging

if __name__ == "__main__":
    argparse.ArgumentParser(description=__doc__).parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    from pairs.long_only import run_long_only

    run_long_only()
