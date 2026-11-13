"""Top-30 portfolio with a holding buffer, sector cap and liquidity-tiered costs."""

from collections import Counter

import numpy as np
import pandas as pd

HOLDINGS, BUFFER, SECTOR_CAP = 30, 45, 0.25
FEE = 0.0010  # 10 bps per side
SLIPPAGE_TIERS_CRORE = (25, 10)  # 63-day median traded value thresholds, Rs crore
SLIPPAGE_RATES = (0.0005, 0.0010, 0.0020)  # 5 / 10 / 20 bps per side


def slippage(traded_value: np.ndarray) -> np.ndarray:
    """Momentum project tiers: >= 25 crore 5 bps, >= 10 crore 10 bps, else 20 bps."""
    crore = traded_value / 1e7
    high, mid = SLIPPAGE_TIERS_CRORE
    return np.where(
        crore >= high,
        SLIPPAGE_RATES[0],
        np.where(crore >= mid, SLIPPAGE_RATES[1], SLIPPAGE_RATES[2]),
    )


def select(ranked: pd.DataFrame, held: list, sector: dict) -> list:
    """Top 30, keeping current holdings ranked <= 45, with at most 25% of names per sector."""
    cap = int(SECTOR_CAP * HOLDINGS)
    chosen, count = [], Counter()
    for f in ranked[ranked.file_id.isin(held) & (ranked["rank"] <= BUFFER)].file_id:
        if len(chosen) < HOLDINGS and count[sector[f]] < cap:
            chosen.append(f)
            count[sector[f]] += 1
    for f in ranked.file_id:
        if len(chosen) >= HOLDINGS:
            break
        if f not in chosen and count[sector[f]] < cap:
            chosen.append(f)
            count[sector[f]] += 1
    return chosen


def backtest(panel: pd.DataFrame, score_col: str | None) -> pd.DataFrame:
    """Monthly rebalance at the feature-date close, equal weight, costs on traded weight.

    `score_col=None` gives the equal-weight universe. Weights drift with returns between
    rebalances, so turnover is measured against the drifted weights.
    """
    weights, rows = pd.Series(dtype=float), []
    for date, month in panel.groupby("date"):
        month = month.set_index("file_id")
        sector = month.industry.fillna("Unclassified").to_dict()
        if score_col is None:
            target = pd.Series(1 / len(month), month.index)
        else:
            ranked = (
                month[score_col].dropna().sort_values(ascending=False).rename("score").reset_index()
            )
            ranked["rank"] = np.arange(1, len(ranked) + 1)
            names = select(ranked, list(weights.index), sector)
            target = pd.Series(1 / len(names), names)
        names_traded = weights.index.union(target.index)
        trade = target.reindex(names_traded, fill_value=0) - weights.reindex(
            names_traded, fill_value=0
        )
        # names that left the universe have no traded value and pay the 20 bps tier
        traded_value = month.traded_value_63d.reindex(trade.index)
        cost = (trade.abs() * (FEE + slippage(traded_value.fillna(0).values))).sum()
        ret = month.fwd_ret.reindex(target.index).fillna(0)
        gross = (target * ret).sum()
        weights = target * (1 + ret) / (1 + gross)
        rows.append({
            "date": date, "gross": gross, "cost": cost, "net": gross - cost,
            "turnover": trade.abs().sum() / 2,
        })  # fmt: skip
    return pd.DataFrame(rows).set_index("date")
