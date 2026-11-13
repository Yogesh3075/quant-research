from __future__ import annotations

import difflib
import logging
import re
import shutil
import subprocess
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
import pdfplumber
from PIL import Image

logger = logging.getLogger(__name__)

MONTHS = "Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec"
DATE_RE = (
    rf"(?:(?:{MONTHS})[a-z]*\.?\s*\d{{1,2}}(?:st|nd|rd|th)?\s*,?\s*\d{{4}}"
    rf"|\d{{1,2}}(?:st|nd|rd|th)?\s+(?:{MONTHS})[a-z]*\s*,?\s*\d{{4}})"
)
EFFECTIVE_RE = re.compile(
    rf"(?:effective\s+(?:from\s+|on\s+)?|w\.\s?e\.\s?f\.?\s*(?:from\s+)?)(?:the\s+)?(?:\w+day,?\s+)?({DATE_RE})",
    re.IGNORECASE,
)
ENUM_RE = re.compile(r"^\(?(?:\d{1,2}|[a-zA-Z]{1,2})[\).]\s*(.+?)\s*:?$")
INDEX_START = re.compile(r"^(S&P\s+)?(CNX|NIFTY|Nifty|LIX)|\bIndex:?$", re.IGNORECASE)
GROUP_START = re.compile(
    r"^(Replacement|Revision|Change|Exclusion|Inclusion|Corporate|Index|Other|Addition|Deletion)",
    re.IGNORECASE,
)
LIST_HEADER_RE = re.compile(
    r"^(?:Replacements?|Changes?|Inclusions?|Exclusions?)\s+(?:in|from)\s+((?:S&P\s+)?(?:CNX|NIFTY|Nifty)\b.+?)"
    r"(?:\s+(?:indices|index|to comply|on account|w\.e\.f).*)?:?$"
)
ISIN_RE = re.compile(r"\bIN[EF0-9][A-Z0-9]{8}\d\b")
SYMBOL_RE = re.compile(r"^(?=.*[A-Z])[A-Z0-9][A-Z0-9&\-_]{0,19}$")


def to_date(text: str):
    """Parse a date written in a notice ('1st April, 2015')."""
    text = re.sub(r"(\d)(st|nd|rd|th)\b", r"\1", text.replace(",", " "))
    d = pd.to_datetime(re.sub(r"\s+", " ", text).strip(), errors="coerce", format="mixed")
    return None if pd.isna(d) else d.date()


def norm_index(name: str) -> str:
    """Normalised index name for matching."""
    name = re.sub(r"s&p|index|indices", "", name.lower())
    return re.sub(r"[^a-z0-9]", "", name)


def is_n500(name: str) -> bool:
    """True for the Nifty 500 (or its old name, CNX 500)."""
    return norm_index(name) in ("nifty500", "cnx500")


def notice_files(cfg: dict) -> list:
    """Notice PDFs, downloaded and placed by hand."""
    files = sorted(Path(cfg["paths"]["raw_notices"]).glob("*.pdf"))
    files += sorted(Path(cfg["paths"]["manual_notices"]).glob("*.pdf"))
    return files


def ocr_pdf(pdf: Path, cfg: dict, cache_dir: Path) -> str:
    """Text of a scanned notice via tesseract."""
    # scanned notices: render each page, erase table borders (tesseract misreads them), run
    # tesseract
    pages = []
    png = cache_dir / "_page.png"
    for p in pdf.pages:
        img = np.array(p.to_image(resolution=cfg["ocr"]["resolution"]).original.convert("L"))
        dark = img < 128
        img[dark.mean(axis=1) > 0.3, :] = 255
        img[:, dark.mean(axis=0) > 0.3] = 255
        Image.fromarray(img).save(png)
        res = subprocess.run(
            [cfg["ocr"]["tesseract"], str(png), "-", "--psm", "6"],
            capture_output=True,
            text=True,
        )
        pages.append(re.sub(r"(?m)^A (?=[A-Z])", "4 ", res.stdout))  # OCR reads row number 4 as "A"
    png.unlink(missing_ok=True)
    return "\n".join(pages)


def notice_text(pdf_path: Path, cfg: dict, cache_dir: Path) -> str:
    """Text of a notice PDF (OCR if it has no text layer), cached."""
    cache = cache_dir / (pdf_path.stem + ".txt")
    if cache.exists():
        return cache.read_text()
    try:
        with pdfplumber.open(pdf_path) as pdf:
            # dedupe_chars removes the doubled letters some PDFs use for bold text
            text = "\n".join(p.dedupe_chars().extract_text() or "" for p in pdf.pages)
            if len(text.strip()) < cfg["ocr"]["min_chars"] and shutil.which(
                cfg["ocr"]["tesseract"]
            ):
                logger.info(f"  OCR {pdf_path.name}")
                text = "[OCR]\n" + ocr_pdf(pdf, cfg, cache_dir)
    except Exception as e:
        logger.info(f"  could not read {pdf_path.name}: {e}")
        text = ""
    cache.write_text(text)
    return text


