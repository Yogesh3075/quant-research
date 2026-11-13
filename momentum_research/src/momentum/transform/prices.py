from __future__ import annotations

import logging
import re
from pathlib import Path

import numpy as np
import pandas as pd

from momentum.extract.prices import read_corp_actions, read_securities, trading_days

logger = logging.getLogger(__name__)

AMOUNT = r"(?:Rs|Re|INR)[\s.:\-]*([\d]+(?:\.\d+)?)"


def parse_actions(ca: pd.DataFrame) -> pd.DataFrame:
    """Splits, bonuses, dividends and demergers from NSE corporate actions."""
    # NSE subjects -> events: split / bonus (price factor), dividend (amount), rights /
    # demerger (listed only)
    rows = []
    for _, r in ca.dropna(subset=["ex_date"]).iterrows():
        subject = re.sub(r"\s+", " ", str(r["subject"])).strip()
        # "AGM/Dividend - Rs 5/- Per Share And Bonus 1:1": split on "/" only before a
        # letter ("Rs 10/-" stays whole)
        for part in re.split(r"\s+(?:and|AND|And)\s+|\s*/\s*(?=[A-Za-z])|;|\s\+\s", subject):
            low = part.lower()
            if re.search(r"debenture|\bdeb\b|deb\d|ncrps|preference|\bpref\b", low):
                # bonus debentures / preference shares: value paid out, but no
                # change in the share count
                rows.append(
                    dict(
                        ex_date=r["ex_date"],
                        kind="bonus securities",
                        factor=np.nan,
                        amount=np.nan,
                        subject=subject,
                    )
                )
            elif re.search(r"split|splt|sub-division|sub division", low):
                fv = re.search(r"from[^\d]*([\d.]+).*?to[^\d]*([\d.]+)", low)
                fv = (
                    [float(fv.group(1).rstrip(".")), float(fv.group(2).rstrip("."))]
                    if fv
                    else [float(x) for x in re.findall(AMOUNT, part)]
                )
                if len(fv) >= 2 and fv[0] > 0:
                    rows.append(
                        dict(
                            ex_date=r["ex_date"],
                            kind="split",
                            factor=fv[1] / fv[0],
                            amount=np.nan,
                            subject=subject,
                        )
                    )
            elif "bonus" in low:
                m = re.search(r"(\d+)\s*:\s*(\d+)", part)
                if m:
                    a, b = int(m.group(1)), int(m.group(2))
                    rows.append(
                        dict(
                            ex_date=r["ex_date"],
                            kind="bonus",
                            factor=b / (a + b),
                            amount=np.nan,
                            subject=subject,
                        )
                    )
            elif re.search(r"dividend|divdend|\bdiv\b", low):
                amt = [float(x) for x in re.findall(AMOUNT, part)]
                pct = re.findall(r"([\d.]+)\s*%", part)
                face = pd.to_numeric(r.get("faceVal"), errors="coerce")
                if amt:
                    rows.append(
                        dict(
                            ex_date=r["ex_date"],
                            kind="dividend",
                            factor=np.nan,
                            amount=sum(amt),
                            subject=subject,
                        )
                    )
                elif pct and pd.notna(face):  # older records give the dividend as % of face value
                    rows.append(
                        dict(
                            ex_date=r["ex_date"],
                            kind="dividend",
                            factor=np.nan,
                            amount=sum(float(p) for p in pct) * face / 100,
                            subject=subject,
                        )
                    )
            elif re.search(r"right|rght|\brh\s*\d", low):
                rows.append(
                    dict(
                        ex_date=r["ex_date"],
                        kind="rights",
                        factor=np.nan,
                        amount=np.nan,
                        subject=subject,
                    )
                )
            elif re.search(r"demerger|scheme of arrangement|spin", low):
                rows.append(
                    dict(
                        ex_date=r["ex_date"],
                        kind="demerger",
                        factor=np.nan,
                        amount=np.nan,
                        subject=subject,
                    )
                )
            elif re.search(r"amalgamation|merger|buy ?back|delist", low):
                rows.append(
                    dict(
                        ex_date=r["ex_date"],
                        kind="merger/buyback",
                        factor=np.nan,
                        amount=np.nan,
                        subject=subject,
                    )
                )
    ev = pd.DataFrame(rows, columns=["ex_date", "kind", "factor", "amount", "subject"])
    ev["ex_date"] = pd.to_datetime(ev["ex_date"])
    return ev.drop_duplicates(["ex_date", "kind", "factor", "amount"]).sort_values("ex_date")


