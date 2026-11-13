from __future__ import annotations

import logging
import time
from pathlib import Path

import numpy as np
import pandas as pd
import requests

from optsell.config import tri_path

logger = logging.getLogger(__name__)

RAW = Path("data/raw")
PROC = Path("data/processed")
NSE = "https://nsearchives.nseindia.com/content"
UA = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Referer": "https://www.nseindia.com/",
}
UDIFF_START = pd.Timestamp("2024-07-08")
IDX_START = pd.Timestamp("2012-06-01")


def read_tri(cfg: dict) -> pd.DataFrame:
    """NIFTY 50 TRI from the factor_regime_rotation download."""
    t = pd.read_csv(tri_path(cfg), parse_dates=["date"])
    return t.set_index("date")[cfg["tri_col"]].rename("tri")


def calendar(cfg: dict) -> pd.DatetimeIndex:
    """Trading days to download."""
    days = read_tri(cfg).index
    extra = pd.bdate_range(days[-1] + pd.Timedelta(days=1), pd.Timestamp.today().normalize())
    days = days.union(extra)
    yp = RAW / "yahoo_nsei.csv"
    if yp.exists():
        days = days.union(pd.read_csv(yp, parse_dates=["date"]).date)
    return days[days >= cfg["start"]]


def fo_urls(d) -> list:
    """NSE F&O bhavcopy URLs for a day, the likelier format first."""
    month, day = d.strftime("%b").upper(), d.strftime("%d%b%Y").upper()
    old = f"{NSE}/historical/DERIVATIVES/{d:%Y}/{month}/fo{day}bhav.csv.zip"
    new = f"{NSE}/fo/BhavCopy_NSE_FO_0_0_0_{d:%Y%m%d}_F_0000.csv.zip"
    return [old, new] if d < UDIFF_START else [new, old]


def idx_urls(d) -> list:
    """NSE index close file URLs for a day."""
    return [f"{NSE}/indices/ind_close_all_{d:%d%m%Y}.csv"]


def fetch(s, urls, check, pause) -> tuple:
    """Download the first URL that works; reports whether NSE blocked the request."""
    blocked = False
    for u in urls:
        try:
            r = s.get(u, timeout=30)
        except requests.RequestException:
            blocked = True
            time.sleep(pause)
            continue
        time.sleep(pause)
        if r.status_code == 200 and check(r.content):
            return r.content, False
        if r.status_code in (401, 403, 429) or (r.status_code == 200 and not check(r.content)):
            blocked = True
    return None, blocked


def download_set(s, days, folder, urls, check, ext, pause) -> int:
    """Download one file per day into a folder, skipping files already there."""
    folder.mkdir(parents=True, exist_ok=True)
    miss_file = folder / "missing.txt"
    missing = set(miss_file.read_text().split()) if miss_file.exists() else set()
    todo = [
        d
        for d in days
        if not (folder / f"{d:%Y%m%d}{ext}").exists() and f"{d:%Y%m%d}" not in missing
    ]
    logger.info(f"{folder}: {len(todo)} days to fetch")
    streak = 0
    for i, d in enumerate(todo):
        body, blocked = fetch(s, urls(d), check, pause)
        if body is not None:
            (folder / f"{d:%Y%m%d}{ext}").write_bytes(body)
            streak = 0
        else:
            streak = streak + 1 if blocked else 0
            if not blocked and d < pd.Timestamp.today().normalize() - pd.Timedelta(days=3):
                missing.add(f"{d:%Y%m%d}")
                miss_file.write_text("\n".join(sorted(missing)))
            if streak >= 5:
                logger.info(
                    f"NSE appears to be blocking downloads (stopped at {d:%Y-%m-%d}). "
                    "Put files by hand into data/raw/manual/ and rerun."
                )
                return False
        if i % 200 == 0:
            logger.info(f"  {d:%Y-%m-%d} ({i}/{len(todo)})")
    return True


def download_yahoo(cfg: dict) -> None:
    """NIFTY 50 closes from Yahoo before NSE's index files start (mid-2012)."""
    import yfinance as yf

    y = yf.download("^NSEI", start=cfg["start"], auto_adjust=False, progress=False)
    y.columns = [c[0] if isinstance(c, tuple) else c for c in y.columns]
    y = y[["Close"]].rename(columns={"Close": "close"}).rename_axis("date").reset_index()
    RAW.mkdir(parents=True, exist_ok=True)
    y.to_csv(RAW / "yahoo_nsei.csv", index=False)
    logger.info(f"yahoo ^NSEI: {len(y)} rows")


