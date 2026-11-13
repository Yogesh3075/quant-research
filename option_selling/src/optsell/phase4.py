from __future__ import annotations

import hashlib
import inspect
import logging
from datetime import datetime
from pathlib import Path

import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from optsell import backtest as bt
from optsell import census, data, marking, report
from optsell import phase2 as p2
from optsell import phase3 as p3
from optsell.config import CONFIG_PATH

matplotlib.use("Agg")
logger = logging.getLogger(__name__)

OUT = Path("results/phase4")
CEN = Path("results/census")
FIXED = ["s6_iron_butterfly", "s6_iron_butterfly_e1", "s9_calendar"]


def census_srs(cfg: dict, ctx, period, new) -> dict:
    """Monthly Sharpe of the census trials after the Phase 4 fixes."""
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
    s2 = pd.read_csv(f"results/phase2/summary_{period}.csv").set_index("variant")
    s3 = pd.read_csv(f"results/phase3/summary_{period}.csv").set_index("variant")
    sc = pd.read_csv(CEN / f"summary_{period}.csv").set_index("strategy")
    for n in cfg["phase2"]["variants"]:
        srs[f"phase2_{n}"] = s2.loc[n, "SR monthly"]
    for n in cfg["phase3"]["variants"]:
        srs[f"phase3_{n}"] = s3.loc[n, "SR monthly"]
    for n in census.strategies(cfg, refs=False):
        if n in FIXED:
            ro = new[new.rule == n].option_return_on_capital_pct
            srs[f"census_{n}"] = ro.mean() / ro.std()
        else:
            srs[f"census_{n}"] = sc.loc[n, "SR monthly"]
    return srs


def worst5(df, label) -> str:
    """The five worst calendar-spread months, as text."""
    w = df[(df.rule == "s9_calendar") & (df.skipped == "no")].nsmallest(
        5, "option_return_on_capital_pct"
    )
    cols = [
        "period",
        "entry_date",
        "legs",
        "index_at_entry",
        "index_at_expiry",
        "units",
        "settlement_payout",
        "option_return_on_capital_pct",
        "exit_flag",
    ]
    w = w[cols].copy()
    w["payout_per_unit"] = w.settlement_payout / w.units
    return f"{label}:\n\n" + w.round(2).to_markdown(index=False) + "\n"


def fix(cfg: dict) -> None:
    """Apply the Phase 4 fixes (S9 far leg, S6 cap) and record what changed."""
    OUT.mkdir(parents=True, exist_ok=True)
    old = pd.read_csv(CEN / "monthly_pnl_census.csv")
    ctx = census.load(cfg)
    st = census.strategies(cfg)
    new_rows, summ = [], {}
    for period in ("design", "validation"):
        cyc = ctx["cyc"][ctx["cyc"].period == period].reset_index(drop=True)
        cyc["tri_ret"] = bt.tri_returns(cyc, ctx["ix"])
        mk = bt.vrp_table(ctx["opt"], ctx["ix"], cyc, cfg).set_index("entry")
        parts = [
            census.run(n, st[n], cyc, ctx, cfg, cfg["cash_rate"], period, mk)[0]
            for n in FIXED + ["ref_base"]
        ]
        df = pd.concat(parts, ignore_index=True)
        srs = census_srs(cfg, ctx, period, df)
        s = census.summarise(df, cyc, cfg, srs)
        summ[period] = s[s.strategy.isin(FIXED)]
        new_rows.append(df[df.rule.isin(FIXED)])
    new = pd.concat(new_rows, ignore_index=True)
    census.write_csv(new, OUT / "_new.csv")
    newc = pd.read_csv(OUT / "_new.csv")
    (OUT / "_new.csv").unlink()
    keep = old[~old.rule.isin(FIXED)]
    both = pd.concat([keep, newc], ignore_index=True)
    order = {r: i for i, r in enumerate(dict.fromkeys(old.rule))}
    both["_o"] = both.rule.map(order)
    both["_p"] = (both.period == "validation").astype(int)
    both = both.sort_values(["_p", "_o", "cycle_no"], kind="stable").drop(columns=["_o", "_p"])
    both.to_csv(CEN / "monthly_pnl_census.csv", index=False)
    lines = [
        "# Phase 4 fixes\n",
        "## 1. S9 calendar valuation\n",
        "Cause, from the five worst S9 months: (a) **wrong far contract**: the far leg was looked "
        "up on the near expiry "
        "day by its entry-day label; NSE relabelled the February 2014 contract (2014-02-27 -> "
        "2014-02-26, holiday), so "
        "on 2014-01-30 the old label had no rows and the entry-day close was carried for a month "
        "(entry 2013-12-27, "
        "-49.4%); (b) **stale close**: the far put had zero contracts traded on the exit day and "
        "its bhavcopy close was "
        "days old (entry 2018-09-28: close 575 vs NSE settle 806). Fix: on the near expiry day the "
        "far contract is the "
        "monthly of the following month as listed that day; its close is used only if contracts "
        "traded > 0; otherwise "
        "it is valued by Black-Scholes (r 6.5%, no dividend) with the ATM implied volatility of "
        "that same contract that "
        "day (Phase 1 method; the expiring near month has no usable IV on its expiry day), India "
        "VIX as a fallback, and "
        "the row is flagged in `exit_flag` (bs_atm_iv / bs_vix). The other large losses used "
        "traded closes (deep "
        "in-the-money far puts traded at or below intrinsic after falls) and are unchanged.\n",
        worst5(old, "Before the fix"),
        worst5(both, "After the fix"),
    ]
    for period in ("design", "validation"):
        so = pd.read_csv(CEN / f"summary_{period}.csv")
        cols = [
            "strategy",
            "option CAGR",
            "option Sharpe",
            "worst month",
            "CVaR99",
            "max DD",
            "win rate",
            "avg credit % cap",
            "avg margin % cap",
            "costs % gross credit",
        ]
        o = so[so.strategy.isin(FIXED)][cols].assign(version="old")
        n = summ[period][cols].assign(version="new")
        lines += [
            f"### Old vs new summary ({period})\n",
            census.fmt(pd.concat([o, n]), ["version"] + cols),
            "",
        ]
        so = so.set_index("strategy")
        nn = summ[period].set_index("strategy")
        for k in FIXED:
            for c in so.columns:
                if c in nn.columns:
                    so.loc[k, c] = nn.loc[k, c]
        so.reset_index().to_csv(CEN / f"summary_{period}.csv", index=False)
    capped = newc.sizing_note.fillna("").str.contains("capped")
    lines += [
        "## 2. S6 iron butterfly sizing\n",
        "Units are now capped so that units x S0 per short side <= 1.5 x capital "
        "(`census.cap_defined` in config), "
        "as for the stress-sized strategies; before, a small max loss per unit (wing width - "
        "credit) made units and "
        "costs very large. Old vs new rows for S6 are in the tables above.\n",
        "Capped cycles: "
        + ", ".join(
            f"{r} {p}: {int(((newc.rule == r) & (newc.period == p) & capped).sum())}"
            for r in FIXED[:2]
            for p in ("design", "validation")
        )
        + ".\n",
        "Other census strategies' summary rows are unchanged as committed; their deflated Sharpe "
        "ratios used the pre-fix "
        "S6/S9 Sharpe values in the trial variance (the S6/S9 rows above use the corrected "
        "values).\n",
    ]
    dsg = both[both.period == "design"].copy()
    dsg["entry_date"] = pd.to_datetime(dsg.entry_date).dt.date
    cyc = ctx["cyc"][ctx["cyc"].period == "design"].reset_index(drop=True)
    cyc["tri_ret"] = bt.tri_returns(cyc, ctx["ix"])
    corr, crash, co = census.combo_inputs(dsg, cyc)
    corr.round(3).to_csv(CEN / "correlation_design.csv")
    crash.round(3).to_csv(CEN / "crash_table.csv")
    co.to_csv(CEN / "co_loss_pairs.csv", index=False)
    (OUT / "fixes.md").write_text("\n".join(lines) + "\n")
    logger.info("\n".join(lines))


