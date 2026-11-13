from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from momentum.extract.prices import (
    extract_nse,
    read_corp_actions,
    read_securities,
    trading_days,
)
from momentum.transform.momentum import forward_returns, score_date
from momentum.transform.prices import load_raw, nse_series, parse_actions
from momentum.transform.split import holdout_start, signal_dates


def nw_t(x, lags: int) -> float:
    """Newey-West t-statistic of the mean (Bartlett weights)."""
    # mean / Newey-West standard error (Bartlett weights)
    x = pd.Series(x).dropna().values
    n = len(x)
    if n < 3:
        return np.nan
    e = x - x.mean()
    var = e @ e / n
    for k in range(1, lags + 1):
        var += 2 * (1 - k / (lags + 1)) * (e[k:] @ e[:-k]) / n
    return x.mean() / np.sqrt(var / n)


def summarise(series, lags: int) -> dict:
    """Mean, t-statistic, hit rate and count of a series."""
    s = pd.Series(series).dropna()
    return dict(
        mean=s.mean(),
        nw_t=nw_t(s, lags),
        share_positive=(s > 0).mean(),
        std=s.std(),
        icir=s.mean() / s.std(),
        icir_annual=s.mean() / s.std() * np.sqrt(12),
        months=len(s),
    )


def monthly_ic(scores: pd.DataFrame, rets: pd.DataFrame, col: str) -> pd.Series:
    """Monthly rank IC of a score with forward returns."""
    m = scores.merge(rets, left_on=["date", "file_id"], right_on=["signal_date", "file_id"])
    # Spearman = Pearson correlation of ranks
    return m.groupby("date").apply(
        lambda g: g[col].rank().corr(g["ret"].rank()) if len(g) > 10 else np.nan,
        include_groups=False,
    )


def bucket_returns(scores: pd.DataFrame, rets: pd.DataFrame, q: int) -> pd.DataFrame:
    """Mean forward return of score quantile buckets each month."""
    # equal-weight return per score bucket each month; bucket q = highest scores
    m = scores.merge(rets, left_on=["date", "file_id"], right_on=["signal_date", "file_id"]).dropna(
        subset=["score", "ret"]
    )
    m["bucket"] = m.groupby("date")["score"].transform(
        lambda s: pd.qcut(s.rank(method="first"), q, labels=False) + 1
    )
    b = m.groupby(["date", "bucket"])["ret"].mean().unstack()
    b["universe"] = m.groupby("date")["ret"].mean()
    return b


def dev_inputs(cfg: dict) -> tuple:
    """Development-period scores, prices and returns."""
    scores = pd.read_parquet(Path(cfg["paths"]["processed_factors"]) / "momentum_scores.parquet")
    scores = scores[(scores["period"] == "development") & scores["eligible"]]
    adj = pd.read_parquet(Path(cfg["paths"]["processed_prices"]) / "adj_close.parquet")
    return scores, adj


def dev_returns(cfg: dict, adj: pd.DataFrame, h: int) -> pd.DataFrame:
    """Development forward returns over horizon h."""
    # forward returns for development signal months whose return period starts before the holdout
    r = forward_returns(cfg, adj, h, before=holdout_start(cfg))
    dev = signal_dates(cfg)
    dev = set(dev.loc[dev["period"] == "development", "signal_date"])
    return r[r["signal_date"].isin(dev)]


