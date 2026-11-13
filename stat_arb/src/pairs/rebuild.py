"""Pairs rebuild on the point-in-time Nifty 500: 6 development trials, one locked holdout run."""

from __future__ import annotations

import json
import logging
from datetime import datetime

import numpy as np
import pandas as pd

from pairs import universe
from pairs.metrics import TRADING_DAYS, deflated_sharpe, stats
from pairs.selection import selections_for
from pairs.trading import returns, run
from pairs.universe import DATA_DIR, RESULTS_DIR

logger = logging.getLogger(__name__)

TRIALS = [(f, z) for f in (6, 12) for z in (1.5, 2.0, 2.5)]  # (formation months, entry z)
LAST_DEV_FORMATION = pd.Timestamp("2022-06-30")
FIRST_HOLDOUT_FORMATION = pd.Timestamp("2022-12-01")
HOLDOUT_LOCK = RESULTS_DIR / "holdout_lock.json"
TRADE_COLUMNS = [
    "period", "formation_date", "pair", "sector", "hedge_ratio", "direction", "entry_date",
    "exit_date", "entry_z", "exit_z", "exit_reason", "holding_days", "gross_pnl", "costs",
    "net_pnl", "traded_value", "fo_eligible", "p_value", "half_life",
]  # fmt: skip


def load_nifty500() -> pd.Series:
    """NIFTY 500 TRI, the benchmark for the correlation figure."""
    return pd.read_csv(DATA_DIR / "nifty500_tri.csv", index_col=0, parse_dates=True).iloc[:, 0]


def dev() -> None:
    """Run the 6 development trials, log them and choose one by development Sharpe."""
    RESULTS_DIR.mkdir(exist_ok=True)
    if HOLDOUT_LOCK.exists():
        raise SystemExit("Holdout already run; development trials are frozen.")
    days = [d for d in universe.formation_dates(universe.PRICES.index) if d <= LAST_DEV_FORMATION]
    nifty = load_nifty500()
    trial_log, results, counts_all = [], {}, []
    for months in (6, 12):
        selections, counts = selections_for(days, months)
        counts_all += counts
        for formation_months, entry_z in TRIALS:
            if formation_months != months:
                continue
            trades, pnl_all, pnl_fo = run(selections, entry_z)
            r_all, r_fo = returns(pnl_all), returns(pnl_fo)
            s = stats(r_all, trades, nifty)
            s_fo = stats(r_fo, trades[trades.fo_eligible], nifty)
            trial_log.append({
                "trial": len(trial_log) + 1, "formation_months": formation_months,
                "entry_z": entry_z, "dev_sharpe": round(s["Sharpe"], 3),
                "dev_cagr": round(s["CAGR"], 4), "dev_max_dd": round(s["Max drawdown"], 4),
                "trades": s["Trades"], "dev_sharpe_fo": round(s_fo["Sharpe"], 3),
                "daily_sr": r_all.mean() / r_all.std(),
                "run_at": datetime.now().isoformat(timespec="seconds"),
            })  # fmt: skip
            results[(formation_months, entry_z)] = (trades, r_all, r_fo)
            logger.info(
                "trial %d: formation %dm, entry z %s: dev Sharpe %.2f, %d trades",
                len(trial_log), formation_months, entry_z, s["Sharpe"], s["Trades"],
            )  # fmt: skip
    trial_log = pd.DataFrame(trial_log)
    best = trial_log.loc[trial_log.dev_sharpe.idxmax()]
    trial_log["chosen"] = trial_log.trial == best.trial
    trial_log.to_csv(RESULTS_DIR / "trial_log.csv", index=False)
    months, entry_z = int(best.formation_months), float(best.entry_z)
    with open(RESULTS_DIR / "chosen_variant.json", "w") as f:
        json.dump(
            {
                "formation_months": months,
                "entry_z": entry_z,
                "chosen_by": "highest development Sharpe (all pairs)",
                "chosen_at": datetime.now().isoformat(timespec="seconds"),
            },
            f,
            indent=2,
        )

    trades, r_all, r_fo = results[(months, entry_z)]
    window_counts = [c for c in counts_all if c["formation_months"] == months]
    save(trades, r_all, r_fo, window_counts, "development")
    logger.info("Chosen: formation %d months, entry z %s. Holdout not run.", months, entry_z)