def compare(snap) -> list:
    """Compare committed files with the recomputed ones."""
    out = []
    for f in sorted(Path("results").rglob("*")):
        if not f.is_file() or "phase4" in f.parts or f.suffix not in (".csv", ".md", ".log"):
            continue
        g = Path(snap) / f
        if not g.exists():
            out.append((str(f), "new file"))
            continue
        a, b = (
            hashlib.sha256(g.read_bytes()).hexdigest(),
            hashlib.sha256(f.read_bytes()).hexdigest(),
        )
        if a == b:
            out.append((str(f), "unchanged (same SHA-256)"))
            continue
        if f.suffix == ".csv":
            x, y = pd.read_csv(g), pd.read_csv(f)
            x = x.rename(columns={"iv_minus_rv_pts": "iv_minus_future_rv_pts"})
            for d in (x, y):
                for c in ("rule", "strategy", "a", "b"):
                    if c in d:
                        d.drop(d[d[c].isin(FIXED)].index, inplace=True)
            x = x.drop(columns=[c for c in x.columns if c in FIXED])
            y = y.drop(columns=[c for c in y.columns if c in FIXED])
            same = x.reset_index(drop=True).equals(y.reset_index(drop=True))
            out.append(
                (
                    str(f),
                    "identical after excluding S6/S9 and the renamed column"
                    if same
                    else "**DIFFERS**",
                )
            )
        else:
            same = f.read_text().startswith(g.read_text())
            out.append((str(f), "old content unchanged, note appended" if same else "**DIFFERS**"))
    return out


PS = [["P", -1, 1, 0.95], ["P", 1, 1, 0.90]]
EXTRA = [
    "prem_ratio",
    "traded",
    "stop_triggered",
    "trigger_date",
    "trigger_day",
    "exit_date",
    "exit_cost",
    "exit_flag",
    "pnl_if_held",
    "stop_effect",
    "cost_stress_pnl",
    "fallback_used",
    "entry_slip_mult",
]


def variants(cfg: dict, sens=False) -> dict:
    """P1, P2, P3 and references (plus sensitivity runs)."""
    p4 = cfg["phase4"]
    v = {
        "ref_base": {"legs": PS, "sizing": "spread", "prem": None, "ivrv": False, "stop": None},
        "ref_e1f1": {"legs": PS, "sizing": "spread", "prem": None, "ivrv": True, "stop": "credit"},
        "ref_s7_e1": {
            "legs": [["P", -1, 1, 0.95]],
            "sizing": "notional",
            "prem": None,
            "ivrv": False,
            "stop": "credit",
        },
    }
    for n, (f, s) in p4["variants"].items():
        v[n] = {
            "legs": PS,
            "sizing": "spread",
            "prem": p4["prem_min"] if f else None,
            "ivrv": False,
            "stop": "index" if s else None,
        }
    if sens:
        for t in p4["sensitivity"]:
            v[f"sens_p3_{t:.2f}"] = {
                "legs": PS,
                "sizing": "spread",
                "prem": t,
                "ivrv": False,
                "stop": "index",
            }
    return v


def load_insample(cfg: dict) -> dict:
    """Inputs for design and validation."""
    ctx = census.load(cfg)
    ctx["gp"] = p3.gaps(ctx, ctx["cyc"].reset_index(drop=True), cfg)
    return ctx


def load_holdout(cfg: dict) -> dict:
    """Inputs for the holdout."""
    fo, ix = data.load()
    cyc = data.cycles(fo, ix)
    vend = pd.Timestamp(cfg["phase2"]["validation_end"])
    cyc["period"] = np.where(
        cyc.entry <= pd.Timestamp(cfg["phase2"]["design_end"]),
        "design",
        np.where(cyc.expiry <= vend, "validation", "holdout"),
    )
    opt = fo[fo.instr == "OPTIDX"][["date", "expiry", "strike", "opt", "close", "volume", "lot"]]
    ctx = {"opt": opt, "ix": ix, "cyc": cyc, "days": pd.DatetimeIndex(sorted(fo.date.unique()))}
    ctx["byday"] = {d: g for d, g in opt[opt.date.isin(cyc.entry)].groupby("date")}
    ctx["bk"] = marking.book(opt, set(cyc.contract))
    ctx["gp"] = p3.gaps(ctx, cyc.reset_index(drop=True), cfg)
    return ctx


def pick(spec, ch, s0, cfg: dict) -> tuple:
    """Strikes of the Phase 4 put spread."""
    legs, fb = [], False
    for o, side, q, m in spec:
        r, f = p2.pick_money(ch, o, m * s0, cfg, "fallback")
        if r is None:
            return None, False, f"no traded {o} strike near {m:.2f} x S0"
        legs.append(
            {
                "opt": o,
                "side": side,
                "q": q,
                "k": float(r.strike),
                "close": float(r.close),
                "volume": float(r.volume),
                "lot": r.lot,
            }
        )
        fb = fb or f
    return legs, fb, ""


