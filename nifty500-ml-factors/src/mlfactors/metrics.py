"""Return statistics: Newey-West means, portfolio summary and the deflated Sharpe ratio."""

from statistics import NormalDist

import numpy as np
import pandas as pd
import statsmodels.api as sm

NW_LAGS = 3
EULER_GAMMA = 0.5772156649
MONTHS_PER_YEAR = 12


def nw_mean(x) -> tuple[float, float]:
    """Mean and its Newey-West t-statistic (3 lags)."""
    x = pd.Series(x).dropna()
    fit = sm.OLS(x.values, np.ones(len(x))).fit(cov_type="HAC", cov_kwds={"maxlags": NW_LAGS})
    return fit.params[0], fit.tvalues[0]


def max_drawdown(returns: pd.Series) -> float:
    """Largest peak-to-trough fall of the compounded return series."""
    equity = (1 + returns).cumprod()
    return (equity / equity.cummax() - 1).min()


def sharpe(returns: pd.Series, periods_per_year: int = MONTHS_PER_YEAR) -> float:
    """Annualised Sharpe on raw returns (no risk-free deduction)."""
    return returns.mean() / returns.std() * np.sqrt(periods_per_year)


def port_stats(bt: pd.DataFrame, ew: pd.DataFrame) -> dict:
    """Summary of a monthly backtest against the equal-weight universe."""
    r = bt.net
    equity = (1 + r).cumprod()
    excess, excess_t = nw_mean(r - ew.net.reindex(r.index))
    return {
        "CAGR": equity.iloc[-1] ** (MONTHS_PER_YEAR / len(r)) - 1,
        "Sharpe": sharpe(r),
        "Max drawdown": max_drawdown(r),
        "Excess over EW (% / month)": excess,
        "Excess t-stat (NW)": excess_t,
        "Turnover (one-way, x / yr)": bt.turnover.mean() * MONTHS_PER_YEAR,
        "Cost drag (% / yr)": bt.cost.mean() * MONTHS_PER_YEAR,
        "Months": len(r),
    }


def deflated_sharpe(r: pd.Series, trial_srs) -> tuple[float, float]:
    """Bailey and Lopez de Prado deflated Sharpe ratio.

    SR0 is the expected maximum Sharpe of `n` zero-skill trials:
    std(trial SRs) * ((1 - g) * Phi^-1(1 - 1/n) + g * Phi^-1(1 - 1/(n e))), g = Euler's constant.
    The result is P(true SR > SR0), adjusting the observed SR for sample length, skew and kurtosis.
    Returns (probability, SR0 annualised from monthly).
    """
    nd, g = NormalDist(), EULER_GAMMA
    n = len(trial_srs)
    sr = r.mean() / r.std()
    sr0 = np.std(trial_srs, ddof=1) * (
        (1 - g) * nd.inv_cdf(1 - 1 / n) + g * nd.inv_cdf(1 - 1 / (n * np.e))
    )
    z = (sr - sr0) * np.sqrt(len(r) - 1) / np.sqrt(1 - r.skew() * sr + (r.kurt() + 2) / 4 * sr**2)
    return nd.cdf(z), sr0 * np.sqrt(MONTHS_PER_YEAR)
