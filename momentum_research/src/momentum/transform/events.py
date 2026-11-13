from __future__ import annotations

import logging
import re
from pathlib import Path

import numpy as np
import pandas as pd

from momentum.extract.prices import (
    read_bhavcopy,
    read_corp_actions,
    read_index,
    read_securities,
    trading_days,
)
from momentum.transform.prices import load_raw

logger = logging.getLogger(__name__)


def notice_demergers(cfg: dict, sec: pd.DataFrame) -> pd.DataFrame:
    """Demergers named in index notices, mapped to securities."""
    # parent symbol and date from "special pre-open session to be conducted for X Ltd. (SYM)
    # ... on <date>"
    owner = {s: r["file_id"] for _, r in sec.iterrows() for s, _, _ in r["history"]}
    rows = []
    for f in sorted((Path(cfg["paths"]["processed_universe"]) / "notice_text").glob("*.txt")):
        body = re.sub(r"\s+", " ", f.read_text())
        for m in re.finditer(
            r"special pre-open session to be conducted for .*?\(([A-Z0-9&\-]+)\) "
            r"in Capital Market segment on "
            r"([A-Z][a-z]+ \d{1,2}, ?\d{4})",
            body,
        ):
            if m.group(1) in owner:
                rows.append(
                    dict(
                        file_id=owner[m.group(1)],
                        ex_date=pd.to_datetime(m.group(2).replace(",", ", ")),
                        kind="demerger",
                        subject=f"notice {f.stem}",
                        source="notice",
                    )
                )
    return pd.DataFrame(
        rows, columns=["file_id", "ex_date", "kind", "subject", "source"]
    ).drop_duplicates(["file_id", "ex_date"])


def rights_value(subject: str, prev_close: float, face: float) -> float:
    """Theoretical value of a rights entitlement from its ratio and price."""
    # theoretical drop for "Rights a:b @ Premium Rs X" (a new for b held): (P - TERP) / P
    m = re.search(r"(\d+)\s*:\s*(\d+)", subject)
    prem = re.search(r"(?:prem(?:ium)?|@)\D*?(\d+(?:\.\d+)?)", subject, re.IGNORECASE)
    if not m or not prem or not prev_close:
        return np.nan
    a, b = int(m.group(1)), int(m.group(2))
    issue = float(prem.group(1)) + (face if "prem" in subject.lower() and pd.notna(face) else 0)
    terp = (b * prev_close + a * issue) / (a + b)
    return max(0.0, (prev_close - terp) / prev_close)


def series_moves(adj: pd.DataFrame, idx, d: pd.Timestamp, after) -> dict:
    """Price moves around an event date."""
    # chosen-series and index returns from the day before d to d, and to `after` trading days later
    s = adj.dropna()
    on = s.index[s.index >= d]
    before = s.index[s.index < d]
    if on.empty or before.empty:
        return None
    d0, p = on[0], before[-1]
    later = s.index[s.index >= d0]
    d5 = later[min(after, len(later) - 1)]

    def mkt(a, b):
        return idx.asof(b) / idx.asof(a) - 1

    return dict(
        day=d0,
        prev=p,
        move=s[d0] / s[p] - 1,
        mkt=mkt(p, d0),
        move_after=s[d5] / s[p] - 1,
        mkt_after=mkt(p, d5),
    )


def review_demergers_rights(
    cfg: dict, sec: pd.DataFrame, src, adj: pd.DataFrame, idx
) -> pd.DataFrame:
    """Demergers and rights issues not adjusted in the prices."""
    p = cfg["events"]
    ev = pd.read_csv(
        Path(cfg["paths"]["processed_prices"]) / "corporate_actions_parsed.csv",
        parse_dates=["ex_date"],
    )
    ev = ev[ev["kind"].isin(["demerger", "rights"])].assign(source="nse corporate actions")
    notes = notice_demergers(cfg, sec)
    # a notice date counts only if NSE has no demerger record near it
    keep = [
        not (
            (ev["file_id"] == n["file_id"])
            & (ev["kind"] == "demerger")
            & ((ev["ex_date"] - n["ex_date"]).abs() <= pd.Timedelta(days=p["match_days"]))
        ).any()
        for _, n in notes.iterrows()
    ]
    ev = pd.concat([ev, notes[keep]], ignore_index=True)
    ev = ev[ev["ex_date"].between(pd.Timestamp(cfg["prices"]["start"]), idx.index.max())]
    eligible = set(src["file_id"])
    rows = []
    for _, e in ev[ev["file_id"].isin(eligible)].iterrows():
        f = e["file_id"]
        if f not in adj.columns:
            continue
        mv = series_moves(adj[f], idx, e["ex_date"], p["recover_days"])
        raw = load_raw(cfg, "nse", f)
        if mv is None or raw is None:
            rows.append(
                dict(
                    file_id=f,
                    ex_date=e["ex_date"].date(),
                    kind=e["kind"],
                    source=e["source"],
                    status="no price around ex-date",
                )
            )
            continue
        raw = raw.loc[raw["qty"] > 0, "close"].astype(float)
        raw_prev, raw_day = raw.asof(mv["prev"]), raw.asof(mv["day"])
        raw_move = raw_day / raw_prev - 1 if raw_prev else np.nan
        value = np.nan
        if e["kind"] == "rights":
            ca = read_corp_actions(
                cfg, [s for s, _, _ in sec.set_index("file_id").at[f, "history"]]
            )
            face = pd.to_numeric(
                ca.loc[ca["ex_date"] == e["ex_date"], "faceVal"], errors="coerce"
            ).max()
            value = rights_value(str(e["subject"]), raw_prev, face)
        if np.isnan(value):
            value = max(0.0, mv["mkt"] - raw_move) if not np.isnan(raw_move) else np.nan
        excess, excess_after = (
            mv["move"] - mv["mkt"],
            mv["move_after"] - mv["mkt_after"],
        )
        if np.isnan(value) or value < p["min_value"]:
            status = "immaterial"
        elif excess < -value / 2 and excess_after < -value / 2:
            status = "unadjusted"
        else:
            status = "adjusted"
        rows.append(
            dict(
                file_id=f,
                ex_date=e["ex_date"].date(),
                kind=e["kind"],
                source=e["source"],
                subject=e["subject"],
                implied_value=round(value, 4),
                raw_move=round(raw_move, 4),
                series_move=round(mv["move"], 4),
                market_move=round(mv["mkt"], 4),
                excess_after=round(excess_after, 4),
                status=status,
                day=mv["day"].date(),
            )
        )
    return pd.DataFrame(rows)