def fill(legs, cc, mult) -> None:
    """Entry fills with slippage (times a stress multiple), in place."""
    for leg in legs:
        slip = mult * max(cc["slip_min"], cc["slip_pct"] * leg["close"])
        leg["px"] = max(0.0, leg["close"] - slip) if leg["side"] < 0 else leg["close"] + slip
        leg["slip"] = leg["px"] - leg["close"] if leg["side"] > 0 else leg["close"] - leg["px"]


def stop_exit(v, legs, units, credit, c, days, ctx, cfg: dict, mult) -> dict | None:
    """Exit on the 2x-credit stop or the index stop."""
    raw = [p3.leg_series(ctx["bk"], c.contract, leg) for leg in legs]
    if v["stop"] == "credit":
        pnl = np.zeros(len(days))
        for leg, s in zip(legs, raw, strict=False):
            m = s.reindex(days)
            m.iloc[0] = leg["close"]
            pnl += leg["side"] * leg["q"] * (m.ffill().values - leg["px"]) * units
        hit = [-pnl[d] >= cfg["phase3"]["stop_mult"] * units * credit for d in range(len(days))]
    else:
        k = [leg["k"] for leg in legs if leg["side"] < 0][0]
        idx = ctx["ix"].close.reindex(days).values
        hit = [idx[d] < k for d in range(len(days))]
    for d in range(1, len(days) - 2):
        if hit[d]:
            break
    else:
        return None
    e = d + 1
    out, flag = [], False
    for leg, s in zip(legs, raw, strict=False):
        a = s[(s.index >= days[e]) & (s.index <= days[-1])]
        if len(a):
            dt, cl = a.index[0], float(a.iloc[0])
            flag = flag or dt != days[e]
        else:
            dt, cl, flag = days[-1], bt.intrinsic(leg["opt"], leg["k"], c.settle), True
        slip = mult * max(cfg["costs"]["slip_min"], cfg["costs"]["slip_pct"] * cl)
        px = cl + slip if leg["side"] < 0 else max(0.0, cl - slip)
        out.append(
            {"date": dt, "close": cl, "px": px, "slip": px - cl if leg["side"] < 0 else cl - px}
        )
    return {
        "trigger": days[d],
        "day": d,
        "exit": max(o["date"] for o in out),
        "legs": out,
        "flag": flag,
    }


def vix_proxy(c, ctx, mk) -> float:
    """India VIX at entry, or ATM IV before May 2014."""
    v = ctx["ix"].vix.get(c.entry, np.nan)
    return float(v) / 100 if pd.notna(v) else float(mk.loc[c.entry].iv)


