from __future__ import annotations

import json
import logging
import subprocess
import sys
from pathlib import Path

import pandas as pd

from momentum.transform.backtest import (
    PRESETS,
    index_returns,
    load_market,
    period_returns,
    simulate,
)
from momentum.transform.diagnostics import monthly_ic
from momentum.transform.momentum import forward_returns
from momentum.transform.split import signal_dates

logger = logging.getLogger(__name__)


def committed(path: Path) -> bool:
    """True if the file is tracked by git and unchanged since the last commit."""
    # the file is tracked and unchanged since the last commit
    tracked = (
        subprocess.run(
            ["git", "ls-files", "--error-unmatch", str(path)], capture_output=True
        ).returncode
        == 0
    )
    clean = subprocess.run(["git", "diff", "--quiet", "HEAD", "--", str(path)]).returncode == 0
    return tracked and clean


def holdout_months(cfg: dict) -> tuple:
    """Signal months of the holdout."""
    sd = signal_dates(cfg)
    h = sd[sd["period"] == "holdout"].index
    return (h[0], h[-2])  # the last signal month has no complete holding period yet


def run_holdout(cfg: dict) -> tuple:
    """Run the frozen configuration on the holdout once, logged before computing."""
    out = Path(cfg["paths"]["results"]) / "phase4"
    frozen_path = out / "frozen_config.json"
    if "--holdout" not in sys.argv:
        raise SystemExit("The holdout runs only with: python scripts/run.py holdout --holdout")
    if not frozen_path.exists() or not committed(frozen_path):
        raise SystemExit(f"{frozen_path} must exist and be committed before the holdout run")
    log = out / "holdout_runs.log"
    runs = log.read_text().splitlines() if log.exists() else []
    if runs and "--unlock-holdout" not in sys.argv:
        raise SystemExit(
            f"The holdout has already been run ({len(runs)} run(s) in {log}). A further run needs "
            "--unlock-holdout."
        )
    run_no = len(runs) + 1
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"], capture_output=True, text=True
    ).stdout.strip()
    frozen = json.loads(frozen_path.read_text())
    with open(log, "a") as fh:  # logged before anything is computed or drawn
        fh.write(
            f"{pd.Timestamp.now().isoformat(timespec='seconds')} run {run_no} commit {head} frozen "
            f"{frozen['params']['name']}\n"
        )
    logger.info(f"HOLDOUT RUN {run_no} logged")
    cfg["split"]["holdout_unlocked"] = True
    months = holdout_months(cfg)
    m = load_market(cfg, periods=("development", "holdout"))
    sc = cfg["walkforward"]["scenario"]
    rets = {}
    for key, p in [
        ("frozen selection", frozen["params"]),
        ("fixed primary", PRESETS["primary"]),
        ("quarterly", PRESETS["quarterly"]),
        ("equal weight", PRESETS["equal_weight"]),
    ]:
        run = simulate(cfg, m, p, sc, months=months)
        rets[key] = period_returns(cfg, run["equity"]["equity"], months=months)
    for name in cfg["prices"]["indices"]:
        rets[f"{name} TRI (index)"] = index_returns(cfg, name, months=months)[0]
    # IC of the frozen signal and of the blend on holdout months
    scores = pd.read_parquet(Path(cfg["paths"]["processed_factors"]) / "momentum_scores.parquet")
    scores = scores[(scores["period"] == "holdout") & scores["eligible"]]
    fr = forward_returns(
        cfg,
        pd.read_parquet(Path(cfg["paths"]["processed_prices"]) / "adj_close.parquet"),
        1,
    )
    sd = signal_dates(cfg)
    hold_dates = sd.loc[(sd.index >= months[0]) & (sd.index <= months[1]), "signal_date"]
    fr = fr[fr["signal_date"].isin(hold_dates)]
    ic_frozen = monthly_ic(scores, fr, frozen["params"]["signal"])
    pd.DataFrame(rets).to_csv(out / f"holdout_returns_run{run_no}.csv")
    ic_frozen.to_csv(out / f"holdout_ic_run{run_no}.csv")
    return run_no, months, rets, ic_frozen, frozen


def saved_holdout(cfg: dict):
    """The last logged holdout run, re-read from its files (never rerun)."""
    # re-render the logged holdout run from its saved results (used by `all`; the holdout
    # itself is never rerun)
    out = Path(cfg["paths"]["results"]) / "phase4"
    log = out / "holdout_runs.log"
    if not log.exists():
        return None
    run_no = len(log.read_text().splitlines())
    rets = pd.read_csv(out / f"holdout_returns_run{run_no}.csv", index_col=0)
    rets = {k: rets[k] for k in rets.columns}
    ic = pd.read_csv(out / f"holdout_ic_run{run_no}.csv", index_col=0).iloc[:, 0]
    frozen = json.loads((out / "frozen_config.json").read_text())
    months = (rets[next(iter(rets))].index[0], rets[next(iter(rets))].index[-1])
    return run_no, months, rets, ic, frozen