def reason_from(text: str) -> str:
    """Reason for an index change, from the notice text."""
    t = text.lower()
    if "demerg" in t:
        return "demerger"
    if re.search(r"merger|amalgamat|acquisition|open offer", t):
        return "merger"
    if "delist" in t:
        return "delisting"
    if "suspen" in t:
        return "suspension"
    if re.search(r"review|rebalanc|reconstitut", t):
        return "review"
    return "other"


def effective_dates(text: str) -> list:
    """Effective dates mentioned in a notice, with their positions."""
    return [
        (m.start(), to_date(m.group(1))) for m in EFFECTIVE_RE.finditer(text) if to_date(m.group(1))
    ]


def date_for(pos: int, eff_dates: list, fallback):
    """Effective date in force at a position in the notice."""
    before = [d for p, d in eff_dates if p <= pos]
    after = [d for p, d in eff_dates if p > pos]
    return before[-1] if before else (after[0] if after else fallback)


def section_rows(lines: list) -> list:
    """Inclusion and exclusion rows in one Nifty 500 section."""
    # lines inside one index section -> list of (action, name, symbol, isin)
    rows, action, has_symbol, can_wrap, prev_text = [], None, False, False, ""
    for line in lines:
        line = re.sub(r"\s*Page \d+$", "", line).strip()
        low = line.lower()
        m = re.match(r"^(\d{1,3})\s+(.+)$", line)
        if action and m and not m.group(2)[0].islower():
            body = m.group(2)
            if has_symbol and SYMBOL_RE.match(body) and prev_text:
                body = prev_text + " " + body  # name printed on the line above the number
            rows.append([action, body, has_symbol])
            can_wrap, prev_text = True, ""
            continue
        if not line or line.isdigit():
            continue
        # the table header can be split over lines: "Sr." / "Scrip Name Symbol" / "No."
        if "name" in low and ("symbol" in low or low.startswith("sr")):
            has_symbol = "symbol" in low
            continue
        verb = re.search(
            r"(?:being|be|are|is)\s+(ex|in)cluded|following.*\b(ex|in)clu|"
            r"^(ex|in)clusions?\b|^no (ex|in)clusion",
            low,
        )
        if verb:
            kind = next(g for g in verb.groups() if g)
            action = None if low.startswith("no ") else ("exclude" if kind == "ex" else "include")
            continue
        # a wrapped company name continues the last row until its symbol arrives
        last = rows[-1] if rows else None
        ends_in_symbol = last and last[2] and SYMBOL_RE.match(last[1].rsplit(" ", 1)[-1])
        plain = (
            len(line) < 60
            and ":" not in line
            and not re.match(r"^(The|No|Sr|For|About|Note|Press|Place|Date|Mumbai|On|\*)\b", line)
        )
        if can_wrap and last and not ends_in_symbol and plain:
            last[1] += " " + line
        else:
            can_wrap = False
            prev_text = line if plain else ""
    out = []
    for action, body, has_symbol in rows:
        # some tables carry an "Effective Date" column per row
        row_date = re.search(rf"\s({DATE_RE})$", body)
        if row_date:
            body = body[: row_date.start()]
            row_date = to_date(row_date.group(1))
        isin = ISIN_RE.search(body)
        body = ISIN_RE.sub("", body).strip()
        symbol = None
        parts = body.rsplit(" ", 1)
        if has_symbol and len(parts) == 2 and SYMBOL_RE.match(parts[1]):
            body, symbol = parts
        out.append((action, body.strip(), symbol, isin.group(0) if isin else None, row_date))
    return out