def holdout() -> None:
    """Run the chosen variant once on 2023 onwards, then lock the holdout."""
    if HOLDOUT_LOCK.exists():
        raise SystemExit("Holdout already run once. Not running it again.")
    with open(RESULTS_DIR / "chosen_variant.json") as f:
        variant = json.load(f)
    days = [
        d for d in universe.formation_dates(universe.PRICES.index) if d >= FIRST_HOLDOUT_FORMATION
    ]
    selections, counts = selections_for(days, variant["formation_months"])
    trades, pnl_all, pnl_fo = run(selections, variant["entry_z"])
    save(trades, returns(pnl_all), returns(pnl_fo), counts, "holdout")
    with open(HOLDOUT_LOCK, "w") as f:
        json.dump(
            {**variant, "holdout_run_at": datetime.now().isoformat(timespec="seconds")}, f, indent=2
        )
    summary()


def save(
    trades: pd.DataFrame, r_all: pd.Series, r_fo: pd.Series, counts: list, period: str
) -> None:
    """Write (or replace this period's rows in) the trade, return and window-count files."""
    trades = trades.assign(period=period)
    daily = pd.DataFrame({"period": period, "all_pairs": r_all, "fo_subset": r_fo})
    daily.index.name = "date"
    monthly = (1 + daily[["all_pairs", "fo_subset"]]).resample("ME").prod() - 1
    monthly.insert(0, "period", period)
    monthly.index = monthly.index.strftime("%Y-%m")
    monthly.index.name = "month"
    outputs = [
        ("trades.csv", trades[TRADE_COLUMNS].round(4)),
        ("daily_returns.csv", daily),
        ("monthly_returns.csv", monthly),
        ("pairs_per_window.csv", pd.DataFrame(counts).assign(period=period)),
    ]
    for name, df in outputs:
        path, has_index = RESULTS_DIR / name, name in ("daily_returns.csv", "monthly_returns.csv")
        if path.exists():
            old = pd.read_csv(path, index_col=0 if has_index else None)
            if name == "daily_returns.csv":
                old.index = pd.to_datetime(old.index)
            old = old[old.period != period]
            df = pd.concat([old, df])
        df.to_csv(path, index=has_index)


def md(df: pd.DataFrame, index: bool = True) -> str:
    """A frame as a Markdown table."""
    df = df.reset_index() if index else df
    out = ["| " + " | ".join(map(str, df.columns)) + " |", "|" + "---|" * len(df.columns)]
    return "\n".join(out + ["| " + " | ".join(map(str, r)) + " |" for r in df.values])


def format_stat(key: str, x) -> str:
    """Format one summary statistic for the Markdown table."""
    if isinstance(x, str):
        return x
    if key in (
        "CAGR", "Max drawdown", "Win rate", "Converged (exit at mean)", "Stopped out",
        "Window end", "Cost drag (% capital / yr)",
    ):  # fmt: skip
        return f"{x:.1%}"
    if "Rs" in key:
        return f"{x:,.0f}"
    if key in ("Trades", "Delisted / suspended"):
        return f"{int(x)}"
    return f"{x:.2f}"


