"""Portfolios, IC, spanning test and trial log -> results/."""

import argparse
import logging

from mlfactors.report import run_report

if __name__ == "__main__":
    argparse.ArgumentParser(description=__doc__).parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    run_report()
