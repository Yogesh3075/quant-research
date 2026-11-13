"""Trading the selected pairs: z-score entries, mean/stop exits, costs on both legs."""

from __future__ import annotations

import numpy as np
import pandas as pd

from pairs import universe
from pairs.selection import SLOTS

CAPITAL = 1_000_000  # Rs 10 lakh
LEG = CAPITAL / SLOTS  # Rs per leg: Rs 50,000 long and Rs 50,000 short per pair slot
FEE = 0.0010  # 10 bps per leg per side
SLIPPAGE = {"large": 0.0005, "mid": 0.0010, "small": 0.0020}
EXIT_Z, STOP_Z = 0.0, 4.0
TRADE_FIELDS = [
    "formation_date",
    "pair",
    "sector",
    "hedge_ratio",
    "p_value",
    "half_life",
    "fo_eligible",
]


def trade_window(
    selected: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp, entry_z: float
) -> tuple[list, pd.DataFrame]:
    """Simulate the selected pairs over (start, end]: trade rows and daily net P&L per trade.

    The z-score uses the formation mean and sd. A signal at day t's close fills at day t+1's
    close (`pending`). A pair that is stopped out or stops trading is not reopened in the window.
    """
    prices = universe.PRICES
    days = prices.index[(prices.index > start) & (prices.index <= end)]
    trades, pnl = [], {}
    for r in selected.to_dict("records"):
        py, px = prices.loc[days, r["y"]].values, prices.loc[days, r["x"]].values
        z = (np.log(py) - r["alpha"] - r["hedge_ratio"] * np.log(px) - r["mu"]) / r["sd"]
        member_until = min(universe.spell_end(r["y"], start), universe.spell_end(r["x"], start))
        cost_y, cost_x = FEE + SLIPPAGE[r["bucket_y"]], FEE + SLIPPAGE[r["bucket_x"]]
        pos, pending, blocked, last_y, last_x, t = 0, None, False, np.nan, np.nan, None
        # set when a signal fires at day k's close, used to fill on day k + 1
        signal_side, signal_z = 0, np.nan

        for k, day in enumerate(days):
            valid = not (np.isnan(py[k]) or np.isnan(px[k]))
            if pos and not valid:  # a leg stopped trading mid-trade
                close(t, day, last_y, last_x, z[k], "delisted", cost_y, cost_x)
                trades.append(t)
                pnl[len(pnl)] = t.pop("daily")
                pos, pending, blocked = 0, None, True
                continue
            if not valid:
                pending = None
                continue
            if pos:
                t["daily"][day] = t["sy"] * (py[k] - last_y) + t["sx"] * (px[k] - last_x)
            last_y, last_x = py[k], px[k]

            if pending == "enter":
                pos = signal_side
                t = {
                    **{c: r[c] for c in TRADE_FIELDS},
                    "direction": "long Y / short X" if pos > 0 else "short Y / long X",
                    "entry_date": day,
                    "entry_z": signal_z,
                    "sy": pos * LEG / py[k],
                    "sx": -pos * LEG / px[k],
                    "costs": LEG * (cost_y + cost_x),
                    "traded_value": 2 * LEG,
                    "daily": {},
                }
                t["daily"][day] = -t["costs"]
            elif pending in ("mean", "stop"):
                close(t, day, py[k], px[k], signal_z, pending, cost_y, cost_x)
                trades.append(t)
                pnl[len(pnl)] = t.pop("daily")
                blocked = blocked or pending == "stop"
                pos = 0
            pending = None

            if pos and k == len(days) - 1:
                close(t, day, py[k], px[k], z[k], "window end", cost_y, cost_x)
                trades.append(t)
                pnl[len(pnl)] = t.pop("daily")
                pos = 0
            elif pos:
                if abs(z[k]) >= STOP_Z:
                    pending, signal_z = "stop", z[k]
                elif pos * z[k] >= EXIT_Z:
                    pending, signal_z = "mean", z[k]
            elif (
                not blocked
                and k < len(days) - 2
                and day <= member_until
                and entry_z < abs(z[k]) < STOP_Z
            ):
                pending, signal_side, signal_z = "enter", -np.sign(z[k]), z[k]
    daily = (
        pd.DataFrame({i: pd.Series(v, dtype=float) for i, v in pnl.items()}).reindex(days).fillna(0)
    )
    return trades, daily


def close(
    t: dict, day: pd.Timestamp, py: float, px: float, z: float, reason: str, cost_y: float,
    cost_x: float,
) -> None:  # fmt: skip
    """Close a trade at the given prices, charging exit costs on both legs."""
    exit_cost = abs(t["sy"]) * py * cost_y + abs(t["sx"]) * px * cost_x
    t["daily"][day] = t["daily"].get(day, 0) - exit_cost
    t["costs"] += exit_cost
    t["traded_value"] += abs(t["sy"]) * py + abs(t["sx"]) * px
    t["exit_date"], t["exit_z"], t["exit_reason"] = day, z, reason
    t["net_pnl"] = sum(t["daily"].values())
    t["gross_pnl"] = t["net_pnl"] + t["costs"]
    index = universe.PRICES.index
    t["holding_days"] = int(((index >= t["entry_date"]) & (index <= day)).sum()) - 1
    del t["sy"], t["sx"]


def run(selections: dict, entry_z: float) -> tuple[pd.DataFrame, pd.Series, pd.Series]:
    """Trade every window: trades, and daily P&L for all pairs and for the F&O subset."""
    prices = universe.PRICES
    dates = universe.formation_dates(prices.index) + [prices.index[-1]]
    next_date = dict(zip(dates[:-1], dates[1:], strict=True))
    all_trades, pnl_all, pnl_fo = [], [], []
    for day, selected in selections.items():
        if not len(selected):
            idle = pd.Series(
                0.0, prices.index[(prices.index > day) & (prices.index <= next_date[day])]
            )
            pnl_all.append(idle)
            pnl_fo.append(idle)
            continue
        trades, daily = trade_window(selected, day, next_date[day], entry_z)
        fo = [i for i, t in enumerate(trades) if t["fo_eligible"]]
        all_trades += trades
        pnl_all.append(daily.sum(axis=1))
        pnl_fo.append(daily[fo].sum(axis=1) if fo else daily.sum(axis=1) * 0)
    return (
        pd.DataFrame(all_trades),
        pd.concat(pnl_all).sort_index(),
        pd.concat(pnl_fo).sort_index(),
    )


def returns(pnl: pd.Series) -> pd.Series:
    """Daily P&L in rupees as a return on the running equity (starting at Rs 10 lakh)."""
    equity = CAPITAL + pnl.cumsum()
    return pnl / equity.shift(1).fillna(CAPITAL)
