from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from optsell import backtest as bt
from optsell import census, data, report
from optsell import phase2 as p2
from optsell import phase3 as p3
from optsell import phase4 as p4

matplotlib.use("Agg")
logger = logging.getLogger(__name__)

OUT = Path("results/phase5")
CYC = "2023-05-26"


def write_round(df, path, drop, dec) -> pd.DataFrame:
    """Write a frame with rounded numbers."""
    out = df.drop(columns=[c for c in drop if c in df])
    num = out.select_dtypes("number").columns
    out[num] = out[num].round(dec)
    out.to_csv(path, index=False)
    return pd.read_csv(path)


def compare(old, new, key, ret, label, extra=None) -> tuple:
    """Compare monthly rows before and after the relabel fix."""
    lines, bad = [], []
    o = old.copy()
    n = new.copy()
    for d in (o, n):
        d["entry_date"] = pd.to_datetime(d[key]).dt.date.astype(str)
    for rule in dict.fromkeys(o.rule):
        for period in dict.fromkeys(o[o.rule == rule].period):
            a = o[(o.rule == rule) & (o.period == period)].set_index("entry_date")
            b = n[(n.rule == rule) & (n.period == period)].set_index("entry_date")
            if len(a) != len(b) or list(a.index) != list(b.index):
                bad.append(f"{label} {rule} {period}: cycle lists differ")
                continue
            pre = a.index < CYC
            post = a.index > CYC
            d_pre = (a[ret][pre] - b[ret][pre]).abs().max() if pre.any() else 0.0
            d_post = (a[ret][post] - b[ret][post]).abs()
            flips = [
                i
                for i in a.index[post]
                if str(a.at[i, "skipped"]) != str(b.at[i, "skipped"])
                or (
                    "stop_triggered" in a
                    and str(a.at[i, "stop_triggered"]) != str(b.at[i, "stop_triggered"])
                )
            ]
            row = None
            if CYC in a.index:
                ra, rb = a.loc[CYC], b.loc[CYC]
                skipped_before = str(ra["skipped"]) in ("yes", "True") or (
                    isinstance(ra["skipped"], str) and ra["skipped"] not in ("", "no")
                )
                skipped_after = str(rb["skipped"]) in ("yes",) or (
                    isinstance(rb["skipped"], str) and rb["skipped"] not in ("", "no")
                )
                skip_reason = ra.get("skip_reason", ra.get("skipped"))
                before = f"skipped ({skip_reason})" if skipped_before else "traded"
                row = (
                    "before: "
                    f"{before}, "
                    f"{ra[ret]:+.3f}%; after: "
                    f"{rb.get('legs', '') if isinstance(rb.get('legs', ''), str) else ''} "
                    f"{'skipped' if skipped_after else 'traded'}, "
                    f"{rb[ret]:+.3f}%"
                )
            ok_pre = d_pre < 0.006
            expl = ""
            if flips and extra is not None:
                thr_changed = [
                    i
                    for i in flips
                    if extra in a and abs(float(a.at[i, extra]) - float(b.at[i, extra])) > 1e-9
                ]
                expl = (
                    f"; {len(thr_changed)} of {len(flips)} decision changes coincide with a "
                    "changed expanding threshold"
                )
                ok_flip = len(thr_changed) == len(flips)
            else:
                ok_flip = not flips
            ok_post = (d_post.max() if len(d_post) else 0.0) < 0.006 or (flips and ok_flip)
            status = "OK" if ok_pre and ok_post and ok_flip else "**UNEXPECTED**"
            if status != "OK":
                bad.append(f"{label} {rule} {period}")
            lines.append(
                f"| {label} | {rule} | {period} | {row or 'cycle not in period'} | {d_pre:.4f} | "
                f"{(d_post.max() if len(d_post) else 0.0):.4f} | {len(flips)}{expl} | {status} |"
            )
    return lines, bad


def summary_diff(old, new, key, cols, label) -> list:
    """Fields of the summary rows that changed with the fix."""
    o = old.set_index(key)
    n = new.set_index(key)
    rows = []
    for k in o.index:
        if k not in n.index:
            continue
        diff = {
            c: (o.loc[k, c], n.loc[k, c])
            for c in cols
            if c in o
            and pd.notna(o.loc[k, c])
            and isinstance(o.loc[k, c], (int, float, np.floating, np.integer))
            and abs(float(o.loc[k, c]) - float(n.loc[k, c])) > 1e-9
        }
        rows.append(
            f"| {label} | {k} | "
            + ("; ".join(f"{c}: {a:.4f} -> {b:.4f}" for c, (a, b) in diff.items()) or "unchanged")
            + " |"
        )
    return rows


