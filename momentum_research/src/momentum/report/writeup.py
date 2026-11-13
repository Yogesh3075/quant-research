from __future__ import annotations

import json
import logging
import shutil
from pathlib import Path

import numpy as np
import pandas as pd

from momentum.report.reports import table

logger = logging.getLogger(__name__)

DOC_CHARTS = [
    ("phase2", "quintile_returns.png"),
    ("phase3", "equity_curves.png"),
    ("phase4", "walkforward_oos.png"),
    ("phase4", "holdout_run1.png"),
    ("phase5", "fm_slopes.png"),
    ("phase5", "capacity.png"),
]


def label(name: str) -> str:
    """Readable strategy label."""
    # "score|N50|quarterly" -> "blend, N50, quarterly" (a pipe would break Markdown tables)
    return name.replace("score", "blend").replace("|", ", ")


def pct(x: float, d: int = 2) -> str:
    """x as a percentage string."""
    return f"{x * 100:.{d}f}%"


def gather(cfg: dict) -> dict:
    """Read every result table the write-up needs."""
    r = Path(cfg["paths"]["results"])
    g = {}
    g["ic"] = pd.read_csv(r / "phase2" / "ic_summary.csv", index_col=0)
    g["spread"] = pd.read_csv(r / "phase2" / "spread_5.csv", index_col=0)
    g["decay"] = pd.read_csv(r / "phase2" / "ic_decay.csv", index_col=0)
    g["surv"] = pd.read_csv(r / "phase2" / "survivorship.csv", index_col=0)
    g["p3"] = pd.read_csv(r / "phase3" / "table_summary.csv")
    g["vs"] = pd.read_csv(r / "phase3" / "table_vs_equal_weight.csv")
    g["be"] = pd.read_csv(r / "phase3" / "breakeven_runs.csv")
    g["wf"] = pd.read_csv(r / "phase4" / "walkforward_summary.csv").set_index("strategy")
    g["folds"] = pd.read_csv(r / "phase4" / "folds.csv")
    g["dsr18"] = pd.read_csv(r / "phase4" / "deflated_sharpe_18.csv")
    g["frozen"] = json.loads((r / "phase4" / "frozen_config.json").read_text())
    runs = len((r / "phase4" / "holdout_runs.log").read_text().splitlines())
    g["holdout_run"] = runs
    g["ho"] = pd.read_csv(r / "phase4" / f"holdout_summary_run{runs}.csv").set_index("strategy")
    g["fm"] = pd.read_csv(r / "phase5" / "fm.csv", index_col=0)
    g["neutral"] = pd.read_csv(r / "phase5" / "neutral.csv", index_col=0).set_index("strategy")
    g["cap"] = pd.read_csv(r / "phase5" / "capacity.csv", index_col=0)
    g["span"] = pd.read_csv(r / "phase5" / "spanning.csv", index_col=0).set_index("series")
    g["states"] = pd.read_csv(r / "phase5" / "states.csv", index_col=0)
    g["trials"] = len(pd.read_csv(r / "trial_log.csv"))
    dr = pd.read_csv(Path(cfg["paths"]["processed_prices"]) / "demerger_rights_review.csv")
    g["unadjusted"] = int((dr["status"] == "unadjusted").sum())
    from momentum.transform.industry import industry_coverage

    g["unclassified"] = industry_coverage(cfg)[1]
    return g


def frozen_development(cfg: dict, g: dict) -> dict:
    """Development statistics of the frozen holdout configuration."""
    # the frozen selection's own development-period result (same engine, base costs)
    from momentum.transform.backtest import load_market, period_returns, simulate, stats
    from momentum.transform.diagnostics import nw_t

    m = load_market(cfg)
    run = simulate(cfg, m, g["frozen"]["params"], "base")
    r = period_returns(cfg, run["equity"]["equity"])
    ew = pd.read_csv(
        Path(cfg["paths"]["results"]) / "phase3" / "equal_weight_base" / "returns_monthly.csv",
        index_col=0,
    )["return"]
    s = stats(cfg, run, r)
    d = r - ew
    return dict(
        cagr=s["cagr"],
        sharpe=s["sharpe"],
        max_drawdown=s["max_drawdown"],
        diff=d.mean(),
        t=nw_t(d, cfg["diagnostics"]["newey_west_lags"]),
    )


