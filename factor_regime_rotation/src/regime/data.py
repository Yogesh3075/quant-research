from __future__ import annotations

import json
import logging
from datetime import date
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)


def load_index(raw: Path, key: str) -> tuple:
    """Daily TRI of one index from its downloaded JSON chunks, with duplicate counts."""
    files = sorted(raw.glob(f"{key}_*.json"))
    if not files:
        raise SystemExit(
            f"No downloaded files for {key} in {raw}. Run: python scripts/run.py download"
        )
    rows = [r for f in files for r in json.loads(f.read_text())]
    df = pd.DataFrame(
        {
            "date": pd.to_datetime([r["Date"] for r in rows], format="%d %b %Y"),
            "tri": pd.to_numeric(
                [str(r["TotalReturnsIndex"]).replace(",", "") for r in rows], errors="coerce"
            ),
        }
    )
    n_dup = int(df["date"].duplicated().sum())
    df = df.drop_duplicates()
    # same date with two different values: keep neither
    clash = df[df["date"].duplicated(keep=False)].sort_values("date")
    df = df[~df["date"].isin(clash["date"])]
    return df.set_index("date")["tri"].sort_index(), n_dup, clash


def month_ends(daily: pd.DataFrame, calendar_key: str) -> pd.DataFrame:
    """Last trading day of each month on the calendar index; drops a running month."""
    cal = daily[calendar_key].dropna().index
    last_day = pd.Series(cal, index=cal).groupby(cal.to_period("M")).max()
    # drop the running month if the calendar has not reached its last business day yet
    if last_day.iloc[-1] < last_day.iloc[-1] + pd.offsets.BMonthEnd(0):
        last_day = last_day.iloc[:-1]
    # last available value of each index within each calendar month
    on_cal = daily.loc[daily.index.isin(cal) & (daily.index <= last_day.iloc[-1])]
    monthly = on_cal.groupby(on_cal.index.to_period("M")).last()
    monthly = monthly.loc[last_day.index]
    monthly.index = pd.DatetimeIndex(last_day.values, name="date")
    return monthly


def build(cfg: dict) -> tuple:
    """Build data/processed: daily and month-end TRI and monthly returns."""
    raw, out = Path(cfg["paths"]["raw"]), Path(cfg["paths"]["processed"])
    out.mkdir(parents=True, exist_ok=True)
    series, dups, clashes = {}, {}, {}
    for key in cfg["indices"]:
        series[key], dups[key], clashes[key] = load_index(raw, key)
    daily = pd.DataFrame(series)
    daily.index.name = "date"
    monthly = month_ends(daily, cfg["calendar"])
    returns = monthly.pct_change(fill_method=None).iloc[1:]
    daily.to_csv(out / "tri_daily.csv")
    monthly.to_csv(out / "tri_monthly.csv")
    returns.to_csv(out / "returns_monthly.csv")
    logger.info(
        f"Wrote {out}/tri_daily.csv {daily.shape}, tri_monthly.csv {monthly.shape}, "
        f"returns_monthly.csv {returns.shape}"
    )
    return daily, monthly, returns, dups, clashes


def md_table(df: pd.DataFrame, fmt: str = "{:.2f}") -> str:
    """A frame as a Markdown table."""
    cols = [str(df.index.name or "")] + [str(c) for c in df.columns]
    lines = ["| " + " | ".join(cols) + " |", "|" + " --- |" * len(cols)]
    for i, row in df.iterrows():
        cells = [fmt.format(v) if isinstance(v, float) else str(v) for v in row]
        lines.append("| " + " | ".join([str(i)] + cells) + " |")
    return "\n".join(lines)


def longest_run(mask: pd.Series) -> int:
    """Length of the longest run of True values."""
    # longest run of consecutive True values
    runs = (~mask).cumsum()[mask]
    return int(runs.value_counts().max()) if len(runs) else 0


def trailing(s: pd.Series, end: pd.Timestamp, years: int) -> float:
    """Annualised trailing return in % over `years`, ending at `end`."""
    s = s.dropna()
    now = s.asof(end)
    then = s.asof(end - pd.DateOffset(years=years))
    return 100 * ((now / then) ** (1 / years) - 1)


