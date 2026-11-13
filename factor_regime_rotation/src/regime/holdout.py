from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

from regime.backtest import NAMES, STRATS, expense_ratios, monthly_table, sensitivity, summarise
from regime.hmm_regime import fit_all
from regime.regimes import make_regimes

logger = logging.getLogger(__name__)


def previous_runs(cfg: dict) -> list:
    """Lines of the holdout run log (empty if never run)."""
    log = Path(cfg["holdout"]["log"])
    return [line for line in log.read_text().splitlines() if line.strip()] if log.exists() else []


def run_holdout(cfg: dict) -> None:
    """Score the locked holdout once and log the run; refuses a second run."""
    runs = previous_runs(cfg)
    if runs:
        raise SystemExit(
            f"The holdout has already been scored ({len(runs)} run in {cfg['holdout']['log']}): "
            f"{runs[-1]}. Not running again."
        )
    out, res = Path(cfg["paths"]["processed"]), Path(cfg["paths"]["results"])
    monthly = pd.read_csv(out / "tri_monthly.csv", index_col=0, parse_dates=True)
    daily = pd.read_csv(out / "tri_daily.csv", index_col=0, parse_dates=True).loc[
        : monthly.index[-1]
    ]
    first, last = (
        pd.Timestamp(cfg["holdout"]["first_decision"]),
        pd.Timestamp(cfg["holdout"]["last_decision"]),
    )
    logger.info(
        f"Scoring the holdout: decisions {first.date()} to {last.date()}, data to "
        f"{monthly.index[-1].date()}"
    )

    # the development walk-forward, continued into the holdout (HMM refitted every month-end)
    regime = make_regimes(monthly[cfg["calendar"]], daily[cfg["calendar"]], cfg)["regime"]
    states, paths = fit_all(monthly, daily, cfg)
    paths = {t: g.set_index("date")["state"] for t, g in paths.groupby("decision")}
    m, w, fallback = monthly_table(
        monthly, regime, states, paths, cfg, cfg["costs"]["switch"], expense_ratios(cfg)
    )

    # the development part must match the saved development run exactly
    dev_states = pd.read_csv(out / "hmm_states.csv", index_col=0, parse_dates=True)
    assert np.allclose(
        states.loc[dev_states.index, "p_stressed"].astype(float), dev_states["p_stressed"]
    ), "HMM differs from development run"
    dev_m = pd.read_csv(res / "monthly_returns.csv", index_col=0, parse_dates=True)
    ret_cols = [f"{k}_ret" for k in STRATS]
    assert np.allclose(m.loc[dev_m.index, ret_cols], dev_m[ret_cols], atol=1e-6), (
        "returns differ from development run"
    )

    decisions = w["ew"].index
    assert decisions[decisions >= first][0] == first and decisions[-1] == last, (
        "decision dates differ from the pre-registration"
    )
    h = m.loc[m.index > first]
    assert len(h) == 24, f"expected 24 holdout months, got {len(h)}"
    periods = [("holdout", h.index[0], h.index[-1])]
    summary = summarise(m, cfg, periods)
    summary.round(4).to_csv(res / "holdout_result.csv", index=False)
    cols = (
        ["regime", "hmm_p_stressed", "hmm_state"]
        + [f"{k}_ret" for k in STRATS + cfg["benchmarks"]]
        + [f"{k}_turnover" for k in STRATS]
    )
    h[cols].round(6).to_csv(res / "holdout_monthly.csv")
    sens = sensitivity(monthly, regime, states, paths, cfg, periods)
    sens.round(4).to_csv(res / "holdout_sensitivity.csv", index=False)

    with open(cfg["holdout"]["log"], "a") as f:
        f.write(
            f"run {len(runs) + 1}, {datetime.now().isoformat(timespec='seconds')}, decisions "
            f"{first.date()} to "
            f"{last.date()}, scored months {h.index[0].date()} to {h.index[-1].date()} ({len(h)})\n"
        )

    show = summary[
        [
            "strategy",
            "total_ret_%",
            "cagr_%",
            "vol_%",
            "sharpe",
            "max_dd_%",
            "turnover_yr",
            "diff_vs_ew_%",
            "diff_t_nw",
            "share_months_beat_ew",
        ]
    ]
    logger.info(
        f"\nHoldout, {h.index[0]:%b %Y} to {h.index[-1]:%b %Y} ({len(h)} months; very low power "
        "for any t-statistic):"
    )
    logger.info(show.round(2).to_string(index=False))
    logger.info("\nMonth by month, %:")
    logger.info(
        (100 * h[[f"{k}_ret" for k in STRATS + cfg["benchmarks"]]])
        .round(2)
        .set_axis([NAMES[k] for k in STRATS + cfg["benchmarks"]], axis=1)
        .to_string()
    )
    logger.info(
        f"\nHMM stressed in {(h['hmm_state'] == 'stressed').sum()} of {len(h)} holdout decisions; "
        f"regime rule fell back to EW in {int(fallback['regime'].loc[decisions >= first].sum())}"
    )
    logger.info("\nCost sensitivity on the holdout (CAGR %):")
    logger.info(
        sens.pivot_table(index="strategy", columns="case", values="cagr_%").round(2).to_string()
    )
    logger.info(f"\nLogged in {cfg['holdout']['log']}")