def bugfix(cfg: dict) -> None:
    """Recompute every phase with the June 2023 relabel fix into *_bugfix.csv."""
    OUT.mkdir(parents=True, exist_ok=True)
    table, bad, summ = [], [], []
    logger.info("phase 1")
    opt, ix, cyc = bt.load_all(cfg)
    dev = cyc[cyc.period == "dev"].reset_index(drop=True)
    new_t = {r: bt.simulate(r, dev, opt, ix, cfg, cfg["cash_rate"]) for r in bt.RULES}
    old_t = {
        r: pd.read_csv(f"results/trades_{r}.csv", parse_dates=["entry", "expiry", "next_entry"])
        for r in bt.RULES
    }
    for r in bt.RULES:
        new_t[r].to_csv(f"results/trades_{r}_bugfix.csv", index=False)
        old_t[r]["skipped"] = old_t[r].skipped.fillna("")
    so = bt.summarise(old_t, dev, ix, cfg, cfg["cash_rate"])
    sn = bt.summarise(new_t, dev, ix, cfg, cfg["cash_rate"])
    sn.to_csv("results/summary_dev_bugfix.csv")

    def f(t, r):
        return t.assign(rule=r, period="dev", ret_pct=100 * t.ret, entry_date=t.entry)

    leg, b = compare(
        pd.concat([f(old_t[r], r) for r in bt.RULES]),
        pd.concat([f(new_t[r], r) for r in bt.RULES]),
        "entry_date",
        "ret_pct",
        "phase1",
    )
    table += leg
    bad += b
    summ += summary_diff(
        so.reset_index(),
        sn.reset_index(),
        "index",
        ["CAGR", "Sharpe", "MaxDD", "Worst month", "CVaR99", "Win rate"],
        "phase1 dev",
    )

    logger.info("phase 2")
    ctx = p2.load(cfg)
    parts = []
    for period in ("design", "validation"):
        df, _, _ = p2.run_period(cfg, ctx, period)
        s = p2.summarise(df, cfg, p2.trial_srs(df, cfg, ctx, period))
        s.to_csv(f"results/phase2/summary_{period}_bugfix.csv", index=False)
        summ += summary_diff(
            pd.read_csv(f"results/phase2/summary_{period}.csv"),
            s,
            "variant",
            [
                "option CAGR",
                "option Sharpe",
                "worst month",
                "CVaR99",
                "win rate",
                "skipped",
                "fallback",
                "DSR",
            ],
            f"phase2 {period}",
        )
        parts.append(df)
    new = write_round(
        pd.concat(parts, ignore_index=True),
        "results/phase2/monthly_pnl_phase2_bugfix.csv",
        ["next_entry"],
        2,
    )
    leg, b = compare(
        pd.read_csv("results/phase2/monthly_pnl_phase2.csv"),
        new,
        "entry_date",
        "option_return_on_capital_pct",
        "phase2",
    )
    table += leg
    bad += b

    logger.info("phase 3")
    parts = []
    for period in ("design", "validation"):
        c3, gp = p3.ctx_for(cfg, period)
        df, _ = p3.run_period(cfg, c3, period, gp)
        s, _ = p3.summarise(df, cfg, p3.trial_srs(cfg, c3, period, df))
        s.to_csv(f"results/phase3/summary_{period}_bugfix.csv", index=False)
        summ += summary_diff(
            pd.read_csv(f"results/phase3/summary_{period}.csv"),
            s,
            "variant",
            [
                "option CAGR",
                "option Sharpe",
                "worst month",
                "CVaR99",
                "win rate",
                "months traded",
                "months filtered",
                "stops",
                "DSR",
            ],
            f"phase3 {period}",
        )
        parts.append(df)
    allp = pd.concat(parts, ignore_index=True)
    p3.write_csv(allp, Path("results/phase3/monthly_pnl_phase3_bugfix.csv"))
    leg, b = compare(
        pd.read_csv("results/phase3/monthly_pnl_phase3.csv"),
        pd.read_csv("results/phase3/monthly_pnl_phase3_bugfix.csv"),
        "entry_date",
        "option_return_on_capital_pct",
        "phase3",
        extra="filter_threshold",
    )
    table += leg
    bad += b

    logger.info("census")
    cx = census.load(cfg)
    parts = []
    for period in ("design", "validation"):
        df, cy, _ = census.run_period(cfg, cx, period)
        s = census.summarise(df, cy, cfg, census.trial_srs(cfg, cx, period, df))
        s.to_csv(f"results/census/summary_{period}_bugfix.csv", index=False)
        summ += summary_diff(
            pd.read_csv(f"results/census/summary_{period}.csv"),
            s,
            "strategy",
            [
                "option CAGR",
                "option Sharpe",
                "worst month",
                "CVaR99",
                "win rate",
                "months traded",
                "stops",
                "DSR",
            ],
            f"census {period}",
        )
        parts.append(df)
    census.write_csv(
        pd.concat(parts, ignore_index=True), Path("results/census/monthly_pnl_census_bugfix.csv")
    )
    old = pd.read_csv("results/census/monthly_pnl_census.csv")
    newc = pd.read_csv("results/census/monthly_pnl_census_bugfix.csv")
    leg, b = compare(
        old[old.rule != "ref_e1f1"],
        newc[newc.rule != "ref_e1f1"],
        "entry_date",
        "option_return_on_capital_pct",
        "census",
    )
    table += leg
    bad += b
    leg, b = compare(
        old[old.rule == "ref_e1f1"],
        newc[newc.rule == "ref_e1f1"],
        "entry_date",
        "option_return_on_capital_pct",
        "census",
    )
    table += [
        x
        + (
            " (e1f1 reference: decision changes come from its expanding filter threshold, checked "
            "in phase3)"
        )
        for x in leg
    ]
    bad += [x for x in b if "cycle lists" in x]

    logger.info("phase 4")
    c4 = p4.load_insample(cfg)
    parts = []
    for period in ("design", "validation"):
        df, sdf, cy = p4.period_runs(cfg, c4, period, sens=True)
        main = df[~df.rule.str.startswith("sens_")]
        s = p4.summarise(main, cy, cfg, p4.trial_srs(cfg, c4, period, main))
        ss = p4.summarise(sdf[~sdf.rule.str.startswith("sens_")], cy, cfg)
        both = pd.concat([s.assign(costs="normal"), ss.assign(costs="stress")])
        both.to_csv(f"results/phase4/summary_{period}_bugfix.csv", index=False)
        o = pd.read_csv(f"results/phase4/summary_{period}.csv")
        for c in ("normal", "stress"):
            summ += summary_diff(
                o[o.costs == c],
                both[both.costs == c],
                "rule",
                [
                    "option CAGR",
                    "Sharpe all months",
                    "worst month",
                    "CVaR99",
                    "months traded",
                    "stops",
                    "DSR",
                ],
                f"phase4 {period} {c}",
            )
        parts.append(df)
    p4.write4(pd.concat(parts, ignore_index=True), p4.OUT / "monthly_pnl_phase4_bugfix.csv")
    o = pd.read_csv("results/phase4/monthly_pnl_phase4.csv")
    o = o[o.period != "holdout"]
    nb = pd.read_csv("results/phase4/monthly_pnl_phase4_bugfix.csv")
    leg, b = compare(
        o[o.rule != "ref_e1f1"],
        nb[nb.rule != "ref_e1f1"],
        "entry_date",
        "option_return_on_capital_pct",
        "phase4",
    )
    table += leg
    bad += b
    leg, b = compare(
        o[o.rule == "ref_e1f1"],
        nb[nb.rule == "ref_e1f1"],
        "entry_date",
        "option_return_on_capital_pct",
        "phase4",
    )
    table += [x + " (e1f1: see phase3)" for x in leg]

    for log in (
        "results/phase2/validation_runs.log",
        "results/phase3/validation_runs.log",
        "results/census/validation_runs.log",
    ):
        with open(log, "a") as fh:
            fh.write(
                f"{datetime.now():%Y-%m-%d %H:%M:%S} bugfix recompute (June 2023 relabel), not a "
                "new run\n"
            )
    md = (
        [
            "# Phase 5 fixes: June 2023 contract relabel\n",
            "**Cause.** NSE renamed the June 2023 monthly contract (2023-06-29 -> 2023-06-28) on "
            "2023-06-28, after the 2023-05-26 "
            "entry. The cycle builder looked up the settled label, which had no rows on the entry "
            "day, so the cycle was skipped.\n",
            "**Fix.** `data.relabel` maps every label that NSE renamed mid-life to the label the "
            "contract finally settled under "
            "(same calendar month, the old label stops trading the day before the new one starts). "
            "On the entry day the target is "
            "therefore the next month's monthly contract as listed that day, and that same "
            "contract is followed (marks, stops, "
            "settlement) to its actual last trading day. Labels whose contract simply expired "
            "early for a holiday (Dec 2008, "
            "Apr 2009, Apr 2014) are not relabels and are unchanged.\n",
            "**Relabels found (old -> settled label, last day of the old label):** "
            + ", ".join(
                f"{k.date()} -> {v.date()}"
                for k, v in data.relabels(
                    pd.read_parquet("data/processed/nifty_fo.parquet")
                ).items()
            )
            + ". Only the June 2023 one falls inside a held cycle (entry 2023-05-26); "
            "the others happen before the relevant entry "
            "(or affect only holdout contracts, which this recompute does not touch). The S9 far "
            "leg already used the month-based lookup.\n",
            "**Recompute.** `python scripts/run.py bugfix-recompute` recomputes design and "
            "validation for every rule; results are in "
            "`*_bugfix.csv` next to the committed files; the logged validation and holdout runs "
            "were not re-run, and one line was "
            "appended to each validation log. Deflated Sharpe in the `_bugfix` summaries uses the "
            "other phases' committed trial "
            "Sharpe values for the trial variance.\n",
            "## Per rule: the 2023-05-26 cycle and the rows around it\n",
            "Max |diff| = largest change in monthly return (percentage points) before the cycle "
            "and after it (after it, units scale "
            "with the new capital and a Rs 20 brokerage is fixed, so tiny differences are "
            "expected). Decision changes after the cycle "
            "are allowed only where an expanding filter threshold now includes that cycle.\n",
            "| phase | rule | period | 2023-05-26 cycle | max diff before | max diff after | "
            "decision changes after | status |",
            "|---|---|---|---|---|---|---|---|",
        ]
        + table
        + [
            "",
            f"**Unexpected changes: {len(bad)}**" + (" - " + "; ".join(bad) if bad else ""),
            "",
            "## Summary rows: old -> new (fields that changed)\n",
            "| phase | rule | changes |",
            "|---|---|---|",
        ]
        + summ
    )
    (OUT / "fixes2.md").write_text("\n".join(md) + "\n")
    logger.info("\n".join(md[-len(summ) - 6 :]))
    logger.warning("UNEXPECTED: %s", bad)


