"""Momentum on the point-in-time Nifty 500: run one stage of the pipeline."""

import argparse
import logging

from momentum.pipeline import STEPS, run

STAGES = """main stages:
  universe-download, industry, prices-download   downloads (several hours)
  universe-all, prices-all                        rebuild membership / prices from raw files
  phase2-all                                      split, momentum scores, signal diagnostics
  backtest, walkforward, institutional, writeup   later phases, one at a time
  all                                             every result from the raw files (about an hour)
  holdout --holdout                               the locked holdout; logged, refuses a re-run
  check                                           all checks"""

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description=__doc__,
        epilog=STAGES,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("step", choices=STEPS, metavar="step")
    parser.add_argument(
        "--only-missing", action="store_true", help="prices-download: skip done files"
    )
    parser.add_argument("--check", action="store_true", help="momentum: run the signal checks")
    # read by the holdout guards in momentum.transform (they check sys.argv directly)
    parser.add_argument("--holdout", action="store_true", help="confirm a holdout run")
    parser.add_argument("--unlock-holdout", action="store_true", help="allow a further holdout run")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    run(args.step, only_missing=args.only_missing, check=args.check)