def survivor_panel(cfg: dict) -> tuple:
    """Prices of today's members only (the survivorship comparison)."""
    # today's Nifty 500 list over the whole window (the old method): NSE closes from 2010
    # adjusted with NSE actions
    out = Path(cfg["paths"]["results"]) / "phase2"
    cache = out / "survivor_prices.parquet"
    if cache.exists():
        p = pd.read_parquet(cache)
        return p.xs("adj", axis=1, level=0), p.xs("value", axis=1, level=0)
    spells = pd.read_csv(Path(cfg["paths"]["processed_universe"]) / "membership.csv")
    today = set(spells.loc[spells["end_date"].isna() & spells["eligible"], "stock_id"])
    sec = read_securities(cfg)
    sec = sec[sec["stock_id"].isin(today)].copy()
    sec["start"] = pd.Timestamp(cfg["prices"]["start"])
    extract_nse(cfg, sec, out_name="nse_full_today")
    adj, value = {}, {}
    for _, r in sec.iterrows():
        raw = load_raw(cfg, "nse_full_today", r["file_id"])
        if raw is None:
            continue
        ev = parse_actions(read_corp_actions(cfg, [s for s, _, _ in r["history"]]))
        _, tr, _ = nse_series(raw, ev)
        adj[r["file_id"]] = tr
        value[r["file_id"]] = raw.loc[raw["qty"] > 0, "value"].astype(float)
    adj, value = pd.DataFrame(adj).sort_index(), pd.DataFrame(value).sort_index()
    out.mkdir(parents=True, exist_ok=True)
    pd.concat({"adj": adj, "value": value}, axis=1).to_parquet(cache)
    return adj, value


def survivor_scores(cfg: dict, adj: pd.DataFrame, value: pd.DataFrame) -> pd.DataFrame:
    """Momentum scores on today's members only."""
    spells = pd.read_csv(Path(cfg["paths"]["processed_universe"]) / "membership.csv")
    today = spells[spells["end_date"].isna() & spells["eligible"]].drop_duplicates("stock_id")
    sec = pd.read_csv(Path(cfg["paths"]["processed_prices"]) / "securities.csv")[
        ["stock_id", "file_id", "isin"]
    ]
    members = today[["stock_id"]].merge(sec, on="stock_id")
    members["symbol"], members["excluded_reason"] = members["stock_id"], ""
    excl = pd.read_csv(
        Path(cfg["paths"]["processed_prices"]) / "lookback_exclusions.csv",
        parse_dates=["date"],
    )
    days = trading_days(cfg)
    sd = signal_dates(cfg)
    frames = [
        score_date(cfg, r["signal_date"], adj, value, members, excl, days)
        for _, r in sd[sd["period"] == "development"].iterrows()
    ]
    s = pd.concat(frames, ignore_index=True)
    return s[s["eligible"]]


