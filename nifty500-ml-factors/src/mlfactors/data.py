"""Inputs copied from the momentum project, and the month-end feature panel built from them."""

import logging
import os
import shutil
from pathlib import Path

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
RESULTS_DIR = PROJECT_ROOT / "results"
MOMENTUM_DIR = Path(os.environ.get("MOMENTUM_DIR", PROJECT_ROOT.parent / "momentum_research"))

MIN_TRADED_VALUE = 5e7  # Rs 5 crore median daily traded value over the past 63 days
FIRST_FEATURE_DATE = pd.Timestamp("2011-01-01")
DAYS_1M, DAYS_3M, DAYS_6M, DAYS_12M = 21, 63, 126, 252
MIN_DAYS_12M = 200  # 12-month features need at least this many daily returns
MIN_DAYS_TRADED_VALUE = 21
FEATURES = [
    "mom_12_1", "mom_6_1", "ret_3m", "ret_1m", "vol_12m", "vol_1m", "beta_ew", "dist_52w_high",
    "log_traded_value", "amihud", "max_ret_1m", "ind_rel_mom_6_1",
]  # fmt: skip
MOMENTUM_INPUTS = [
    "processed/prices/adj_close.parquet",
    "processed/prices/volume.parquet",
    "processed/prices/traded_value.parquet",
    "processed/prices/securities.csv",
    "processed/prices/return_overrides.csv",
    "processed/universe/membership.csv",
    "processed/universe/industry.csv",
]


def copy_inputs(momentum_dir: Path = MOMENTUM_DIR, data_dir: Path = DATA_DIR) -> None:
    """Copy the momentum project's processed prices, universe and IIMA factor file into data/."""
    data_dir.mkdir(exist_ok=True)
    source = momentum_dir / "Data"
    if not source.exists():
        raise FileNotFoundError(
            f"{source} not found: build momentum_research first or set MOMENTUM_DIR"
        )
    files = MOMENTUM_INPUTS + [
        str(p.relative_to(source)) for p in (source / "raw/iima").glob("*.csv")
    ]
    for f in files:
        shutil.copy(source / f, data_dir / Path(f).name)


def load(data_dir: Path = DATA_DIR) -> tuple:
    """Prices, traded value, eligible membership spells, daily returns and a total-return index."""
    adj = pd.read_parquet(data_dir / "adj_close.parquet")
    traded_value = pd.read_parquet(data_dir / "traded_value.parquet").reindex(columns=adj.columns)
    securities = (
        pd.read_csv(data_dir / "securities.csv").drop_duplicates("stock_id").set_index("stock_id")
    )
    industry = (
        pd.read_csv(data_dir / "industry.csv")
        .drop_duplicates("stock_id")
        .set_index("stock_id")
        .industry
    )
    membership = pd.read_csv(data_dir / "membership.csv", parse_dates=["start_date", "end_date"])
    # a blank start date means the stock was a member before the first notice on file
    membership["start_date"] = membership.start_date.fillna(pd.Timestamp("2000-01-01"))
    membership["file_id"] = membership.stock_id.map(securities.file_id)
    membership["industry"] = membership.industry.fillna(membership.stock_id.map(industry)).replace(
        "Unclassified", np.nan
    )
    membership = membership[membership.eligible & membership.file_id.isin(adj.columns)]

    # A stock that stops trading keeps its last close (return 0); unadjusted demerger/rights days
    # flagged by the momentum project are set to 0 rather than showing a fake crash.
    prices = adj.ffill()
    returns = prices.pct_change(fill_method=None)
    overrides = pd.read_csv(data_dir / "return_overrides.csv", parse_dates=["date"])
    for row in overrides.itertuples():
        if row.file_id in returns.columns and row.date in returns.index:
            returns.loc[row.date, row.file_id] = 0.0
    total_return = (1 + returns.fillna(0)).cumprod().where(prices.notna())
    return adj, traded_value, membership, returns, total_return


def members_on(membership: pd.DataFrame, day: pd.Timestamp) -> pd.DataFrame:
    """Index members on `day`; end_date is the effective exit day, so the stock is out on it."""
    m = membership[
        (membership.start_date <= day) & (membership.end_date.isna() | (membership.end_date > day))
    ]
    return m.drop_duplicates("file_id")


