from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
import pandas as pd

from momentum.extract.prices import trading_days
from momentum.transform.split import guard, signal_dates

logger = logging.getLogger(__name__)


def load_inputs(cfg: dict) -> tuple:
    """Prices, traded value, membership and exclusions for scoring."""
    pp, uni = (
        Path(cfg["paths"]["processed_prices"]),
        Path(cfg["paths"]["processed_universe"]),
    )
    adj = pd.read_parquet(pp / "adj_close.parquet")
    value = pd.read_parquet(pp / "traded_value.parquet")
    base = pd.read_csv(uni / "eligibility_base.csv", parse_dates=["date"])
    sec = pd.read_csv(pp / "securities.csv")[["stock_id", "file_id", "isin"]]
    base = base.drop(columns=["isin"]).merge(sec, on="stock_id", how="left")
    excl = pd.read_csv(pp / "lookback_exclusions.csv", parse_dates=["date"])
    return adj, value, base, excl


def asof_price(series: pd.Series, day: pd.Timestamp, days, max_stale: int) -> tuple:
    """(last close on or before `day`, its date); the price is NaN if older than max_stale days."""
    s = series.loc[:day].dropna()
    if s.empty:
        return np.nan, None
    last = s.index[-1]
    if days.get_loc(day) - days.searchsorted(last) > max_stale:
        return np.nan, last
    return s.iloc[-1], last


def score_date(
    cfg: dict, t: pd.Timestamp, adj: pd.DataFrame, value: pd.DataFrame, members, excl, days
) -> pd.DataFrame:
    """Momentum score of each eligible stock at signal date t."""
    # momentum scores at signal date t for the member rows given; uses only data up to t
    m, liq = cfg["momentum"], cfg["liquidity"]
    i = days.get_loc(t)
    lag = {k: days[i - m[k]] for k in ["skip_days", "short_days", "long_days"]}
    window = value.loc[:t].tail(liq["window_days"])
    rows = []
    for _, r in members.iterrows():
        f = r["file_id"]
        row = dict(
            date=t,
            stock_id=r["stock_id"],
            isin=r["isin"],
            file_id=f,
            symbol=r["symbol"],
            mom_12_1=np.nan,
            mom_6_1=np.nan,
            reason_if_not="",
        )
        s = adj[f] if isinstance(f, str) and f in adj.columns else None
        if r["excluded_reason"]:
            row["reason_if_not"] = r["excluded_reason"]
        elif s is None or pd.isna(s.get(t, np.nan)):
            row["reason_if_not"] = "no price on t"
        elif s.loc[:t].first_valid_index() > lag["long_days"]:
            row["reason_if_not"] = "less than 252 days of history"
        else:
            p21, _ = asof_price(s, lag["skip_days"], days, m["max_lag_staleness_days"])
            p126, _ = asof_price(s, lag["short_days"], days, m["max_lag_staleness_days"])
            p252, _ = asof_price(s, lag["long_days"], days, m["max_lag_staleness_days"])
            obs = window[f].notna().sum() if f in window.columns else 0
            med = window[f].median() if obs >= liq["min_obs"] else np.nan
            hit = excl[
                (excl["file_id"] == f) & (excl["date"] > lag["long_days"]) & (excl["date"] <= t)
            ]
            if np.isnan([p21, p126, p252]).any():
                row["reason_if_not"] = "no price on a lag date"
            elif not med >= m["min_liquidity_crore"] * 1e7:
                row["reason_if_not"] = "median traded value below threshold"
            elif len(hit):
                row["reason_if_not"] = hit["reason"].iloc[0]
            else:
                row.update(mom_12_1=p21 / p252 - 1, mom_6_1=p21 / p126 - 1)
        rows.append(row)
    df = pd.DataFrame(rows)
    df["eligible"] = df["reason_if_not"] == ""
    e = df["eligible"]
    lo, hi = m["clip_pct"]
    for col, z in [("mom_12_1", "z_12_1"), ("mom_6_1", "z_6_1")]:
        x = df.loc[e, col].clip(df.loc[e, col].quantile(lo), df.loc[e, col].quantile(hi))
        df.loc[e, z] = (x - x.mean()) / x.std(ddof=1)
    combo = (
        m["weights"]["z_12_1"] * df.loc[e, "z_12_1"] + m["weights"]["z_6_1"] * df.loc[e, "z_6_1"]
    )
    df.loc[e, "score"] = (combo - combo.mean()) / combo.std(ddof=1)
    df.loc[e, "rank"] = df.loc[e, "score"].rank(ascending=False, method="first")
    df.loc[~e, ["mom_12_1", "mom_6_1"]] = np.nan
    return df