def load_raw(cfg: dict, kind: str, file_id: str):
    """Raw price file of one security from one source."""
    path = Path(cfg["paths"]["raw_prices"]) / kind / f"{file_id}.parquet"
    if not path.exists():
        return None
    df = pd.read_parquet(path)
    df["date"] = pd.to_datetime(df["date"])
    return df.set_index("date").sort_index()


def clean_yahoo(y, last_day: pd.Timestamp) -> tuple:
    """Drop Yahoo filler rows and rows after the last trading day."""
    if y is None:
        return None, 0
    y = y.dropna(subset=["close"])
    y = y[y.index <= last_day]  # incomplete bar: a date after the last finished index day
    prev = y["close"].shift(1)
    filler = (
        (y["volume"] == 0)
        & (y["open"] == y["high"])
        & (y["high"] == y["low"])
        & (y["low"] == y["close"])
        & (y["close"] == prev)
    )
    return y[~filler], int(filler.sum())


def nse_series(nse: pd.DataFrame, events: pd.DataFrame) -> tuple:
    """Adjusted series built from NSE closes and corporate actions."""
    # split/bonus-adjusted close, and total-return adjusted close (dividends as (1 - D /
    # previous close))
    nse = nse[nse["qty"] > 0]
    close = nse["close"].astype(float)
    split_f = pd.Series(1.0, index=close.index)
    div_f = pd.Series(1.0, index=close.index)
    used = []
    for _, e in events.iterrows():
        on = close.index[close.index >= e["ex_date"]]
        if on.empty and e["kind"] in ("split", "bonus"):
            split_f *= e[
                "factor"
            ]  # after the window: Yahoo adjusts all history for later splits, so do the same
            used.append(
                dict(
                    ex_date=e["ex_date"],
                    kind=e["kind"],
                    factor=e["factor"],
                    subject=e["subject"],
                )
            )
            continue
        if on.empty or on[0] == close.index[0]:
            continue
        day = on[0]
        if e["kind"] in ("split", "bonus"):
            split_f[close.index < day] *= e["factor"]
            used.append(
                dict(
                    ex_date=day,
                    kind=e["kind"],
                    factor=e["factor"],
                    subject=e["subject"],
                )
            )
        elif e["kind"] == "dividend":
            # raw close of the previous trading day (NSE's prev_close is already
            # split-adjusted on a split ex-date)
            prev = float(close[close.index < day].iloc[-1])
            if prev > 0 and e["amount"] < prev:
                f = 1 - e["amount"] / prev
                div_f[close.index < day] *= f
                used.append(dict(ex_date=day, kind="dividend", factor=f, subject=e["subject"]))
    return close * split_f, close * split_f * div_f, pd.DataFrame(used)


def drop_bad_yahoo_rows(y, nse, tol: float) -> tuple:
    """Drop isolated Yahoo rows that disagree with NSE."""
    # a single Yahoo row whose Yahoo/NSE ratio jumps away from both neighbours (which agree
    # with each other)
    # is a bad row (e.g. an unadjusted Muhurat-session price); the NSE trade replaces it later
    if y is None or nse is None or len(y) < 3:
        return y, 0
    raw = nse.loc[nse["qty"] > 0, "close"].astype(float)
    common = y.index.intersection(raw.index)
    r = y.loc[common, "close"] / raw[common]
    prev, nxt = r.shift(1), r.shift(-1)
    bad = (
        ((r / prev - 1).abs() > tol) & ((r / nxt - 1).abs() > tol) & ((prev / nxt - 1).abs() <= tol)
    )
    return y.drop(index=r.index[bad]), int(bad.sum())


