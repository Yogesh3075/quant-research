"""Pair formation: same-industry candidates, Engle-Granger test, half-life filter, top 20."""

from __future__ import annotations

from multiprocessing import Pool

import numpy as np
import pandas as pd
from statsmodels.tsa.stattools import coint

from pairs import universe

MIN_TRADED_VALUE = 5e7  # Rs 5 crore median daily traded value over the formation window
P_MAX = 0.05  # Engle-Granger p-value
HALF_LIFE_MIN, HALF_LIFE_MAX = 5, 60  # trading days
MAX_PAIRS_PER_STOCK = 2
SLOTS = 20  # pairs selected per window
LARGE_RANK, MID_RANK = 100, 250  # size buckets by traded-value rank, used for slippage
WORKERS = 8


def half_life(spread: np.ndarray) -> float:
    """Half-life of mean reversion, in days, from an AR(1) fit of the spread changes.

    Regress d s_t = b * s_{t-1} + c. The spread decays by (1 + b) a day, so the half-life is
    -ln 2 / ln(1 + b); it is infinite unless -1 < b < 0.
    """
    b = np.polyfit(spread[:-1], np.diff(spread), 1)[0]
    return -np.log(2) / np.log(1 + b) if -1 < b < 0 else np.inf


def bucket(rank: float) -> str:
    """Size bucket by traded-value rank among the formation date's members."""
    return "large" if rank <= LARGE_RANK else "mid" if rank <= MID_RANK else "small"


def select_pairs(task: tuple) -> tuple[pd.DataFrame, dict]:
    """Candidate pairs, Engle-Granger, half-life and top-20 selection on formation data only."""
    day, months = task
    prices = universe.PRICES
    window = prices.loc[(prices.index > day - pd.DateOffset(months=months)) & (prices.index <= day)]
    members = universe.members_on(day)
    traded_value = universe.TRADED_VALUE.loc[window.index, members.file_id].median()
    rank = traded_value.rank(ascending=False)
    eligible = members[
        members.file_id.map(window[members.file_id].notna().all())
        & members.file_id.map(traded_value >= MIN_TRADED_VALUE)
        & members.industry.notna()
        & (members.industry != "Unclassified")
    ]
    logp = np.log(window)
    fo_ids = set(universe.FO_MEMBERS.loc[universe.FO_MEMBERS.date == day, "file_id"])
    names = universe.MEMBERSHIP.drop_duplicates("file_id").set_index("file_id").stock_id

    tested, rows = 0, []
    for sector, group in eligible.groupby("industry"):
        ids = sorted(group.file_id)
        for i in range(len(ids)):
            for j in range(i + 1, len(ids)):
                y, x = ids[i], ids[j]
                tested += 1
                p = coint(logp[y], logp[x])[1]
                if p >= P_MAX:
                    continue
                beta, alpha = np.polyfit(logp[x], logp[y], 1)
                spread = (logp[y] - alpha - beta * logp[x]).values
                rows.append({
                    "formation_date": day, "y": y, "x": x, "pair": f"{names[y]}-{names[x]}",
                    "sector": sector, "p_value": p, "hedge_ratio": beta, "alpha": alpha,
                    "mu": spread.mean(), "sd": spread.std(ddof=1), "half_life": half_life(spread),
                    "bucket_y": bucket(rank[y]), "bucket_x": bucket(rank[x]),
                    "fo_eligible": y in fo_ids and x in fo_ids,
                })  # fmt: skip
    cointegrated = pd.DataFrame(rows)
    selected, used = [], {}
    if len(cointegrated):
        good = cointegrated[
            cointegrated.half_life.between(HALF_LIFE_MIN, HALF_LIFE_MAX)
        ].sort_values("p_value")
        for r in good.to_dict("records"):
            if (
                used.get(r["y"], 0) < MAX_PAIRS_PER_STOCK
                and used.get(r["x"], 0) < MAX_PAIRS_PER_STOCK
            ):
                selected.append(r)
                used[r["y"]] = used.get(r["y"], 0) + 1
                used[r["x"]] = used.get(r["x"], 0) + 1
            if len(selected) == SLOTS:
                break
        half_life_ok = len(good)
    else:
        half_life_ok = 0
    selected = pd.DataFrame(selected)
    counts = {
        "formation_date": day.date(),
        "formation_months": months,
        "members": len(members),
        "eligible_stocks": len(eligible),
        "fo_stocks_eligible": int(eligible.file_id.isin(fo_ids).sum()),
        "candidates_tested": tested,
        "cointegrated": len(cointegrated),
        "half_life_ok": half_life_ok,
        "selected": len(selected),
        "selected_fo": int(selected.fo_eligible.sum()) if len(selected) else 0,
    }
    return selected, counts


def selections_for(days: list, months: int) -> tuple[dict, list]:
    """Selected pairs and window counts for each formation date, in parallel."""
    with Pool(WORKERS, initializer=universe.load) as pool:
        out = pool.map(select_pairs, [(d, months) for d in days])
    return {d: s for d, (s, _) in zip(days, out, strict=True)}, [c for _, c in out]
