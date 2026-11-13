from __future__ import annotations

import logging
import math
from pathlib import Path
from statistics import NormalDist

import numpy as np
import pandas as pd

from momentum.extract.prices import read_index, trading_days
from momentum.transform.portfolio import select, select_all
from momentum.transform.split import (
    guard,
    holdout_start,
    signal_dates,
    special_sessions,
)

logger = logging.getLogger(__name__)


PRESETS = {
    "primary": dict(kind="momentum", signal="score", n=30, buffer=45, rebalance="monthly"),
    "quarterly": dict(kind="momentum", signal="score", n=30, buffer=45, rebalance="quarterly"),
    "equal_weight": dict(kind="equal_weight", rebalance="monthly"),
}


def load_market(cfg: dict, periods=("development",)) -> dict:
    """Prices, liquidity, scores, eligibility and sectors for a backtest."""
    pp = Path(cfg["paths"]["processed_prices"])
    days = trading_days(cfg)
    adj = pd.read_parquet(pp / "adj_close.parquet").reindex(days)
    # unadjusted demerger/rights/corporate-action ex-dates: remove that day's drop (ex-date
    # return set to 0)
    over = pd.read_csv(pp / "return_overrides.csv", parse_dates=["date"])
    for _, o in over.iterrows():
        f = o["file_id"]
        if f not in adj.columns:
            continue
        s = adj[f].dropna()
        on, before = s.index[s.index >= o["date"]], s.index[s.index < o["date"]]
        if len(on) and len(before):
            adj.loc[adj.index >= on[0], f] /= s[on[0]] / s[before[-1]]
    raw = pd.read_parquet(pp / "close.parquet").reindex(days)
    value = pd.read_parquet(pp / "traded_value.parquet").reindex(days)
    liq = value.rolling(
        cfg["liquidity"]["window_days"], min_periods=cfg["liquidity"]["min_obs"]
    ).median()
    sec = pd.read_csv(pp / "securities.csv")
    ind = pd.read_csv(Path(cfg["paths"]["processed_universe"]) / "industry.csv")
    sector = dict(
        sec.merge(ind[["stock_id", "industry"]], on="stock_id", how="left")[["file_id", "industry"]]
        .fillna("Unclassified")
        .values
    )
    names = dict(zip(sec["file_id"], sec["stock_id"], strict=False))
    isin = dict(zip(sec["file_id"], sec["isin"].fillna(""), strict=False))
    scores = pd.read_parquet(Path(cfg["paths"]["processed_factors"]) / "momentum_scores.parquet")
    scores = scores[scores["period"].isin(periods) & scores["eligible"]].sort_values(
        ["date", "rank"]
    )
    return dict(
        days=days,
        adj=adj,
        raw=raw,
        liq=liq,
        sector=sector,
        names=names,
        isin=isin,
        scores=scores,
        exits=exit_dates(cfg, adj),
    )


def exit_dates(cfg: dict, adj: pd.DataFrame) -> pd.Series:
    """Last price date of each delisted security."""
    # a holding is sold at its last close before it stops trading for good, or before a gap
    # longer than the suspension limit
    pp = Path(cfg["paths"]["processed_prices"])
    out = {}
    delist = pd.read_csv(pp / "delistings.csv", parse_dates=["last_price_date"])
    for f, d in zip(delist["file_id"], delist["last_price_date"], strict=False):
        out.setdefault(d, []).append((f, "delisted"))
    limit = pd.Timedelta(days=cfg["events"]["suspension_max_days"])
    for f in adj.columns:
        s = adj[f].dropna().index
        if len(s) < 2:
            continue
        for a, b in zip(s[:-1], s[1:], strict=False):
            if b - a > limit:
                out.setdefault(a, []).append((f, "stopped trading (gap over the suspension limit)"))
        out.setdefault(s[-1], []).append((f, "end of price data"))
    return out


