from __future__ import annotations

import io
import logging
from pathlib import Path

import pandas as pd

from momentum.extract.prices import parse_history

logger = logging.getLogger(__name__)


def read_constituent_file(path: Path) -> pd.DataFrame:
    """One archived constituent CSV as symbol, name, industry."""
    # older files start with a title line; the table starts at "Company Name"
    lines = Path(path).read_text(encoding="latin-1").splitlines()
    start = next(i for i, line in enumerate(lines) if line.lower().startswith("company name"))
    df = pd.read_csv(io.StringIO("\n".join(lines[start:])))
    df.columns = [c.strip() for c in df.columns]
    df = df.rename(
        columns={
            "Company Name": "company",
            "Industry": "industry",
            "Symbol": "symbol",
            "ISIN Code": "isin",
        }
    )
    for c in ["company", "industry", "symbol", "isin"]:
        df[c] = df[c].astype(str).str.strip()
    return df[["company", "industry", "symbol", "isin"]]


def read_snapshots(cfg: dict) -> pd.DataFrame:
    """Every archived constituent file, with its snapshot date."""
    rows = []
    for f in sorted((Path(cfg["paths"]["raw_industry"]) / "wayback").glob("2*.csv")):
        df = read_constituent_file(f)
        df["as_of"] = pd.Timestamp(f.name[:8])
        df["source"] = "wayback " + f.name[:8]
        rows.append(df)
    today = sorted(Path(cfg["paths"]["raw_universe"]).glob("ind_nifty500list_*.csv"))[-1]
    df = read_constituent_file(today)
    df["as_of"], df["source"] = pd.Timestamp(today.stem[-10:]), "nse current list"
    rows.append(df)
    return pd.concat(rows, ignore_index=True)


def link_stocks(snaps: pd.DataFrame, spells: pd.DataFrame) -> pd.DataFrame:
    """Link snapshot rows to stocks by symbol history and name."""
    # snapshot symbol -> stock_id, using the symbol in force on the snapshot date
    hist = {
        k: parse_history(h)
        for k, h in spells.drop_duplicates("stock_id")[["stock_id", "symbol_history"]].values
    }
    owners = {}
    for k, h in hist.items():
        for sym, a, b in h:
            owners.setdefault(sym, []).append((k, a, b))
    keys = []
    for sym, d in zip(snaps["symbol"], snaps["as_of"], strict=False):
        hit = [
            k for k, a, b in owners.get(sym, []) if (a is None or d >= a) and (b is None or d < b)
        ]
        keys.append(hit[0] if hit else None)
    snaps["stock_id"] = keys
    return snaps


def build_map(cfg: dict, snaps: pd.DataFrame) -> tuple:
    """Map archived industry names to NSE's current industries."""
    # votes: stocks that appear under an old industry name and under a current one
    current = set(
        snaps.loc[
            snaps["as_of"] >= pd.Timestamp(cfg["industry"]["current_taxonomy_from"]),
            "industry",
        ]
    )
    snaps["current_taxonomy"] = snaps["industry"].isin(current)
    new = (
        snaps[snaps["current_taxonomy"] & snaps["stock_id"].notna()]
        .sort_values("as_of")
        .drop_duplicates("stock_id", keep="last")
    )
    old = snaps[~snaps["current_taxonomy"] & snaps["stock_id"].notna()].drop_duplicates(
        ["stock_id", "industry"]
    )
    pairs = old.merge(new[["stock_id", "industry"]], on="stock_id", suffixes=("", "_current"))
    votes = pairs.groupby(["industry", "industry_current"]).size().rename("votes").reset_index()
    votes["share"] = votes["votes"] / votes.groupby("industry")["votes"].transform("sum")
    votes = votes.sort_values(["industry", "votes"], ascending=[True, False])
    top = votes.drop_duplicates("industry").rename(
        columns={"industry": "old_name", "industry_current": "current_name"}
    )
    top["method"] = "votes"
    names = sorted(set(snaps.loc[~snaps["current_taxonomy"], "industry"]))
    table = pd.DataFrame({"old_name": names}).merge(top, on="old_name", how="left")
    path = Path(cfg["paths"]["industry_map"])
    if path.exists():
        hand = pd.read_csv(path, comment="#")
        table = table.drop(columns=["current_name", "method"]).merge(
            hand[["old_name", "current_name", "method"]], on="old_name", how="left"
        )
    return table, votes, current


def membership_distance(as_of: pd.Timestamp, spells: pd.DataFrame):
    """Days from a snapshot to the nearest membership spell."""
    # days from a snapshot date to the nearest day of membership (0 if inside a spell)
    best = None
    for s, e in spells:
        s = s if pd.notna(s) else pd.Timestamp("1990-01-01")
        e = e if pd.notna(e) else pd.Timestamp("2100-01-01")
        d = 0 if s <= as_of < e else min(abs((as_of - s).days), abs((as_of - e).days))
        best = d if best is None else min(best, d)
    return best


