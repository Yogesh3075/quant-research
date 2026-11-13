from __future__ import annotations

import logging
from datetime import date
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

NAMES = {
    "ew": "Equal weight",
    "mom": "Factor momentum",
    "regime": "Regime rule",
    "hmmreg": "HMM regime rule",
    "hmmdef": "HMM defensive switch",
    "static": "Static momentum + quality",
    "nifty200": "NIFTY 200 TRI",
    "nifty50": "NIFTY 50 TRI",
}
STRATS = ["ew", "mom", "regime", "hmmreg", "hmmdef", "static"]


def top_n(score: pd.Series, n: int) -> pd.Series:
    """Equal weight on the n highest scores."""
    w = pd.Series(0.0, index=score.index)
    w[score.nlargest(n).index] = 1 / n
    return w


def weights_ew(factors: list) -> pd.Series:
    """Equal weight across the factors."""
    return pd.Series(1 / len(factors), index=factors)


def weights_mom(tri: pd.DataFrame, t: pd.Timestamp, cfg: dict) -> pd.Series:
    """Top factors by trailing return up to t."""
    hist = tri.loc[:t, cfg["traded"]]
    k = cfg["backtest"]["momentum_months"]
    return top_n(hist.iloc[-1] / hist.iloc[-1 - k] - 1, cfg["backtest"]["top_n"])


def weights_regime(
    rets: pd.DataFrame, labels: pd.Series, now: str, t: pd.Timestamp, cfg: dict
) -> tuple:
    """Top factors by average excess over EW in past months with the current label."""
    # labels: regime or state at past month-ends; now: the label at t.
    # The second value is True when it falls back to equal weight.
    f = cfg["traded"]
    hist = rets.loc[:t, f]
    start = labels.shift(1).reindex(hist.index)  # label at the start of each past month
    same = hist[start == now]
    if pd.isna(now) or len(same) < cfg["backtest"]["min_regime_months"]:
        return weights_ew(f), True
    excess = same.sub(same.mean(axis=1), axis=0).mean()
    return top_n(excess, cfg["backtest"]["top_n"]), False


def weights_hmm_regime(
    rets: pd.DataFrame, path: pd.Series, state: str, t: pd.Timestamp, cfg: dict
) -> tuple:
    """weights_regime with the HMM state as the label."""
    return weights_regime(rets, path, state, t, cfg)


def weights_defensive(p_stressed: float, cfg: dict) -> pd.Series:
    """Quality + low vol when p(stressed) is above the threshold, else EW."""
    if p_stressed > cfg["hmm"]["stressed_above"]:
        d = cfg["hmm"]["defensive"]
        return pd.Series(
            [1 / len(d) if f in d else 0.0 for f in cfg["traded"]], index=cfg["traded"]
        )
    return weights_ew(cfg["traded"])


def weights_static(cfg: dict) -> pd.Series:
    """Fixed momentum + quality tilt."""
    return pd.Series(
        [0.5 if f in cfg["static"] else 0.0 for f in cfg["traded"]], index=cfg["traded"]
    )


def all_weights(
    tri: pd.DataFrame, regime: pd.Series, states: pd.DataFrame, paths: pd.DataFrame, cfg: dict
) -> tuple:
    """Weights of every strategy at every decision month-end."""
    rets = tri.pct_change(fill_method=None).iloc[1:]
    decisions = tri.index[cfg["backtest"]["min_history_months"] : -1]
    w = {k: {} for k in STRATS}
    fallback = {"regime": {}, "hmmreg": {}}
    for t in decisions:
        w["ew"][t] = weights_ew(cfg["traded"])
        w["mom"][t] = weights_mom(tri, t, cfg)
        w["regime"][t], fallback["regime"][t] = weights_regime(rets, regime, regime.get(t), t, cfg)
        w["hmmreg"][t], fallback["hmmreg"][t] = weights_hmm_regime(
            rets, paths[t], states.loc[t, "state"], t, cfg
        )
        w["hmmdef"][t] = weights_defensive(states.loc[t, "p_stressed"], cfg)
        w["static"][t] = weights_static(cfg)
    return {k: pd.DataFrame(v).T for k, v in w.items()}, pd.DataFrame(fallback)