EXTRA5 = [
    "prem_ratio",
    "action",
    "traded",
    "stop_triggered",
    "trigger_date",
    "exit_date",
    "exit_cost",
    "pnl_if_held",
    "stop_effect",
    "hedge_strike",
    "hedge_units",
    "hedge_cost",
    "hedge_payoff",
    "hedge_note",
    "buy_debit",
    "buy_payoff",
    "spread_credit_net",
    "fallback_used",
]


def variants5(cfg: dict, sens=False) -> dict:
    """Tail hedges on P1 and e1f1, and the mirror rule."""
    c = cfg["phase5"]
    pm = cfg["phase4"]["prem_min"]
    base = {"prem": None, "ivrv": False, "stop": None, "hedge": None, "buy_below": None}
    v = {
        "ref_p1": {**base, "prem": pm},
        "ref_e1f1": {**base, "ivrv": True, "stop": "credit"},
        "ref_base": dict(base),
        "h1a": {**base, "prem": pm, "hedge": c["hedge_budget"]},
        "h1b": {**base, "ivrv": True, "stop": "credit", "hedge": c["hedge_budget"]},
        "h2": {**base, "prem": pm, "buy_below": c["buy_below"]},
    }
    if sens:
        for b in c["hedge_sens"]:
            v[f"sens_h1a_{b:.2f}"] = {**base, "prem": pm, "hedge": b}
        for t in c["buy_sens"]:
            v[f"sens_h2_{t:.2f}"] = {**base, "prem": pm, "buy_below": t}
    return v


def leg_of(r, o, side) -> dict:
    """A leg record from a chain row."""
    return {
        "opt": o,
        "side": side,
        "q": 1,
        "k": float(r.strike),
        "close": float(r.close),
        "volume": float(r.volume),
        "lot": r.lot,
    }