def run(name, v, cyc, ctx, cfg: dict, period, mk, stress=False) -> pd.DataFrame:
    """Run one Phase 4 rule over a period's cycles."""
    cc, p4 = cfg["costs"], cfg["phase4"]
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
            "fallback_used": "no",
        }
        legs, fb, why = pick(v["legs"], census.chain(ctx, c.entry, c.contract), s0, cfg)
        prem = np.nan
        if legs is not None and len(legs) == 2:
            prem = (legs[0]["close"] - legs[1]["close"]) / (legs[0]["k"] - legs[1]["k"])
        row["prem_ratio"] = prem
        if legs is not None and v["prem"] is not None and prem < v["prem"]:
            legs, why = None, f"filtered: prem_ratio {prem:.3f} < {v['prem']:.2f}"
        if legs is not None and v["ivrv"]:
            g = ctx["gp"].loc[c.entry]
            if pd.notna(g.gap) and pd.notna(g.threshold) and g.gap <= g.threshold:
                legs, why = None, "filtered: IV - RV gap not above the expanding median"
        if legs is None:
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
                    **dict.fromkeys(ITEMS4, 0.0),
                }
            )
        else:
            ke = (
                p4["stress_mult"]
                if stress and vix_proxy(c, ctx, mk) * 100 > p4["vix_stress"]
                else 1.0
            )
            fill(legs, cc, ke)
            credit = sum(-leg["side"] * leg["q"] * leg["px"] for leg in legs)
            if v["sizing"] == "spread":
                width = max(leg["k"] for leg in legs) - min(leg["k"] for leg in legs)
                maxloss = width - credit
                units = cfg["max_loss_pct"] * capital / maxloss
                margin = plan = units * maxloss
            else:
                units = capital / s0
                margin = cfg["census"]["naked_margin"] * units * s0
                plan = np.nan
            payoff = sum(
                leg["side"] * leg["q"] * bt.intrinsic(leg["opt"], leg["k"], c.settle)
                for leg in legs
            )
            itm = sum(
                leg["q"] * bt.intrinsic(leg["opt"], leg["k"], c.settle) * units
                for leg in legs
                if leg["side"] > 0
            )
            entry_fills = [(c.entry, leg["px"], units * leg["q"], leg["side"] < 0) for leg in legs]
            it = p3.fees(entry_fills, itm, cc)
            slip = sum(leg["slip"] * leg["q"] for leg in legs) * units
            held_pnl = units * (credit + payoff) - sum(it.values())
            interest = rate * (capital - margin) * days_total / 365
            row.update(
                {
                    "traded": "yes",
                    "skipped": "no",
                    "skip_reason": "",
                    "fallback_used": "yes" if fb else "no",
                    "entry_slip_mult": ke,
                    "pnl_if_held": held_pnl,
                }
            )
            if v["stop"]:
                days = ctx["days"][(ctx["days"] >= c.entry) & (ctx["days"] <= c.expiry)]
                s = stop_exit(
                    v, legs, units, credit, c, days, ctx, cfg, p4["stress_mult"] if stress else 1.0
                )
                if s:
                    payoff = sum(
                        leg["side"] * leg["q"] * x["close"]
                        for leg, x in zip(legs, s["legs"], strict=False)
                    )
                    exit_slip = (
                        sum(x["slip"] * leg["q"] for leg, x in zip(legs, s["legs"], strict=False))
                        * units
                    )
                    fills = entry_fills + [
                        (x["date"], x["px"], units * leg["q"], leg["side"] > 0)
                        for leg, x in zip(legs, s["legs"], strict=False)
                    ]
                    it = p3.fees(fills, 0.0, cc)
                    entry_it = p3.fees(entry_fills, 0.0, cc)
                    slip += exit_slip
                    interest = (
                        rate * (capital * days_total - margin * (s["exit"] - c.entry).days) / 365
                    )
                    opt_net = units * (credit + payoff) - exit_slip - sum(it.values())
                    row.update(
                        {
                            "stop_triggered": "yes",
                            "trigger_date": s["trigger"].date(),
                            "trigger_day": s["day"],
                            "exit_date": s["exit"].date(),
                            "exit_flag": "yes" if s["flag"] else "no",
                            "exit_cost": exit_slip + sum(it.values()) - sum(entry_it.values()),
                            "stop_effect": "helped" if opt_net > held_pnl else "hurt",
                        }
                    )
            for leg in legs:
                nm = report.LEGS[("S" if leg["side"] < 0 else "B", leg["opt"])]
                row[f"{nm}_strike"] = leg["k"]
                row[f"{nm}_entry_price"] = leg["close"]
                row[f"{nm}_settle_value"] = bt.intrinsic(leg["opt"], leg["k"], c.settle)
                if leg["side"] < 0:
                    row[f"{nm}_contracts_traded"] = leg["volume"]
                    row["lot_size"] = leg["lot"]
                    row["lots"] = np.floor(units / leg["lot"]) if pd.notna(leg["lot"]) else np.nan
            row.update(
                {
                    "units": units,
                    "notional": units * s0,
                    "margin_used": margin,
                    "margin_pct_of_capital": 100 * margin / capital,
                    "idle_cash": max(0.0, capital - margin),
                    "max_loss_planned": "unlimited" if pd.isna(plan) else plan,
                    "credit_gross": units
                    * sum(-leg["side"] * leg["q"] * leg["close"] for leg in legs),
                    "slippage_cost": slip,
                    "settlement_payout": -units * payoff + 0.0,
                    "cash_interest": interest,
                    **{k: it.get(k, 0.0) for k in ITEMS4},
                }
            )
        row["credit_net"] = row["credit_gross"] - row["slippage_cost"]
        row["option_pnl_before_charges"] = row["credit_net"] - row["settlement_payout"]
        row["total_charges"] = sum(row[k] for k in ITEMS4)
        row["total_costs"] = row["slippage_cost"] + row["total_charges"]
        row["costs_pct_of_credit_gross"] = (
            100 * row["total_costs"] / row["credit_gross"] if row["credit_gross"] else np.nan
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
    for col in report.COLS + EXTRA:
        if col not in df:
            df[col] = np.nan
    return df[report.COLS + EXTRA + ["next_entry"]]


ITEMS4 = p3.ITEMS


def period_runs(cfg: dict, ctx, period, sens=False) -> tuple:
    """Run every rule on one period, normal and stressed costs."""
    cyc = ctx["cyc"][ctx["cyc"].period == period].reset_index(drop=True)
    cyc["tri_ret"] = bt.tri_returns(cyc, ctx["ix"])
    mk = bt.vrp_table(ctx["opt"], ctx["ix"], cyc, cfg).set_index("entry")
    normal, stressed = [], []
    for n, v in variants(cfg, sens).items():
        a = run(n, v, cyc, ctx, cfg, period, mk)
        b = run(n, v, cyc, ctx, cfg, period, mk, stress=True)
        a["cost_stress_pnl"] = b.option_pnl_net.values
        normal.append(a)
        stressed.append(b)
        logger.info(f"  {period} {n}: done")
    return pd.concat(normal, ignore_index=True), pd.concat(stressed, ignore_index=True), cyc


def reconcile(df) -> list:
    """Reconciliation checks."""
    lhs = (
        df.credit_gross
        - df.slippage_cost
        - df.settlement_payout
        - df.total_charges
        + df.cash_interest
    )
    g = {
        "credit_gross - slippage - payout - charges + interest = total_pnl": (lhs - df.total_pnl)
        .abs()
        .max(),
        "capital_end = capital_start + total_pnl": (
            df.capital_start + df.total_pnl - df.capital_end
        )
        .abs()
        .max(),
        "charge items sum to total_charges": (df[ITEMS4].sum(axis=1) - df.total_charges)
        .abs()
        .max(),
    }
    ch = 0.0
    for _, x in df.groupby(["rule", "period"]):
        ch = max(ch, np.abs(x.capital_start.values[1:] - x.capital_end.values[:-1]).max())
    g["capital_start = previous capital_end"] = ch
    return [f"- {k}: max gap Rs {v:.6f} -> {'PASS' if v < 1 else 'FAIL'}" for k, v in g.items()]


def trial_srs(cfg: dict, ctx, period, df) -> dict:
    """Monthly Sharpe of every logged trial."""
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
        (f"results/phase2/summary_{period}.csv", "variant", cfg["phase2"]["variants"]),
        (f"results/phase3/summary_{period}.csv", "variant", cfg["phase3"]["variants"]),
        (f"results/census/summary_{period}.csv", "strategy", census.strategies(cfg, refs=False)),
    ):
        s = pd.read_csv(f).set_index(key)
        for n in names:
            srs[f"{Path(f).parent.name}_{n}"] = s.loc[n, "SR monthly"]
    for n in cfg["phase4"]["variants"]:
        ro = df[df.rule == n].option_return_on_capital_pct
        srs[f"phase4_{n}"] = ro.mean() / ro.std()
    return srs


def summarise(df, cyc, cfg: dict, srs=None) -> pd.DataFrame:
    """Summary statistics and deflated Sharpe of each rule."""
    rows = []
    cy = cyc[["entry", "next_entry"]]
    base = df[df.rule == "ref_base"].option_return_on_capital_pct.values / 100
    e1 = df[df.rule == "ref_e1f1"].option_return_on_capital_pct.values / 100
    for n, g in df.groupby("rule", sort=False):
        ro = g.option_return_on_capital_pct.values / 100
        m = bt.metrics(pd.Series(ro), cy, pd.Series(np.zeros(len(g))))
        tot = bt.metrics(
            pd.Series(g.return_on_capital_pct.values / 100), cy, bt.cash_returns(cy, cfg["rf"])
        )
        tr = g[g.traded == "yes"]
        rt = tr.option_pnl_net / tr.capital_start
        aw = rt[rt > 0].mean() if (rt > 0).any() else np.nan
        al = -rt[rt <= 0].mean() if (rt <= 0).any() else 0.0
        be = al / (al + aw) if pd.notna(aw) else np.nan
        win = (rt > 0).mean() if len(rt) else np.nan
        st = g[g.stop_triggered == "yes"]
        r = {
            "rule": n,
            "trial": "yes" if n in cfg["phase4"]["variants"] else "no",
            "option CAGR": m["CAGR"],
            "Sharpe all months": m["Sharpe"],
            "Sharpe traded months": rt.mean() / rt.std() * np.sqrt(12) if len(rt) > 2 else np.nan,
            "worst month": m["Worst month"],
            "worst 3m": m["Worst 3m"],
            "CVaR95": m["CVaR95"],
            "CVaR99": m["CVaR99"],
            "max DD": m["MaxDD"],
            "win rate": win,
            "break-even win rate": be,
            "break-even margin": win - be,
            "months": len(g),
            "months traded": len(tr),
            "avg prem_ratio traded": tr.prem_ratio.mean(),
            "stops": len(st),
            "stops helped": int((st.stop_effect == "helped").sum()),
            "stops hurt": int((st.stop_effect == "hurt").sum()),
            "median trigger day": st.trigger_day.median(),
            "costs % gross credit": tr.total_costs.sum() / tr.credit_gross.sum()
            if len(tr)
            else np.nan,
            "total CAGR (cash 6.5%)": tot["CAGR"],
        }
        r["NW t vs base"] = (
            p3.nw_t(ro - base, cfg["phase3"]["nw_lags"])[1] if n != "ref_base" else np.nan
        )
        r["NW t vs e1f1"] = (
            p3.nw_t(ro - e1, cfg["phase3"]["nw_lags"])[1] if n != "ref_e1f1" else np.nan
        )
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