def trade_costs(cfg: dict, side: str, value: float, liq_value, scenario: str) -> dict:
    """Cost of one trade, by item: STT, exchange, SEBI, stamp, GST, DP, slippage."""
    c, sc = (
        cfg["costs"],
        cfg["backtest"]["scenarios"][scenario] if isinstance(scenario, str) else scenario,
    )
    out = dict(
        slippage=0.0,
        brokerage=0.0,
        stt=0.0,
        exchange=0.0,
        sebi=0.0,
        stamp=0.0,
        gst=0.0,
        dp=0.0,
    )
    bps = next(
        b
        for floor, b in c["slippage_tiers"]
        if (liq_value if not np.isnan(liq_value) else 0) >= floor * 1e7
    )
    out["slippage"] = value * bps / 1e4 * sc["slippage_multiple"]
    if sc["statutory"]:
        out["brokerage"] = value * c["brokerage"]
        out["stt"] = value * c["stt"]
        out["exchange"] = value * c["exchange_txn"]
        out["sebi"] = value * c["sebi_fee"]
        out["stamp"] = value * c["stamp_duty_buy"] if side == "buy" else 0.0
        out["gst"] = c["gst"] * (out["brokerage"] + out["exchange"] + out["sebi"])
        out["dp"] = c["dp_charge_per_sell"] if side == "sell" else 0.0
    out["total"] = sum(out.values())
    out["bps"] = bps
    return out


def month_window(cfg: dict, months=None) -> tuple:
    """First and last signal month of a period."""
    # signal months (first, last); default: the development period
    sp = cfg["split"]
    return months or (sp["first_signal_month"], sp["last_dev_month"])


def rebalance_dates(cfg: dict, params: dict, months=None) -> list:
    """Signal dates on which the strategy rebalances."""
    first, last = month_window(cfg, months)
    sd = signal_dates(cfg)
    sd = sd[(sd.index >= first) & (sd.index <= last)]
    if params["rebalance"] == "quarterly":
        keep = pd.PeriodIndex(sd.index, freq="M").month.isin(cfg["backtest"]["quarterly_months"])
        keep[0] = True  # the first portfolio is formed at the first signal month of the window
        sd = sd[keep]
    return sd


def end_date(cfg: dict, months=None) -> pd.Timestamp:
    """Last execution day of a period."""
    # the execution close after the last signal month's following signal date: the end of its
    # holding period
    first, last = month_window(cfg, months)
    sd = signal_dates(cfg)
    nxt = sd[sd.index > last]
    if nxt.empty:
        raise ValueError(f"no complete holding period after signal month {last}")
    return nxt["execution_date"].iloc[0]


def ranked_at(m: dict, t, params: dict) -> pd.DataFrame:
    """Eligible stocks at signal date t, ranked by the strategy's score."""
    # eligible stocks at t ordered by the chosen signal; rank 1 = best
    g = (
        m["scores"][m["scores"]["date"] == t]
        .sort_values(params.get("signal", "score"), ascending=False)
        .copy()
    )
    g["rank"] = np.arange(1, len(g) + 1)
    return g