def simulate(
    w: pd.DataFrame, rets: pd.DataFrame, switch: float, expense: pd.Series
) -> pd.DataFrame:
    """Monthly returns after switching costs and per-factor expense ratios."""
    # w at month-end t is held over the next month; turnover is measured against drifted weights
    # expense: annual expense ratio per factor, charged monthly on the weights held
    dates = list(rets.index)
    prev, rows = None, []
    for t in w.index:
        nxt = dates[dates.index(t) + 1]
        wt, r = w.loc[t], rets.loc[nxt, w.columns]
        turn = 0.0 if prev is None else 0.5 * (wt - prev).abs().sum()
        gross = (wt * r).sum()
        charge = (wt * expense[w.columns]).sum() / 12
        rows.append(
            {
                "date": nxt,
                "ret": gross - charge - switch * turn,
                "turnover": turn,
                "expense": charge,
            }
        )
        prev = wt * (1 + r) / (1 + gross)
    return pd.DataFrame(rows).set_index("date")


def nw_tstat(x: np.ndarray | pd.Series, lags: int) -> float:
    """t-statistic of the mean with Newey-West (Bartlett) standard errors."""
    x = np.asarray(x, dtype=float)
    n, e = len(x), x - x.mean()
    s = e @ e / n
    for k in range(1, lags + 1):
        s += 2 * (1 - k / (lags + 1)) * (e[k:] @ e[:-k]) / n
    return x.mean() / np.sqrt(s / n)


def metrics(r: pd.Series, rf: float, turnover: pd.Series | None = None) -> dict:
    """Total return, CAGR, vol, Sharpe over rf, drawdown and turnover."""
    wealth = (1 + r).cumprod()
    dd = wealth / wealth.cummax() - 1
    trough = dd.idxmin()
    peak = wealth.loc[:trough].idxmax()
    rf_m = (1 + rf) ** (1 / 12) - 1
    return {
        "total_ret_%": 100 * (wealth.iloc[-1] - 1),
        "cagr_%": 100 * (wealth.iloc[-1] ** (12 / len(r)) - 1),
        "vol_%": 100 * r.std() * np.sqrt(12),
        "sharpe": (r.mean() - rf_m) / r.std() * np.sqrt(12),
        "max_dd_%": 100 * dd.min(),
        "dd_peak": peak.date(),
        "dd_trough": trough.date(),
        "turnover_yr": np.nan if turnover is None else 12 * turnover.mean(),
        "months": len(r),
        "first": r.index[0].date(),
        "last": r.index[-1].date(),
    }


def expense_ratios(cfg: dict, scale: float = 1.0) -> pd.Series:
    """Expense ratio per factor, optionally scaled for sensitivity."""
    return pd.Series(cfg["costs"]["expense"]) * scale


def monthly_table(
    monthly: pd.DataFrame,
    regime: pd.Series,
    states: pd.DataFrame,
    paths: pd.DataFrame,
    cfg: dict,
    switch: float,
    expense: pd.Series,
) -> tuple:
    """Net monthly returns of all strategies and benchmarks, with weights."""
    rets = monthly.pct_change(fill_method=None).iloc[1:]
    w, fallback = all_weights(monthly, regime, states, paths, cfg)
    sims = {k: simulate(w[k], rets, switch, expense) for k in w}
    idx = sims["ew"].index

    # one row per holding month: regime and HMM state at the decision date, weights, returns
    m = pd.DataFrame(index=idx)
    m.index.name = "date"
    m["regime"] = regime.reindex(w["ew"].index).values
    m["regime_fallback_ew"] = fallback["regime"].values
    m["hmm_p_stressed"] = states["p_stressed"].reindex(w["ew"].index).values
    m["hmm_state"] = states["state"].reindex(w["ew"].index).values
    m["hmmreg_fallback_ew"] = fallback["hmmreg"].values
    for k in w:
        for f in cfg["traded"]:
            m[f"{k}_w_{f}"] = w[k][f].values
        m[f"{k}_turnover"] = sims[k]["turnover"]
        m[f"{k}_expense"] = sims[k]["expense"]
        m[f"{k}_ret"] = sims[k]["ret"]
    for b in cfg["benchmarks"]:
        m[f"{b}_ret"] = rets.loc[idx, b]
    return m, w, fallback


