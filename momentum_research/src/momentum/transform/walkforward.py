from __future__ import annotations

import itertools
import logging
from pathlib import Path

import numpy as np
import pandas as pd

from momentum.transform.backtest import (
    PRESETS,
    index_returns,
    load_market,
    period_returns,
    simulate,
)
from momentum.transform.diagnostics import dev_returns, monthly_ic, nw_t
from momentum.transform.split import signal_dates

logger = logging.getLogger(__name__)


def grid(cfg: dict) -> list:
    """The 18 strategy combinations of the walk-forward grid."""
    w = cfg["walkforward"]
    return [
        dict(
            name=f"{sig}|N{n}|{reb}",
            kind="momentum",
            signal=sig,
            n=n,
            buffer=int(w["buffer_multiple"] * n),
            rebalance=reb,
        )
        for sig, n, reb in itertools.product(w["signals"], w["holdings"], w["rebalance"])
    ]


def months_between(first: str, last: str) -> list:
    """Months from first to last, as 'YYYY-MM' strings."""
    return [str(p) for p in pd.period_range(first, last, freq="M")]


def folds(cfg: dict) -> pd.DataFrame:
    """Expanding-window folds with a one-month embargo and 12-month tests."""
    w, sp = cfg["walkforward"], cfg["split"]
    dev = months_between(sp["first_signal_month"], sp["last_dev_month"])
    out, k = [], 0
    while True:
        train_last = w["first_train_months"] - 1 + k * w["step_months"]
        test_first = train_last + 1 + w["embargo_months"]
        if test_first >= len(dev):
            break
        test_last = min(test_first + w["test_months"] - 1, len(dev) - 1)
        out.append(
            dict(
                fold=k + 1,
                train=(dev[0], dev[train_last]),
                embargo=dev[train_last + 1 : test_first],
                test=(dev[test_first], dev[test_last]),
            )
        )
        k += 1
    return out


def sharpe(r: pd.Series, rf_m: float) -> float:
    """Annualised Sharpe of monthly returns over rf."""
    x = r - rf_m
    return x.mean() / x.std() * np.sqrt(12) if len(x) > 2 else np.nan


def window_turnover(run: dict, first_exec, last_exec, years: float) -> float:
    """Annualised turnover inside a window."""
    tr = run["trades"]
    eq = run["equity"]["equity"]
    tr = tr[(tr["date"] >= first_exec) & (tr["date"] <= last_exec)]
    avg = eq[(eq.index >= first_exec) & (eq.index <= last_exec)].mean()
    return tr["value"].sum() / 2 / avg / years if len(tr) else 0.0


def choose(cfg: dict, table: pd.DataFrame) -> pd.Series:
    """Highest net Sharpe; ties broken by mean IC, then turnover."""
    # highest net Sharpe; tie-break higher mean IC, then lower turnover
    t = table.sort_values(["sharpe", "ic", "turnover"], ascending=[False, False, True])
    return t.iloc[0]


def train_table(cfg: dict, full: dict, ics: dict, months) -> pd.DataFrame:
    """Grid statistics on a fold's training months."""
    rf_m = (1 + cfg["backtest"]["risk_free"]) ** (1 / 12) - 1
    sd = signal_dates(cfg)
    rows = []
    for g in grid(cfg):
        r = full[g["name"]]["returns"]
        r = r[r.index.isin(months)]
        first_exec = sd.loc[months[0], "execution_date"]
        last_exec = sd.loc[months[-1], "execution_date"]
        rows.append(
            dict(
                name=g["name"],
                sharpe=sharpe(r, rf_m),
                ic=ics[g["signal"]].reindex(pd.to_datetime(sd.loc[months, "signal_date"])).mean(),
                turnover=window_turnover(
                    full[g["name"]]["run"], first_exec, last_exec, len(months) / 12
                ),
            )
        )
    return pd.DataFrame(rows)