def members_at(base: pd.DataFrame, t: pd.Timestamp) -> pd.DataFrame:
    """Members at the month-end of signal date t."""
    # point-in-time member rows for the month of signal date t (eligibility base is at
    # calendar month-ends)
    month_end = t + pd.offsets.MonthEnd(0)
    g = base[(base["date"] == month_end) & base["member"]].copy()
    g["excluded_reason"] = g["excluded_reason"].fillna("")
    return g


def build_scores(cfg: dict) -> pd.DataFrame:
    """Momentum scores at every signal date."""
    adj, value, base, excl = load_inputs(cfg)
    days = trading_days(cfg)
    sd = signal_dates(cfg)
    frames = []
    for _, r in sd.iterrows():
        frames.append(
            score_date(
                cfg,
                r["signal_date"],
                adj,
                value,
                members_at(base, r["signal_date"]),
                excl,
                days,
            ).assign(period=r["period"])
        )
    scores = pd.concat(frames, ignore_index=True)
    out = Path(cfg["paths"]["processed_factors"])
    out.mkdir(parents=True, exist_ok=True)
    cols = [
        "date",
        "isin",
        "symbol",
        "stock_id",
        "file_id",
        "mom_12_1",
        "mom_6_1",
        "z_12_1",
        "z_6_1",
        "score",
        "rank",
        "eligible",
        "reason_if_not",
        "period",
    ]
    scores[cols].to_parquet(out / "momentum_scores.parquet", index=False)
    n = scores[scores["eligible"]].groupby("date").size()
    logger.info(
        f"saved {out / 'momentum_scores.parquet'}: eligible per month min {n.min()}, median "
        f"{int(n.median())}, max {n.max()}"
    )
    return scores


def forward_returns(cfg: dict, adj: pd.DataFrame, h: int = 1, before=None) -> pd.DataFrame:
    """Return over the h-th period after each signal date.

    The period runs from the execution close after signal k+h-1 to the one after signal k+h.
    `before` keeps only periods starting before that date (development diagnostics pass the
    holdout start).
    """
    # `before`: keep only periods starting before this date (development diagnostics pass the
    # holdout start)
    sd = signal_dates(cfg)
    days = trading_days(cfg)
    overrides = pd.read_csv(
        Path(cfg["paths"]["processed_prices"]) / "return_overrides.csv",
        parse_dates=["date"],
    )
    stale = cfg["momentum"]["max_lag_staleness_days"]
    ex = list(sd["execution_date"])
    rows = []
    for k, t in enumerate(sd["signal_date"]):
        if k + h >= len(ex) or pd.isna(ex[k + h]):
            continue
        start, end = ex[k + h - 1], ex[k + h]
        rows.append((t, start, end))
    periods = pd.DataFrame(rows, columns=["signal_date", "start", "end"])
    if before is not None:
        periods = periods[periods["start"] < before]
    guard(cfg, periods["start"])
    on_days = adj.reindex(days)
    entry_px = on_days.ffill(limit=stale)  # entry: last close within `stale` trading days
    exit_px = (
        on_days.ffill()
    )  # exit: last close up to the end; a stock that stopped trading keeps its last close
    # suspended at the end of a period: valued at the first close after trading resumes (it
    # could not be sold)
    susp = pd.read_csv(
        Path(cfg["paths"]["processed_prices"]) / "suspensions.csv",
        parse_dates=["last_close", "resume"],
    )
    for _, x in susp[susp["file_id"].isin(exit_px.columns)].iterrows():
        gap = (exit_px.index > x["last_close"]) & (exit_px.index < x["resume"])
        exit_px.loc[gap, x["file_id"]] = (
            on_days.at[x["resume"], x["file_id"]] if x["resume"] in on_days.index else np.nan
        )
    out = []
    for _, p in periods.iterrows():
        r = exit_px.loc[p["end"]] / entry_px.loc[p["start"]] - 1
        for _, o in overrides[
            (overrides["date"] > p["start"]) & (overrides["date"] <= p["end"])
        ].iterrows():
            if o["file_id"] not in adj.columns or o["file_id"] not in r.index:
                continue
            s = adj[o["file_id"]].dropna()
            on, before = s.index[s.index >= o["date"]], s.index[s.index < o["date"]]
            if len(on) and len(before) and on[0] <= p["end"]:
                day_ret = s[on[0]] / s[before[-1]]
                r[o["file_id"]] = (1 + r[o["file_id"]]) / day_ret - 1  # ex-date return set to 0
        out.append(
            pd.DataFrame(
                {"signal_date": p["signal_date"], "file_id": r.index, "ret": r.values}
            ).dropna()
        )
    return pd.concat(out, ignore_index=True)


