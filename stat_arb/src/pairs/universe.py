"""Point-in-time Nifty 500 universe, prices and F&O eligibility for the pairs rebuild.

`load()` fills the module-level frames below. They are module globals (not arguments) because
`multiprocessing.Pool` runs `load` once per worker as its initializer, and the pair search then
reads them; other modules access them as `universe.PRICES` etc. at call time.
"""

from __future__ import annotations

import io
import json
import logging
import os
import shutil
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
RESULTS_DIR = PROJECT_ROOT / "results"
MOMENTUM_DIR = Path(os.environ.get("MOMENTUM_DIR", PROJECT_ROOT.parent / "momentum_research"))

FIRST_FORMATION = pd.Timestamp("2010-12-01")
FORMATION_MONTHS = (6, 12)  # formation dates are the last trading days of June and December
NSE_ARCHIVE = "https://nsearchives.nseindia.com/content"

PRICES: pd.DataFrame | None = None
TRADED_VALUE: pd.DataFrame | None = None
MEMBERSHIP: pd.DataFrame | None = None
FO_MEMBERS: pd.DataFrame | None = None


def fo_symbols(day: pd.Timestamp) -> set | None:
    """Stock-futures symbols in NSE's F&O bhavcopy for one day (None if NSE has no file)."""
    old = (
        f"{NSE_ARCHIVE}/historical/DERIVATIVES/{day:%Y}/"
        f"{day.strftime('%b').upper()}/fo{day.strftime('%d%b%Y').upper()}bhav.csv.zip"
    )
    new = f"{NSE_ARCHIVE}/fo/BhavCopy_NSE_FO_0_0_0_{day:%Y%m%d}_F_0000.csv.zip"
    for url in (old, new):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            z = zipfile.ZipFile(io.BytesIO(urllib.request.urlopen(req, timeout=60).read()))
            df = pd.read_csv(z.open(z.namelist()[0]))
        except (urllib.error.URLError, zipfile.BadZipFile, OSError, pd.errors.ParserError):
            continue  # the old and new archive formats cover different dates; try the other
        if "INSTRUMENT" in df:
            return set(df.loc[df.INSTRUMENT.str.strip() == "FUTSTK", "SYMBOL"].str.strip())
        return set(df.loc[df.FinInstrmTp == "STF", "TckrSymb"].str.strip())
    return None


def symbol_map(securities: pd.DataFrame, day: pd.Timestamp) -> dict:
    """NSE symbol -> price column (file_id) on a given day, from the symbol history."""
    day, out = f"{day:%Y-%m-%d}", {}
    for fid, hist in zip(securities.file_id, securities.history, strict=True):
        for seg in str(hist).split("; "):
            sym, start, end = (seg.split("|") + ["", ""])[:3]
            if (not start or start <= day) and (not end or day < end):
                out[sym] = fid
    return out


def build_data() -> None:
    """Copy inputs from the momentum project and build the point-in-time F&O list."""
    DATA_DIR.mkdir(exist_ok=True)
    src = MOMENTUM_DIR / "Data" / "processed"
    if not src.exists():
        raise FileNotFoundError(
            f"{src} not found: build momentum_research first or set MOMENTUM_DIR"
        )
    for f in [
        "prices/adj_close.parquet",
        "prices/traded_value.parquet",
        "prices/securities.csv",
        "universe/membership.csv",
        "universe/industry.csv",
    ]:
        shutil.copy(src / f, DATA_DIR / Path(f).name)

    rows = []
    for f in sorted((MOMENTUM_DIR / "Data/raw/prices/index").glob("NIFTY_500_tri_*.json")):
        rows += json.loads(f.read_text() or "[]")
    tri = pd.DataFrame(rows)
    tri = pd.Series(
        pd.to_numeric(tri.TotalReturnsIndex, errors="coerce").values,
        pd.to_datetime(tri.Date, format="%d %b %Y"),
        name="nifty500_tri",
    )
    tri = tri[~tri.index.duplicated()].sort_index().dropna()
    tri.to_csv(DATA_DIR / "nifty500_tri.csv")

    prices = pd.read_parquet(DATA_DIR / "adj_close.parquet")
    securities = pd.read_csv(DATA_DIR / "securities.csv")
    out = []
    for day in formation_dates(prices.index):
        symbols = fo_symbols(day)
        if symbols is None:
            logger.warning("F&O bhavcopy missing for %s", f"{day:%Y-%m-%d}")
            continue
        mapping = symbol_map(securities, day)
        out += [{"date": day, "symbol": s, "file_id": mapping.get(s)} for s in sorted(symbols)]
        logger.info(
            "%s: %d stock futures, %d mapped",
            f"{day:%Y-%m-%d}", len(symbols), sum(s in mapping for s in symbols),
        )  # fmt: skip
    pd.DataFrame(out).to_csv(DATA_DIR / "fo_members.csv", index=False)


