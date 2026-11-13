"""Audit of the original pairs code: the before/after table and significance tests.

1. Before: pairs chosen on the full sample, cost charged on the Y leg only (the original code).
2. Cost fix only: the same pairs, cost charged on both legs.
3. After: the scan's output (pairs chosen in sample, costs on both legs), with significance tests
   on the out-of-sample returns. Run `run_scan` first.
"""

from __future__ import annotations

import logging
import warnings

import numpy as np
import pandas as pd
from statsmodels.tsa.stattools import coint

from pairs.original.backtest import kpis, run_stat_arb_backtest
from pairs.original.scan import COINT_THRESHOLD, CORR_THRESHOLD, SPLIT_DATE, load_universe
from pairs.universe import RESULTS_DIR

logger = logging.getLogger(__name__)

TRADING_DAYS = 252
BOOTSTRAP_SAMPLES, BOOTSTRAP_BLOCK = 2000, 20
SEED = 0


def sharpe_stats(
    r: pd.Series, n_boot: int = BOOTSTRAP_SAMPLES, block: int = BOOTSTRAP_BLOCK
) -> tuple:
    """Annualised daily Sharpe, its t-stat, and a moving-block bootstrap 95% interval.

    Uses numpy's global random state, seeded once in `run_audit`, so the intervals reproduce
    only if the calls happen in the same order.
    """
    r = r.dropna().values
    sr = r.mean() / r.std() * np.sqrt(TRADING_DAYS)
    t = r.mean() / r.std() * np.sqrt(len(r))
    boots = []
    for _ in range(n_boot):
        starts = np.random.randint(0, len(r) - block, len(r) // block + 1)
        s = np.concatenate([r[i : i + block] for i in starts])[: len(r)]
        boots.append(s.mean() / s.std() * np.sqrt(TRADING_DAYS))
    lo, hi = np.percentile(boots, [2.5, 97.5])
    return round(sr, 2), round(t, 2), round(lo, 2), round(hi, 2)


def summary(df: pd.DataFrame, sharpe_col: str, dd_col: str) -> dict:
    """Pair count, best and median Sharpe, and how many pairs pass the original filters."""
    return {
        "Pairs": len(df),
        "Best Sharpe": df[sharpe_col].max(),
        "Median Sharpe": df[sharpe_col].median(),
        "Pairs Sharpe>1 & DD>-18%": int(((df[sharpe_col] > 1.0) & (df[dd_col] > -18)).sum()),
        "Holy Grail pairs": int(((df[sharpe_col] > 1.5) & (df[dd_col] >= -15)).sum()),
    }


def full_sample_pairs(prices: pd.DataFrame, sectors: pd.DataFrame) -> pd.DataFrame:
    """The original full-sample selection, backtested with one-leg and two-leg costs."""
    rows = []
    for _, group in sectors.groupby("Sector"):
        tickers = group["Ticker"].tolist()
        if len(tickers) < 2:
            continue
        sector_prices = prices[tickers].dropna()
        corr = sector_prices.corr()
        for i in range(len(tickers)):
            for j in range(i + 1, len(tickers)):
                y, x = tickers[i], tickers[j]
                if corr.loc[y, x] < CORR_THRESHOLD:
                    continue
                if coint(sector_prices[y], sector_prices[x])[1] > COINT_THRESHOLD:
                    continue
                r1, t1 = run_stat_arb_backtest(
                    sector_prices[y], sector_prices[x], cost_both_legs=False
                )
                r2, t2 = run_stat_arb_backtest(
                    sector_prices[y], sector_prices[x], cost_both_legs=True
                )
                k1, k2 = kpis(r1, t1), kpis(r2, t2)
                rows.append({
                    "Pair": f"{y}|{x}", "Days": len(r1),
                    "Sharpe_old": k1["Sharpe"], "DD_old": k1["MaxDD (%)"],
                    "SharpeD_old": k1["Sharpe (daily)"],
                    "Sharpe_new": k2["Sharpe"], "DD_new": k2["MaxDD (%)"],
                    "SharpeD_new": k2["Sharpe (daily)"],
                    "Trades": k1["Total Trades"],
                })  # fmt: skip
    return pd.DataFrame(rows)


def run_audit() -> None:
    """Write results/full_sample_before_after_costs.csv and log the audit tables and tests."""
    warnings.filterwarnings("ignore")  # statsmodels warns on near-collinear price pairs
    np.random.seed(SEED)
    prices, sectors = load_universe()

    full = full_sample_pairs(prices, sectors)
    full.to_csv(RESULTS_DIR / "full_sample_before_after_costs.csv", index=False)

    report = pd.read_csv(RESULTS_DIR / "FnO_StatArb_Report.csv")
    daily = pd.read_csv(RESULTS_DIR / "daily_net_returns.csv", index_col=0, parse_dates=True)
    oos_days = daily.index >= SPLIT_DATE
    top3 = report.sort_values("IS Sharpe", ascending=False).head(3)
    top3_keys = (top3["Asset Y"] + "|" + top3["Asset X"]).tolist()
    top3_oos = daily.loc[oos_days, top3_keys].mean(axis=1)
    top3_is = daily.loc[~oos_days, top3_keys].mean(axis=1)
    equity = (1 + top3_oos).cumprod()

    table = pd.DataFrame({
        "Original (full-sample, 1-leg cost)": summary(full, "Sharpe_old", "DD_old"),
        "Cost fix (full-sample, 2-leg cost)": summary(full, "Sharpe_new", "DD_new"),
        "In-sample selection: IS": summary(report, "IS Sharpe", "IS MaxDD (%)"),
        "In-sample selection: OOS": summary(report, "OOS Sharpe", "OOS MaxDD (%)"),
    }).T  # fmt: skip
    logger.info("=" * 70)
    logger.info("BEFORE vs AFTER (CAGR/vol 'Sharpe' as in the original code)")
    logger.info("=" * 70)
    logger.info(table.to_string())

    best = full.sort_values("Sharpe_old", ascending=False).iloc[0]
    r_best, _ = run_stat_arb_backtest(*[prices[s] for s in best["Pair"].split("|")])
    years = best["Days"] / TRADING_DAYS
    # the expected best Sharpe of N independent zero-skill strategies ~ sqrt(2 ln N / years)
    expected_best = np.sqrt(2 * np.log(len(full))) / np.sqrt(years)
    logger.info(
        f"\nBest full-sample pair {best['Pair']}: daily Sharpe, t, 95% CI = {sharpe_stats(r_best)}"
    )
    logger.info(
        f"Expected best Sharpe from {len(full)} zero-skill pairs over {years:.1f} years "
        f"~ sqrt(2 ln N)/sqrt(years) = {expected_best:.2f}"
    )
    logger.info(
        f"\nOOS window: {daily.index[oos_days][0].date()} to {daily.index[-1].date()} "
        f"({oos_days.sum()} days, {oos_days.sum() / 21:.0f} months)"
    )
    logger.info(f"Top-3 IS pairs: {top3_keys}")
    logger.info(f"Top-3 equal-weight IS : Sharpe, t, 95% CI = {sharpe_stats(top3_is)}")
    logger.info(f"Top-3 equal-weight OOS: Sharpe, t, 95% CI = {sharpe_stats(top3_oos)}")
    logger.info(
        f"Top-3 equal-weight OOS: total return {equity.iloc[-1] - 1:.2%}, "
        f"MaxDD {((equity - equity.cummax()) / equity.cummax()).min():.2%}, "
        f"round trips {int(top3['OOS Total Trades'].sum() / 2)}"
    )
    logger.info(
        f"All {len(report)} IS-selected pairs, equal-weight OOS: Sharpe, t, 95% CI = "
        f"{sharpe_stats(daily.loc[oos_days].mean(axis=1))}"
    )