def add_nse_sessions(y_adj, nse, events: pd.DataFrame) -> tuple:
    """Add NSE special sessions missing from Yahoo (marking only)."""
    # Yahoo leaves out some sessions (weekend budget days, Muhurat trading, a few others) that
    # NSE traded:
    # add the NSE close scaled by the Yahoo/NSE adjustment ratio of the previous common day
    # (the next common day if a corporate action falls in between). Real trades only, no filling.
    if nse is None:
        return y_adj, 0
    raw = nse.loc[nse["qty"] > 0, "close"].astype(float)
    missing = raw.index[
        (raw.index > y_adj.index.min())
        & (raw.index < y_adj.index.max())
        & ~raw.index.isin(y_adj.index)
    ]
    if missing.empty:
        return y_adj, 0
    common = y_adj.index.intersection(raw.index)
    ratio = y_adj[common] / raw[common]
    added = {}
    for d in missing:
        prev, nxt = common[common < d], common[common > d]
        if prev.empty or nxt.empty:
            continue
        between = events[(events["ex_date"] > prev[-1]) & (events["ex_date"] <= d)]
        added[d] = raw[d] * (ratio[nxt[0]] if len(between) else ratio[prev[-1]])
    return pd.concat([y_adj, pd.Series(added, dtype=float)]).sort_index(), len(added)


def longest_run(flags) -> int:
    """Length of the longest run of True flags."""
    best = run = 0
    for f in flags:
        run = run + 1 if f else 0
        best = max(best, run)
    return best


