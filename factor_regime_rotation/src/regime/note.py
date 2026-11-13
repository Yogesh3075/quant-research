from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)

TIMING = [
    "Factor momentum",
    "Regime rule",
    "HMM regime rule",
    "HMM defensive switch",
    "Static momentum + quality",
]


def table(s: pd.DataFrame) -> str:
    """Markdown results table for one period."""
    lines = [
        "| strategy | total return % | CAGR % | vol % | Sharpe | max DD % | turnover / yr | vs EW "
        "%/month (t) |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for _, r in s.iterrows():
        vs = (
            "" if pd.isna(r["diff_vs_ew_%"]) else f"{r['diff_vs_ew_%']:+.2f} ({r['diff_t_nw']:.2f})"
        )
        to = "" if pd.isna(r["turnover_yr"]) else f"{r['turnover_yr']:.2f}"
        name = (
            r["strategy"]
            + (" *" if r["strategy"] == "Static momentum + quality" else "")
            + (" †" if r["strategy"].startswith("NIFTY") else "")
        )
        lines.append(
            f"| {name} | {r['total_ret_%']:.1f} | {r['cagr_%']:.1f} | {r['vol_%']:.1f} | "
            f"{r['sharpe']:.2f} | "
            f"{r['max_dd_%']:.1f} | {to} | {vs} |"
        )
    return "\n".join(lines)


def ahead(d: float, t: float) -> str:
    """'ahead by x% a month (t = y)' or 'behind by ...'."""
    return (
        f"ahead by {d:.2f}% a month (t = {t:.2f})"
        if d >= 0
        else f"behind by {-d:.2f}% a month (t = {t:.2f})"
    )


def write_note(cfg: dict) -> None:
    """Write results/research_note.md from the result files."""
    res, out = Path(cfg["paths"]["results"]), Path(cfg["paths"]["processed"])
    s = pd.concat(
        [pd.read_csv(res / "backtest_summary.csv"), pd.read_csv(res / "holdout_result.csv")]
    )

    def get(period, name):
        return s[(s["period"] == period) & (s["strategy"] == name)].iloc[0]

    daily = pd.read_csv(out / "tri_daily.csv", index_col=0, parse_dates=True)
    rets = pd.read_csv(out / "returns_monthly.csv", index_col=0, parse_dates=True)
    reg = pd.read_csv(out / "regimes.csv", index_col=0, parse_dates=True)
    states = pd.read_csv(out / "hmm_states.csv", index_col=0, parse_dates=True)
    hm = pd.read_csv(res / "holdout_monthly.csv", index_col=0, parse_dates=True)
    dm = pd.read_csv(res / "monthly_returns.csv", index_col=0, parse_dates=True)
    trials = pd.read_csv(res / "trials.csv")
    change = pd.read_csv(res / "cost_change_vs_phase2.csv")
    sens = pd.concat(
        [pd.read_csv(res / "cost_sensitivity.csv"), pd.read_csv(res / "holdout_sensitivity.csv")]
    )
    run = (res / "holdout_runs.log").read_text().splitlines()[0]

    dev, live, hold = (
        get("development", "Equal weight"),
        get("live", "Equal weight"),
        get("holdout", "Equal weight"),
    )
    corr = rets["momentum"].corr(rets["alpha"])
    reg_dev = reg.loc[: dev["last"], "regime"].dropna()
    n_stress, n_dec = int((states["state"] == "stressed").sum()), len(states)
    stress_months = ", ".join(f"{d:%b %Y}" for d in states.index[states["state"] == "stressed"])
    h_stress = hm.index[hm["hmm_state"] == "stressed"]
    last = states.iloc[-1]
    periods = [("development", "development"), ("live", "live period"), ("holdout", "holdout")]
    f = cfg["traded"]
    pairs = dm[[f"hmmreg_w_{x}" for x in f]].apply(
        lambda r: " + ".join(x for x in f if r[f"hmmreg_w_{x}"] > 0), axis=1
    )
    top_pair, top_share = pairs.value_counts().index[0], pairs.value_counts().iloc[0]
    def_ew = (dm["hmmdef_w_momentum"] > 0).sum()

    # findings computed from the tables
    vs_bench = []
    for p, label in periods:
        b = get(p, "NIFTY 200 TRI")
        vs_bench.append(f"{label}, {ahead(-b['diff_vs_ew_%'], -b['diff_t_nw'])}")
    rule_rows = s[s["strategy"].isin(TIMING)]
    sig_up = rule_rows[rule_rows["diff_t_nw"] > 2]
    sig_down = rule_rows[rule_rows["diff_t_nw"] < -2]
    hold_rules = rule_rows[rule_rows["period"] == "holdout"]
    all_behind = (hold_rules["diff_vs_ew_%"] < 0).all()
    st_dev, st_hold = (
        get("development", "Static momentum + quality"),
        get("holdout", "Static momentum + quality"),
    )
    hr_dev = get("development", "HMM regime rule")
    ew_beats_bench_dev = -get("development", "NIFTY 200 TRI")["diff_t_nw"] > 2
    ew_cagr_hold = hold["cagr_%"]

    timing_lines = []
    for name in TIMING:
        parts = [
            f"{label}, {ahead(get(p, name)['diff_vs_ew_%'], get(p, name)['diff_t_nw'])}"
            for p, label in periods
        ]
        timing_lines.append(f"- {name}: " + "; ".join(parts) + ".")

    sens_rules = sens[sens["strategy"].isin(TIMING)]
    flips = sens_rules.groupby(["period", "strategy"])["diff_vs_ew_%"].agg(
        lambda x: (x > 0).any() and (x < 0).any()
    )

    conclusion = (
        f"Over {dev['first'][:4]} to {dev['last'][:4]} an equal-weight mix of four Nifty factor "
        "indices "
        f"{'clearly' if ew_beats_bench_dev else ''} beat the market indices, but none of the "
        f"{len(TIMING)} rules that tried "
        f"to time or tilt the factors beat simply holding all four equally"
        + (
            ", and on the 24 unseen holdout months every one of them did worse than equal weight."
            if all_behind
            else "."
        )
    ).replace("  ", " ")

    note = f"""# Factor Regime Rotation: research note

*Hypothetical backtest on index data. Not investment advice. All numbers on this page are generated from the files in `results/` by `python scripts/run.py note`.*

**Main conclusion.** {conclusion}

## 1. Question and data

Do Indian factor indices behave differently in different market regimes, and does a monthly allocation that follows the regime beat a fixed equal-weight mix after costs?

The data is the daily Total Returns Index of NSE's factor and market indices, downloaded from niftyindices.com: {len(daily):,} trading days from {daily.index[0]:%d %b %Y} to {daily.index[-1]:%d %b %Y}. The series match NSE's own published 1, 3 and 5-year returns to two decimals. Before each index's launch date the history is **back-calculated by NSE**, not real performance. The known launch dates are Momentum 30 ({cfg["launch_dates"]["momentum"]}), Quality 30 ({cfg["launch_dates"]["quality"]}) and Low Volatility 30 ({cfg["launch_dates"]["lowvol"]}). For Value 30, the factsheet still needs checking.

## 2. Method

- **Traded factors:** {", ".join(cfg["traded"])}. Alpha 30 is excluded because its monthly returns correlate {corr:.2f} with momentum.
- **Rule-based regimes** (NIFTY 50, data up to t only): trend (12-month return above or below 0) crossed with volatility (63-day volatility above or below its expanding median). There are {len(reg_dev)} labelled development months, and {(reg_dev == "up/low").mean():.0%} of them are up/low.
- **HMM regimes:** a 2-state Gaussian hidden Markov model on the NIFTY 50 monthly log return and realised volatility, refitted every month on data up to t. The current state is the filtered probability.
- **Strategies:** equal weight; factor momentum (top 2 by 12-month return); regime rule and HMM regime rule (top 2 by past performance in the current regime or state); HMM defensive switch (quality + lowvol when p(stressed) > 0.5); static momentum + quality (50/50).
- **Walk-forward:** expanding window. The first decision is at {pd.Timestamp(dev["first"]) - pd.offsets.MonthEnd(1):%b %Y}, and each position is decided at month-end t and held over the next month.
- **Costs:** ETF expense ratios per factor ({", ".join(f"{k} {100 * v:.2f}%" for k, v in cfg["costs"]["expense"].items())} a year) and {100 * cfg["costs"]["switch"]:.2f}% per unit of one-way turnover. Both need checking.
- **Locked holdout:** the last 24 month-ends, scored once ({run}).
- **Trials:** {len(trials)} rules were tested in total. The static momentum + quality rule was chosen after seeing development data.

## 3. Results

**Development** ({dev["first"][:7]} to {dev["last"][:7]}, {int(dev["months"])} months; mostly back-calculated history):

{table(s[s["period"] == "development"])}

**Live period** ({live["first"][:7]} to {live["last"][:7]}, {int(live["months"])} months; after the last known launch date; inside development):

{table(s[s["period"] == "live"])}

**Holdout** ({hold["first"][:7]} to {hold["last"][:7]}, {int(hold["months"])} months; scored once):

{table(s[s["period"] == "holdout"])}

\\* chosen after seeing development data. † index, not investable as is, no costs. "vs EW" is the mean monthly return difference against equal weight with a Newey-West t-statistic (3 lags).

## 4. Findings

**A diversified factor mix against the market.** Against NIFTY 200, equal weight was: {"; ".join(vs_bench)}. The development and live gaps come from holding the factor indices, not from timing, and mostly from back-calculated years. On the holdout equal weight's CAGR was {ew_cagr_hold:.1f}%, and {"the edge over the market did not appear" if get("holdout", "NIFTY 200 TRI")["diff_vs_ew_%"] > 0 else "the edge over the market held"}.

**Timing against equal weight.** {"No rule beat equal weight with a t-statistic above 2 in any period." if sig_up.empty else "Rules with t above 2: " + ", ".join(sig_up["strategy"] + " (" + sig_up["period"] + ")") + "."}

{chr(10).join(timing_lines)}

{"" if sig_down.empty else "Differences with t below -2: " + ", ".join(sig_down["strategy"] + " (" + sig_down["period"] + ", t = " + sig_down["diff_t_nw"].round(2).astype(str) + ")") + ". With " + str(len(trials)) + " trials and few months, even these should be read with care."}

In the cost sensitivity (expenses ×0.5 and ×1.5, switching 0.10% and 0.40%), a rule's sign against equal weight changes in {int(flips.sum())} of {len(flips)} rule-and-period cases.

**What the HMM detected.** The model works as a crisis detector, not a market cycle. In the last development fit:
- The calm state has a mean monthly log return of {100 * last["calm_ret_mean"]:.2f}% and realised volatility of {100 * last["calm_vol_mean"]:.0f}%.
- The stressed state has {100 * last["stressed_ret_mean"]:.2f}% and {100 * last["stressed_vol_mean"]:.0f}%.
- Only {n_stress} of {n_dec} development decisions ({n_stress / n_dec:.0%}) were stressed ({stress_months}). In the holdout it was stressed in {len(h_stress)} of {len(hm)} decisions.

In development the HMM regime rule held {top_pair} in {top_share} of {len(pairs)} months, and the defensive switch was equal weight in {def_ew} of {len(dm)} months.

**The static tilt on unseen data.** Static momentum + quality was {ahead(st_dev["diff_vs_ew_%"], st_dev["diff_t_nw"])} against equal weight in development. The HMM regime rule was {ahead(hr_dev["diff_vs_ew_%"], hr_dev["diff_t_nw"])}, {"almost the same, which supports the view that its edge was the tilt" if abs(st_dev["diff_vs_ew_%"] - hr_dev["diff_vs_ew_%"]) < 0.03 else "which differs from the tilt"}. On the holdout the tilt was {ahead(st_hold["diff_vs_ew_%"], st_hold["diff_t_nw"])}, with a total return of {st_hold["total_ret_%"]:.1f}% against {hold["total_ret_%"]:.1f}% for equal weight. {"The development edge did not carry over." if st_hold["diff_vs_ew_%"] < 0 else "The direction of the development edge carried over."}

## 5. Limitations

- Most of the development history is NSE's back-calculation, not live index performance. Index rules designed later may fit the earlier data better than they would have in real time.
- There are few regime episodes. Up/low is {(reg_dev == "up/low").mean():.0%} of labelled months, and the HMM was stressed in only {n_stress} development decisions, so regime-conditional averages rest on few months.
- The holdout is short ({int(hold["months"])} months), so the tests have very low power. A lack of significance there is not evidence that strategies are equal.
- Costs are approximate (ETF expense ratios from factsheets, a rough switching cost). Against Phase 2's flat rate, development CAGR changed by {change.loc[change["period"] == "development", "cagr_% change"].min():.2f} to {change.loc[change["period"] == "development", "cagr_% change"].max():.2f} points. Tracking error and taxes are not modelled.
- This is a hypothetical backtest of indices, not a record of investable returns, and not investment advice.

## 6. What to test next

- Factor timing with signals that have more episodes: valuation spreads between factors, or factor momentum with a shorter look-back, tested on the same pre-registered walk-forward.
- A longer live record: re-score all rules once a further 24 months of post-launch data exist, without changing them.
- Implementation detail: ETF tracking difference and taxes on switching, which would weigh against the higher-turnover rules.
"""
    (res / "research_note.md").write_text(note)
    logger.info(note)
    logger.info(f"Saved {res / 'research_note.md'}")
