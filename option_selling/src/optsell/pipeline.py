"""Run one stage of the option-selling project, or one command of the paper-trading tool."""

from __future__ import annotations

from optsell import backtest, census, data, live, phase2, phase3, phase4, phase5, report
from optsell.config import load_config

LIVE_COMMANDS = ("signal", "fill", "monitor", "close", "status")
STAGES = (
    "download", "check", "vrp", "backtest", "holdout", "monthly", "diagnostics", "phase2",
    "phase2-validate", "phase3", "phase3-validate", "census", "census-validate", "phase4",
    "phase4-holdout", "phase5", "bugfix-recompute", "all",
)  # fmt: skip


def run(cmd: str, live_args: list | None = None) -> None:
    """Run a stage; `all` = download, check, vrp and the Phase 1 backtest (not the holdout)."""
    if cmd in LIVE_COMMANDS:
        load_config()  # live paths are relative to the project root
        live.cli(cmd, live_args or [])
        return
    if cmd not in STAGES:
        raise ValueError(f"unknown command {cmd!r}")
    cfg = load_config()
    if cmd in ("download", "all"):
        data.download(cfg)
        data.build(cfg)
    if cmd in ("check", "all"):
        data.check(cfg)
        backtest.check(cfg)
        phase2.check(cfg)
        phase3.check(cfg)
        census.check(cfg)
        phase4.check(cfg)
        phase5.check(cfg)
        live.check()
    if cmd in ("vrp", "all"):
        backtest.vrp(cfg)
    if cmd in ("backtest", "all"):
        backtest.run(cfg)
    if cmd == "monthly":
        report.monthly(cfg)
    if cmd == "diagnostics":
        report.diagnostics(cfg)
    if cmd == "phase2":
        phase2.design(cfg)
    if cmd == "phase2-validate":
        phase2.validate(cfg)
    if cmd == "phase3":
        phase3.design(cfg)
    if cmd == "phase3-validate":
        phase3.validate(cfg)
    if cmd == "census":
        census.design(cfg)
    if cmd == "census-validate":
        census.validate(cfg)
    if cmd == "phase4":
        phase4.insample(cfg)
    if cmd == "phase4-holdout":
        phase4.holdout(cfg)
    if cmd == "phase5":
        phase5.results(cfg)
    if cmd == "bugfix-recompute":
        phase5.bugfix(cfg)
    if cmd == "holdout":
        backtest.holdout(cfg)