def simulate(
    cfg: dict,
    m: dict,
    strategy,
    scenario: str,
    whole_shares=False,
    months=None,
    capital=None,
    participation=None,
) -> dict:
    """Daily simulation with cash, costs, buffer, sector cap and delistings."""
    params = PRESETS[strategy] if isinstance(strategy, str) else strategy
    days, adj, raw, liq = m["days"], m["adj"], m["raw"], m["liq"]
    marks = adj.ffill()
    end = end_date(cfg, months)
    reb = rebalance_dates(cfg, params, months)
    guard(cfg, reb["execution_date"])
    cap = math.floor(cfg["portfolio"]["sector_cap"] * params.get("n", 30))
    by_exec = {r["execution_date"]: r["signal_date"] for _, r in reb.iterrows()}
    start = reb["execution_date"].min()
    sim_days = days[(days >= start) & (days <= end)]
    units, cash = {}, float(capital or cfg["backtest"]["capital"])
    equity, pnl_by, trades, holdings = [], {}, [], []
    prev = None

    def trade(d, f, side, value, reason, close_out=False):
        nonlocal cash
        price = adj.at[d, f]
        if close_out:
            value = units[f] * price
        lv = liq.at[d, f] if f in liq.columns else np.nan
        capped = False
        if participation is not None and reason == "rebalance":
            limit = participation * (lv if not np.isnan(lv) else 0.0)
            if value > limit:  # unfilled part: a buy stays in cash, a sell stays held
                value, capped, close_out = limit, True, False
        if whole_shares and side == "buy":
            rp = raw.at[d, f] if f in raw.columns and not np.isnan(raw.at[d, f]) else price
            value = math.floor(value / rp) * rp
        if value <= 0:
            return
        cost = trade_costs(cfg, side, value, lv, scenario)
        u = units[f] if close_out else value / price
        units[f] = units.get(f, 0.0) + (u if side == "buy" else -u)
        if close_out or units[f] <= 1e-12:
            units.pop(f)
        cash += (-value if side == "buy" else value) - cost["total"]
        trades.append(
            dict(
                date=d,
                file_id=f,
                isin=m["isin"].get(f, ""),
                symbol=m["names"].get(f, f),
                side=side,
                units=u,
                price=price,
                value=value,
                reason=reason,
                capped=capped,
                **{k: v for k, v in cost.items()},
            )
        )

    for d in sim_days:
        if prev is not None:  # mark to market
            for f, u in units.items():
                p0, p1 = marks.at[prev, f], marks.at[d, f]
                if not (np.isnan(p0) or np.isnan(p1)):
                    pnl_by[f] = pnl_by.get(f, 0.0) + u * (p1 - p0)
        for f, why in m["exits"].get(d, []):  # sold at the last close before it stops trading
            if f in units and d < end:
                trade(d, f, "sell", 0.0, why, close_out=True)
        if d in by_exec:
            t = by_exec[d]
            ranked = ranked_at(m, t, params)

            def tradable(f, d=d):
                return f in adj.columns and not np.isnan(adj.at[d, f])

            forced = [f for f in units if not tradable(f)]
            if params["kind"] == "equal_weight":
                picks = select_all(ranked, list(units), forced, m["sector"], cfg)
            else:
                picks = select(
                    ranked,
                    list(units),
                    forced,
                    m["sector"],
                    params["n"],
                    params["buffer"],
                    cap,
                )
            target = [f for f in picks if f in forced or tradable(f)]
            value_now = {f: u * marks.at[d, f] for f, u in units.items()}
            eq = cash + sum(value_now.values())
            free = eq - sum(value_now[f] for f in forced)
            buyable = [f for f in target if f not in forced]
            each = free / len(buyable) if buyable else 0.0
            for f in list(units):  # sells first
                if f in forced:
                    continue
                want = each if f in buyable else 0.0
                if want == 0.0:
                    trade(d, f, "sell", 0.0, "rebalance", close_out=True)
                elif value_now[f] > want + 1e-9:
                    trade(d, f, "sell", value_now[f] - want, "rebalance")
            need = {f: each - units.get(f, 0.0) * adj.at[d, f] for f in buyable}
            need = {f: v for f, v in need.items() if v > 1e-9}

            # buys sized so that cash (after their costs) does not go negative
            def rate(f, d=d):
                return trade_costs(
                    cfg, "buy", 1.0, liq.at[d, f] if f in liq.columns else np.nan, scenario
                )["total"]

            total = sum(v * (1 + rate(f)) for f, v in need.items())
            scale = min(1.0, cash / total) if total > 0 else 0.0
            for f, v in need.items():
                trade(d, f, "buy", v * scale, "rebalance")
            ranks = ranked.set_index("file_id")
            post = {f: u * marks.at[d, f] for f, u in units.items()}
            tot = cash + sum(post.values())
            for f, v in post.items():
                holdings.append(
                    dict(
                        signal_date=t,
                        execution_date=d,
                        file_id=f,
                        symbol=m["names"].get(f, f),
                        rank=ranks["rank"].get(f, np.nan),
                        score=ranks["score"].get(f, np.nan),
                        sector=m["sector"].get(f, "Unclassified"),
                        weight=v / tot,
                        forced=f in forced,
                    )
                )
        equity.append(
            (
                d,
                cash
                + sum(u * marks.at[d, f] for f, u in units.items() if not np.isnan(marks.at[d, f])),
                cash,
            )
        )
        prev = d
    eq = pd.DataFrame(equity, columns=["date", "equity", "cash"]).set_index("date")
    return dict(
        equity=eq,
        trades=pd.DataFrame(trades),
        holdings=pd.DataFrame(holdings),
        pnl_by=pd.Series(pnl_by, dtype=float),
    )


