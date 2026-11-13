"""Pairs rebuild on the point-in-time Nifty 500."""

import argparse
import logging

STAGES = """stages:
  data     copy inputs from ../momentum_research and fetch NSE F&O lists into data/
  dev      run the 6 development trials (2011-2022) and choose one by development Sharpe
  holdout  run the chosen variant once on 2023 onwards; refuses to run a second time
  summary  rewrite results/summary.md from the saved results"""

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description=__doc__, epilog=STAGES, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("stage", choices=["data", "dev", "holdout", "summary"])
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    from pairs import rebuild, universe

    if args.stage == "data":
        universe.build_data()
    else:
        universe.load()
        {"dev": rebuild.dev, "holdout": rebuild.holdout, "summary": rebuild.summary}[args.stage]()
