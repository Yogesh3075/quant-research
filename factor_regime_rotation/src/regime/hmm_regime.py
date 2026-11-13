from __future__ import annotations

import logging
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from hmmlearn.hmm import GaussianHMM

logger = logging.getLogger(__name__)


def features(daily50: pd.Series, month_ends: pd.DatetimeIndex) -> pd.DataFrame:
    """Monthly HMM inputs: NIFTY 50 log return and annualised realised volatility."""
    # monthly log return and realised vol (std of that month's daily log returns, annualised)
    logp = np.log(daily50.dropna())
    ret = logp.reindex(month_ends).diff()
    d = logp.diff().dropna()
    vol = d.groupby(d.index.to_period("M")).std() * np.sqrt(252)
    vol = pd.Series(vol.reindex(month_ends.to_period("M")).values, index=month_ends)
    return pd.DataFrame({"ret": ret, "vol": vol}).dropna()


def fit(X: pd.DataFrame, cfg: dict) -> tuple:
    """Best-of-seeds 2-state Gaussian HMM on standardised X; the higher-vol state is stressed."""
    h = cfg["hmm"]
    mu, sd = X.mean(), X.std()
    Z = ((X - mu) / sd).values  # standardised with the training window only
    best, best_ll = None, -np.inf
    for seed in h["seeds"]:
        m = GaussianHMM(
            n_components=h["states"],
            covariance_type=h["covariance"],
            n_iter=h["iterations"],
            random_state=seed,
        )
        m.fit(Z)
        ll = m.score(Z)
        if ll > best_ll:
            best, best_ll = m, ll
    stressed = int(np.argmax(best.means_[:, 1]))  # higher volatility mean
    return best, Z, mu, sd, stressed, best_ll


def state_at(X: pd.DataFrame, cfg: dict) -> tuple:
    """Filtered p(stressed) at the last row of X and the Viterbi path up to it."""
    model, Z, mu, sd, stressed, loglik = fit(X, cfg)
    # X ends at t, so the last row of the smoothed probabilities is the filtered probability at t:
    # smoothing only uses later observations, and there are none.
    p = model.predict_proba(Z)[-1, stressed]
    path = pd.Series(np.where(model.predict(Z) == stressed, "stressed", "calm"), index=X.index)
    means = model.means_ * sd.values + mu.values
    ret_sd = np.sqrt(model.covars_[:, 0, 0]) * sd["ret"]
    calm = 1 - stressed
    row = {
        "p_stressed": p,
        "state": "stressed" if p > cfg["hmm"]["stressed_above"] else "calm",
        "calm_ret_mean": means[calm, 0],
        "calm_ret_sd": ret_sd[calm],
        "calm_vol_mean": means[calm, 1],
        "stressed_ret_mean": means[stressed, 0],
        "stressed_ret_sd": ret_sd[stressed],
        "stressed_vol_mean": means[stressed, 1],
        "p_stay_calm": model.transmat_[calm, calm],
        "p_stay_stressed": model.transmat_[stressed, stressed],
        "loglik": loglik,
        "months": len(X),
    }
    return row, path


def fit_all(monthly: pd.DataFrame, daily: pd.DataFrame, cfg: dict) -> tuple:
    """Refit the HMM at every decision month-end on data up to that month."""
    X = features(daily[cfg["calendar"]], monthly.index)
    decisions = monthly.index[cfg["backtest"]["min_history_months"] : -1]
    rows, paths = {}, []
    for t in decisions:
        rows[t], path = state_at(X.loc[:t], cfg)
        paths.append(pd.DataFrame({"decision": t, "date": path.index, "state": path.values}))
    states = pd.DataFrame(rows).T
    states.index.name = "date"
    return states, pd.concat(paths, ignore_index=True)


def load_hmm(cfg: dict) -> tuple:
    """Saved HMM states and paths from data/processed."""
    out = Path(cfg["paths"]["processed"])
    if not (out / "hmm_states.csv").exists():
        raise SystemExit("No HMM states. Run: python scripts/run.py hmm")
    states = pd.read_csv(out / "hmm_states.csv", index_col=0, parse_dates=True)
    paths = pd.read_csv(out / "hmm_paths.csv", parse_dates=["decision", "date"])
    paths = {t: g.set_index("date")["state"] for t, g in paths.groupby("decision")}
    return states, paths


