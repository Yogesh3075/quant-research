from __future__ import annotations

import io
import json
import logging
import time
import zipfile
from datetime import date
from pathlib import Path

import pandas as pd
import requests

from momentum.extract.universe import fetch, make_session

logger = logging.getLogger(__name__)


def log_rows(path: Path, rows: list) -> None:
    """Append rows to a CSV download log."""
    if rows:
        pd.DataFrame(rows).to_csv(path, mode="a", header=not path.exists(), index=False)


def parse_history(text: str) -> list:
    """Symbol history 'A; B from 2019-01-01' as (symbol, start, end) tuples."""
    # "A; B from 2016-03-18" -> [(A, None, 2016-03-18), (B, 2016-03-18, None)]
    parts = []
    for p in str(text).split("; "):
        sym, _, since = p.partition(" from ")
        parts.append([sym.strip(), pd.Timestamp(since) if since else None, None])
    for a, b in zip(parts, parts[1:], strict=False):
        a[2] = b[1]
    return [tuple(p) for p in parts]


def load_securities(cfg: dict) -> pd.DataFrame:
    """Securities to price: every stock that was ever a member."""
    spells = pd.read_csv(
        Path(cfg["paths"]["processed_universe"]) / "membership.csv",
        parse_dates=["start_date", "end_date"],
    )
    spells = spells[spells["eligible"]]
    p = cfg["prices"]
    first, today = pd.Timestamp(p["start"]), pd.Timestamp.today().normalize()
    rows = []
    for key, g in spells.groupby("stock_id"):
        start = g["start_date"].min() if g["start_date"].notna().all() else first
        end = g["end_date"].max() if g["end_date"].notna().all() else today
        rows.append(
            dict(
                stock_id=key,
                isin=g["isin"].dropna().iloc[0] if g["isin"].notna().any() else "",
                history=parse_history(g["symbol_history"].iloc[0]),
                start=max(first, start - pd.DateOffset(months=p["lookback_months"])),
                end=min(today, end + pd.DateOffset(months=p["after_months"])),
            )
        )
    return pd.DataFrame(rows)


def securities_file(cfg: dict) -> Path:
    """Path of the processed securities list."""
    return Path(cfg["paths"]["processed_prices"]) / "securities.csv"


def save_securities(cfg: dict, sec: pd.DataFrame) -> None:
    """Write the securities list with its symbol histories."""
    out = sec.copy()
    out["history"] = out["history"].map(
        lambda h: "; ".join(
            f"{s}|{a.date() if a is not None else ''}|{b.date() if b is not None else ''}"
            for s, a, b in h
        )
    )
    securities_file(cfg).parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(securities_file(cfg), index=False)


def read_securities(cfg: dict) -> pd.DataFrame:
    """The processed securities list, histories parsed."""
    path = securities_file(cfg)
    if not path.exists():
        raise SystemExit(f"Missing {path}. Run: python scripts/run.py prices-download")
    sec = pd.read_csv(path, parse_dates=["start", "end"], keep_default_na=False)

    def to_ts(x):
        return pd.Timestamp(x) if x else None

    sec["history"] = sec["history"].map(
        lambda t: [(s, to_ts(a), to_ts(b)) for s, a, b in (p.split("|") for p in t.split("; "))]
    )
    return sec


