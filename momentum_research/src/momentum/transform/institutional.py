from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
import pandas as pd

from momentum.extract.factors import download_iima
from momentum.extract.prices import read_index, trading_days
from momentum.transform.backtest import (
    PRESETS,
    load_market,
    period_returns,
    simulate,
    stats,
)
from momentum.transform.diagnostics import dev_returns, nw_t
from momentum.transform.split import signal_dates

logger = logging.getLogger(__name__)


def characteristics(cfg: dict, m: dict) -> pd.DataFrame:
    """Monthly size, beta, volatility, reversal and sector of each stock."""
    p = cfg["institutional"]
    days = trading_days(cfg)
    rets = m["adj"].pct_change(fill_method=None)
    mkt = (
        read_index(cfg, cfg["prices"]["indices"][0], "price")
        .reindex(days)
        .pct_change(fill_method=None)
    )
    rows = []
    for t, g in m["scores"].groupby("date"):
        ids = [f for f in g["file_id"] if f in rets.columns]
        i = days.get_loc(t)
        W = rets.iloc[i - p["beta_days"] + 1 : i + 1][ids]
        mk = mkt.iloc[i - p["beta_days"] + 1 : i + 1]
        mask = W.notna() & mk.notna().values[:, None]
        n = mask.sum()
        Wm = W.where(mask)
        Mm = mask.mul(mk, axis=0).where(mask)
        cov = ((Wm - Wm.mean()) * (Mm - Mm.mean())).sum() / (n - 1)
        beta = cov / Mm.var()
        vol = Wm.std() * np.sqrt(252)
        beta[n < p["beta_min_obs"]] = np.nan
        vol[n < p["beta_min_obs"]] = np.nan
        prev = m["adj"].iloc[i][ids] / m["adj"].iloc[i - p["prev_return_days"]][ids] - 1
        rows.append(
            pd.DataFrame(
                dict(
                    date=t,
                    file_id=ids,
                    beta=beta.values,
                    vol=vol.values,
                    prev_ret=prev.values,
                    log_tv=np.log(m["liq"].iloc[i][ids].values),
                )
            )
        )
    ch = pd.concat(rows, ignore_index=True)
    ch = m["scores"].merge(ch, on=["date", "file_id"], how="left")
    ch["sector"] = ch["file_id"].map(m["sector"]).fillna("Unclassified")
    return ch


def zgroup(x: pd.Series, min_n: int) -> pd.Series:
    """z-score within a group, zero if the group is too small."""
    return (x - x.mean()) / x.std(ddof=1) if len(x) >= min_n else x * 0.0


def add_neutral_scores(cfg: dict, m: dict, ch: pd.DataFrame) -> pd.DataFrame:
    """Sector- and size-neutral momentum scores."""
    p = cfg["institutional"]
    ch["score_sector"] = ch.groupby(["date", "sector"])["score"].transform(
        lambda x: zgroup(x, p["neutral_min_group"])
    )
    ch["size_group"] = ch.groupby("date")["log_tv"].transform(
        lambda v: pd.qcut(v.rank(method="first"), p["size_groups"], labels=False)
    )
    ch["score_size"] = ch.groupby(["date", "size_group"])["score"].transform(
        lambda x: zgroup(x, p["neutral_min_group"])
    )
    m["scores"] = m["scores"].merge(
        ch[["date", "file_id", "score_sector", "score_size"]],
        on=["date", "file_id"],
        how="left",
    )
    return ch


MODELS = {
    "A": ["score"],
    "B": ["score", "log_tv"],
    "C": ["score", "log_tv", "beta", "vol"],
    "D": ["score", "log_tv", "beta", "vol", "sector"],
    "E": ["score", "log_tv", "beta", "vol", "sector", "prev_ret"],
}


def cross_section(g: pd.DataFrame, cols: list):
    """One month's Fama-MacBeth cross-sectional regression."""
    X = g[[c for c in cols if c != "sector"]].astype(float)
    if "sector" in cols:
        X = pd.concat(
            [
                X,
                pd.get_dummies(g["sector"], prefix="sec", drop_first=True, dtype=float),
            ],
            axis=1,
        )
    X.insert(0, "const", 1.0)
    b = np.linalg.lstsq(X.values, g["ret"].values, rcond=None)[0]
    return pd.Series(b, index=X.columns)


