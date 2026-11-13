"""Run one stage of the momentum project, and the project-wide checks."""

from __future__ import annotations

import logging
import os
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = PROJECT_ROOT / "configs" / "config.yaml"
RESULTS_DIR = "results"
STEPS = [
    "universe-download", "membership", "coverage", "universe-all", "industry", "prices-download",
    "prices-build", "liquidity", "prices-all", "split", "momentum", "diagnostics", "phase2-all",
    "backtest", "phase3-all", "walkforward", "holdout", "institutional", "writeup", "all", "check",
]  # fmt: skip


def load_config() -> dict:
    """Read configs/config.yaml and work from the project root, where its paths are relative.

    The config's SHA-256 is recorded in the frozen holdout configuration, so the file is kept
    byte-identical; results now live in results/ instead of its `paths.results`.
    """
    os.chdir(PROJECT_ROOT)
    with open(CONFIG_PATH) as f:
        cfg = yaml.safe_load(f)
    cfg["paths"]["results"] = RESULTS_DIR
    return cfg


def run_check(cfg: dict) -> None:
    """All project checks; exits with status 1 if any fails."""
    from momentum.transform import membership

    out = Path(cfg["paths"]["processed_universe"])
    for name in ["index_changes.csv", "membership.csv", "universe_report.md"]:
        if not (out / name).exists():
            raise SystemExit(f"Missing {out / name}. Run: python scripts/run.py membership")
    changes = pd.read_csv(out / "index_changes.csv", parse_dates=["effective_date"])
    spells = pd.read_csv(out / "membership.csv", parse_dates=["start_date", "end_date"])
    sym_changes, _, _, _, current = membership.load_nse_lists(cfg)
    today = pd.Timestamp.today().normalize()
    current_keys = {
        membership.symbol_key(s, today, sym_changes)
        for s in current["Symbol"]
        if not s.startswith("DUMMY")
    }
    for s in current["Symbol"]:
        if s.startswith("DUMMY"):  # placeholder: key of its inclusion row
            inc = changes[(changes["symbol"] == s) & (changes["action"] == "include")]
            current_keys.add(inc.sort_values("effective_date")["key"].iloc[-1] if len(inc) else s)
    results = []

    open_spells = set(spells.loc[spells["end_date"].isna(), "stock_id"])
    results.append(
        (
            "today's reconstructed list equals today's NSE file",
            open_spells == current_keys,
            f"{len(open_spells - current_keys)} extra, {len(current_keys - open_spells)} missing",
        )
    )

    # replay the changes both ways from the two ends and compare
    start = set(spells.loc[spells["start_date"].isna(), "stock_id"])
    fwd = set(start)
    for _, day in changes.groupby("effective_date"):
        fwd -= set(day.loc[day["action"] == "exclude", "key"])
        fwd |= set(day.loc[day["action"] == "include", "key"])
    back = set(current_keys)
    for _, day in sorted(changes.groupby("effective_date"), key=lambda x: x[0], reverse=True):
        back -= set(day.loc[day["action"] == "include", "key"])
        back |= set(day.loc[day["action"] == "exclude", "key"])
    results.append(
        (
            "forward replay ends on today's list",
            fwd == current_keys,
            f"{len(fwd ^ current_keys)} stocks differ",
        )
    )
    results.append(
        (
            "backward replay ends on the earliest list",
            back == start,
            f"{len(back ^ start)} stocks differ",
        )
    )

    overlaps = 0
    for _, g in spells.sort_values("start_date", na_position="first").groupby("stock_id"):
        ends = g["end_date"].fillna(pd.Timestamp("2100-01-01")).tolist()
        starts = g["start_date"].fillna(pd.Timestamp("1900-01-01")).tolist()
        overlaps += sum(ends[i] > starts[i + 1] for i in range(len(g) - 1))
    results.append(("no stock has overlapping spells", overlaps == 0, f"{overlaps} overlaps"))

    monthly = pd.read_csv(out / "monthly_members.csv")
    counts = monthly.groupby("date").size()
    flagged = counts[
        (counts < cfg["universe"]["count_min"]) | (counts > cfg["universe"]["count_max"])
    ]
    report = (out / "universe_report.md").read_text()
    section = (
        report.split("### Flagged month-ends")[1].split("###")[0]
        if "### Flagged month-ends" in report
        else ""
    )
    unexplained = [d for d in flagged.index if d not in section]
    results.append(
        (
            "every flagged month is explained in the report",
            not unexplained,
            f"{len(flagged)} flagged, {len(unexplained)} unexplained",
        )
    )

    if (Path(cfg["paths"]["processed_prices"]) / "adj_close.parquet").exists():
        results += price_checks(cfg)
    if (Path(cfg["paths"]["processed_factors"]) / "momentum_scores.parquet").exists():
        from momentum.transform import momentum

        results += momentum.run_checks(cfg)
    if (Path(cfg["paths"]["results"]) / "phase3" / "primary_base" / "pnl_by_stock.csv").exists():
        from momentum.transform import backtest

        results += backtest.run_checks(cfg)
    if (Path(cfg["paths"]["results"]) / "phase4" / "folds.csv").exists():
        from momentum.transform import walkforward

        results += walkforward.run_checks(cfg)
    if (Path(cfg["paths"]["results"]) / "phase5" / "characteristics.parquet").exists():
        from momentum.transform import institutional

        results += institutional.run_checks(cfg)
    for name, ok, detail in results:
        logger.info(f"{'PASS' if ok else 'FAIL'}  {name}  ({detail})")
    if not all(ok for _, ok, _ in results):
        raise SystemExit(1)


