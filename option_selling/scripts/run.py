"""Nifty option selling: run one research stage, or one paper-trading command."""

import argparse
import logging

from optsell.pipeline import LIVE_COMMANDS, STAGES, run

HELP = """research stages (development data only unless named):
  download, check              NSE bhavcopies and index files -> data/processed; all checks
  vrp, backtest, monthly, diagnostics       Phase 1: implied vs realised vol, three rules
  phase2, phase3, census, phase4, phase5    later phases (design data)
  phase2-validate, phase3-validate, census-validate    each validation run, once
  holdout, phase4-holdout      locked holdouts; each runs once and refuses a re-run
  bugfix-recompute             the June 2023 relabel fix, recomputed into *_bugfix.csv

paper trading (see NOTES.md):
  signal --date YYYY-MM-DD     entry-day decision for e1f1 and P1
  fill --rule R --leg L --price X [--lots N] [--time HH:MM] [--exit]
  monitor --date YYYY-MM-DD    daily mark and stop status
  close --date YYYY-MM-DD [--expiry]
  status"""

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description=__doc__, epilog=HELP, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("command", choices=STAGES + LIVE_COMMANDS, metavar="command")
    args, live_args = parser.parse_known_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    run(args.command, live_args)