def crosscheck(y, nse_split, raw, events: pd.DataFrame, cfg: dict) -> dict:
    """Compare Yahoo and NSE day by day and classify the security."""
    p = cfg["crosscheck"]
    common = y.index.intersection(nse_split.index)
    if len(common) == 0:
        return dict(
            overlap_days=0,
            share_within=np.nan,
            cls="disagree",
            note="no overlapping days",
            worst="",
            factor_mismatches=0,
        )
    ratio = y.loc[common, "close"] / nse_split.loc[common]
    # Yahoo also adjusts for demergers / rights: a lasting step in the ratio on such an NSE
    # ex-date is explained
    other = events[events["kind"].isin(["demerger", "rights", "merger/buyback"])]
    explained = []
    step = ratio / ratio.shift(1)
    before = ratio.rolling(p["step_days"]).median()
    after = ratio[::-1].rolling(p["step_days"]).median()[::-1]
    for d in step.index[(step - 1).abs() > p["tolerance"]]:
        i = ratio.index.get_loc(d)
        if i < p["step_days"] or i + p["step_days"] > len(ratio):
            continue
        lasting = after.iloc[i] / before.iloc[i - 1]
        near = other[(other["ex_date"] - d).abs() <= pd.Timedelta(days=p["explain_days"])]
        if abs(lasting - 1) > p["tolerance"] and len(near):
            ratio[ratio.index < d] *= lasting
            explained.append(f"{d:%Y-%m-%d} {near.iloc[0]['kind']} x{1 / lasting:.4f}")
    # events after the overlap: Yahoo scales all of this history by a constant; compare
    # against the ending level
    later = events[
        events["kind"].isin(["demerger", "rights", "merger/buyback", "bonus securities"])
        & (events["ex_date"] > common[-1])
    ]
    end_level = ratio.tail(p["step_days"]).median()
    if len(later) and abs(end_level - 1) > p["tolerance"]:
        ratio = ratio / end_level
        explained.append(
            f"after the window ({later.iloc[0]['ex_date']:%Y-%m-%d} {later.iloc[0]['kind']}) "
            f"x{end_level:.4f}"
        )
    diff = (ratio - 1).abs()
    within = diff <= p["tolerance"]
    worst = diff.sort_values(ascending=False).head(p["worst_n"])
    # Yahoo's implied factor across each NSE split/bonus ex-date: (Yahoo / raw NSE) the day
    # before over the day of
    mismatches = 0
    raw_close = raw.loc[raw["qty"] > 0, "close"].astype(float)
    for d, g in events[events["kind"].isin(["split", "bonus"])].groupby("ex_date"):
        on = common[common >= d]
        if on.empty or on[0] == common[0] or (on[0] - d).days > p["event_days"]:
            continue
        prev = common[common < on[0]][-1]
        implied = (y.at[prev, "close"] / raw_close[prev]) / (
            y.at[on[0], "close"] / raw_close[on[0]]
        )
        if abs(implied / g["factor"].prod() - 1) > p["factor_tolerance"]:
            mismatches += 1
    share = within.mean()
    coverage = len(common) / len(nse_split)
    run = longest_run(~within.values)
    if coverage < p["min_yahoo_coverage"]:
        cls, note = "disagree", f"Yahoo has {coverage:.0%} of NSE trading days"
    elif mismatches:
        cls, note = "disagree", f"{mismatches} split/bonus factors differ"
    elif share >= p["agree_share"]:
        cls, note = "agree", ""
    elif share >= p["minor_share"] and run <= p["max_bad_run"]:
        cls, note = "minor", f"longest run of differing days {run}"
    else:
        cls, note = "disagree", f"longest run of differing days {run}"
    if explained:
        note = (note + "; " if note else "") + "Yahoo also adjusts at " + ", ".join(explained)
    return dict(
        overlap_days=len(common),
        share_within=round(share, 4),
        cls=cls,
        note=note,
        factor_mismatches=mismatches,
        explained_steps=len(explained),
        ratio=ratio,
        worst="; ".join(f"{d:%Y-%m-%d} {v:.1%}" for d, v in worst.items()),
    )


STANDARD_FACTORS = sorted({b / (a + b) for a in range(1, 11) for b in range(1, 11)})


def resolve_disagree(ratio, raw, events: pd.DataFrame, cfg: dict) -> tuple:
    """Pick the source for a security where Yahoo and NSE disagree."""
    # one lasting step in Yahoo/NSE that looks like a split or bonus NSE did not record ->
    # Yahoo is right
    p = cfg["crosscheck"]
    n = p["step_days"]
    before = ratio.rolling(n).median().shift(1)
    after = ratio[::-1].rolling(n).median()[::-1]
    jump = (after / before - 1).abs()
    steps, last = [], None
    for d in jump.index[jump > p["tolerance"]]:
        i = ratio.index.get_loc(d)
        if last is not None and i - last <= n:  # same step seen over neighbouring days
            last = i
            continue
        last = i
        daily = (ratio / ratio.shift(1)).iloc[max(i - n, 1) : i + n]
        steps.append((daily.apply(np.log).abs()).idxmax())  # the day the ratio actually moved
    if len(steps) != 1:
        return None, f"{len(steps)} lasting steps"
    d = steps[0]
    i = ratio.index.get_loc(d)
    factor = before.iloc[i] / after.iloc[i]  # Yahoo scaled earlier prices by this
    nearest = min(STANDARD_FACTORS, key=lambda f: abs(f / factor - 1))
    inverse = min(STANDARD_FACTORS, key=lambda f: abs(f * factor - 1))
    raw_close = raw.loc[raw["qty"] > 0, "close"].astype(float)
    prev = raw_close.index[raw_close.index < d]
    raw_move = (
        raw_close[d] / raw_close[prev[-1]] if len(prev) and d in raw_close.index else float("nan")
    )
    recorded = events[
        events["kind"].isin(["split", "bonus"])
        & ((events["ex_date"] - d).abs() <= pd.Timedelta(days=p["event_days"]))
    ]
    info = dict(
        step_date=d.date(),
        yahoo_factor=round(factor, 4),
        standard=round(nearest, 4),
        raw_move=round(raw_move, 4),
    )
    if abs(inverse * factor - 1) <= p["standard_tolerance"]:
        return info, "NSE records a split/bonus that Yahoo lacks"
    if abs(nearest / factor - 1) > p["standard_tolerance"]:
        return info, "step is not a standard split/bonus ratio"
    if not abs(raw_move / factor - 1) <= p["raw_move_tolerance"]:
        return info, "NSE raw close does not show the step"
    if len(recorded):
        return info, "NSE records a split/bonus on that date"
    return info, "NSE record missing corporate action"


