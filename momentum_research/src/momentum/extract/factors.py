from __future__ import annotations

import logging
from pathlib import Path

import requests

from momentum.extract.universe import fetch, make_session

logger = logging.getLogger(__name__)


def download_iima(cfg: dict) -> Path:
    """Download the IIMA four-factor file (or use a copy placed by hand)."""
    # IIMA monthly four-factor file, saved as received; if blocked, the file must be placed by hand
    p = cfg["institutional"]
    folder = Path(p["iima_folder"])
    folder.mkdir(parents=True, exist_ok=True)
    out = folder / p["iima_url"].rsplit("/", 1)[-1]
    if out.exists():
        return out
    try:
        body = fetch(make_session(cfg), p["iima_url"], cfg)
        if not body.startswith(b"Date"):
            raise requests.RequestException("not the factor CSV")
        out.write_bytes(body)
        logger.info(f"saved {out}")
        return out
    except requests.RequestException as e:
        manual = sorted(Path(p["manual_iima_folder"]).glob("*.csv"))
        if manual:
            return manual[-1]
        raise SystemExit(
            f"Could not download the IIMA factor file ({e}). Place the monthly four-factor CSV in "
            f"{p['manual_iima_folder']}/ and rerun."
        ) from e
