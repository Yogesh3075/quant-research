from __future__ import annotations

import logging
from pathlib import Path

import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from optsell import backtest as bt
from optsell import data

matplotlib.use("Agg")
logger = logging.getLogger(__name__)

RES = Path("results")
LEGS = {
    ("S", "P"): "short_put",
    ("B", "P"): "long_put",
    ("S", "C"): "short_call",
    ("B", "C"): "long_call",
}
MONEY = [
    "credit_gross",
    "slippage_cost",
    "credit_net",
    "settlement_payout",
    "option_pnl_before_charges",
    "brokerage",
    "stt",
    "exchange_charges",
    "sebi_fees",
    "stamp_duty",
    "gst",
    "total_charges",
    "total_costs",
    "option_pnl_net",
    "cash_interest",
    "total_pnl",
]
COLS = [
    "rule",
    "period",
    "cycle_no",
    "entry_date",
    "expiry_date",
    "days_to_expiry",
    "skipped",
    "skip_reason",
    "index_at_entry",
    "index_at_expiry",
    "index_move_pct",
    "india_vix_at_entry",
    "atm_iv_at_entry_pct",
    "realised_vol_pct",
    "iv_minus_future_rv_pts",
    "short_put_strike",
    "long_put_strike",
    "short_call_strike",
    "long_call_strike",
    "short_put_entry_price",
    "long_put_entry_price",
    "short_call_entry_price",
    "long_call_entry_price",
    "short_put_contracts_traded",
    "short_call_contracts_traded",
    "short_put_settle_value",
    "long_put_settle_value",
    "short_call_settle_value",
    "long_call_settle_value",
    "capital_start",
    "units",
    "lots",
    "lot_size",
    "notional",
    "margin_used",
    "margin_pct_of_capital",
    "idle_cash",
    "max_loss_planned",
    "credit_gross",
    "slippage_cost",
    "credit_net",
    "settlement_payout",
    "option_pnl_before_charges",
    "brokerage",
    "stt",
    "exchange_charges",
    "sebi_fees",
    "stamp_duty",
    "gst",
    "total_charges",
    "total_costs",
    "costs_pct_of_credit_gross",
    "option_pnl_net",
    "cash_interest",
    "total_pnl",
    "return_on_capital_pct",
    "option_return_on_capital_pct",
    "return_on_margin_pct",
    "capital_end",
    "cumulative_pnl",
    "drawdown_from_peak_pct",
    "win",
    "outcome",
    "nifty_tri_return_pct",
]


def context(cfg: dict) -> dict:
    """Inputs for the monthly P&L files."""
    fo, ix = data.load()
    opt = fo[fo.instr == "OPTIDX"][["date", "expiry", "strike", "opt", "close", "volume", "lot"]]
    cyc = data.cycles(fo, ix)
    v = bt.vrp_table(opt, ix, cyc, cfg).set_index("entry")
    cyc["tri_ret"] = bt.tri_returns(cyc, ix)
    cyc = cyc.set_index("entry")
    book = opt[opt.date.isin(cyc.index)].set_index(["date", "expiry", "strike", "opt"]).sort_index()
    return {"opt": opt, "ix": ix, "cyc": cyc, "vrp": v, "book": book}


def legs_of(t) -> list:
    """Legs of a stored trade."""
    out = []
    for j in range(1, 5):
        s = t.get(f"leg{j}")
        if isinstance(s, str):
            side, o, k = s.split()
            out.append(
                {
                    "name": LEGS[(side, o)],
                    "side": -1 if side == "S" else 1,
                    "opt": o,
                    "k": float(k),
                    "close": float(t[f"leg{j}_close"]),
                }
            )
    return out