def download_index(cfg: dict, sess) -> None:
    """Download benchmark index prices and TRI from niftyindices.com."""
    p, folder = cfg["prices"], Path(cfg["paths"]["raw_prices"]) / "index"
    folder.mkdir(parents=True, exist_ok=True)
    head = {
        "Content-Type": "application/json; charset=utf-8",
        "X-Requested-With": "XMLHttpRequest",
        "Referer": cfg["urls"]["index_referer"],
    }
    today = pd.Timestamp.today().normalize()
    for name in p["indices"]:
        for kind, url in [
            ("tri", cfg["urls"]["index_tri"]),
            ("price", cfg["urls"]["index_price"]),
        ]:
            start = pd.Timestamp(p["start"])
            while start <= today:
                end = min(start + pd.Timedelta(days=p["index_chunk_days"] - 1), today)
                out = folder / f"{name.replace(' ', '_')}_{kind}_{start:%Y%m%d}_{end:%Y%m%d}.json"
                if not out.exists() or end >= today - pd.Timedelta(days=7):
                    info = {
                        "name": name,
                        "startDate": f"{start:%d-%b-%Y}",
                        "endDate": f"{end:%d-%b-%Y}",
                        "indexName": name,
                    }
                    time.sleep(cfg["http"]["pause_seconds"])
                    r = sess.post(
                        url,
                        json={"cinfo": json.dumps(info).replace('"', "'")},
                        headers=head,
                        timeout=cfg["http"]["timeout_seconds"],
                    )
                    r.raise_for_status()
                    out.write_bytes(r.content)
                start = end + pd.Timedelta(days=1)
        logger.info(f"index {name} saved")


def read_index(cfg: dict, name: str, kind: str) -> pd.Series:
    """Daily close of one index ('price' or 'tri')."""
    folder = Path(cfg["paths"]["raw_prices"]) / "index"
    rows = []
    for f in sorted(folder.glob(f"{name.replace(' ', '_')}_{kind}_*.json")):
        rows += json.loads(f.read_text() or "[]")
    if not rows:
        raise SystemExit(
            f"No {name} {kind} files in {folder}. Run: python scripts/run.py prices-download"
        )
    df = pd.DataFrame(rows)
    date_col = "Date" if "Date" in df else "HistoricalDate"
    val_col = "TotalReturnsIndex" if kind == "tri" else "CLOSE"
    s = pd.Series(
        pd.to_numeric(df[val_col].astype(str).str.replace(",", ""), errors="coerce").values,
        index=pd.to_datetime(df[date_col], format="%d %b %Y"),
    )
    return s[~s.index.duplicated()].sort_index().dropna()


def trading_days(cfg: dict) -> pd.DatetimeIndex:
    """NSE trading days, from the calendar index."""
    return read_index(cfg, cfg["prices"]["calendar_index"], "price").index


def download_corp_actions(cfg: dict, sec: pd.DataFrame) -> None:
    """Download NSE corporate-action records for every symbol."""
    folder = Path(cfg["paths"]["raw_prices"]) / "nse_corp_actions"
    folder.mkdir(parents=True, exist_ok=True)
    sess = make_session(cfg)
    sess.headers.update({"Accept": "*/*", "Referer": cfg["urls"]["nse_ca_referer"]})
    today, log = date.today(), []
    symbols = sorted({s for h in sec["history"] for s, _, _ in h})
    logger.info(f"corporate actions for {len(symbols)} symbols")
    for i, sym in enumerate(symbols):
        out = folder / f"ca_{sym.replace('&', '_and_')}.json"
        url = cfg["urls"]["nse_ca"].format(
            symbol=requests.utils.quote(sym),
            start=cfg["prices"]["ca_from"],
            end=f"{today:%d-%m-%Y}",
        )
        status = "ok"
        for attempt in range(cfg["http"]["retries"]):
            try:
                body = fetch(sess, url, cfg)
                json.loads(body)
                out.write_bytes(body)
                break
            except (requests.RequestException, ValueError) as e:
                status = f"failed: {e}"
                time.sleep(cfg["http"]["pause_seconds"] * (attempt + 2))
        else:
            log.append(dict(symbol=sym, status=status))
            continue
        log.append(dict(symbol=sym, status="ok"))
        if i % 100 == 0:
            logger.info(f"  {i + 1}/{len(symbols)}")
    pd.DataFrame(log).to_csv(folder / "download_log.csv", index=False)
    logger.info(
        f"corporate actions: {sum(r['status'] == 'ok' for r in log)} ok, "
        f"{sum(r['status'] != 'ok' for r in log)} failed"
    )


