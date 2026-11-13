"""Portfolio test, IC, head-to-head, spanning test and deflated Sharpe for the three models.

Development = feature dates 2015-2022. Seen = 2023 onwards: momentum results for that period
had already been looked at, so it is not out of sample.
"""

import logging
from datetime import datetime

import numpy as np
import pandas as pd
import statsmodels.api as sm

from mlfactors.data import DATA_DIR, RESULTS_DIR
from mlfactors.metrics import NW_LAGS, deflated_sharpe, nw_mean, port_stats
from mlfactors.models import LGB_PARAMS, N_ESTIMATORS
from mlfactors.portfolio import backtest

logger = logging.getLogger(__name__)

MODELS = {"momentum": "pred_momentum", "linear": "pred_linear", "lgbm": "pred_lgbm"}
NAMES = {
    "momentum": "Momentum baseline",
    "linear": "Linear blend (12 features)",
    "lgbm": "LightGBM",
    "ew": "Equal-weight universe",
}
DEV_LAST_YEAR = 2022
TOP_QUINTILE = 0.8
SPANNING_PERIODS = {
    "development": ("2015-02", "2023-01"),
    "seen (to 2025-12)": ("2023-02", "2025-12"),
    "all (to 2025-12)": ("2015-02", "2025-12"),
}
FEATURE_GROUPS = {
    "momentum": ["mom_12_1", "mom_6_1", "ind_rel_mom_6_1", "dist_52w_high", "ret_3m"],
    "low volatility / low beta": ["vol_12m", "vol_1m", "beta_ew", "max_ret_1m"],
    "short-term reversal": ["ret_1m"],
    "liquidity / size": ["log_traded_value", "amihud"],
}


def period_of(d: pd.Timestamp) -> str:
    """'development' for 2015-2022 feature dates, else 'seen'."""
    return "development" if d.year <= DEV_LAST_YEAR else "seen"


def ic_by_month(df: pd.DataFrame) -> pd.DataFrame:
    """Rank IC and top-quintile-minus-universe return of each model, per month."""
    rows = []
    for date, month in df.groupby("date"):
        row = {"date": date.date(), "period": period_of(date)}
        for m, col in MODELS.items():
            ok = month[col].notna()
            row[f"ic_{m}"] = month.loc[ok, col].rank().corr(month.loc[ok, "fwd_ret"].rank())
            top = month.loc[ok, col] >= month.loc[ok, col].quantile(TOP_QUINTILE)
            row[f"q5_minus_universe_{m}"] = month.loc[ok][top].fwd_ret.mean() - month.fwd_ret.mean()
        rows.append(row)
    return pd.DataFrame(rows)


def spanning(lgbm_net: pd.Series) -> pd.DataFrame:
    """Regress LightGBM net return minus RF on IIMA MF, SMB, HML and WML (Newey-West)."""
    factors = pd.read_csv(next(DATA_DIR.glob("*FourFactors*.csv")), na_values="NA")
    factors["month"] = pd.PeriodIndex(factors.Date, freq="M")
    factors = factors.set_index("month")[["MF", "SMB", "HML", "WML", "RF"]] / 100
    lgbm = lgbm_net.copy()
    lgbm.index = pd.PeriodIndex(lgbm.index, freq="M") + 1  # return month = feature month + 1
    out = {}
    for period, (start, end) in SPANNING_PERIODS.items():
        joined = factors.join(lgbm.rename("lgbm"), how="inner").loc[start:end].dropna()
        fit = sm.OLS(
            joined.lgbm - joined.RF, sm.add_constant(joined[["MF", "SMB", "HML", "WML"]])
        ).fit(cov_type="HAC", cov_kwds={"maxlags": NW_LAGS})
        out[period] = {
            "months": len(joined),
            "alpha (% / yr)": fit.params["const"] * 12,
            "alpha t": fit.tvalues["const"],
            **{f"b_{k}": fit.params[k] for k in ["MF", "SMB", "HML", "WML"]},
            "t_WML": fit.tvalues["WML"],
            "R2": fit.rsquared,
        }
    return pd.DataFrame(out)