def charge_items(legs, units, settle, entry, cc) -> dict:
    """Recompute each charge item of a cycle from its legs and units."""
    sell = buy = itm = 0.0
    for leg in legs:
        slip = max(cc["slip_min"], cc["slip_pct"] * leg["close"])
        if leg["side"] < 0:
            sell += max(0.0, leg["close"] - slip) * units
        else:
            buy += (leg["close"] + slip) * units
            itm += bt.intrinsic(leg["opt"], leg["k"], settle) * units
    turnover = sell + buy
    c = {
        "brokerage": cc["brokerage"] * len(legs),
        "stt": bt.rate_on(cc["stt_sell"], entry) * sell + cc["stt_itm"] * itm,
        "exchange_charges": bt.rate_on(cc["exch"], entry) * turnover,
        "sebi_fees": cc["sebi"] * turnover,
        "stamp_duty": cc["stamp"] * buy,
    }
    c["gst"] = cc["gst"] * (c["brokerage"] + c["exchange_charges"] + c["sebi_fees"])
    return c


def rows(rule, period, trades, ctx, cfg: dict) -> list:
    """Monthly rows of one rule and period."""
    out = []
    peak = cfg["capital"]
    for n, (_, t) in enumerate(trades.iterrows(), 1):
        c = ctx["cyc"].loc[t.entry]
        v = ctx["vrp"].loc[t.entry]
        r = {
            "rule": rule,
            "period": period,
            "cycle_no": n,
            "entry_date": t.entry.date(),
            "expiry_date": t.expiry.date(),
            "days_to_expiry": (t.expiry - t.entry).days,
            "skipped": "yes" if isinstance(t.skipped, str) and t.skipped else "no",
            "skip_reason": t.skipped if isinstance(t.skipped, str) else "",
            "index_at_entry": t.S0,
            "index_at_expiry": t.settle,
            "index_move_pct": 100 * (t.settle / t.S0 - 1),
            "india_vix_at_entry": v.vix * 100 if pd.notna(v.vix) else np.nan,
            "atm_iv_at_entry_pct": 100 * v.iv,
            "realised_vol_pct": 100 * v.rv,
            "iv_minus_future_rv_pts": 100 * v.vrp,
            "capital_start": t.capital_before,
            "cash_interest": t.interest,
            "total_pnl": t.net,
            "capital_end": t.capital_after,
            "nifty_tri_return_pct": 100 * c.tri_ret,
            "next_entry": t.next_entry,
        }
        if r["skipped"] == "yes":
            r.update({k: 0.0 for k in MONEY if k not in ("cash_interest", "total_pnl")})
            r.update(
                {
                    "units": 0.0,
                    "notional": 0.0,
                    "margin_used": 0.0,
                    "margin_pct_of_capital": 0.0,
                    "idle_cash": t.capital_before,
                    "outcome": "skipped",
                    "win": "no",
                }
            )
        else:
            legs = legs_of(t)
            u = t.units
            for leg in legs:
                r[f"{leg['name']}_strike"] = leg["k"]
                r[f"{leg['name']}_entry_price"] = leg["close"]
                r[f"{leg['name']}_settle_value"] = bt.intrinsic(leg["opt"], leg["k"], t.settle)
                if leg["side"] < 0:
                    code = "PE" if leg["opt"] == "P" else "CE"
                    b = ctx["book"].loc[(t.entry, c.contract, leg["k"], code)]
                    r[f"{leg['name']}_contracts_traded"] = float(b.volume)
                    lot = b.lot
            r["lot_size"] = lot if pd.notna(lot) else np.nan
            r["lots"] = np.floor(u / lot) if pd.notna(lot) else np.nan
            shorts = sum(1 for leg in legs if leg["side"] < 0)
            r.update(
                {
                    "units": u,
                    "notional": u * t.S0 * shorts,
                    "margin_used": t.margin,
                    "margin_pct_of_capital": 100 * t.margin / t.capital_before,
                    "idle_cash": max(0.0, t.capital_before - t.margin),
                    "max_loss_planned": "unlimited"
                    if pd.isna(t.maxloss_plan)
                    else round(t.maxloss_plan, 2),
                }
            )
            r["credit_gross"] = u * sum(-leg["side"] * leg["close"] for leg in legs)
            r["slippage_cost"] = t.slippage
            r["credit_net"] = r["credit_gross"] - t.slippage
            r["settlement_payout"] = -u * t.payoff_unit + 0.0
            r["option_pnl_before_charges"] = r["credit_net"] - r["settlement_payout"]
            r.update(charge_items(legs, u, t.settle, t.entry, cfg["costs"]))
            r["total_charges"] = t.charges
            r["total_costs"] = t.slippage + t.charges
            r["option_pnl_net"] = r["option_pnl_before_charges"] - t.charges
            r["costs_pct_of_credit_gross"] = (
                100 * r["total_costs"] / r["credit_gross"] if r["credit_gross"] else np.nan
            )
            r["return_on_margin_pct"] = 100 * r["option_pnl_net"] / t.margin
            r["win"] = "yes" if r["option_pnl_net"] > 0 else "no"
            if r["settlement_payout"] <= 0:
                r["outcome"] = "full profit"
            elif pd.notna(t.maxloss_plan) and r["option_pnl_before_charges"] <= -t.maxloss_plan + 1:
                r["outcome"] = "max loss"
            else:
                r["outcome"] = "partial loss"
        r["return_on_capital_pct"] = 100 * t.net / t.capital_before
        r["option_return_on_capital_pct"] = 100 * r["option_pnl_net"] / t.capital_before
        r["cumulative_pnl"] = t.capital_after - cfg["capital"]
        peak = max(peak, t.capital_after)
        r["drawdown_from_peak_pct"] = 100 * (t.capital_after / peak - 1)
        out.append(r)
    return out