PCT4 = [
    "option CAGR",
    "worst month",
    "worst 3m",
    "CVaR95",
    "CVaR99",
    "max DD",
    "win rate",
    "break-even win rate",
    "break-even margin",
    "costs % gross credit",
    "total CAGR (cash 6.5%)",
    "DSR",
]
MAIN4 = [
    "rule",
    "option CAGR",
    "Sharpe all months",
    "Sharpe traded months",
    "worst month",
    "worst 3m",
    "CVaR95",
    "CVaR99",
    "max DD",
    "win rate",
    "break-even win rate",
    "break-even margin",
    "months traded",
    "avg prem_ratio traded",
    "stops",
    "stops helped",
    "stops hurt",
    "median trigger day",
    "costs % gross credit",
    "total CAGR (cash 6.5%)",
    "NW t vs base",
    "NW t vs e1f1",
]
STRESS4 = [
    "rule",
    "option CAGR",
    "Sharpe all months",
    "worst month",
    "CVaR99",
    "max DD",
    "total CAGR (cash 6.5%)",
]


def fmt4(s, cols) -> pd.DataFrame:
    """Format a summary table for Markdown."""
    d = s[cols].copy()
    for c in cols:
        if c in PCT4:
            d[c] = d[c].map(lambda v: "" if pd.isna(v) else f"{v:.1%}")
        elif d[c].dtype.kind == "f":
            d[c] = d[c].map(lambda v: "" if pd.isna(v) else f"{v:.2f}")
    return d.to_markdown(index=False)


def buckets(df) -> tuple:
    """P3 trades by premium-ratio bucket and by year."""
    g = df[(df.rule == "p3") & (df.traded == "yes")].copy()
    g["bucket"] = pd.cut(
        g.prem_ratio,
        [0.12, 0.15, 0.20, 10],
        right=False,
        labels=["0.12-0.15", "0.15-0.20", "above 0.20"],
    )
    g["year"] = pd.to_datetime(g.entry_date).dt.year

    def f(x):
        return pd.Series(
            {
                "months traded": len(x),
                "mean return %": x.option_return_on_capital_pct.mean(),
                "compounded %": 100 * ((1 + x.option_return_on_capital_pct / 100).prod() - 1),
                "stops": int((x.stop_triggered == "yes").sum()),
            }
        )

    b = g.groupby(["period", "bucket"], observed=False).apply(f, include_groups=False)
    y = g.groupby(["period", "year"]).apply(f, include_groups=False)
    return b, y


def reading4(s, ss, period, df) -> list:
    """Plain-language reading of the Phase 4 results."""
    t, u = s.set_index("rule"), ss.set_index("rule")
    p3r, b, e = t.loc["p3"], t.loc["ref_base"], t.loc["ref_e1f1"]
    out = [
        f"- P3 (primary): option CAGR {p3r['option CAGR']:.1%}, Sharpe all months "
        f"{p3r['Sharpe all months']:.2f} "
        f"(traded months {p3r['Sharpe traded months']:.2f}), worst month {p3r['worst month']:.1%}, "
        "traded "
        f"{int(p3r['months traded'])} of {int(p3r['months'])} months. Base: {b['option CAGR']:.1%} "
        f"/ {b['Sharpe all months']:.2f} / "
        f"{b['worst month']:.1%}; e1f1: {e['option CAGR']:.1%} / {e['Sharpe all months']:.2f} / "
        f"{e['worst month']:.1%}.",
        "- P3 "
        f"{'beats' if p3r['Sharpe all months'] > b['Sharpe all months'] else '**does not beat**'} "
        "the base and "
        f"{'beats' if p3r['Sharpe all months'] > e['Sharpe all months'] else '**does not beat**'} "
        "e1f1 on Sharpe over all months "
        f"(paired Newey-West t {p3r['NW t vs base']:.2f} vs base, {p3r['NW t vs e1f1']:.2f} vs "
        "e1f1).",
    ]
    for n in ("p1", "p2"):
        out.append(
            f"- {n.upper()} alone: CAGR {t.loc[n, 'option CAGR']:.1%}, Sharpe "
            f"{t.loc[n, 'Sharpe all months']:.2f}, worst month "
            f"{t.loc[n, 'worst month']:.1%}, months traded {int(t.loc[n, 'months traded'])}, stops "
            f"{int(t.loc[n, 'stops'])} "
            f"({int(t.loc[n, 'stops helped'])} helped, {int(t.loc[n, 'stops hurt'])} hurt)."
        )
    out.append(
        "- Cost stress (option CAGR / Sharpe, normal -> stressed): "
        + "; ".join(
            f"{n} {t.loc[n, 'option CAGR']:.1%} / {t.loc[n, 'Sharpe all months']:.2f} -> "
            f"{u.loc[n, 'option CAGR']:.1%} / {u.loc[n, 'Sharpe all months']:.2f}"
            for n in t.index
        )
        + "."
    )
    if p3r["months traded"] < 0.5 * p3r["months"]:
        if p3r["option CAGR"] > max(b["option CAGR"], e["option CAGR"]):
            p3_vs_refs = "more"
        else:
            p3_vs_refs = "less than at least one of them"
        out.append(
            f"- P3 trades only {int(p3r['months traded'])} of {int(p3r['months'])} months; its "
            "result rests on few trades. "
            "Sharpe over all months counts the cash months as zero option return, which lowers "
            "volatility and flatters "
            f"a rule that rarely trades; on option CAGR P3 earns {p3r['option CAGR']:.1%} vs "
            f"{b['option CAGR']:.1%} for the "
            f"base and {e['option CAGR']:.1%} for e1f1 "
            f"({p3_vs_refs})."
        )
    st = df[(df.rule == "p3") & (df.stop_triggered == "yes")]
    if len(st):
        out.append(
            f"- P3's index stop: {len(st)} stops, {int((st.stop_effect == 'helped').sum())} helped "
            "and "
            f"{int((st.stop_effect == 'hurt').sum())} hurt vs holding to expiry; net effect "
            f"{(st.option_pnl_net - st.pnl_if_held).sum() / 1e5:+.2f} lakh."
        )
    return out