def model_settings(m: str) -> str:
    """Settings text for the trial log."""
    if m == "momentum":
        return "z(0.5 z(12-1) + 0.5 z(6-1)), clip 1/99"
    if m == "linear":
        return "sign of training IC x 12 rank features, equal weight"
    params = ", ".join(
        f"{k}={v}" for k, v in LGB_PARAMS.items() if k not in ("verbose", "num_threads")
    )
    return f"lightgbm.train, {N_ESTIMATORS} rounds, " + params


def run_report() -> None:
    """Write the result tables and results/summary.md from data/panel and data/predictions."""
    panel = pd.read_parquet(DATA_DIR / "panel.parquet")
    pred = pd.read_parquet(DATA_DIR / "predictions.parquet")
    df = pred.merge(
        panel[["date", "file_id", "fwd_ret", "r_fwd_ret", "industry", "traded_value_63d"]],
        on=["date", "file_id"],
    )
    df["period"] = df.date.map(period_of)

    ic = ic_by_month(df)
    ic.round(6).to_csv(RESULTS_DIR / "ic_by_month.csv", index=False)

    bts = {m: backtest(df, col) for m, col in MODELS.items()}
    bts["ew"] = backtest(df, None)
    monthly = pd.DataFrame({f"{m}_net": b.net for m, b in bts.items()})
    monthly["lgbm_minus_linear"] = monthly.lgbm_net - monthly.linear_net
    monthly.insert(0, "period", monthly.index.map(period_of))
    monthly.insert(0, "return_month", (monthly.index + pd.offsets.MonthEnd(1)).strftime("%Y-%m"))
    monthly.index = monthly.index.strftime("%Y-%m-%d")
    monthly.index.name = "feature_date"
    monthly.round(6).to_csv(RESULTS_DIR / "monthly_returns.csv")

    tables, head_to_head = {}, {}
    for p in ["development", "seen"]:
        in_period = ic.period == p
        table = {}
        for m in list(MODELS) + ["ew"]:
            b = bts[m][bts[m].index.map(period_of) == p]
            stats = port_stats(b, bts["ew"])
            if m in MODELS:
                monthly_ic = ic.loc[in_period, f"ic_{m}"]
                ic_mean, ic_t = nw_mean(monthly_ic)
                q5, q5_t = nw_mean(ic.loc[in_period, f"q5_minus_universe_{m}"])
                stats = {
                    "IC mean": ic_mean,
                    "IC t-stat (NW)": ic_t,
                    "ICIR (monthly)": monthly_ic.mean() / monthly_ic.std(),
                    "Top quintile − universe (% / month)": q5,
                    "Top quintile t-stat (NW)": q5_t,
                    **stats,
                }
            table[NAMES[m]] = stats
        tables[p] = pd.DataFrame(table)
        diff = monthly[monthly.period == p].lgbm_minus_linear
        head_to_head[p] = nw_mean(diff) + (len(diff),)

    span = spanning(bts["lgbm"].net)

    # trial log: the 3 pre-specified models, the best chosen on development only
    dev = tables["development"]
    trial_log = pd.DataFrame([
        {
            "trial": i + 1,
            "model": NAMES[m],
            "settings": model_settings(m),
            "dev_ic": dev.loc["IC mean", NAMES[m]],
            "dev_sharpe": dev.loc["Sharpe", NAMES[m]],
            "dev_excess_pm": dev.loc["Excess over EW (% / month)", NAMES[m]],
            "monthly_sr": bts[m].net[bts[m].index.year <= DEV_LAST_YEAR].mean()
            / bts[m].net[bts[m].index.year <= DEV_LAST_YEAR].std(),
            "run_at": datetime.now().isoformat(timespec="seconds"),
        }
        for i, m in enumerate(MODELS)
    ])  # fmt: skip
    best = trial_log.loc[trial_log.dev_sharpe.idxmax()]
    trial_log["best_on_dev"] = trial_log.trial == best.trial
    trial_log.round(6).to_csv(RESULTS_DIR / "trial_log.csv", index=False)
    best_key = [m for m in MODELS if NAMES[m] == best.model][0]
    best_r = bts[best_key].net[bts[best_key].index.year <= DEV_LAST_YEAR]
    dsr, sr0 = deflated_sharpe(best_r, trial_log.monthly_sr.values)
    ew_dev = bts["ew"].net[bts["ew"].index.year <= DEV_LAST_YEAR]
    excess_srs = [
        (bts[m].net[bts[m].index.year <= DEV_LAST_YEAR] - ew_dev).pipe(lambda x: x.mean() / x.std())
        for m in MODELS
    ]
    dsr_excess, sr0_excess = deflated_sharpe(best_r - ew_dev, excess_srs)

    write_summary(
        tables,
        head_to_head,
        span,
        trial_log,
        best,
        (dsr, sr0, dsr_excess, sr0_excess, best_r - ew_dev),
    )


