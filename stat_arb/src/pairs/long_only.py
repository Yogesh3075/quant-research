"""Long-only versions of the point-in-time Nifty 500 pairs strategy.

Reuses the rebuild's data, pair selection (12-month formation, top 20) and costs.
  leg split  the rebuild's development trades, split into long and short legs
  A          pair switching: each slot holds one stock of its pair, switches at |z| > 2
  B          cheap leg only on the rebuild's signals, hedged with Nifty 50 futures
  B-unh      B without the hedge
Development = 2011-2022. 2023 onwards is a "seen holdout": the rebuild had already looked at it.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime

import numpy as np
import pandas as pd

from pairs import universe
from pairs.metrics import TRADING_DAYS, deflated_sharpe
from pairs.rebuild import md
from pairs.selection import selections_for
from pairs.trading import CAPITAL, FEE, LEG, SLIPPAGE, returns
from pairs.universe import DATA_DIR, MOMENTUM_DIR, RESULTS_DIR

logger = logging.getLogger(__name__)

OUT = RESULTS_DIR / "long_only"
SWITCH_Z = 2.0
FUTURES_COST = 0.0003  # Nifty 50 futures, 3 bps per side
PERIODS = {
    "development": ("2011-01-01", "2022-12-31"),
    "seen holdout": ("2023-01-01", "2026-12-31"),
}
VARIANT_KEYS = {
    "long-only A: pair switching": "A",
    "long-only B: cheap leg + Nifty futures hedge": "B",
    "long-only B-unhedged": "B-unhedged",
}


def nifty50() -> pd.Series:
    """NIFTY 50 closes from the momentum project's raw index files, on the price calendar."""
    rows = []
    for f in sorted((MOMENTUM_DIR / "Data/raw/prices/index").glob("NIFTY_50_price_*.json")):
        rows += json.loads(f.read_text() or "[]")
    df = pd.DataFrame(rows)
    s = pd.Series(
        pd.to_numeric(df.CLOSE, errors="coerce").values,
        pd.to_datetime(df.HistoricalDate, format="%d %b %Y"),
    ).sort_index()
    return s[~s.index.duplicated()].dropna().reindex(universe.PRICES.index).ffill()


def equal_weight_nifty500() -> pd.Series:
    """Daily equal-weight return of the stocks that were members at the previous month-end."""
    rets = universe.PRICES.pct_change(fill_method=None)
    month_ends = rets.index.to_series().groupby(rets.index.to_period("M")).max()
    out = pd.Series(np.nan, rets.index)
    for prev, cur in zip(month_ends.iloc[:-1], month_ends.iloc[1:], strict=True):
        days = rets.index[(rets.index > prev) & (rets.index <= cur)]
        out[days] = rets.loc[days, universe.members_on(prev).file_id].mean(axis=1)
    return out.fillna(0)


def cost_rate(bucket: str) -> float:
    """Fee plus size-bucket slippage, per side."""
    return FEE + SLIPPAGE[bucket]


def exit_day(t, pair) -> pd.Timestamp:
    """The rebuild closes a delisted trade at the last day on which both stocks had a price."""
    if t.exit_reason != "delisted":
        return t.exit_date
    both = universe.PRICES.loc[t.entry_date : t.exit_date, [pair.y, pair.x]].dropna()
    return both.index[-1]


def price_at(file_id: str, day: pd.Timestamp) -> float:
    """Last available price on or before `day` (handles stocks that stopped trading)."""
    return universe.PRICES.loc[:day, file_id].dropna().iloc[-1]


def stock_names() -> pd.Series:
    """NSE symbol for each price column."""
    return universe.MEMBERSHIP.drop_duplicates("file_id").set_index("file_id").stock_id


