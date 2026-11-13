from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


def read(out: Path, name: str, **kw) -> pd.DataFrame:
    """A processed CSV, failing with the command that builds it."""
    path = out / name
    if not path.exists():
        raise SystemExit(f"Missing {path}. Run: python scripts/run.py membership")
    return pd.read_csv(path, **kw)


def table(df: pd.DataFrame) -> str:
    """A frame as a Markdown table."""
    if df.empty:
        return "(none)\n"
    cols = list(df.columns)
    lines = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    for _, r in df.iterrows():
        lines.append("| " + " | ".join("" if pd.isna(r[c]) else str(r[c]) for c in cols) + " |")
    return "\n".join(lines) + "\n"


def review_coverage(changes: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    """Months whose member count needs a notice that is missing."""
    # a review period counts as covered if some notice brings at least `review_min_rows` Nifty
    # 500 changes
    # into effect within a month either side of the review month
    u = cfg["universe"]
    start, today = pd.Timestamp(u["start_date"]), pd.Timestamp.today()
    rows = []
    for year in range(start.year, today.year + 1):
        for month in u["review_months"]:
            mid = pd.Timestamp(year=year, month=month, day=28)
            if mid > today:
                continue
            near = changes[
                (changes["effective_date"] - mid).abs()
                <= pd.Timedelta(days=u["review_window_days"])
            ]
            sizes = near.groupby(["effective_date", "source_file"]).size()
            big = sizes[sizes >= u["review_min_rows"]]
            moved = u.get("review_moved", {}).get(f"{mid:%b %Y}")
            if moved:
                rows.append(
                    dict(
                        review=f"{mid:%b %Y} review",
                        found=True,
                        effective_date=moved,
                        changes=None,
                        source="",
                    )
                )
                continue
            rows.append(
                dict(
                    review=f"{mid:%b %Y} review",
                    found=not big.empty,
                    effective_date=", ".join(sorted({f"{d:%Y-%m-%d}" for d, _ in big.index})),
                    changes=int(big.sum()) if not big.empty else 0,
                    source=", ".join(sorted({f for _, f in big.index})),
                )
            )
    return pd.DataFrame(rows)


def write_missing_notices(cfg: dict) -> pd.DataFrame:
    """Write the list of notices still to be found."""
    out = Path(cfg["paths"]["processed_universe"])
    changes = read(out, "index_changes.csv", parse_dates=["effective_date"])
    seen = read(out, "notices_parsed.csv")
    anomalies = read(out, "reconstruction_anomalies.csv")
    reviews = review_coverage(changes, cfg)
    missing = reviews[~reviews["found"]]
    unreadable = seen[seen["chars"] < cfg["ocr"]["min_chars"]]
    silent = seen[seen["mentions_n500"] & (seen["n500_rows"] == 0)]
    text = [
        "# Missing or unreadable index-change notices\n",
        f"Download any notice listed here by hand into `{cfg['paths']['manual_notices']}/` (PDF, "
        "any name "
        "containing `annYYYY-MM-DD`) and rerun `python scripts/run.py membership`.\n",
        "## Review periods with no parsed Nifty 500 review notice\n",
        "A review counts as found when one notice brings at least "
        f"{cfg['universe']['review_min_rows']} Nifty 500 changes into effect within "
        f"{cfg['universe']['review_window_days']} days of the end of the review month.\n",
        table(missing[["review"]]),
        "\n## Notices on the site that could not be read\n",
        "Empty text even after OCR, or the site returned an error page instead of a PDF.\n",
        table(unreadable[["source_file", "announce_date"]]),
        "\n## Notices that mention the Nifty 500 but gave no rows\n",
        "Mostly methodology or name-change notices; the irregular ones are transcribed in "
        f"`{cfg['paths']['manual_rows']}`.\n",
        table(silent[["source_file", "announce_date"]]),
        "\n## Gaps implied by the reconstruction\n",
        "Each line is a change that does not fit the list before or after it, which usually means "
        "a notice "
        "in between is missing.\n",
        table(
            anomalies[
                [
                    "effective_date",
                    "action",
                    "key",
                    "company_name",
                    "problem",
                    "source_file",
                ]
            ]
        ),
    ]
    (out / "missing_notices.md").write_text("\n".join(text))
    logger.info(f"saved {out / 'missing_notices.md'}")
    return missing


def explain_month(month: pd.Timestamp, changes, anomalies, missing_reviews) -> str:
    """Why a flagged month-end has an unusual member count."""
    # likely cause of a member count outside the expected range
    near = changes[(changes["effective_date"] - month).abs() <= pd.Timedelta(days=31)]
    bits = []
    if len(near):
        inc, exc = (
            (near["action"] == "include").sum(),
            (near["action"] == "exclude").sum(),
        )
        bits.append(
            f"{inc} inclusions and {exc} exclusions within a month (timing or a one-sided notice)"
        )
    dummies = near[near["key"].astype(str).str.startswith("DUMMY")]
    if len(dummies):
        bits.append("temporary demerger placeholders in the index")
    bad = anomalies[
        (pd.to_datetime(anomalies["effective_date"]) - month).abs() <= pd.Timedelta(days=200)
    ]
    if len(bad):
        bits.append(f"{len(bad)} reconstruction anomalies nearby (likely a missing notice)")
    if missing_reviews:
        bits.append("missing review notices: " + ", ".join(missing_reviews))
    return "; ".join(bits) or "no nearby change found: likely a missing notice"


def write_report(cfg: dict) -> None:
    """Write the universe report."""
    out = Path(cfg["paths"]["processed_universe"])
    u = cfg["universe"]
    changes = read(out, "index_changes.csv", parse_dates=["effective_date"])
    seen = read(out, "notices_parsed.csv", parse_dates=["announce_date"])
    membership = read(out, "membership.csv", parse_dates=["start_date", "end_date"])
    monthly = read(out, "monthly_members.csv", parse_dates=["date"])
    anomalies = read(out, "reconstruction_anomalies.csv")
    rescheduled = read(out, "rescheduled_dropped.csv")
    reviews = review_coverage(changes, cfg)
    missing_reviews = reviews.loc[~reviews["found"], "review"].tolist()

    used = seen[seen["n500_rows"] > 0]
    per_year = (
        used.groupby(used["announce_date"].dt.year)
        .size()
        .rename("notices with Nifty 500 rows")
        .reset_index()
    )
    per_year.columns = ["year", "notices with Nifty 500 rows"]

    counts = monthly.groupby("date").size()
    flagged = counts[(counts < u["count_min"]) | (counts > u["count_max"])]
    flagged_rows = [
        dict(
            month_end=f"{m:%Y-%m-%d}",
            members=n,
            likely_cause=explain_month(m, changes, anomalies, missing_reviews),
        )
        for m, n in flagged.items()
    ]

    stocks = membership.drop_duplicates("stock_id")
    renamed = stocks[stocks["symbol_history"].str.contains(";", na=False)][
        ["stock_id", "symbol_history"]
    ]
    current_ids = set(membership.loc[membership["end_date"].isna(), "stock_id"])
    former = stocks[~stocks["stock_id"].isin(current_ids)]
    no_industry = former[former["industry"].isna()][["stock_id", "company_name"]]
    fuzzy = changes[
        changes["match"].astype(str).str.startswith(("fuzzy", "by name", "exact", "unresolved"))
    ]
    manual = changes[changes["manual"].eq(True)] if "manual" in changes else changes.iloc[0:0]

    text = [
        "# Nifty 500 point-in-time universe report\n",
        f"Built {pd.Timestamp.today():%Y-%m-%d}. Window {u['start_date']} to today.\n",
        "## Notices\n",
        f"- Candidate press releases downloaded: {len(seen)}; mentioning the Nifty 500 (or CNX 500 "
        "/ S&P CNX 500): "
        f"{int(seen['mentions_n500'].sum())}; giving Nifty 500 change rows: {len(used)}.",
        f"- Change rows: {len(changes)} ({(changes['action'] == 'include').sum()} inclusions, "
        f"{(changes['action'] == 'exclude').sum()} exclusions); {len(manual)} transcribed by hand "
        f"(see `{cfg['paths']['manual_rows']}`).",
        "- Rescheduled duplicates dropped (a later notice moved an announced change): "
        f"{len(rescheduled)}.",
        f"- Review periods without a parsed review notice: {', '.join(missing_reviews) or 'none'} "
        "(see missing_notices.md).\n",
        table(per_year),
        "\n## Inclusions and exclusions per review\n",
        table(reviews.rename(columns={"changes": "rows"})),
        "\n## Stocks and membership counts\n",
        f"- Distinct stocks ever in the index in the window: {membership['stock_id'].nunique()} "
        f"({len(current_ids)} current, {len(former)} former).",
        f"- Membership spells: {len(membership)}.",
        f"- Members per month-end: min {counts.min()}, median {int(counts.median())}, max "
        f"{counts.max()} "
        f"over {len(counts)} month-ends.",
        f"- Month-ends outside {u['count_min']}-{u['count_max']}: {len(flagged)}.\n",
        "Counts slightly above 500 are expected: temporary demerger placeholders (DUMMY symbols) "
        "and, "
        "from April 2016 to August 2024, the Tata Motors DVR share counted as an extra security.\n",
        "### Flagged month-ends\n",
        table(pd.DataFrame(flagged_rows, columns=["month_end", "members", "likely_cause"])),
        "\n### Reconstruction anomalies\n",
        "Backward reconstruction from today's list: changes that did not fit (an inclusion of a "
        "stock that "
        "was not in the later list, or an exclusion of a stock already in the earlier list).\n",
        table(anomalies[["effective_date", "action", "key", "company_name", "problem"]]),
        "\n## Symbol changes applied\n",
        f"{len(renamed)} stocks carry more than one symbol (from NSE symbolchange.csv).\n",
        table(renamed),
        "\n## Name matches (notices without symbols, mostly 2009-2011)\n",
        table(fuzzy[["effective_date", "action", "company_name", "key", "match"]]),
        "\n## Former members without industry\n",
        f"Industry comes from today's NSE file; notices do not give it. {len(no_industry)} former "
        "members have none.\n",
        table(no_industry),
    ]

    cov_path = out / "price_coverage.csv"
    text.append("\n## Price coverage\n")
    if cov_path.exists():
        text.append(coverage_summary(pd.read_csv(cov_path), monthly))
    else:
        text.append("Not run yet: `python scripts/run.py coverage`.\n")
    (out / "universe_report.md").write_text("\n".join(text))
    logger.info(f"saved {out / 'universe_report.md'}")


def coverage_summary(cov: pd.DataFrame, monthly: pd.DataFrame) -> pd.DataFrame:
    """Coverage of members by Yahoo and NSE, by year."""
    cov["yahoo"] = cov["yahoo_first"].notna()
    former = cov[~cov["still_member"]]
    m = monthly.merge(
        cov[["stock_id", "yahoo_first", "yahoo_last", "nse_found"]],
        on="stock_id",
        how="left",
    )
    in_yahoo = (pd.to_datetime(m["yahoo_first"]) <= m["date"] + pd.offsets.MonthEnd(0)) & (
        pd.to_datetime(m["yahoo_last"]) >= m["date"] - pd.offsets.MonthBegin(1)
    )
    no_source = ~in_yahoo & ~m["nse_found"].fillna(False).astype(bool)
    yahoo_only_miss = ~in_yahoo
    lines = [
        f"- Stocks checked: {len(cov)} ({len(former)} former members).",
        f"- Yahoo has data: {cov['yahoo'].sum()} of {len(cov)}; former members missing on Yahoo: "
        f"{(~former['yahoo']).sum()} of {len(former)}.",
        "- Of those former members missing on Yahoo, NSE bhavcopy has the symbol on the sample "
        "date: "
        f"{(former[~former['yahoo']]['nse_found']).sum()}.",
        "- NSE bhavcopy has the symbol on its sample date (last month-end in the index): "
        f"{cov['nse_found'].sum()} of {len(cov)}.",
        f"- Member-months outside Yahoo's date range: {yahoo_only_miss.mean():.1%}.",
        "- Member-months with no price source (not on Yahoo for that month and not found in the "
        "NSE sample): "
        f"{no_source.mean():.1%} ({no_source.sum()} of {len(m)}).",
        "- NSE presence is tested on one sample date per stock, so it is taken to cover the whole "
        "membership; "
        "Phase 1 has to confirm this with the full bhavcopy history.\n",
        "### Stocks with no price source\n",
        table(
            cov[~cov["yahoo"] & ~cov["nse_found"]][
                ["stock_id", "member_symbol", "last_member_month", "nse_date"]
            ]
        ),
    ]
    return "\n".join(lines)


def write_decisions(cfg: dict) -> None:
    """Write the universe decisions report."""
    out = Path(cfg["paths"]["processed_universe"])
    d = cfg["decisions"]
    spells = read(out, "membership.csv", parse_dates=["start_date", "end_date"])
    base = read(out, "eligibility_base.csv", parse_dates=["date"])
    bad = spells[~spells["eligible"]]
    by_reason = (
        bad.groupby("excluded_reason")
        .agg(spells=("stock_id", "size"), stocks=("stock_id", "nunique"))
        .reset_index()
    )
    months = (
        base[base["excluded_reason"].fillna("") != ""]
        .groupby("excluded_reason")
        .size()
        .rename("month_end_rows")
        .reset_index()
    )

    # look for other second share classes among every stock ever in the index
    names = spells.drop_duplicates("stock_id")
    second = names[
        names["stock_id"].str.contains(r"DVR|PP$|PARTLY", regex=True)
        | names["company_name"].str.contains(
            r"DVR|'A' Ordinary|Differential|Partly Paid", case=False, na=False
        )
    ]

    gaps = []
    for g in d["missing_notices"]:
        lo, hi = pd.Timestamp(g["start"]), pd.Timestamp(g["end"])
        hit = spells[spells["start_date"].between(lo, hi) | spells["end_date"].between(lo, hi)]
        for _, s in hit.iterrows():
            gaps.append(
                dict(
                    missing_notice=g["name"],
                    stock_id=s["stock_id"],
                    company_name=s["company_name"],
                    start_date=s["start_date"].date() if pd.notna(s["start_date"]) else "",
                    end_date=s["end_date"].date() if pd.notna(s["end_date"]) else "",
                )
            )
    manual = sorted(p.name for p in Path(cfg["paths"]["manual_notices"]).glob("*.pdf"))

    text = [
        "# Universe decisions\n",
        f"Applied {pd.Timestamp.today():%Y-%m-%d}. Rules are in `configs/config.yaml` under "
        "`decisions`.\n",
        "1. **Demerger placeholders** (DUMMY symbols, and spun-off entities included before "
        "listing): never eligible. "
        "Every such spell in the window ends with the post-listing exclusion, so the whole spell "
        "is ineligible "
        "(this drops at most a few days of post-listing membership).",
        "2. **Second share classes**: never eligible (one company, one security).",
        "3. **Missing notices**: kept as documented gaps; the spells below start or end inside the "
        "window of a "
        "missing notice and may depend on it. A missing notice can also hide a change for any "
        "other stock; the "
        "reconstruction found no conflict except Jindal Saw.",
        "4. **Jindal Saw**: excluded 22 Nov 2011 and again 29 Apr 2016 with no inclusion found "
        "between. It is not a "
        "member in that window in `monthly_members.csv`; the possible spell is added to "
        "`membership.csv` with "
        "`eligible = false`. Manual notices present: " + (", ".join(manual) or "none") + ".",
        "5. **Eligible** at a month-end = member that day, not excluded above, and a usable price "
        "(added in Phase 1 "
        "prices). Base table: `eligibility_base.csv`.\n",
        "## Ineligible spells by reason\n",
        table(by_reason),
        "\n## Excluded month-end rows by reason\n",
        table(months),
        "\n## Ineligible spells\n",
        table(
            bad[
                [
                    "stock_id",
                    "company_name",
                    "start_date",
                    "end_date",
                    "excluded_reason",
                ]
            ].assign(start_date=bad["start_date"].dt.date, end_date=bad["end_date"].dt.date)
        ),
        "\n## Second share classes found\n",
        table(second[["stock_id", "company_name"]]),
        "\n## Spells that may depend on a missing notice\n",
        table(pd.DataFrame(gaps)),
    ]
    (out / "universe_decisions.md").write_text("\n".join(text))
    logger.info(f"saved {out / 'universe_decisions.md'}")


def log_counts(path: Path, col: str) -> str:
    """Counts of outcomes in a download log."""
    if not path.exists():
        return "no log"
    log = pd.read_csv(path)
    return ", ".join(
        f"{k}: {v}" for k, v in log[col].astype(str).str.split(":").str[0].value_counts().items()
    )


def write_prices_report(cfg: dict, elig, gaps, delist, off_days, thin_days, liq_summary) -> None:
    """Write the prices report: sources, gaps, delistings, calendar, liquidity."""
    from momentum.transform.industry import industry_coverage

    raw, out = Path(cfg["paths"]["raw_prices"]), Path(cfg["paths"]["processed_prices"])
    src = pd.read_csv(out / "price_source.csv")
    cc = pd.read_csv(out / "crosscheck.csv")
    used = pd.read_csv(out / "nse_adjustments_applied.csv")
    cand = pd.read_csv(out / "price_event_candidates.csv")
    ev = pd.read_csv(out / "corporate_actions_parsed.csv")
    ylog = pd.read_csv(raw / "yahoo" / "download_log.csv")
    by_sec = ylog.groupby("file_id")["rows"].max()

    em = elig[elig["eligible_member"]]
    by_month = em.groupby("date")["has_price"].mean()
    worst = by_month.sort_values().head(5)
    examples = pd.concat([cc[cc["cls"] == k].head(3) for k in ["agree", "minor", "disagree"]])
    nse_only = src[src["price_source"] == "nse_built"].merge(cc[["file_id", "cls"]], on="file_id")
    by_source, unclassified, uncl_stocks = industry_coverage(cfg)

    text = [
        "# Prices report\n",
        f"Built {pd.Timestamp.today():%Y-%m-%d}.\n",
        "## Downloads\n",
        f"- Benchmarks (niftyindices.com): {len(list((raw / 'index').glob('*.json')))} files for "
        f"{', '.join(cfg['prices']['indices'])} (TRI and price).",
        f"- NSE bhavcopy: {len(list((raw / 'nse_bhavcopy').glob('bhav_*.zip')))} daily files for "
        f"{len(trading_days_list(cfg))} index trading days; log: "
        f"{log_counts(raw / 'nse_bhavcopy' / 'download_log.csv', 'status')}.",
        f"- Yahoo: {int((by_sec > 0).sum())} of {by_sec.size} securities have data; requests: "
        f"{log_counts(raw / 'yahoo' / 'download_log.csv', 'status')}.",
        "- NSE corporate actions: "
        f"{log_counts(raw / 'nse_corp_actions' / 'download_log.csv', 'status')}.",
        f"- Yahoo filler rows removed: {(out / 'yahoo_fillers_removed.txt').read_text()}.\n",
        "## Price source\n",
        table(src["price_source"].value_counts().rename("securities").reset_index()),
        "\nNSE sessions added to Yahoo series (sessions Yahoo leaves out, e.g. weekend budget "
        "days and Muhurat "
        "trading; NSE close scaled by the adjacent Yahoo/NSE ratio): "
        f"{int(src['nse_sessions_added'].sum())} "
        f"rows across {int((src['nse_sessions_added'] > 0).sum())} securities.\n",
        "\n## Cross-check (Yahoo close vs NSE close adjusted for splits and bonuses)\n",
        f"Within {cfg['crosscheck']['tolerance']:.1%} on at least "
        f"{cfg['crosscheck']['agree_share']:.0%} of days = agree; "
        f"at least {cfg['crosscheck']['minor_share']:.0%} with no run longer than "
        f"{cfg['crosscheck']['max_bad_run']} days = minor; "
        "otherwise, or any split/bonus factor mismatch, or Yahoo covering under "
        f"{cfg['crosscheck']['min_yahoo_coverage']:.0%} of NSE days = disagree. Rule: Yahoo "
        "adj_close for agree/minor, NSE-built series otherwise.\n",
        table(cc["cls"].value_counts().rename("securities").reset_index()),
        "\n### Examples\n",
        table(
            examples[
                [
                    "file_id",
                    "stock_id",
                    "cls",
                    "share_within",
                    "factor_mismatches",
                    "note",
                    "worst",
                ]
            ]
        ),
        "\n## NSE-built series\n",
        f"{len(nse_only)} securities use the NSE-built series. Adjustments applied (all securities "
        "with NSE data):\n",
        table(used["kind"].value_counts().rename("events").reset_index()),
        "\nRights issues, demergers and bonus debentures / preference shares are not adjusted; "
        "listed for review:\n",
        table(
            ev[ev["kind"].isin(["rights", "demerger", "bonus securities"])]
            .groupby("kind")
            .size()
            .rename("events")
            .reset_index()
        ),
        "\n(full list in `corporate_actions_parsed.csv`)\n",
        "\n## One-day moves above "
        f"{cfg['prices']['event_move']:.0%} with no corporate action nearby (for review)\n",
        f"{len(cand)} candidates in `price_event_candidates.csv`.\n",
        table(cand.head(30)),
        "\n## Delistings and mergers\n",
        "Securities whose last price falls inside a spell or within 2 months after it. Backtest "
        "rule: a holding is sold "
        "at its last available close. Merger or buyback proceeds may differ from that close.\n",
        table(delist),
        "\n## Trading calendar (NIFTY 50 index days)\n",
        f"- Securities with prices on non-index days: {len(off_days)}.\n",
        table(off_days.head(20)),
        f"\n- Index days with more than {cfg['prices']['max_missing_share']:.0%} of eligible "
        f"stocks missing: {len(thin_days)}.\n",
        table(thin_days.head(30)),
        "\n## Eligible member-months with a usable price\n",
        f"- Overall: {em['has_price'].mean():.2%} ({int(em['has_price'].sum())} of {len(em)}). "
        "Target above 99%.",
        "- Worst month-ends:\n",
        table(worst.rename("share_with_price").reset_index()),
        f"\n- Gaps ({len(gaps)} member-months without a price, full list `price_gaps.csv`):\n",
        table(
            gaps.groupby("stock_id")
            .agg(months=("date", "size"), first=("date", "min"), last=("date", "max"))
            .reset_index()
            .sort_values("months", ascending=False)
            .head(40)
        ),
        "\n## Liquidity (median daily traded value, trailing 63 days, Rs crore; thresholds "
        "VERIFY)\n",
        table(liq_summary),
        "\n## Industry coverage (eligible member-months)\n",
        table(by_source),
        f"\nUnclassified: {unclassified:.2%} of eligible member-months "
        f"(limit {cfg['industry']['max_unclassified_share']:.0%}). Mapping table: "
        f"`{cfg['paths']['industry_map']}`; "
        "hand overrides: `" + cfg["paths"]["manual_industry"] + "`.\n",
        table(uncl_stocks.sort_values("member_months", ascending=False)),
    ]
    (out / "prices_report.md").write_text("\n".join(text))
    logger.info(f"saved {out / 'prices_report.md'}")


def trading_days_list(cfg: dict) -> list:
    """Trading days as a list."""
    from momentum.extract.prices import trading_days

    return trading_days(cfg)


def write_cleanup_reports(cfg: dict) -> None:
    """Write the price-cleaning and event reports."""
    out = Path(cfg["paths"]["processed_prices"])
    res = pd.read_csv(out / "disagree_resolution.csv")
    src = pd.read_csv(out / "price_source.csv")
    switched = res[res["decision"] == "NSE record missing corporate action"]
    text = [
        "# Disagree resolution (Phase 1c)\n",
        "Stocks where Yahoo's close and NSE's close (adjusted for NSE splits and bonuses) "
        "disagree. Rule: switch to "
        "Yahoo only if there is a single lasting step, Yahoo's step is a standard split/bonus "
        "ratio within "
        f"{cfg['crosscheck']['standard_tolerance']:.0%}, NSE's raw close moves by the same factor "
        "(within "
        f"{cfg['crosscheck']['raw_move_tolerance']:.0%}) and NSE records no split/bonus on that "
        "date. Otherwise keep "
        "the NSE-built series.\n",
        f"- Switched to Yahoo: {len(switched)}; kept on NSE: {len(res) - len(switched)}.\n",
        table(
            res.rename(
                columns={
                    "yahoo_factor": "step (Yahoo factor)",
                    "standard": "nearest standard ratio",
                    "raw_move": "NSE raw move",
                }
            ).assign(
                choice=lambda d: np.where(
                    d["decision"] == "NSE record missing corporate action",
                    "yahoo",
                    "nse_built",
                )
            )[
                [
                    "stock_id",
                    "step_date",
                    "step (Yahoo factor)",
                    "nearest standard ratio",
                    "NSE raw move",
                    "decision",
                    "choice",
                    "note",
                ]
            ]
        ),
    ]
    (out / "disagree_resolution.md").write_text("\n".join(text))

    dr = pd.read_csv(out / "demerger_rights_review.csv")
    ev = pd.read_csv(out / "event_review.csv")
    rel = pd.read_csv(out / "relisted_check.csv")
    excl = pd.read_csv(out / "lookback_exclusions.csv")
    names = src.set_index("file_id")["stock_id"]
    dr["stock_id"] = dr["file_id"].map(names)
    from momentum.extract.prices import trading_days

    days = trading_days(cfg)
    text = [
        "# Event review (Phase 1c)\n",
        "## Demergers and rights issues (eligible stocks, 2010-2026)\n",
        "Implied value: theoretical ex-rights drop for rights with a stated price, otherwise NSE's "
        "raw drop beyond "
        "the NIFTY 500 that day. `unadjusted` = the chosen series falls by more than half the "
        "implied value relative "
        f"to the market and is still down {cfg['events']['recover_days']} trading days later. "
        "Values below "
        f"{cfg['events']['min_value']:.0%} are immaterial. Rule for `unadjusted`: ineligible at "
        "any month-end whose "
        "12-month look-back contains the ex-date; the ex-date return is set to 0 in a holding "
        "month.\n",
        table(dr["status"].value_counts().rename("events").reset_index()),
        "\n`no price around ex-date`: the ex-date is outside the stock's price window (before it "
        "was needed or after it left).\n",
        table(
            dr[dr["status"].isin(["unadjusted", "adjusted"])][
                [
                    "stock_id",
                    "ex_date",
                    "kind",
                    "source",
                    "implied_value",
                    "raw_move",
                    "series_move",
                    "market_move",
                    "status",
                ]
            ].sort_values(["status", "ex_date"])
        ),
        f"\n## One-day moves above {cfg['prices']['event_move']:.0%} with no corporate action in "
        "the build\n",
        "`corporate_action`: a Yahoo split, an NSE corporate action or a demerger notice within "
        f"{cfg['events']['match_days']} days (treated like an unadjusted demerger). `real`: NSE's "
        "raw close shows the "
        f"same move (within {cfg['events']['same_move']:.0%}), volume at least "
        f"{cfg['events']['min_volume_ratio']}x the "
        f"{cfg['events']['volume_days']}-day median, not reversed within "
        f"{cfg['events']['recover_days']} days. "
        "`suspect`: anything else; quarantined (ineligible at any month-end whose look-back "
        "contains the date).\n",
        table(ev["cls"].value_counts().rename("cases").reset_index()),
        "\n" + table(ev.drop(columns=["file_id"])),
        "\n## Delisting cases that trade again under another symbol (same ISIN issuer code)\n",
        "`traded_again`: found in the bhavcopy within "
        f"{cfg['events']['relist_days']} days of the last price (ISINs are in the bhavcopy from "
        "2012). `listed_today`: "
        "the issuer is in today's NSE equity list. Castrol (CASTROL -> CASTROLIND, 14 Mar 2014) is "
        "fixed in "
        f"`{cfg['paths']['manual_symbol_changes']}` and is no longer a delisting case.\n",
        table(rel),
        "\n## Exclusions written\n",
        table(excl["reason"].value_counts().rename("stock-dates").reset_index()),
        "\n## Trading calendar\n",
        f"Every step uses the NIFTY 50 index calendar ({len(days)} days, {days.min():%Y-%m-%d} to "
        f"{days.max():%Y-%m-%d}), "
        f"including {int((days.dayofweek >= 5).sum())} weekend special sessions (budget days, "
        "Muhurat trading). "
        f"Yahoo rows that disagreed with NSE on a single day and were replaced by the NSE trade: "
        f"{(out / 'yahoo_bad_rows_removed.txt').read_text()}.\n",
    ]
    (out / "event_review.md").write_text("\n".join(text))
    logger.info(f"saved {out / 'disagree_resolution.md'} and {out / 'event_review.md'}")


def write_momentum_summary(cfg: dict) -> None:
    """Write the momentum-score summary."""
    out = Path(cfg["paths"]["processed_factors"])
    s = pd.read_parquet(out / "momentum_scores.parquet")
    n = s[s["eligible"]].groupby("date").size()
    members = s.groupby("date").size()
    by_year = (
        n.groupby(n.index.year)
        .agg(["min", "median", "max"])
        .reset_index()
        .rename(columns={"date": "year"})
    )
    reasons = (
        s[~s["eligible"]]["reason_if_not"].value_counts().rename("member-months").reset_index()
    )
    text = [
        "# Momentum factor\n",
        "Scores for every signal date (development and holdout); forward returns of holdout dates "
        "are not read.\n",
        f"- Signal dates: {n.index.size} ({n.index.min():%Y-%m-%d} to {n.index.max():%Y-%m-%d}).",
        f"- Eligible stocks per month: min {n.min()} ({n.idxmin():%Y-%m}), median "
        f"{int(n.median())}, max {n.max()} "
        f"({n.idxmax():%Y-%m}); members per month median {int(members.median())}.\n",
        "## Eligible stocks per month, by year\n",
        table(by_year),
        "\n## Why members were not eligible (member-months)\n",
        table(reasons),
    ]
    (out / "momentum_summary.md").write_text("\n".join(text))
    logger.info(f"saved {out / 'momentum_summary.md'}")


INK, MUTED, GRID, SURFACE, BLUE = "#0b0b0b", "#52514e", "#e5e4e0", "#fcfcfb", "#2a78d6"


def chart_axes(title: str, ylabel: str) -> tuple:
    """A figure and axes in the house style."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(7, 3.8), dpi=150)
    fig.patch.set_facecolor(SURFACE)
    ax.set_facecolor(SURFACE)
    for side in ["top", "right"]:
        ax.spines[side].set_visible(False)
    for side in ["left", "bottom"]:
        ax.spines[side].set_color(GRID)
    ax.tick_params(colors=MUTED, labelsize=8)
    ax.yaxis.grid(True, color=GRID, linewidth=0.6)
    ax.set_axisbelow(True)
    ax.set_title(title, color=INK, fontsize=10, loc="left")
    ax.set_ylabel(ylabel, color=MUTED, fontsize=8)
    ax.axhline(0, color=MUTED, linewidth=0.8)
    return fig, ax


def write_charts(res: dict, out: Path) -> None:
    """Phase 2 charts."""
    import matplotlib.pyplot as plt

    b = res["buckets_5"]["mean"]
    fig, ax = chart_axes(
        "Mean monthly return by momentum quintile (development, gross)", "% per month"
    )
    q = [f"Q{i}" for i in range(1, 6)]
    vals = [b[i] * 100 for i in range(1, 6)]
    ax.bar(q, vals, width=0.6, color=BLUE, edgecolor=SURFACE, linewidth=2)
    for x, v in zip(q, vals, strict=False):
        ax.annotate(
            f"{v:.2f}",
            (x, v),
            textcoords="offset points",
            xytext=(0, 3),
            ha="center",
            fontsize=8,
            color=MUTED,
            bbox=dict(facecolor=SURFACE, edgecolor="none", pad=1),
            zorder=4,
        )
    ax.axhline(b["universe"] * 100, color=MUTED, linewidth=1, linestyle="--", zorder=3)
    ax.annotate(
        f"eligible universe {b['universe'] * 100:.2f}",
        (-0.45, b["universe"] * 100),
        textcoords="offset points",
        xytext=(0, 3),
        ha="left",
        fontsize=8,
        color=MUTED,
        bbox=dict(facecolor=SURFACE, edgecolor="none", pad=1),
        zorder=4,
    )
    ax.set_xlabel("Q1 = lowest score, Q5 = highest", color=MUTED, fontsize=8)
    fig.tight_layout()
    fig.savefig(out / "quintile_returns.png", facecolor=SURFACE)
    plt.close(fig)

    tmu = res["tmu_series"]
    fig, ax = chart_axes("Cumulative Q5 minus universe return (development, gross)", "cumulative %")
    cum = ((1 + tmu).cumprod() - 1) * 100
    ax.plot(cum.index, cum.values, color=BLUE, linewidth=2)
    fig.tight_layout()
    fig.savefig(out / "cumulative_top_minus_universe.png", facecolor=SURFACE)
    plt.close(fig)

    dec = res["ic_decay"]
    fig, ax = chart_axes(
        "IC of the score with returns h months ahead (mean, 95% interval)",
        "mean monthly IC",
    )
    labels = [f"t+{int(h)}" for h in dec.index]
    ax.errorbar(
        labels,
        dec["mean"],
        yerr=1.96 * dec["se"],
        fmt="o",
        color=BLUE,
        ecolor=BLUE,
        elinewidth=1.5,
        capsize=4,
        markersize=6,
    )
    fig.tight_layout()
    fig.savefig(out / "ic_decay.png", facecolor=SURFACE)
    plt.close(fig)

    y = res["ic_by_year"]["score"]
    fig, ax = chart_axes("Mean monthly IC of the score by year (development)", "mean IC")
    ax.bar(
        [str(i) for i in y.index],
        y.values,
        width=0.6,
        color=BLUE,
        edgecolor=SURFACE,
        linewidth=2,
    )
    ax.tick_params(axis="x", rotation=45)
    fig.tight_layout()
    fig.savefig(out / "ic_by_year.png", facecolor=SURFACE)
    plt.close(fig)


def write_signal_diagnostics(cfg: dict, res: dict):
    """Write the Phase 2 signal diagnostics report and tables."""
    out = Path(cfg["paths"]["results"]) / "phase2"
    write_charts(res, out)

    def pct(x):
        return f"{x * 100:.2f}%"

    ic, s5, s10 = res["ic_summary"], res["spread_5"], res["spread_10"]
    b5 = res["buckets_5"]["mean"]
    dec, liq, surv = res["ic_decay"], res["liquidity"], res["survivorship"]
    start, end, n = res["months"]
    neg_years = [str(y) for y, v in res["ic_by_year"]["score"].items() if v < 0]
    stronger = "12-1" if ic.at["z_12_1", "mean"] > ic.at["z_6_1", "mean"] else "6-1"
    half = (
        f"about {res['half_life']:.1f} months after its peak at t+{res['decay_peak']}"
        if not np.isnan(res["half_life"])
        else "not estimable from this pattern"
    )
    lt = liq["mean"]
    sp, st = surv.loc["point-in-time Nifty 500"], surv.loc["today's list for all dates"]
    text = [
        "# Signal diagnostics\n",
        "**Development period only; holdout locked.**\n",
        f"Signal months {start:%Y-%m} to {end:%Y-%m} ({n} months). Returns run from the execution "
        "close after each "
        "signal date to the execution close after the next one, equal weight, gross of costs. "
        "t-statistics are "
        f"Newey-West with {cfg['diagnostics']['newey_west_lags']} lags.\n",
        "## Reading\n",
        f"- **IC.** The score's mean monthly rank IC is {ic.at['score', 'mean']:.3f} (t = "
        f"{ic.at['score', 'nw_t']:.2f}), "
        f"positive in {ic.at['score', 'share_positive']:.0%} of months; ICIR "
        f"{ic.at['score', 'icir']:.2f} "
        f"({ic.at['score', 'icir_annual']:.2f} annualised). Of the two parts, {stronger} is "
        "stronger "
        f"(12-1: {ic.at['z_12_1', 'mean']:.3f}, t = {ic.at['z_12_1', 'nw_t']:.2f}; 6-1: "
        f"{ic.at['z_6_1', 'mean']:.3f}, "
        f"t = {ic.at['z_6_1', 'nw_t']:.2f}). Years with a negative mean IC: "
        f"{', '.join(neg_years) or 'none'}.",
        f"- **Quintiles.** Mean monthly return rises from {pct(b5[1])} in Q1 to {pct(b5[5])} in Q5 "
        f"(universe {pct(b5['universe'])}); "
        f"monotonicity {s5['monotonicity'].iloc[0]:.2f}. Q5 minus Q1: "
        f"{pct(s5.at['top_minus_bottom', 'mean'])} a month "
        f"(t = {s5.at['top_minus_bottom', 'nw_t']:.2f}); Q5 minus universe: "
        f"{pct(s5.at['top_minus_universe', 'mean'])} "
        f"(t = {s5.at['top_minus_universe', 'nw_t']:.2f}). Deciles: D10 minus D1 "
        f"{pct(s10.at['top_minus_bottom', 'mean'])} "
        f"(t = {s10.at['top_minus_bottom', 'nw_t']:.2f}), monotonicity "
        f"{s10['monotonicity'].iloc[0]:.2f}.",
        "- **Decay.** Single-month IC is "
        + ", ".join(
            f"t+{int(h)} {v:.3f} (t = {t:.2f})"
            for h, v, t in zip(dec.index, dec["mean"], dec["nw_t"], strict=False)
        )
        + ". "
        f"The signal peaks at t+{res['decay_peak']}; half-life {half}.",
        "- **Liquidity.** Q5 minus Q1 within liquidity terciles: "
        + "; ".join(f"{k} {pct(v)} (t = {liq.at[k, 'nw_t']:.2f})" for k, v in lt.items())
        + f". The spread is {'larger' if lt.iloc[0] > lt.iloc[-1] else 'smaller'} among the "
        "least liquid third than the most liquid.",
        "- **Survivorship.** Using today's list for all dates (the old method, NSE-built prices "
        "for today's members) gives "
        f"mean IC {st['ic_mean']:.3f} (t = {st['ic_nw_t']:.2f}) and Q5 minus Q1 "
        f"{pct(st['q5_minus_q1'])} (t = {st['q5_minus_q1_t']:.2f}), "
        f"against {sp['ic_mean']:.3f} (t = {sp['ic_nw_t']:.2f}) and {pct(sp['q5_minus_q1'])} (t = "
        f"{sp['q5_minus_q1_t']:.2f}) point in time. "
        f"The universe's mean monthly return is {pct(st['universe_return'])} with today's list vs "
        f"{pct(sp['universe_return'])} point in time "
        f"(difference {pct(st['universe_return'] - sp['universe_return'])} a month).\n",
        "## Information coefficient\n",
        table(ic.round(4).reset_index().rename(columns={"index": "signal"})),
        "\n### By year (mean monthly IC)\n",
        table(res["ic_by_year"].round(3).reset_index().rename(columns={"date": "year"})),
        "\n## Quintiles\n",
        table(res["buckets_5"].round(4).reset_index()),
        "\n",
        table(s5.round(4).reset_index()),
        "\n### By year\n",
        table(res["spread_5_by_year"].round(4).reset_index().rename(columns={"date": "year"})),
        "\n## Deciles\n",
        table(res["buckets_10"].round(4).reset_index()),
        "\n",
        table(s10.round(4).reset_index()),
        "\n## IC decay\n",
        table(dec.round(4).reset_index().rename(columns={"index": "horizon (months)"})),
        "\nHorizons whose return month falls in the holdout are dropped, so later horizons have "
        "fewer months.\n",
        "\n## Liquidity terciles (Q5 minus Q1 within each)\n",
        table(liq.round(4).reset_index()),
        "\n## Survivorship comparison (descriptive)\n",
        table(surv.round(4).reset_index()),
        "\n## Charts\n",
        "![quintiles](quintile_returns.png)\n",
        "![cumulative](cumulative_top_minus_universe.png)\n",
        "![decay](ic_decay.png)\n",
        "![by year](ic_by_year.png)\n",
    ]
    (out / "signal_diagnostics.md").write_text("\n".join(text))
    logger.info(f"saved {out / 'signal_diagnostics.md'}")


def write_data_fix_effect(cfg: dict) -> None:
    """Compare signal results before and after the Phase 3 data fixes."""
    from momentum.extract.prices import trading_days
    from momentum.transform.momentum import asof_price
    from momentum.transform.split import signal_dates, special_sessions

    res, pp = Path(cfg["paths"]["results"]), Path(cfg["paths"]["processed_prices"])
    before, after = res / "phase3" / "before", res / "phase2"
    rows = []
    for name, idx, cols in [
        ("ic_summary", ["score", "z_12_1", "z_6_1"], ["mean", "nw_t"]),
        ("spread_5", ["top_minus_bottom", "top_minus_universe"], ["mean", "nw_t"]),
        ("ic_decay", [1, 2, 3, 6, 12], ["mean", "nw_t"]),
    ]:
        b, a = (
            pd.read_csv(before / f"{name}.csv", index_col=0),
            pd.read_csv(after / f"{name}.csv", index_col=0),
        )
        for i in idx:
            for c in cols:
                label = {
                    "ic_summary": f"IC {i}",
                    "spread_5": f"Q5 {str(i).replace('_', ' ')}",
                    "ic_decay": f"IC decay t+{i}",
                }[name]
                rows.append(
                    dict(
                        measure=f"{label} ({'t' if c == 'nw_t' else 'mean'})",
                        before=round(b.at[i, c], 4),
                        after=round(a.at[i, c], 4),
                        change=round(a.at[i, c] - b.at[i, c], 4),
                    )
                )
    eb = pd.read_csv(before / "event_review.csv")[["stock_id", "date", "move", "cls"]]
    ea = pd.read_csv(pp / "event_review.csv")[["stock_id", "date", "move", "cls", "why"]]
    ev = eb.merge(ea, on=["stock_id", "date"], how="outer", suffixes=("_before", "_after"))
    ev = ev[(ev["cls_before"] == "suspect") | (ev["cls_after"] == "suspect")]
    sym = pd.read_csv(cfg["paths"]["manual_symbol_changes"], comment="#")
    relisted = pd.read_csv(pp / "relisted_check.csv")
    susp = pd.read_csv(pp / "suspensions.csv")
    sp = special_sessions(cfg)
    sd = signal_dates(cfg)
    # lag staleness: a lag price up to max_lag_staleness_days old is used, older is not
    days = trading_days(cfg)
    k = cfg["momentum"]["max_lag_staleness_days"]
    test = pd.Series([1.0], index=[days[100]])
    ok_old = not np.isnan(asof_price(test, days[100 + k], days, k)[0])
    ok_stale = np.isnan(asof_price(test, days[100 + k + 1], days, k)[0])
    scores = pd.read_parquet(Path(cfg["paths"]["processed_factors"]) / "momentum_scores.parquet")
    text = [
        "# Effect of the Phase 3 data-rule fixes\n",
        "Development period only; holdout locked. Before = Phase 2 as committed; after = the same "
        "code with the fixes below.\n",
        "## Headline diagnostics\n",
        table(pd.DataFrame(rows)),
        "\n## 1. Suspect moves (real if NSE confirms on at least median volume, even if "
        "reversed)\n",
        table(ev),
        "\n## 2. Execution on regular sessions\n",
        f"Special sessions ({len(sp)}): weekend sessions and weekday sessions with turnover below "
        f"{cfg['split']['special_turnover_ratio']:.0%} of the trailing "
        f"{cfg['split']['turnover_window']}-session median "
        "(Muhurat trading). They are used for marking prices, never for execution. Execution dates "
        "on a special session "
        f"now: {int(sd['execution_date'].isin(sp['date']).sum())}.\n",
        table(sp.assign(date=sp["date"].dt.date)),
        "\n## 3. Symbols that reappear under a new symbol (same issuer)\n",
        f"Added to `{cfg['paths']['manual_symbol_changes']}`:\n",
        table(sym),
        "\nStill delisting cases, deliberately not merged: re-listings years later with a new ISIN "
        "(CHEMPLAST 2012 -> "
        "2021, HEXAWARE 2020 -> 2025), the same symbol absent from NSE's bhavcopy for 2.5 years "
        "(KENNAMET, KIRLFER), and "
        "KIRLOSIND, whose 65-day gap after the KIRLOSOIL change exceeds the 60-day suspension "
        "limit.\n",
        table(relisted),
        "\n## 4. Suspensions (held, not sold; valued at the first close after trading resumes)\n",
        f"Stops of at least {cfg['events']['suspension_min_days']} index sessions with trading "
        "again within "
        f"{cfg['events']['suspension_max_days']} days.\n",
        table(susp),
        "\n## 5. Lag prices\n",
        f"Each lag price is the last close on or before the lag date if it is at most {k} trading "
        "days old "
        f"(test: {k} days old used = {ok_old}, {k + 1} days old rejected = {ok_stale}). "
        "Member-months ineligible for "
        "a stale or missing lag price: "
        f"{int((scores['reason_if_not'] == 'no price on a lag date').sum())}.\n",
    ]
    out = res / "phase3"
    out.mkdir(parents=True, exist_ok=True)
    (out / "data_fix_effect.md").write_text("\n".join(text))
    logger.info(f"saved {out / 'data_fix_effect.md'}")


SERIES = {
    "primary": ("#2a78d6", "Primary (monthly)"),
    "quarterly": ("#eb6834", "Quarterly"),
    "equal_weight": ("#1baf7a", "Equal weight (eligible)"),
    "NIFTY 500": ("#eda100", "NIFTY 500 TRI (index)"),
    "NIFTY 50": ("#e87ba4", "NIFTY 50 TRI (index)"),
}


def backtest_charts(out: Path, eqs, dds, roll, costs_year) -> None:
    """Phase 3 charts: equity, drawdown, rolling excess, costs."""
    import matplotlib.pyplot as plt

    fig, ax = chart_axes("Equity, Rs (log scale), base costs; indices without costs", "Rs")
    ax.axhline(0, alpha=0)
    for k, s in eqs.items():
        ax.plot(s.index, s.values, color=SERIES[k][0], linewidth=2, label=SERIES[k][1])
    ax.set_yscale("log")
    ax.legend(frameon=False, fontsize=8, labelcolor=MUTED)
    fig.tight_layout()
    fig.savefig(out / "equity_curves.png", facecolor=SURFACE)
    plt.close(fig)

    fig, ax = chart_axes("Drawdown from previous peak, base costs", "%")
    for k, s in dds.items():
        ax.plot(
            s.index,
            s.values * 100,
            color=SERIES[k][0],
            linewidth=1.5,
            label=SERIES[k][1],
        )
    ax.legend(frameon=False, fontsize=8, labelcolor=MUTED)
    fig.tight_layout()
    fig.savefig(out / "drawdowns.png", facecolor=SURFACE)
    plt.close(fig)

    fig, ax = chart_axes(
        "Rolling 36-month excess return over equal weight, annualised, base costs",
        "% a year",
    )
    for k, s in roll.items():
        ax.plot(s.index, s.values * 100, color=SERIES[k][0], linewidth=2, label=SERIES[k][1])
    ax.legend(frameon=False, fontsize=8, labelcolor=MUTED)
    fig.tight_layout()
    fig.savefig(out / "rolling_excess.png", facecolor=SURFACE)
    plt.close(fig)

    fig, ax = chart_axes(
        "Primary: costs per year by component, base (% of average equity)",
        "% of equity",
    )
    colors = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4"]
    bottom = np.zeros(len(costs_year))
    for (k, s), col in zip(costs_year.items(), colors, strict=False):
        ax.bar(
            [str(y) for y in costs_year.index],
            s.values * 100,
            bottom=bottom,
            color=col,
            edgecolor=SURFACE,
            linewidth=1,
            label=k,
            width=0.6,
        )
        bottom += s.values * 100
    ax.tick_params(axis="x", rotation=45)
    ax.set_ylim(0, bottom.max() * 1.25)  # room for the legend above the bars
    ax.legend(frameon=False, fontsize=8, labelcolor=MUTED, ncol=5, loc="upper left")
    fig.tight_layout()
    fig.savefig(out / "cost_breakdown.png", facecolor=SURFACE)
    plt.close(fig)


def write_backtest_report(cfg: dict):
    """Write the Phase 3 backtest report and tables."""
    from momentum.transform.backtest import (
        STRATEGIES,
        deflated_sharpe,
        drawdown,
        index_returns,
        ols_nw,
    )
    from momentum.transform.diagnostics import nw_t

    out = Path(cfg["paths"]["results"]) / "phase3"
    lags = cfg["diagnostics"]["newey_west_lags"]
    st = pd.read_csv(out / "summary_stats.csv")
    be = pd.read_csv(out / "breakeven_runs.csv")

    def load(s, sc, f):
        return pd.read_csv(
            out / f"{s}_{sc}" / f, index_col=0, parse_dates=f.startswith("equity") or None
        )

    rets = {
        (s, sc): load(s, sc, "returns_monthly.csv")["return"]
        for s in STRATEGIES
        for sc in cfg["backtest"]["scenarios"]
    }
    eqd = {
        (s, sc): pd.read_csv(
            out / f"{s}_{sc}" / "equity_daily.csv",
            parse_dates=["date"],
            index_col="date",
        )["equity"]
        for s in STRATEGIES
        for sc in cfg["backtest"]["scenarios"]
    }
    idx = {n: index_returns(cfg, n) for n in cfg["prices"]["indices"]}
    rf = (1 + cfg["backtest"]["risk_free"]) ** (1 / 12) - 1
    start, end = eqd[("primary", "base")].index[0], eqd[("primary", "base")].index[-1]

    def pct(x):
        return f"{x * 100:.2f}%"

    # indices on the same dates, without costs
    idx_rows, idx_eq = [], {}
    for n, (r, tri) in idx.items():
        s = tri[(tri.index >= start) & (tri.index <= end)]
        e = s / s.iloc[0] * cfg["backtest"]["capital"]
        idx_eq[n] = e
        yrs = (s.index[-1] - s.index[0]).days / 365.25
        dd, info = drawdown(pd.DataFrame({"equity": e}))
        x = r - rf
        idx_rows.append(
            dict(
                strategy=f"{n} TRI (index)",
                scenario="no costs",
                cagr=(s.iloc[-1] / s.iloc[0]) ** (1 / yrs) - 1,
                vol=r.std() * np.sqrt(12),
                sharpe=x.mean() / x.std() * np.sqrt(12),
                max_drawdown=info["max_drawdown"],
                peak=info["peak"],
                trough=info["trough"],
                worst_month=r.min(),
            )
        )
    main_cols = [
        "strategy",
        "scenario",
        "cagr",
        "vol",
        "sharpe",
        "sortino",
        "max_drawdown",
        "peak",
        "trough",
        "calmar",
        "worst_month",
        "worst_month_date",
        "turnover",
        "avg_holdings",
        "mean_largest_sector_weight",
        "max_sector_weight",
        "cost_total_pct_yr",
        "end_equity",
    ]
    summary = pd.concat([st[main_cols], pd.DataFrame(idx_rows)], ignore_index=True)
    summary.to_csv(out / "table_summary.csv", index=False)

    # against equal weight, alpha and beta
    vs = []
    n500 = idx[cfg["prices"]["indices"][0]][0]
    for s in ["primary", "quarterly"]:
        for sc in cfg["backtest"]["scenarios"]:
            r, e = rets[(s, sc)], rets[("equal_weight", sc)]
            d = r - e
            b_ew, t_ew = ols_nw(r.values, e.values, lags)
            b_ix, t_ix = ols_nw(r.values, n500.reindex(r.index).values, lags)
            vs.append(
                dict(
                    strategy=s,
                    scenario=sc,
                    diff_mean=d.mean(),
                    diff_nw_t=nw_t(d, lags),
                    share_positive=(d > 0).mean(),
                    alpha_ew_annual=b_ew[0] * 12,
                    alpha_ew_t=t_ew[0],
                    beta_ew=b_ew[1],
                    beta_ew_t=t_ew[1],
                    alpha_n500_annual=b_ix[0] * 12,
                    alpha_n500_t=t_ix[0],
                    beta_n500=b_ix[1],
                    beta_n500_t=t_ix[1],
                )
            )
    vs = pd.DataFrame(vs)
    vs.to_csv(out / "table_vs_equal_weight.csv", index=False)

    # break-even slippage multiple: where the mean monthly excess over equal weight reaches zero
    def crossing(col):
        x, y = be["multiple"].values, be[col].values
        for i in range(1, len(x)):
            if y[i - 1] > 0 >= y[i]:
                return x[i - 1] + (x[i] - x[i - 1]) * y[i - 1] / (y[i - 1] - y[i])
        if y[-1] > 0 and y[-1] < y[-2]:
            return x[-1] + y[-1] * (x[-1] - x[-2]) / (
                y[-2] - y[-1]
            )  # linear extrapolation beyond the last run
        return np.nan

    be_primary, be_quarterly = (
        crossing("primary_minus_ew"),
        crossing("quarterly_minus_ew"),
    )

    # calendar years (daily equity / index at year ends), worst months
    cal = {}
    for s in STRATEGIES:
        e = eqd[(s, "base")]
        cal[s] = (
            e.groupby(e.index.year).last()
            / pd.concat([e.iloc[:1], e.groupby(e.index.year).last()]).shift(1).dropna().values
            - 1
        )
    for n, e in idx_eq.items():
        cal[f"{n} TRI"] = (
            e.groupby(e.index.year).last()
            / pd.concat([e.iloc[:1], e.groupby(e.index.year).last()]).shift(1).dropna().values
            - 1
        )
    cal = pd.DataFrame(cal)
    cal.index.name = "year"
    cal.to_csv(out / "table_calendar_years.csv")
    worst = rets[("primary", "base")].nsmallest(10).rename("primary").to_frame()
    worst["equal_weight"] = rets[("equal_weight", "base")].reindex(worst.index)
    worst["NIFTY 500 TRI"] = n500.reindex(worst.index)
    worst.to_csv(out / "table_worst_months.csv")

    # deflated Sharpe (2 trials, base costs)
    trials = {
        "primary": rets[("primary", "base")],
        "quarterly": rets[("quarterly", "base")],
    }
    dsr = pd.DataFrame([deflated_sharpe(trials, rf, k) for k in trials])
    dsr.to_csv(out / "table_deflated_sharpe.csv", index=False)

    # profit concentration (primary, base): share of total P&L (gross of costs) from the top stocks
    pnl = pd.read_csv(out / "primary_base" / "pnl_by_stock.csv").sort_values("pnl", ascending=False)
    names = pd.read_csv(Path(cfg["paths"]["processed_prices"]) / "securities.csv").set_index(
        "file_id"
    )["stock_id"]
    total = pnl["pnl"].sum()
    conc = pd.DataFrame(
        [
            dict(
                top=k,
                share_of_total_pnl=pnl["pnl"].head(k).sum() / total,
                stocks=", ".join(names.get(f, f) for f in pnl["file_id"].head(min(k, 5))),
            )
            for k in [1, 5, 10]
        ]
    )
    conc.to_csv(out / "table_concentration.csv", index=False)

    # costs and sectors (base)
    cost_cols = [c for c in st.columns if c.startswith("cost_")]
    costs = st[st["scenario"] == "base"][["strategy"] + cost_cols]
    costs.to_csv(out / "table_costs.csv", index=False)
    hold = pd.read_csv(out / "primary_base" / "holdings.csv", parse_dates=["execution_date"])
    sw = hold.groupby(["execution_date", "sector"])["weight"].sum().unstack(fill_value=0)
    sectors = sw.mean().sort_values(ascending=False).rename("average_weight").to_frame()
    sectors["max_weight"] = sw.max()
    sectors.to_csv(out / "table_sector_weights.csv")
    largest = sw.max(axis=1)

    # charts
    tr = pd.read_csv(out / "primary_base" / "trades.csv", parse_dates=["date"])
    avg_eq = eqd[("primary", "base")].groupby(eqd[("primary", "base")].index.year).mean()
    by_year = tr.groupby(tr["date"].dt.year)[
        ["slippage", "stt", "stamp", "dp", "exchange", "sebi", "gst"]
    ].sum()
    costs_year = pd.DataFrame(
        {
            "slippage": by_year["slippage"],
            "STT": by_year["stt"],
            "stamp duty": by_year["stamp"],
            "DP charge": by_year["dp"],
            "exchange + SEBI + GST": by_year[["exchange", "sebi", "gst"]].sum(axis=1),
        }
    )
    costs_year = costs_year.div(avg_eq.reindex(costs_year.index), axis=0)
    eqs = {s: eqd[(s, "base")] for s in STRATEGIES} | {n: e for n, e in idx_eq.items()}
    dds = {s: drawdown(pd.DataFrame({"equity": eqd[(s, "base")]}))[0] for s in STRATEGIES}
    roll = {
        s: (rets[(s, "base")] - rets[("equal_weight", "base")]).rolling(36).mean().dropna() * 12
        for s in ["primary", "quarterly"]
    }
    roll = {
        k: v.set_axis(pd.PeriodIndex(v.index, freq="M").to_timestamp()) for k, v in roll.items()
    }
    backtest_charts(out, eqs, dds, roll, costs_year)

    # reading
    def g(s, sc):
        return summary[(summary["strategy"] == s) & (summary["scenario"] == sc)].iloc[0]

    def v(s, sc):
        return vs[(vs["strategy"] == s) & (vs["scenario"] == sc)].iloc[0]

    P, Q, E = g("primary", "base"), g("quarterly", "base"), g("equal_weight", "base")
    vp, vq = v("primary", "base"), v("quarterly", "base")

    def sig(t):
        return (
            "statistically significant at the 5% level"
            if abs(t) >= 1.96
            else "not statistically significant at the 5% level"
        )

    beats = "beats" if vp["diff_mean"] > 0 else "does not beat"
    text = [
        "# Backtest report\n",
        "**Hypothetical backtest, development period only (Jan 2011 to Oct 2024); holdout locked. "
        "Not investment advice.**\n",
        f"Simulated from {start:%Y-%m-%d} to {end:%Y-%m-%d} with Rs "
        f"{cfg['backtest']['capital']:,.0f}. Monthly returns run "
        "between execution closes. Costs are assumptions marked VERIFY in the config. Sharpe uses "
        "a "
        f"{cfg['backtest']['risk_free']:.1%} risk-free rate (VERIFY).\n",
        "## Reading\n",
        f"- **Primary vs equal weight, after base costs.** The primary {beats} the equal-weight "
        f"benchmark: CAGR {pct(P['cagr'])} "
        f"vs {pct(E['cagr'])}, Sharpe {P['sharpe']:.2f} vs {E['sharpe']:.2f}. The mean monthly "
        "difference is "
        f"{pct(vp['diff_mean'])} (Newey-West t = {vp['diff_nw_t']:.2f}, {sig(vp['diff_nw_t'])}), "
        "positive in "
        f"{vp['share_positive']:.0%} of months. Alpha on equal weight is "
        f"{pct(vp['alpha_ew_annual'])} a year (t = "
        f"{vp['alpha_ew_t']:.2f}, beta {vp['beta_ew']:.2f}); alpha on NIFTY 500 TRI is "
        f"{pct(vp['alpha_n500_annual'])} a year "
        f"(t = {vp['alpha_n500_t']:.2f}, beta {vp['beta_n500']:.2f}).",
        f"- **Risk.** Maximum drawdown {pct(P['max_drawdown'])} ({P['peak']} to {P['trough']}) "
        f"against {pct(E['max_drawdown'])} "
        f"for equal weight; worst month {pct(P['worst_month'])} ({P['worst_month_date']}).",
        f"- **Costs.** One-way turnover {P['turnover']:.1f}x a year; costs "
        f"{pct(P['cost_total_pct_yr'])} of equity a year at base "
        f"({pct(g('primary', 'high')['cost_total_pct_yr'])} at high). Break-even: the primary's "
        "excess over equal weight "
        + (
            f"reaches zero at about {be_primary:.1f}x the base slippage."
            if not np.isnan(be_primary)
            else "does not reach zero within the multiples tested."
        )
        + " The equal-weight benchmark pays the same multiple.",
        f"- **Quarterly.** CAGR {pct(Q['cagr'])}, Sharpe {Q['sharpe']:.2f}, turnover "
        f"{Q['turnover']:.1f}x, costs "
        f"{pct(Q['cost_total_pct_yr'])} a year; difference vs equal weight {pct(vq['diff_mean'])} "
        f"a month (t = {vq['diff_nw_t']:.2f}). "
        f"It {'keeps more' if vq['diff_mean'] > vp['diff_mean'] else 'keeps less'} of the excess "
        "than the monthly version after costs.",
        "- **Overfitting check.** Deflated Sharpe ratio (2 trials): primary "
        f"{dsr.iloc[0]['deflated_sharpe']:.2f}, quarterly "
        f"{dsr.iloc[1]['deflated_sharpe']:.2f} (probability that the true Sharpe exceeds the best "
        "of 2 trials under the null).",
        f"- **Concentration.** The top stock gives {conc.iloc[0]['share_of_total_pnl']:.0%} of the "
        "primary's total P&L, the top 5 "
        f"{conc.iloc[1]['share_of_total_pnl']:.0%}, the top 10 "
        f"{conc.iloc[2]['share_of_total_pnl']:.0%}. Largest sector weight at a "
        f"rebalance: mean {largest.mean():.0%}, maximum {largest.max():.0%}.\n",
        "## Summary (all scenarios; indices without costs)\n",
        table(summary.round(4)),
        "\n## Against equal weight (same cost scenario)\n",
        table(vs.round(4)),
        "\n## Break-even slippage multiple\n",
        f"Primary: {be_primary:.2f}x; quarterly: {be_quarterly:.2f}x base slippage (statutory "
        "charges on; linear between runs).\n",
        table(be.round(5)),
        "\n## Calendar-year returns (base costs; 2011 from February, 2024 to 2 December)\n",
        table(cal.round(4).reset_index()),
        "\n## The 10 worst months of the primary\n",
        table(worst.round(4).reset_index().rename(columns={"index": "signal month"})),
        "\n## Deflated Sharpe ratio (inputs)\n",
        table(dsr.round(4)),
        "\n## Profit concentration (primary, base; P&L gross of costs)\n",
        table(conc.round(4)),
        "\n## Costs per year, % of average equity (base)\n",
        table(costs.round(5)),
        "\n## Sector weights (primary, base)\n",
        table(sectors.round(4).reset_index()),
        "\n## Whole shares vs fractional (base)\n",
        table(
            st[
                st["scenario"].isin(["base", "base_whole_shares"])
                & st["strategy"].isin(["primary", "quarterly"])
            ][
                [
                    "strategy",
                    "scenario",
                    "cagr",
                    "sharpe",
                    "max_drawdown",
                    "turnover",
                    "end_equity",
                ]
            ].round(4)
        ),
        "\n## Charts\n",
        "![equity](equity_curves.png)\n",
        "![drawdowns](drawdowns.png)\n",
        "![rolling](rolling_excess.png)\n",
        "![costs](cost_breakdown.png)\n",
    ]
    (out / "backtest_report.md").write_text("\n".join(text))
    logger.info(f"saved {out / 'backtest_report.md'}")


def dsr_against(trial_returns, series, rf_m: float):
    """Deflated Sharpe of a series against a set of trial returns."""
    # deflated Sharpe of `series` against the spread of Sharpe ratios across the trials
    import math
    from statistics import NormalDist

    srs = [(r - rf_m).mean() / (r - rf_m).std() for r in trial_returns]
    n, var = len(srs), np.var(srs, ddof=1)
    g, z = 0.5772156649, NormalDist().inv_cdf
    sr0 = math.sqrt(var) * ((1 - g) * z(1 - 1 / n) + g * z(1 - 1 / (n * math.e)))
    x = series - rf_m
    s = x.mean() / x.std()
    skew = ((x - x.mean()) ** 3).mean() / x.std(ddof=0) ** 3
    kurt = ((x - x.mean()) ** 4).mean() / x.std(ddof=0) ** 4
    dsr = NormalDist().cdf(
        (s - sr0) * math.sqrt(len(x) - 1) / math.sqrt(1 - skew * s + (kurt - 1) / 4 * s**2)
    )
    return dict(
        trials=n,
        sharpe_monthly=s,
        sharpe_annual=s * math.sqrt(12),
        var_trial_sharpes=var,
        expected_max_sharpe_null=sr0,
        skew=skew,
        kurtosis=kurt,
        months=len(x),
        deflated_sharpe=dsr,
    )


def write_walkforward_report(cfg: dict, folds_df, stitched, full_tab, full, entry):
    """Write the Phase 4 walk-forward report and tables."""
    from momentum.transform.walkforward import summarise_oos

    out = Path(cfg["paths"]["results"]) / "phase4"
    rf_m = (1 + cfg["backtest"]["risk_free"]) ** (1 / 12) - 1
    sel_ic = pd.read_csv(out / "selection_ic.csv", index_col=0).iloc[:, 0]
    summ = summarise_oos(cfg, stitched, sel_ic, entry)
    summ.to_csv(out / "walkforward_summary.csv", index=False)
    freq = (
        pd.concat(
            [
                folds_df["signal"].value_counts().rename("signal"),
                folds_df["n"].astype(str).value_counts().rename("holdings"),
                folds_df["rebalance"].value_counts().rename("rebalance"),
            ],
            axis=1,
        )
        .fillna(0)
        .astype(int)
    )
    freq.to_csv(out / "parameter_frequency.csv")
    trials = [v["returns"] for v in full.values()]
    dsr = pd.DataFrame(
        [
            dict(
                series="fixed primary, full development",
                **dsr_against(trials, full["score|N30|monthly"]["returns"], rf_m),
            ),
            dict(
                series="best grid combination, full development",
                **dsr_against(
                    trials,
                    full[full_tab.sort_values("sharpe").iloc[-1]["name"]]["returns"],
                    rf_m,
                ),
            ),
            dict(
                series="stitched selection, out of sample",
                **dsr_against(trials, stitched["selection"], rf_m),
            ),
        ]
    )
    dsr.to_csv(out / "deflated_sharpe_18.csv", index=False)
    degr = folds_df["oos_sharpe"] - folds_df["is_sharpe"]

    # chart: stitched out-of-sample growth of Rs 1
    import matplotlib.pyplot as plt

    fig, ax = chart_axes("Walk-forward test months stitched: growth of Rs 1 (base costs)", "Rs")
    cols = {
        "selection": ("#2a78d6", "Selection (walk-forward)"),
        "primary": ("#eb6834", "Fixed primary"),
        "quarterly": ("#1baf7a", "Quarterly"),
        "equal_weight": ("#eda100", "Equal weight"),
    }
    for k, (c, lab) in cols.items():
        g = (1 + stitched[k]).cumprod()
        ax.plot(
            pd.PeriodIndex(g.index, freq="M").to_timestamp(),
            g.values,
            color=c,
            linewidth=2,
            label=lab,
        )
    ax.axhline(1, color=MUTED, linewidth=0.8)
    ax.legend(frameon=False, fontsize=8, labelcolor=MUTED)
    fig.tight_layout()
    fig.savefig(out / "walkforward_oos.png", facecolor=SURFACE)
    plt.close(fig)

    s = summ.set_index("strategy")

    def pct(x):
        return f"{x * 100:.2f}%"

    sel, prim = s.loc["selection"], s.loc["primary"]
    text = [
        "# Walk-forward\n",
        "**Hypothetical backtest; development period only; holdout locked. Not investment "
        "advice.**\n",
        f"{len(folds_df)} folds, test months {folds_df['test_first'].iloc[0]} to "
        f"{folds_df['test_last'].iloc[-1]} "
        f"({int(sel['months'])} months). Each test window starts in cash (mean cost of entering: "
        f"{pct(sel['entry_cost_pct'])} of capital for the selection, "
        f"{pct(s.loc['equal_weight', 'entry_cost_pct'])} for equal weight). "
        "Base costs. 18 trials.\n",
        "## Reading\n",
        f"- The stitched out-of-sample selection earns {pct(sel['cagr'])} a year (Sharpe "
        f"{sel['sharpe']:.2f}) against "
        f"{pct(s.loc['equal_weight', 'cagr'])} for equal weight; mean monthly difference "
        f"{pct(sel['diff_vs_ew'])} "
        f"(Newey-West t = {sel['diff_nw_t']:.2f}). The fixed primary with no selection: "
        f"{pct(prim['cagr'])}, Sharpe {prim['sharpe']:.2f}, "
        f"difference {pct(prim['diff_vs_ew'])} (t = {prim['diff_nw_t']:.2f}). "
        "Selection "
        f"{'adds to' if sel['diff_vs_ew'] > prim['diff_vs_ew'] else 'does not improve on'} the "
        "fixed rule out of sample.",
        f"- In-sample to out-of-sample Sharpe changes by {degr.mean():+.2f} on average across "
        "folds "
        f"(in-sample mean {folds_df['is_sharpe'].mean():.2f}, out-of-sample mean "
        f"{folds_df['oos_sharpe'].mean():.2f}).",
        f"- Mean IC of the chosen signal on test months: {sel['mean_ic']:.3f} (t = "
        f"{sel['ic_nw_t']:.2f}).",
        f"- Deflated Sharpe at 18 trials: fixed primary {dsr.iloc[0]['deflated_sharpe']:.2f}, best "
        "grid combination "
        f"{dsr.iloc[1]['deflated_sharpe']:.2f}, stitched selection "
        f"{dsr.iloc[2]['deflated_sharpe']:.2f}.\n",
        "## Folds\n",
        table(folds_df.round(3)),
        "\n## Stitched test months\n",
        table(summ.round(4)),
        "\n## How often each parameter was chosen\n",
        table(freq.reset_index().rename(columns={"index": "value"})),
        "\n## Grid on the full development period\n",
        table(full_tab.sort_values("sharpe", ascending=False).round(4)),
        "\n## Deflated Sharpe (18 trials; inputs)\n",
        table(dsr.round(4)),
        "\n![walk-forward](walkforward_oos.png)\n",
    ]
    (out / "walkforward_report.md").write_text("\n".join(text))
    logger.info(f"saved {out / 'walkforward_report.md'}")


def write_frozen_config(cfg: dict, full_tab) -> dict:
    """Freeze the holdout configuration; an existing frozen file is never overwritten."""
    import hashlib
    import json

    from momentum.extract.prices import trading_days
    from momentum.transform.walkforward import frozen_choice

    out = Path(cfg["paths"]["results"]) / "phase4"
    g, best = frozen_choice(cfg, full_tab)
    if (out / "frozen_config.json").exists():  # committed before the holdout run: never overwritten
        old = json.loads((out / "frozen_config.json").read_text())
        logger.info(
            f"frozen config kept ({old['params']['name']}); this run's choice {g['name']} "
            f"{'matches' if old['params']['name'] == g['name'] else 'DIFFERS'}"
        )
        return old
    frozen = dict(
        params=g,
        rule=(
            "highest net Sharpe on the full development period (base costs); tie-break mean IC, "
            "then turnover"
        ),
        full_development_sharpe=float(best["sharpe"]),
        mean_ic=float(best["ic"]),
        turnover=float(best["turnover"]),
        config_sha256=hashlib.sha256(Path("configs/config.yaml").read_bytes()).hexdigest(),
        data_end_date=str(trading_days(cfg).max().date()),
        written=str(pd.Timestamp.today().date()),
    )
    (out / "frozen_config.json").write_text(json.dumps(frozen, indent=2))
    logger.info(f"frozen config: {g['name']} (Sharpe {best['sharpe']:.2f})")
    return frozen


def write_holdout_report(cfg: dict, run_no, months, rets, ic, frozen):
    """Write the holdout report for one logged run."""
    from momentum.transform.diagnostics import nw_t

    out = Path(cfg["paths"]["results"]) / "phase4"
    lags = cfg["diagnostics"]["newey_west_lags"]
    rf_m = (1 + cfg["backtest"]["risk_free"]) ** (1 / 12) - 1
    ew = rets["equal weight"]
    rows = []
    for k, r in rets.items():
        eq = (1 + r).cumprod()
        x = r - rf_m
        row = dict(
            strategy=k,
            months=len(r),
            cagr=eq.iloc[-1] ** (12 / len(r)) - 1,
            sharpe=x.mean() / x.std() * np.sqrt(12),
            max_drawdown_monthly=(eq / eq.cummax() - 1).min(),
        )
        if k != "equal weight":
            d = r - ew
            row.update(
                diff_vs_ew=d.mean(),
                diff_nw_t=nw_t(d, lags),
                diff_share_positive=(d > 0).mean(),
                detectable_diff_t2=2 * d.std() / np.sqrt(len(d)),
            )
        rows.append(row)
    tab = pd.DataFrame(rows)
    tab.loc[tab["strategy"] == "frozen selection", "mean_ic"] = ic.mean()
    tab.loc[tab["strategy"] == "frozen selection", "ic_nw_t"] = nw_t(ic, lags)
    tab.to_csv(out / f"holdout_summary_run{run_no}.csv", index=False)
    import matplotlib.pyplot as plt

    fig, ax = chart_axes(
        f"HOLDOUT RUN {run_no}: growth of Rs 1, {months[0]} to {months[1]} (base costs; indices "
        "without costs)",
        "Rs",
    )
    colors = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300"]
    for (k, r), c in zip(rets.items(), colors, strict=False):
        g = (1 + r).cumprod()
        ax.plot(
            pd.PeriodIndex(g.index, freq="M").to_timestamp(),
            g.values,
            color=c,
            linewidth=2,
            label=k,
        )
    ax.axhline(1, color=MUTED, linewidth=0.8)
    ax.legend(frameon=False, fontsize=8, labelcolor=MUTED)
    fig.tight_layout()
    fig.savefig(out / f"holdout_run{run_no}.png", facecolor=SURFACE)
    plt.close(fig)
    s = tab.set_index("strategy")
    f = s.loc["frozen selection"]

    def pct(x):
        return f"{x * 100:.2f}%"

    banner = f"# HOLDOUT RUN {run_no}" + (
        "" if run_no == 1 else " (NOT THE FIRST RUN: earlier runs exist, see holdout_runs.log)"
    )
    text = [
        banner + "\n",
        "**Hypothetical backtest. Not investment advice.**\n",
        f"Signal months {months[0]} to {months[1]} ({int(f['months'])} months scored), each "
        "strategy starting in cash, base costs. "
        f"Frozen selection: {frozen['params']['name']} (chosen on the full development period, "
        "committed before this run).\n",
        "## Reading\n",
        f"- Frozen selection: {pct(f['cagr'])} a year, Sharpe {f['sharpe']:.2f}; equal weight "
        f"{pct(s.loc['equal weight', 'cagr'])}. "
        f"Mean monthly difference vs equal weight {pct(f['diff_vs_ew'])} (Newey-West t = "
        f"{f['diff_nw_t']:.2f}), positive in "
        f"{f['diff_share_positive']:.0%} of months.",
        f"- Low power: with {int(f['months'])} months, a mean monthly difference needs to be about "
        f"{pct(f['detectable_diff_t2'])} "
        "to reach t = 2. A result below that is consistent with both no edge and the "
        "development-period edge.",
        f"- Mean IC of the frozen signal: {f['mean_ic']:.3f} (t = {f['ic_nw_t']:.2f}).\n",
        table(tab.round(4)),
        f"\n![holdout](holdout_run{run_no}.png)\n",
    ]
    (out / f"holdout_report_run{run_no}.md").write_text("\n".join(text))
    logger.info(f"saved {out / f'holdout_report_run{run_no}.md'}")


def write_institutional_report(cfg: dict, res: dict):
    """Write the Phase 5 report: Fama-MacBeth, neutral variants, capacity, spanning."""
    import matplotlib.pyplot as plt

    out = Path(cfg["paths"]["results"]) / "phase5"

    def pct(x):
        return f"{x * 100:.2f}%"

    fm = res["fm"]
    dev = fm[fm["sample"] == "development"].set_index(["model", "variable"])
    a, e = dev.loc[("A", "score")], dev.loc[("E", "score")]
    sp = res["spanning"].set_index("series")
    pr, q = sp.loc["primary minus RF"], sp.loc["Q5 minus Q1"]
    res.setdefault("corr_q51_wml", q.get("corr_with_wml", np.nan))
    shrink_fm = 1 - e["mean_slope"] / a["mean_slope"]
    shrink_span = 1 - pr["alpha_annual"] / pr["capm_alpha_annual"]
    big = (
        shrink_fm > 0.5
        or shrink_span > 0.5
        or (abs(a["nw_t"]) >= 1.96 and abs(e["nw_t"]) < 1.96)
        or (abs(pr["capm_alpha_t"]) >= 1.96 and abs(pr["alpha_t"]) < 1.96)
    )
    neu, cap, stt = res["neutral"].set_index("strategy"), res["capacity"], res["states"]
    ex = res["exposures"]["value"]

    # charts
    fig, ax = chart_axes(
        "Fama-MacBeth slope on the momentum score, models A to E (development, 95% interval)",
        "mean monthly slope",
    )
    s = dev.xs("score", level="variable")
    se = s["mean_slope"] / s["nw_t"]
    ax.errorbar(
        list(s.index),
        s["mean_slope"] * 100,
        yerr=1.96 * se * 100,
        fmt="o",
        color="#2a78d6",
        capsize=4,
        elinewidth=1.5,
        markersize=6,
    )
    ax.set_ylabel("% per month per 1 sd of score", color=MUTED, fontsize=8)
    fig.tight_layout()
    fig.savefig(out / "fm_slopes.png", facecolor=SURFACE)
    plt.close(fig)
    fig, ax = chart_axes(
        "Capacity: primary CAGR by starting capital (trades capped at 5% of median traded value)",
        "CAGR %",
    )
    ax.plot(
        cap["capital"],
        cap["cagr"] * 100,
        "o-",
        color="#2a78d6",
        linewidth=2,
        markersize=6,
    )
    ax.set_xscale("log")
    ax.set_xticks(
        cap["capital"],
        [f"Rs {c / 1e7:g} cr" if c >= 1e7 else f"Rs {c / 1e5:g} lakh" for c in cap["capital"]],
    )
    fig.tight_layout()
    fig.savefig(out / "capacity.png", facecolor=SURFACE)
    plt.close(fig)
    ep = res["episode_2020"]
    fig, ax = chart_axes("2019-12 to 2020-12: monthly returns by signal month", "% per month")
    x = np.arange(len(ep))
    for j, (k, c) in enumerate(
        [
            ("primary", "#2a78d6"),
            ("equal_weight", "#eb6834"),
            ("NIFTY 500 TRI", "#1baf7a"),
        ]
    ):
        ax.bar(
            x + (j - 1) * 0.27,
            ep[k] * 100,
            width=0.25,
            color=c,
            label=k.replace("_", " "),
        )
    ax.set_xticks(x, ep.index, rotation=45)
    ax.legend(frameon=False, fontsize=8, labelcolor=MUTED)
    fig.tight_layout()
    fig.savefig(out / "episode_2020.png", facecolor=SURFACE)
    plt.close(fig)

    lead = (
        "**The edge shrinks substantially under controls or spanning.**"
        if big
        else "**The edge does not shrink substantially under the controls or the spanning test.**"
    )
    text = [
        "# Institutional tests\n",
        "**Hypothetical backtest; development period only; holdout not used. Not investment "
        "advice.**\n",
        lead + f" The momentum slope goes from {pct(a['mean_slope'])} a month "
        f"(t = {a['nw_t']:.2f}, model A) to {pct(e['mean_slope'])} "
        f"(t = {e['nw_t']:.2f}) with all controls (model E), a change of {-shrink_fm:+.0%}. The "
        "primary's alpha over the risk-free rate goes "
        f"from {pct(pr['capm_alpha_annual'])} a year (t = {pr['capm_alpha_t']:.2f}) against IIMA's "
        "market factor alone to "
        f"{pct(pr['alpha_annual'])} (t = {pr['alpha_t']:.2f}) against market, SMB, HML and WML "
        f"({-shrink_span:+.0%}).\n",
        "## Reading\n",
        "- **Fama-MacBeth.** Adding size (B), beta and volatility (C), sector dummies (D) and last "
        "month's return (E) leaves the score slope at "
        + ", ".join(
            f"{mm} {pct(dev.loc[(mm, 'score'), 'mean_slope'])} (t = "
            f"{dev.loc[(mm, 'score'), 'nw_t']:.2f})"
            for mm in "ABCDE"
        )
        + ".",
        f"- **Neutral variants.** Sector-neutral: CAGR {pct(neu.loc['sector-neutral', 'cagr'])}, "
        "difference vs equal weight "
        f"{pct(neu.loc['sector-neutral', 'diff_vs_ew'])} a month (t = "
        f"{neu.loc['sector-neutral', 'diff_nw_t']:.2f}); size-neutral: "
        f"{pct(neu.loc['size-neutral', 'cagr'])}, {pct(neu.loc['size-neutral', 'diff_vs_ew'])} (t "
        f"= {neu.loc['size-neutral', 'diff_nw_t']:.2f}); "
        f"primary {pct(neu.loc['primary', 'cagr'])}, {pct(neu.loc['primary', 'diff_vs_ew'])} (t = "
        f"{neu.loc['primary', 'diff_nw_t']:.2f}). "
        "On walk-forward test months: sector-neutral "
        f"{pct(neu.loc['sector-neutral', 'wf_diff_vs_ew'])} (t = "
        f"{neu.loc['sector-neutral', 'wf_diff_nw_t']:.2f}), "
        f"size-neutral {pct(neu.loc['size-neutral', 'wf_diff_vs_ew'])} (t = "
        f"{neu.loc['size-neutral', 'wf_diff_nw_t']:.2f}).",
        f"- **Exposures.** Holdings sit at the {ex['holdings_tv_percentile']:.0%} traded-value "
        f"percentile (universe {ex['universe_tv_percentile']:.0%}); "
        f"beta {ex['holdings_beta']:.2f} vs {ex['universe_beta']:.2f}; volatility "
        f"{pct(ex['holdings_vol'])} vs {pct(ex['universe_vol'])}.",
        "- **Capacity.** "
        + "; ".join(
            f"Rs {r['capital'] / 1e7:g} crore: CAGR {pct(r['cagr'])}, excess vs equal weight "
            f"{pct(r['excess_vs_ew'])} a month "
            f"(t = {r['excess_nw_t']:.2f}), {r['share_trades_capped']:.0%} of trades capped"
            for _, r in cap.iterrows()
        )
        + ".",
        f"- **States.** After a rising market: {pct(stt.iloc[0]['mean_diff'])} a month over equal "
        f"weight (t = {stt.iloc[0]['nw_t']:.2f}, "
        f"{int(stt.iloc[0]['months'])} months); after a falling market: "
        f"{pct(stt.iloc[1]['mean_diff'])} (t = {stt.iloc[1]['nw_t']:.2f}, "
        f"{int(stt.iloc[1]['months'])} months). Worst month in the 2020 episode: "
        f"{ep['primary_minus_ew'].idxmin()} "
        f"({pct(ep['primary_minus_ew'].min())} vs equal weight).",
        f"- **Spanning (IIMA factors, {int(pr['months'])} overlapping months, {pr['first']} to "
        f"{pr['last']}).** Primary: four-factor alpha "
        f"{pct(pr['alpha_annual'])} a year (t = {pr['alpha_t']:.2f}), WML loading "
        f"{pr['b_WML']:.2f} (t = {pr['t_WML']:.2f}). Q5 minus Q1: alpha "
        f"{pct(q['alpha_annual'])} a year (t = {q['alpha_t']:.2f}), WML loading {q['b_WML']:.2f} "
        f"(t = {q['t_WML']:.2f}); correlation with WML "
        f"{res['corr_q51_wml']:.2f}. IIMA's MF is taken as the market factor (market minus "
        "risk-free); VERIFY against the library's notes.\n",
        "## Fama-MacBeth\n",
        table(res["fm"].round(4)),
        "\n### Model D score slope by year\n",
        table(res["fm_by_year"].round(4).reset_index().rename(columns={"date": "year"})),
        "\n## Neutral variants (base costs)\n",
        table(res["neutral"].round(4)),
        "\n## Exposures of the primary\n",
        table(res["exposures"].round(4).reset_index()),
        "\n### Sector over/underweights vs the eligible universe (top 5 each)\n",
        table(res["sector_tilts"].round(4).reset_index()),
        "\n## Capacity\n",
        table(cap.round(4)),
        "\n## Momentum states\n",
        table(stt.round(4)),
        "\n### 2020 episode\n",
        table(ep.round(4).reset_index()),
        "\n## Spanning\n",
        table(res["spanning"].round(4)),
        "\n![slopes](fm_slopes.png)\n",
        "![capacity](capacity.png)\n",
        "![2020](episode_2020.png)\n",
    ]
    (out / "institutional_report.md").write_text("\n".join(text))
    logger.info(f"saved {out / 'institutional_report.md'}")