def run_hmm(
    cfg: dict, monthly: pd.DataFrame, daily: pd.DataFrame, regimes: pd.DataFrame
) -> pd.DataFrame:
    """Fit all month-ends, save the states, write diagnostics and the chart."""
    from regime.backtest import weights_regime

    states, paths = fit_all(monthly, daily, cfg)
    out, res = Path(cfg["paths"]["processed"]), Path(cfg["paths"]["results"])
    states.to_csv(out / "hmm_states.csv")
    paths.to_csv(out / "hmm_paths.csv", index=False)
    logger.info(
        f"HMM fitted at {len(states)} month-ends, {states.index[0].date()} to "
        f"{states.index[-1].date()}"
    )

    last = states.iloc[-1]
    rets = monthly.pct_change(fill_method=None).iloc[1:]
    path_by_t = {t: g.set_index("date")["state"] for t, g in paths.groupby("decision")}
    fallback = sum(
        weights_regime(rets, path_by_t[t], states.loc[t, "state"], t, cfg)[1] for t in states.index
    )
    stressed = states["state"] == "stressed"
    vol_label = regimes["vol"].reindex(states.index)
    agree = ((vol_label == "high") == stressed)[vol_label.notna()]
    flips = int((states["state"] != states["state"].shift()).iloc[1:].sum())
    dur_c, dur_s = 1 / (1 - last["p_stay_calm"]), 1 / (1 - last["p_stay_stressed"])

    lines = [
        "# HMM diagnostics",
        "",
        f"2-state Gaussian HMM (full covariance, {cfg['hmm']['iterations']} iterations, best of "
        f"seeds {cfg['hmm']['seeds']}) "
        "on NIFTY 50 TRI monthly log return and realised volatility, refitted every month-end on "
        "all months up to t.",
        "",
        f"## Last development fit ({states.index[-1].date()}, {int(last['months'])} months)",
        "",
        "| state | mean monthly log return % | sd of monthly return % | mean realised vol % "
        "(annualised) | p(stay) | expected duration (months) |",
        "| --- | --- | --- | --- | --- | --- |",
        f"| calm | {100 * last['calm_ret_mean']:.2f} | {100 * last['calm_ret_sd']:.2f} | "
        f"{100 * last['calm_vol_mean']:.1f} | "
        f"{last['p_stay_calm']:.3f} | {dur_c:.1f} |",
        f"| stressed | {100 * last['stressed_ret_mean']:.2f} | {100 * last['stressed_ret_sd']:.2f} "
        f"| {100 * last['stressed_vol_mean']:.1f} | "
        f"{last['p_stay_stressed']:.3f} | {dur_s:.1f} |",
        "",
        "Transition matrix (row = from, column = to):",
        "",
        "| from / to | calm | stressed |",
        "| --- | --- | --- |",
        f"| calm | {last['p_stay_calm']:.3f} | {1 - last['p_stay_calm']:.3f} |",
        f"| stressed | {1 - last['p_stay_stressed']:.3f} | {last['p_stay_stressed']:.3f} |",
        "",
        f"## Filtered state at each decision month-end ({len(states)} months)",
        "",
        f"- Stressed (p > {cfg['hmm']['stressed_above']}): {stressed.sum()} months "
        f"({stressed.mean():.0%}); calm: {(~stressed).sum()} ({(~stressed).mean():.0%}).",
        f"- State flips: {flips}.",
        f"- Agreement with the Phase 1 volatility label (stressed = high): {agree.mean():.0%} of "
        f"{len(agree)} months.",
        "- HMM regime rule fell back to equal weight (fewer than "
        f"{cfg['backtest']['min_regime_months']} past months in the state): {fallback} months.",
        "- HMM defensive switch: no fallback rule (it is always defined).",
    ]
    (res / "hmm_diagnostics.md").write_text("\n".join(lines) + "\n")
    logger.info("\n".join(lines))
    plot_states(monthly[cfg["calendar"]], states, res / "hmm_states.png")
    return states


def plot_states(nifty: pd.Series, states: pd.DataFrame, path: Path) -> None:
    """Chart of NIFTY 50 and filtered p(stressed)."""
    nifty = nifty.loc[states.index[0] :]
    fig, (a1, a2) = plt.subplots(
        2, 1, figsize=(10, 6), sharex=True, height_ratios=[2, 1], facecolor="#fcfcfb"
    )
    stressed = states.index[states["state"] == "stressed"]
    for ax in (a1, a2):
        ax.set_facecolor("#fcfcfb")
        for t in stressed:  # shade the month ending at t
            ax.axvspan(t - pd.offsets.MonthEnd(1), t, color="#f6d9cc", lw=0)
        for s in ["top", "right"]:
            ax.spines[s].set_visible(False)
        ax.grid(axis="y", color="#e2e1dc", lw=0.8)
    a1.plot(nifty.index, nifty, color="#2a78d6", lw=2)
    a1.set_yscale("log")
    a1.set_ylabel("NIFTY 50 TRI (log)", color="#52514e")
    a1.set_title(
        "HMM state at each month-end, fitted on data up to that month-end only\n"
        "Shaded: months whose end-of-month filtered p(stressed) > 0.5",
        fontsize=10,
        loc="left",
    )
    a2.plot(states.index, states["p_stressed"], color="#eb6834", lw=2)
    a2.axhline(0.5, color="#8a8983", lw=1, ls="--")
    a2.set_ylim(0, 1)
    a2.set_ylabel("p(stressed)", color="#52514e")
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
    logger.info(f"Saved {path}")