def leg_split(trades: pd.DataFrame, selections: dict, ew: pd.Series) -> pd.DataFrame:
    """Each rebuild trade split into its long and short leg, with excess over EW Nifty 500."""
    prices, rows = universe.PRICES, []
    for t in trades.itertuples():
        pair = selections[t.formation_date].set_index("pair").loc[t.pair]
        long_y = t.direction.startswith("long Y")
        legs = {
            "long": (pair.y, pair.bucket_y) if long_y else (pair.x, pair.bucket_x),
            "short": (pair.x, pair.bucket_x) if long_y else (pair.y, pair.bucket_y),
        }
        days = prices.index[(prices.index > t.entry_date) & (prices.index <= t.exit_date)]
        ew_ret = (1 + ew[days]).prod() - 1
        for leg, (fid, b) in legs.items():
            p0, p1 = prices.loc[t.entry_date, fid], price_at(fid, exit_day(t, pair))
            r = p1 / p0 - 1
            sign = 1 if leg == "long" else -1
            gross = sign * LEG * r
            costs = (LEG + LEG * p1 / p0) * cost_rate(b)
            rows.append({
                "period": t.period, "formation_date": t.formation_date, "pair": t.pair, "leg": leg,
                "stock": stock_names()[fid], "entry_date": t.entry_date, "exit_date": t.exit_date,
                "exit_reason": t.exit_reason, "stock_return": r, "ew_nifty500_return": ew_ret,
                "excess_return": sign * (r - ew_ret), "gross_pnl": gross, "costs": costs,
                "net_pnl": gross - costs, "trade_gross_pnl": t.gross_pnl,
            })  # fmt: skip
    return pd.DataFrame(rows)


def leg_table(legs: pd.DataFrame) -> pd.DataFrame:
    """Per-leg totals, win rates and the t-stat of the excess return."""
    out = {}
    for leg, g in legs.groupby("leg"):
        ex = g.excess_return
        out[leg] = {
            "Trades": len(g),
            "Total gross P&L (Rs)": g.gross_pnl.sum(),
            "Total net P&L (Rs)": g.net_pnl.sum(),
            "Mean net P&L per trade (Rs)": g.net_pnl.mean(),
            "Win rate (net > 0)": (g.net_pnl > 0).mean(),
            "Mean excess vs EW Nifty 500 per trade": ex.mean(),
            "t-stat of excess": ex.mean() / ex.std() * np.sqrt(len(ex)),
            "Excess win rate": (ex > 0).mean(),
        }
    return pd.DataFrame(out)


