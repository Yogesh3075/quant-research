from __future__ import annotations

import json
import logging
import time
from datetime import date, datetime, timedelta
from pathlib import Path

import requests

logger = logging.getLogger(__name__)

PAGE = "https://www.niftyindices.com/reports/historical-data"
URL = "https://www.niftyindices.com/BackPage/getTotalReturnIndexString"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/130.0 Safari/537.36"
    ),
    "Content-Type": "application/json; charset=UTF-8",
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Referer": PAGE,
    "Origin": "https://www.niftyindices.com",
}


def year_chunks(start: date, end: date) -> list:
    """Split [start, end] into one-year date ranges (the site's request limit)."""
    # the site refuses ranges longer than 365 days, so go 1 Apr to 31 Mar
    chunks = []
    while start <= end:
        stop = min(start.replace(year=start.year + 1) - timedelta(days=1), end)
        chunks.append((start, stop))
        start = stop + timedelta(days=1)
    return chunks


def fetch_chunk(
    session: requests.Session, name: str, start: date, end: date, retries: int, pause: float
) -> list | None:
    """Daily TRI rows for one index and date range, with retries; None on failure."""
    d1, d2 = start.strftime("%d-%b-%Y"), end.strftime("%d-%b-%Y")
    # the page sends a JSON body whose 'cinfo' field is itself a single-quoted string
    cinfo = f"{{'name':'{name}','startDate':'{d1}','endDate':'{d2}','indexName':'{name}'}}"
    for attempt in range(1, retries + 1):
        try:
            r = session.post(URL, data=json.dumps({"cinfo": cinfo}), headers=HEADERS, timeout=60)
            if r.status_code == 200 and isinstance(r.json(), list) and r.json():
                return r.text
            logger.info(
                f"  {name} {d1}..{d2}: status {r.status_code}, body starts {r.text[:80]!r} (try "
                f"{attempt})"
            )
        except (requests.RequestException, ValueError) as e:
            logger.info(f"  {name} {d1}..{d2}: {e} (try {attempt})")
        time.sleep(pause)
    return None


def download_all(cfg: dict) -> None:
    """Download every configured index into data/raw, one JSON file per year."""
    raw = Path(cfg["paths"]["raw"])
    raw.mkdir(parents=True, exist_ok=True)
    start, end = cfg["start_date"], date.today()
    chunks = year_chunks(start, end)
    pause, retries = cfg["download"]["pause_seconds"], cfg["download"]["retries"]

    session = requests.Session()
    session.get(
        PAGE, headers={"User-Agent": HEADERS["User-Agent"]}, timeout=60
    )  # picks up the session cookie

    failed = {}
    for key, name in cfg["indices"].items():
        for old in raw.glob(f"{key}_*.json"):
            old.unlink()
        logger.info(f"{key}: {name}, {len(chunks)} chunks")
        ok, rows, dates = 0, 0, []
        failed[key] = []
        for a, b in chunks:
            text = fetch_chunk(session, name, a, b, retries, pause)
            time.sleep(pause)
            if text is None:
                failed[key].append(f"{a}..{b}")
                continue
            (raw / f"{key}_{a}_{b}.json").write_text(text)
            data = json.loads(text)
            ok, rows = ok + 1, rows + len(data)
            dates += [d["Date"] for d in data]
        dates = sorted(datetime.strptime(d, "%d %b %Y").date() for d in dates)
        first, last = (dates[0], dates[-1]) if dates else ("-", "-")
        logger.info(f"  {key}: {ok} ok, {len(failed[key])} failed, {rows} rows, {first} to {last}")

    bad = {k: v for k, v in failed.items() if v}
    if bad:
        logger.warning("Failed chunks: %s", bad)
        raise SystemExit(
            "Some requests failed after retries. Re-run download; if it keeps failing the site may "
            "be "
            "blocking requests, so download the CSVs by hand."
        )