def price_checks(cfg: dict) -> list:
    """Price checks: hand-recomputed adjustments, source rules, gap list."""
    from momentum.extract.prices import read_corp_actions, read_securities, trading_days
    from momentum.transform import prices

    out = Path(cfg["paths"]["processed_prices"])
    adj = pd.read_parquet(out / "adj_close.parquet")
    src = pd.read_csv(out / "price_source.csv")
    cc = pd.read_csv(out / "crosscheck.csv")
    used = pd.read_csv(out / "nse_adjustments_applied.csv", parse_dates=["ex_date"])
    sec = read_securities(cfg).set_index("file_id")
    last_day = trading_days(cfg).max()
    results = []

    # (1) NSE-only stocks: one split/bonus and one dividend factor recomputed from raw NSE closes
    nse_only = cc.loc[cc["cls"] == "nse only", "file_id"]
    picks = [
        f
        for f in nse_only
        if {"dividend"} <= set(used.loc[used["file_id"] == f, "kind"])
        and set(used.loc[used["file_id"] == f, "kind"]) & {"split", "bonus"}
    ][:3]
    bad, tried = 0, 0
    for f in picks:
        raw = prices.load_raw(cfg, "nse", f)
        raw = raw[raw["qty"] > 0]
        a = adj[f].dropna()
        for kind in (["split", "bonus"], ["dividend"]):
            e = used[(used["file_id"] == f) & used["kind"].isin(kind)].iloc[0]
            same_day = used[(used["file_id"] == f) & (used["ex_date"] == e["ex_date"])][
                "factor"
            ].prod()
            if kind == ["dividend"]:  # by hand: 1 - dividend / previous close on the ex-date
                ev = prices.parse_actions(
                    read_corp_actions(cfg, [s for s, _, _ in sec.at[f, "history"]])
                )
                amt = ev[(ev["kind"] == "dividend") & (ev["ex_date"] <= e["ex_date"])].iloc[-1][
                    "amount"
                ]
                expected = 1 - amt / raw["close"][raw.index < e["ex_date"]].iloc[-1]
                expected *= same_day / e["factor"]
            else:
                expected = same_day
            d = e["ex_date"]
            p = raw.index[raw.index < d][-1]
            implied = (a[p] / raw.at[p, "close"]) / (a[d] / raw.at[d, "close"])
            tried += 1
            bad += abs(implied / expected - 1) > 1e-6
    results.append(
        (
            "NSE-built adjustments recomputed by hand (3 stocks, split and dividend)",
            tried == 6 and bad == 0,
            f"{tried} recomputed, {bad} differ, stocks: {', '.join(picks)}",
        )
    )

    # (2) stocks with both sources follow the rule
    both = cc[cc["cls"].isin(["agree", "minor", "disagree"])]
    picks = (
        list(both[both["cls"] == "agree"]["file_id"][:1])
        + list(both[both["cls"] == "minor"]["file_id"][:1])
        + list(both[both["cls"] == "disagree"]["file_id"][:1])
    )
    bad = 0
    for f in picks:
        cls = cc.set_index("file_id").at[f, "cls"]
        if cls in ("agree", "minor"):
            want, _ = prices.clean_yahoo(prices.load_raw(cfg, "yahoo", f), last_day)
            want, _ = prices.drop_bad_yahoo_rows(
                want, prices.load_raw(cfg, "nse", f), cfg["prices"]["bad_row_tolerance"]
            )
            ev = prices.parse_actions(
                read_corp_actions(cfg, [s for s, _, _ in sec.at[f, "history"]])
            )
            want, _ = prices.add_nse_sessions(
                want["adj_close"].dropna(), prices.load_raw(cfg, "nse", f), ev
            )
        else:
            ev = prices.parse_actions(
                read_corp_actions(cfg, [s for s, _, _ in sec.at[f, "history"]])
            )
            _, want, _ = prices.nse_series(prices.load_raw(cfg, "nse", f), ev)
        got = adj[f].dropna()
        bad += not (
            got.index.equals(want.dropna().index) and np.allclose(got.values, want.dropna().values)
        )
    results.append(
        (
            "chosen series follows the source rule (agree, minor, disagree example)",
            bad == 0 and len(picks) == 3,
            f"{len(picks)} checked, {bad} wrong: {', '.join(picks)}",
        )
    )

    # (3) no price on a date the security did not trade
    extra = 0
    for f, source in zip(src["file_id"], src["price_source"], strict=False):
        if f not in adj.columns:
            continue
        if source == "yahoo":
            rows, _ = prices.clean_yahoo(prices.load_raw(cfg, "yahoo", f), last_day)
            raw = prices.load_raw(cfg, "nse", f)
            rows, _ = prices.drop_bad_yahoo_rows(rows, raw, cfg["prices"]["bad_row_tolerance"])
            traded = rows.index.union(raw.index[raw["qty"] > 0]) if raw is not None else rows.index
        else:
            raw = prices.load_raw(cfg, "nse", f)
            traded = raw.index[raw["qty"] > 0]
        extra += int((~adj[f].dropna().index.isin(traded)).sum())
    results.append(
        (
            "no price on a date the security did not trade",
            extra == 0,
            f"{extra} prices without a trade",
        )
    )

    # (4) every eligible member-month has a price or is in the gap list
    elig = pd.read_csv(Path(cfg["paths"]["processed_universe"]) / "eligibility.csv")
    gaps = pd.read_csv(out / "price_gaps.csv")
    need = elig[elig["eligible_member"] & ~elig["has_price"]][["date", "stock_id"]]
    listed = set(zip(gaps["date"], gaps["stock_id"], strict=False))
    missing = sum((d, s) not in listed for d, s in need.values)
    results.append(
        (
            "every eligible member-month has a price or is in the gap list",
            missing == 0,
            f"{len(need)} gaps, {missing} not listed",
        )
    )
    return results


