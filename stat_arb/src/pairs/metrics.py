"""Performance statistics on daily returns, and the deflated Sharpe ratio."""

from __future__ import annotations

from statistics import NormalDist

import numpy as np
import pandas as pd

from pairs.trading import CAPITAL

TRADING_DAYS = 252
EULER_GAMMA = 0.5772156649


def sharpe(ret: pd.Series) -> float:
    """Annualised Sharpe of daily returns (no risk-free rate; idle capital earns 0)."""
    return ret.mean() / ret.std() * np.sqrt(TRADING_DAYS) if ret.std() > 0 else 0.0


def max_drawdown(ret: pd.Series) -> float:
    """Largest peak-to-trough fall of the compounded return series."""
    equity = (1 + ret).cumprod()
    return (equity / equity.cummax() - 1).min()


def stats(ret: pd.Series, trades: pd.DataFrame, nifty: pd.Series) -> dict:
    """Return, risk and trade statistics for one period."""
    years = len(ret) / TRADING_DAYS
    equity = (1 + ret).cumprod()
    monthly = (1 + ret).resample("ME").prod() - 1
    bench = nifty.reindex(ret.index).ffill().resample("ME").last().pct_change()
    t = trades
    return {
        "Period": f"{ret.index[0]:%Y-%m} to {ret.index[-1]:%Y-%m}",
        "CAGR": equity.iloc[-1] ** (1 / years) - 1,
        "Sharpe": sharpe(ret),
        "t-stat": ret.mean() / ret.std() * np.sqrt(len(ret)) if ret.std() > 0 else 0.0,
        "Max drawdown": max_drawdown(ret),
        "Trades": len(t),
        "Win rate": (t.net_pnl > 0).mean() if len(t) else np.nan,
        "Avg holding days": t.holding_days.mean() if len(t) else np.nan,
        "Converged (exit at mean)": (t.exit_reason == "mean").mean() if len(t) else np.nan,
        "Stopped out": (t.exit_reason == "stop").mean() if len(t) else np.nan,
        "Window end": (t.exit_reason == "window end").mean() if len(t) else np.nan,
        "Delisted / suspended": int((t.exit_reason == "delisted").sum()) if len(t) else 0,
        "Turnover (x capital / yr)": t.traded_value.sum() / CAPITAL / years if len(t) else 0,
        "Cost drag (% capital / yr)": t.costs.sum() / CAPITAL / years if len(t) else 0,
        "Gross P&L (Rs)": t.gross_pnl.sum() if len(t) else 0,
        "Net P&L (Rs)": t.net_pnl.sum() if len(t) else 0,
        "Corr with Nifty 500 (monthly)": monthly.corr(bench.reindex(monthly.index)),
    }


def deflated_sharpe(ret: pd.Series, trial_srs) -> tuple[float, float]:
    """Bailey and Lopez de Prado (2014) deflated Sharpe, on daily (not annualised) Sharpe ratios.

    SR0, the expected best Sharpe of n zero-skill trials, is
    std(trial SRs) * ((1 - g) * Phi^-1(1 - 1/n) + g * Phi^-1(1 - 1/(n e))), g = Euler's constant.
    The result is P(true SR > SR0) given the sample length, skew and kurtosis of `ret`.
    Returns (probability, SR0 annualised).
    """
    sr = ret.mean() / ret.std()
    n, g = len(trial_srs), EULER_GAMMA
    nd = NormalDist()
    sr0 = np.std(trial_srs, ddof=1) * (
        (1 - g) * nd.inv_cdf(1 - 1 / n) + g * nd.inv_cdf(1 - 1 / (n * np.e))
    )
    skew, kurt = ret.skew(), ret.kurt() + 3
    zval = (sr - sr0) * np.sqrt(len(ret) - 1) / np.sqrt(1 - skew * sr + (kurt - 1) / 4 * sr**2)
    return nd.cdf(zval), sr0 * np.sqrt(TRADING_DAYS)