def results_table(cfg: dict, g: dict) -> tuple:
    """The development / walk-forward / holdout results table."""
    p3 = g["p3"][g["p3"]["scenario"].isin(["base"])].set_index("strategy")
    vs = g["vs"][g["vs"]["scenario"] == "base"].set_index("strategy")
    fz = frozen_development(cfg, g)
    name = label(g["frozen"]["params"]["name"])
    rows = [
        dict(
            period="Development (2011-01 to 2024-10)",
            strategy="Primary (blend, 30, monthly)",
            cagr=p3.at["primary", "cagr"],
            sharpe=p3.at["primary", "sharpe"],
            max_drawdown=p3.at["primary", "max_drawdown"],
            diff=vs.at["primary", "diff_mean"],
            t=vs.at["primary", "diff_nw_t"],
        ),
        dict(
            period="Development (2011-01 to 2024-10)",
            strategy=f"Selection ({name})",
            **fz,
        ),
        dict(
            period="Development (2011-01 to 2024-10)",
            strategy="Equal weight (eligible)",
            cagr=p3.at["equal_weight", "cagr"],
            sharpe=p3.at["equal_weight", "sharpe"],
            max_drawdown=p3.at["equal_weight", "max_drawdown"],
            diff=np.nan,
            t=np.nan,
        ),
    ]
    wf, ho = g["wf"], g["ho"]
    first, last = g["folds"]["test_first"].iloc[0], g["folds"]["test_last"].iloc[-1]
    for k, lab in [
        ("primary", "Primary (blend, 30, monthly)"),
        ("selection", "Selection (chosen per fold)"),
        ("equal_weight", "Equal weight (eligible)"),
    ]:
        rows.append(
            dict(
                period=f"Walk-forward out of sample ({first} to {last})",
                strategy=lab,
                cagr=wf.at[k, "cagr"],
                sharpe=wf.at[k, "sharpe"],
                max_drawdown=wf.at[k, "max_drawdown_monthly"],
                diff=wf.at[k, "diff_vs_ew"] if k != "equal_weight" else np.nan,
                t=wf.at[k, "diff_nw_t"] if k != "equal_weight" else np.nan,
            )
        )
    for k, lab in [
        ("fixed primary", "Primary (blend, 30, monthly)"),
        ("frozen selection", f"Selection ({name})"),
        ("equal weight", "Equal weight (eligible)"),
    ]:
        rows.append(
            dict(
                period=f"Holdout, run {g['holdout_run']} ({int(ho.at[k, 'months'])} months)",
                strategy=lab,
                cagr=ho.at[k, "cagr"],
                sharpe=ho.at[k, "sharpe"],
                max_drawdown=ho.at[k, "max_drawdown_monthly"],
                diff=ho.at[k, "diff_vs_ew"] if k != "equal weight" else np.nan,
                t=ho.at[k, "diff_nw_t"] if k != "equal weight" else np.nan,
            )
        )
    t = pd.DataFrame(rows)
    show = t.assign(
        cagr=t["cagr"].map(pct),
        sharpe=t["sharpe"].round(2),
        max_drawdown=t["max_drawdown"].map(pct),
        **{
            "vs equal weight, per month (t)": [
                ("" if np.isnan(d) else f"{pct(d)} ({tt:.2f})")
                for d, tt in zip(t["diff"], t["t"], strict=False)
            ]
        },
    )
    return t, show.drop(columns=["diff", "t"]).rename(
        columns={"cagr": "CAGR", "sharpe": "Sharpe", "max_drawdown": "max drawdown"}
    )