def formation_dates(idx: pd.DatetimeIndex) -> list:
    """Last trading day of every June and December from Dec 2010 (excluding the last day)."""
    s = pd.Series(idx, idx)
    ends = s.groupby([idx.year, idx.month]).max()
    return [
        d
        for (_, m), d in ends.items()
        if m in FORMATION_MONTHS and d >= FIRST_FORMATION and d < idx[-1]
    ]


def load() -> None:
    """Read prices, traded value, membership and F&O lists into the module globals."""
    global PRICES, TRADED_VALUE, MEMBERSHIP, FO_MEMBERS
    PRICES = pd.read_parquet(DATA_DIR / "adj_close.parquet")
    TRADED_VALUE = pd.read_parquet(DATA_DIR / "traded_value.parquet").reindex(
        columns=PRICES.columns
    )
    sec = pd.read_csv(DATA_DIR / "securities.csv").drop_duplicates("stock_id").set_index("stock_id")
    ind = pd.read_csv(DATA_DIR / "industry.csv").drop_duplicates("stock_id").set_index("stock_id")
    membership = pd.read_csv(DATA_DIR / "membership.csv", parse_dates=["start_date", "end_date"])
    # a blank start date means the stock was a member before the first notice on file
    membership["start_date"] = membership.start_date.fillna(pd.Timestamp("2000-01-01"))
    membership["file_id"] = membership.stock_id.map(sec.file_id)
    # membership.csv has industry mostly for current members; fill the rest from industry.csv
    membership["industry"] = membership.industry.fillna(membership.stock_id.map(ind.industry))
    MEMBERSHIP = membership[membership.eligible & membership.file_id.isin(PRICES.columns)]
    FO_MEMBERS = pd.read_csv(DATA_DIR / "fo_members.csv", parse_dates=["date"]).dropna(
        subset=["file_id"]
    )


def members_on(day: pd.Timestamp) -> pd.DataFrame:
    """Membership spells covering `day`, one row per stock.

    Known issue (kept so the reported numbers reproduce): a spell is treated as covering its
    `end_date`, the day the stock leaves the index, so a pair can be formed on that day.
    """
    m = MEMBERSHIP[
        (MEMBERSHIP.start_date <= day) & (MEMBERSHIP.end_date.isna() | (MEMBERSHIP.end_date >= day))
    ]
    return m.drop_duplicates("file_id")


def spell_end(file_id: str, day: pd.Timestamp) -> pd.Timestamp:
    """End of the membership spell covering `day` (Timestamp.max if still a member)."""
    m = MEMBERSHIP[
        (MEMBERSHIP.file_id == file_id)
        & (MEMBERSHIP.start_date <= day)
        & (MEMBERSHIP.end_date.isna() | (MEMBERSHIP.end_date >= day))
    ]
    return m.end_date.max() if m.end_date.notna().all() else pd.Timestamp.max