def download(cfg: dict) -> None:
    """Download bhavcopies, index files and the Yahoo series."""
    download_yahoo(cfg)
    days = calendar(cfg)
    s = requests.Session()
    s.headers.update(UA)
    ok = download_set(s, days, RAW / "fo", fo_urls, lambda b: b[:2] == b"PK", ".zip", cfg["pause"])
    if not ok:
        return
    idx_days = days[days >= IDX_START]
    download_set(
        s,
        idx_days,
        RAW / "index",
        idx_urls,
        lambda b: b[:10].startswith(b"Index Name"),
        ".csv",
        cfg["pause"],
    )


COLS = [
    "date",
    "instr",
    "symbol",
    "expiry",
    "strike",
    "opt",
    "open",
    "high",
    "low",
    "close",
    "settle",
    "volume",
    "oi",
    "und",
    "lot",
]


def nse_date(col) -> pd.Series:
    """Parse NSE's date formats."""
    col = col.str.strip()
    d = pd.to_datetime(col, format="%d-%b-%Y", errors="coerce")
    return d.fillna(pd.to_datetime(col, format="%d-%b-%y", errors="coerce"))


def parse_fo(src) -> pd.DataFrame:
    """NIFTY options and futures rows from one bhavcopy (old or UDiFF format)."""
    df = pd.read_csv(src, low_memory=False)
    df.columns = df.columns.str.strip()
    if "TckrSymb" in df:
        df = df[(df.TckrSymb == "NIFTY") & df.FinInstrmTp.isin(["IDO", "IDF"])]
        out = pd.DataFrame(
            {
                "date": pd.to_datetime(df.TradDt),
                "instr": df.FinInstrmTp.map({"IDO": "OPTIDX", "IDF": "FUTIDX"}),
                "symbol": df.TckrSymb,
                "expiry": pd.to_datetime(df.XpryDt),
                "strike": df.StrkPric,
                "opt": df.OptnTp.fillna("XX"),
                "open": df.OpnPric,
                "high": df.HghPric,
                "low": df.LwPric,
                "close": df.ClsPric,
                "settle": df.SttlmPric,
                "volume": df.TtlTradgVol,
                "oi": df.OpnIntrst,
                "und": df.UndrlygPric,
                "lot": df.NewBrdLotQty,
            }
        )
    else:
        df = df.rename(columns={"OPTIONTYPE": "OPTION_TYP"})
        df = df[
            (df.SYMBOL.str.strip() == "NIFTY")
            & df.INSTRUMENT.str.strip().isin(["OPTIDX", "FUTIDX"])
        ]
        out = pd.DataFrame(
            {
                "date": nse_date(df.TIMESTAMP),
                "instr": df.INSTRUMENT.str.strip(),
                "symbol": "NIFTY",
                "expiry": nse_date(df.EXPIRY_DT),
                "strike": df.STRIKE_PR,
                "opt": df.OPTION_TYP.str.strip(),
                "open": df.OPEN,
                "high": df.HIGH,
                "low": df.LOW,
                "close": df.CLOSE,
                "settle": df.SETTLE_PR,
                "volume": df.CONTRACTS,
                "oi": df.OPEN_INT,
                "und": np.nan,
                "lot": np.nan,
            }
        )
    return out[COLS]


def manual_files() -> list:
    """Files placed by hand in data/raw/manual/."""
    m = RAW / "manual"
    return sorted(list(m.glob("*.zip")) + list(m.glob("*.csv"))) if m.exists() else []


def parse_index(path) -> dict | None:
    """NIFTY 50 and India VIX closes from one index file."""
    df = pd.read_csv(path)
    df.columns = df.columns.str.strip()
    name = df["Index Name"].str.strip().str.lower()
    d = pd.to_datetime(Path(path).stem, format="%Y%m%d")
    nifty = df.loc[name.isin(["nifty 50", "s&p cnx nifty", "cnx nifty"]), "Closing Index Value"]
    vix = df.loc[name == "india vix", "Closing Index Value"]
    return {
        "date": d,
        "close_nse": float(nifty.iloc[0]) if len(nifty) else np.nan,
        "vix": float(vix.iloc[0]) if len(vix) else np.nan,
    }