def numbers(g: dict) -> dict:
    """The headline numbers, each read from its result file."""
    fm = g["fm"]
    dev = fm[fm["sample"] == "development"].set_index(["model", "variable"])
    sp = g["span"]
    surv = g["surv"]
    infl = (
        surv.at["today's list for all dates", "universe_return"]
        - surv.at["point-in-time Nifty 500", "universe_return"]
    ) * 12
    vs = g["vs"][g["vs"]["scenario"] == "base"].set_index("strategy")
    return dict(
        ic=g["ic"].at["score", "mean"],
        ic_t=g["ic"].at["score", "nw_t"],
        q5u=g["spread"].at["top_minus_universe", "mean"],
        q5u_t=g["spread"].at["top_minus_universe", "nw_t"],
        q51=g["spread"].at["top_minus_bottom", "mean"],
        q51_t=g["spread"].at["top_minus_bottom", "nw_t"],
        dev_diff=vs.at["primary", "diff_mean"],
        dev_t=vs.at["primary", "diff_nw_t"],
        oos_diff=g["wf"].at["primary", "diff_vs_ew"],
        oos_t=g["wf"].at["primary", "diff_nw_t"],
        sel_diff=g["wf"].at["selection", "diff_vs_ew"],
        sel_t=g["wf"].at["selection", "diff_nw_t"],
        ho_diff=g["ho"].at["frozen selection", "diff_vs_ew"],
        ho_t=g["ho"].at["frozen selection", "diff_nw_t"],
        ho_months=int(g["ho"].at["frozen selection", "months"]),
        fm_a=dev.at[("A", "score"), "mean_slope"],
        fm_a_t=dev.at[("A", "score"), "nw_t"],
        fm_e=dev.at[("E", "score"), "mean_slope"],
        fm_e_t=dev.at[("E", "score"), "nw_t"],
        span_a=sp.at["primary minus RF", "alpha_annual"],
        span_t=sp.at["primary minus RF", "alpha_t"],
        capm_a=sp.at["primary minus RF", "capm_alpha_annual"],
        capm_t=sp.at["primary minus RF", "capm_alpha_t"],
        wml_corr=sp.at["Q5 minus Q1", "corr_with_wml"],
        span_months=int(sp.at["primary minus RF", "months"]),
        surv_infl=infl,
        trials=g["trials"],
    )


def write_resume_numbers(cfg: dict, g: dict, out: Path) -> None:
    """Write docs/resume_numbers.md (number, file, row)."""
    n = numbers(g)
    rows = [
        (
            "Rank IC of the momentum score with next-month returns",
            f"{n['ic']:.3f} (t = {n['ic_t']:.2f})",
            "results/phase2/ic_summary.csv",
            "IC, row score",
        ),
        (
            "Top quintile minus eligible universe, gross",
            f"{pct(n['q5u'])} a month (t = {n['q5u_t']:.2f})",
            "results/phase2/spread_5.csv",
            "top_minus_universe",
        ),
        (
            "Primary minus equal weight after base costs, development",
            f"{pct(n['dev_diff'])} a month (t = {n['dev_t']:.2f})",
            "results/phase3/table_vs_equal_weight.csv",
            "primary, base",
        ),
        (
            "Primary minus equal weight, walk-forward test months (out of sample)",
            f"{pct(n['oos_diff'])} a month (t = {n['oos_t']:.2f})",
            "results/phase4/walkforward_summary.csv",
            "primary",
        ),
        (
            "Holdout (frozen selection minus equal weight)",
            f"{pct(n['ho_diff'])} a month (t = {n['ho_t']:.2f}, {n['ho_months']} months)",
            f"results/phase4/holdout_summary_run{g['holdout_run']}.csv",
            "frozen selection",
        ),
        (
            "Fama-MacBeth momentum slope with all controls (model E)",
            f"{pct(n['fm_e'])} a month per 1 sd (t = {n['fm_e_t']:.2f})",
            "results/phase5/fm.csv",
            "model E, score, development",
        ),
        (
            "Four-factor alpha of the primary vs IIMA MF, SMB, HML, WML",
            f"{pct(n['span_a'])} a year (t = {n['span_t']:.2f}); market-only alpha "
            f"{pct(n['capm_a'])} (t = {n['capm_t']:.2f})",
            "results/phase5/spanning.csv",
            "primary minus RF",
        ),
        (
            "Correlation of Q5 minus Q1 with IIMA WML",
            f"{n['wml_corr']:.2f}",
            "results/phase5/spanning.csv",
            "Q5 minus Q1, corr_with_wml",
        ),
        (
            "Survivorship inflation of the universe return (today's list vs point in time)",
            f"{pct(n['surv_infl'])} a year",
            "results/phase2/survivorship.csv",
            "universe_return, x12",
        ),
        (
            "Trials run (all logged before running)",
            f"{n['trials']}",
            "results/trial_log.csv",
            "all rows",
        ),
    ]
    text = [
        "# Numbers worth quoting\n",
        "Hypothetical backtest results; costs are assumptions (VERIFY). Each number names the file "
        "it comes from.\n",
        table(pd.DataFrame(rows, columns=["what", "number", "file", "table / row"])),
    ]
    (out / "resume_numbers.md").write_text("\n".join(text))