def parse_table_notice(text: str, lines: list) -> list:
    """Rows from a notice laid out as one table of all indices."""
    # prose notices with a "Sr. No. Index Name" table (demergers and their later exclusions)
    in_table = [line for line in lines if re.match(r"^\d{1,3}\s+(Nifty|NIFTY|CNX)", line)]
    if not any(is_n500(re.sub(r"^\d{1,3}\s+", "", line)) for line in in_table):
        return []
    body = re.sub(r"\s+", " ", text)
    eff = effective_dates(body)
    rows = []
    title = re.search(r"Exclusion of (.+?) from\s+Nifty", body)
    if title:
        names = re.split(r"(?<=Ltd\.)\s+and\s+", title.group(1))
        listed = re.findall(r"\(([A-Z][A-Z0-9&\-]+)\)\s+(?:was|were)\s+listed", body)
        for name in names:
            name = re.sub(r"\s*\(formerly known as .*?\)", "", name).strip()
            sym = re.search(re.escape(name) + r"\s*\(([A-Z][A-Z0-9&\-]+)\)", body)
            sym = (
                sym.group(1)
                if sym
                else (listed[0] if len(names) == 1 and len(listed) == 1 else None)
            )
            rows.append(("exclude", name, sym, None, eff[-1][1] if eff else None))
        # dummy symbols listed in the same order as the companies in "inclusion of A (X),
        # B (Y) ... dummy symbols"
        incl = re.search(
            r"inclusion of (.+?)with (?:a )?dummy symbols?\s*[“\"]?([A-Z0-9, and“”\"]+)",
            body,
        )
        if incl:
            dummies = re.findall(r"DUMMY[A-Z0-9]+", incl.group(2))
            listed = re.findall(r"([A-Z][\w'&\.\(\) ]+?Ltd\.)", incl.group(1))
            listed = [n.strip() for n in listed]
            rows = [
                (
                    a,
                    n,
                    s,
                    dummies[listed.index(n)]
                    if n in listed and len(dummies) == len(listed)
                    else (dummies[0] if len(dummies) == 1 else None),
                    e,
                )
                for a, n, s, _, e in rows
            ]
        return rows
    m = re.search(
        r"(?:demerged|spun.off) entit(?:y|ies)\s+(?:(?!with\b)(.+?)\s+)?"
        r"\(?(?:with )?(?:a )?dummy\s+symbols?",
        body,
        re.IGNORECASE,
    )
    if m:
        named = m.group(1)
        if (
            not named
        ):  # "demerged entity with a dummy Symbol": the name is in "... business into the X Ltd."
            into = re.search(r"into (?:the )?([A-Z][\w&'\. ]*?Ltd\.)", body)
            named = into.group(1) if into else "unnamed demerged entity"
        names = re.split(r",\s*|(?<=Ltd\.)\s+and\s+", named)
        dummies = re.findall(r"DUMMY[A-Z0-9]+", body[m.end() : m.end() + 200])
        for i, name in enumerate(n for n in names if n):
            rows.append(
                (
                    "include",
                    name.strip(),
                    dummies[i] if i < len(dummies) else None,
                    None,
                    date_for(m.start(), eff, None),
                )
            )
    return rows


def parse_notice(text: str, source_file, announce_date, title_date) -> list:
    """Nifty 500 inclusions and exclusions in one notice."""
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    starts, pos = [], 0
    for line in lines:
        starts.append(text.find(line, pos))
        pos = max(pos, starts[-1])
    eff = effective_dates(re.sub(r"\n", " ", text))
    rows = []
    # index sections: numbered headers; a Nifty 500 section runs until the next header or group
    enum = [
        (i, ENUM_RE.match(line).group(1)) for i, line in enumerate(lines) if ENUM_RE.match(line)
    ]
    headers = [i for i, rest in enum if INDEX_START.search(rest) and not GROUP_START.match(rest)]
    groups = [i for i, rest in enum if GROUP_START.match(rest)]
    # un-numbered headers such as "Replacement in NIFTY 500, NIFTY Smallcap 250 and NIFTY
    # MidSmallcap 400 ..."
    lists = [i for i, line in enumerate(lines) if LIST_HEADER_RE.match(line)]
    n500 = [i for i in headers if is_n500(ENUM_RE.match(lines[i]).group(1))]
    n500 += [
        i
        for i in lists
        if any(
            is_n500(x)
            for x in re.split(r",\s*|\s+and\s+|\s+&\s+", LIST_HEADER_RE.match(lines[i]).group(1))
        )
    ]
    for i in sorted(set(n500)):
        end = min([j for j in headers + groups + lists if j > i] + [len(lines)])
        end = min(
            [j for j in range(i + 1, end) if lines[j].startswith(("About ", "For more", "Place:"))]
            + [end]
        )
        group_start = max([g for g in groups if g < i] + [0])
        context = " ".join(lines[group_start:i])
        when = date_for(starts[i], eff, title_date)
        for action, name, symbol, isin, row_date in section_rows(lines[i + 1 : end]):
            rows.append(
                dict(
                    effective_date=row_date or when,
                    action=action,
                    symbol=symbol,
                    company_name=name,
                    isin=isin,
                    reason=reason_from(context),
                    announce_date=announce_date,
                    source_file=source_file,
                )
            )
    first_action = next(
        (j for j, line in enumerate(lines) if re.search(r"being (ex|in)cluded", line)), None
    )
    if not rows and not headers and not lists and first_action is not None:
        # single-index notice: "... the following change in CNX 500 index ..." with no
        # section header
        intro = " ".join(lines[:first_action])
        named = re.findall(r"((?:S&P\s+)?(?:CNX|NIFTY|Nifty)[\w &]*?)\s+[Ii]ndex", intro)
        if named and all(is_n500(n) for n in named):
            when = date_for(starts[first_action], eff, title_date)
            for action, name, symbol, isin, row_date in section_rows(lines[first_action:]):
                rows.append(
                    dict(
                        effective_date=row_date or when,
                        action=action,
                        symbol=symbol,
                        company_name=name,
                        isin=isin,
                        reason=reason_from(intro),
                        announce_date=announce_date,
                        source_file=source_file,
                    )
                )
    if not rows:
        for action, name, symbol, dummy, when in parse_table_notice(text, lines):
            rows.append(
                dict(
                    effective_date=when or title_date,
                    action=action,
                    symbol=symbol or dummy,
                    company_name=name,
                    isin=None,
                    reason="demerger",
                    announce_date=announce_date,
                    source_file=source_file,
                    dummy_symbol=dummy,
                )
            )
    return rows