def build(cfg: dict) -> None:
    """Build data/processed from the raw files."""
    PROC.mkdir(parents=True, exist_ok=True)
    files = sorted((RAW / "fo").glob("*.zip")) + manual_files()
    parts = []
    for i, f in enumerate(files):
        try:
            parts.append(parse_fo(f))
        except Exception as e:
            logger.info(f"  could not parse {f.name}: {e}")
        if i % 500 == 0:
            logger.info(f"  parsed {i}/{len(files)}")
    fo = pd.concat(parts).drop_duplicates(["date", "instr", "expiry", "strike", "opt"])
    fo.to_parquet(PROC / "nifty_fo.parquet", index=False)
    logger.info(f"nifty_fo: {len(fo)} rows, {fo.date.nunique()} days")

    rows = [parse_index(f) for f in sorted((RAW / "index").glob("*.csv"))]
    idx = (
        pd.DataFrame(rows).set_index("date") if rows else pd.DataFrame(columns=["close_nse", "vix"])
    )
    y = (
        pd.read_csv(RAW / "yahoo_nsei.csv", parse_dates=["date"])
        .set_index("date")
        .close.rename("close_yahoo")
    )
    tri = read_tri(cfg)
    idx.index = pd.to_datetime(idx.index)
    ix = pd.concat([idx, y, tri], axis=1).sort_index()
    ix = ix[ix.index >= pd.Timestamp(cfg["start"])]
    ix["close"] = ix.close_nse.fillna(ix.close_yahoo)
    ix["source"] = np.where(
        ix.close_nse.notna(), "nse", np.where(ix.close_yahoo.notna(), "yahoo", "")
    )
    ix.rename_axis("date").to_csv(PROC / "index.csv")
    logger.info(
        f"index: {ix.close.notna().sum()} days with close ({(ix.source == 'nse').sum()} NSE, "
        f"{(ix.source == 'yahoo').sum()} Yahoo), {ix.vix.notna().sum()} with VIX"
    )


def relabels(fo) -> dict:
    """Contracts NSE renamed mid-life, mapped to the label they settled under."""
    opt = fo[fo.instr == "OPTIDX"]
    last = opt.groupby("expiry").date.max()
    real = set(opt.loc[opt.date == opt.expiry, "expiry"].unique())
    m = {}
    for e, d in last.items():
        if e in real or e > fo.date.max():
            continue
        same = [x for x in real if x.to_period("M") == e.to_period("M") and last[x] > d]
        if same:
            m[e] = max(same)
    return m


def relabel(fo) -> pd.DataFrame:
    """Apply `relabels` so each contract keeps one label to settlement."""
    m = relabels(fo)
    if not m:
        return fo
    fo = fo.copy()
    fo["_old"] = fo.expiry.isin(list(m))
    fo["expiry"] = fo.expiry.replace(m)
    fo = fo.sort_values("_old").drop_duplicates(
        ["date", "instr", "expiry", "strike", "opt"], keep="first"
    )
    return (
        fo.drop(columns="_old")
        .sort_values(["date", "instr", "expiry", "strike", "opt"])
        .reset_index(drop=True)
    )


def load() -> tuple:
    """Processed F&O rows and the index frame."""
    fo = relabel(pd.read_parquet(PROC / "nifty_fo.parquet"))
    ix = pd.read_csv(PROC / "index.csv", parse_dates=["date"], index_col="date")
    return fo, ix


def monthly_expiries(fo) -> pd.DataFrame:
    """The monthly expiry of each month: the last expiry that traded."""
    opt = fo[fo.instr == "OPTIDX"]
    real = pd.Series(opt.loc[opt.date == opt.expiry, "expiry"].unique())
    listed = pd.Series(opt.expiry.unique())
    listed = listed[listed <= opt.date.max()]
    r = real.groupby(real.dt.to_period("M")).max()
    lst = listed.groupby(listed.dt.to_period("M")).max()
    e = r.combine_first(lst)
    last = opt.date.max()
    later = opt.loc[opt.date == last, "expiry"]
    if (later.dt.to_period("M") == last.to_period("M")).any() and (later > last).any():
        e = e.drop(last.to_period("M"), errors="ignore")
    return pd.Series(sorted(e.values))