def classify_candidates(cfg: dict, sec: pd.DataFrame, src, adj: pd.DataFrame, idx) -> pd.DataFrame:
    """Classify large unexplained price moves for quarantine."""
    p = cfg["events"]
    out = Path(cfg["paths"]["processed_prices"])
    cand = pd.read_csv(out / "price_event_candidates.csv", parse_dates=["date"])
    ev = pd.read_csv(out / "corporate_actions_parsed.csv", parse_dates=["ex_date"])
    notes = notice_demergers(cfg, sec)
    rows = []
    for _, c in cand.iterrows():
        f, d = c["file_id"], c["date"]

        def near(dates, days, d=d):
            return bool((abs(pd.Series(dates) - d) <= pd.Timedelta(days=days)).any())

        y = load_raw(cfg, "yahoo", f)
        yahoo_action = y is not None and near(
            y.index[y["stock_splits"].fillna(0) > 0], p["match_days"]
        )
        nse_action = near(ev.loc[ev["file_id"] == f, "ex_date"], p["match_days"])
        notice = near(notes.loc[notes["file_id"] == f, "ex_date"], p["match_days"])
        raw = load_raw(cfg, "nse", f)
        raw_move, vol_ratio = np.nan, np.nan
        if raw is not None and d in raw.index:
            r = raw[raw["qty"] > 0]
            prev = r.index[r.index < d]
            if len(prev):
                raw_move = r.at[d, "close"] / r.at[prev[-1], "close"] - 1
                base = r.loc[prev[-p["volume_days"] :], "qty"].median()
                vol_ratio = r.at[d, "qty"] / base if base else np.nan
        mv = series_moves(adj[f], idx, d, p["recover_days"]) if f in adj.columns else None
        reversed_ = (
            mv is None
            or abs(mv["move_after"]) < abs(c["move"]) / 2
            or np.sign(mv["move_after"]) != np.sign(c["move"])
        )
        if yahoo_action or nse_action or notice:
            cls = "corporate_action"
            why = ", ".join(
                n
                for n, v in [
                    ("Yahoo action", yahoo_action),
                    ("NSE action", nse_action),
                    ("notice", notice),
                ]
                if v
            )
        elif (
            not np.isnan(raw_move)
            and abs(raw_move - c["move"]) <= p["same_move"]
            and vol_ratio >= p["min_volume_ratio"]
        ):
            # confirmed by NSE on at least median volume counts as real even if it
            # reverses (Phase 3 rule)
            cls = "real"
            why = "NSE raw close shows it, volume at or above median" + (
                f", reversed within {p['recover_days']} days" if reversed_ else ""
            )
        else:
            bits = []
            if np.isnan(raw_move) or abs(raw_move - c["move"]) > p["same_move"]:
                bits.append("not in NSE raw close")
            if not np.isnan(vol_ratio) and vol_ratio < p["min_volume_ratio"]:
                bits.append("low volume")
            if reversed_:
                bits.append(f"reversed within {p['recover_days']} days (not by itself a reason)")
            cls, why = "suspect", ", ".join(bits)
        rows.append(
            dict(
                file_id=f,
                stock_id=c["stock_id"],
                date=d.date(),
                move=c["move"],
                source=c["source"],
                raw_move=round(raw_move, 4) if not np.isnan(raw_move) else None,
                volume_vs_median=round(vol_ratio, 2) if not np.isnan(vol_ratio) else None,
                cls=cls,
                why=why,
            )
        )
    return pd.DataFrame(rows)