def summarise(m: pd.DataFrame, cfg: dict, periods: list) -> pd.DataFrame:
    """Summary statistics per strategy and period."""
    rows = []
    for period, a, b in periods:
        p = m.loc[a:b]
        for k in STRATS + cfg["benchmarks"]:
            row = {
                "period": period,
                "strategy": NAMES[k],
                "costs": "ETF expense + switch (VERIFY)"
                if k in STRATS
                else "none: index, not investable as is",
            }
            if k == "static":
                row["note"] = "chosen after seeing development data"
            row.update(
                metrics(
                    p[f"{k}_ret"], cfg["risk_free"], p[f"{k}_turnover"] if k in STRATS else None
                )
            )
            if k != "ew":
                d = p[f"{k}_ret"] - p["ew_ret"]
                row.update(
                    {
                        "diff_vs_ew_%": 100 * d.mean(),
                        "diff_t_nw": nw_tstat(d, cfg["backtest"]["nw_lags"]),
                        "share_months_beat_ew": (d > 0).mean(),
                    }
                )
            if k == "hmmreg":
                d = p["hmmreg_ret"] - p["regime_ret"]
                row.update(
                    {
                        "diff_vs_regime_rule_%": 100 * d.mean(),
                        "diff_vs_regime_rule_t_nw": nw_tstat(d, cfg["backtest"]["nw_lags"]),
                    }
                )
            rows.append(row)
    return pd.DataFrame(rows)


def sensitivity(
    monthly: pd.DataFrame,
    regime: pd.Series,
    states: pd.DataFrame,
    paths: pd.DataFrame,
    cfg: dict,
    periods: list,
) -> pd.DataFrame:
    """Summary under scaled expenses and switching costs."""
    c, s = cfg["costs"], cfg["sensitivity"]
    cases = (
        [("base", c["switch"], 1.0)]
        + [(f"expense x{x}", c["switch"], x) for x in s["expense_scale"]]
        + [(f"switch {100 * x:.2f}%", x, 1.0) for x in s["switch"]]
    )
    rows = []
    for name, switch, scale in cases:
        m, _, _ = monthly_table(
            monthly, regime, states, paths, cfg, switch, expense_ratios(cfg, scale)
        )
        out = summarise(m, cfg, periods)
        out = out[out["strategy"].isin([NAMES[k] for k in STRATS])]
        rows.append(
            out[["period", "strategy", "cagr_%", "sharpe", "diff_vs_ew_%", "diff_t_nw"]].assign(
                case=name
            )
        )
    return pd.concat(rows)[
        ["case", "period", "strategy", "cagr_%", "sharpe", "diff_vs_ew_%", "diff_t_nw"]
    ]