def write_research_note(cfg: dict, g: dict, out: Path, show) -> None:
    """Write docs/research_note.md."""
    n = numbers(g)
    p3 = g["p3"].set_index(["strategy", "scenario"])
    fz = label(g["frozen"]["params"]["name"])
    folds = g["folds"]
    cap = g["cap"]
    neu = g["neutral"]
    st = g["states"]
    dsr = g["dsr18"].set_index("series")
    chosen = folds["chosen"].value_counts()
    text = [
        "# Price momentum on the point-in-time Nifty 500, 2011-2026\n",
        "*Hypothetical backtest. Costs are assumptions marked VERIFY. Not investment advice.*\n",
        "## Question\n",
        "Does 12-1 / 6-1 price momentum earn a premium on the point-in-time Nifty 500 after "
        "realistic costs, and is that premium "
        "anything more than the known momentum factor?\n",
        "## Data\n",
        "- Universe: Nifty 500 membership rebuilt for every month-end from 2010 from NSE / "
        "niftyindices.com index-change notices "
        "(parsed, a few transcribed by hand, each citing its notice), checked backwards from "
        "today's list and forwards from the earliest list.",
        "- Prices: Yahoo adjusted closes cross-checked day by day with NSE's daily bhavcopy (4,183 "
        "files); NSE corporate actions; a series "
        "built from NSE closes where the sources disagree. Benchmarks: NIFTY 500 and NIFTY 50 TRI "
        "from niftyindices.com.",
        "- Industries: NSE constituent files archived by the Internet Archive, mapped to NSE's "
        "current industry list.",
        "- Factors: IIMA's Indian Fama-French and momentum factors (Agarwalla, Jacob and Varma).\n",
        "## Method\n",
        "Score = z(0.5 z(12-1) + 0.5 z(6-1)) across eligible stocks (members, Rs 5 crore median "
        "traded value, 252 days of history, "
        "no quarantined or unadjusted corporate event in the look-back). Signals at month-ends, "
        "execution at the next regular session's close. "
        "Portfolio: top 30 equal weight, buffer to rank 45, sector cap 25%, monthly; costs: STT, "
        "exchange, SEBI, stamp, GST, DP charge and "
        "liquidity-tiered slippage. Development 2011-01 to 2024-10; walk-forward with expanding "
        "windows, 1-month embargo and 12-month tests; "
        "holdout 2024-11 onward run once on a configuration frozen and committed beforehand. "
        f"{n['trials']} trials in total, each logged before it ran.\n",
        "## Results\n",
        f"**Signal.** Mean monthly rank IC {n['ic']:.3f} (t = {n['ic_t']:.2f}); Q5 minus Q1 "
        f"{pct(n['q51'])} a month (t = {n['q51_t']:.2f}); "
        f"Q5 minus universe {pct(n['q5u'])} (t = {n['q5u_t']:.2f}). IC peaks three months out and "
        "is near zero at twelve.\n",
        "**Portfolio (development, base costs).** Primary CAGR "
        f"{pct(p3.loc[('primary', 'base'), 'cagr'])}, Sharpe "
        f"{p3.loc[('primary', 'base'), 'sharpe']:.2f}, "
        f"max drawdown {pct(p3.loc[('primary', 'base'), 'max_drawdown'])}; equal weight "
        f"{pct(p3.loc[('equal_weight', 'base'), 'cagr'])}, "
        f"Sharpe {p3.loc[('equal_weight', 'base'), 'sharpe']:.2f}. Difference {pct(n['dev_diff'])} "
        f"a month (t = {n['dev_t']:.2f}). "
        f"Costs {pct(p3.loc[('primary', 'base'), 'cost_total_pct_yr'])} a year at "
        f"{p3.loc[('primary', 'base'), 'turnover']:.1f}x one-way turnover. "
        f"Quarterly rebalancing: CAGR {pct(p3.loc[('quarterly', 'base'), 'cagr'])}, Sharpe "
        f"{p3.loc[('quarterly', 'base'), 'sharpe']:.2f}.\n",
        "**Walk-forward.** Out of sample the fixed primary beats equal weight by "
        f"{pct(n['oos_diff'])} a month (t = {n['oos_t']:.2f}); "
        f"selecting from the 18-combination grid fold by fold gives {pct(n['sel_diff'])} (t = "
        f"{n['sel_t']:.2f}), so selection adds nothing. "
        f"Most chosen: {', '.join(f'{label(k)} ({v})' for k, v in chosen.head(3).items())}. "
        "Deflated Sharpe at 18 trials: fixed primary "
        f"{dsr.at['fixed primary, full development', 'deflated_sharpe']:.2f}.\n",
        f"**Holdout (run {g['holdout_run']}).** Frozen configuration {fz}: {pct(n['ho_diff'])} a "
        f"month over equal weight (t = {n['ho_t']:.2f}) "
        f"over {n['ho_months']} months. With so few months only a difference of about "
        f"{pct(g['ho'].at['frozen selection', 'detectable_diff_t2'])} a month "
        "would reach t = 2; the holdout neither confirms nor rejects the development result.\n",
        f"**Controls.** The Fama-MacBeth momentum slope is {pct(n['fm_a'])} a month per standard "
        f"deviation (t = {n['fm_a_t']:.2f}) alone and "
        f"{pct(n['fm_e'])} (t = {n['fm_e_t']:.2f}) after size, beta, volatility, sector and "
        "short-term reversal. Sector-neutral and size-neutral "
        f"versions keep the excess ({pct(neu.at['sector-neutral', 'diff_vs_ew'])} and "
        f"{pct(neu.at['size-neutral', 'diff_vs_ew'])} a month).\n",
        "**Spanning.** Against IIMA's market factor alone the primary's alpha is "
        f"{pct(n['capm_a'])} a year (t = {n['capm_t']:.2f}); adding SMB, HML "
        f"and WML leaves {pct(n['span_a'])} (t = {n['span_t']:.2f}) over {n['span_months']} "
        f"months. Q5 minus Q1 correlates {n['wml_corr']:.2f} with WML. "
        "The strategy is a liquid, implementable version of Indian momentum, not a separate source "
        "of return.\n",
        "**Capacity and states.** With trades capped at 5% of median traded value, CAGR is "
        + ", ".join(
            f"{pct(r['cagr'])} at Rs {r['capital'] / 1e7:g} crore" for _, r in cap.iterrows()
        )
        + f". The excess over equal weight is {pct(st.iloc[0]['mean_diff'])} a month after rising "
        f"markets and {pct(st.iloc[1]['mean_diff'])} after falling ones.\n",
        "## Results table\n",
        table(show),
        "\n## Limitations\n",
        "- Cost rates and the 6.5% risk-free rate are assumptions to verify; slippage is a tiered "
        "estimate, not a market-impact model.",
        "- Yahoo prices are used where they match NSE; NSE's corporate-action records miss some "
        f"events; {g['unadjusted']} unadjusted demergers/rights are handled by exclusion.",
        "- Delisted holdings are sold at the last close; merger or buyback proceeds may differ.",
        "- The Sep 2010 review notice and one 2012 notice are missing; industries for "
        f"{pct(g['unclassified'], 1)} of eligible member-months are unclassified.",
        f"- The holdout has {n['ho_months']} months and little power.\n",
        "## Next\n",
        "Verify the cost schedule against a broker's contract notes; model market impact with "
        "order-book data; test a residual-momentum signal "
        "that removes the WML exposure; extend the holdout as months accrue (each extension logged "
        "as a new run).\n",
    ]
    (out / "research_note.md").write_text("\n".join(text))


def write_all(cfg: dict) -> None:
    """Copy charts to docs/ and write the research note and resume numbers."""
    out = Path("docs")
    out.mkdir(exist_ok=True)
    for phase, name in DOC_CHARTS:
        src = Path(cfg["paths"]["results"]) / phase / name
        if src.exists():
            shutil.copy(src, out / name)
    g = gather(cfg)
    t, show = results_table(cfg, g)
    t.to_csv(Path(cfg["paths"]["results"]) / "results_table.csv", index=False)
    write_resume_numbers(cfg, g, out)
    write_research_note(cfg, g, out, show)
    logger.info("wrote docs/research_note.md, docs/resume_numbers.md and docs charts")