def switching_window(selected: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp) -> tuple:
    """A: each slot holds one stock of its pair, switching to the cheap stock when |z| > 2.

    Returns daily P&L of A, of its 50/50 buy-and-hold benchmark, the trade log and per-slot returns.
    """
    prices = universe.PRICES
    days = prices.index[(prices.index > start) & (prices.index <= end)]
    pnl_a, pnl_b, rows, slots = {}, {}, [], []
    names = stock_names()
    for i, r in enumerate(selected.to_dict("records")):
        ids = {"y": r["y"], "x": r["x"]}
        cost = {"y": cost_rate(r["bucket_y"]), "x": cost_rate(r["bucket_x"])}
        p = {k: prices.loc[days, ids[k]].values for k in ids}
        z = (np.log(p["y"]) - r["alpha"] - r["hedge_ratio"] * np.log(p["x"]) - r["mu"]) / r["sd"]
        z_start = (
            np.log(prices.loc[start, r["y"]])
            - r["alpha"]
            - r["hedge_ratio"] * np.log(prices.loc[start, r["x"]])
            - r["mu"]
        ) / r["sd"]
        a, b = np.zeros(len(days)), np.zeros(len(days))

        def record(k, action, frm, to, value, trade_cost, z_value, r=r, ids=ids):
            rows.append({
                "formation_date": start.date(), "pair": r["pair"], "date": days[k].date(),
                "action": action, "sell": names[ids[frm]] if frm else "",
                "buy": names[ids[to]] if to else "", "z": z_value, "traded_value": value,
                "costs": trade_cost,
            })  # fmt: skip

        # start in the cheaper stock: z > 0 means Y is rich, so X is cheap
        hold = "x" if z_start > 0 else "y"
        shares = LEG / p[hold][0]
        a[0] -= LEG * cost[hold]
        record(0, "buy at window start", None, hold, LEG, LEG * cost[hold], z_start)
        last, pending, in_cash = p[hold][0], None, False
        for k in range(1, len(days)):
            if in_cash:
                continue
            if np.isnan(p[hold][k]):  # stopped trading: sell at the last price, hold cash
                value = shares * last
                a[k] -= value * cost[hold]
                record(k, "delisted", hold, None, value, value * cost[hold], np.nan)
                in_cash = True
                continue
            a[k] += shares * (p[hold][k] - last)
            last = p[hold][k]
            other = "x" if hold == "y" else "y"
            if pending and not np.isnan(p[other][k]):
                value = shares * p[hold][k]
                a[k] -= value * (cost[hold] + cost[other])
                record(
                    k, "switch", hold, other, 2 * value, value * (cost[hold] + cost[other]), pending
                )
                hold, shares, last = other, value / p[other][k], p[other][k]
            pending = None
            if k == len(days) - 1:
                value = shares * p[hold][k]
                a[k] -= value * cost[hold]
                record(k, "sell at window end", hold, None, value, value * cost[hold], z[k])
            elif k < len(days) - 1 and (
                (z[k] > SWITCH_Z and hold == "y") or (z[k] < -SWITCH_Z and hold == "x")
            ):
                pending = z[k]

        # benchmark: 50/50 buy and hold of the same two stocks
        for k in ids:
            held_shares = LEG / 2 / p[k][0]
            b[0] -= LEG / 2 * cost[k]
            valid = ~np.isnan(p[k])
            stop = len(days) - 1 if valid.all() else int(np.argmin(valid))  # first missing day
            filled = pd.Series(p[k]).ffill().values
            b[1 : stop + 1] += held_shares * np.diff(filled[: stop + 1])
            b[stop] -= held_shares * filled[stop] * cost[k]

        pnl_a[i], pnl_b[i] = a, b
        slots.append({
            "formation_date": start.date(), "pair": r["pair"], "return_A": a.sum() / LEG,
            "return_benchmark": b.sum() / LEG,
        })  # fmt: skip
    return (
        pd.DataFrame(pnl_a, index=days).sum(axis=1),
        pd.DataFrame(pnl_b, index=days).sum(axis=1),
        rows,
        slots,
    )


def cheap_leg(trades: pd.DataFrame, selections: dict, n50: pd.Series) -> tuple:
    """B: long the cheap stock on the rebuild's entry/exit dates, hedged and unhedged."""
    prices = universe.PRICES
    pnl_hedged, pnl_unhedged, rows = {}, {}, []
    for i, t in enumerate(trades.itertuples()):
        pair = selections[t.formation_date].set_index("pair").loc[t.pair]
        if t.direction.startswith("long Y"):
            fid, b = pair.y, pair.bucket_y
        else:
            fid, b = pair.x, pair.bucket_x
        days = prices.index[(prices.index >= t.entry_date) & (prices.index <= exit_day(t, pair))]
        p = prices.loc[days, fid].ffill()
        n = n50[days]
        stock = LEG / p.iloc[0] * p.diff().fillna(0)
        hedge = -LEG / n.iloc[0] * n.diff().fillna(0)
        cost_stock = LEG * cost_rate(b) + LEG * p.iloc[-1] / p.iloc[0] * cost_rate(b)
        cost_hedge = LEG * FUTURES_COST + LEG * n.iloc[-1] / n.iloc[0] * FUTURES_COST
        unhedged = stock.copy()
        unhedged.iloc[0] -= LEG * cost_rate(b)
        unhedged.iloc[-1] -= cost_stock - LEG * cost_rate(b)
        hedged = unhedged + hedge
        hedged.iloc[0] -= LEG * FUTURES_COST
        hedged.iloc[-1] -= cost_hedge - LEG * FUTURES_COST
        pnl_unhedged[i], pnl_hedged[i] = unhedged, hedged
        rows.append({
            "period": t.period, "formation_date": t.formation_date, "pair": t.pair,
            "stock": stock_names()[fid], "entry_date": t.entry_date, "exit_date": t.exit_date,
            "exit_reason": t.exit_reason, "stock_pnl": stock.sum(), "stock_costs": cost_stock,
            "hedge_pnl": hedge.sum(), "hedge_costs": cost_hedge,
            "net_pnl_unhedged": unhedged.sum(), "net_pnl_hedged": hedged.sum(),
            "traded_value_stock": LEG * (1 + p.iloc[-1] / p.iloc[0]),
            "traded_value_hedge": LEG * (1 + n.iloc[-1] / n.iloc[0]),
        })  # fmt: skip
    daily_hedged = pd.concat(pnl_hedged.values()).groupby(level=0).sum()
    daily_unhedged = pd.concat(pnl_unhedged.values()).groupby(level=0).sum()
    return daily_hedged, daily_unhedged, pd.DataFrame(rows)