def build_prices(cfg: dict) -> None:
    """Adjusted closes for every security, with the source of each."""
    out = Path(cfg["paths"]["processed_prices"])
    out.mkdir(parents=True, exist_ok=True)
    sec = read_securities(cfg)
    days = trading_days(cfg)
    last_day = days.max()
    (
        adj,
        close,
        volume,
        value,
        src_rows,
        checks,
        events_all,
        used_all,
        cand,
        filler_total,
    ) = {}, {}, {}, {}, [], [], [], [], [], 0
    resolutions, bad_total = [], 0
    logger.info(f"building prices for {len(sec)} securities")
    for n, r in sec.iterrows():
        fid = r["file_id"]
        symbols = [s for s, _, _ in r["history"]]
        events = parse_actions(read_corp_actions(cfg, symbols))
        events_all.append(events.assign(file_id=fid))
        y, fillers = clean_yahoo(load_raw(cfg, "yahoo", fid), last_day)
        filler_total += fillers
        nse = load_raw(cfg, "nse", fid)
        y, bad_rows = drop_bad_yahoo_rows(y, nse, cfg["prices"]["bad_row_tolerance"])
        bad_total += bad_rows
        check = dict(
            file_id=fid,
            stock_id=r["stock_id"],
            yahoo_rows=0 if y is None else len(y),
            nse_rows=0 if nse is None else len(nse),
        )
        if nse is not None and len(nse[nse["qty"] > 0]):
            nse_split, nse_tr, used = nse_series(nse, events)
            used_all.append(used.assign(file_id=fid))
            close[fid] = nse.loc[nse["qty"] > 0, "close"].astype(float)
            volume[fid] = nse.loc[nse["qty"] > 0, "qty"].astype(float)
            value[fid] = nse.loc[nse["qty"] > 0, "value"].astype(float)
        else:
            nse_split = nse_tr = None
        reason = ""
        if y is not None and len(y) and nse_split is not None:
            check.update(crosscheck(y, nse_split, nse, events, cfg))
            ratio = check.pop("ratio")
            source = "yahoo" if check["cls"] in ("agree", "minor") else "nse_built"
            reason = f"cross-check {check['cls']}"
            if check["cls"] == "disagree":
                info, why = resolve_disagree(ratio, nse, events, cfg)
                resolutions.append(
                    dict(
                        file_id=fid,
                        stock_id=r["stock_id"],
                        note=check["note"],
                        **(info or {}),
                        decision=why,
                    )
                )
                if why == "NSE record missing corporate action":
                    source, reason = "yahoo", why
                else:
                    reason = f"cross-check disagree ({why})"
        elif y is not None and len(y):
            check.update(cls="yahoo only", note="no NSE rows")
            source = "yahoo"
            close[fid] = y["close"]
        elif nse_split is not None:
            check.update(cls="nse only", note="")
            source = "nse_built"
        else:
            check.update(cls="no data", note="")
            source = "none"
        added = 0
        if source == "yahoo":
            series, added = add_nse_sessions(y["adj_close"].dropna(), nse, events)
        else:
            series = nse_tr if source == "nse_built" else None
        if series is not None:
            series = series.dropna()
            adj[fid] = series
            ret = series.pct_change()
            big = ret[ret.abs() > cfg["prices"]["event_move"]]
            for d, v in big.items():
                near = events[
                    (events["ex_date"] - d).abs()
                    <= pd.Timedelta(days=cfg["crosscheck"]["event_days"])
                ]
                if near.empty:
                    cand.append(
                        dict(
                            file_id=fid,
                            stock_id=r["stock_id"],
                            date=d.date(),
                            move=round(v, 4),
                            source=source,
                        )
                    )
        src_rows.append(
            dict(
                file_id=fid,
                stock_id=r["stock_id"],
                isin=r["isin"],
                price_source=source,
                source_reason=reason or check["cls"],
                nse_sessions_added=added,
                first_date=series.index.min().date()
                if series is not None and len(series)
                else None,
                last_date=series.index.max().date() if series is not None and len(series) else None,
            )
        )
        checks.append(check)
        if n % 100 == 0:
            logger.info(f"  {n + 1}/{len(sec)}")

    pd.DataFrame(adj).sort_index().to_parquet(out / "adj_close.parquet")
    pd.DataFrame(close).sort_index().to_parquet(out / "close.parquet")
    pd.DataFrame(volume).sort_index().to_parquet(out / "volume.parquet")
    pd.DataFrame(value).sort_index().to_parquet(out / "traded_value.parquet")
    pd.DataFrame(src_rows).to_csv(out / "price_source.csv", index=False)
    pd.DataFrame(checks).to_csv(out / "crosscheck.csv", index=False)
    pd.concat(events_all).to_csv(out / "corporate_actions_parsed.csv", index=False)
    pd.concat(used_all).to_csv(out / "nse_adjustments_applied.csv", index=False)
    pd.DataFrame(cand, columns=["file_id", "stock_id", "date", "move", "source"]).to_csv(
        out / "price_event_candidates.csv", index=False
    )
    (out / "yahoo_fillers_removed.txt").write_text(str(filler_total))
    (out / "yahoo_bad_rows_removed.txt").write_text(str(bad_total))
    pd.DataFrame(resolutions).to_csv(out / "disagree_resolution.csv", index=False)
    logger.info(f"saved prices for {len(adj)} securities")