def parse_all_notices(cfg: dict) -> tuple:
    """Parse every notice into one table of index changes."""
    out_dir = Path(cfg["paths"]["processed_universe"])
    cache = out_dir / "notice_text"
    cache.mkdir(parents=True, exist_ok=True)
    index = pd.read_csv(Path(cfg["paths"]["raw_notices"]) / "notice_index.csv")
    index = index.drop_duplicates("file").set_index("file")
    name_re = re.compile(cfg["universe"]["index_name_regex"], re.IGNORECASE)
    rows, seen = [], []
    for f in notice_files(cfg):
        text = notice_text(f, cfg, cache)
        mentions = bool(name_re.search(text))
        ann = re.search(r"ann(\d{4}-\d{2}-\d{2})", f.name)
        ann = date.fromisoformat(ann.group(1)) if ann else None
        title_date = index["title_effective_date"].get(f.name)
        title_date = date.fromisoformat(title_date) if isinstance(title_date, str) else None
        found = parse_notice(text, f.name, ann, title_date) if mentions else []
        seen.append(
            dict(
                source_file=f.name,
                announce_date=ann,
                mentions_n500=mentions,
                n500_rows=len(found),
                chars=len(text),
            )
        )
        rows += found
    changes = pd.DataFrame(rows)
    changes["effective_date"] = pd.to_datetime(changes["effective_date"])
    # a few old notices are listed late (e.g. a 2005 notice listed in 2015)
    changes = changes[
        changes["effective_date"] >= pd.Timestamp(cfg["universe"]["notice_listing_from"])
    ]
    changes = changes.drop_duplicates(["effective_date", "action", "company_name", "symbol"])
    return changes, pd.DataFrame(seen)