def run5(name, v, cyc, ctx, cfg: dict, period, mk) -> pd.DataFrame:
    """Run one Phase 5 rule over a period's cycles."""
    cc, c5 = cfg["costs"], cfg["phase5"]
    rate = cfg["cash_rate"]
    capital = peak = cfg["capital"]
    rows = []
    for n, c in enumerate(cyc.itertuples(), 1):
        s0 = float(ctx["ix"].close[c.entry])
        m = mk.loc[c.entry]
        days_total = (c.next_entry - c.entry).days
        row = {
            "rule": name,
            "period": period,
            "cycle_no": n,
            "entry_date": c.entry.date(),
            "expiry_date": c.expiry.date(),
            "days_to_expiry": (c.expiry - c.entry).days,
            "index_at_entry": s0,
            "index_at_expiry": c.settle,
            "index_move_pct": 100 * (c.settle / s0 - 1),
            "india_vix_at_entry": m.vix * 100 if pd.notna(m.vix) else np.nan,
            "atm_iv_at_entry_pct": 100 * m.iv,
            "realised_vol_pct": 100 * m.rv,
            "iv_minus_future_rv_pts": 100 * m.vrp,
            "capital_start": capital,
            "nifty_tri_return_pct": 100 * c.tri_ret,
            "next_entry": c.next_entry,
            "stop_triggered": "no",
            "traded": "no",
            "action": "cash",
            "fallback_used": "no",
        }
        ch = census.chain(ctx, c.entry, c.contract)
        legs, fb, why = p4.pick(p4.PS, ch, s0, cfg)
        prem = (
            (legs[0]["close"] - legs[1]["close"]) / (legs[0]["k"] - legs[1]["k"])
            if legs
            else np.nan
        )
        row["prem_ratio"] = prem
        act = "sell"
        if legs is None:
            act = "cash"
        elif v["buy_below"] is not None and prem < v["buy_below"]:
            act = "buy"
        elif v["prem"] is not None and prem < v["prem"]:
            act, why = (
                "cash",
                f"filtered: prem_ratio {prem:.3f} between thresholds"
                if v["buy_below"] is not None
                else f"filtered: prem_ratio {prem:.3f} < {v['prem']:.2f}",
            )
        if act == "sell" and v["ivrv"]:
            g = ctx["gp"].loc[c.entry]
            if pd.notna(g.gap) and pd.notna(g.threshold) and g.gap <= g.threshold:
                act, why = "cash", "filtered: IV - RV gap not above the expanding median"
        pos, margin, held_days, plan = [], 0.0, days_total, np.nan
        if act == "sell":
            p4.fill(legs, cc, 1.0)
            credit = sum(-leg["side"] * leg["px"] for leg in legs)
            maxloss = (legs[0]["k"] - legs[1]["k"]) - credit
            units = cfg["max_loss_pct"] * capital / maxloss
            margin = plan = units * maxloss
            row["spread_credit_net"] = units * credit
            for leg in legs:
                pos.append({**leg, "units": units, "role": "spread"})
            if v["hedge"] is not None:
                r, f = p2.pick_money(ch, "P", c5["hedge_moneyness"] * s0, cfg, "fallback")
                if r is None:
                    row["hedge_note"] = "no traded 0.85 put: unhedged"
                else:
                    h = leg_of(r, "P", 1)
                    p4.fill([h], cc, 1.0)
                    hu = v["hedge"] * units * credit / h["px"]
                    pos.append({**h, "units": hu, "role": "hedge"})
                    row.update(
                        {"hedge_strike": h["k"], "hedge_units": hu, "hedge_cost": hu * h["px"]}
                    )
        elif act == "buy":
            b = [{**legs[0], "side": 1}, {**legs[1], "side": -1}]
            p4.fill(b, cc, 1.0)
            debit = b[0]["px"] - b[1]["px"]
            f1 = p3.fees(
                [(c.entry, b[0]["px"], 1.0, False), (c.entry, b[1]["px"], 1.0, True)], 0.0, cc
            )
            f0 = p3.fees(
                [(c.entry, b[0]["px"], 0.0, False), (c.entry, b[1]["px"], 0.0, True)], 0.0, cc
            )
            var = sum(f1.values()) - sum(f0.values())
            units = (c5["buy_debit"] * capital - sum(f0.values())) / (debit + var)
            for leg in b:
                pos.append({**leg, "units": units, "role": "buy"})
            margin = units * debit
            row["buy_debit"] = units * debit + sum(
                p3.fees(
                    [(c.entry, leg["px"], units, leg["side"] < 0) for leg in b], 0.0, cc
                ).values()
            )
        if not pos:
            interest = rate * capital * days_total / 365
            row.update(
                {
                    "skipped": "yes",
                    "skip_reason": why,
                    "units": 0.0,
                    "margin_used": 0.0,
                    "notional": 0.0,
                    "margin_pct_of_capital": 0.0,
                    "idle_cash": capital,
                    "credit_gross": 0.0,
                    "slippage_cost": 0.0,
                    "settlement_payout": 0.0,
                    "cash_interest": interest,
                    "outcome": "skipped",
                    "win": "no",
                    **dict.fromkeys(p3.ITEMS, 0.0),
                }
            )
        else:
            sp = [p for p in pos if p["role"] != "hedge"]
            u = sp[0]["units"]

            def held(c=c, pos=pos):
                return sum(
                    p["side"] * bt.intrinsic("P", p["k"], c.settle) * p["units"] for p in pos
                )

            entry_fills = [(c.entry, p["px"], p["units"], p["side"] < 0) for p in pos]
            itm_all = sum(
                bt.intrinsic("P", p["k"], c.settle) * p["units"] for p in pos if p["side"] > 0
            )
            it = p3.fees(entry_fills, itm_all, cc)
            row["pnl_if_held"] = (
                sum(-p["side"] * p["px"] * p["units"] for p in pos) + held() - sum(it.values())
            )
            if v["stop"] and act == "sell":
                days = ctx["days"][(ctx["days"] >= c.entry) & (ctx["days"] <= c.expiry)]
                s = p4.stop_exit({"stop": v["stop"]}, sp, u, credit, c, days, ctx, cfg, 1.0)
                if s:
                    for p, x in zip(sp, s["legs"], strict=False):
                        p["exit"] = x
                    held_days = (s["exit"] - c.entry).days
                    row.update(
                        {
                            "stop_triggered": "yes",
                            "trigger_date": s["trigger"].date(),
                            "exit_date": s["exit"].date(),
                        }
                    )
            fills = list(entry_fills)
            itm = 0.0
            payout_val = 0.0
            slip = sum(p["slip"] * p["units"] for p in pos)
            for p in pos:
                if "exit" in p:
                    x = p["exit"]
                    fills.append((x["date"], x["px"], p["units"], p["side"] > 0))
                    slip += x["slip"] * p["units"]
                    payout_val += p["side"] * x["close"] * p["units"]
                else:
                    val = bt.intrinsic("P", p["k"], c.settle)
                    payout_val += p["side"] * val * p["units"]
                    if p["side"] > 0:
                        itm += val * p["units"]
            it = p3.fees(fills, itm, cc)
            interest = rate * (capital * days_total - margin * held_days) / 365
            if row["stop_triggered"] == "yes":
                opt_net = (
                    sum(-p["side"] * p["close"] * p["units"] for p in pos)
                    - slip
                    + payout_val
                    - sum(it.values())
                )
                entry_only = p3.fees(entry_fills, 0.0, cc)
                row["exit_cost"] = (
                    sum(p["exit"]["slip"] * p["units"] for p in sp)
                    + sum(it.values())
                    - sum(entry_only.values())
                )
                row["stop_effect"] = "helped" if opt_net > row["pnl_if_held"] else "hurt"
            for p in pos:
                if p["role"] == "hedge":
                    row["hedge_payoff"] = bt.intrinsic("P", p["k"], c.settle) * p["units"]
                    continue
                nm = report.LEGS[("S" if p["side"] < 0 else "B", "P")]
                row[f"{nm}_strike"] = p["k"]
                row[f"{nm}_entry_price"] = p["close"]
                row[f"{nm}_settle_value"] = bt.intrinsic("P", p["k"], c.settle)
                if p["side"] < 0:
                    row[f"{nm}_contracts_traded"] = p["volume"]
                    row["lot_size"] = p["lot"]
                    row["lots"] = np.floor(p["units"] / p["lot"]) if pd.notna(p["lot"]) else np.nan
            if act == "buy":
                row["buy_payoff"] = sum(
                    p["side"] * bt.intrinsic("P", p["k"], c.settle) * p["units"] for p in pos
                )
            row.update(
                {
                    "traded": "yes",
                    "skipped": "no",
                    "skip_reason": "",
                    "action": act,
                    "fallback_used": "yes" if fb else "no",
                    "units": u,
                    "notional": u * s0,
                    "margin_used": margin,
                    "margin_pct_of_capital": 100 * margin / capital,
                    "idle_cash": max(0.0, capital - margin),
                    "max_loss_planned": plan,
                    "credit_gross": sum(-p["side"] * p["close"] * p["units"] for p in pos),
                    "slippage_cost": slip,
                    "settlement_payout": -payout_val + 0.0,
                    "cash_interest": interest,
                    **{k: it[k] for k in p3.ITEMS},
                }
            )
        row["credit_net"] = row["credit_gross"] - row["slippage_cost"]
        row["option_pnl_before_charges"] = row["credit_net"] - row["settlement_payout"]
        row["total_charges"] = sum(row[k] for k in p3.ITEMS)
        row["total_costs"] = row["slippage_cost"] + row["total_charges"]
        row["costs_pct_of_credit_gross"] = (
            100 * row["total_costs"] / abs(row["credit_gross"]) if row["credit_gross"] else np.nan
        )
        row["option_pnl_net"] = row["option_pnl_before_charges"] - row["total_charges"]
        row["total_pnl"] = row["option_pnl_net"] + row["cash_interest"]
        row["capital_end"] = capital + row["total_pnl"]
        row["return_on_capital_pct"] = 100 * row["total_pnl"] / capital
        row["option_return_on_capital_pct"] = 100 * row["option_pnl_net"] / capital
        row["return_on_margin_pct"] = (
            100 * row["option_pnl_net"] / row["margin_used"] if row["margin_used"] else np.nan
        )
        if row["traded"] == "yes":
            row["win"] = "yes" if row["option_pnl_net"] > 0 else "no"
            row["outcome"] = (
                "stopped"
                if row["stop_triggered"] == "yes"
                else "full profit"
                if row["settlement_payout"] <= 0
                else "max loss"
                if pd.notna(plan) and row["option_pnl_before_charges"] <= -plan + 1
                else "partial loss"
            )
        capital = row["capital_end"]
        peak = max(peak, capital)
        row["cumulative_pnl"] = capital - cfg["capital"]
        row["drawdown_from_peak_pct"] = 100 * (capital / peak - 1)
        rows.append(row)
    df = pd.DataFrame(rows)
    for col in report.COLS + EXTRA5:
        if col not in df:
            df[col] = np.nan
    return df[report.COLS + EXTRA5 + ["next_entry"]]