def build(cfg: dict, ctx) -> pd.DataFrame:
    """Monthly rows of every rule and period."""
    out = []
    for rule in bt.RULES:
        for period, sfx in (("development", ""), ("holdout", "_holdout")):
            t = pd.read_csv(
                RES / f"trades_{rule}{sfx}.csv", parse_dates=["entry", "expiry", "next_entry"]
            )
            out += rows(rule, period, t, ctx, cfg)
    df = pd.DataFrame(out)
    for c in COLS:
        if c not in df:
            df[c] = np.nan
    return df[COLS + ["next_entry"]]


def reconcile(df, cfg: dict, ctx) -> list:
    """Reconciliation checks of the monthly file."""
    lhs = (
        df.credit_gross
        - df.slippage_cost
        - df.settlement_payout
        - df.total_charges
        + df.cash_interest
    )
    ok1 = (lhs - df.total_pnl).abs().max()
    ok2 = (df.capital_start + df.total_pnl - df.capital_end).abs().max()
    items = df[["brokerage", "stt", "exchange_charges", "sebi_fees", "stamp_duty", "gst"]].sum(
        axis=1
    )
    ok3 = (items - df.total_charges).abs().max()
    chain_gap = 0.0
    for _, g in df.groupby(["rule", "period"]):
        chain_gap = max(
            chain_gap,
            (g.capital_start.iloc[1:].values - g.capital_end.iloc[:-1].values).__abs__().max(),
        )
    dev = ctx["cyc"][
        ctx["cyc"].index.isin(df[df.period == "development"].entry_date.astype("datetime64[ns]"))
    ]
    dev = dev.reset_index()
    fresh = {}
    for rule in bt.RULES:
        sim = bt.simulate(rule, dev, ctx["opt"], ctx["ix"], cfg, cfg["cash_rate"])
        last = df[(df.rule == rule) & (df.period == "development")].capital_end.iloc[-1]
        fresh[rule] = abs(sim.capital_after.iloc[-1] - last)
    lines = [
        "- credit_gross - slippage - payout - charges + interest = total_pnl: max gap Rs "
        f"{ok1:.6f} -> {'PASS' if ok1 < 1 else 'FAIL'}",
        f"- capital_end = capital_start + total_pnl: max gap Rs {ok2:.6f} -> "
        f"{'PASS' if ok2 < 1 else 'FAIL'}",
        f"- capital_start = previous capital_end: max gap Rs {chain_gap:.6f} -> "
        f"{'PASS' if chain_gap < 1 else 'FAIL'}",
        f"- charge items sum to stored total_charges: max gap Rs {ok3:.6f} -> "
        f"{'PASS' if ok3 < 1 else 'FAIL'}",
    ]
    for rule, gap in fresh.items():
        lines.append(
            f"- last development capital_end vs fresh development backtest, {rule}: gap Rs "
            f"{gap:.6f} -> "
            f"{'PASS' if gap < 1 else 'FAIL'}"
        )
    return lines


