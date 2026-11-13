from __future__ import annotations

import numpy as np
import pandas as pd


def book(opt, contracts) -> pd.DataFrame:
    """Daily closes of the contracts in play, indexed for fast lookup."""
    b = opt[opt.expiry.isin(contracts)][["expiry", "opt", "strike", "date", "close"]]
    return b.set_index(["expiry", "opt", "strike", "date"]).sort_index().close


def mark(legs, units, capital, contract, days, bk) -> np.ndarray:
    """Daily mark-to-market P&L of a position."""
    pnl = np.zeros(len(days))
    carried = 0
    for leg in legs:
        code = "PE" if leg["opt"] == "P" else "CE"
        try:
            s = bk.loc[(contract, code, leg["k"])]
        except KeyError:
            s = pd.Series(dtype=float)
        s = s[s > 0].reindex(days)
        carried += int(s.iloc[1:].isna().sum())
        s.iloc[0] = leg["close"]
        s = s.ffill()
        pnl += leg["side"] * (s.values - leg["px"]) * units
    p = pnl[1:] / capital
    out = {
        "worst_mtm_pct": 100 * p.min(),
        "worst_mtm_day": int(p.argmin()) + 1,
        "worst_mtm_date": days[int(p.argmin()) + 1].date(),
        "days_in_loss": int((p < 0).sum()),
        "pnl_day10_pct": 100 * p[9] if len(p) >= 10 else np.nan,
        "pnl_day15_pct": 100 * p[14] if len(p) >= 15 else np.nan,
        "mark_carried_days": carried,
    }
    return out