def build_industry(cfg: dict) -> tuple:
    """Industry of each stock through time."""
    out = Path(cfg["paths"]["processed_universe"])
    spells = pd.read_csv(out / "membership.csv", parse_dates=["start_date", "end_date"])
    snaps = link_stocks(read_snapshots(cfg), spells)
    table, votes, current = build_map(cfg, snaps)
    mapping = dict(zip(table["old_name"], table["current_name"], strict=False))
    votes.to_csv(out / "industry_map_votes.csv", index=False)
    table.to_csv(out / "industry_map_used.csv", index=False)

    manual_path = Path(cfg["paths"]["manual_industry"])
    manual = (
        pd.read_csv(manual_path, comment="#")
        if manual_path.exists()
        else pd.DataFrame(columns=["stock_id", "industry", "note"])
    )
    manual = dict(zip(manual["stock_id"], manual["industry"], strict=False))
    rows = []
    for key, g in spells.groupby("stock_id"):
        isin = g["isin"].dropna().iloc[0] if g["isin"].notna().any() else ""
        mine = snaps[snaps["stock_id"] == key]
        if key in manual:
            rows.append(
                dict(
                    stock_id=key,
                    isin=isin,
                    industry=manual[key],
                    source="manual",
                    as_of=None,
                    raw_industry="",
                )
            )
            continue
        if g["end_date"].isna().any():  # current member: today's NSE file
            now = mine[mine["source"] == "nse current list"]
            if len(now):
                rows.append(
                    dict(
                        stock_id=key,
                        isin=isin,
                        industry=now.iloc[0]["industry"],
                        source="nse current list",
                        as_of=now.iloc[0]["as_of"].date(),
                        raw_industry=now.iloc[0]["industry"],
                    )
                )
                continue
        if mine.empty:
            rows.append(
                dict(
                    stock_id=key,
                    isin=isin,
                    industry="Unclassified",
                    source="none",
                    as_of=None,
                    raw_industry="",
                )
            )
            continue
        dist = [
            membership_distance(d, list(zip(g["start_date"], g["end_date"], strict=False)))
            for d in mine["as_of"]
        ]
        pick = mine.assign(dist=dist).sort_values(["dist", "as_of"]).iloc[0]
        industry, source = pick["industry"], pick["source"]
        if not pick["current_taxonomy"]:
            same = mine[mine["current_taxonomy"]].sort_values("as_of")
            if len(same):  # the same stock under today's taxonomy beats a name mapping
                industry, source = (
                    same.iloc[0]["industry"],
                    same.iloc[0]["source"] + " (current taxonomy)",
                )
            else:
                industry, source = (
                    mapping.get(pick["industry"]) or "Unclassified",
                    pick["source"] + " (mapped)",
                )
        rows.append(
            dict(
                stock_id=key,
                isin=isin,
                industry=industry,
                source=source,
                as_of=pick["as_of"].date(),
                raw_industry=pick["industry"],
            )
        )
    ind = pd.DataFrame(rows)
    bad = ~ind["industry"].isin(current | {"Unclassified"})
    if bad.any():
        logger.info(
            f"  {bad.sum()} industries not in NSE's current list: "
            f"{sorted(set(ind.loc[bad, 'industry']))}"
        )
    ind.to_csv(out / "industry.csv", index=False)
    logger.info(
        f"saved {out / 'industry.csv'}: {len(ind)} stocks, "
        f"{(ind['industry'] == 'Unclassified').sum()} unclassified"
    )
    return ind, table


def industry_coverage(cfg: dict) -> tuple:
    """Share of eligible member-months with a known industry."""
    # share of eligible member-months by industry source
    out = Path(cfg["paths"]["processed_universe"])
    ind = pd.read_csv(out / "industry.csv")
    base = pd.read_csv(out / "eligibility_base.csv")
    base = base[base["member"] & base["excluded_reason"].isna()]
    m = base.merge(ind[["stock_id", "industry", "source"]], on="stock_id", how="left")
    m["source_kind"] = m["source"].str.replace(r"wayback \d+", "wayback", regex=True)
    by_source = (
        m["source_kind"].value_counts(normalize=True).rename("share_of_member_months").reset_index()
    )
    unclassified = (m["industry"] == "Unclassified").mean()
    stocks = (
        m[m["industry"] == "Unclassified"]
        .groupby("stock_id")
        .size()
        .rename("member_months")
        .reset_index()
    )
    return by_source, unclassified, stocks