def run_walkforward(cfg: dict, only_fold=None) -> tuple:
    """Phase 4 walk-forward: choose in each fold, test out of sample."""
    out = Path(cfg["paths"]["results"]) / "phase4"
    out.mkdir(parents=True, exist_ok=True)
    sc = cfg["walkforward"]["scenario"]
    rf_m = (1 + cfg["backtest"]["risk_free"]) ** (1 / 12) - 1
    m = load_market(cfg)
    params = {g["name"]: g for g in grid(cfg)}
    # one full development run per combination (training windows are its first months)
    full = {}
    for name, g in params.items():
        run = simulate(cfg, m, g, sc)
        full[name] = dict(run=run, returns=period_returns(cfg, run["equity"]["equity"]))
        logger.info(f"  full development run {name}")
    rets1 = dev_returns(cfg, m["adj"], 1)
    sc_all = pd.read_parquet(Path(cfg["paths"]["processed_factors"]) / "momentum_scores.parquet")
    sc_all = sc_all[(sc_all["period"] == "development") & sc_all["eligible"]]
    ics = {s: monthly_ic(sc_all, rets1, s) for s in cfg["walkforward"]["signals"]}
    fold_rows, stitched, entry = (
        [],
        {k: [] for k in ["selection", "primary", "quarterly", "equal_weight"]},
        [],
    )
    for f in folds(cfg):
        if only_fold and f["fold"] != only_fold:
            continue
        train_months = months_between(*f["train"])
        tab = train_table(cfg, full, ics, train_months)
        best = choose(cfg, tab)
        chosen = params[best["name"]]
        test = f["test"]
        test_rets = {}
        for key, p in [
            ("selection", chosen),
            ("primary", PRESETS["primary"]),
            ("quarterly", PRESETS["quarterly"]),
            ("equal_weight", PRESETS["equal_weight"]),
        ]:
            run = simulate(cfg, m, p, sc, months=test)
            r = period_returns(cfg, run["equity"]["equity"], months=test)
            test_rets[key] = r
            stitched[key].append(r)
            first = run["trades"]["date"].min()
            entry.append(
                dict(
                    fold=f["fold"],
                    strategy=key,
                    entry_cost_pct=run["trades"].loc[run["trades"]["date"] == first, "total"].sum()
                    / cfg["backtest"]["capital"],
                    turnover=window_turnover(
                        run,
                        run["equity"].index[0],
                        run["equity"].index[-1],
                        len(r) / 12,
                    ),
                )
            )
        sd = signal_dates(cfg)
        fold_rows.append(
            dict(
                fold=f["fold"],
                train_first=f["train"][0],
                train_last=f["train"][1],
                embargo=",".join(f["embargo"]),
                test_first=test[0],
                test_last=test[1],
                test_months=len(test_rets["selection"]),
                chosen=best["name"],
                signal=chosen["signal"],
                n=chosen["n"],
                rebalance=chosen["rebalance"],
                is_sharpe=best["sharpe"],
                oos_sharpe=sharpe(test_rets["selection"], rf_m),
                train_ic=best["ic"],
                primary_oos_sharpe=sharpe(test_rets["primary"], rf_m),
                oos_ic=ics[chosen["signal"]]
                .reindex(pd.to_datetime(sd.loc[months_between(*test), "signal_date"]))
                .mean(),
            )
        )
        logger.info(
            f"  fold {f['fold']}: train {f['train'][0]}..{f['train'][1]}, test "
            f"{test[0]}..{test[1]}, chose {best['name']}"
        )
    folds_df = pd.DataFrame(fold_rows)
    stitched = {k: pd.concat(v) for k, v in stitched.items()}
    if only_fold:
        return folds_df, stitched
    folds_df.to_csv(out / "folds.csv", index=False)
    pd.DataFrame(stitched).to_csv(out / "stitched_returns.csv")
    pd.DataFrame(entry).to_csv(out / "entry_costs.csv", index=False)
    # full-development statistics per combination (for the deflated Sharpe and the frozen config)
    full_tab = train_table(cfg, full, ics, list(full[next(iter(full))]["returns"].index))
    full_tab.to_csv(out / "grid_full_development.csv", index=False)
    # per-month IC of the selection's chosen signal on its test months
    sd = signal_dates(cfg)
    sel_ic = pd.concat(
        [
            ics[r["signal"]].reindex(
                pd.to_datetime(
                    sd.loc[months_between(r["test_first"], r["test_last"]), "signal_date"]
                )
            )
            for _, r in folds_df.iterrows()
        ]
    )
    sel_ic.to_csv(out / "selection_ic.csv")
    return folds_df, stitched, full_tab, full, ics, entry