def check(
    cfg: dict,
    daily: pd.DataFrame,
    monthly: pd.DataFrame,
    returns: pd.DataFrame,
    dups: dict,
    clashes: dict,
) -> None:
    """Data checks and results/data_check.md; fails loudly on gaps, duplicates or clashes."""
    c, today = cfg["checks"], pd.Timestamp(date.today())
    cal = daily[cfg["calendar"]].dropna().index
    out = [
        "# Data check",
        "",
        f"Run on {today.date()}. Source: niftyindices.com, Total Returns Index (daily).",
        f"Calendar for missing days and month-ends: {cfg['calendar']} trading days.",
        "",
    ]

    # daily checks
    rows, moves, clash_lines = [], [], []
    for key in cfg["indices"]:
        s = daily[key].dropna()
        span = cal[(cal >= s.index[0]) & (cal <= s.index[-1])]
        missing = ~span.isin(s.index)
        ret = s.pct_change().dropna()
        big = ret[ret.abs() > c["big_move"]]
        moves += [f"| {key} | {d.date()} | {100 * v:.2f} |" for d, v in big.items()]
        clash_lines += [
            f"| {key} | {d.date()} | {v} |"
            for d, v in clashes[key].set_index("date")["tri"].items()
        ]
        rows.append(
            {
                "index": key,
                "first": s.index[0].date(),
                "last": s.index[-1].date(),
                "days": len(s),
                "missing vs cal": int(missing.sum()),
                "longest gap": longest_run(pd.Series(missing)),
                "extra vs cal": int((~s.index.isin(cal)).sum()),
                "duplicates": dups[key],
                "clashes": len(clashes[key]),
                "non-positive": int((s <= 0).sum()),
                f"moves >{100 * c['big_move']:.0f}%": len(big),
                "days stale": (today - s.index[-1]).days,
            }
        )
    out += [
        "## Daily series",
        "",
        md_table(pd.DataFrame(rows).set_index("index")),
        "",
        "Missing and longest gap (in calendar trading days) count only within each index's own "
        "first and last date. "
        "Extra: days the index has but the calendar does not. Duplicates: repeated dates in the "
        "raw responses "
        "(identical repeats are kept once). Clashes: one date with two different values (both "
        "dropped).",
        "",
    ]
    if clash_lines:
        out += (
            ["Clashing dates:", "", "| index | date | value |", "| --- | --- | --- |"]
            + clash_lines
            + [""]
        )
    out += (
        [
            f"## Daily moves larger than {100 * c['big_move']:.0f}%",
            "",
            "| index | date | return % |",
            "| --- | --- | --- |",
        ]
        + (moves or ["| none | | |"])
        + [""]
    )

    # monthly checks
    first_month = monthly.apply(lambda s: s.first_valid_index().date())
    gaps = monthly.apply(lambda s: int(s.loc[s.first_valid_index() :].isna().sum()))
    mrows = pd.DataFrame(
        {
            "months": monthly.notna().sum(),
            "first month-end": first_month,
            "empty months before start": monthly.isna().sum() - gaps,
            "empty months after start": gaps,
        }
    )
    mrows.index.name = "index"
    out += [
        "## Monthly series",
        "",
        f"{len(monthly)} month-ends from {monthly.index[0].date()} to {monthly.index[-1].date()} "
        "(last NIFTY 50 trading day of each month; an unfinished running month is left out).",
        "",
        md_table(mrows),
        "",
    ]
    corr = returns[cfg["factors"]].corr()
    corr.index.name = ""
    high = [
        f"{a}/{b} {corr.loc[a, b]:.2f}"
        for i, a in enumerate(corr.index)
        for b in corr.columns[i + 1 :]
        if corr.loc[a, b] > c["corr_flag"]
    ]
    out += [
        "Correlation of monthly returns, factor indices:",
        "",
        md_table(corr),
        "",
        f"Pairs above {c['corr_flag']}: " + (", ".join(high) if high else "none"),
        "",
    ]

    # sanity check against the NSE dashboard
    end = pd.Timestamp(cfg["sanity_date"])
    srows = []
    for key, nse in cfg["nse_dashboard"].items():
        ours = [trailing(daily[key], end, y) for y in (1, 3, 5)]
        diff = [o - n for o, n in zip(ours, nse, strict=True)]
        flag = "yes" if any(abs(d) > c["sanity_flag_pp"] for d in diff) else ""
        srows.append(
            {
                "index": key,
                "1y ours": ours[0],
                "1y NSE": nse[0],
                "3y ours": ours[1],
                "3y NSE": nse[1],
                "5y ours": ours[2],
                "5y NSE": nse[2],
                "max diff pp": round(max(diff, key=abs), 2) + 0.0,
                "flag": flag,
            }
        )
    out += [
        f"## Sanity check against NSE Index Dashboard (to {end.date()})",
        "",
        "Ours: from TRI at the last trading day on or before each date. 1y absolute, 3y and 5y "
        "CAGR, in %. "
        f"If the dashboard showed price returns, ours would be higher by about the dividend yield; "
        f"flag if any gap is above {c['sanity_flag_pp']} pp a year.",
        "",
        md_table(pd.DataFrame(srows).set_index("index")),
        "",
    ]

    # back-calculated history
    out += [
        "## Launch dates",
        "",
        "History before each index's launch date is back-calculated by NSE, not live.",
        "",
        "| index | launch date |",
        "| --- | --- |",
    ]
    out += [f"| {k} | {v} |" for k, v in cfg["launch_dates"].items()] + [""]

    path = Path(cfg["paths"]["results"]) / "data_check.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(out))
    logger.info("\n".join(out))
    logger.info(f"Saved {path}")


def load_dev(cfg: dict) -> tuple:
    """Month-end and daily TRI up to the end of development (the holdout is cut off)."""
    # processed series cut at the end of the development period; holdout month-ends are never loaded
    out = Path(cfg["paths"]["processed"])
    if not (out / "tri_monthly.csv").exists():
        raise SystemExit("No processed data. Run: python scripts/run.py check")
    monthly = pd.read_csv(out / "tri_monthly.csv", index_col=0, parse_dates=True)
    daily = pd.read_csv(out / "tri_daily.csv", index_col=0, parse_dates=True)
    dev_end = monthly.index[monthly.index < pd.Timestamp(cfg["holdout_start"])][-1]
    return monthly.loc[:dev_end], daily.loc[:dev_end]