def run_backtest(cfg: dict, monthly: pd.DataFrame, regime: pd.Series) -> tuple:
    """Walk-forward backtest of all rules; writes the results/ tables and chart."""
    from regime.hmm_regime import load_hmm

    c, res = cfg["costs"], Path(cfg["paths"]["results"])
    states, paths = load_hmm(cfg)
    m, w, fallback = monthly_table(
        monthly, regime, states, paths, cfg, c["switch"], expense_ratios(cfg)
    )
    idx = m.index
    periods = [("development", idx[0], idx[-1]), ("live", pd.Timestamp(cfg["live_start"]), idx[-1])]
    m.round(6).to_csv(res / "monthly_returns.csv")
    summary = summarise(m, cfg, periods)
    summary.round(4).to_csv(res / "backtest_summary.csv", index=False)

    # change versus the flat expense used in Phases 1 and 2
    flat = pd.Series(c["phase2_expense"], index=cfg["traded"])
    old = summarise(
        monthly_table(monthly, regime, states, paths, cfg, c["switch"], flat)[0], cfg, periods
    )
    cols = ["cagr_%", "sharpe", "diff_vs_ew_%", "diff_t_nw"]
    keep = summary["strategy"].isin([NAMES[k] for k in STRATS])
    change = summary.loc[keep, ["period", "strategy"]].copy()
    for col in cols:
        change[f"{col} flat 0.30%"] = old.loc[keep, col].values
        change[f"{col} ETF"] = summary.loc[keep, col].values
        change[f"{col} change"] = summary.loc[keep, col].values - old.loc[keep, col].values
    change.round(4).to_csv(res / "cost_change_vs_phase2.csv", index=False)
    sens = sensitivity(monthly, regime, states, paths, cfg, periods)
    sens.round(4).to_csv(res / "cost_sensitivity.csv", index=False)

    by_year = (
        m[[f"{k}_ret" for k in NAMES]].groupby(m.index.year).apply(lambda g: (1 + g).prod() - 1)
    )
    by_year.columns = [NAMES[c[:-4]] for c in by_year.columns]
    by_year.index.name = "year"
    (100 * by_year).round(2).to_csv(res / "by_year.csv")

    live = idx >= pd.Timestamp(cfg["live_start"])
    for k in fallback:
        fb = fallback[k]
        logger.info(
            f"\n{NAMES[k]} fell back to equal weight in {int(fb.sum())} of {len(fb)} months "
            f"(fewer than {cfg['backtest']['min_regime_months']} earlier months in the regime or "
            "state):"
        )
        logger.info("  " + ", ".join(str(d.date())[:7] for d in fb[fb].index))
    for a, b in [("regime", "mom"), ("hmmreg", "mom"), ("hmmreg", "regime")]:
        same = (w[a] > 0).eq(w[b] > 0).all(axis=1).set_axis(idx)
        logger.info(
            f"{NAMES[a]} and {NAMES[b]} hold the same factors: {same.mean():.0%} of months, "
            f"{same[live].mean():.0%} live"
        )
    logger.info(
        f"HMM defensive switch is defensive in {(w['hmmdef']['quality'] == 0.5).mean():.0%} of "
        "months"
    )

    show = summary[
        [
            "period",
            "strategy",
            "cagr_%",
            "vol_%",
            "sharpe",
            "max_dd_%",
            "turnover_yr",
            "diff_vs_ew_%",
            "diff_t_nw",
            "share_months_beat_ew",
            "diff_vs_regime_rule_%",
            "diff_vs_regime_rule_t_nw",
            "months",
        ]
    ]
    logger.info("\n" + show.round(2).to_string(index=False))
    logger.info("\nChange versus Phase 2 (flat 0.30% expense) with ETF expense ratios:")
    logger.info(
        change[["period", "strategy"] + [f"{c} change" for c in cols]]
        .round(2)
        .to_string(index=False)
    )
    logger.info("\nCost sensitivity (sensitivity, not selection):")
    logger.info(
        sens.pivot_table(index=["period", "strategy"], columns="case", values="cagr_%")
        .round(2)
        .to_string()
    )
    logger.info("\nReturn by year, %:\n" + (100 * by_year).round(1).to_string())

    plot(m, cfg, res / "equity_curves.png")
    log_trials(cfg, res / "trials.csv")
    return m, summary, w, fallback


