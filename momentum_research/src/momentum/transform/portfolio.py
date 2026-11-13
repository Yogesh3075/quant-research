from __future__ import annotations

import math
from collections import Counter
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import pandas as pd


def sector_cap_names(cfg: dict, n: int | None = None) -> int:
    """Most names allowed per sector for an n-stock portfolio."""
    p = cfg["portfolio"]
    return math.floor(p["sector_cap"] * (n or p["holdings"]))


def select(
    ranked: pd.DataFrame, held: list, forced: list, sector: dict, n: int, buffer, cap
) -> list:
    """Top n by rank, keeping holdings within the buffer, under the sector cap."""
    # ranked: eligible stocks at t sorted by rank (file_id, rank); held: current holdings;
    # forced: holdings that cannot
    # be traded on the execution day (kept as they are); sector: file_id -> sector; cap: most
    # names per sector
    chosen, count = [], Counter()
    for f in forced:
        chosen.append(f)
        count[sector.get(f, "Unclassified")] += 1
    # buffer: current holdings still eligible and ranked within buffer_rank, best rank first
    keep = ranked[ranked["file_id"].isin(held) & (ranked["rank"] <= buffer)]
    for f in keep["file_id"]:
        s = sector.get(f, "Unclassified")
        if f not in chosen and len(chosen) < n and count[s] < cap:
            chosen.append(f)
            count[s] += 1
    # fill from the top, skipping names whose sector is full
    for f in ranked["file_id"]:
        if len(chosen) >= n:
            break
        s = sector.get(f, "Unclassified")
        if f not in chosen and count[s] < cap:
            chosen.append(f)
            count[s] += 1
    return chosen


def select_all(ranked: pd.DataFrame, held: list, forced: list, sector: dict, cfg: dict) -> list:
    """Every eligible stock (the equal-weight universe), forced holdings first."""
    # equal-weight benchmark: every eligible stock (plus untradable holdings)
    return list(dict.fromkeys(list(forced) + list(ranked["file_id"])))