def summary(df) -> pd.DataFrame:
    """Totals and averages per rule and period."""
    out = []
    for (rule, period), g in df.groupby(["rule", "period"], sort=False):
        tr = g[g.skipped == "no"]
        r = {
            "rule": rule,
            "period": period,
            "months": len(g),
            "traded": len(tr),
            "skipped": int((g.skipped == "yes").sum()),
        }
        for m in MONEY:
            r[f"total_{m}"] = g[m].sum()
        for m in MONEY:
            r[f"avg_{m}"] = tr[m].mean()
        w, lo = tr[tr.option_pnl_net > 0], tr[tr.option_pnl_net <= 0]
        r.update(
            {
                "win_rate_pct": 100 * len(w) / len(tr),
                "avg_win": w.option_pnl_net.mean(),
                "avg_loss": lo.option_pnl_net.mean(),
                "avg_win_pct_of_capital": w.option_return_on_capital_pct.mean(),
                "avg_loss_pct_of_capital": lo.option_return_on_capital_pct.mean(),
                "worst_month_pct": g.return_on_capital_pct.min(),
                "best_month_pct": g.return_on_capital_pct.max(),
                "costs_pct_of_credit_gross": 100 * tr.total_costs.sum() / tr.credit_gross.sum(),
                "capital_end": g.capital_end.iloc[-1],
            }
        )
        out.append(r)
    return pd.DataFrame(out)


def monthly(cfg: dict) -> None:
    """Write the monthly P&L files and their checks."""
    ctx = context(cfg)
    df = build(cfg, ctx)
    out = df.drop(columns="next_entry")
    num = out.select_dtypes("number").columns
    out[num] = out[num].round(2)
    for rule in bt.RULES:
        out[out.rule == rule].to_csv(RES / f"monthly_pnl_{rule}.csv", index=False)
    out.to_csv(RES / "monthly_pnl_all.csv", index=False)
    s = summary(df)
    s[s.select_dtypes("number").columns] = s.select_dtypes("number").round(2)
    s.to_csv(RES / "monthly_pnl_summary.csv", index=False)
    blank = [c for c in COLS if out[out.period == "holdout"][c].isna().all()]
    lines = reconcile(df, cfg, ctx)
    text = (
        "# Monthly P&L file checks\n\n"
        + "\n".join(lines)
        + f"\n\nRows: {len(out)} ({', '.join(f'{r} {(out.rule == r).sum()}' for r in bt.RULES)}).\n"
        "Holdout rows built from the stored trades_<rule>_holdout.csv files; the holdout command "
        "was not run. "
        f"Columns entirely blank in the holdout: {', '.join(blank) if blank else 'none'}.\n"
    )
    (RES / "monthly_pnl_checks.md").write_text(text)
    logger.info(text)


def met(r, d, rf) -> dict:
    """Return statistics of a monthly return series."""
    d = d.reset_index(drop=True)
    m = bt.metrics(pd.Series(np.asarray(r, float)), d, bt.cash_returns(d, rf))
    return {k: m[k] for k in ("CAGR", "Sharpe", "MaxDD", "Worst month", "Worst 3m", "CVaR99")}


def cyc_of(g) -> pd.DataFrame:
    """Cycle frame of a rule's rows."""
    return pd.DataFrame(
        {"entry": pd.to_datetime(g.entry_date).values, "next_entry": g.next_entry.values}
    )


def lever(g, mult, rate) -> tuple:
    """Returns at a leverage multiple, stopping on ruin."""
    caps, rets, stop = 1.0, [], ""
    for _, r in g.iterrows():
        m = mult * r.margin_pct_of_capital / 100
        if m > 1:
            stop = f"margin exceeds capital at entry {r.entry_date}"
            break
        days = (r.next_entry - pd.Timestamp(r.entry_date)).days
        ret = mult * r.option_return_on_capital_pct / 100 + rate * (1 - m) * days / 365
        caps *= 1 + ret
        rets.append(ret)
        if caps <= 0:
            stop = f"capital fell to zero at entry {r.entry_date}"
            break
    return rets, stop


def pct(v) -> str:
    """A fraction as a percentage string."""
    return f"{v:.1%}"