def run(step: str, only_missing: bool = False, check: bool = False) -> None:
    """Run one stage; `all` rebuilds every result from raw files (the holdout is re-rendered)."""
    if step not in STEPS:
        raise ValueError(f"unknown step {step!r}; expected one of {STEPS}")
    cfg = load_config()
    do_check = check

    from momentum.extract import industry as industry_x
    from momentum.extract import prices as prices_x
    from momentum.extract import universe
    from momentum.report import reports
    from momentum.transform import (
        events,
        industry,
        liquidity,
        membership,
        momentum,
        prices,
        split,
    )

    if step in ("universe-download", "universe-all"):
        universe.run_download(cfg)
    if step in ("membership", "universe-all"):
        membership.build_membership(cfg)
        membership.apply_decisions(cfg)
        reports.write_decisions(cfg)
        reports.write_missing_notices(cfg)
        reports.write_report(cfg)
    if step in ("coverage", "universe-all"):
        universe.run_coverage(cfg)
        reports.write_report(cfg)
    if step in ("industry", "prices-all"):
        industry_x.download_wayback(cfg)
        spells = pd.read_csv(Path(cfg["paths"]["processed_universe"]) / "membership.csv")
        current = set(spells.loc[spells["end_date"].isna(), "stock_id"])
        industry_x.try_nse_quote(
            cfg, sorted(set(spells["stock_id"]) - current)
        )  # former members, latest symbol
        industry.build_industry(cfg)
    if step in ("prices-download", "prices-all"):
        prices_x.run_download(cfg, only_missing=only_missing)
    if step in ("prices-build", "prices-all"):
        prices.build_prices(cfg)
        prices.delistings(cfg)  # the event step reads the delisting cases
        events.build_events(cfg)
        reports.write_cleanup_reports(cfg)
    if step in ("prices-build", "liquidity", "prices-all"):
        elig, gaps = prices.build_eligibility(cfg)
        liq = liquidity.build_liquidity(cfg)
        delist = prices.delistings(cfg)
        off_days, thin_days = prices.calendar_check(cfg, elig)
        reports.write_prices_report(
            cfg,
            elig,
            gaps,
            delist,
            off_days,
            thin_days,
            liquidity.liquidity_summary(cfg, liq),
        )
    if step in ("split", "phase2-all"):
        split.write_split(cfg)
    if step in ("momentum", "phase2-all"):
        momentum.build_scores(cfg)
        reports.write_momentum_summary(cfg)
        if do_check:
            res = momentum.run_checks(cfg)
            for name, ok, detail in res:
                logger.info(f"{'PASS' if ok else 'FAIL'}  {name}  ({detail})")
    if step in ("diagnostics", "phase2-all"):
        from momentum.transform import diagnostics

        reports.write_signal_diagnostics(cfg, diagnostics.run_diagnostics(cfg))
    if step in ("phase3-all",):
        reports.write_data_fix_effect(cfg)
    if step in ("backtest", "phase3-all"):
        from momentum.transform import backtest

        backtest.run_all(cfg)
        reports.write_backtest_report(cfg)
    if step == "walkforward":
        from momentum.transform import walkforward

        folds_df, stitched, full_tab, full, ics, entry = walkforward.run_walkforward(cfg)
        reports.write_walkforward_report(cfg, folds_df, stitched, full_tab, full, entry)
        reports.write_frozen_config(cfg, full_tab)
    if step == "holdout":
        from momentum.transform import holdout

        reports.write_holdout_report(cfg, *holdout.run_holdout(cfg))
    if step == "institutional":
        from momentum.transform import institutional

        reports.write_institutional_report(cfg, institutional.run_institutional(cfg))
    if step == "all":
        # every result from the raw files (no downloads; the holdout is re-rendered from
        # its logged run, never rerun)
        from momentum.transform import holdout, institutional, walkforward

        membership.build_membership(cfg)
        membership.apply_decisions(cfg)
        reports.write_decisions(cfg)
        reports.write_missing_notices(cfg)
        reports.write_report(cfg)
        industry.build_industry(cfg)
        prices_x.run_download(cfg, parts=("extract",))
        prices.build_prices(cfg)
        prices.delistings(cfg)
        events.build_events(cfg)
        reports.write_cleanup_reports(cfg)
        elig, gaps = prices.build_eligibility(cfg)
        liq = liquidity.build_liquidity(cfg)
        off_days, thin_days = prices.calendar_check(cfg, elig)
        reports.write_prices_report(
            cfg,
            elig,
            gaps,
            prices.delistings(cfg),
            off_days,
            thin_days,
            liquidity.liquidity_summary(cfg, liq),
        )
        split.write_split(cfg)
        momentum.build_scores(cfg)
        reports.write_momentum_summary(cfg)
        from momentum.transform import diagnostics

        reports.write_signal_diagnostics(cfg, diagnostics.run_diagnostics(cfg))
        if (Path(cfg["paths"]["results"]) / "phase3" / "before").exists():
            reports.write_data_fix_effect(cfg)
        from momentum.transform import backtest

        backtest.run_all(cfg)
        reports.write_backtest_report(cfg)
        folds_df, stitched, full_tab, full, ics, entry = walkforward.run_walkforward(cfg)
        reports.write_walkforward_report(cfg, folds_df, stitched, full_tab, full, entry)
        reports.write_frozen_config(cfg, full_tab)
        saved = holdout.saved_holdout(cfg)
        if saved:
            reports.write_holdout_report(cfg, *saved)
        reports.write_institutional_report(cfg, institutional.run_institutional(cfg))
    if step in ("writeup", "all"):
        from momentum.report import writeup

        writeup.write_all(cfg)
    if step in (
        "check",
        "universe-all",
        "prices-all",
        "phase2-all",
        "phase3-all",
        "all",
    ):
        run_check(cfg)