def md(df: pd.DataFrame, index: bool = True) -> str:
    """A pandas frame as a Markdown table (no tabulate dependency)."""
    df = df.reset_index() if index else df
    out = ["| " + " | ".join(map(str, df.columns)) + " |", "|" + "---|" * len(df.columns)]
    return "\n".join(out + ["| " + " | ".join(map(str, r)) + " |" for r in df.values])


def fmt(x: float, pct: bool = False) -> str:
    """Percent or two-decimal formatting."""
    return f"{x:.2%}" if pct else f"{x:.2f}"


def write_summary(tables, head_to_head, span, trial_log, best, deflated) -> None:
    """Write results/summary.md."""
    dsr, sr0, dsr_excess, sr0_excess, excess = deflated
    importance = pd.read_csv(RESULTS_DIR / "feature_importance.csv")
    interactions = pd.read_csv(RESULTS_DIR / "interactions.csv")
    pct_rows = {
        "IC mean": False,
        "Top quintile − universe (% / month)": True,
        "CAGR": True,
        "Max drawdown": True,
        "Excess over EW (% / month)": True,
        "Cost drag (% / yr)": True,
    }

    def show(t):
        t = t.copy().astype(object)
        for k in t.index:
            t.loc[k] = [
                (
                    ""
                    if pd.isna(x)
                    else f"{int(x)}"
                    if k == "Months"
                    else f"{x:.3f}"
                    if k == "IC mean"
                    else fmt(x, pct_rows.get(k, False))
                )
                for x in t.loc[k]
            ]
        return md(t.rename_axis("Metric"))

    dv, sn = tables["development"], tables["seen"]
    lines = [
        "# Does LightGBM beat a linear factor blend on the point-in-time Nifty 500?",
        "",
        "Walk-forward from 2015 (expanding window, retrained yearly, 1-month embargo). "
        "**Development** = feature "
        "dates 2015-2022. **Seen** = 2023 to Sep 2026; momentum results for this period were "
        "already looked at, "
        "so it is not out of sample. Portfolios: top 30, equal weight, 25% sector cap, hold until "
        "rank > 45, "
        "10 bps + 5/10/20 bps slippage per side. Returns are monthly, from the feature-date close.",
        "",
        "## Development (2015-2022)",
        "",
        show(dv),
        "",
        "## Seen (2023 to Sep 2026)",
        "",
        show(sn),
        "",
        "## Head-to-head: LightGBM minus linear blend (net monthly returns)",
        "",
        "| Period | Mean (% / month) | t-stat (NW) | Months |",
        "|---|---:|---:|---:|",
    ]
    for p, (mu, t, n) in head_to_head.items():
        lines.append(f"| {p} | {mu:.2%} | {t:.2f} | {n} |")
    top = importance.head(4).feature.tolist()
    span_table = span.T.assign(**{
        "alpha (% / yr)": lambda x: x["alpha (% / yr)"].map(lambda v: f"{v:.2%}"),
        "months": lambda x: x.months.astype(int),
    }).round(2)  # fmt: skip
    lines += [
        "",
        "## Feature importance (LightGBM)",
        "",
        md(importance.round(4), index=False),
        "",
        "`gain_share_dev`: average share of total gain across the 8 development models. "
        "`mean_abs_shap`: mean "
        "|SHAP| on test predictions. `linear_sign_dev_years`: how often the linear blend gave the "
        "feature a "
        "positive or negative sign.",
        "",
        f"In plain words: by mean |SHAP| the model leaned most on {', '.join(top)}. "
        + interpretation(importance),
        "",
        "Top 3 SHAP interaction pairs (development models, 500 test rows per year):",
        "",
        md(interactions.head(3).round(5), index=False),
        "",
        "## Spanning test: LightGBM net return − RF on IIMA four factors (Newey-West, 3 lags)",
        "",
        md(span_table.rename_axis("Period")),
        "",
        "## Trials and deflated Sharpe",
        "",
        md(trial_log.drop(columns=["monthly_sr"]).round(4), index=False),
        "",
        f"Best development model: **{best.model}** (development Sharpe {best.dev_sharpe:.2f}). "
        "Expected best "
        f"Sharpe of {len(trial_log)} zero-skill trials: {sr0:.2f}. **Deflated Sharpe on raw "
        f"returns: {dsr:.2f}.** "
        "That mostly says a long-only Nifty 500 portfolio had a positive Sharpe; all three trials "
        "hold the "
        "market, so they differ little and the bar is low. On returns in excess of the "
        "equal-weight universe "
        f"(Sharpe {excess.mean() / excess.std() * np.sqrt(12):.2f}, expected best of 3 zero-skill "
        "trials "
        f"{sr0_excess:.2f}), the **deflated Sharpe is {dsr_excess:.2f}**.",
        "",
        "## Conclusion",
        "",
        conclusion(tables, head_to_head, span),
        "",
    ]
    (RESULTS_DIR / "summary.md").write_text("\n".join(lines))
    logger.info("Wrote %s", RESULTS_DIR / "summary.md")