def apply_manual_rows(changes: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    """Add the hand-transcribed rows (each citing its notice)."""
    # hand-transcribed rows for notices the parser cannot read (each row cites its notice)
    path = Path(cfg["paths"]["manual_rows"])
    if not path.exists():
        return changes
    manual = pd.read_csv(path, comment="#")
    manual["effective_date"] = pd.to_datetime(manual["effective_date"])
    for _, v in manual[manual["action"] == "void_notice"].iterrows():
        hit = (changes["source_file"] == v["source_file"]) & (
            changes["effective_date"] == v["effective_date"]
        )
        logger.info(f"  void {hit.sum()} rows from {v['source_file']}")
        changes = changes[~hit]
    for _, v in manual[manual["action"] == "symbol_for_name"].iterrows():
        changes.loc[changes["company_name"] == v["company_name"], "symbol"] = v["symbol"]
    manual = manual[~manual["action"].isin(["void_notice", "symbol_for_name"])]
    cancels = manual[manual["action"].str.startswith("cancel_")]
    for _, c in cancels.iterrows():
        hit = (
            (changes["effective_date"] == c["effective_date"])
            & (changes["symbol"] == c["symbol"])
            & (changes["action"] == c["action"].replace("cancel_", ""))
        )
        if not hit.any():
            logger.info(
                f"  manual cancel matched nothing: {c['symbol']} {c['effective_date']:%Y-%m-%d}"
            )
        changes = changes[~hit]
    adds = manual[~manual["action"].str.startswith("cancel_")].assign(manual=True)
    return pd.concat([changes, adds], ignore_index=True)


def latest_file(folder, prefix: str) -> Path:
    """Most recent file with a prefix in a folder."""
    files = sorted(Path(folder).glob(f"{prefix}*.csv"))
    if not files:
        raise SystemExit(
            f"Missing {prefix}*.csv in {folder}. Run: python scripts/run.py universe-download"
        )
    return files[-1]


def load_nse_lists(cfg: dict) -> tuple:
    """NSE's symbol changes, name changes, equity, delisted and current lists."""
    raw = cfg["paths"]["raw_universe"]

    def strip(df):
        return df.rename(columns=lambda c: c.strip()).apply(
            lambda s: s.str.strip() if pd.api.types.is_string_dtype(s) else s
        )

    sym = strip(pd.read_csv(latest_file(raw, "symbolchange"), encoding="latin-1"))
    sym = pd.DataFrame(
        {
            "old": sym["OLD SYMBOL"],
            "new": sym["NEW SYMBOL"],
            "date": pd.to_datetime(sym["EFFECTIVE DATE"], format="%d-%b-%Y"),
        }
    )
    manual = Path(cfg["paths"]["manual_symbol_changes"])
    if manual.exists():  # changes missing from NSE's file, found by hand
        m = pd.read_csv(manual, comment="#")
        sym = pd.concat(
            [
                sym,
                pd.DataFrame(
                    {
                        "old": m["old"],
                        "new": m["new"],
                        "date": pd.to_datetime(m["date"]),
                    }
                ),
            ],
            ignore_index=True,
        )
    names = strip(pd.read_csv(latest_file(raw, "namechange"), encoding="latin-1"))
    names["date"] = pd.to_datetime(names["EFFECTIVE DATE"], format="%d-%b-%Y", errors="coerce")
    equity = strip(pd.read_csv(latest_file(raw, "EQUITY_L"), encoding="latin-1"))
    delisted = strip(pd.read_csv(latest_file(raw, "delisted"), encoding="latin-1").iloc[:, :4])
    delisted.columns = ["symbol", "company", "date", "type"]
    delisted["date"] = pd.to_datetime(
        delisted["date"], format="mixed", dayfirst=True, errors="coerce"
    )
    current = strip(pd.read_csv(latest_file(raw, "ind_nifty500list"), encoding="latin-1"))
    return sym, names, equity, delisted, current


def forward_symbol(symbol: str, when, sym_changes: pd.DataFrame) -> str:
    """The symbol a stock trades under today, from an old symbol and date."""
    # follow old -> new symbol changes that happen after `when`; returns the latest symbol
    when = pd.Timestamp(when)
    for _ in range(20):
        nxt = sym_changes[
            (sym_changes["old"] == symbol) & (sym_changes["date"] > when)
        ].sort_values("date")
        if nxt.empty:
            return symbol
        symbol, when = nxt.iloc[0]["new"], nxt.iloc[0]["date"]
    return symbol


def symbol_history(latest: str, sym_changes: pd.DataFrame) -> list:
    """Every symbol a stock has used, latest first, with dates."""
    # list of (symbol, valid_from) walking back from the latest symbol
    hist, symbol, until = [], latest, pd.Timestamp.max
    for _ in range(20):
        prev = sym_changes[
            (sym_changes["new"] == symbol) & (sym_changes["date"] < until)
        ].sort_values("date")
        if prev.empty:
            break
        row = prev.iloc[-1]
        hist.append((symbol, row["date"]))
        symbol, until = row["old"], row["date"]
    hist.append((symbol, None))
    return hist[::-1]


def norm_name(name) -> str:
    """Normalised company name for matching."""
    n = str(name).lower().replace("&", " and ").replace("(i)", " india ")
    n = re.sub(r"[^a-z0-9 ]", " ", n)
    swaps = {
        "corpn": "corporation",
        "corp": "corporation",
        "co": "company",
        "inds": "industries",
        "ind": "industries",
        "intl": "international",
        "engg": "engineering",
        "mfg": "manufacturing",
        "dev": "development",
        "fin": "finance",
        "pharma": "pharmaceuticals",
        "tech": "technologies",
    }
    words = [swaps.get(w, w) for w in n.split() if w not in ("ltd", "limited", "the", "and")]
    return " ".join(words)


def name_table(changes: pd.DataFrame, names, equity, delisted, current) -> pd.DataFrame:
    """Company names to symbols, through time."""
    today = pd.Timestamp.today().normalize()
    parts = [
        pd.DataFrame(
            {
                "name": changes["company_name"],
                "symbol": changes["symbol"],
                "date": changes["effective_date"],
            }
        ),
        pd.DataFrame(
            {
                "name": current["Company Name"],
                "symbol": current["Symbol"],
                "date": today,
            }
        ),
        pd.DataFrame(
            {
                "name": equity["NAME OF COMPANY"],
                "symbol": equity["SYMBOL"],
                "date": today,
            }
        ),
        pd.DataFrame(
            {
                "name": names["OLD NAME OF THE COMPANY"],
                "symbol": names["SYMBOL"],
                "date": names["date"] - pd.Timedelta(days=1),
            }
        ),
        pd.DataFrame(
            {
                "name": names["NEW NAME OF THE COMPANY"],
                "symbol": names["SYMBOL"],
                "date": names["date"],
            }
        ),
        pd.DataFrame(
            {
                "name": delisted["company"],
                "symbol": delisted["symbol"],
                "date": delisted["date"] - pd.Timedelta(days=1),
            }
        ),
    ]
    t = pd.concat(parts).dropna(subset=["name", "symbol"])
    t = t[~t["symbol"].str.startswith("DUMMY")]
    t["key"] = t["name"].map(norm_name)
    return t


def resolve_name(name: str, when, table: pd.DataFrame, among=None, cutoff=0.86) -> tuple:
    """Symbol for a company name on a date (fuzzy match as a last resort)."""
    # name -> (symbol at source date, source date, how); `among` limits candidates to these
    # latest symbols
    key = norm_name(name)
    t = table if among is None else table[table["latest"].isin(among)]
    hit = t[t["key"] == key]
    how = "exact"
    if hit.empty:
        # fuzzy only among names that share the first word ("zandu pharma" must not match
        # "anuh pharma")
        same_start = [k for k in t["key"].unique() if k.split()[:1] == key.split()[:1]]
        close = difflib.get_close_matches(key, same_start, n=1, cutoff=cutoff)
        if not close:
            return None, None, "unresolved"
        hit, how = t[t["key"] == close[0]], f"fuzzy:{close[0]}"
    hit = hit.assign(gap=(hit["date"] - pd.Timestamp(when)).abs()).sort_values("gap")
    return hit.iloc[0]["symbol"], hit.iloc[0]["date"], how


def symbol_key(symbol: str, when, sym_changes: pd.DataFrame) -> str:
    """Stable stock key: the symbol it trades under today."""
    return forward_symbol(symbol, pd.Timestamp(when) - pd.Timedelta(days=1), sym_changes)


def dummy_keys(changes: pd.DataFrame, sym_changes: pd.DataFrame) -> dict:
    """Keys for demerger placeholder symbols."""
    # a demerged entity enters under DUMMYxxx and later leaves under its listed symbol
    out = {}
    if "dummy_symbol" not in changes:
        return out
    for _, r in changes[
        changes["dummy_symbol"].notna() & (changes["action"] == "exclude")
    ].iterrows():
        if r["symbol"] and not str(r["symbol"]).startswith("DUMMY"):
            out[(r["dummy_symbol"], r["effective_date"].year)] = symbol_key(
                r["symbol"], r["effective_date"], sym_changes
            )
    return out


def row_key(r: pd.Series, dummies: dict, sym_changes: pd.DataFrame):
    """Stock key of one index-change row."""
    sym = r["symbol"] if isinstance(r["symbol"], str) else None
    if sym and sym.startswith("DUMMY"):
        for yr in (r["effective_date"].year, r["effective_date"].year + 1):
            if (sym, yr) in dummies:
                return dummies[(sym, yr)]
        return f"{sym}:{r['effective_date']:%Y%m}"
    return (
        symbol_key(
            sym,
            r["announce_date"] if pd.notna(r["announce_date"]) else r["effective_date"],
            sym_changes,
        )
        if sym
        else None
    )


def drop_rescheduled(changes: pd.DataFrame, days: int) -> pd.DataFrame:
    """Drop rows of changes that were announced twice and rescheduled."""
    # a later notice can move an announced change to another date: the same stock gets the same
    # action twice with nothing in between; keep the row from the later-announced notice
    drop = []
    for _, g in changes[changes["key"].notna()].groupby("key"):
        g = g.sort_values("effective_date")
        for (i, a), (j, b) in zip(g.iterrows(), list(g.iterrows())[1:], strict=False):
            if (
                a["action"] == b["action"]
                and (b["effective_date"] - a["effective_date"]).days <= days
            ):
                drop.append(i if a["announce_date"] <= b["announce_date"] else j)
    if drop:
        logger.info(f"  {len(drop)} rescheduled duplicate rows dropped")
    changes.loc[drop].to_csv(Path("Data/processed/universe/rescheduled_dropped.csv"), index=False)
    return changes.drop(index=drop)


def reconstruct(changes: pd.DataFrame, current_keys, table, sym_changes) -> tuple:
    """Membership spells from today's list and the changes, run backwards."""
    dummies = dummy_keys(changes, sym_changes)
    changes = changes.sort_values("effective_date").reset_index(drop=True)
    changes["key"] = [row_key(r, dummies, sym_changes) for _, r in changes.iterrows()]
    changes = drop_rescheduled(changes, days=120)
    changes["match"] = ["" if pd.isna(k) else "symbol" for k in changes["key"]]
    table["latest"] = [
        symbol_key(s, d, sym_changes) for s, d in zip(table["symbol"], table["date"], strict=False)
    ]

    # backward: undo each date's changes, newest first
    members, anomalies = set(current_keys), []
    for when in sorted(changes["effective_date"].unique(), reverse=True):
        day = changes[changes["effective_date"] == when]
        for i in day.index[day["action"] == "include"]:
            if pd.isna(changes.at[i, "key"]):
                sym, d, how = resolve_name(
                    changes.at[i, "company_name"],
                    when,
                    table,
                    among=members,
                    cutoff=0.75,
                )
                changes.at[i, "key"] = (
                    symbol_key(sym, d, sym_changes)
                    if sym
                    else "NAME:" + norm_name(changes.at[i, "company_name"])
                )
                changes.at[i, "match"] = how
            k = changes.at[i, "key"]
            if k not in members:
                # symbol changed without an NSE record, or a demerged entity kept
                # under its listed symbol
                sym, d, how = resolve_name(
                    changes.at[i, "company_name"],
                    when,
                    table,
                    among=members,
                    cutoff=0.9,
                )
                if sym:
                    k = changes.at[i, "key"] = symbol_key(sym, d, sym_changes)
                    changes.at[i, "match"] = "by name after symbol miss: " + how
            if k in members:
                members.remove(k)
            else:
                anomalies.append(
                    dict(
                        effective_date=when,
                        action="include",
                        key=k,
                        problem="included stock not in later list",
                        company_name=changes.at[i, "company_name"],
                        source_file=changes.at[i, "source_file"],
                    )
                )
        for i in day.index[day["action"] == "exclude"]:
            if pd.isna(changes.at[i, "key"]):
                sym, d, how = resolve_name(changes.at[i, "company_name"], when, table)
                changes.at[i, "key"] = (
                    symbol_key(sym, d, sym_changes)
                    if sym
                    else "NAME:" + norm_name(changes.at[i, "company_name"])
                )
                changes.at[i, "match"] = how
            k = changes.at[i, "key"]
            if k in members:
                anomalies.append(
                    dict(
                        effective_date=when,
                        action="exclude",
                        key=k,
                        problem="excluded stock already in earlier list",
                        company_name=changes.at[i, "company_name"],
                        source_file=changes.at[i, "source_file"],
                    )
                )
            members.add(k)
    start_set = set(members)

    # forward: replay from the earliest list and build spells
    members, spells, forward_issues = set(start_set), {}, []
    for k in start_set:
        spells[k] = [
            dict(
                start_date=None,
                end_date=None,
                entry_reason="member before first notice",
                exit_reason=None,
            )
        ]
    for when in sorted(changes["effective_date"].unique()):
        day = changes[changes["effective_date"] == when]
        for _, r in day[day["action"] == "exclude"].iterrows():
            if r["key"] not in members:
                forward_issues.append(f"{when:%Y-%m-%d} exclude {r['key']} not a member")
                continue
            members.remove(r["key"])
            spells[r["key"]][-1].update(end_date=when, exit_reason=r["reason"])
        for _, r in day[day["action"] == "include"].iterrows():
            if r["key"] in members:
                forward_issues.append(f"{when:%Y-%m-%d} include {r['key']} already a member")
                continue
            members.add(r["key"])
            spells.setdefault(r["key"], []).append(
                dict(
                    start_date=when,
                    end_date=None,
                    entry_reason=r["reason"],
                    exit_reason=None,
                )
            )
    return changes, start_set, spells, members, pd.DataFrame(anomalies), forward_issues


def symbol_at(key, when: pd.Timestamp, histories: dict) -> str:
    """Symbol of a stock on a date."""
    sym = key
    for s, since in histories.get(key, [(key, None)]):
        if since is None or since <= when:
            sym = s
    return sym


def build_membership(cfg: dict) -> dict:
    """Point-in-time membership: spells and monthly members."""
    out = Path(cfg["paths"]["processed_universe"])
    changes, seen = parse_all_notices(cfg)
    changes = apply_manual_rows(changes, cfg)
    sym_changes, names, equity, delisted, current = load_nse_lists(cfg)
    today = pd.Timestamp.today().normalize()
    current_keys = [symbol_key(s, today, sym_changes) for s in current["Symbol"]]
    # a placeholder still in today's list (e.g. DUMMYHEG) gets the dated key of its inclusion
    for i, s in enumerate(current["Symbol"]):
        if s.startswith("DUMMY"):
            inc = changes[(changes["symbol"] == s) & (changes["action"] == "include")]
            if len(inc):
                current_keys[i] = f"{s}:{inc['effective_date'].max():%Y%m}"
    table = name_table(changes, names, equity, delisted, current)
    changes, start_set, spells, end_set, anomalies, forward_issues = reconstruct(
        changes, current_keys, table, sym_changes
    )

    # names, ISIN and industry per stock
    isin = dict(zip(equity["SYMBOL"], equity["ISIN NUMBER"], strict=False)) | dict(
        zip(current["Symbol"], current["ISIN Code"], strict=False)
    )
    industry = dict(zip(current["Symbol"], current["Industry"], strict=False))
    last_name = (
        changes.sort_values("effective_date").groupby("key")["company_name"].last().to_dict()
    )
    last_name |= dict(zip(current_keys, current["Company Name"], strict=False))
    histories = {k: symbol_history(k, sym_changes) for k in spells}

    rows = []
    for k, sp in spells.items():
        hist = "; ".join(f"{s} from {d:%Y-%m-%d}" if d is not None else s for s, d in histories[k])
        for s in sp:
            rows.append(
                dict(
                    stock_id=k,
                    isin=isin.get(k, ""),
                    symbol_history=hist,
                    company_name=last_name.get(k, ""),
                    industry=industry.get(k, ""),
                    **s,
                )
            )
    membership = pd.DataFrame(rows).sort_values(["stock_id", "start_date"], na_position="first")
    membership.to_csv(out / "membership.csv", index=False)

    month_ends = pd.date_range(cfg["universe"]["start_date"], today, freq="ME")
    monthly = []
    for m in month_ends:
        live = membership[
            (membership["start_date"].isna() | (membership["start_date"] <= m))
            & (membership["end_date"].isna() | (membership["end_date"] > m))
        ]
        for k in live["stock_id"]:
            monthly.append(
                dict(
                    date=m.date(),
                    stock_id=k,
                    isin=isin.get(k, ""),
                    symbol=symbol_at(k, m, histories),
                )
            )
    monthly = pd.DataFrame(monthly)
    monthly.to_csv(out / "monthly_members.csv", index=False)

    changes.drop(columns=["manual"], errors="ignore").assign(
        manual=changes.get("manual", False)
    ).to_csv(out / "index_changes.csv", index=False)
    seen.to_csv(out / "notices_parsed.csv", index=False)
    anomalies.to_csv(out / "reconstruction_anomalies.csv", index=False)
    logger.info(
        f"{len(changes)} change rows, {membership['stock_id'].nunique()} distinct stocks, "
        f"{len(anomalies)} backward anomalies, {len(forward_issues)} forward issues"
    )
    return dict(
        changes=changes,
        seen=seen,
        membership=membership,
        monthly=monthly,
        anomalies=anomalies,
        forward_issues=forward_issues,
        start_set=start_set,
        end_set=end_set,
        current_keys=current_keys,
        sym_changes=sym_changes,
        current=current,
    )


def apply_decisions(cfg: dict) -> tuple:
    """Apply the universe decisions (placeholders, share classes) to membership."""
    out = Path(cfg["paths"]["processed_universe"])
    d = cfg["decisions"]
    spells = pd.read_csv(out / "membership.csv", parse_dates=["start_date", "end_date"])
    changes = pd.read_csv(out / "index_changes.csv", parse_dates=["effective_date"])
    spells = spells[spells["entry_reason"] != "uncertain"]  # rerun-safe

    placeholder_entries = changes[
        (changes["action"] == "include")
        & changes["symbol"].astype(str).str.startswith(d["placeholder_prefix"])
    ]
    entries = {(r["key"], r["effective_date"]) for _, r in placeholder_entries.iterrows()}
    entries |= {(s["stock_id"], pd.Timestamp(s["date"])) for s in d["spinoff_inclusions"]}

    spells["eligible"], spells["excluded_reason"] = True, ""
    is_placeholder = [
        (k, s) in entries or str(k).startswith(d["placeholder_prefix"])
        for k, s in zip(spells["stock_id"], spells["start_date"], strict=False)
    ]
    spells.loc[is_placeholder, ["eligible", "excluded_reason"]] = [
        False,
        "placeholder, no prices",
    ]
    second = spells["stock_id"].isin(d["second_share_classes"])
    spells.loc[second, ["eligible", "excluded_reason"]] = [False, "second share class"]

    extra = []
    for u in d["uncertain_spells"]:
        info = spells[spells["stock_id"] == u["stock_id"]].iloc[0]
        extra.append(
            dict(
                info,
                start_date=pd.Timestamp(u["start"]),
                end_date=pd.Timestamp(u["end"]),
                entry_reason="uncertain",
                exit_reason="",
                eligible=False,
                excluded_reason=u["reason"],
            )
        )
    spells = pd.concat([spells, pd.DataFrame(extra)], ignore_index=True)
    spells = spells.sort_values(["stock_id", "start_date"], na_position="first")
    spells.to_csv(out / "membership.csv", index=False)

    # month-end base table: members plus the uncertain months (not members)
    monthly = pd.read_csv(out / "monthly_members.csv", parse_dates=["date"])
    monthly["member"], monthly["excluded_reason"] = True, ""
    for _, s in spells[~spells["eligible"]].iterrows():
        start = s["start_date"] if pd.notna(s["start_date"]) else pd.Timestamp.min
        end = s["end_date"] if pd.notna(s["end_date"]) else pd.Timestamp.max
        hit = (
            (monthly["stock_id"] == s["stock_id"])
            & (monthly["date"] >= start)
            & (monthly["date"] < end)
        )
        monthly.loc[hit, "excluded_reason"] = s["excluded_reason"]
        if s["entry_reason"] == "uncertain":
            months = pd.date_range(start, end, freq="ME")
            monthly = pd.concat(
                [
                    monthly,
                    pd.DataFrame(
                        dict(
                            date=months,
                            stock_id=s["stock_id"],
                            isin=s["isin"],
                            symbol=s["stock_id"],
                            member=False,
                            excluded_reason=s["excluded_reason"],
                        )
                    ),
                ]
            )
    monthly = monthly.sort_values(["date", "stock_id"])
    monthly[["date", "stock_id", "isin", "symbol", "member", "excluded_reason"]].to_csv(
        out / "eligibility_base.csv", index=False
    )
    logger.info(
        f"decisions: {(~spells['eligible']).sum()} ineligible spells, "
        f"{(monthly['excluded_reason'] != '').sum()} month-end rows excluded"
    )
    return spells, monthly
