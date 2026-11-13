from __future__ import annotations

import logging
import sys
from pathlib import Path

import pandas as pd

from momentum.extract.prices import read_bhavcopy, trading_days

logger = logging.getLogger(__name__)


class HoldoutLocked(Exception):
    pass


def special_sessions(cfg: dict) -> set:
    """Special (non-regular) NSE sessions, used for marking only."""
    # weekend sessions (budget days, Muhurat) and weekday sessions with tiny turnover (Muhurat
    # trading):
    # used for marking prices, never for execution
    path = Path(cfg["paths"]["processed_prices"]) / "special_sessions.csv"
    days = trading_days(cfg)
    if path.exists():
        t = pd.read_csv(path, parse_dates=["date"])
    else:
        rows = []
        for d in days:
            f = Path(cfg["paths"]["raw_prices"]) / "nse_bhavcopy" / f"bhav_{d:%Y-%m-%d}.zip"
            if f.exists():
                b = read_bhavcopy(f)
                rows.append(
                    (
                        d,
                        b.loc[b["series"].isin(cfg["prices"]["nse_series"]), "value"].sum(),
                    )
                )
        t = pd.DataFrame(rows, columns=["date", "turnover"])
        t.to_csv(path, index=False)
    p = cfg["split"]
    med = t["turnover"].rolling(p["turnover_window"], min_periods=5).median().shift(1)
    t["special"] = (t["date"].dt.day_of_week >= 5) | (
        t["turnover"] < p["special_turnover_ratio"] * med
    )
    t["reason"] = [
        "weekend session" if d.day_of_week >= 5 else ("low-turnover session" if s else "")
        for d, s in zip(t["date"], t["special"], strict=False)
    ]
    return t[t["special"]][["date", "turnover", "reason"]]


def regular_days(cfg: dict) -> pd.DatetimeIndex:
    """Regular trading days."""
    days = trading_days(cfg)
    return days[~days.isin(special_sessions(cfg)["date"])]


def signal_dates(cfg: dict) -> pd.DataFrame:
    """Month-end signal dates and their execution days."""
    # last trading day of each month (NIFTY 50 calendar), first signal month to the latest
    # complete month
    days = trading_days(cfg)
    s = cfg["split"]
    last = pd.Series(days, index=days).groupby(days.to_period("M")).max()
    last = last[last.index >= pd.Period(s["first_signal_month"], "M")]
    last = last[last.index < pd.Period(days.max(), "M")]  # the current month is not complete
    out = pd.DataFrame({"signal_date": last.values}, index=last.index.astype(str))
    # execution: the next regular session after the signal date (special sessions are never
    # used for execution)
    reg = regular_days(cfg)
    out["execution_date"] = [
        reg[reg > d][s["execution_lag_days"] - 1]
        if (reg > d).sum() >= s["execution_lag_days"]
        else pd.NaT
        for d in out["signal_date"]
    ]
    out["period"] = [
        "holdout" if m >= s["holdout_first_month"] else "development" for m in out.index
    ]
    return out


def holdout_start(cfg: dict) -> pd.Timestamp:
    """First signal date of the holdout."""
    # returns over periods starting at or after this execution date belong to the holdout
    sd = signal_dates(cfg)
    return sd.loc[sd["period"] == "holdout", "execution_date"].min()


def guard(cfg: dict, period_starts) -> None:
    """Refuse to touch holdout months unless the holdout run is confirmed."""
    # raise if any requested return period starts inside the holdout, unless explicitly unlocked
    starts = pd.to_datetime(pd.Series(period_starts)).dropna()
    first = holdout_start(cfg)
    if (starts >= first).any() and not (
        cfg["split"]["holdout_unlocked"] and "--holdout" in sys.argv
    ):
        raise HoldoutLocked(
            f"holdout returns requested (periods starting {starts[starts >= first].min():%Y-%m-%d} "
            "or later; "
            f"holdout starts {first:%Y-%m-%d}). Locked until the final testing phase."
        )


def write_split(cfg: dict) -> pd.DataFrame:
    """Write the development / holdout split."""
    out = Path(cfg["paths"]["results"])
    out.mkdir(parents=True, exist_ok=True)
    sd = signal_dates(cfg)
    sd.to_csv(out / "split.csv", index_label="signal_month")
    log = out / "trial_log.csv"
    if not log.exists():
        pd.DataFrame(
            columns=[
                "trial_id",
                "date",
                "phase",
                "description",
                "parameters",
                "period",
                "result_file",
            ]
        ).to_csv(log, index=False)
    dev = sd[sd["period"] == "development"]
    logger.info(
        f"signal months: {len(dev)} development ({dev.index[0]} to {dev.index[-1]}), "
        f"{(sd['period'] == 'holdout').sum()} holdout ({cfg['split']['holdout_first_month']} "
        "onward); "
        f"holdout returns start {holdout_start(cfg):%Y-%m-%d}"
    )
    return sd