def period5(cfg: dict, ctx, period) -> tuple:
    """Run every Phase 5 rule on one period."""
    cyc = ctx["cyc"][ctx["cyc"].period == period].reset_index(drop=True)
    cyc["tri_ret"] = bt.tri_returns(cyc, ctx["ix"])
    mk = bt.vrp_table(ctx["opt"], ctx["ix"], cyc, cfg).set_index("entry")
    out = []
    for n, v in variants5(cfg, sens=True).items():
        out.append(run5(n, v, cyc, ctx, cfg, period, mk))
        logger.info(f"  {period} {n}: done")
    s7 = p4.run("ref_s7_e1", p4.variants(cfg)["ref_s7_e1"], cyc, ctx, cfg, period, mk)
    s7["action"] = s7.traded.map({"yes": "sell", "no": "cash"})
    out.append(s7)
    df = pd.concat(out, ignore_index=True)
    for c in EXTRA5:
        if c not in df:
            df[c] = np.nan
    return df[report.COLS + EXTRA5 + ["next_entry"]], cyc


def srs38(cfg: dict, ctx, period, df) -> dict:
    """Monthly Sharpe of all 38 trials."""
    cyc = ctx["cyc"][ctx["cyc"].period == period].reset_index(drop=True)
    srs = {}
    for rule in bt.RULES:
        t = p2.simulate(
            {"name": rule, "kind": "ref", "rule": rule, "skip": "phase1"},
            cyc,
            ctx,
            cfg,
            cfg["cash_rate"],
            mark=False,
        )
        ro = (t.net - t.interest) / t.capital_before
        srs[f"phase1_{rule}"] = ro.mean() / ro.std()
    for f, key, names in (
        (f"results/phase2/summary_{period}_bugfix.csv", "variant", cfg["phase2"]["variants"]),
        (f"results/phase3/summary_{period}_bugfix.csv", "variant", cfg["phase3"]["variants"]),
        (
            f"results/census/summary_{period}_bugfix.csv",
            "strategy",
            census.strategies(cfg, refs=False),
        ),
    ):
        t = pd.read_csv(f).set_index(key)
        for n in names:
            srs[f"{Path(f).parent.name}_{n}"] = t.loc[n, "SR monthly"]
    t = pd.read_csv(f"results/phase4/summary_{period}_bugfix.csv")
    t = t[t.costs == "normal"].set_index("rule")
    for n in cfg["phase4"]["variants"]:
        srs[f"phase4_{n}"] = t.loc[n, "SR monthly"]
    for n in ("h1a", "h1b", "h2"):
        ro = df[df.rule == n].option_return_on_capital_pct
        srs[f"phase5_{n}"] = ro.mean() / ro.std()
    return srs


def summarise5(df, cyc, cfg: dict, srs=None) -> pd.DataFrame:
    """Summary statistics and deflated Sharpe of each rule."""
    cy = cyc[["entry", "next_entry"]]
    p1 = df[df.rule == "ref_p1"].option_return_on_capital_pct.values / 100
    e1 = df[df.rule == "ref_e1f1"].option_return_on_capital_pct.values / 100
    rows = []
    for n, g in df.groupby("rule", sort=False):
        ro = g.option_return_on_capital_pct.values / 100
        m = bt.metrics(pd.Series(ro), cy, pd.Series(np.zeros(len(g))))
        tot = bt.metrics(
            pd.Series(g.return_on_capital_pct.values / 100), cy, bt.cash_returns(cy, cfg["rf"])
        )
        tr = g[g.traded == "yes"]
        rt = tr.option_pnl_net / tr.capital_start
        r = {
            "rule": n,
            "trial": "yes" if n in ("h1a", "h1b", "h2") else "no",
            "option CAGR": m["CAGR"],
            "Sharpe all months": m["Sharpe"],
            "worst month": m["Worst month"],
            "worst 3m": m["Worst 3m"],
            "CVaR95": m["CVaR95"],
            "CVaR99": m["CVaR99"],
            "max DD": m["MaxDD"],
            "win rate": (rt > 0).mean() if len(rt) else np.nan,
            "months selling": int((g.action == "sell").sum()),
            "months buying": int((g.action == "buy").sum()),
            "months in cash": int((g.action == "cash").sum()),
            "stops": int((g.stop_triggered == "yes").sum()),
            "costs % gross premium": tr.total_costs.sum() / tr.credit_gross.abs().sum()
            if len(tr)
            else np.nan,
            "total CAGR (cash 6.5%)": tot["CAGR"],
            "NW t vs P1": p3.nw_t(ro - p1, cfg["phase3"]["nw_lags"])[1]
            if n != "ref_p1"
            else np.nan,
            "NW t vs e1f1": p3.nw_t(ro - e1, cfg["phase3"]["nw_lags"])[1]
            if n != "ref_e1f1"
            else np.nan,
        }
        if srs:
            srm = ro.mean() / ro.std()
            r["SR monthly"] = srm
            r["DSR"], r["DSR SR0 (monthly)"] = p2.dsr(
                srm,
                len(ro),
                pd.Series(ro).skew(),
                pd.Series(ro).kurt() + 3,
                np.var(list(srs.values()), ddof=1),
                len(srs),
            )
        rows.append(r)
    return pd.DataFrame(rows)