def read_corp_actions(cfg: dict, symbols: list) -> pd.DataFrame:
    """Corporate-action records for the given symbols."""
    folder = Path(cfg["paths"]["raw_prices"]) / "nse_corp_actions"
    rows = []
    for sym in symbols:
        f = folder / f"ca_{sym.replace('&', '_and_')}.json"
        if f.exists():
            rows += json.loads(f.read_text() or "[]")
    df = pd.DataFrame(
        rows,
        columns=["symbol", "series", "isin", "subject", "exDate", "faceVal", "comp"],
    )
    df["ex_date"] = pd.to_datetime(df["exDate"], format="%d-%b-%Y", errors="coerce")
    return df.drop_duplicates(["symbol", "subject", "exDate"])


def assign_isins(cfg: dict, sec: pd.DataFrame) -> pd.DataFrame:
    """ISIN from today's NSE list where known, else from corporate actions."""
    # Phase 0 ISIN (today's NSE list) where known, else the ISIN NSE gives in the
    # corporate-action records
    for i, r in sec.iterrows():
        if not r["isin"]:
            ca = read_corp_actions(cfg, [s for s, _, _ in r["history"]])
            found = ca["isin"].dropna()
            found = found[found.str.startswith("IN")]
            sec.at[i, "isin"] = found.iloc[0] if len(found) else ""
    sec["file_id"] = [r["isin"] or r["stock_id"].replace(":", "_") for _, r in sec.iterrows()]
    dup = sec["file_id"].duplicated(keep=False)
    sec.loc[dup, "file_id"] = sec.loc[dup, "file_id"] + "_" + sec.loc[dup, "stock_id"]
    return sec


def yahoo_history(sym: str, start, end, cfg: dict):
    """Daily Yahoo history for one symbol, adjusted and raw."""
    import yfinance as yf

    logging.getLogger("yfinance").setLevel(logging.CRITICAL)
    for attempt in range(cfg["http"]["retries"]):
        time.sleep(cfg["prices"]["yahoo_pause_seconds"])
        try:
            h = yf.Ticker(sym + cfg["coverage"]["yahoo_suffix"]).history(
                start=f"{start:%Y-%m-%d}",
                end=f"{end + pd.Timedelta(days=1):%Y-%m-%d}",
                auto_adjust=False,
                actions=True,
            )
            return h, "ok" if len(h) else "empty"
        except Exception as e:
            err = str(e)
            time.sleep(cfg["prices"]["yahoo_pause_seconds"] * (attempt + 2))
    return pd.DataFrame(), f"failed: {err[:100]}"


def download_yahoo(cfg: dict, sec: pd.DataFrame) -> None:
    """Download Yahoo prices for every security, symbol by symbol through time."""
    folder = Path(cfg["paths"]["raw_prices"]) / "yahoo"
    folder.mkdir(parents=True, exist_ok=True)
    log = []
    logger.info(f"yahoo for {len(sec)} securities")
    for i, r in sec.iterrows():
        frames = {}
        for sym, _, _ in r["history"]:
            h, status = yahoo_history(sym, r["start"], r["end"], cfg)
            log.append(dict(file_id=r["file_id"], symbol=sym, status=status, rows=len(h)))
            if len(h):
                h.index = h.index.tz_localize(None).normalize()
                frames[sym] = h
        if not frames:
            continue
        # each date from the symbol in force that day; if Yahoo has nothing under that
        # symbol, the latest symbol that has it
        dates = sorted(set().union(*[f.index for f in frames.values()]))
        out = []
        for d in dates:
            in_force = [
                s for s, a, b in r["history"] if (a is None or d >= a) and (b is None or d < b)
            ]
            order = in_force + [s for s, _, _ in reversed(r["history"]) if s not in in_force]
            sym = next(s for s in order if s in frames and d in frames[s].index)
            row = frames[sym].loc[d]
            out.append(
                dict(
                    date=d,
                    open=row["Open"],
                    high=row["High"],
                    low=row["Low"],
                    close=row["Close"],
                    adj_close=row["Adj Close"],
                    volume=row["Volume"],
                    dividends=row.get("Dividends", 0.0),
                    stock_splits=row.get("Stock Splits", 0.0),
                    yahoo_symbol=sym,
                )
            )
        pd.DataFrame(out).to_parquet(folder / f"{r['file_id']}.parquet", index=False)
        if i % 100 == 0:
            logger.info(f"  {i + 1}/{len(sec)}")
    log_rows(folder / "download_log.csv", [dict(row, run=f"{date.today()}") for row in log])
    got = {row["file_id"] for row in log if row["rows"]}
    logger.info(f"yahoo: data for {len(got)} of {len(sec)} securities")