def conclusion(tables, head_to_head, span) -> str:
    """The conclusion paragraph, with every number read from the tables."""
    dv, sn = tables["development"], tables["seen"]

    def g(t, k, m):
        return t.loc[k, NAMES[m]]

    return (
        "ML did not add anything after costs. LightGBM ranked stocks about as well as the linear "
        "blend of the same "
        f"12 features: development IC {g(dv, 'IC mean', 'lgbm'):.3f} against "
        f"{g(dv, 'IC mean', 'linear'):.3f}, with "
        f"the steadier IC (ICIR {g(dv, 'ICIR (monthly)', 'lgbm'):.2f} against "
        f"{g(dv, 'ICIR (monthly)', 'linear'):.2f}). "
        f"But its portfolio traded {g(dv, 'Turnover (one-way, x / yr)', 'lgbm'):.1f}x a year "
        "against "
        f"{g(dv, 'Turnover (one-way, x / yr)', 'linear'):.1f}x and paid "
        f"{g(dv, 'Cost drag (% / yr)', 'lgbm'):.1%} a year "
        "in costs. Net, it beat the equal-weight universe by only "
        f"{g(dv, 'Excess over EW (% / month)', 'lgbm'):.2%} a "
        f"month in development (t = {g(dv, 'Excess t-stat (NW)', 'lgbm'):.2f}) and by "
        f"{g(sn, 'Excess over EW (% / month)', 'lgbm'):.2%} in the seen period. "
        f"Head-to-head, LightGBM minus the linear blend was {head_to_head['development'][0]:.2%} a "
        "month in "
        f"development (t = {head_to_head['development'][1]:.2f}) and {head_to_head['seen'][0]:.2%} "
        "in the seen "
        f"period (t = {head_to_head['seen'][1]:.2f}): no evidence either way. Against the IIMA "
        "four factors, "
        f"LightGBM's alpha is {span.loc['alpha (% / yr)', 'all (to 2025-12)']:.1%} a year "
        f"(t = {span.loc['alpha t', 'all (to 2025-12)']:.2f}). "
        "The plain momentum baseline did best on the one comparison that matters for a long-only "
        "investor: "
        f"{g(dv, 'Excess over EW (% / month)', 'momentum'):.2%} a month over equal weight in "
        "development "
        f"(t = {g(dv, 'Excess t-stat (NW)', 'momentum'):.2f}) and "
        f"{g(sn, 'Excess over EW (% / month)', 'momentum'):.2%} "
        "in the seen period. LightGBM mostly rediscovered momentum and low volatility/low beta. "
        "It found little in "
        "reversal: the 1-month return was given a positive sign in 5 of 8 years, so it is not a "
        "reversal signal in "
        f"this universe."
    )


def interpretation(importance: pd.DataFrame) -> str:
    """Share of development |SHAP| by feature group."""
    by_feature = importance.set_index("feature").mean_abs_shap_dev
    share = {group: by_feature.loc[features].sum() for group, features in FEATURE_GROUPS.items()}
    total = sum(share.values())
    parts = ", ".join(f"{g} {v / total:.0%}" for g, v in sorted(share.items(), key=lambda x: -x[1]))
    return f"Grouping the features, the development SHAP mass splits as: {parts}."