PCT5 = [
    "option CAGR",
    "worst month",
    "worst 3m",
    "CVaR95",
    "CVaR99",
    "max DD",
    "win rate",
    "costs % gross premium",
    "total CAGR (cash 6.5%)",
    "DSR",
]
MAIN5 = [
    "rule",
    "option CAGR",
    "Sharpe all months",
    "worst month",
    "worst 3m",
    "CVaR95",
    "CVaR99",
    "max DD",
    "win rate",
    "months selling",
    "months buying",
    "months in cash",
    "stops",
    "costs % gross premium",
    "total CAGR (cash 6.5%)",
    "NW t vs P1",
    "NW t vs e1f1",
    "DSR",
]


def fmt5(s, cols) -> pd.DataFrame:
    """Format a summary table for Markdown."""
    d = s[cols].copy()
    for c in cols:
        if c in PCT5:
            d[c] = d[c].map(lambda v: "" if pd.isna(v) else f"{v:.1%}")
        elif d[c].dtype.kind == "f":
            d[c] = d[c].map(lambda v: "" if pd.isna(v) else f"{v:.2f}")
    return d.to_markdown(index=False)


def worst_best(cyc, k=10) -> tuple:
    """The k worst and best NIFTY TRI months."""
    t = pd.Series(cyc.tri_ret.values * 100, index=cyc.entry.dt.date.astype(str))
    return t.nsmallest(k), t.nlargest(k)


def hedge_stats(df, cyc) -> tuple:
    """Cost and payoff of the hedge leg."""
    out, crash = [], []
    w, _ = worst_best(cyc)
    years = (cyc.next_entry.iloc[-1] - cyc.entry.iloc[0]).days / 365.25
    for n in ("h1a", "h1b"):
        g = df[df.rule == n].copy()
        h = g[g.hedge_cost.notna()]
        g["entry_date"] = g.entry_date.astype(str)
        net = (h.hedge_payoff - h.hedge_cost) / h.capital_start
        out.append(
            {
                "rule": n,
                "months hedged": len(h),
                "months the 0.85 put expired in the money": int((h.hedge_payoff > 0).sum()),
                "total paid (Rs)": h.hedge_cost.sum(),
                "total received (Rs)": h.hedge_payoff.sum(),
                "net cost a year, % of capital": -100 * net.sum() / years,
                "unhedged months (no 0.85 put)": int(g.hedge_note.notna().sum()),
            }
        )
        gi = g.set_index("entry_date")
        crash.append(
            pd.Series(
                {
                    d: 100
                    * (gi.at[d, "hedge_payoff"] - gi.at[d, "hedge_cost"])
                    / gi.at[d, "capital_start"]
                    if pd.notna(gi.at[d, "hedge_cost"])
                    else np.nan
                    for d in w.index
                },
                name=n,
            )
        )
    ct = pd.concat(crash, axis=1)
    ct.insert(0, "TRI %", w.values)
    return pd.DataFrame(out), ct


def buy_stats(df) -> tuple:
    """Buy and sell months of the mirror rule."""
    g = df[(df.rule == "h2") & (df.action == "buy")].copy()
    s = df[(df.rule == "h2") & (df.action == "sell")]
    r = g.option_return_on_capital_pct
    stats = {
        "buy months": len(g),
        "paid off (net > 0)": f"{(r > 0).mean():.0%}" if len(g) else "",
        "avg win %": r[r > 0].mean(),
        "avg loss %": r[r <= 0].mean(),
        "total % (sum)": r.sum(),
        "sell months": len(s),
        "sell months total % (sum)": s.option_return_on_capital_pct.sum(),
        "sell months worst %": s.option_return_on_capital_pct.min(),
    }
    top = g.nlargest(5, "buy_payoff")[
        ["entry_date", "index_move_pct", "buy_debit", "buy_payoff", "option_return_on_capital_pct"]
    ]
    return stats, top


def crash_table(df, cyc, period) -> pd.DataFrame:
    """Each rule's result in the worst index months."""
    w, b = worst_best(cyc)
    piv = (
        df[~df.rule.str.startswith("sens_")]
        .assign(entry_date=lambda x: x.entry_date.astype(str))
        .pivot_table(
            index="entry_date", columns="rule", values="option_return_on_capital_pct", sort=False
        )
    )
    a = piv.loc[w.index].assign(case="10 worst TRI months", tri_pct=w.values)
    c = piv.loc[b.index].assign(case="10 best TRI months", tri_pct=b.values)
    return pd.concat([a, c]).assign(period=period)


def by_year(df) -> pd.DataFrame:
    """Option return by year."""
    g = df[~df.rule.str.startswith("sens_")].copy()
    g["year"] = pd.to_datetime(g.entry_date).dt.year
    return (
        g.groupby(["year", "rule"])
        .option_return_on_capital_pct.apply(lambda x: 100 * ((1 + x / 100).prod() - 1))
        .unstack()
    )


def reading5(s, df, hs, bs, period) -> list:
    """Plain-language reading of the Phase 5 results."""
    t = s.set_index("rule")
    p1, e1 = t.loc["ref_p1"], t.loc["ref_e1f1"]
    out = []
    for n, ref, rn in (("h1a", p1, "P1"), ("h1b", e1, "e1f1")):
        h = hs.set_index("rule").loc[n]
        out.append(
            f"- {n} vs {rn}: worst month {t.loc[n, 'worst month']:.1%} vs "
            f"{ref['worst month']:.1%}, CVaR 99% "
            f"{t.loc[n, 'CVaR99']:.1%} vs {ref['CVaR99']:.1%}, option CAGR "
            f"{t.loc[n, 'option CAGR']:.1%} vs "
            f"{ref['option CAGR']:.1%}. The hedge leg cost a net "
            f"{h['net cost a year, % of capital']:.2f}% of capital a year "
            f"and expired in the money in {int(h['months the 0.85 put expired in the money'])} of "
            f"{int(h['months hedged'])} hedged months; "
            + (
                "it reduced the worst month."
                if t.loc[n, "worst month"] > ref["worst month"] + 1e-9
                else "it did not reduce the worst month."
            )
        )
    out.append(
        f"- h2 mirror: {bs['buy months']} buy months, paid off in {bs['paid off (net > 0)']}, buy "
        "months summed to "
        f"{bs['total % (sum)']:+.2f}% of capital (sell months "
        f"{bs['sell months total % (sum)']:+.2f}%). "
        + (
            "The buying earned money overall."
            if bs["total % (sum)"] > 0
            else "The buying bled: it lost money overall."
        )
        + f" h2 option CAGR {t.loc['h2', 'option CAGR']:.1%} vs P1 {p1['option CAGR']:.1%}."
    )
    beat_p1 = [
        n
        for n in ("h1a", "h1b", "h2")
        if t.loc[n, "Sharpe all months"] > p1["Sharpe all months"]
        and t.loc[n, "option CAGR"] > p1["option CAGR"]
    ]
    beat_e1 = [
        n
        for n in ("h1a", "h1b", "h2")
        if t.loc[n, "Sharpe all months"] > e1["Sharpe all months"]
        and t.loc[n, "option CAGR"] > e1["option CAGR"]
    ]
    out.append(
        f"- Beat P1 on both Sharpe and option CAGR: {', '.join(beat_p1) or 'none'}. Beat e1f1 on "
        f"both: {', '.join(beat_e1) or 'none'}."
        + (
            " **Neither the hedges nor the mirror rule beats P1 or e1f1.**"
            if not beat_p1 and not beat_e1
            else ""
        )
    )
    out.append(
        "- Paired Newey-West t: "
        + "; ".join(
            f"{n} {t.loc[n, 'NW t vs P1']:.2f} vs P1, {t.loc[n, 'NW t vs e1f1']:.2f} vs e1f1"
            for n in ("h1a", "h1b", "h2")
        )
        + "."
    )
    return out


