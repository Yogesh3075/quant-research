"""The original single-pair engine: rolling OLS hedge ratio on log prices and a rolling z-score.

Enter at |z| > Z_ENTRY, exit at |z| <= Z_EXIT. Unchanged from the original code except the cost
line, so the scan and the audit run the same engine.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

LOOKBACK = 60  # days, for the rolling OLS beta and the z-score
Z_ENTRY = 2.0
Z_EXIT = 0.5
TC = 0.0015  # 0.15% per leg per side
TRADING_DAYS = 252


def run_stat_arb_backtest(
    y: pd.Series, x: pd.Series, cost_both_legs: bool = True
) -> tuple[pd.Series, pd.Series]:
    """Daily net returns and daily trade counts for one pair.

    Returns are per 1 unit of notional in Y (the X leg is beta units).
    cost_both_legs=False reproduces the original code, which charged TC on
    the Y leg only.
    """
    y_val, x_val = np.log(y.values), np.log(x.values)
    n = len(y_val)
    betas, spreads = np.full(n, np.nan), np.full(n, np.nan)

    # beta at day i is fitted on the previous LOOKBACK days only (day i excluded)
    for i in range(LOOKBACK, n):
        y_win, x_win = y_val[i - LOOKBACK : i], x_val[i - LOOKBACK : i]
        X_const = np.column_stack((np.ones(LOOKBACK), x_win))
        try:
            beta_vec = np.linalg.inv(X_const.T @ X_const) @ X_const.T @ y_win
            alpha, beta = beta_vec[0], beta_vec[1]
            betas[i] = beta
            spreads[i] = y_val[i] - (beta * x_val[i] + alpha)
        except np.linalg.LinAlgError:
            continue

    spread_ts, beta_ts = pd.Series(spreads, index=y.index), pd.Series(betas, index=y.index)

    # the z-score uses spreads up to and including today, all known at today's close
    zscore = (spread_ts - spread_ts.rolling(LOOKBACK).mean()) / spread_ts.rolling(LOOKBACK).std()

    pos = np.zeros(n)
    curr = 0
    z_val = zscore.values

    for i in range(LOOKBACK, n):
        z = z_val[i]
        if np.isnan(z):
            continue
        if curr == 0:
            if z < -Z_ENTRY:
                curr = 1  # long the spread
            elif z > Z_ENTRY:
                curr = -1  # short the spread
        elif (curr == 1 and z >= -Z_EXIT) or (curr == -1 and z <= Z_EXIT):
            curr = 0
        pos[i] = curr

    pos_ts = pd.Series(pos, index=y.index)

    # the position decided at close t earns the returns of t+1
    ret_y, ret_x = y.pct_change(), x.pct_change()
    strat_ret = (pos_ts.shift(1) * (ret_y - beta_ts.shift(1) * ret_x)).fillna(0)

    # each change in position trades 1 unit of Y and |beta| units of X
    trades = pos_ts.diff().abs().fillna(0)
    if cost_both_legs:
        net_ret = strat_ret - trades * TC * (1 + beta_ts.abs().fillna(0))
    else:
        net_ret = strat_ret - trades * TC
    return net_ret, trades


def kpis(net_ret: pd.Series, trades: pd.Series) -> dict:
    """The original KPI formulas (Sharpe = CAGR / vol), plus a standard daily Sharpe."""
    n = len(net_ret)
    equity = (1 + net_ret).cumprod()
    cagr = equity.iloc[-1] ** (TRADING_DAYS / n) - 1
    vol = net_ret.std() * np.sqrt(TRADING_DAYS)
    sharpe = cagr / vol if vol > 0 else 0
    sharpe_d = net_ret.mean() / net_ret.std() * np.sqrt(TRADING_DAYS) if vol > 0 else 0
    mdd = ((equity - equity.cummax()) / equity.cummax()).min()
    return {
        "CAGR (%)": round(cagr * 100, 2),
        "Sharpe": round(sharpe, 2),
        "Sharpe (daily)": round(sharpe_d, 2),
        "MaxDD (%)": round(mdd * 100, 2),
        "Total Trades": int(trades.sum()),
    }