def relisted_check(cfg: dict, delist: pd.DataFrame) -> pd.DataFrame:
    """Check that delisted stocks do not trade again."""
    # a "delisting" followed by trading under another symbol with the same ISIN issuer code
    folder = Path(cfg["paths"]["raw_prices"]) / "nse_bhavcopy"
    eq = pd.read_csv(sorted(Path(cfg["paths"]["raw_universe"]).glob("EQUITY_L_*.csv"))[-1])
    eq.columns = [c.strip() for c in eq.columns]
    rows = []
    for _, r in delist.iterrows():
        issuer = str(r["file_id"])[:7]
        if not issuer.startswith("IN"):
            continue
        found = []
        last = pd.Timestamp(r["last_price_date"])
        for k in range(1, cfg["events"]["relist_days"]):
            f = folder / f"bhav_{last + pd.Timedelta(days=k):%Y-%m-%d}.zip"
            if f.exists():
                b = read_bhavcopy(f)
                hit = b[
                    b["isin"].astype(str).str.startswith(issuer)
                    & (b["series"].isin(cfg["prices"]["nse_series"]))
                ]
                found += [
                    f"{s} ({i}) from {f.stem[5:]}"
                    for s, i in zip(hit["symbol"], hit["isin"], strict=False)
                ]
                if found:
                    break
        now = eq[eq["ISIN NUMBER"].astype(str).str.startswith(issuer)]
        if found or len(now):
            rows.append(
                dict(
                    stock_id=r["stock_id"],
                    file_id=r["file_id"],
                    last_price_date=r["last_price_date"],
                    traded_again=", ".join(found),
                    listed_today=", ".join(now["SYMBOL"]),
                )
            )
    return pd.DataFrame(rows)


def find_suspensions(cfg: dict, adj: pd.DataFrame) -> pd.DataFrame:
    """Trading gaps that look like suspensions."""
    # a stock that stops trading for at least `min_days` index sessions and trades again
    # within `max_days` calendar days
    p = cfg["events"]
    days = trading_days(cfg)
    rows = []
    for f in adj.columns:
        s = adj[f].dropna()
        if len(s) < 2:
            continue
        pos = days.get_indexer(s.index)
        gaps = np.diff(pos) - 1
        for k in np.where(gaps >= p["suspension_min_days"])[0]:
            last, resume = s.index[k], s.index[k + 1]
            if (resume - last).days <= p["suspension_max_days"]:
                rows.append(
                    dict(
                        file_id=f,
                        last_close=last.date(),
                        resume=resume.date(),
                        missing_sessions=int(gaps[k]),
                    )
                )
    return pd.DataFrame(rows, columns=["file_id", "last_close", "resume", "missing_sessions"])


def build_events(cfg: dict) -> tuple:
    """Event table, quarantines and return overrides."""
    out = Path(cfg["paths"]["processed_prices"])
    sec = read_securities(cfg)
    src = pd.read_csv(out / "price_source.csv")
    adj = pd.read_parquet(out / "adj_close.parquet")
    idx = read_index(cfg, cfg["prices"]["indices"][0], "price")
    dr = review_demergers_rights(cfg, sec, src, adj, idx)
    cand = classify_candidates(cfg, sec, src, adj, idx)
    delist = pd.read_csv(out / "delistings.csv")
    relisted = relisted_check(cfg, delist)
    susp = find_suspensions(cfg, adj).merge(src[["file_id", "stock_id"]], on="file_id", how="left")
    susp.to_csv(out / "suspensions.csv", index=False)

    # look-back exclusions (momentum) and zero-return days (holding returns)
    excl = [
        dict(
            file_id=r["file_id"],
            date=r["day"],
            reason="unadjusted demerger/rights in look-back",
        )
        for _, r in dr[dr["status"] == "unadjusted"].iterrows()
    ]
    excl += [
        dict(
            file_id=r["file_id"],
            date=r["date"],
            reason="quarantined price event (suspect)",
        )
        for _, r in cand[cand["cls"] == "suspect"].iterrows()
    ]
    excl += [
        dict(
            file_id=r["file_id"],
            date=r["date"],
            reason="unadjusted corporate action in look-back",
        )
        for _, r in cand[cand["cls"] == "corporate_action"].iterrows()
    ]
    excl = pd.DataFrame(excl, columns=["file_id", "date", "reason"])
    excl.to_csv(out / "lookback_exclusions.csv", index=False)
    zero = excl[excl["reason"] != "quarantined price event (suspect)"][
        ["file_id", "date", "reason"]
    ]
    zero.to_csv(out / "return_overrides.csv", index=False)
    dr.to_csv(out / "demerger_rights_review.csv", index=False)
    cand.to_csv(out / "event_review.csv", index=False)
    relisted.to_csv(out / "relisted_check.csv", index=False)
    logger.info(
        f"demergers/rights: {dr['status'].value_counts().to_dict()}; events: "
        f"{cand['cls'].value_counts().to_dict()}; "
        f"relisted under another symbol: {len(relisted)}; suspensions: {len(susp)}"
    )
    return dr, cand, relisted, excl
