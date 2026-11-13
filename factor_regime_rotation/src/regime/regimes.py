from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


def make_regimes(monthly50: pd.Series, daily50: pd.Series, cfg: dict) -> pd.DataFrame:
    """Trend x volatility regime at each month-end, using data up to that date."""
    c = cfg["regime"]
    ret_12m = monthly50 / monthly50.shift(c["trend_months"]) - 1
    vol = daily50.pct_change().rolling(c["vol_days"]).std() * np.sqrt(252)
    vol = vol.reindex(monthly50.index)
    # median over earlier month-ends only
    med = vol.shift(1).expanding(min_periods=c["min_median_months"]).median()
    reg = pd.DataFrame({"ret_12m": ret_12m, "vol_63d": vol, "vol_median_so_far": med})
    reg["trend"] = np.where(ret_12m > 0, "up", "down")
    reg["vol"] = np.where(vol > med, "high", "low")
    reg["regime"] = reg["trend"] + "/" + reg["vol"]
    reg.loc[
        reg[["ret_12m", "vol_63d", "vol_median_so_far"]].isna().any(axis=1),
        ["trend", "vol", "regime"],
    ] = np.nan
    reg.index.name = "date"
    return reg


def regime_counts(regime: pd.Series) -> pd.DataFrame:
    """Months and average run length per regime."""
    r = regime.dropna()
    run_id = (r != r.shift()).cumsum()
    runs = r.groupby(run_id).agg(["first", "size"])
    return pd.DataFrame(
        {
            "months": r.value_counts(),
            "avg run (months)": runs.groupby("first")["size"].mean().round(1),
            "runs": runs.groupby("first").size(),
        }
    )


def regime_table(rets: pd.DataFrame, regime: pd.Series, cfg: dict) -> pd.DataFrame:
    """Descriptive in-sample table: each factor's return by regime."""
    # each return month is labelled with the regime at its start (the previous month-end)
    start = regime.shift(1).reindex(rets.index)
    ew = rets[cfg["traded"]].mean(axis=1)
    rows = []
    for period, since in [
        ("development", rets.index[0]),
        ("live", pd.Timestamp(cfg["live_start"])),
    ]:
        keep = (rets.index >= since) & start.notna()
        for reg, idx in rets[keep].groupby(start[keep]).groups.items():
            for f in cfg["factors"]:
                excess = rets.loc[idx, f] - ew.loc[idx]
                rows.append(
                    {
                        "period": period,
                        "regime": reg,
                        "factor": f,
                        "note": ""
                        if f in cfg["traded"]
                        else "not traded (near-duplicate of momentum)",
                        "avg_ret_%": 100 * rets.loc[idx, f].mean(),
                        "avg_minus_ew_%": 100 * excess.mean(),
                        "share_beat_ew": (excess > 0).mean(),
                        "months": len(idx),
                    }
                )
    t = pd.DataFrame(rows)
    t.insert(0, "sample", "descriptive, in-sample")
    return t


def run_regimes(cfg: dict, monthly: pd.DataFrame, daily: pd.DataFrame) -> pd.DataFrame:
    """Write data/processed/regimes.csv and the regime tables."""
    reg = make_regimes(monthly[cfg["calendar"]], daily[cfg["calendar"]], cfg)
    out, res = Path(cfg["paths"]["processed"]), Path(cfg["paths"]["results"])
    reg.to_csv(out / "regimes.csv")
    logger.info(
        f"Regimes labelled from {reg['regime'].first_valid_index().date()} to "
        f"{reg.index[-1].date()}"
    )
    logger.info(regime_counts(reg["regime"]).to_string())

    rets = monthly.pct_change(fill_method=None).iloc[1:]
    table = regime_table(rets, reg["regime"], cfg)
    res.mkdir(exist_ok=True)
    table.round(4).to_csv(res / "regime_table.csv", index=False)
    for period in ["development", "live"]:
        t = table[table["period"] == period].pivot(
            index="regime", columns="factor", values="avg_minus_ew_%"
        )
        n = table[table["period"] == period].groupby("regime")["months"].first()
        logger.info(
            f"\nAverage monthly return minus equal weight, %, {period} (descriptive, in-sample; "
            "alpha not traded):"
        )
        logger.info(t[cfg["factors"]].assign(months=n).round(2).to_string())
    return reg