def table(d) -> str:
    """A diagnostics table as Markdown."""
    f = d.copy()
    for c in f.columns:
        if c in ("Sharpe",):
            f[c] = f[c].map(lambda v: f"{v:.2f}")
        elif f[c].dtype.kind == "f":
            f[c] = f[c].map(lambda v: "" if pd.isna(v) else pct(v))
    return f.to_markdown(index=False)


def diagnostics(cfg: dict) -> None:
    """Development-only diagnostics report."""
    ctx = context(cfg)
    df = build(cfg, ctx)
    dev = df[df.period == "development"].copy()
    rate = cfg["cash_rate"]
    tabs, md = (
        [],
        [
            "# Diagnostics (development period only)\n",
            f"{dev.cycle_no.max()} monthly cycles, {dev.entry_date.min()} to "
            f"{dev.expiry_date.max()}. "
            "Option return = option_pnl_net / capital at the start of the cycle (no cash "
            "interest); "
            "its Sharpe is mean / std x sqrt(12) with no risk-free deduction. All other Sharpe "
            "ratios are "
            f"in excess of {rate:.1%} cash.\n",
        ],
    )

    def add(name, d):
        x = d.copy()
        x.insert(0, "table", name)
        tabs.append(x)

    opt_rows = []
    for rule in bt.RULES:
        g = dev[dev.rule == rule]
        opt_rows.append({"rule": rule, **met(g.option_return_on_capital_pct / 100, cyc_of(g), 0.0)})
    o = pd.DataFrame(opt_rows)
    add("option_pnl_no_interest", o)
    yr = dev.assign(
        year=pd.to_datetime(dev.entry_date).dt.year, r=dev.option_return_on_capital_pct / 100
    )
    yearly = yr.groupby(["year", "rule"]).r.apply(lambda x: (1 + x).prod() - 1).unstack()[bt.RULES]
    add("option_return_by_year", yearly.reset_index())
    md += [
        "## 1. Option P&L without cash interest\n",
        table(o),
        "",
        "Yearly option return (compounded option_pnl_net / capital, % of capital):\n",
        yearly.map(pct).to_markdown(),
        "",
    ]
    neg_years = {r: int((yearly[r] < 0).sum()) for r in bt.RULES}
    md.append(
        "Reading: "
        + "; ".join(
            f"{r} compounds at {o.set_index('rule').loc[r, 'CAGR']:.1%} a year from options alone "
            "(Sharpe "
            f"{o.set_index('rule').loc[r, 'Sharpe']:.2f}), with {neg_years[r]} losing years of "
            f"{len(yearly)}"
            for r in bt.RULES
        )
        + f". Compare with {rate:.1%} a year on cash.\n"
    )

    tr = dev[dev.skipped == "no"]
    rom = []
    for rule in bt.RULES:
        g = tr[tr.rule == rule]
        rom.append(
            {
                "rule": rule,
                "avg monthly return on margin": g.return_on_margin_pct.mean() / 100,
                "total (sum pnl / sum margin)": g.option_pnl_net.sum() / g.margin_used.sum(),
                "worst month on margin": g.return_on_margin_pct.min() / 100,
            }
        )
    rom = pd.DataFrame(rom)
    add("return_on_margin", rom)
    ry = (
        tr.assign(year=pd.to_datetime(tr.entry_date).dt.year)
        .groupby(["year", "rule"])
        .apply(lambda g: g.option_pnl_net.sum() / g.margin_used.sum(), include_groups=False)
        .unstack()[bt.RULES]
    )
    add("return_on_margin_by_year", ry.reset_index())
    md += [
        "## 2. Return on margin used\n",
        table(rom),
        "",
        "By year (sum of option_pnl_net / sum of margin used in traded months):\n",
        ry.map(pct).to_markdown(),
        "",
        "Reading: "
        + "; ".join(
            f"{r['rule']} averages {r['avg monthly return on margin']:.1%} a month on margin, "
            f"worst month {r['worst month on margin']:.0%}"
            for _, r in rom.iterrows()
        )
        + ".\n",
    ]

    lev = []
    for rule in bt.RULES:
        g = dev[dev.rule == rule]
        for mult in (1, 2, 3):
            rets, stop = lever(g, mult, rate)
            m = met(rets, cyc_of(g.iloc[: len(rets)]), cfg["rf"])
            lev.append({"rule": rule, "leverage": f"{mult}x", **m, "stopped": stop or "no"})
    lev = pd.DataFrame(lev)
    add("leverage", lev)
    sh = lev.pivot(index="rule", columns="leverage", values="Sharpe").loc[bt.RULES]
    spread = (sh.max(axis=1) - sh.min(axis=1)).max()
    md += [
        "## 3. Leverage (units and margin x1, x2, x3; same strikes and prices; idle cash at "
        f"{rate:.1%})\n",
        table(lev),
        "",
        "Reading: Sharpe by leverage: "
        + "; ".join(
            f"{r} {sh.loc[r, '1x']:.2f} / {sh.loc[r, '2x']:.2f} / {sh.loc[r, '3x']:.2f}"
            for r in bt.RULES
        )
        + (
            f". Sharpe does not improve with leverage (largest change {spread:.2f}): leverage "
            "scales the gains and "
            "the losses together, and the worst month and CVaR grow roughly in proportion."
            if (sh["3x"] <= sh["1x"] + 0.05).all()
            else ". Sharpe changes with leverage here; see the table."
        )
        + (
            " Brokerage is a fixed Rs 20 per order and is scaled with the rest, a negligible "
            "approximation.\n"
        ),
    ]

    sl = []
    base = ctx["cyc"].reset_index()
    base = base[base.entry.isin(pd.to_datetime(dev.entry_date))].reset_index(drop=True)
    for k in (0.5, 1.0, 2.0):
        c2 = {
            **cfg,
            "costs": {
                **cfg["costs"],
                "slip_min": cfg["costs"]["slip_min"] * k,
                "slip_pct": cfg["costs"]["slip_pct"] * k,
            },
        }
        for rule in bt.RULES:
            t = bt.simulate(rule, base, ctx["opt"], ctx["ix"], c2, rate)
            ro = (t.net - t.interest) / t.capital_before
            m = met(t.ret, base, cfg["rf"])
            sl.append(
                {
                    "rule": rule,
                    "slippage": f"x{k:g}",
                    **m,
                    "option-only CAGR": met(ro, base, 0.0)["CAGR"],
                }
            )
    sl = pd.DataFrame(sl).sort_values(
        ["rule", "slippage"],
        key=lambda s: s.map({r: i for i, r in enumerate(bt.RULES)}) if s.name == "rule" else s,
    )
    add("slippage", sl)
    sc = sl.pivot(index="rule", columns="slippage", values="option-only CAGR").loc[bt.RULES]
    md += [
        "## 4. Slippage sensitivity (x0.5 = max(0.25, 1.5%); x2 = max(1, 6%); charges unchanged)\n",
        table(sl),
        "",
        "Reading: option-only CAGR at slippage x0.5 / x1 / x2: "
        + "; ".join(
            f"{r} {sc.loc[r, 'x0.5']:.1%} / {sc.loc[r, 'x1']:.1%} / {sc.loc[r, 'x2']:.1%}"
            for r in bt.RULES
        )
        + ". Going from x0.5 to x2 slippage changes option-only CAGR by "
        + ", ".join(
            f"{(sc.loc[r, 'x2'] - sc.loc[r, 'x0.5']) * 100:+.1f} pts ({r})" for r in bt.RULES
        )
        + ", compared with option-only CAGRs at x1 of "
        + ", ".join(f"{sc.loc[r, 'x1']:.1%}" for r in bt.RULES)
        + ".\n",
    ]

    sub = []
    for name, lo, hi in (("2008-2015", 2008, 2015), ("2016-end", 2016, 2100)):
        for rule in bt.RULES:
            g = dev[(dev.rule == rule) & pd.to_datetime(dev.entry_date).dt.year.between(lo, hi)]
            sub.append(
                {
                    "rule": rule,
                    "period": name,
                    **met(g.option_return_on_capital_pct / 100, cyc_of(g), 0.0),
                }
            )
    sub = pd.DataFrame(sub)
    add("subperiods_option_only", sub)
    sp = sub.pivot(index="rule", columns="period", values="CAGR").loc[bt.RULES]
    md += [
        "## 5. Sub-periods (option P&L only, no cash interest)\n",
        table(sub),
        "",
        "Reading: option-only CAGR 2008-2015 vs 2016-end: "
        + "; ".join(
            f"{r} {sp.loc[r, '2008-2015']:.1%} vs {sp.loc[r, '2016-end']:.1%}" for r in bt.RULES
        )
        + ".\n",
    ]

    ill = []
    for rule in bt.RULES:
        r = tr[tr.rule == rule].option_return_on_capital_pct / 100
        pos, neg = r[r > 0].sort_values(ascending=False), r[r < 0].sort_values()
        ill.append(
            {
                "rule": rule,
                "months won": (r > 0).mean(),
                "profit from best 10 months": pos.head(10).sum() / pos.sum(),
                "losses from worst 5 months": neg.head(5).sum() / neg.sum(),
                "avg win": pos.mean(),
                "avg loss": neg.mean(),
                "net option return (sum)": r.sum(),
            }
        )
    ill = pd.DataFrame(ill)
    add("win_rate_illusion", ill)
    md += [
        "## 6. Win-rate illusion (traded months, option return as % of capital)\n",
        table(ill),
        "",
        "Reading: "
        + "; ".join(
            f"{x['rule']} wins {x['months won']:.0%} of months, but the worst 5 months are "
            f"{x['losses from worst 5 months']:.0%} of all losses and an average loss is "
            f"{abs(x['avg loss'] / x['avg win']):.1f}x an average win"
            for _, x in ill.iterrows()
        )
        + ".\n",
    ]

    sk = dev[dev.skipped == "yes"][
        ["rule", "entry_date", "expiry_date", "skip_reason", "index_move_pct"]
    ].copy()
    sk["index_move_pct"] = sk.index_move_pct.map(lambda v: f"{v:+.1f}%")
    add("skipped", sk)
    big = (
        dev[(dev.skipped == "yes") & (dev.index_move_pct < -5)]
        .drop_duplicates("entry_date")
        .sort_values("entry_date")
    )
    md += [
        "## 7. Skipped months (no traded strike within 1% of target)\n",
        sk.to_markdown(index=False),
        "",
        f"{len(sk)} rule-months were skipped; in {big.entry_date.nunique()} of these cycles the "
        "index fell more "
        "than 5% ("
        + ", ".join(
            f"{d} {v:+.1f}%" for d, v in zip(big.entry_date, big.index_move_pct, strict=False)
        )
        + "). "
        "These skips may hide losses a live trader would have taken: with a less strict liquidity "
        "rule, or a "
        "quote rather than a last trade, the position would have been opened. No hypothetical P&L "
        "is "
        "estimated for them.\n",
    ]

    pd.concat(tabs, ignore_index=True).to_csv(RES / "diagnostics_tables.csv", index=False)
    (RES / "diagnostics.md").write_text("\n".join(md))

    g = dev[dev.rule == "put_spread"]
    x = pd.to_datetime(g.expiry_date)
    fig, ax = plt.subplots(figsize=(12, 4.5))
    y = g.option_pnl_net / 1e5
    ax.bar(x, y, width=25, color=np.where(g.option_pnl_net < 0, "tab:red", "tab:blue"))
    n = 0
    for d, v, p in zip(x, y, g.option_return_on_capital_pct, strict=False):
        if p < -4:
            ax.annotate(
                f"{d:%b %Y}\n{p:.1f}%",
                (d, v),
                textcoords="offset points",
                xytext=(0, -16 - 18 * (n % 2)),
                ha="center",
                va="top",
                fontsize=7,
            )
            n += 1
    ax.set_ylim(y.min() * 1.45, y.max() * 1.3)
    ax.axhline(0, color="k", lw=0.8)
    ax.set_ylabel("option P&L net, Rs lakh")
    ax.set_title(
        "Put spread: monthly option P&L net of costs, no cash interest (by expiry month; labels: "
        "losses worse than 4% of capital)",
        fontsize=10,
    )
    ax.grid(alpha=0.3, axis="y")
    fig.tight_layout()
    fig.savefig(RES / "monthly_pnl.png", dpi=130)
    plt.close(fig)
    logger.info("\n".join(md))