def fama_macbeth(cfg: dict, ch: pd.DataFrame, rets: pd.DataFrame, months=None) -> tuple:
    """Fama-MacBeth slopes for models A-E with Newey-West t-statistics."""
    lags = cfg["diagnostics"]["newey_west_lags"]
    d = ch.merge(rets, left_on=["date", "file_id"], right_on=["signal_date", "file_id"])
    if months is not None:
        d = d[d["date"].isin(months)]
    slopes, rows = {}, []
    for name, cols in MODELS.items():
        need = [c for c in cols if c != "sector"] + ["ret"]
        dd = d.dropna(subset=need)
        s = pd.DataFrame(
            {d: cross_section(g, cols) for d, g in dd.groupby("date")}
        ).T  # sector dummies vary by month
        s = s[[c for c in s.columns if not c.startswith("sec_")]]
        slopes[name] = s
        for c in s.columns:
            if c == "const":
                continue
            rows.append(
                dict(
                    model=name,
                    variable=c,
                    mean_slope=s[c].mean(),
                    nw_t=nw_t(s[c], lags),
                    months=s[c].count(),
                )
            )
    return pd.DataFrame(rows), slopes


def stitched_test(cfg: dict, m: dict, params: dict, sc) -> pd.Series:
    """Walk-forward test months stitched into one series."""
    fd = pd.read_csv(Path(cfg["paths"]["results"]) / "phase4" / "folds.csv")
    out = []
    for _, f in fd.iterrows():
        months = (f["test_first"], f["test_last"])
        run = simulate(cfg, m, params, sc, months=months)
        out.append(period_returns(cfg, run["equity"]["equity"], months=months))
    return pd.concat(out)