def bhavcopy_url(day: pd.Timestamp, cfg: dict) -> str:
    """NSE bhavcopy URL for a day (old format before UDiFF)."""
    if day < pd.Timestamp(cfg["coverage"]["udiff_from"]):
        return cfg["urls"]["bhavcopy_old"].format(
            yyyy=day.year, mon=day.strftime("%b").upper(), dd=day.strftime("%d")
        )
    return cfg["urls"]["bhavcopy_udiff"].format(date=day.strftime("%Y%m%d"))


def download_bhavcopy(cfg: dict, only_missing: bool = False) -> None:
    """Download NSE's daily equity bhavcopy files."""
    folder = Path(cfg["paths"]["raw_prices"]) / "nse_bhavcopy"
    folder.mkdir(parents=True, exist_ok=True)
    sess, log, misses = make_session(cfg), [], 0
    days = [d for d in trading_days(cfg) if d >= pd.Timestamp(cfg["prices"]["start"])]
    logger.info(f"bhavcopy: {len(days)} index trading days")
    for i, day in enumerate(days):
        out = folder / f"bhav_{day:%Y-%m-%d}.zip"
        if only_missing and out.exists():
            continue
        url = bhavcopy_url(day, cfg)
        status = "ok"
        for attempt in range(cfg["http"]["retries"]):
            try:
                body = fetch(sess, url, cfg)
                status = "ok" if body.startswith(b"PK") else "not a zip"
                break
            except requests.RequestException as e:
                status = f"failed: {e}"[:120]
                time.sleep(cfg["http"]["pause_seconds"] * (attempt + 2))
        if status == "ok":
            out.write_bytes(body)
            misses = 0
        else:
            misses += 1
        log.append(
            dict(
                date=day.date(),
                url=url,
                status=status,
                bytes=len(body) if status == "ok" else 0,
            )
        )
        if misses >= cfg["prices"]["max_consecutive_misses"]:
            log_rows(folder / "download_log.csv", log)
            raise SystemExit(
                f"NSE bhavcopy: {misses} failures in a row (last {url}: {status}). NSE may be "
                "blocking; stopping."
            )
        if i % 200 == 0:
            logger.info(f"  {i + 1}/{len(days)} {day:%Y-%m-%d}")
            log_rows(folder / "download_log.csv", log)
            log = []
    log_rows(folder / "download_log.csv", log)
    logger.info("bhavcopy download done")


