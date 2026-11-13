"""The original F&O pairs code and its audit."""

import argparse
import logging

STAGES = """stages:
  data   download Yahoo prices and sectors into data/original/ (about 10 minutes)
  scan   in-sample pair selection and IS/OOS backtest -> results/FnO_StatArb_Report.csv
  audit  before/after table and significance tests (run scan first)"""

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description=__doc__, epilog=STAGES, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("stage", choices=["data", "scan", "audit"])
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    if args.stage == "data":
        from pairs.original.yahoo import build_yahoo_data

        build_yahoo_data()
    elif args.stage == "scan":
        from pairs.original.scan import run_scan

        run_scan()
    else:
        from pairs.original.audit import run_audit

        run_audit()