def exec_points(cfg: dict, months=None) -> tuple:
    """Execution days that bound each monthly holding period."""
    first, last = month_window(cfg, months)
    sd = signal_dates(cfg)
    sd = sd[(sd.index >= first) & (sd.index <= last)]
    return list(sd["execution_date"]) + [end_date(cfg, months)], sd.index


def period_returns(cfg: dict, eq: pd.DataFrame, months=None) -> pd.Series:
    """Monthly returns between execution points."""
    # returns between monthly execution closes of the window; the last period ends at the next
    # signal's execution
    ex, idx = exec_points(cfg, months)
    s = eq.reindex(ex).ffill()
    r = s.pct_change().iloc[1:]
    r.index = idx[: len(r)]
    return r


def index_returns(cfg: dict, name: str, months=None) -> tuple:
    """Monthly returns of an index between execution points."""
    tri = read_index(cfg, name, "tri")
    ex, idx = exec_points(cfg, months)
    s = tri.reindex(tri.index.union(ex)).ffill().reindex(ex)
    r = s.pct_change().iloc[1:]
    r.index = idx[: len(r)]
    return r, tri


def nw_t(x, lags: int) -> float:
    """Newey-West t-statistic of the mean."""
    from momentum.transform.diagnostics import nw_t as t

    return t(x, lags)


def ols_nw(y, x, lags: int) -> tuple:
    """Fit y = a + b x by OLS; returns coefficients and Newey-West t-statistics."""
    X = np.column_stack([np.ones(len(x)), x])
    beta = np.linalg.lstsq(X, y, rcond=None)[0]
    e = y - X @ beta
    n = len(y)
    S = (X * e[:, None]).T @ (X * e[:, None]) / n
    for k in range(1, lags + 1):
        g = (X[k:] * e[k:, None]).T @ (X[:-k] * e[:-k, None]) / n
        S += (1 - k / (lags + 1)) * (g + g.T)
    Q = np.linalg.inv(X.T @ X / n)
    se = np.sqrt(np.diag(Q @ S @ Q / n))
    return beta, beta / se


def drawdown(eq: pd.DataFrame) -> tuple:
    """Drawdown series of an equity curve."""
    s = eq["equity"]
    peak = s.cummax()
    dd = s / peak - 1
    trough = dd.idxmin()
    top = s.loc[:trough].idxmax()
    rec = s.loc[trough:][s.loc[trough:] >= s[top]]
    return dd, dict(
        max_drawdown=dd.min(),
        peak=top.date(),
        trough=trough.date(),
        recovered=rec.index[0].date() if len(rec) else None,
    )


def stats(cfg: dict, run: dict, r: pd.Series) -> dict:
    """Return, risk, turnover and cost statistics of one run."""
    eq, tr, hold = run["equity"], run["trades"], run["holdings"]
    rf = (1 + cfg["backtest"]["risk_free"]) ** (1 / 12) - 1
    years = (eq.index[-1] - eq.index[0]).days / 365.25
    cagr = (eq["equity"].iloc[-1] / eq["equity"].iloc[0]) ** (1 / years) - 1
    ex = r - rf
    down = np.sqrt((np.minimum(ex, 0) ** 2).mean())
    _, dd = drawdown(eq)
    avg_eq = eq["equity"].mean()
    out = dict(
        cagr=cagr,
        vol=r.std() * np.sqrt(12),
        sharpe=ex.mean() / ex.std() * np.sqrt(12),
        sortino=ex.mean() * 12 / (down * np.sqrt(12)) if down > 0 else np.nan,
        **dd,
        calmar=cagr / abs(dd["max_drawdown"]),
        worst_month=r.min(),
        worst_month_date=r.idxmin(),
        turnover=(tr["value"].sum() / 2 / avg_eq / years) if len(tr) else 0.0,
        avg_holdings=hold.groupby("execution_date").size().mean() if len(hold) else np.nan,
        end_equity=eq["equity"].iloc[-1],
        years=years,
    )
    if len(hold):
        sw = hold.groupby(["execution_date", "sector"])["weight"].sum()
        out["max_sector_weight"] = sw.max()
        out["mean_largest_sector_weight"] = sw.groupby(level=0).max().mean()
    if len(tr):
        for k in [
            "slippage",
            "stt",
            "exchange",
            "sebi",
            "stamp",
            "gst",
            "dp",
            "brokerage",
        ]:
            out[f"cost_{k}_pct_yr"] = tr[k].sum() / years / avg_eq
        out["cost_total_pct_yr"] = tr["total"].sum() / years / avg_eq
    return out