def summarise_oos(cfg: dict, stitched: pd.DataFrame, sel_ic, entry) -> pd.DataFrame:
    """Out-of-sample summary of the stitched test months."""
    lags = cfg["diagnostics"]["newey_west_lags"]
    rf_m = (1 + cfg["backtest"]["risk_free"]) ** (1 / 12) - 1
    n500, _ = index_returns(
        cfg,
        cfg["prices"]["indices"][0],
        months=(stitched["selection"].index[0], stitched["selection"].index[-1]),
    )
    rows = []
    ent = pd.DataFrame(entry)
    for k, r in list(stitched.items()) + [
        ("NIFTY 500 TRI (index)", n500.reindex(stitched["selection"].index))
    ]:
        eq = (1 + r).cumprod()
        d = r - stitched["equal_weight"]
        row = dict(
            strategy=k,
            months=len(r),
            cagr=eq.iloc[-1] ** (12 / len(r)) - 1,
            sharpe=sharpe(r, rf_m),
            max_drawdown_monthly=(eq / eq.cummax() - 1).min(),
        )
        if k in stitched:
            row.update(
                turnover=ent[ent["strategy"] == k]["turnover"].mean(),
                entry_cost_pct=ent[ent["strategy"] == k]["entry_cost_pct"].mean(),
            )
        if k != "equal_weight":
            row.update(
                diff_vs_ew=d.mean(),
                diff_nw_t=nw_t(d, lags),
                diff_share_positive=(d > 0).mean(),
            )
        rows.append(row)
    out = pd.DataFrame(rows)
    out.loc[out["strategy"] == "selection", "mean_ic"] = sel_ic.mean()
    out.loc[out["strategy"] == "selection", "ic_nw_t"] = nw_t(sel_ic, lags)
    return out


def frozen_choice(cfg: dict, full_tab: pd.DataFrame) -> tuple:
    """The configuration frozen for the holdout, chosen on all development data."""
    best = choose(cfg, full_tab)
    g = {x["name"]: x for x in grid(cfg)}[best["name"]]
    return g, best


def run_checks(cfg: dict) -> list:
    """Walk-forward checks: no fold trains on its test months."""
    from momentum.transform.backtest import end_date

    out = Path(cfg["paths"]["results"]) / "phase4"
    fd = pd.read_csv(out / "folds.csv")
    sd = signal_dates(cfg)
    results = []
    leak = 0
    for _, f in fd.iterrows():
        train_end = end_date(
            cfg, (f["train_first"], f["train_last"])
        )  # last training return ends here
        test_start = sd.loc[f["test_first"], "execution_date"]
        leak += int(test_start < train_end)
    results.append(
        (
            "walk-forward: no test period or return window inside its training window",
            leak == 0,
            f"{leak} overlaps in {len(fd)} folds",
        )
    )
    gaps = [
        len(pd.period_range(f["train_last"], f["test_first"], freq="M")) - 2
        for _, f in fd.iterrows()
    ]
    results.append(
        (
            "walk-forward: embargo respected",
            all(g == cfg["walkforward"]["embargo_months"] for g in gaps),
            f"months between train end and test start: {sorted(set(gaps))}",
        )
    )
    last = cfg["split"]["last_dev_month"]
    bad = int(((fd["test_last"] > last) | (fd["train_last"] > last)).sum())
    results.append(
        (
            "walk-forward: no holdout month in any fold",
            bad == 0,
            f"latest test month {fd['test_last'].max()}",
        )
    )
    f1 = int(fd["fold"].iloc[0])
    again, stitched = run_walkforward(cfg, only_fold=f1)
    saved = pd.read_csv(out / "stitched_returns.csv", index_col=0)
    a = stitched["selection"].values
    b = saved["selection"].iloc[: len(a)].values
    same = again["chosen"].iloc[0] == fd["chosen"].iloc[0] and np.allclose(a, b)
    results.append(
        (
            "walk-forward: determinism (fold rerun gives the same choice and returns)",
            same,
            f"fold {f1}: {again['chosen'].iloc[0]}",
        )
    )
    return results
