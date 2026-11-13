"""Factor Regime Rotation: run one stage of the pipeline."""

import argparse
import logging

from regime.pipeline import COMMANDS, run

STAGES = """stages:
  download  fetch NSE index data into data/raw (about 10 minutes)
  check     build data/processed, write results/data_check.md, run all checks
  regimes   rule-based regimes and the descriptive regime table
  hmm       HMM fits at every month-end (filtered probabilities)
  backtest  walk-forward backtest of all rules
  all       check + regimes + hmm + backtest + checks (not the holdout)
  holdout   score the locked holdout; refuses to run a second time
  note      write results/research_note.md"""

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description=__doc__, epilog=STAGES, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("stage", choices=COMMANDS)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    run(args.stage)