def deflated_sharpe(r_by_trial: dict, rf_m: float, trial):
    """Deflated Sharpe of `trial` given all trials' monthly returns (Bailey and Lopez de Prado).

    SR0 = std(trial SRs) * ((1 - g) Phi^-1(1 - 1/N) + g Phi^-1(1 - 1/(N e))), g = Euler's
    constant, is the expected best Sharpe of N zero-skill trials; the result is P(SR > SR0)
    after adjusting for sample length, skew and kurtosis.
    """
    # Bailey and Lopez de Prado; Sharpe ratios per month
    sr = {k: (v - rf_m).mean() / (v - rf_m).std() for k, v in r_by_trial.items()}
    n = len(sr)
    var = np.var(list(sr.values()), ddof=1) if n > 1 else 0.0
    g = 0.5772156649
    z = NormalDist().inv_cdf
    sr0 = math.sqrt(var) * ((1 - g) * z(1 - 1 / n) + g * z(1 - 1 / (n * math.e))) if n > 1 else 0.0
    x = r_by_trial[trial] - rf_m
    skew = ((x - x.mean()) ** 3).mean() / x.std(ddof=0) ** 3
    kurt = ((x - x.mean()) ** 4).mean() / x.std(ddof=0) ** 4
    s, t = sr[trial], len(x)
    dsr = NormalDist().cdf(
        (s - sr0) * math.sqrt(t - 1) / math.sqrt(1 - skew * s + (kurt - 1) / 4 * s**2)
    )
    return dict(
        trial=trial,
        sharpe_monthly=s,
        sharpe_annual=s * math.sqrt(12),
        trials=n,
        var_of_trial_sharpes=var,
        expected_max_sharpe_null=sr0,
        skew=skew,
        kurtosis=kurt,
        months=t,
        deflated_sharpe=dsr,
    )


STRATEGIES = ["primary", "quarterly", "equal_weight"]


def run_all(cfg: dict) -> tuple:
    """All Phase 3 runs (strategies x cost scenarios) and their tables."""
    out = Path(cfg["paths"]["results"]) / "phase3"
    out.mkdir(parents=True, exist_ok=True)
    m = load_market(cfg)
    runs, rets, rows = {}, {}, []
    for strat in STRATEGIES:
        for sc in cfg["backtest"]["scenarios"]:
            run = simulate(cfg, m, strat, sc)
            r = period_returns(cfg, run["equity"]["equity"])
            runs[(strat, sc)], rets[(strat, sc)] = run, r
            folder = out / f"{strat}_{sc}"
            folder.mkdir(exist_ok=True)
            run["equity"].to_csv(folder / "equity_daily.csv")
            r.rename("return").to_csv(folder / "returns_monthly.csv")
            run["trades"].to_csv(folder / "trades.csv", index=False)
            run["holdings"].to_csv(folder / "holdings.csv", index=False)
            run["pnl_by"].rename("pnl").to_csv(folder / "pnl_by_stock.csv", index_label="file_id")
            rows.append(dict(strategy=strat, scenario=sc, **stats(cfg, run, r)))
            logger.info(f"  {strat} {sc}: end equity {run['equity']['equity'].iloc[-1]:,.0f}")
    # whole shares, base costs
    for strat in ["primary", "quarterly"]:
        run = simulate(cfg, m, strat, "base", whole_shares=True)
        r = period_returns(cfg, run["equity"]["equity"])
        runs[(strat, "base_whole_shares")], rets[(strat, "base_whole_shares")] = run, r
        rows.append(dict(strategy=strat, scenario="base_whole_shares", **stats(cfg, run, r)))
    # break-even slippage multiple (statutory charges on)
    be = []
    for k in cfg["backtest"]["breakeven_multiples"]:
        sc = {"statutory": True, "slippage_multiple": k}
        rp = period_returns(cfg, simulate(cfg, m, "primary", sc)["equity"]["equity"])
        rq = period_returns(cfg, simulate(cfg, m, "quarterly", sc)["equity"]["equity"])
        re = period_returns(cfg, simulate(cfg, m, "equal_weight", sc)["equity"]["equity"])
        be.append(
            dict(
                multiple=k,
                primary_minus_ew=(rp - re).mean(),
                quarterly_minus_ew=(rq - re).mean(),
            )
        )
        logger.info(f"  break-even run x{k}")
    pd.DataFrame(be).to_csv(out / "breakeven_runs.csv", index=False)
    pd.DataFrame(rows).to_csv(out / "summary_stats.csv", index=False)
    return m, runs, rets, pd.DataFrame(rows), pd.DataFrame(be)