def run_diagnostics(cfg: dict) -> dict:
    """Phase 2: IC, decay, quantile spreads, liquidity and survivorship."""
    d = cfg["diagnostics"]
    lags = d["newey_west_lags"]
    out = Path(cfg["paths"]["results"]) / "phase2"
    out.mkdir(parents=True, exist_ok=True)
    scores, adj = dev_inputs(cfg)
    rets = dev_returns(cfg, adj, 1)
    res = {}

    # IC
    ic = pd.DataFrame({c: monthly_ic(scores, rets, c) for c in ["score", "z_12_1", "z_6_1"]})
    ic.to_csv(out / "ic_monthly.csv")
    res["ic_summary"] = pd.DataFrame({c: summarise(ic[c], lags) for c in ic}).T
    res["ic_by_year"] = ic.groupby(ic.index.year).mean()

    # quintiles and deciles
    for q in d["quantiles"]:
        b = bucket_returns(scores, rets, q)
        b.to_csv(out / f"buckets_{q}_monthly.csv")
        means = b[list(range(1, q + 1))].mean()
        tmb, tmu = b[q] - b[1], b[q] - b["universe"]
        res[f"buckets_{q}"] = pd.DataFrame({"mean": b.mean(), "vol": b.std(), "months": b.count()})
        res[f"spread_{q}"] = pd.DataFrame(
            {
                k: dict(
                    mean=v.mean(),
                    nw_t=nw_t(v, lags),
                    share_positive=(v > 0).mean(),
                    months=v.count(),
                )
                for k, v in [("top_minus_bottom", tmb), ("top_minus_universe", tmu)]
            }
        ).T
        res[f"spread_{q}"]["monotonicity"] = pd.Series(range(1, q + 1)).corr(
            means.reset_index(drop=True).rank()
        )
        res[f"spread_{q}_by_year"] = (
            pd.DataFrame({"top_minus_bottom": tmb, "top_minus_universe": tmu})
            .groupby(b.index.year)
            .mean()
        )
        if q == 5:
            res["tmu_series"] = tmu

    # IC decay: single-month returns h periods ahead, development periods only
    decay = {}
    for h in d["decay_horizons"]:
        s = monthly_ic(scores, dev_returns(cfg, adj, h), "score")
        decay[h] = dict(
            mean=s.mean(),
            nw_t=nw_t(s, lags),
            se=s.std() / np.sqrt(s.count()),
            months=s.count(),
        )
    res["ic_decay"] = pd.DataFrame(decay).T
    # half-life from the peak horizon on (log-linear fit on positive mean ICs)
    dec = res["ic_decay"]["mean"]
    tail = dec.loc[dec.idxmax() :]
    tail = tail[tail > 0]
    res["half_life"], res["decay_peak"] = np.nan, int(dec.idxmax())
    if len(tail) >= 3:
        slope = np.polyfit(tail.index.values.astype(float), np.log(tail.values), 1)[0]
        if slope < 0:
            res["half_life"] = np.log(2) / -slope

    # liquidity terciles (point-in-time 63-day median traded value)
    liq = pd.read_parquet(Path(cfg["paths"]["processed_liquidity"]) / "liquidity.parquet")
    sc = scores.assign(month_end=scores["date"] + pd.offsets.MonthEnd(0)).merge(
        liq,
        left_on=["month_end", "file_id"],
        right_on=["date", "file_id"],
        suffixes=("", "_liq"),
    )
    sc["tercile"] = sc.groupby("date")["median_traded_value"].transform(
        lambda v: pd.qcut(v.rank(method="first"), d["liquidity_terciles"], labels=False) + 1
    )
    rows = {}
    for t, g in sc.groupby("tercile"):
        b = bucket_returns(g, rets, 5)
        v = b[5] - b[1]
        rows[
            f"tercile {int(t)} "
            f"({'least' if t == 1 else 'most' if t == d['liquidity_terciles'] else 'middle'} "
            "liquid)"
        ] = dict(
            mean=v.mean(),
            nw_t=nw_t(v, lags),
            share_positive=(v > 0).mean(),
            months=v.count(),
            median_traded_value_cr=g["median_traded_value"].median() / 1e7,
        )
    res["liquidity"] = pd.DataFrame(rows).T

    # survivorship: today's list for all dates vs point in time
    sadj, sval = survivor_panel(cfg)
    ss = survivor_scores(cfg, sadj, sval)
    srets = dev_returns(cfg, sadj, 1)
    sic = monthly_ic(ss, srets, "score")
    sb = bucket_returns(ss, srets, 5)
    pit_b = bucket_returns(scores, rets, 5)
    res["survivorship"] = pd.DataFrame(
        {
            "point-in-time Nifty 500": dict(
                ic_mean=ic["score"].mean(),
                ic_nw_t=nw_t(ic["score"], lags),
                q5_minus_q1=(pit_b[5] - pit_b[1]).mean(),
                q5_minus_q1_t=nw_t(pit_b[5] - pit_b[1], lags),
                universe_return=pit_b["universe"].mean(),
                stocks_per_month=scores.groupby("date").size().median(),
            ),
            "today's list for all dates": dict(
                ic_mean=sic.mean(),
                ic_nw_t=nw_t(sic, lags),
                q5_minus_q1=(sb[5] - sb[1]).mean(),
                q5_minus_q1_t=nw_t(sb[5] - sb[1], lags),
                universe_return=sb["universe"].mean(),
                stocks_per_month=ss.groupby("date").size().median(),
            ),
        }
    ).T

    for k, v in res.items():
        if isinstance(v, pd.DataFrame):
            v.to_csv(out / f"{k}.csv")
    res["tmu_series"].to_csv(out / "top_minus_universe_monthly.csv")
    res["months"] = (
        scores["date"].min(),
        rets["signal_date"].max(),
        rets["signal_date"].nunique(),
    )
    return res