def plot(m: pd.DataFrame, cfg: dict, path: Path) -> None:
    """Equity curves of all strategies."""
    colors = {
        "ew": "#2a78d6",
        "mom": "#eb6834",
        "regime": "#1baf7a",
        "hmmreg": "#eda100",
        "hmmdef": "#e87ba4",
        "static": "#008300",
        "nifty200": "#52514e",
        "nifty50": "#8a8983",
    }
    styles = {"nifty200": "--", "nifty50": ":"}
    fig, ax = plt.subplots(figsize=(10, 5.5), facecolor="#fcfcfb")
    ax.set_facecolor("#fcfcfb")
    ax.axvspan(pd.Timestamp(cfg["live_start"]), m.index[-1], color="#e9e8e4", lw=0)
    ax.text(
        pd.Timestamp(cfg["live_start"]),
        0.02,
        "  live period\n  (after last launch date)",
        transform=ax.get_xaxis_transform(),
        fontsize=9,
        color="#52514e",
        va="bottom",
    )
    ends = {}
    for k, c in colors.items():
        wealth = (1 + m[f"{k}_ret"]).cumprod()
        ax.plot(wealth.index, wealth, color=c, lw=2, ls=styles.get(k, "-"), label=NAMES[k])
        ends[k] = wealth.iloc[-1]
    # end labels, pushed apart so they do not overlap on the log scale
    y_prev = 0
    for k in sorted(ends, key=ends.get):
        y = max(ends[k], y_prev * 10**0.035)
        ax.text(
            m.index[-1] + pd.Timedelta(days=60),
            y,
            f"{NAMES[k]} {ends[k]:.1f}x",
            fontsize=8.5,
            color="#0b0b0b",
            va="center",
        )
        y_prev = y
    ax.set_yscale("log")
    ax.set_ylabel("Growth of 1 (log scale)", color="#52514e")
    ax.set_title(
        f"Walk-forward, development period {m.index[0]:%b %Y} to {m.index[-1]:%b %Y}\n"
        "Strategies after costs (VERIFY); benchmarks are indices with no costs",
        fontsize=10,
        loc="left",
    )
    ax.grid(axis="y", color="#e2e1dc", lw=0.8)
    for s in ["top", "right"]:
        ax.spines[s].set_visible(False)
    ax.legend(frameon=False, fontsize=9, loc="upper left")
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
    logger.info(f"Saved {path}")


def log_trials(cfg: dict, path: Path) -> None:
    """Append any new trial definitions to results/trials.csv."""
    b = cfg["backtest"]
    new = pd.DataFrame(
        [
            {
                "name": "factor momentum",
                "date": date.today(),
                "parameters": (
                    f"top {b['top_n']} of {'/'.join(cfg['traded'])} by trailing "
                    f"{b['momentum_months']}m return, equal weight"
                ),
            },
            {
                "name": "regime rule",
                "date": date.today(),
                "parameters": f"top {b['top_n']} by average return minus EW in same-regime months "
                "(trend 12m>0, vol 63d vs expanding "
                f"median, min {b['min_regime_months']} months else EW)",
            },
            {
                "name": "HMM regime rule",
                "date": date.today(),
                "parameters": f"top {b['top_n']} by average return minus EW in past months "
                "of the same HMM state "
                "(2-state Gaussian HMM, "
                "full cov, NIFTY 50 monthly log return and realised vol, expanding refit, seeds "
                "0-4; current state = "
                "filtered p(stressed) > 0.5; past states from Viterbi; min "
                f"{b['min_regime_months']} months else EW)",
            },
            {
                "name": "HMM defensive switch",
                "date": date.today(),
                "parameters": (
                    "same HMM; filtered p(stressed) > 0.5: 50% quality + 50% lowvol, else equal "
                    "weight"
                ),
            },
            {
                "name": "static momentum + quality",
                "date": date.today(),
                "parameters": "50% momentum + 50% quality, rebalanced monthly. "
                "Reason: Phase 2 HMM regime rule held this pair in "
                "166 of 174 months, so its development edge looked like a fixed tilt; tests that "
                "on the holdout. "
                "Chosen after seeing development data",
            },
        ]
    )
    old = pd.read_csv(path) if path.exists() else new.iloc[:0]
    new = new[~new["parameters"].isin(old["parameters"])]
    pd.concat([old, new]).to_csv(path, index=False)