def run_checks(cfg: dict) -> list:
    """Backtest checks: costs, cash, sector cap, reconciliation."""
    from momentum.transform.portfolio import sector_cap_names
    from momentum.transform.split import HoldoutLocked

    out = Path(cfg["paths"]["results"]) / "phase3"
    folder = out / "primary_base"
    hold = pd.read_csv(folder / "holdings.csv", parse_dates=["signal_date", "execution_date"])
    trades = pd.read_csv(folder / "trades.csv", parse_dates=["date"])
    eq = pd.read_csv(folder / "equity_daily.csv", parse_dates=["date"], index_col="date")
    pnl = pd.read_csv(folder / "pnl_by_stock.csv")
    m = load_market(cfg)
    results = []

    # (1) one rebalance by hand
    p = cfg["portfolio"]
    dates = sorted(hold["execution_date"].unique())
    d = pd.Timestamp(dates[cfg["checks"]["rebalance_index"]])
    prev_d = pd.Timestamp(dates[cfg["checks"]["rebalance_index"] - 1])
    now = hold[hold["execution_date"] == d]
    sold_between = trades[
        (trades["date"] > prev_d) & (trades["date"] < d) & (trades["reason"] != "rebalance")
    ]["file_id"]
    before = [
        f for f in hold[hold["execution_date"] == prev_d]["file_id"] if f not in set(sold_between)
    ]
    forced = list(now[now["forced"]]["file_id"])
    t = now["signal_date"].iloc[0]
    ranked = m["scores"][m["scores"]["date"] == t].sort_values("rank")
    cap, picks, count = sector_cap_names(cfg), list(forced), {}
    for f in forced:
        count[m["sector"].get(f, "Unclassified")] = (
            count.get(m["sector"].get(f, "Unclassified"), 0) + 1
        )
    for _, r in ranked.iterrows():  # kept holdings first, in rank order
        sec = m["sector"].get(r["file_id"], "Unclassified")
        if (
            r["file_id"] in before
            and r["rank"] <= p["buffer_rank"]
            and r["file_id"] not in picks
            and len(picks) < p["holdings"]
            and count.get(sec, 0) < cap
        ):
            picks.append(r["file_id"])
            count[sec] = count.get(sec, 0) + 1
    kept = len(picks) - len(forced)
    for _, r in ranked.iterrows():  # then new names from the top
        sec = m["sector"].get(r["file_id"], "Unclassified")
        if len(picks) < p["holdings"] and r["file_id"] not in picks and count.get(sec, 0) < cap:
            picks.append(r["file_id"])
            count[sec] = count.get(sec, 0) + 1
    tradable = [f for f in picks if f in forced or not np.isnan(m["adj"].at[d, f])]
    same = set(tradable) == set(now["file_id"])
    logger.info(
        f"  rebalance by hand: signal {t:%Y-%m-%d}, execution {d:%Y-%m-%d}: {len(before)} held "
        f"before, {kept} kept by the "
        f"buffer, {len(picks) - kept - len(forced)} new, {len(forced)} untradable; largest sector "
        f"{max(count.values())} names (cap {cap})"
    )
    logger.info(
        "    chosen (rank, sector): "
        + ", ".join(
            f"{m['names'][f]} ({int(ranked.set_index('file_id')['rank'].get(f, 0))}, "
            f"{m['sector'].get(f, 'Unclassified')[:12]})"
            for f in picks[:8]
        )
        + ", ..."
    )
    results.append(
        (
            "backtest: one rebalance recomputed by hand (ranks, buffer, sector cap, chosen 30)",
            same,
            f"{d:%Y-%m-%d}, {len(tradable)} names, {'same' if same else 'different'} set",
        )
    )

    # (2) one trade's costs by hand
    c = cfg["costs"]
    tr = trades[(trades["side"] == "buy")].iloc[cfg["checks"]["trade_index"]]
    v = tr["value"]
    liq = m["liq"].at[tr["date"], tr["file_id"]]
    bps = next(
        b for floor, b in c["slippage_tiers"] if (0 if np.isnan(liq) else liq) >= floor * 1e7
    )
    hand = dict(
        slippage=v * bps / 1e4,
        stt=v * c["stt"],
        exchange=v * c["exchange_txn"],
        sebi=v * c["sebi_fee"],
        stamp=v * c["stamp_duty_buy"],
        gst=c["gst"] * (v * c["brokerage"] + v * c["exchange_txn"] + v * c["sebi_fee"]),
        dp=0.0,
        brokerage=v * c["brokerage"],
    )
    logger.info(
        f"  trade by hand: buy {tr['symbol']} on {tr['date']:%Y-%m-%d}, value Rs {v:,.2f}, 63-day "
        "median traded value "
        f"Rs {liq / 1e7:,.1f} crore -> {bps} bps"
    )
    for k, x in hand.items():
        logger.info(f"    {k}: by hand {x:,.4f}, engine {tr[k]:,.4f}")
    results.append(
        (
            "backtest: one trade's costs recomputed by hand",
            all(abs(hand[k] - tr[k]) < 1e-6 for k in hand),
            f"{tr['symbol']} {tr['date']:%Y-%m-%d}, total Rs {sum(hand.values()):,.2f}",
        )
    )

    # (3) equity reconciles
    start, end = cfg["backtest"]["capital"], eq["equity"].iloc[-1]
    implied = start + pnl["pnl"].sum() - trades["total"].sum()
    results.append(
        (
            "backtest: start capital + P&L - costs = end equity",
            abs(implied - end) < 1e-4 * start,
            f"{start:,.0f} + {pnl['pnl'].sum():,.0f} - {trades['total'].sum():,.0f} = "
            f"{implied:,.0f}; end {end:,.0f}",
        )
    )

    # (4) no trade on a special session (all strategies and scenarios)
    special = set(special_sessions(cfg)["date"])
    bad = 0
    for f in out.glob("*_*/trades.csv"):
        bad += pd.read_csv(f, parse_dates=["date"])["date"].isin(special).sum()
    results.append(
        (
            "backtest: no trade on a special session",
            bad == 0,
            f"{bad} trades on special sessions",
        )
    )

    # (5) no holdout return read
    first = holdout_start(cfg)
    last_mark = max(
        pd.read_csv(f, parse_dates=["date"])["date"].max() for f in out.glob("*_*/equity_daily.csv")
    )
    last_exec = hold["execution_date"].max()
    try:
        guard(cfg, [first])
        raised = False
    except HoldoutLocked:
        raised = True
    results.append(
        (
            "backtest: no holdout return is read",
            last_mark <= first and last_exec < first and raised,
            f"last mark {last_mark:%Y-%m-%d}, last rebalance {last_exec:%Y-%m-%d}, holdout starts "
            f"{first:%Y-%m-%d}, guard raises: {raised}",
        )
    )

    # (6) sector cap never breached at a rebalance (untradable holdings reported separately)
    worst, from_forced = 0, 0
    for folder in [out / "primary_base", out / "quarterly_base"]:
        h = pd.read_csv(folder / "holdings.csv")
        n = h.groupby(["execution_date", "sector"]).size()
        nf = h[~h["forced"]].groupby(["execution_date", "sector"]).size()
        worst = max(worst, nf.max())
        from_forced += int(((n > cap) & ~(nf.reindex(n.index).fillna(0) > cap)).sum())
    results.append(
        (
            "backtest: sector cap never breached at a rebalance",
            worst <= cap,
            f"most names in one sector {worst} (cap {cap}); breaches caused only by untradable "
            f"holdings: {from_forced}",
        )
    )
    return results