def charts4(df) -> None:
    """Phase 4 charts."""
    fig, ax = plt.subplots(figsize=(11, 5.5))
    for n in ("p3", "ref_e1f1", "ref_base"):
        g = df[df.rule == n]
        x = np.r_[pd.Timestamp(g.entry_date.iloc[0]), pd.to_datetime(g.next_entry).values]
        ax.plot(x, np.r_[1.0, (1 + g.option_return_on_capital_pct / 100).cumprod().values], label=n)
    for p, d in df[df.rule == "p3"].groupby("period").entry_date.min().items():
        if p != "design":
            ax.axvline(pd.Timestamp(d), color="grey", ls=":", lw=0.8)
            ax.text(pd.Timestamp(d), ax.get_ylim()[1], f" {p}", va="top", fontsize=8)
    ax.set_yscale("log")
    ax.set_title("Option-only P&L (no cash interest), all periods chained, log scale", fontsize=10)
    ax.legend()
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(OUT / "equity_all_periods.png", dpi=130)
    plt.close(fig)
    b = df[(df.rule == "ref_base") & (df.traded == "yes")]
    fig, ax = plt.subplots(figsize=(8, 5.5))
    for p, g in b.groupby("period"):
        ax.scatter(g.prem_ratio, g.option_return_on_capital_pct, s=14, label=p)
    ax.axvline(0.12, color="k", ls="--", lw=0.8)
    ax.axhline(0, color="grey", lw=0.6)
    ax.set_xlabel("prem_ratio at entry (net credit / spread width, closes)")
    ax.set_ylabel("option return, % of capital")
    ax.set_title(
        "Base put spread trades: premium vs result (dashed = P1/P3 threshold 0.12)", fontsize=10
    )
    ax.legend()
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(OUT / "prem_ratio_vs_return.png", dpi=130)
    plt.close(fig)


def write4(df, path) -> None:
    """Write the monthly Phase 4 file."""
    out = df.drop(columns=["next_entry"])
    num = out.select_dtypes("number").columns
    out[num] = out[num].round(4)
    out.to_csv(path, index=False)


def insample(cfg: dict) -> None:
    """Phase 4 design and validation (both in-sample for this idea)."""
    OUT.mkdir(parents=True, exist_ok=True)
    if (OUT / "holdout_runs.log").exists():
        logger.info("Holdout already run; in-sample results are frozen.")
        return
    ctx = load_insample(cfg)
    md = [
        "# Phase 4 report\n",
        "Base structure: Phase 1 put spread (0.95 / 0.90, max loss 10%, fallback rule). P1 = trade "
        "only if prem_ratio >= "
        f"{cfg['phase4']['prem_min']}; P2 = exit at the next close if NIFTY 50 closes below the "
        "short strike; **P3 = P1 + P2 "
        "(primary hypothesis)**. ref_* = references (recomputed in the Phase 4 engine). "
        "Option-only returns (no cash interest); "
        "Sharpe without risk-free deduction, over all months (cash months count as 0) and over "
        "traded months only. Cost stress: "
        "entry slippage x2 when India VIX at entry > 20 (ATM IV before May 2014) and x2 on every "
        "stop exit.\n",
    ]
    allrows = []
    for period in ("design", "validation"):
        df, sdf, cyc = period_runs(cfg, ctx, period, sens=True)
        main = df[~df.rule.str.startswith("sens_")]
        srs = trial_srs(cfg, ctx, period, main)
        s = summarise(main, cyc, cfg, srs)
        ss = summarise(sdf[~sdf.rule.str.startswith("sens_")], cyc, cfg)
        both = pd.concat([s.assign(costs="normal"), ss.assign(costs="stress")])
        both.to_csv(OUT / f"summary_{period}.csv", index=False)
        sens_rows = []
        for n in [r for r in df.rule.unique() if r.startswith("sens_")] + ["p3"]:
            g = df[df.rule.isin([n, "ref_base", "ref_e1f1"])]
            x = summarise(g, cyc, cfg).set_index("rule").loc[n]
            sens_rows.append(
                {
                    "rule": n,
                    "option CAGR": x["option CAGR"],
                    "Sharpe all months": x["Sharpe all months"],
                    "worst month": x["worst month"],
                    "months traded": x["months traded"],
                }
            )
        rec = reconcile(df)
        b, y = buckets(df)
        md += (
            [
                f"## {period.capitalize()} (in-sample for this idea)\n",
                f"{len(cyc)} cycles, entries {cyc.entry.min():%Y-%m-%d} to "
                f"{cyc.entry.max():%Y-%m-%d}.\n",
                fmt4(s, MAIN4),
                "",
                "Under the cost stress:\n",
                fmt4(ss, STRESS4),
                "",
                "Deflated Sharpe (35 cumulative trials; inputs: each series' monthly Sharpe, "
                "months, skewness, kurtosis; "
                f"variance of monthly Sharpe across the {len(srs)} trials in this period = "
                f"{np.var(list(srs.values()), ddof=1):.4f}):\n",
                fmt4(s, ["rule", "SR monthly", "DSR SR0 (monthly)", "DSR"]),
                "",
                "Sensitivity only (P3 prem_ratio threshold; not trials):\n",
                fmt4(
                    pd.DataFrame(sens_rows),
                    ["rule", "option CAGR", "Sharpe all months", "worst month", "months traded"],
                ),
                "",
                "P3 trades by prem_ratio bucket:\n",
                b.loc[period].round(2).to_markdown(),
                "",
                "P3 trades by year:\n",
                y.loc[period].round(2).to_markdown(),
                "",
                "Reading:\n",
            ]
            + reading4(s, ss, period, df)
            + ["", "Checks:\n"]
            + rec
            + [""]
        )
        allrows.append(df)
    df = pd.concat(allrows, ignore_index=True)
    write4(df, OUT / "monthly_pnl_phase4.csv")
    charts4(df[~df.rule.str.startswith("sens_")])
    (OUT / "phase4_report.md").write_text("\n".join(md) + "\n")
    logger.info("\n".join(md))