def run_checks(cfg: dict) -> None:
    """Look-ahead, weight, HMM and reconciliation checks; raise on any failure."""
    from scipy.stats import multivariate_normal

    from regime.data import load_dev
    from regime.hmm_regime import features, fit, fit_all, load_hmm, state_at
    from regime.regimes import make_regimes

    monthly, daily = load_dev(cfg)
    cal, f = cfg["calendar"], cfg["traded"]
    reg = make_regimes(monthly[cal], daily[cal], cfg)
    rets = monthly.pct_change(fill_method=None).iloc[1:]
    states, paths = load_hmm(cfg)
    w, fallback = all_weights(monthly, reg["regime"], states, paths, cfg)
    decisions = w["ew"].index

    # look-ahead: drop everything after t and recompute regime, HMM and weights at t
    for t in [decisions[10], decisions[len(decisions) // 2], decisions[-1]]:
        m_t, d_t = monthly.loc[:t], daily.loc[:t]
        r_t = m_t.pct_change(fill_method=None).iloc[1:]
        reg_t = make_regimes(m_t[cal], d_t[cal], cfg)
        assert reg_t.loc[t, "regime"] == reg.loc[t, "regime"], f"regime changed at {t}"
        assert np.allclose(
            reg_t.loc[t, ["ret_12m", "vol_63d", "vol_median_so_far"]].astype(float),
            reg.loc[t, ["ret_12m", "vol_63d", "vol_median_so_far"]].astype(float),
        ), f"regime inputs changed at {t}"
        assert np.allclose(weights_mom(m_t, t, cfg)[f], w["mom"].loc[t, f]), (
            f"momentum weights changed at {t}"
        )
        wr, fb = weights_regime(r_t, reg_t["regime"], reg_t["regime"].get(t), t, cfg)
        assert np.allclose(wr[f], w["regime"].loc[t, f]) and fb == fallback.loc[t, "regime"], (
            f"regime weights changed at {t}"
        )
        row, path = state_at(features(d_t[cal], m_t.index), cfg)
        assert np.isclose(row["p_stressed"], states.loc[t, "p_stressed"], rtol=0, atol=1e-10), (
            f"p_stressed changed at {t}"
        )
        wh, fb = weights_hmm_regime(r_t, path, row["state"], t, cfg)
        assert np.allclose(wh[f], w["hmmreg"].loc[t, f]) and fb == fallback.loc[t, "hmmreg"], (
            f"HMM regime weights changed at {t}"
        )
        assert np.allclose(weights_defensive(row["p_stressed"], cfg)[f], w["hmmdef"].loc[t, f]), (
            f"defensive weights changed at {t}"
        )
    logger.info(
        "check ok: look-ahead (regime, HMM p_stressed and all weights unchanged after deleting "
        "later data, 3 month-ends)"
    )

    # determinism: a second full HMM run writes the identical file
    states2, paths2 = fit_all(monthly, daily, cfg)
    out = Path(cfg["paths"]["processed"])
    assert states2.to_csv() == (out / "hmm_states.csv").read_text(), (
        "hmm_states.csv differs between runs"
    )
    assert paths2.to_csv(index=False) == (out / "hmm_paths.csv").read_text(), (
        "hmm_paths.csv differs between runs"
    )
    logger.info(
        "check ok: determinism (second HMM run gives identical hmm_states.csv and hmm_paths.csv)"
    )

    # filtered probability by hand (forward algorithm) equals the last row of predict_proba
    t = (states["p_stressed"] - 0.5).abs().idxmin()  # least certain month, the hardest case
    m, Z, mu, sd, s, ll = fit(features(daily[cal], monthly.index).loc[:t], cfg)
    b = np.column_stack(
        [multivariate_normal(m.means_[k], m.covars_[k]).pdf(Z) for k in range(m.n_components)]
    )
    alpha = m.startprob_ * b[0]
    alpha /= alpha.sum()
    for i in range(1, len(Z)):
        alpha = (alpha @ m.transmat_) * b[i]
        alpha /= alpha.sum()
    assert np.allclose(alpha, m.predict_proba(Z)[-1], rtol=0, atol=1e-8), (
        "filtered probability mismatch"
    )
    assert np.isclose(alpha[s], states.loc[t, "p_stressed"], rtol=0, atol=1e-8), (
        "filtered probability differs from saved"
    )
    logger.info(
        f"check ok: filtered p(stressed) by hand = last row of predict_proba at {t.date()} "
        f"({alpha[s]:.6f})"
    )

    # labels: stressed has the higher volatility mean in every fit
    assert (states["stressed_vol_mean"] > states["calm_vol_mean"]).all(), (
        "stressed label has lower vol mean"
    )
    logger.info(f"check ok: stressed has the higher volatility mean in all {len(states)} fits")

    # holdout untouched
    hs = pd.Timestamp(cfg["holdout_start"])
    full = pd.read_csv(out / "tri_monthly.csv", index_col=0, parse_dates=True)
    sim = simulate(w["ew"], rets, 0, expense_ratios(cfg, 0))
    assert monthly.index.max() < hs and daily.index.max() < hs, "holdout data loaded"
    assert decisions.max() < hs and sim.index.max() < hs, "holdout month in backtest"
    assert states.index.max() < hs and max(p.index.max() for p in paths.values()) < hs, (
        "holdout month in HMM"
    )
    logger.info(
        f"check ok: holdout untouched ({(full.index >= hs).sum()} locked month-ends from "
        f"{hs.date()}; "
        f"last decision {decisions.max().date()}, last backtest month {sim.index.max().date()})"
    )

    # weights valid
    for k, wk in w.items():
        assert (wk >= 0).all().all() and np.allclose(wk.sum(axis=1), 1), f"bad weights in {k}"
    logger.info(f"check ok: weights non-negative and sum to 1 every month ({len(w)} strategies)")

    # regime rule uses only earlier labels and returns: scramble everything after t
    rng = np.random.default_rng(0)
    labels = reg["regime"].dropna().unique()
    for t in decisions:
        r2, g2 = rets.copy(), reg["regime"].copy()
        later = r2.index > t
        r2.loc[later, f] = rng.normal(0, 0.1, (later.sum(), len(f)))
        g2[g2.index > t] = rng.choice(labels, (g2.index > t).sum())
        wr, fb = weights_regime(r2, g2, g2.get(t), t, cfg)
        assert np.allclose(wr[f], w["regime"].loc[t, f]) and fb == fallback.loc[t, "regime"], (
            f"regime rule used later data at {t}"
        )
    logger.info(
        "check ok: regime rule unchanged when later labels and returns are scrambled "
        f"({len(decisions)} month-ends)"
    )

    # reconciliation: equal weight with no costs = mean of the four factor returns, compounded
    expected = (1 + rets.loc[sim.index, f].mean(axis=1)).prod()
    assert np.isclose((1 + sim["ret"]).prod(), expected), "equal weight does not reconcile"
    logger.info(
        f"check ok: equal weight with zero costs reconciles ({(1 + sim['ret']).prod():.6f} vs "
        f"{expected:.6f})"
    )

    # per-factor expense ratios: recompute one month of factor momentum by hand
    from regime.holdout import previous_runs

    c = cfg["costs"]
    s = simulate(w["mom"], rets, c["switch"], expense_ratios(cfg))
    i = (
        int(np.argmax((w["mom"]["momentum"] > 0).values[100:])) + 100
    )  # a month that holds momentum (0.76%)
    t, nxt = decisions[i], s.index[i]
    wt, r = w["mom"].loc[t], rets.loc[nxt]
    held = [x for x in f if wt[x] > 0]
    by_hand = (
        sum(wt[x] * r[x] for x in held)
        - sum(wt[x] * c["expense"][x] for x in held) / 12
        - c["switch"] * s.loc[nxt, "turnover"]
    )
    assert np.isclose(s.loc[nxt, "ret"], by_hand, rtol=0, atol=1e-12), (
        "per-factor expense not applied"
    )
    logger.info(
        f"check ok: per-factor expense applied ({nxt.date()}, holds {' + '.join(held)}, "
        f"expense {100 * s.loc[nxt, 'expense']:.4f}% this month, return {100 * by_hand:.4f}%)"
    )

    # the holdout is scored at most once
    runs = previous_runs(cfg)
    assert len(runs) <= 1, f"holdout scored {len(runs)} times"
    logger.info(f"check ok: holdout scored {len(runs)} time(s) (at most once)")