def summary() -> None:
    """Rewrite results/summary.md from the saved result files."""
    nifty = load_nifty500()
    trades = pd.read_csv(RESULTS_DIR / "trades.csv", parse_dates=["entry_date", "exit_date"])
    daily = pd.read_csv(RESULTS_DIR / "daily_returns.csv", index_col=0, parse_dates=True)
    trial_log = pd.read_csv(RESULTS_DIR / "trial_log.csv")
    # rebuild trials only: the long-only script appends trials 7-9 and two columns
    trial_log = trial_log[trial_log.trial <= 6].drop(
        columns=["variant", "best_of_9_on_dev"], errors="ignore"
    )
    with open(RESULTS_DIR / "chosen_variant.json") as f:
        variant = json.load(f)
    windows = pd.read_csv(RESULTS_DIR / "pairs_per_window.csv")

    table, dsr = {}, {}
    for period in ["development", "holdout"]:
        if period not in set(daily.period):
            continue
        d, t = daily[daily.period == period], trades[trades.period == period]
        table[f"{period}, all pairs"] = stats(d.all_pairs, t, nifty)
        table[f"{period}, F&O subset"] = stats(d.fo_subset, t[t.fo_eligible], nifty)
        dsr[period] = deflated_sharpe(d.all_pairs, trial_log.daily_sr.values)
    tab = pd.DataFrame(table)
    tab = tab.apply(lambda col: [format_stat(k, x) for k, x in col.items()])
    tab.index.name = "Metric"
    lines = [
        "# Pairs trading on the point-in-time Nifty 500: summary",
        "",
        f"Chosen variant: {variant['formation_months']}-month formation, entry |z| > "
        f"{variant['entry_z']} (picked on development Sharpe only, {variant['chosen_at']}).",
        "",
        md(tab),
        "",
        "Sharpe uses daily returns on Rs 10 lakh (idle capital earns 0), annualised by sqrt(252).",
        "",
    ]
    lines += [
        "## Deflated Sharpe (6 trials)",
        "",
        "| Period | Sharpe | Expected max Sharpe of 6 zero-skill trials | "
        "Deflated Sharpe (prob. true SR > 0) |",
        "|---|---:|---:|---:|",
    ]
    for period, (p, sr0) in dsr.items():
        r = daily[daily.period == period].all_pairs
        lines.append(
            f"| {period} | {r.mean() / r.std() * np.sqrt(TRADING_DAYS):.2f} | {sr0:.2f} | {p:.2f} |"
        )
    window_cols = [
        "members", "eligible_stocks", "candidates_tested", "cointegrated", "half_life_ok",
        "selected", "selected_fo",
    ]  # fmt: skip
    lines += [
        "",
        "## Development trials",
        "",
        md(trial_log.drop(columns=["daily_sr"]), index=False),
        "",
        "## Pairs per window (averages)",
        "",
        md(windows.groupby("period")[window_cols].mean().round(0)),
        "",
    ]
    if "holdout" in dsr:
        dv, ho, hf = (
            table["development, all pairs"],
            table["holdout, all pairs"],
            table["holdout, F&O subset"],
        )
        edge = ho["Sharpe"] > 0 and dsr["holdout"][0] > 0.95
        lines += [
            "## Conclusion",
            "",
            f"**{'Edge' if edge else 'No edge'}.** The chosen variant's development Sharpe was "
            f"{dv['Sharpe']:.2f} (t = {dv['t-stat']:.2f}). That is below the "
            f"{dsr['development'][1]:.2f} you'd expect from the best of 6 zero-skill trials, so "
            f"the deflated Sharpe is {dsr['development'][0]:.2f}. In the holdout, run once, the "
            f"Sharpe was {ho['Sharpe']:.2f} (t = {ho['t-stat']:.2f}): net P&L of Rs "
            f"{ho['Net P&L (Rs)']:,.0f} on Rs 10 lakh, or Rs {ho['Gross P&L (Rs)']:,.0f} before "
            "costs. The F&O subset, the part you could actually short overnight, had a holdout "
            f"Sharpe of {hf['Sharpe']:.2f}. About {ho['Stopped out']:.0%} of trades hit the "
            "|z| > 4 stop, and their losses roughly cancel the gains from the trades that "
            f"converged. Costs ({ho['Cost drag (% capital / yr)']:.1%} of capital a year) then "
            "push the result below zero.",
            "",
        ]
    lines += [
        "## Notes on method",
        "",
        "- Universe: point-in-time Nifty 500 membership, adjusted closes and traded value from the "
        "`momentum_research` project (copied into `data/`, not committed).",
        "- Sector: `industry` from `membership.csv`. It is blank for most past members, so blanks "
        "are filled from the same project's `industry.csv` (archived NSE constituent files). "
        "Stocks still 'Unclassified' are dropped.",
        "- F&O eligibility is point-in-time: the stock-futures list in NSE's F&O bhavcopy on each "
        "formation date.",
        "- Size bucket (for slippage) uses the rank by median traded value among Nifty 500 members "
        "on the formation date: 1-100 large, 101-250 mid, the rest small. Market cap was not "
        "available.",
        "- Signals use day t's close; trades fill at day t+1's close. Each leg is Rs 50,000 (equal "
        "rupees long and short), fractional shares, no lot sizes or margin.",
        "- A pair that is stopped out or stops trading is not reopened in the same window. Hedge "
        "ratios are only used for the z-score; sizing is dollar-neutral, as specified. "
        f"{(trades.hedge_ratio <= 0).mean():.0%} of trades have a hedge ratio <= 0.",
        "- The F&O subset uses the same Rs 10 lakh and 20 slots, so its non-F&O slots sit idle.",
        "",
    ]
    (RESULTS_DIR / "summary.md").write_text("\n".join(lines))
    logger.info("Wrote %s", RESULTS_DIR / "summary.md")