def run_institutional(cfg: dict) -> dict:
    """Phase 5: Fama-MacBeth, neutral variants, exposures, capacity, states, spanning."""
    out = Path(cfg["paths"]["results"]) / "phase5"
    out.mkdir(parents=True, exist_ok=True)
    p3, p4 = (
        Path(cfg["paths"]["results"]) / "phase3",
        Path(cfg["paths"]["results"]) / "phase4",
    )
    lags = cfg["diagnostics"]["newey_west_lags"]
    m = load_market(cfg)
    ch = add_neutral_scores(cfg, m, characteristics(cfg, m))
    ch.to_parquet(out / "characteristics.parquet", index=False)
    res = {}

    rets = dev_returns(
        cfg,
        pd.read_parquet(Path(cfg["paths"]["processed_prices"]) / "adj_close.parquet"),
        1,
    )
    fd = pd.read_csv(p4 / "folds.csv")
    sd = signal_dates(cfg)
    test_months = pd.to_datetime(
        [
            sd.loc[str(mm), "signal_date"]
            for _, f in fd.iterrows()
            for mm in pd.period_range(f["test_first"], f["test_last"], freq="M")
        ]
    )
    fm, slopes = fama_macbeth(cfg, ch, rets)
    fm_test, _ = fama_macbeth(cfg, ch, rets, months=test_months)
    res["fm"] = fm.assign(sample="development").pipe(
        lambda x: pd.concat([x, fm_test.assign(sample="walk-forward test months")])
    )
    res["fm_by_year"] = (
        slopes["D"]["score"]
        .groupby(slopes["D"].index.year)
        .agg(["mean", "count"])
        .rename(columns={"mean": "score_slope"})
    )
    for k, s in slopes.items():
        s.to_csv(out / f"fm_slopes_{k}.csv")

    # 2. neutral variants (base costs) vs primary and equal weight
    ew_dev = pd.read_csv(p3 / "equal_weight_base" / "returns_monthly.csv", index_col=0)["return"]
    stitched = pd.read_csv(p4 / "stitched_returns.csv", index_col=0)
    rows, curves = [], {}
    for name, params in [
        ("primary", PRESETS["primary"]),
        ("sector-neutral", dict(PRESETS["primary"], signal="score_sector")),
        ("size-neutral", dict(PRESETS["primary"], signal="score_size")),
    ]:
        run = simulate(cfg, m, params, "base")
        r = period_returns(cfg, run["equity"]["equity"])
        curves[name] = run["equity"]["equity"]
        wf = stitched["primary"] if name == "primary" else stitched_test(cfg, m, params, "base")
        d, dw = r - ew_dev, wf - stitched["equal_weight"]
        s = stats(cfg, run, r)
        rows.append(
            dict(
                strategy=name,
                cagr=s["cagr"],
                sharpe=s["sharpe"],
                max_drawdown=s["max_drawdown"],
                turnover=s["turnover"],
                cost_pct_yr=s["cost_total_pct_yr"],
                diff_vs_ew=d.mean(),
                diff_nw_t=nw_t(d, lags),
                wf_diff_vs_ew=dw.mean(),
                wf_diff_nw_t=nw_t(dw, lags),
                wf_months=len(dw),
            )
        )
        if name == "primary":
            r_primary = r
    res["neutral"] = pd.DataFrame(rows)

    # 3. exposures of the primary's holdings
    hold = pd.read_csv(p3 / "primary_base" / "holdings.csv", parse_dates=["signal_date"])
    ch["tv_pct"] = ch.groupby("date")["log_tv"].rank(pct=True)
    h = hold.merge(
        ch[["date", "file_id", "tv_pct", "size_group", "beta", "vol"]],
        left_on=["signal_date", "file_id"],
        right_on=["date", "file_id"],
        how="left",
    )
    uni = ch[ch["date"].isin(hold["signal_date"])]
    exp = dict(
        holdings_tv_percentile=h["tv_pct"].mean(),
        universe_tv_percentile=uni["tv_pct"].mean(),
        holdings_beta=h["beta"].mean(),
        universe_beta=uni["beta"].mean(),
        holdings_vol=h["vol"].mean(),
        universe_vol=uni["vol"].mean(),
    )
    for k in range(cfg["institutional"]["size_groups"]):
        exp[f"share_in_tercile_{k + 1}"] = (h["size_group"] == k).mean()
    res["exposures"] = pd.Series(exp).rename("value").to_frame()
    hw = hold.groupby(["signal_date", "sector"])["weight"].sum().unstack(fill_value=0).mean()
    uw = uni.groupby(["date", "sector"]).size().unstack(fill_value=0)
    uw = uw.div(uw.sum(axis=1), axis=0).mean()
    tilt = (hw.reindex(uw.index).fillna(0) - uw).sort_values()
    res["sector_tilts"] = (
        pd.concat([tilt.tail(5)[::-1], tilt.head(5)]).rename("over/underweight").to_frame()
    )

    # 4. capacity with a participation cap
    cap_rows = []
    for c in cfg["institutional"]["capacity_capitals"]:
        run = simulate(
            cfg,
            m,
            "primary",
            "base",
            capital=c,
            participation=cfg["institutional"]["participation"],
        )
        r = period_returns(cfg, run["equity"]["equity"])
        s = stats(cfg, run, r)
        tr = run["trades"][run["trades"]["reason"] == "rebalance"]
        d = r - ew_dev
        cap_rows.append(
            dict(
                capital=c,
                cagr=s["cagr"],
                sharpe=s["sharpe"],
                excess_vs_ew=d.mean(),
                excess_nw_t=nw_t(d, lags),
                share_trades_capped=tr["capped"].mean(),
                end_equity=run["equity"]["equity"].iloc[-1],
            )
        )
        logger.info(f"  capacity Rs {c:,.0f}: CAGR {s['cagr']:.2%}")
    res["capacity"] = pd.DataFrame(cap_rows)

    # 5. momentum states
    tri = read_index(cfg, cfg["prices"]["indices"][0], "tri")
    sdev = sd[sd["period"] == "development"]
    trail = pd.Series(
        [tri.asof(t) / tri.asof(t - pd.DateOffset(months=12)) - 1 for t in sdev["signal_date"]],
        index=sdev.index,
    )
    diff = (r_primary - ew_dev).dropna()
    st_rows = []
    for state, mask in [
        ("NIFTY 500 TRI up over the past 12 months", trail > 0),
        ("down over the past 12 months", trail <= 0),
    ]:
        x = diff[mask.reindex(diff.index).fillna(False)]
        st_rows.append(
            dict(
                state=state,
                months=len(x),
                mean_diff=x.mean(),
                nw_t=nw_t(x, lags),
                share_positive=(x > 0).mean(),
            )
        )
    res["states"] = pd.DataFrame(st_rows)
    from momentum.transform.backtest import index_returns

    n500 = index_returns(cfg, cfg["prices"]["indices"][0])[0]
    ep = pd.DataFrame({"primary": r_primary, "equal_weight": ew_dev, "NIFTY 500 TRI": n500})
    ep = ep[(ep.index >= "2019-12") & (ep.index <= "2020-12")]
    ep["primary_minus_ew"] = ep["primary"] - ep["equal_weight"]
    res["episode_2020"] = ep
    k = cfg["institutional"]["beta_roll_months"]
    res["rolling_beta"] = (
        (r_primary.rolling(k).cov(ew_dev) / ew_dev.rolling(k).var())
        .dropna()
        .rename("beta_to_ew")
        .to_frame()
    )

    # 6. spanning vs IIMA factors
    f = pd.read_csv(download_iima(cfg), na_values="NA")
    f["month"] = pd.PeriodIndex(f["Date"], freq="M")
    f = f.set_index("month")[["MF", "SMB", "HML", "WML", "RF"]] / 100
    q = pd.read_csv(
        Path(cfg["paths"]["results"]) / "phase2" / "buckets_5_monthly.csv",
        index_col=0,
        parse_dates=True,
    )
    q51 = (q["5"] - q["1"]).set_axis(
        pd.PeriodIndex(q.index, freq="M") + 1
    )  # signal month t -> calendar month t+1
    prim = r_primary.set_axis(pd.PeriodIndex(r_primary.index, freq="M") + 1)
    span_rows = []

    for name, y in [("primary minus RF", None), ("Q5 minus Q1", q51)]:
        df = f.join(prim.rename("prim"), how="inner").join(q51.rename("q51"), how="inner").dropna()
        yy = df["prim"] - df["RF"] if y is None else df["q51"]
        X = df[["MF", "SMB", "HML", "WML"]].values
        b, t = ols_nw_multi(yy.values, X, lags)
        capm_b, capm_t = ols_nw_multi(yy.values, df[["MF"]].values, lags)
        span_rows.append(
            dict(
                series=name,
                months=len(df),
                first=str(df.index.min()),
                last=str(df.index.max()),
                alpha_annual=b[0] * 12,
                alpha_t=t[0],
                b_MF=b[1],
                t_MF=t[1],
                b_SMB=b[2],
                t_SMB=t[2],
                b_HML=b[3],
                t_HML=t[3],
                b_WML=b[4],
                t_WML=t[4],
                capm_alpha_annual=capm_b[0] * 12,
                capm_alpha_t=capm_t[0],
                mean_annual=yy.mean() * 12,
            )
        )
        if name == "Q5 minus Q1":
            res["corr_q51_wml"] = df["q51"].corr(df["WML"])
    res["spanning"] = pd.DataFrame(span_rows)
    res["spanning"]["corr_with_wml"] = [np.nan, res["corr_q51_wml"]]
    for k_, v in res.items():
        if isinstance(v, pd.DataFrame):
            v.to_csv(out / f"{k_}.csv")
    return res