def frozen_v2(cfg: dict) -> str:
    """Write the frozen P3 rule file with the config hash."""
    h = hashlib.sha256(CONFIG_PATH.read_bytes()).hexdigest()
    fo_end = pd.read_parquet("data/processed/nifty_fo.parquet", columns=["date"]).date.max()
    c, p4 = cfg["costs"], cfg["phase4"]
    return "\n".join(
        [
            "# Frozen rule v2: P3 (minimum premium + index stop)\n",
            f"Written {datetime.now():%Y-%m-%d %H:%M} regardless of results (the decision to paper "
            "trade is the owner's). Config SHA-256 "
            f"`{h}`. Data in hand to {fo_end:%Y-%m-%d}; design and validation to "
            f"{cfg['phase2']['validation_end']}; holdout scored once in Phase 4. "
            "`results/phase3/frozen_rule.md` (e1f1) is unchanged.\n",
            "## Trade",
            "- NIFTY 50 index options, monthly expiry only (last expiry of each calendar month as "
            "listed by NSE; actual expiry = the contract's last trading day).",
            "- Entry: close of the first trading day after each monthly expiry; options on the "
            "next monthly expiry; S0 = NIFTY 50 close that day.",
            f"- Sell the put nearest {cfg['rules']['put_spread'][0][2]} x S0, buy the put nearest "
            f"{cfg['rules']['put_spread'][1][2]} x S0. A strike needs close > 0 and contracts "
            "traded > 0 that day; search from the listed strike nearest the target further out of "
            "the money within 1% of target; else the nearest traded strike further out of the "
            "money than the target; skip only if none.",
            "- **Premium filter:** prem_ratio = (short put close - long put close) / (short "
            "strike - long strike), entry-day closes before slippage. Trade only if prem_ratio >= "
            f"{p4['prem_min']}; otherwise hold cash that cycle.",
            "- Size: units so (spread width - net credit after slippage) x units = "
            f"{cfg['max_loss_pct']:.0%} of current capital; margin = that maximum loss.",
            "- **Index stop:** at each NIFTY 50 close after entry and before the expiry day, if "
            "the close is below the short put strike, close both legs at the next trading day's "
            "close; if that day is the expiry day, let it settle. Otherwise hold to expiry; "
            "cash-settled against the final settlement price.",
            "",
            "## Costs (VERIFY before trading)",
            f"- Slippage per unit: sell at close - max({c['slip_min']}, {c['slip_pct']:.0%} of "
            "close), buy at close + the same (stop exits included).",
            f"- STT on premium sold: {', '.join(f'{r:.4%} from {d}' for d, r in c['stt_sell'])}; "
            f"on long options expiring in the money {c['stt_itm']:.3%} of intrinsic.",
            f"- Brokerage Rs {c['brokerage']} per order; exchange "
            f"{', '.join(f'{r:.4%} from {d}' for d, r in c['exch'])}; SEBI {c['sebi']:.4%}; stamp "
            f"{c['stamp']:.3%} on premium bought; GST {c['gst']:.0%}.",
            f"- Idle cash {cfg['cash_rate']:.1%} a year (assumption).",
            "",
            "## Capital",
            f"- Paper capital Rs {cfg['capital']:,}; live units are rounded down to whole lots "
            "(NSE lot size on the entry date).",
            "",
        ]
    )


def holdout(cfg: dict) -> None:
    """Phase 4 holdout, run once and logged before any chart."""
    log = OUT / "holdout_runs.log"
    if log.exists() and log.read_text().strip():
        logger.info("Holdout already run once; not running again. Log:\n" + log.read_text())
        return
    ctx = load_holdout(cfg)
    df, sdf, cyc = period_runs(cfg, ctx, "holdout")
    s, ss = summarise(df, cyc, cfg), summarise(sdf, cyc, cfg)
    with open(log, "a") as f:
        f.write(
            f"run 1 at {datetime.now():%Y-%m-%d %H:%M:%S}, {len(cyc)} cycles "
            f"{cyc.entry.min():%Y-%m-%d} to {cyc.expiry.max():%Y-%m-%d}. "
            "Note: two earlier attempts on 2026-11-10 crashed while drawing a chart, before this "
            "log was written and "
            "before any holdout result was printed or read; rules and code for the results were "
            "unchanged and the "
            "computation is deterministic, so this run reproduces them. The log is now written "
            "before any chart.\n"
            + fmt4(
                s,
                [
                    "rule",
                    "option CAGR",
                    "Sharpe all months",
                    "worst month",
                    "CVaR99",
                    "months traded",
                ],
            )
            + "\n"
        )
    rec = reconcile(df)
    pd.concat([s.assign(costs="normal"), ss.assign(costs="stress")]).to_csv(
        OUT / "summary_holdout.csv", index=False
    )
    prev = pd.read_csv(OUT / "monthly_pnl_phase4.csv")
    write4(df, OUT / "_h.csv")
    both = pd.concat([prev, pd.read_csv(OUT / "_h.csv")], ignore_index=True)
    (OUT / "_h.csv").unlink()
    both.to_csv(OUT / "monthly_pnl_phase4.csv", index=False)
    (OUT / "frozen_rule_v2.md").write_text(frozen_v2(cfg))
    pd.DataFrame(
        columns=[
            "month",
            "entry_date",
            "expiry_date",
            "index_at_entry",
            "india_vix",
            "prem_ratio",
            "decision_e1f1",
            "decision_p3",
            "strikes",
            "lots",
            "credit",
            "stop_triggered",
            "exit_date",
            "exit_cost",
            "pnl",
            "backtest_expected_pnl",
            "notes",
        ]
    ).to_csv(OUT / "paper_trading_log.csv", index=False)
    t = s.set_index("rule")
    few = [n for n in ("p1", "p3") if t.loc[n, "months traded"] < 6]
    md = (
        [
            "## Holdout (run 1)\n",
            "**Holdout; aggregate results of the Phase 1 rules on this period were seen "
            f"earlier.** {len(cyc)} cycles, entries "
            f"{cyc.entry.min():%Y-%m-%d} to {cyc.entry.max():%Y-%m-%d}, last expiry "
            f"{cyc.expiry.max():%Y-%m-%d}.\n",
            fmt4(s, MAIN4),
            "",
            "Under the cost stress:\n",
            fmt4(ss, STRESS4),
            "",
            f"Months traded in the holdout: P1 {int(t.loc['p1', 'months traded'])}, P3 "
            f"{int(t.loc['p3', 'months traded'])} of {len(cyc)}."
            + (
                " **With fewer than 6 traded months, the holdout cannot judge "
                f"{', '.join(x.upper() for x in few)}.**"
                if few
                else ""
            ),
            "",
            "Reading (holdout):\n",
        ]
        + reading4(s, ss, "holdout", df)
        + ["", "Holdout checks:\n"]
        + rec
        + [
            "",
            "Deflated Sharpe is not computed for the holdout: the other 32 trials were never run "
            "on it, so the trial variance is unknown, and 24 months are too few.",
            "",
            "Run note: two earlier attempts crashed while drawing a chart before the log was "
            "written and before any result was read; see `holdout_runs.log`.",
        ]
    )
    with open(OUT / "phase4_report.md", "a") as f:
        f.write("\n".join(md) + "\n")
    nxt = dict(zip(ctx["cyc"].entry.dt.date.astype(str), ctx["cyc"].next_entry, strict=False))
    ch = both[~both.rule.str.startswith("sens_")].copy()
    ch["next_entry"] = ch.entry_date.astype(str).map(nxt)
    charts4(ch)
    logger.info("\n".join(md))


