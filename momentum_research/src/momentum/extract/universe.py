from __future__ import annotations

import logging
import re
import time
from datetime import date
from pathlib import Path

import pandas as pd
import requests

logger = logging.getLogger(__name__)


def make_session(cfg: dict) -> requests.Session:
    """An HTTP session with the configured headers."""
    s = requests.Session()
    s.headers["User-Agent"] = cfg["http"]["user_agent"]
    return s


def fetch(sess, url: str, cfg: dict) -> requests.Response:
    """GET with a pause and retries; raises on failure."""
    time.sleep(cfg["http"]["pause_seconds"])
    r = sess.get(url, timeout=cfg["http"]["timeout_seconds"])
    r.raise_for_status()
    return r.content


def download_current_list(cfg: dict, sess) -> Path:
    """Today's Nifty 500 list from NSE (once a day)."""
    out = Path(cfg["paths"]["raw_universe"]) / f"ind_nifty500list_{date.today():%Y-%m-%d}.csv"
    if out.exists():
        logger.info(f"current list already downloaded today: {out}")
        return out
    try:
        body = fetch(sess, cfg["urls"]["current_list"], cfg)
    except requests.RequestException as e:
        raise SystemExit(
            f"Could not download the Nifty 500 list ({e}). "
            f"Place ind_nifty500list.csv by hand in {cfg['paths']['manual']}/ and rerun."
        ) from e
    if b"Symbol" not in body[:500]:
        raise SystemExit(
            "Downloaded Nifty 500 list does not look like a CSV. "
            f"Place ind_nifty500list.csv by hand in {cfg['paths']['manual']}/."
        )
    out.write_bytes(body)
    logger.info(f"saved {out}")
    return out


def date_from_title(title: str):
    """Effective date in a notice title ('w.e.f. ...')."""
    # "Replacements in indices w.e.f. July 31, 2026" -> 2026-07-31
    m = re.search(r"w\.?\s*e\.?\s*f\.?\s*(.*)$", title, re.IGNORECASE)
    if not m:
        return None
    text = re.sub(r"[^A-Za-z0-9 ]", " ", m.group(1))
    text = re.sub(r"(\d)(st|nd|rd|th)\b", r"\1", text)
    text = re.sub(r"\s+", " ", text).strip()
    d = pd.to_datetime(text, errors="coerce", format="mixed")
    return None if pd.isna(d) else d.date()


def list_notices(cfg: dict, html: str) -> pd.DataFrame:
    """Index-change notices listed on the niftyindices.com page."""
    items = re.findall(
        r'data-date="([^"]+)".*?href=[\'"]([^\'"]+)[\'"][^>]*>(.*?)</a>',
        html,
        re.DOTALL,
    )
    df = pd.DataFrame(items, columns=["announce_date", "href", "title"])
    df["title"] = (
        df["title"].str.replace(r"\s+", " ", regex=True).str.replace("&amp;", "&").str.strip()
    )
    df["announce_date"] = pd.to_datetime(df["announce_date"], format="%b %d, %Y").dt.date
    df["title_effective_date"] = df["title"].map(date_from_title)
    keep = pd.to_datetime(df["announce_date"]) >= pd.Timestamp(
        cfg["universe"]["notice_listing_from"]
    )
    keep &= ~df["title"].str.contains(cfg["universe"]["title_skip_regex"], case=False, regex=True)
    keep &= df["href"].str.lower().str.endswith(".pdf")
    return df[keep].reset_index(drop=True)


def notice_file_name(row) -> str:
    """File name for a saved notice PDF."""
    eff = row["title_effective_date"] or "effNA"
    return f"{eff}_ann{row['announce_date']}_{Path(row['href']).name}"


def download_notices(cfg: dict, sess) -> None:
    """Download every index-change notice PDF."""
    raw = Path(cfg["paths"]["raw_universe"])
    folder = Path(cfg["paths"]["raw_notices"])
    listing = raw / f"press_release_listing_{date.today():%Y-%m-%d}.html"
    if not listing.exists():
        listing.write_bytes(fetch(sess, cfg["urls"]["press_listing"], cfg))
        logger.info(f"saved {listing}")
    notices = list_notices(cfg, listing.read_text(encoding="utf-8", errors="ignore"))
    notices["file"] = notices.apply(notice_file_name, axis=1)
    notices.to_csv(folder / "notice_index.csv", index=False)
    logger.info(f"{len(notices)} candidate notices since {cfg['universe']['notice_listing_from']}")

    failed = []
    for i, row in notices.iterrows():
        out = folder / row["file"]
        if out.exists():
            continue
        try:
            out.write_bytes(fetch(sess, cfg["urls"]["press_base"] + row["href"], cfg))
        except requests.RequestException as e:
            failed.append((row["href"], str(e)))
        if i % 25 == 0:
            logger.info(f"  {i + 1}/{len(notices)}")
    for href, err in failed:
        logger.info(f"  failed: {href} ({err})")
    logger.info(f"notices downloaded, {len(failed)} failed")


