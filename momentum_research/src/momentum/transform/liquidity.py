from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)


def build_liquidity(cfg: dict) -> pd.DataFrame:
    """Median traded value per stock and month."""
    # median daily traded value (NSE, rupees) over the trailing window at each month-end,
    # eligible stocks only
    p = cfg["liquidity"]
    value = pd.read_parquet(Path(cfg["paths"]["processed_prices"]) / "traded_value.parquet")
    elig = pd.read_csv(
        Path(cfg["paths"]["processed_universe"]) / "eligibility.csv",
        parse_dates=["date", "price_date"],
    )
    elig = elig[elig["eligible"]]
    rows = []
    for (month, day), g in elig.groupby(["date", "price_date"]):
        window = value.loc[:day].tail(p["window_days"])
        ids = [f for f in g["file_id"] if f in window.columns]
        med = window[ids].median()
        obs = window[ids].notna().sum()
        med[obs < p["min_obs"]] = float("nan")
        rows.append(
            pd.DataFrame(
                dict(
                    date=month,
                    file_id=ids,
                    median_traded_value=med.values,
                    obs=obs.values,
                )
            )
        )
    liq = pd.concat(rows, ignore_index=True)
    out = Path(cfg["paths"]["processed_liquidity"])
    out.mkdir(parents=True, exist_ok=True)
    liq.to_parquet(out / "liquidity.parquet", index=False)
    logger.info(f"saved {out / 'liquidity.parquet'}: {len(liq)} stock-months")
    return liq


def liquidity_summary(cfg: dict, liq: pd.DataFrame) -> pd.DataFrame:
    """Members passing the liquidity floor, by year."""
    p = cfg["liquidity"]
    dates = [pd.Timestamp(d) for d in p["report_dates"]] + [liq["date"].max()]
    rows = []
    for d in dates:
        g = liq[liq["date"] == liq["date"][liq["date"] <= d].max()]
        v = g["median_traded_value"] / 1e7
        row = dict(
            date=g["date"].iloc[0].date(),
            stocks=len(g),
            p10_cr=round(v.quantile(0.1), 2),
            median_cr=round(v.median(), 2),
            p90_cr=round(v.quantile(0.9), 2),
            no_value=int(v.isna().sum()),
        )
        for t in p["thresholds_crore"]:
            row[f">= {t} cr (VERIFY)"] = int((v >= t).sum())
        rows.append(row)
    return pd.DataFrame(rows)