def results(cfg: dict) -> None:
    """Phase 5 report, crash table and yearly table."""
    OUT.mkdir(parents=True, exist_ok=True)
    ctx = p4.load_insample(cfg)
    md = [
        "# Phase 5 report: selling paired with buying\n",
        "H1a = P1 + 0.85 put hedge (15% of credit); H1b = e1f1 + the same hedge; H2 = mirror (sell "
        "the 0.95/0.90 put spread "
        "when prem_ratio >= 0.12, buy it when < 0.06 with a 2% debit, else cash). ref_* are "
        "references; sens_* are sensitivity "
        "only. Option-only returns (no cash interest); Sharpe over all months with cash months = "
        "0, no risk-free deduction. "
        "Both periods are **in-sample for this idea**; the holdout is not used.\n",
    ]
    allrows, crash, years = [], [], []
    for period in ("design", "validation"):
        df, cyc = period5(cfg, ctx, period)
        main = df[~df.rule.str.startswith("sens_")]
        srs = srs38(cfg, ctx, period, main)
        s = summarise5(main, cyc, cfg, srs)
        sens = summarise5(
            df[df.rule.str.startswith("sens_") | df.rule.isin(["h1a", "h2", "ref_p1", "ref_e1f1"])],
            cyc,
            cfg,
        )
        s.to_csv(OUT / f"summary_{period}.csv", index=False)
        hs, hc = hedge_stats(df, cyc)
        bs, top = buy_stats(df)
        crash.append(crash_table(df, cyc, period))
        years.append(by_year(df).assign(period=period))
        rec = p4.reconcile(df)
        md += (
            [
                f"## {period.capitalize()} (in-sample for this idea): {len(cyc)} cycles, entries "
                f"{cyc.entry.min():%Y-%m-%d} to "
                f"{cyc.entry.max():%Y-%m-%d}\n",
                fmt5(s, MAIN5),
                "",
                "Deflated Sharpe uses 38 trials; variance of monthly Sharpe across them = "
                f"{np.var(list(srs.values()), ddof=1):.4f}.\n",
                "Hedge leg alone (H1a, H1b):\n",
                hs.round(2).to_markdown(index=False),
                "",
                "Hedge leg net payoff (% of capital) in the 10 worst NIFTY TRI months (blank = no "
                "hedge that month):\n",
                hc.round(2).to_markdown(),
                "",
                "H2 buy leg and sell leg:\n",
                pd.DataFrame([bs]).round(2).to_markdown(index=False),
                "",
                "H2 top 5 buy months by payoff:\n",
                top.round(2).to_markdown(index=False),
                "",
                "Sensitivity only (not trials):\n",
                fmt5(
                    sens[sens.rule.str.startswith("sens_")],
                    [
                        "rule",
                        "option CAGR",
                        "Sharpe all months",
                        "worst month",
                        "CVaR99",
                        "months selling",
                        "months buying",
                    ],
                ),
                "",
                "Reading:\n",
            ]
            + reading5(s, df, hs, bs, period)
            + ["", "Checks:\n"]
            + rec
            + [""]
        )
        allrows.append(df)
    df = pd.concat(allrows, ignore_index=True)
    out = df.drop(columns=["next_entry"])
    num = out.select_dtypes("number").columns
    out[num] = out[num].round(4)
    out.to_csv(OUT / "monthly_pnl_phase5.csv", index=False)
    pd.concat(crash).round(3).to_csv(OUT / "crash_table.csv")
    pd.concat(years).round(3).to_csv(OUT / "by_year.csv")
    md += ["## Crash table highlights (option return, % of capital)\n"]
    for c in crash:
        p = c.period.iloc[0]
        w = c[c.case == "10 worst TRI months"].drop(columns=["case", "period"])
        md += [
            f"{p}: 10 worst NIFTY TRI months\n",
            w.round(2).to_markdown(),
            "",
            f"{p}: average over the 10 worst / 10 best TRI months: "
            + "; ".join(
                f"{r} {c[c.case == '10 worst TRI months'][r].mean():+.2f} / "
                f"{c[c.case == '10 best TRI months'][r].mean():+.2f}"
                for r in w.columns
                if r != "tri_pct"
            )
            + "\n",
        ]
    md += ["Full tables: `crash_table.csv`, `by_year.csv`."]
    (OUT / "phase5_report.md").write_text("\n".join(md) + "\n")
    charts5(df)
    logger.info("\n".join(md))


def charts5(df) -> None:
    """Phase 5 charts."""
    d = df[df.period == "design"]
    fig, ax = plt.subplots(figsize=(11, 5.5))
    for n in ("h1a", "h1b", "h2", "ref_p1", "ref_e1f1"):
        g = d[d.rule == n]
        x = np.r_[pd.Timestamp(g.entry_date.iloc[0]), pd.to_datetime(g.next_entry).values]
        ax.plot(
            x,
            np.r_[1.0, (1 + g.option_return_on_capital_pct / 100).cumprod().values],
            label=n,
            ls="--" if n.startswith("ref_") else "-",
        )
    ax.set_yscale("log")
    ax.set_title("Design cycles: option-only P&L (no cash interest), log scale", fontsize=10)
    ax.legend()
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(OUT / "equity_design.png", dpi=130)
    plt.close(fig)
    g = df[(df.rule == "h2") & (df.action == "buy")]
    fig, ax = plt.subplots(figsize=(12, 4.5))
    x = pd.to_datetime(g.expiry_date)
    y = g.option_return_on_capital_pct
    ax.bar(x, y, width=25, color=np.where(y < 0, "tab:red", "tab:green"))
    for d0, v in zip(x, y, strict=False):
        if v > 2:
            ax.annotate(
                f"{d0:%b %Y}\n{v:+.1f}%",
                (d0, v),
                textcoords="offset points",
                xytext=(0, 3),
                ha="center",
                fontsize=7,
            )
    ax.axhline(0, color="k", lw=0.8)
    ax.axvline(
        pd.Timestamp(df[df.period == "validation"].entry_date.min()), color="grey", ls=":", lw=0.8
    )
    ax.set_ylabel("option P&L, % of capital")
    ax.set_title(
        "H2 buy months (bought 0.95/0.90 put spread, debit 2% of capital); dotted line = "
        "validation start",
        fontsize=10,
    )
    ax.grid(alpha=0.3, axis="y")
    fig.tight_layout()
    fig.savefig(OUT / "buy_leg_months.png", dpi=130)
    plt.close(fig)