def expiry_day(fo, label) -> pd.Timestamp:
    """Actual last trading day of a contract."""
    f = fo[(fo.instr == "FUTIDX") & (fo.expiry == label)]
    if f.empty:
        f = fo[(fo.instr == "OPTIDX") & (fo.expiry == label)]
    return f.date.max()


def settlement(fo, ix, label, day) -> float:
    """Final settlement price: the expiring future's settle price."""
    f = fo[(fo.instr == "FUTIDX") & (fo.date == day) & (fo.expiry == label)]
    if len(f):
        return float(f.settle.iloc[0])
    return float(ix.close.get(day, np.nan))


def cycles(fo, ix) -> pd.DataFrame:
    """Monthly cycles: entry day, contract, expiry, settlement, period."""
    days = pd.DatetimeIndex(sorted(fo.date.unique()))
    days = days[days.isin(ix.index[ix.close.notna()])]
    exps = monthly_expiries(fo)
    actual = {e: expiry_day(fo, e) for e in exps}
    rows = []
    for prev, nxt in zip(exps[:-1], exps[1:], strict=False):
        after = days[days > actual[prev]]
        if len(after) == 0 or after[0] >= actual[nxt]:
            continue
        rows.append(
            {
                "entry": after[0],
                "expiry": actual[nxt],
                "contract": nxt,
                "settle": settlement(fo, ix, nxt, actual[nxt]),
            }
        )
    c = pd.DataFrame(rows)
    nxt_entry = c.entry.shift(-1)
    last_after = days[days > c.expiry.iloc[-1]]
    nxt_entry.iloc[-1] = last_after[0] if len(last_after) else c.expiry.iloc[-1]
    c["next_entry"] = nxt_entry
    return c


def day(d) -> str:
    """A date as YYYY-MM-DD, or 'n/a'."""
    return "n/a" if pd.isna(d) else f"{d:%Y-%m-%d}"


