"""Run one stage of the project: download, check, regimes, hmm, backtest, all, holdout or note."""

import os
from pathlib import Path

import yaml

from regime.backtest import run_backtest, run_checks
from regime.data import build, check, load_dev
from regime.download import download_all
from regime.hmm_regime import run_hmm
from regime.holdout import run_holdout
from regime.note import write_note
from regime.regimes import run_regimes

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = PROJECT_ROOT / "configs" / "config.yaml"
COMMANDS = ("download", "check", "regimes", "hmm", "backtest", "all", "holdout", "note")


def load_config() -> dict:
    """Read configs/config.yaml. Its paths are relative to the project root, so work from there."""
    os.chdir(PROJECT_ROOT)
    with open(CONFIG_PATH) as f:
        return yaml.safe_load(f)


def run(cmd: str) -> None:
    """Run a stage; `all` = data check, regimes, HMM fits, backtest and checks (not the holdout)."""
    if cmd not in COMMANDS:
        raise ValueError(f"unknown command {cmd!r}; expected one of {COMMANDS}")
    cfg = load_config()
    if cmd == "download":
        download_all(cfg)
    if cmd == "holdout":
        run_holdout(cfg)
    if cmd == "note":
        write_note(cfg)
    if cmd in ("check", "all"):
        check(cfg, *build(cfg))
    if cmd in ("regimes", "hmm", "backtest", "all"):
        monthly, daily = load_dev(cfg)
        regimes = run_regimes(cfg, monthly, daily)
        if cmd in ("hmm", "all"):
            run_hmm(cfg, monthly, daily, regimes)
        if cmd in ("backtest", "all"):
            run_backtest(cfg, monthly, regimes["regime"])
    if cmd in ("check", "all"):
        run_checks(cfg)