def ols_nw_multi(y, X, lags: int) -> tuple:
    """Fit y = a + X b by OLS; returns coefficients and Newey-West t-statistics."""
    X = np.column_stack([np.ones(len(y)), X])
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


def run_checks(cfg: dict) -> list:
    """Phase 5 checks."""
    out = Path(cfg["paths"]["results"]) / "phase5"
    ch = pd.read_parquet(out / "characteristics.parquet")
    results = []
    rets = dev_returns(
        cfg,
        pd.read_parquet(Path(cfg["paths"]["processed_prices"]) / "adj_close.parquet"),
        1,
    )
    t = pd.Timestamp(cfg["checks"]["hand_date"])
    g = (
        ch[ch["date"] == t]
        .merge(rets, left_on=["date", "file_id"], right_on=["signal_date", "file_id"])
        .dropna(subset=["score", "ret"])
    )
    by_hand = ((g["score"] - g["score"].mean()) * (g["ret"] - g["ret"].mean())).sum() / (
        (g["score"] - g["score"].mean()) ** 2
    ).sum()
    stored = pd.read_csv(out / "fm_slopes_A.csv", index_col=0, parse_dates=True).loc[t, "score"]
    logger.info(
        f"  Fama-MacBeth by hand, model A, {t:%Y-%m-%d}: {len(g)} stocks, slope = cov(ret, score) "
        f"/ var(score) = {by_hand:.6f} (stored {stored:.6f})"
    )
    results.append(
        (
            "institutional: one Fama-MacBeth cross-section recomputed by hand",
            abs(by_hand - stored) < 1e-10,
            f"{t:%Y-%m-%d} model A",
        )
    )
    worst = 0.0
    for col, grp in [("score_sector", "sector"), ("score_size", "size_group")]:
        z = ch.groupby(["date", grp])[col].agg(["mean", "std", "count"])
        z = z[z["count"] >= cfg["institutional"]["neutral_min_group"]]
        worst = max(worst, z["mean"].abs().max(), (z["std"] - 1).abs().max())
    results.append(
        (
            "institutional: neutral scores have mean 0 and sd 1 within groups",
            worst < 1e-9,
            f"largest deviation {worst:.2e}",
        )
    )
    cap = pd.read_csv(out / "capacity.csv")
    prim = pd.read_csv(
        Path(cfg["paths"]["results"]) / "phase3" / "primary_base" / "equity_daily.csv"
    )["equity"].iloc[-1]
    small = cap.loc[cap["capital"] == cfg["backtest"]["capital"], "end_equity"].iloc[0]
    results.append(
        (
            "institutional: capacity run at Rs 10 lakh reproduces the primary",
            abs(small - prim) < 1e-6 * prim,
            f"end equity {small:,.0f} vs primary {prim:,.0f}",
        )
    )
    last = pd.Timestamp(signal_dates(cfg).loc[cfg["split"]["last_dev_month"], "signal_date"])
    results.append(
        (
            "institutional: no holdout data read",
            ch["date"].max() <= last,
            f"latest signal date used {ch['date'].max():%Y-%m-%d}",
        )
    )
    return results