def monthly(ret: pd.Series) -> pd.Series:
    """Compound daily returns to calendar months."""
    return (1 + ret).resample("ME").prod() - 1


def metrics(
    ret: pd.Series, bench: pd.Series, traded: float, costs: float, nifty500: pd.Series
) -> dict:
    """Return statistics against a benchmark, plus turnover, cost drag and beta."""
    years = len(ret) / TRADING_DAYS
    equity = (1 + ret).cumprod()
    m, mb = monthly(ret), monthly(bench)
    excess = m - mb
    mn = monthly(nifty500.pct_change().reindex(ret.index).fillna(0))
    return {
        "CAGR": equity.iloc[-1] ** (1 / years) - 1,
        "Sharpe": ret.mean() / ret.std() * np.sqrt(TRADING_DAYS),
        "Max drawdown": (equity / equity.cummax() - 1).min(),
        "Excess vs benchmark (% / month)": excess.mean(),
        "t-stat of excess": excess.mean() / excess.std() * np.sqrt(len(excess)),
        "Turnover (x capital / yr)": traded / CAPITAL / years,
        "Cost drag (% capital / yr)": costs / CAPITAL / years,
        "Beta to Nifty 500 (monthly)": np.cov(m, mn)[0, 1] / mn.var(),
    }


def fmt(key: str, x: float) -> str:
    """Format one statistic for the Markdown tables."""
    if key in (
        "Sharpe",
        "t-stat of excess",
        "Beta to Nifty 500 (monthly)",
        "Turnover (x capital / yr)",
    ):
        return f"{x:.2f}"
    if "Rs" in key:
        return f"{x:,.0f}"
    if key == "Trades":
        return f"{int(x)}"
    return f"{x:.2%}"


