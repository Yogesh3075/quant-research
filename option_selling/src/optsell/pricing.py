from __future__ import annotations

import numpy as np
from scipy.optimize import brentq
from scipy.stats import norm


def d1(s, k, t, r, vol, q=0.0):
    """Black-Scholes d1 with a dividend yield q."""
    return (np.log(s / k) + (r - q + 0.5 * vol**2) * t) / (vol * np.sqrt(t))


def bs(s, k, t, r, vol, opt, q=0.0):
    """Black-Scholes price of a European call or put."""
    a = d1(s, k, t, r, vol, q)
    b = a - vol * np.sqrt(t)
    if opt == "C":
        return s * np.exp(-q * t) * norm.cdf(a) - k * np.exp(-r * t) * norm.cdf(b)
    return k * np.exp(-r * t) * norm.cdf(-b) - s * np.exp(-q * t) * norm.cdf(-a)


def iv(price, s, k, t, r, opt, q=0.0):
    """Implied volatility by bisection; NaN if the price is outside no-arbitrage bounds."""
    lo, hi = 1e-4, 5.0

    def f(v):
        return bs(s, k, t, r, v, opt, q) - price

    if not (f(lo) < 0 < f(hi)):
        return np.nan
    return brentq(f, lo, hi)


def put_delta(s, k, t, r, vol, q=0.0):
    """Black-Scholes put delta."""
    return -np.exp(-q * t) * norm.cdf(-d1(s, k, t, r, vol, q))