def check(cfg: dict) -> None:
    """Phase 5 checks."""
    out = ["# Phase 5 checks\n"]
    ctx = p4.load_insample(cfg)
    vend = pd.Timestamp(cfg["phase2"]["validation_end"])
    assert ctx["opt"].date.max() <= vend
    out.append(f"- holdout not loaded: no option data after {vend:%Y-%m-%d}.")
    cc = cfg["costs"]
    allp = []
    for period in ("design", "validation"):
        cyc = ctx["cyc"][ctx["cyc"].period == period].reset_index(drop=True)
        cyc["tri_ret"] = bt.tri_returns(cyc, ctx["ix"])
        mk = bt.vrp_table(ctx["opt"], ctx["ix"], cyc, cfg).set_index("entry")
        v = variants5(cfg)
        dd = {
            n: run5(n, v[n], cyc, ctx, cfg, period, mk)
            for n in ("h1a", "h1b", "h2", "ref_p1", "ref_e1f1", "ref_base")
        }
        allp += list(dd.values())
        ref = pd.read_csv("results/phase4/monthly_pnl_phase4_bugfix.csv")
        for n, rr in (("ref_p1", "p1"), ("ref_e1f1", "ref_e1f1"), ("ref_base", "ref_base")):
            b = ref[(ref.rule == rr) & (ref.period == period)]
            gap = np.abs(dd[n].capital_end.values - b.capital_end.values).max()
            assert gap < 0.01, (n, period, gap)
            out.append(
                f"- {n} reproduces the bugfix-recomputed Phase 4 {rr} ({period}): max capital gap "
                f"Rs {gap:.4f}"
            )
        if period != "design":
            continue
        rng = np.random.default_rng(11)
        for n in ("h1a", "h1b"):
            h = dd[n][dd[n].hedge_cost.notna()]
            for i in rng.choice(h.index, 3, replace=False):
                r = h.loc[i]
                c = cyc[cyc.entry == pd.Timestamp(r.entry_date)].iloc[0]
                s0 = float(ctx["ix"].close[c.entry])
                ch = census.chain(ctx, c.entry, c.contract)
                a = float(ch[(ch.opt == "PE") & (ch.strike == r.short_put_strike)].close.iloc[0])
                b = float(ch[(ch.opt == "PE") & (ch.strike == r.long_put_strike)].close.iloc[0])
                pa = a - max(cc["slip_min"], cc["slip_pct"] * a)
                pb = b + max(cc["slip_min"], cc["slip_pct"] * b)
                net = r.units * (pa - pb)
                hc = float(ch[(ch.opt == "PE") & (ch.strike == r.hedge_strike)].close.iloc[0])
                hp = hc + max(cc["slip_min"], cc["slip_pct"] * hc)
                paid = r.hedge_units * hp
                assert (
                    abs(paid - cfg["phase5"]["hedge_budget"] * net) < 1
                    and abs(r.hedge_cost - paid) < 1
                )
                out.append(
                    f"- {n} hedge {r.entry_date}: put {r.hedge_strike:.0f} (target "
                    f"{cfg['phase5']['hedge_moneyness'] * s0:.0f}) "
                    f"paid Rs {paid:,.2f} = 15% x spread net credit Rs {net:,.2f}: OK"
                )
        h2 = dd["h2"]
        for act in ("buy", "sell"):
            g = h2[h2.action == act]
            for i in rng.choice(g.index, 3, replace=False):
                r = g.loc[i]
                c = cyc[cyc.entry == pd.Timestamp(r.entry_date)].iloc[0]
                s0 = float(ctx["ix"].close[c.entry])
                legs, _, _ = p4.pick(p4.PS, census.chain(ctx, c.entry, c.contract), s0, cfg)
                assert legs[0]["k"] == (r.short_put_strike if act == "sell" else r.long_put_strike)
                k1, k2 = legs[0]["k"], legs[1]["k"]
                a, b = legs[0]["close"], legs[1]["close"]
                prem = (a - b) / (k1 - k2)
                if act == "buy":
                    px1 = a + max(cc["slip_min"], cc["slip_pct"] * a)
                    px2 = b - max(cc["slip_min"], cc["slip_pct"] * b)
                    fees = p3.fees(
                        [(c.entry, px1, r.units, False), (c.entry, px2, r.units, True)], 0.0, cc
                    )
                    debit = r.units * (px1 - px2) + sum(fees.values())
                    pay = r.units * (
                        max(0, k1 - r.index_at_expiry) - max(0, k2 - r.index_at_expiry)
                    )
                    assert (
                        prem < cfg["phase5"]["buy_below"]
                        and abs(debit - 0.02 * r.capital_start) < 1
                        and abs(pay - r.buy_payoff) < 1e-6
                    )
                    out.append(
                        f"- h2 buy {r.entry_date}: prem_ratio {prem:.3f}; long {k1:.0f} @ "
                        f"{px1:.2f}, short {k2:.0f} @ {px2:.2f}; "
                        f"debit incl. charges Rs {debit:,.2f} = 2% of capital; payoff Rs "
                        f"{pay:,.2f} = code: OK"
                    )
                else:
                    pa = a - max(cc["slip_min"], cc["slip_pct"] * a)
                    pb = b + max(cc["slip_min"], cc["slip_pct"] * b)
                    pay = -r.units * (
                        max(0, k1 - r.index_at_expiry) - max(0, k2 - r.index_at_expiry)
                    )
                    assert (
                        prem >= cfg["phase4"]["prem_min"]
                        and abs(r.units * (k1 - k2 - (pa - pb)) - 0.1 * r.capital_start) < 1
                    )
                    assert abs(-r.settlement_payout - pay) < 1e-6
                    out.append(
                        f"- h2 sell {r.entry_date}: prem_ratio {prem:.3f}; credit Rs "
                        f"{r.units * (pa - pb):,.2f}; max loss = 10% of "
                        f"capital; payoff Rs {pay:,.2f} = code: OK"
                    )
    out.append(
        "- no look-ahead: prem_ratio, strikes and sizing use the entry-day chain (chain() asserts "
        "date == entry) and the "
        "entry-day index close; settlement only for payoff; the e1f1 filter uses entry-day IV and "
        "trailing RV."
    )
    out += p4.reconcile(pd.concat(allp, ignore_index=True))
    (OUT / "checks.md").write_text("\n".join(out) + "\n")
    logger.info("\n".join(out))