def run_long_only() -> None:
    """Leg split, variants A and B, trials 7-9 and results/long_only/summary_long_only.md."""
    OUT.mkdir(parents=True, exist_ok=True)
    universe.load()
    prices = universe.PRICES
    with open(RESULTS_DIR / "chosen_variant.json") as f:
        months = json.load(f)["formation_months"]
    dates = universe.formation_dates(prices.index)
    selections, _ = selections_for(dates, months)
    next_date = dict(zip(dates, dates[1:] + [prices.index[-1]], strict=True))
    ew, n50 = equal_weight_nifty500(), nifty50()
    n500 = pd.read_csv(DATA_DIR / "nifty500_tri.csv", index_col=0, parse_dates=True).iloc[:, 0]
    n500 = n500.reindex(prices.index).ffill()

    date_cols = ["formation_date", "entry_date", "exit_date"]
    trades = pd.read_csv(RESULTS_DIR / "trades.csv", parse_dates=date_cols)
    for col in date_cols:
        trades[col] = pd.to_datetime(trades[col], format="mixed").dt.normalize()
    trades["period"] = trades.period.replace({"holdout": "seen holdout"})

    legs = leg_split(trades[trades.period == "development"], selections, ew)
    check = legs.groupby(["formation_date", "pair", "entry_date"]).agg(
        legs=("gross_pnl", "sum"), trade=("trade_gross_pnl", "first")
    )
    bad = check[(check.legs - check.trade).abs() > 1]
    if len(bad):
        detail = bad.join(legs.set_index(["formation_date", "pair", "entry_date"])[["exit_reason"]])
        raise SystemExit(
            "Leg P&L does not add up to the rebuild's trade P&L:\n" + detail.head(10).to_string()
        )
    legs.drop(columns="trade_gross_pnl").round(6).to_csv(OUT / "leg_split.csv", index=False)
    leg_stats = leg_table(legs)
    logger.info(
        "Leg split, development trades (12-month formation, entry |z| > 2.0):\n%s",
        leg_stats.round(4).to_string(),
    )

    pnl_a_parts, pnl_bench_parts, rows_a, slots = [], [], [], []
    for day in dates:
        a, b, rows, s = switching_window(selections[day], day, next_date[day])
        pnl_a_parts.append(a)
        pnl_bench_parts.append(b)
        rows_a += rows
        slots += s
    pnl_a, pnl_bench = pd.concat(pnl_a_parts), pd.concat(pnl_bench_parts)
    trades_a, slots = pd.DataFrame(rows_a), pd.DataFrame(slots)
    trades_a.round(4).to_csv(OUT / "trades_A.csv", index=False)

    pnl_hedged, pnl_unhedged, trades_b = cheap_leg(trades, selections, n50)
    trades_b.round(4).to_csv(OUT / "trades_B.csv", index=False)

    # daily returns on Rs 10 lakh, per period (each period starts with fresh capital)
    results, month_rows = {}, []
    for period, (start, end) in PERIODS.items():
        idx = prices.index[(prices.index >= start) & (prices.index <= end)]
        r = {
            "A": returns(pnl_a.reindex(idx).fillna(0)),
            "A benchmark": returns(pnl_bench.reindex(idx).fillna(0)),
            "B": returns(pnl_hedged.reindex(idx).fillna(0)),
            "B-unhedged": returns(pnl_unhedged.reindex(idx).fillna(0)),
            "EW Nifty 500": ew[idx],
        }
        ta = trades_a[pd.to_datetime(trades_a.date).between(start, end)]
        tb = trades_b[trades_b.period == period]
        cash = pd.Series(0.0, idx)
        results[period] = {
            "A (vs 50/50 buy-and-hold)": metrics(
                r["A"], r["A benchmark"], ta.traded_value.sum(), ta.costs.sum(), n500
            ),
            "A benchmark: 50/50 buy-and-hold (vs cash)": metrics(
                r["A benchmark"], cash, 0, 0, n500
            ),
            "B hedged (vs cash)": metrics(
                r["B"],
                cash,
                tb.traded_value_stock.sum() + tb.traded_value_hedge.sum(),
                tb.stock_costs.sum() + tb.hedge_costs.sum(),
                n500,
            ),  # fmt: skip
            "B-unhedged (vs EW Nifty 500)": metrics(
                r["B-unhedged"],
                r["EW Nifty 500"],
                tb.traded_value_stock.sum(),
                tb.stock_costs.sum(),
                n500,
            ),  # fmt: skip
            "EW Nifty 500 (vs cash)": metrics(r["EW Nifty 500"], cash, 0, 0, n500),
        }
        results[period]["_daily"] = r
        mm = pd.DataFrame({k: monthly(x) for k, x in r.items()})
        mm.insert(2, "A minus benchmark", mm["A"] - mm["A benchmark"])
        mm.insert(0, "period", period)
        month_rows.append(mm)
    monthly_df = pd.concat(month_rows)
    monthly_df.index = monthly_df.index.strftime("%Y-%m")
    monthly_df.index.name = "month"
    monthly_df.round(6).to_csv(OUT / "monthly_returns.csv")

    # trials 7-9 on development only, then the deflated Sharpe over all 9
    trial_log = pd.read_csv(RESULTS_DIR / "trial_log.csv")
    trial_log = trial_log[trial_log.trial <= 6].copy()
    trial_log["variant"] = "long-short pairs (rebuild)"
    dev = results["development"]["_daily"]
    for name, key in VARIANT_KEYS.items():
        r = dev[key]
        equity = (1 + r).cumprod()
        n_trades = (
            len(trades_a[pd.to_datetime(trades_a.date) <= "2022-12-31"])
            if key == "A"
            else int((trades_b.period == "development").sum())
        )
        trial_log.loc[len(trial_log)] = {
            "trial": len(trial_log) + 1, "formation_months": months, "entry_z": SWITCH_Z,
            "dev_sharpe": round(r.mean() / r.std() * np.sqrt(TRADING_DAYS), 3),
            "dev_cagr": round(equity.iloc[-1] ** (TRADING_DAYS / len(r)) - 1, 4),
            "dev_max_dd": round((equity / equity.cummax() - 1).min(), 4),
            "trades": n_trades, "dev_sharpe_fo": np.nan, "daily_sr": r.mean() / r.std(),
            "run_at": datetime.now().isoformat(timespec="seconds"), "chosen": False,
            "variant": name,
        }  # fmt: skip
    trial_log["best_of_9_on_dev"] = trial_log.dev_sharpe == trial_log.dev_sharpe.max()
    trial_log.to_csv(RESULTS_DIR / "trial_log.csv", index=False)
    best = trial_log.loc[trial_log.dev_sharpe.idxmax()]
    key = VARIANT_KEYS.get(best.variant)
    if key:
        best_ret = dev[key]
    else:
        daily = pd.read_csv(RESULTS_DIR / "daily_returns.csv", index_col=0, parse_dates=True)
        best_ret = daily.query("period == 'development'").all_pairs
    dsr, sr0 = deflated_sharpe(best_ret, trial_log.daily_sr.values)
    seen = None
    if key:
        r = results["seen holdout"]["_daily"][key]
        seen = r.mean() / r.std() * np.sqrt(TRADING_DAYS)

    write_summary(leg_stats, results, slots, trial_log, best, dsr, sr0, seen)