def download_nse_lists(cfg: dict, sess) -> None:
    """Download NSE's symbol-change, name-change and delisted lists."""
    raw = Path(cfg["paths"]["raw_universe"])
    for key in ["symbol_changes", "name_changes", "equity_list", "delisted"]:
        url = cfg["urls"][key]
        out = raw / f"{Path(url).stem}_{date.today():%Y-%m-%d}.csv"
        if out.exists():
            continue
        try:
            out.write_bytes(fetch(sess, url, cfg))
            logger.info(f"saved {out}")
        except requests.RequestException as e:
            logger.info(
                f"could not download {url} ({e}); place {Path(url).name} in "
                f"{cfg['paths']['manual']}/"
            )


def run_download(cfg: dict) -> None:
    """Download today's list, the NSE lists and the notices."""
    sess = make_session(cfg)
    download_current_list(cfg, sess)
    download_nse_lists(cfg, sess)
    download_notices(cfg, sess)


def yahoo_range(symbol: str, cfg: dict) -> tuple:
    """First and last date Yahoo has for a symbol (coverage check only)."""
    import yfinance as yf

    logging.getLogger("yfinance").setLevel(
        logging.CRITICAL
    )  # a missing symbol is an expected result here
    time.sleep(cfg["coverage"]["yahoo_pause_seconds"])
    try:
        h = yf.Ticker(symbol + cfg["coverage"]["yahoo_suffix"]).history(
            start=cfg["coverage"]["yahoo_start"], interval="1mo", auto_adjust=False
        )
    except Exception:
        return None, None
    h = h.dropna(subset=["Close"])
    if h.empty:
        return None, None
    return h.index.min().date(), h.index.max().date()


def bhavcopy_symbols(day: pd.Timestamp, cfg: dict, sess):
    """Symbols in one day's bhavcopy (coverage check only)."""
    # all symbols traded on NSE that day (EQ-type series), or None if no file (holiday)
    folder = Path(cfg["paths"]["raw_universe"]) / "bhavcopy_samples"
    folder.mkdir(exist_ok=True)
    out = folder / f"bhav_{day:%Y-%m-%d}.csv"
    if not out.exists():
        if day < pd.Timestamp(cfg["coverage"]["udiff_from"]):
            url = cfg["urls"]["bhavcopy_old"].format(
                yyyy=day.year, mon=day.strftime("%b").upper(), dd=day.strftime("%d")
            )
        else:
            url = cfg["urls"]["bhavcopy_udiff"].format(date=day.strftime("%Y%m%d"))
        try:
            body = fetch(sess, url, cfg)
        except requests.RequestException:
            return None
        if not body.startswith(b"PK"):
            return None
        out.write_bytes(body)
    df = pd.read_csv(out, compression="zip")
    if "TckrSymb" in df:
        df = df.rename(columns={"TckrSymb": "SYMBOL", "SctySrs": "SERIES"})
    return set(df["SYMBOL"].astype(str).str.strip())


def sample_day_symbols(month_end, cfg: dict, sess, cache):
    """Bhavcopy symbols on the last trading day on or before a month-end."""
    # step back from the month-end to the last trading day that has a bhavcopy
    for back in range(cfg["coverage"]["max_days_back"]):
        day = month_end - pd.Timedelta(days=back)
        if day.weekday() >= 5:
            continue
        if day not in cache:
            cache[day] = bhavcopy_symbols(day, cfg, sess)
        if cache[day] is not None:
            return day, cache[day]
    return None, None


def run_coverage(cfg: dict) -> pd.DataFrame:
    """Phase 0 check: which members Yahoo and NSE cover each month."""
    out = Path(cfg["paths"]["processed_universe"])
    path = out / "monthly_members.csv"
    if not path.exists():
        raise SystemExit(f"Missing {path}. Run: python scripts/run.py membership")
    monthly = pd.read_csv(path, parse_dates=["date"])
    today = pd.Timestamp.today().normalize()
    sess, bhav_cache, rows = make_session(cfg), {}, []
    stocks = monthly.groupby("stock_id")
    logger.info(f"checking price coverage for {len(stocks)} stocks")
    for n, (key, g) in enumerate(stocks):
        last = g.sort_values("date").iloc[-1]
        member_symbol = last["symbol"]
        row = dict(
            stock_id=key,
            isin=last["isin"],
            member_symbol=member_symbol,
            first_member_month=g["date"].min().date(),
            last_member_month=last["date"].date(),
            still_member=bool(last["date"] >= today - pd.offsets.MonthEnd(1)),
        )
        if key.startswith(("NAME:", "DUMMY")):
            row.update(
                yahoo_symbol="",
                yahoo_first=None,
                yahoo_last=None,
                nse_date=None,
                nse_found=False,
            )
            rows.append(row)
            continue
        tried = [member_symbol] + ([key] if key != member_symbol else [])
        first = last_ = used = None
        for sym in tried:
            first, last_ = yahoo_range(sym, cfg)
            if first:
                used = sym
                break
        day, symbols = sample_day_symbols(last["date"], cfg, sess, bhav_cache)
        row.update(
            yahoo_symbol=used or "",
            yahoo_first=first,
            yahoo_last=last_,
            nse_date=day.date() if day is not None else None,
            nse_found=bool(symbols and member_symbol in symbols),
        )
        rows.append(row)
        if n % 50 == 0:
            logger.info(f"  {n + 1}/{len(stocks)}")
    cov = pd.DataFrame(rows)
    cov.to_csv(out / "price_coverage.csv", index=False)
    logger.info(f"saved {out / 'price_coverage.csv'}")
    return cov