def rank_to_unit(panel: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    """Rank each column within its month to [-0.5, 0.5]; missing features become 0 after ranking."""
    by_month = panel.groupby("date")
    for c in columns:
        rank = by_month[c].rank(method="average")
        count = by_month[c].transform("count")
        scaled = (rank - 1) / (count - 1) - 0.5
        panel["r_" + c] = scaled if c == "fwd_ret" else scaled.fillna(0)
    return panel


def build_panel(data_dir: Path = DATA_DIR) -> pd.DataFrame:
    """One row per (month-end, eligible stock): 12 features and next month's return."""
    adj, traded_value, membership, returns, total_return = load(data_dir)
    days = adj.index
    month_ends = list(days.to_series().groupby(days.to_period("M")).max())

    # equal-weight Nifty 500 daily return (members at the previous month-end), used for beta
    ew_return = pd.Series(np.nan, days)
    for prev, cur in zip(month_ends[:-1], month_ends[1:], strict=True):
        in_month = days[(days > prev) & (days <= cur)]
        ew_return[in_month] = returns.loc[in_month, members_on(membership, prev).file_id].mean(
            axis=1
        )

    rows = []
    for k, t in enumerate(month_ends[:-1]):
        i = days.get_loc(t)
        if i < DAYS_12M or t < FIRST_FEATURE_DATE:
            continue
        members = members_on(membership, t)
        ids = [f for f in members.file_id if pd.notna(adj.at[t, f])]  # must have a price on t
        tv_63d = traded_value.iloc[i - 62 : i + 1][ids]
        median_tv = tv_63d.median().where(tv_63d.notna().sum() >= MIN_DAYS_TRADED_VALUE)
        ids = median_tv[median_tv >= MIN_TRADED_VALUE].index
        if len(ids) == 0:
            continue

        r252 = returns.iloc[i - 251 : i + 1][ids]
        r63 = returns.iloc[i - 62 : i + 1][ids]
        r21 = returns.iloc[i - 20 : i + 1][ids]
        tri = total_return[ids]
        ew252 = pd.DataFrame(
            np.repeat(ew_return.iloc[i - 251 : i + 1].values[:, None], len(ids), 1),
            index=r252.index,
            columns=ids,
        ).where(r252.notna())
        enough_history = r252.notna().sum() >= MIN_DAYS_12M
        high_52w = tri.iloc[i - 251 : i + 1].max()
        tv_63d_positive = traded_value.iloc[i - 62 : i + 1][ids].where(lambda x: x > 0)
        cov = (r252 * ew252).mean() - r252.mean() * ew252.mean()
        features = pd.DataFrame({
            "mom_12_1": tri.iloc[i - DAYS_1M] / tri.iloc[i - DAYS_12M] - 1,
            "mom_6_1": tri.iloc[i - DAYS_1M] / tri.iloc[i - DAYS_6M] - 1,
            "ret_3m": tri.iloc[i] / tri.iloc[i - DAYS_3M] - 1,
            "ret_1m": tri.iloc[i] / tri.iloc[i - DAYS_1M] - 1,
            "vol_12m": r252.std().where(enough_history),
            "vol_1m": r21.std(),
            "beta_ew": (cov / ((ew252**2).mean() - ew252.mean() ** 2)).where(enough_history),
            "dist_52w_high": tri.iloc[i] / high_52w.where(enough_history) - 1,
            "log_traded_value": np.log(median_tv[ids]),
            "amihud": (r63.abs() / tv_63d_positive).mean() * 1e7,
            "max_ret_1m": r21.max(),
        })  # fmt: skip
        features["industry"] = members.set_index("file_id").industry.reindex(ids)
        features["ind_rel_mom_6_1"] = features.mom_6_1 - features.groupby(
            "industry"
        ).mom_6_1.transform("median")
        next_month_end = month_ends[k + 1]
        # close on t to close on the next month-end
        features["fwd_ret"] = total_return.loc[next_month_end, ids] / total_return.loc[t, ids] - 1
        features["traded_value_63d"] = median_tv[ids]
        features["date"], features["next_date"] = t, next_month_end
        features["stock_id"] = members.set_index("file_id").stock_id.reindex(ids)
        rows.append(features.rename_axis("file_id").reset_index())

    panel = rank_to_unit(pd.concat(rows, ignore_index=True), FEATURES + ["fwd_ret"])
    panel.to_parquet(data_dir / "panel.parquet", index=False)
    size = panel.groupby("date").size()
    logger.info(
        "Panel: %d stock-months, %s to %s, universe per month min %d median %d max %d",
        len(panel), f"{panel.date.min():%Y-%m}", f"{panel.date.max():%Y-%m}",
        size.min(), int(size.median()), size.max(),
    )  # fmt: skip
    logger.info(
        "Share missing before fill:\n%s", panel[FEATURES].isna().mean().round(3).to_string()
    )
    return panel