def write_summary(legs, results, slots, trial_log, best, dsr, sr0, seen) -> None:
    """Write results/long_only/summary_long_only.md."""
    lines = [
        "# Long-only pairs on the point-in-time Nifty 500",
        "",
        "Development 2011-2022 is the decision period. 2023 to Nov 2026 is a **seen holdout**: the "
        "rebuild already looked at it, so it is not out of sample.",
        "",
        "## Step 1: leg split of the rebuild's development trades",
        "",
        "Each leg is Rs 50,000. Excess is measured against the equal-weight Nifty 500 "
        "(point-in-time members) over the same holding days. For the short leg, excess = EW return "
        "− stock return, so it is positive when the shorted stock lagged the market.",
        "",
    ]
    leg_text = legs.copy().apply(
        lambda col: [
            fmt(k, x) if "Rs" in k or k in ("Trades",) or "t-stat" in k else f"{x:.2%}"
            for k, x in col.items()
        ]
    )
    lines += [md(leg_text.rename_axis("Metric")), ""]

    for period in PERIODS:
        t = pd.DataFrame({k: v for k, v in results[period].items() if k != "_daily"})
        t = t.apply(lambda col: [fmt(k, x) for k, x in col.items()]).rename_axis("Metric")
        lines += [f"## {period.capitalize()}", "", md(t), ""]

    s = slots.assign(
        excess=slots.return_A - slots.return_benchmark,
        period=np.where(
            pd.to_datetime(slots.formation_date) < pd.Timestamp("2022-12-01"),
            "development",
            "seen holdout",
        ),
    )
    lines += [
        "## A minus benchmark per slot (one slot = one pair for one 6-month window)",
        "",
        "| Period | Slot-windows | Mean excess per window | t-stat | "
        "Share of slots beating benchmark |",
        "|---|---:|---:|---:|---:|",
    ]
    for p, e in s.groupby("period").excess:
        t_stat = e.mean() / e.std() * np.sqrt(len(e))
        lines.append(f"| {p} | {len(e)} | {e.mean():.2%} | {t_stat:.2f} | {(e > 0).mean():.0%} |")
    lines += [
        "",
        "## Trials and deflated Sharpe",
        "",
        md(trial_log.drop(columns=["daily_sr", "run_at"]), index=False),
        "",
        f"Best development variant out of 9: **{best.variant}** (trial {int(best.trial)}), with a "
        f"development Sharpe of {best.dev_sharpe:.2f}. The best of 9 zero-skill trials would be "
        f"expected to reach {sr0:.2f}. **Deflated Sharpe: {dsr:.2f}**."
        + (f" Its Sharpe on the seen holdout was {seen:.2f}." if seen is not None else ""),
        "",
        "Trials 1-6 enter at |z| > 1.5, 2.0 or 2.5. For trials 7-9, `entry_z` is the switch/entry "
        "threshold (2.0). Ranking by raw Sharpe mixes market-neutral and long-only variants, so A "
        "ranks first largely because of market beta.",
        "",
    ]
    d, h = results["development"], results["seen holdout"]
    ad, ah = d["A (vs 50/50 buy-and-hold)"], h["A (vs 50/50 buy-and-hold)"]
    bd, bh = d["B hedged (vs cash)"], h["B hedged (vs cash)"]
    ud = d["B-unhedged (vs EW Nifty 500)"]
    bench_sharpe = d["A benchmark: 50/50 buy-and-hold (vs cash)"]["Sharpe"]
    lines += [
        "## Conclusion",
        "",
        "**No edge.** A (pair switching) beat its 50/50 buy-and-hold benchmark by "
        f"{ad['Excess vs benchmark (% / month)']:.2%} a month in development "
        f"(t = {ad['t-stat of excess']:.2f}) and by {ah['Excess vs benchmark (% / month)']:.2%} a "
        f"month in the seen holdout (t = {ah['t-stat of excess']:.2f}). Its Sharpe "
        f"({ad['Sharpe']:.2f} in development) is almost all market exposure: the buy-and-hold "
        f"benchmark alone had {bench_sharpe:.2f}, and the deflated Sharpe over 9 trials is "
        f"{dsr:.2f}. B (cheap leg, hedged with Nifty futures) had a Sharpe of {bd['Sharpe']:.2f} "
        "in "
        f"development and {bh['Sharpe']:.2f} in the seen holdout. B-unhedged trailed the "
        f"equal-weight Nifty 500 by {-ud['Excess vs benchmark (% / month)']:.2%} a month in "
        "development, mostly because it is in cash much of the time (beta "
        f"{ud['Beta to Nifty 500 (monthly)']:.2f}).",
        "",
        "**Was the money in the long leg?** In rupees, yes: the long leg made Rs "
        f"{legs.loc['Total net P&L (Rs)', 'long']:,.0f} net and the short leg lost Rs "
        f"{-legs.loc['Total net P&L (Rs)', 'short']:,.0f}. But that is the market rising in "
        "2011-2022. Measured against the equal-weight Nifty 500 over the same days, the long leg "
        f"added only {legs.loc['Mean excess vs EW Nifty 500 per trade', 'long']:.2%} a trade "
        f"(t = {legs.loc['t-stat of excess', 'long']:.2f}). The short leg added "
        f"{legs.loc['Mean excess vs EW Nifty 500 per trade', 'short']:.2%} "
        f"(t = {legs.loc['t-stat of excess', 'short']:.2f}), because the rich stock tended to lag. "
        "So the little relative-value signal there is came mostly from the short leg, which is "
        "exactly the leg a long-only version drops. The trade-level t-stats treat overlapping "
        "trades "
        "as independent, so they overstate significance.",
        "",
    ]
    (OUT / "summary_long_only.md").write_text("\n".join(lines))
    logger.info("Wrote %s", OUT / "summary_long_only.md")