def delistings(cfg: dict) -> pd.DataFrame:
    """Delisted securities and their last trading day."""
    out = Path(cfg["paths"]["processed_prices"])
    src = pd.read_csv(out / "price_source.csv", parse_dates=["first_date", "last_date"])
    spells = pd.read_csv(
        Path(cfg["paths"]["processed_universe"]) / "membership.csv",
        parse_dates=["start_date", "end_date"],
    )
    spells = spells[spells["eligible"]]
    ev = pd.read_csv(out / "corporate_actions_parsed.csv", parse_dates=["ex_date"])
    delisted = sorted(Path(cfg["paths"]["raw_universe"]).glob("delisted_*.csv"))[-1]
    dl = pd.read_csv(delisted, encoding="latin-1").iloc[:, :4]
    dl.columns = ["symbol", "company", "date", "type"]
    dl["symbol"] = dl["symbol"].astype(str).str.strip()
    last_index_day = trading_days(cfg).max()
    window_end = pd.read_csv(out / "securities.csv", parse_dates=["end"]).set_index("file_id")[
        "end"
    ]
    rows = []
    for _, s in src.dropna(subset=["last_date"]).iterrows():
        # stopped trading: prices end well before the end of the window we asked for
        if s["last_date"] >= min(window_end[s["file_id"]], last_index_day) - pd.Timedelta(
            days=cfg["prices"]["stale_days"]
        ):
            continue
        sp = spells[spells["stock_id"] == s["stock_id"]]
        for _, x in sp.iterrows():
            end = x["end_date"] if pd.notna(x["end_date"]) else last_index_day
            if (
                (x["start_date"] if pd.notna(x["start_date"]) else pd.Timestamp.min)
                <= s["last_date"]
                <= end + pd.DateOffset(months=2)
            ):
                hist = str(x["symbol_history"]).replace(" from ", " ").split("; ")
                syms = [h.split(" ")[0] for h in hist]
                why = dl[dl["symbol"].isin(syms)]["type"].dropna().astype(str).str.strip().tolist()
                ca = ev[
                    (ev["file_id"] == s["file_id"])
                    & ev["kind"].isin(["merger/buyback", "demerger"])
                ]["subject"].tolist()
                rows.append(
                    dict(
                        file_id=s["file_id"],
                        stock_id=s["stock_id"],
                        last_price_date=s["last_date"].date(),
                        spell_end=x["end_date"].date() if pd.notna(x["end_date"]) else "",
                        index_exit_reason=x["exit_reason"],
                        nse_delisting=", ".join(why),
                        corporate_actions=" | ".join(ca[-2:]),
                        inside_spell=pd.isna(x["end_date"]) or s["last_date"] < x["end_date"],
                    )
                )
                break
    out_df = pd.DataFrame(rows)
    out_df.to_csv(out / "delistings.csv", index=False)
    return out_df