def read_bhavcopy(path: Path) -> pd.DataFrame:
    """One bhavcopy zip as a frame (both file formats)."""
    with zipfile.ZipFile(path) as z:
        df = pd.read_csv(io.BytesIO(z.read(z.namelist()[0])))
    df.columns = [c.strip() for c in df.columns]
    if "TckrSymb" in df:
        df = df.rename(
            columns={
                "TckrSymb": "symbol",
                "SctySrs": "series",
                "OpnPric": "open",
                "HghPric": "high",
                "LwPric": "low",
                "ClsPric": "close",
                "PrvsClsgPric": "prev_close",
                "TtlTradgVol": "qty",
                "TtlTrfVal": "value",
                "TtlNbOfTxsExctd": "trades",
                "ISIN": "isin",
            }
        )
    else:
        df = df.rename(
            columns={
                "SYMBOL": "symbol",
                "SERIES": "series",
                "OPEN": "open",
                "HIGH": "high",
                "LOW": "low",
                "CLOSE": "close",
                "PREVCLOSE": "prev_close",
                "TOTTRDQTY": "qty",
                "TOTTRDVAL": "value",
                "TOTALTRADES": "trades",
                "ISIN": "isin",
            }
        )
    for c in ["trades", "isin"]:
        if c not in df:
            df[c] = None
    df["symbol"] = df["symbol"].astype(str).str.strip()
    df["series"] = df["series"].astype(str).str.strip()
    return df[
        [
            "symbol",
            "series",
            "open",
            "high",
            "low",
            "close",
            "prev_close",
            "qty",
            "value",
            "trades",
            "isin",
        ]
    ]


def extract_nse(cfg: dict, sec: pd.DataFrame, out_name="nse") -> None:
    """Per-security NSE close and volume series from the bhavcopies."""
    # one parquet per security: the rows for its symbol in force each day, series EQ (or BE/BZ
    # if it moved series)
    folder = Path(cfg["paths"]["raw_prices"]) / "nse_bhavcopy"
    out_dir = Path(cfg["paths"]["raw_prices"]) / out_name
    out_dir.mkdir(parents=True, exist_ok=True)
    series = cfg["prices"]["nse_series"]
    wanted = {}
    for _, r in sec.iterrows():
        for sym, a, b in r["history"]:
            wanted.setdefault(sym, []).append(
                (
                    r["file_id"],
                    max(r["start"], a) if a else r["start"],
                    min(r["end"], b) if b else r["end"],
                )
            )
    files = sorted(folder.glob("bhav_*.zip"))
    logger.info(f"extracting {len(wanted)} symbols from {len(files)} bhavcopy files")
    rows = []
    for n, f in enumerate(files):
        day = pd.Timestamp(f.stem[5:])
        df = read_bhavcopy(f)
        df = df[df["symbol"].isin(wanted.keys()) & df["series"].isin(series)]
        for _, x in df.iterrows():
            for file_id, a, b in wanted[x["symbol"]]:
                if a <= day <= b:
                    rows.append(dict(file_id=file_id, date=day, **x.to_dict()))
        if n % 500 == 0:
            logger.info(f"  {n + 1}/{len(files)}")
    allrows = pd.DataFrame(rows)
    # one row per day: prefer EQ, then the other series in config order
    allrows["rank"] = allrows["series"].map({s: i for i, s in enumerate(series)})
    allrows = (
        allrows.sort_values(["file_id", "date", "rank"])
        .drop_duplicates(["file_id", "date"])
        .drop(columns="rank")
    )
    for file_id, g in allrows.groupby("file_id"):
        g.drop(columns="file_id").to_parquet(out_dir / f"{file_id}.parquet", index=False)
    logger.info(f"nse: {allrows['file_id'].nunique()} securities written")


def run_download(
    cfg: dict, only_missing=False, parts=("index", "ca", "yahoo", "bhavcopy", "extract")
) -> None:
    """Download securities, indices, corporate actions, Yahoo and NSE prices."""
    sec = load_securities(cfg)
    if "index" in parts:
        download_index(cfg, make_session(cfg))
    if "ca" in parts:
        download_corp_actions(cfg, sec)
    sec = assign_isins(cfg, sec)
    save_securities(cfg, sec)
    if "yahoo" in parts:
        download_yahoo(cfg, sec)
    if "bhavcopy" in parts:
        download_bhavcopy(cfg, only_missing)
    if "extract" in parts:
        extract_nse(cfg, sec)
