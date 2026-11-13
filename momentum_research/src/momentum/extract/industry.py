from __future__ import annotations

import logging
import time
from pathlib import Path

import pandas as pd
import requests

from momentum.extract.universe import make_session

logger = logging.getLogger(__name__)


def download_wayback(cfg: dict) -> None:
    """Save archived copies of NSE's Nifty 500 constituent file."""
    # archived copies of the Nifty 500 constituent file, saved as received with the snapshot
    # timestamp
    folder = Path(cfg["paths"]["raw_industry"]) / "wayback"
    folder.mkdir(parents=True, exist_ok=True)
    sess, pause, log = make_session(cfg), cfg["industry"]["wayback_pause_seconds"], []
    sess.headers["User-Agent"] = cfg["industry"]["wayback_user_agent"]
    for url in cfg["industry"]["archived_urls"]:
        time.sleep(pause)
        r = sess.get(
            cfg["urls"]["wayback_cdx"],
            params={"url": url, "output": "json", "filter": "statuscode:200"},
            timeout=120,
        )
        r.raise_for_status()
        snaps = r.json()[1:] if r.text.strip() else []
        logger.info(f"{url}: {len(snaps)} snapshots")
        for snap in snaps:
            ts, original = snap[1], snap[2]
            out = folder / f"{ts}_{url.replace('/', '_')}"
            if out.exists() and out.read_bytes()[:12].lower().startswith(b"company name"):
                continue  # a valid copy is already saved
            time.sleep(pause)
            try:
                r = sess.get(cfg["urls"]["wayback_file"].format(ts=ts, url=original), timeout=120)
                r.raise_for_status()
                out.write_bytes(r.content)
                log.append(dict(timestamp=ts, url=original, status="ok", bytes=len(r.content)))
            except requests.RequestException as e:
                log.append(dict(timestamp=ts, url=original, status=f"failed: {e}"[:120], bytes=0))
    pd.DataFrame(log).to_csv(
        folder / "download_log.csv",
        mode="a",
        index=False,
        header=not (folder / "download_log.csv").exists(),
    )


def try_nse_quote(cfg: dict, symbols):
    """Industry from NSE's quote API for former members (best effort)."""
    # NSE equity quote metadata (industry); stops after repeated refusals
    folder = Path(cfg["paths"]["raw_industry"]) / "nse_quote"
    folder.mkdir(parents=True, exist_ok=True)
    sess, log, refused = make_session(cfg), [], 0
    for sym in symbols:
        time.sleep(cfg["http"]["pause_seconds"])
        try:
            r = sess.get(
                cfg["urls"]["nse_quote"].format(symbol=requests.utils.quote(sym)),
                timeout=30,
            )
            (folder / f"{sym.replace('&', '_and_')}.json").write_bytes(r.content)
            log.append(dict(symbol=sym, status=r.status_code))
            refused = refused + 1 if r.status_code != 200 else 0
        except requests.RequestException as e:
            log.append(dict(symbol=sym, status=str(e)[:100]))
            refused += 1
        if refused >= 5:
            logger.info(f"NSE quote page refused {refused} requests in a row; skipping this source")
            break
    pd.DataFrame(log).to_csv(folder / "download_log.csv", index=False)
    return pd.DataFrame(log)
