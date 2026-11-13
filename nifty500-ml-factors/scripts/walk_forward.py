"""Yearly walk-forward models: predictions, feature importance and SHAP interactions."""

import argparse
import logging

from mlfactors.models import run_walk_forward

if __name__ == "__main__":
    argparse.ArgumentParser(description=__doc__).parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    run_walk_forward()