def run_checks(cfg: dict) -> list:
    """Momentum-score checks, including recomputation by hand."""
    from momentum.transform.prices import load_raw
    from momentum.transform.split import HoldoutLocked, holdout_start

    out = Path(cfg["paths"]["processed_factors"])
    scores = pd.read_parquet(out / "momentum_scores.parquet")
    adj, value, base, excl = load_inputs(cfg)
    days = trading_days(cfg)
    src = pd.read_csv(Path(cfg["paths"]["processed_prices"]) / "price_source.csv").set_index(
        "file_id"
    )
    m = cfg["momentum"]
    results = []

    # (1) one stock on one date by hand from its raw price file
    t = pd.Timestamp(cfg["checks"]["hand_date"])
    row = scores[(scores["date"] == t) & (scores["stock_id"] == cfg["checks"]["hand_stock"])].iloc[
        0
    ]
    f = row["file_id"]
    raw = load_raw(cfg, src.at[f, "price_source"].replace("nse_built", "nse"), f)
    i = days.get_loc(t)
    lags = {k: days[i - m[k]] for k in ["skip_days", "short_days", "long_days"]}
    px = (
        {k: raw.loc[:d, "adj_close"].dropna().iloc[-1] for k, d in lags.items()}
        if "adj_close" in raw
        else {}
    )
    logger.info(
        f"  hand recompute {row['stock_id']} at {t:%Y-%m-%d} from {src.at[f, 'price_source']} raw "
        "file:"
    )
    for k, d in lags.items():
        logger.info(f"    {k}: lag date {d:%Y-%m-%d}, adjusted close {px.get(k)}")
    h12 = px["skip_days"] / px["long_days"] - 1
    h6 = px["skip_days"] / px["short_days"] - 1
    logger.info(
        f"    mom_12_1 = {px['skip_days']:.4f} / {px['long_days']:.4f} - 1 = {h12:.6f} (stored "
        f"{row['mom_12_1']:.6f})"
    )
    logger.info(
        f"    mom_6_1  = {px['skip_days']:.4f} / {px['short_days']:.4f} - 1 = {h6:.6f} (stored "
        f"{row['mom_6_1']:.6f})"
    )
    results.append(
        (
            "momentum: hand recompute of one stock on one date",
            abs(h12 - row["mom_12_1"]) < 1e-9 and abs(h6 - row["mom_6_1"]) < 1e-9,
            f"{row['stock_id']} {t:%Y-%m-%d}",
        )
    )

    # (2) look-ahead: prices after t deleted, scores at t unchanged
    t = pd.Timestamp(cfg["checks"]["lookahead_date"])
    again = score_date(
        cfg, t, adj.loc[:t], value.loc[:t], members_at(base, t), excl, days[days <= t]
    )
    saved = scores[scores["date"] == t].set_index("file_id")["score"]
    again = again.set_index("file_id")["score"]
    same = saved.index.equals(again.index) and np.allclose(
        saved.values, again.values, equal_nan=True
    )
    results.append(
        (
            "momentum: no look-ahead (prices after t deleted, same scores at t)",
            same,
            f"{t:%Y-%m-%d}, {saved.notna().sum()} scores",
        )
    )

    # (3) a quarantined case and a demerger case are ineligible exactly while the date is in
    # the look-back
    ok, detail = True, []
    for reason in [
        "quarantined price event (suspect)",
        "unadjusted demerger/rights in look-back",
    ]:
        cases = excl[excl["reason"] == reason]
        for _, c in cases.iterrows():
            s = scores[scores["file_id"] == c["file_id"]]
            if s.empty:
                continue
            inside = s[
                [
                    days.get_loc(d) - m["long_days"]
                    < days.searchsorted(c["date"])
                    <= days.get_loc(d)
                    for d in s["date"]
                ]
            ]
            outside = s[~s.index.isin(inside.index)]
            if inside.empty:
                continue
            good = (~inside["eligible"]).all() and not (outside["reason_if_not"] == reason).any()
            ok &= good
            detail.append(
                f"{s['stock_id'].iloc[0]} {c['date']:%Y-%m-%d}: {len(inside)} months ineligible"
            )
            break
    results.append(
        (
            "momentum: quarantined and demerger cases ineligible at the right dates",
            ok and len(detail) == 2,
            "; ".join(detail),
        )
    )

    # (4) no ineligible stock has a score
    leak = scores[~scores["eligible"]]["score"].notna().sum()
    results.append(
        (
            "momentum: no ineligible stock has a score",
            leak == 0,
            f"{leak} scores on ineligible rows",
        )
    )

    # (5) holdout guard
    try:
        forward_returns(cfg, adj.loc[: holdout_start(cfg) + pd.Timedelta(days=40)], h=1)
        raised = False
    except HoldoutLocked as e:
        raised, msg = True, str(e)
    results.append(
        (
            "momentum: holdout guard raises when holdout returns are requested",
            raised,
            msg[:90] if raised else "no error",
        )
    )
    return results