def check(cfg: dict) -> None:
    """Data checks: coverage, expiries, settlement vs index close."""
    fo, ix = load()
    opt = fo[fo.instr == "OPTIDX"]
    out = ["# Data check\n"]
    cal = calendar(cfg)
    cal = cal[cal <= fo.date.max()]
    have = set(fo.date.unique())
    miss = [d for d in cal if d not in have]
    out.append(
        f"Option data: {fo.date.min():%Y-%m-%d} to {fo.date.max():%Y-%m-%d}, {len(have)} trading "
        "days, "
        f"{len(opt)} NIFTY option rows. Manual files read: {len(manual_files())}.\n"
    )
    out.append(f"## Trading days with no F&O file: {len(miss)}\n")
    out.append(", ".join(f"{d:%Y-%m-%d}" for d in miss) + "\n" if miss else "None.\n")

    exps = monthly_expiries(fo)
    logger.info("Monthly expiry dates found:")
    logger.info(" ".join(f"{d:%Y-%m-%d}" for d in exps))
    wd = pd.Series(exps).dt.day_name().value_counts()
    out.append(
        f"## Monthly expiries: {len(exps)} ({exps.iloc[0]:%Y-%m-%d} to {exps.iloc[-1]:%Y-%m-%d})\n"
    )
    out.append("Weekday counts: " + ", ".join(f"{k} {v}" for k, v in wd.items()) + "\n")
    e = pd.Series(exps)
    for wday in wd.index:
        sub = e[e.dt.day_name() == wday]
        out.append(f"- {wday}: {sub.iloc[0]:%Y-%m-%d} to {sub.iloc[-1]:%Y-%m-%d}")
    out.append("\n" + " ".join(f"{d:%Y-%m-%d}" for d in exps) + "\n")

    moved = [(e, expiry_day(fo, e)) for e in exps]
    moved = [(e, d) for e, d in moved if d != e]
    out.append(
        "Contracts that expired on a different day from their label (holiday shifts): "
        f"{len(moved)}\n"
    )
    out += [f"- label {e:%Y-%m-%d} expired {d:%Y-%m-%d}" for e, d in moved]
    out.append("")
    fut = pd.Series(opt.expiry.unique())
    fut = fut[fut > opt.date.max()]
    mset = set(exps) | set(fut.groupby(fut.dt.to_period("M")).max())
    days_m = opt[opt.expiry.isin(mset)].date.unique()
    nom = sorted(have - set(days_m))
    out.append(f"## Days with no NIFTY monthly options: {len(nom)}\n")
    out.append((", ".join(f"{d:%Y-%m-%d}" for d in nom) if nom else "None.") + "\n")

    zero = (opt.close.isna() | (opt.close <= 0)).mean()
    out.append(f"## Zero or missing option closes: {zero:.1%} of all NIFTY option rows\n")

    c = cycles(fo, ix)
    rows = []
    for _, r in c.iterrows():
        ch = opt[(opt.date == r.entry) & (opt.expiry == r.contract)]
        s0 = ix.close[r.entry]
        rows.append(
            {
                "entry": r.entry,
                "expiry": r.expiry,
                "strikes": ch.strike.nunique(),
                "min_k_pct": ch.strike.min() / s0,
                "max_k_pct": ch.strike.max() / s0,
                "zero_close": (ch.close <= 0).mean(),
                "zero_vol": (ch.volume <= 0).mean(),
                "fsp": r.settle,
                "index_close": ix.close.get(r.expiry, np.nan),
            }
        )
    st = pd.DataFrame(rows)
    st["fsp_diff"] = st.fsp - st.index_close
    st.to_csv("results/entry_day_chain.csv", index=False)
    by = st.groupby(st.entry.dt.year).agg(
        cycles=("strikes", "size"),
        strikes=("strikes", "median"),
        min_k=("min_k_pct", "median"),
        max_k=("max_k_pct", "median"),
        zero_close=("zero_close", "mean"),
        zero_vol=("zero_vol", "mean"),
    )
    out.append(
        f"## Entry-day chains ({len(st)} cycles; per year medians; strikes as share of S0)\n"
    )
    out.append(by.to_markdown(floatfmt=".2f") + "\n")
    out.append(
        "zero_close / zero_vol = share of listed strikes of the target expiry with zero close / "
        "zero contracts traded on the entry day.\n"
    )

    d = st.dropna(subset=["fsp_diff"])
    out.append(
        "## Final settlement price (expiring NIFTY future settle) vs index close on expiry day\n"
    )
    out.append(
        f"{len(d)} expiries; mean abs diff {d.fsp_diff.abs().mean():.2f} pts, max abs "
        f"{d.fsp_diff.abs().max():.2f} pts; {(d.fsp_diff.abs() > 1).sum()} differ by more than 1 "
        "point.\n"
    )
    big = d.loc[d.fsp_diff.abs() > 1, ["expiry", "fsp", "index_close", "fsp_diff"]]
    if len(big):
        out.append(big.to_markdown(index=False, floatfmt=".2f") + "\n")

    ret = ix.close.dropna().pct_change()
    jumps = ret[ret.abs() > 0.05]
    out.append(f"## Days with index move above 5%: {len(jumps)}\n")
    out.append("\n".join(f"- {d:%Y-%m-%d}: {v:+.1%}" for d, v in jumps.items()) + "\n")

    both = ix.dropna(subset=["close_nse", "close_yahoo"])
    rel = (both.close_yahoo / both.close_nse - 1).abs()
    out.append(
        "## Index source\nNIFTY 50 close: NSE ind_close_all archive from "
        f"{day(ix.index[ix.source == 'nse'].min())}, "
        f"Yahoo ^NSEI before ({(ix.source == 'yahoo').sum()} days). On {len(both)} overlap days "
        "Yahoo vs NSE: "
        f"median abs diff {rel.median():.4%}, {(rel > 0.005).sum()} days above 0.5%.\n"
    )
    nod = ix[ix.close.isna() & ix.index.isin(list(have))]
    out.append(
        f"F&O days with no index close: {len(nod)}. India VIX (NSE) available from "
        f"{day(ix.vix.dropna().index.min())} ({ix.vix.notna().sum()} days).\n"
    )
    lots = fo.dropna(subset=["lot"])
    out.append(
        f"Lot size in data: only in UDiFF files ({lots.date.min():%Y-%m-%d} onward); values "
        f"{sorted(lots.lot.unique().astype(int).tolist())}.\n"
        if len(lots)
        else "No lot size in data.\n"
    )
    Path("results").mkdir(exist_ok=True)
    Path("results/data_check.md").write_text("\n".join(out))
    pd.DataFrame({"expiry": exps}).to_csv("results/monthly_expiries.csv", index=False)
    logger.info("wrote results/data_check.md")