def check(cfg: dict) -> None:
    """Phase 4 checks."""
    out = ["# Phase 4 checks\n"]
    ctx = load_insample(cfg)
    vend = pd.Timestamp(cfg["phase2"]["validation_end"])
    assert ctx["opt"].date.max() <= vend
    runs = (
        sum(leg.startswith("run ") for leg in (OUT / "holdout_runs.log").read_text().splitlines())
        if (OUT / "holdout_runs.log").exists()
        else 0
    )
    assert runs <= 1
    out.append(
        f"- in-sample runs load no option data after {vend:%Y-%m-%d}; holdout runs logged: {runs}."
    )
    src = "".join(
        inspect.getsource(f)
        for f in (
            run,
            pick,
            fill,
            stop_exit,
            vix_proxy,
            p3.gaps,
            p3.trailing_rv,
            p2.pick_money,
            bt.pick,
        )
    )
    assert "iv_minus_future_rv_pts" not in src.replace(
        '"iv_minus_future_rv_pts": 100 * m.vrp', ""
    ) and "m.rv" not in src.replace('"realised_vol_pct": 100 * m.rv', "")
    assert "v.vrp" not in inspect.getsource(p3.gaps) and "v.rv" not in inspect.getsource(p3.gaps)
    out.append(
        "- no rule input reads `iv_minus_future_rv_pts` or the after-entry realised vol: in the "
        "rule code they appear only as "
        "output columns; the e1f1 filter uses ATM IV at entry and the trailing 21-day RV."
    )
    cyc = ctx["cyc"][ctx["cyc"].period == "design"].reset_index(drop=True)
    cyc["tri_ret"] = bt.tri_returns(cyc, ctx["ix"])
    mk = bt.vrp_table(ctx["opt"], ctx["ix"], cyc, cfg).set_index("entry")
    v = variants(cfg)
    rng = np.random.default_rng(7)
    for i in sorted(rng.choice(len(cyc), 3, replace=False)):
        c = cyc.iloc[i]
        s0 = float(ctx["ix"].close[c.entry])
        ch = ctx["opt"][
            (ctx["opt"].date == c.entry)
            & (ctx["opt"].expiry == c.contract)
            & (ctx["opt"].opt == "PE")
            & (ctx["opt"].close > 0)
            & (ctx["opt"].volume > 0)
        ]
        legs, _, _ = pick(PS, census.chain(ctx, c.entry, c.contract), s0, cfg)
        a = float(ch[ch.strike == legs[0]["k"]].close.iloc[0])
        b = float(ch[ch.strike == legs[1]["k"]].close.iloc[0])
        hand = (a - b) / (legs[0]["k"] - legs[1]["k"])
        code = run(
            "p1", v["p1"], cyc.iloc[[i]].reset_index(drop=True), ctx, cfg, "design", mk
        ).prem_ratio.iloc[0]
        assert abs(hand - code) < 1e-12
        out.append(
            f"- prem_ratio {c.entry:%Y-%m-%d}: ({a} - {b}) / ({legs[0]['k']:.0f} - "
            f"{legs[1]['k']:.0f}) = {hand:.4f} = code {code:.4f}"
        )
    df = run("p2", v["p2"], cyc, ctx, cfg, "design", mk)
    st = df[df.stop_triggered == "yes"]
    days = ctx["days"]
    for _, r in st.sample(3, random_state=7).iterrows():
        e, x = pd.Timestamp(r.entry_date), pd.Timestamp(r.expiry_date)
        d = days[(days >= e) & (days <= x)]
        closes = ctx["ix"].close.reindex(d)
        below = [j for j in range(1, len(d) - 2) if closes.iloc[j] < r.short_put_strike]
        assert below and d[below[0]].date() == pd.Timestamp(r.trigger_date).date()
        nxt = d[below[0] + 1]
        assert pd.Timestamp(r.exit_date) == nxt or r.exit_flag == "yes"
        shown = ", ".join(
            f"{dd:%m-%d} {cl:.0f}"
            for dd, cl in closes.iloc[max(0, below[0] - 2) : below[0] + 2].items()
        )
        out.append(
            f"- index stop {r.entry_date}: short strike {r.short_put_strike:.0f}; closes {shown}; "
            "first close below on "
            f"{d[below[0]]:%Y-%m-%d}; exit {r.exit_date} = next trading day close: OK"
        )
    allp = []
    for period in ("design", "validation"):
        cy = ctx["cyc"][ctx["cyc"].period == period].reset_index(drop=True)
        cy["tri_ret"] = bt.tri_returns(cy, ctx["ix"])
        m2 = bt.vrp_table(ctx["opt"], ctx["ix"], cy, cfg).set_index("entry")
        for n, ref, rr, col in (
            (
                "ref_base",
                "results/phase2/monthly_pnl_phase2.csv",
                "ref_put_spread_fallback",
                "rule",
            ),
            ("ref_e1f1", "results/phase3/monthly_pnl_phase3.csv", "e1f1", "rule"),
            (
                "ref_s7_e1",
                "results/census/monthly_pnl_census.csv",
                "s7_cash_secured_put_e1",
                "rule",
            ),
        ):
            a = run(n, v[n], cy, ctx, cfg, period, m2)
            allp.append(a)
            b = pd.read_csv(ref)
            b = b[(b[col] == rr) & (b.period == period)]
            gap = np.abs(a.capital_end.values - b.capital_end.values).max()
            assert gap < 0.01, (n, period, gap)
            out.append(f"- {n} reproduces committed {rr} ({period}): max capital gap Rs {gap:.4f}")
    out += reconcile(pd.concat(allp + [df], ignore_index=True))
    (OUT / "checks.md").write_text("\n".join(out) + "\n")
    logger.info("\n".join(out))