def calendar_check(cfg: dict, elig: pd.DataFrame) -> tuple:
    """Members with no price on a trading day, and thin days."""
    out = Path(cfg["paths"]["processed_prices"])
    adj = pd.read_parquet(out / "adj_close.parquet")
    days = trading_days(cfg)
    off = adj.loc[~adj.index.isin(days)].notna().sum()
    off = (
        off[off > 0]
        .rename("rows_on_non_index_days")
        .reset_index()
        .rename(columns={"index": "file_id"})
    )
    # index days with many eligible stocks missing: eligible set taken from the month-end before
    month_set = elig[elig["eligible_member"]].groupby("date")["file_id"].apply(set)
    rows = []
    for d in days[days >= adj.index.min()]:
        prev = month_set.index[month_set.index < d]
        if prev.empty:
            continue
        ids = [i for i in month_set[prev[-1]] if i in adj.columns]
        if not ids:
            continue
        missing = adj.loc[d, ids].isna().mean() if d in adj.index else 1.0
        if missing > cfg["prices"]["max_missing_share"]:
            rows.append(dict(date=d.date(), missing_share=round(missing, 3), eligible=len(ids)))
    return off, pd.DataFrame(rows)


def build_eligibility(cfg: dict) -> tuple:
    """Eligible member-days and the price gap list."""
    # month-end eligibility = member, not excluded by a decision, and an adjusted price on the
    # last index day of the month
    uni = Path(cfg["paths"]["processed_universe"])
    out = Path(cfg["paths"]["processed_prices"])
    base = pd.read_csv(uni / "eligibility_base.csv", parse_dates=["date"])
    sec = pd.read_csv(out / "securities.csv")
    adj = pd.read_parquet(out / "adj_close.parquet")
    days = trading_days(cfg)
    base = base.merge(sec[["stock_id", "file_id"]], on="stock_id", how="left")
    base["excluded_reason"] = base["excluded_reason"].fillna("")
    base["eligible_member"] = base["member"] & (base["excluded_reason"] == "")
    last_day = {m: days[days <= m].max() for m in base["date"].unique()}
    base["price_date"] = base["date"].map(last_day)
    base["has_price"] = [
        bool(f in adj.columns and d in adj.index and pd.notna(adj.at[d, f]))
        for f, d in zip(base["file_id"], base["price_date"], strict=False)
    ]
    base["eligible"] = base["eligible_member"] & base["has_price"]
    base.to_csv(uni / "eligibility.csv", index=False)
    gaps = base[base["eligible_member"] & ~base["has_price"]]
    gaps.to_csv(out / "price_gaps.csv", index=False)
    return base, gaps
