from __future__ import annotations

import logging
from datetime import datetime
from math import erf, exp, log, sqrt
from pathlib import Path

import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.stats import norm

from optsell import backtest as bt
from optsell import data, marking, report
from optsell.pricing import iv, put_delta

matplotlib.use("Agg")
logger = logging.getLogger(__name__)

OUT = Path("results/phase2")
REFS = {
    "ref_put_spread_p1skip": ("put_spread", "phase1"),
    "ref_put_spread_fallback": ("put_spread", "fallback"),
    "ref_strangle_p1skip": ("strangle", "phase1"),
    "ref_strangle_fallback": ("strangle", "fallback"),
}
EXTRA = [
    "target_delta",
    "short_put_iv",
    "long_put_iv",
    "short_put_delta",
    "long_put_delta",
    "fallback_used",
    "worst_mtm_pct",
    "worst_mtm_day",
    "days_in_loss",
    "pnl_day10_pct",
    "pnl_day15_pct",
    "worst_mtm_date",
    "mark_carried_days",
    "max_risk_pct",
]


def load(cfg: dict) -> dict:
    """Shared inputs for Phase 2."""
    p = cfg["phase2"]
    fo, ix = data.load()
    cyc = data.cycles(fo, ix)
    vend = pd.Timestamp(p["validation_end"])
    cyc = cyc[cyc.expiry <= vend].reset_index(drop=True)
    fo = fo[fo.date <= vend]
    cyc["period"] = np.where(cyc.entry <= pd.Timestamp(p["design_end"]), "design", "validation")
    opt = fo[fo.instr == "OPTIDX"][["date", "expiry", "strike", "opt", "close", "volume", "lot"]]
    days = pd.DatetimeIndex(sorted(fo.date.unique()))
    return {
        "opt": opt,
        "ix": ix,
        "cyc": cyc,
        "days": days,
        "bk": marking.book(opt, cyc.contract.unique()),
    }


def traded(ch, code) -> pd.DataFrame:
    """Strikes with a positive close and volume."""
    return ch[(ch.opt == code) & (ch.close > 0) & (ch.volume > 0)].sort_values("strike")


def greeks(p, s0, t, cfg: dict) -> pd.DataFrame:
    """Implied vol and delta of each put in the chain."""
    r, q = cfg["rf"], cfg["phase2"]["div_yield"]
    p = p.copy()
    p["iv"] = [
        np.nan if c < max(k - s0, 0.0) else iv(c, s0, k, t, r, "P", q)
        for c, k in zip(p.close, p.strike, strict=False)
    ]
    p = p.dropna(subset=["iv"])
    p["delta"] = put_delta(s0, p.strike.values, t, r, p.iv.values, q)
    return p


def pick_delta(p, target, band, below=None) -> tuple:
    """Put nearest a target |delta| (optionally below a strike)."""
    c = p if below is None else p[p.strike < below]
    if c.empty:
        return None, False
    i = (c.delta.abs() - target).abs().idxmin()
    if abs(abs(c.delta[i]) - target) <= band:
        return c.loc[i], False
    otm = c[c.delta.abs() < target]
    if otm.empty:
        return None, False
    return otm.loc[otm.delta.abs().idxmax()], True


def pick_money(ch, o, target, cfg: dict, skip) -> tuple:
    """Put nearest a moneyness target, with the Phase 1 fallback."""
    r = bt.pick(ch, o, target, cfg["strike_band"])
    if r is not None or skip == "phase1":
        return r, False
    c = traded(ch, "PE" if o == "P" else "CE")
    c = c[c.strike <= target] if o == "P" else c[c.strike >= target]
    if c.empty:
        return None, False
    return c.loc[(c.strike - target).abs().idxmin()], True


def leg(r, o, side, p=None) -> dict:
    """A leg record from a chain row."""
    d = {
        "opt": o,
        "side": side,
        "k": float(r.strike),
        "close": float(r.close),
        "volume": float(r.volume),
        "lot": r.lot,
        "iv": np.nan,
        "delta": np.nan,
    }
    if p is not None and r.strike in p.strike.values:
        x = p[p.strike == r.strike].iloc[0]
        d["iv"], d["delta"] = x.iv, x.delta
    return d


def select(v, ch, s0, t, cfg: dict) -> tuple:
    """Legs of a Phase 2 variant on the entry day."""
    p2 = cfg["phase2"]
    puts = greeks(traded(ch, "PE"), s0, t, cfg)
    if v["kind"] == "ref":
        legs, fb = [], False
        for o, side, m in cfg["rules"][v["rule"]]:
            r, f = pick_money(ch, o, m * s0, cfg, v["skip"])
            if r is None:
                return None, False, f"no traded {o} strike near {m:.2f} x S0"
            legs.append(leg(r, o, side, puts if o == "P" else None))
            fb = fb or f
        return legs, fb, ""
    sh, fb = pick_delta(puts, v["delta"], p2["delta_band"])
    if sh is None:
        return None, False, f"no traded put at or beyond |delta| {v['delta']:.2f}"
    legs = [leg(sh, "P", -1, puts)]
    if v["hedge"] == "H1":
        lg, f2 = pick_delta(puts, p2["hedge_delta"], p2["delta_band"], below=sh.strike)
        if lg is None:
            return None, fb, "no traded put at or beyond |delta| 0.05 below the short strike"
        legs.append(leg(lg, "P", 1, puts))
        fb = fb or f2
    elif v["hedge"] == "H2":
        c = traded(ch, "PE")
        c = c[c.strike <= sh.strike - p2["h2_width"] * s0]
        if c.empty:
            return None, fb, "no traded put at or below short strike - 5% of S0"
        legs.append(leg(c.iloc[-1], "P", 1, greeks(c.iloc[[-1]], s0, t, cfg)))
    return legs, fb, ""


def trade(v, legs, s0, settle, capital, days_held, entry, cfg: dict, rate) -> dict | None:
    """One Phase 2 cycle."""
    cc, p2 = cfg["costs"], cfg["phase2"]
    for leg in legs:
        slip = max(cc["slip_min"], cc["slip_pct"] * leg["close"])
        leg["px"] = max(0.0, leg["close"] - slip) if leg["side"] < 0 else leg["close"] + slip
        leg["slip"] = leg["px"] - leg["close"] if leg["side"] > 0 else leg["close"] - leg["px"]
    credit = sum(-leg["side"] * leg["px"] for leg in legs)
    sizing = (
        "notional"
        if v.get("rule") == "strangle"
        else "stress"
        if v.get("hedge") == "H3"
        else "spread"
    )
    plan = np.nan
    if sizing == "spread":
        puts = [leg["k"] for leg in legs if leg["opt"] == "P"]
        calls = [leg["k"] for leg in legs if leg["opt"] == "C"]
        width = max(max(puts) - min(puts), (max(calls) - min(calls)) if calls else 0)
        maxloss = width - credit
        if maxloss <= 0:
            return None
        units = cfg["max_loss_pct"] * capital / maxloss
        margin = plan = units * maxloss
    elif sizing == "notional":
        units = cfg["strangle_notional"] * capital / s0
        margin = 2 * cfg["strangle_margin"] * units * s0
    else:
        den = legs[0]["k"] - (1 - p2["stress_drop"]) * s0 - credit
        if den <= 0:
            return None
        units = cfg["max_loss_pct"] * capital / den
        margin = p2["naked_margin"] * units * s0
    payoff = sum(leg["side"] * bt.intrinsic(leg["opt"], leg["k"], settle) for leg in legs)
    low = (1 - p2["stress_drop"]) * s0
    stress = -units * (
        credit + sum(leg["side"] * bt.intrinsic(leg["opt"], leg["k"], low) for leg in legs)
    )
    items = report.charge_items(legs, units, settle, entry, cc)
    charges = sum(items.values())
    slippage = sum(leg["slip"] * units for leg in legs)
    interest = rate * max(0.0, capital - margin) * days_held / 365
    return {
        "units": units,
        "credit": credit,
        "payoff_unit": payoff,
        "margin": margin,
        "margin_pct": margin / capital,
        "gross": units * (credit + payoff) + slippage,
        "slippage": slippage,
        "charges": charges,
        "costs": slippage + charges,
        "interest": interest,
        "net": units * (credit + payoff) - charges + interest,
        "maxloss_plan": plan,
        "max_risk_pct": 100 * (plan if sizing == "spread" else stress) / capital,
    }


def simulate(v, cyc, ctx, cfg: dict, rate, mark=True) -> pd.DataFrame:
    """Run a variant over all cycles."""
    capital = cfg["capital"]
    rows = []
    for _, c in cyc.iterrows():
        s0 = float(ctx["ix"].close[c.entry])
        t = (c.expiry - c.entry).days / 365
        ch = bt.chain(ctx["opt"], c.entry, c.contract)
        row = {
            "entry": c.entry,
            "expiry": c.expiry,
            "next_entry": c.next_entry,
            "S0": s0,
            "settle": c.settle,
            "capital_before": capital,
            "target_delta": v.get("delta", np.nan),
            "fallback_used": "no",
        }
        days_held = (c.next_entry - c.entry).days
        legs, fb, why = select(v, ch, s0, t, cfg)
        tr = trade(v, legs, s0, c.settle, capital, days_held, c.entry, cfg, rate) if legs else None
        if legs and tr is None:
            why = "sizing denominator not positive"
        if tr is None:
            interest = rate * capital * days_held / 365
            row.update({"skipped": why, "net": interest, "interest": interest})
        else:
            for j, leg in enumerate(legs):
                row[f"leg{j + 1}"] = (
                    f"{'S' if leg['side'] < 0 else 'B'} {leg['opt']} {leg['k']:.0f}"
                )
                row[f"leg{j + 1}_close"] = leg["close"]
                row[f"leg{j + 1}_px"] = leg["px"]
                name = report.LEGS[("S" if leg["side"] < 0 else "B", leg["opt"])]
                if leg["opt"] == "P":
                    row[f"{name}_iv"], row[f"{name}_delta"] = leg["iv"], leg["delta"]
            row.update(tr)
            row["settle_value"] = tr["units"] * tr["payoff_unit"]
            row["skipped"] = ""
            row["fallback_used"] = "yes" if fb else "no"
            if mark:
                d = ctx["days"][(ctx["days"] >= c.entry) & (ctx["days"] <= c.expiry)]
                row.update(marking.mark(legs, tr["units"], capital, c.contract, d, ctx["bk"]))
        capital += row["net"]
        row["capital_after"] = capital
        row["ret"] = row["net"] / row["capital_before"]
        rows.append(row)
    return pd.DataFrame(rows)


def variants(cfg: dict) -> dict:
    """The six pre-registered delta and hedge variants plus references."""
    v = {
        n: {"name": n, "kind": "delta", "delta": d, "hedge": h}
        for n, (d, h) in cfg["phase2"]["variants"].items()
    }
    v.update({n: {"name": n, "kind": "ref", "rule": r, "skip": s} for n, (r, s) in REFS.items()})
    return v


def context(ctx, cyc, cfg: dict) -> dict:
    """Per-cycle inputs (chains, settlement, marks)."""
    c = cyc.copy()
    c["tri_ret"] = bt.tri_returns(c, ctx["ix"])
    vr = bt.vrp_table(ctx["opt"], ctx["ix"], c, cfg).set_index("entry")
    book = (
        ctx["opt"][ctx["opt"].date.isin(c.entry)]
        .set_index(["date", "expiry", "strike", "opt"])
        .sort_index()
    )
    return {"cyc": c.set_index("entry"), "vrp": vr, "book": book}


def run_period(cfg: dict, ctx, period) -> tuple:
    """Run every variant on one period."""
    cyc = ctx["cyc"][ctx["cyc"].period == period].reset_index(drop=True)
    rc = context(ctx, cyc, cfg)
    out, trades = [], {}
    for n, v in variants(cfg).items():
        t = simulate(v, cyc, ctx, cfg, cfg["cash_rate"])
        trades[n] = t
        r = pd.DataFrame(report.rows(n, period, t, rc, cfg))
        for c in EXTRA:
            r[c] = t[c].values if c in t else np.nan
        out.append(r)
    df = pd.concat(out, ignore_index=True)
    for c in report.COLS:
        if c not in df:
            df[c] = np.nan
    return df[report.COLS + EXTRA + ["next_entry"]], trades, cyc


def reconcile(df) -> list:
    """Reconciliation checks."""
    lhs = (
        df.credit_gross
        - df.slippage_cost
        - df.settlement_payout
        - df.total_charges
        + df.cash_interest
    )
    gaps = {
        "credit_gross - slippage - payout - charges + interest = total_pnl": (lhs - df.total_pnl)
        .abs()
        .max(),
        "capital_end = capital_start + total_pnl": (
            df.capital_start + df.total_pnl - df.capital_end
        )
        .abs()
        .max(),
        "charge items sum to total_charges": (
            df[["brokerage", "stt", "exchange_charges", "sebi_fees", "stamp_duty", "gst"]].sum(
                axis=1
            )
            - df.total_charges
        )
        .abs()
        .max(),
    }
    chain = 0.0
    for _, g in df.groupby(["rule", "period"]):
        chain = max(chain, np.abs(g.capital_start.values[1:] - g.capital_end.values[:-1]).max())
    gaps["capital_start = previous capital_end"] = chain
    return [f"- {k}: max gap Rs {v:.6f} -> {'PASS' if v < 1 else 'FAIL'}" for k, v in gaps.items()]


def dsr(sr, n_obs, skew, kurt, sr_var, trials) -> tuple:
    """Deflated Sharpe ratio (Bailey and Lopez de Prado).

    SR0 = sqrt(var of trial SRs) * ((1 - g) Phi^-1(1 - 1/N) + g Phi^-1(1 - 1/(N e))), with
    g Euler's constant; returns P(true SR > SR0) given n_obs, skew and kurtosis, and SR0.
    """
    g = 0.5772156649
    sr0 = np.sqrt(sr_var) * (
        (1 - g) * norm.ppf(1 - 1 / trials) + g * norm.ppf(1 - 1 / (trials * np.e))
    )
    z = (sr - sr0) * np.sqrt(n_obs - 1) / np.sqrt(1 - skew * sr + (kurt - 1) / 4 * sr**2)
    return norm.cdf(z), sr0


def summarise(df, cfg: dict, trial_sr) -> pd.DataFrame:
    """Summary statistics of each variant."""
    rows = []
    for n, g in df.groupby("rule", sort=False):
        ro = g.option_return_on_capital_pct / 100
        cy = pd.DataFrame(
            {"entry": pd.to_datetime(g.entry_date).values, "next_entry": g.next_entry.values}
        )
        m = bt.metrics(ro.reset_index(drop=True), cy, pd.Series(np.zeros(len(g))))
        tot = bt.metrics(
            (g.return_on_capital_pct / 100).reset_index(drop=True),
            cy,
            bt.cash_returns(cy, cfg["rf"]),
        )
        tr = g[g.skipped == "no"]
        w, lo = tr[tr.option_pnl_net > 0], tr[tr.option_pnl_net <= 0]
        aw = (w.option_pnl_net / w.capital_start).mean()
        al = -(lo.option_pnl_net / lo.capital_start).mean() if len(lo) else 0.0
        be = al / (al + aw)
        win = len(w) / len(tr)
        srm = ro.mean() / ro.std()
        p, sr0 = dsr(
            srm,
            len(ro),
            ro.skew(),
            ro.kurt() + 3,
            np.var(list(trial_sr.values()), ddof=1),
            len(trial_sr),
        )
        sk = g.skipped == "yes"
        rows.append(
            {
                "variant": n,
                "trial": "no" if n.startswith("ref_") else "yes",
                "option CAGR": m["CAGR"],
                "option Sharpe": m["Sharpe"],
                "worst month": m["Worst month"],
                "worst 3m": m["Worst 3m"],
                "CVaR95": m["CVaR95"],
                "CVaR99": m["CVaR99"],
                "max DD": m["MaxDD"],
                "skew": m["Skew"],
                "win rate": win,
                "avg win": aw,
                "avg loss": -al,
                "break-even win rate": be,
                "break-even margin": win - be,
                "avg credit % cap": (tr.credit_net / tr.capital_start).mean(),
                "avg max risk % cap": tr.max_risk_pct.mean() / 100,
                "costs % gross credit": tr.total_costs.sum() / tr.credit_gross.sum(),
                "skipped": int(sk.sum()),
                "fallback": int((g.fallback_used == "yes").sum()),
                "avg worst MTM": tr.worst_mtm_pct.mean() / 100,
                "avg margin % cap": tr.margin_pct_of_capital.mean() / 100,
                "max margin % cap": tr.margin_pct_of_capital.max() / 100,
                "short put IV": tr.short_put_iv.mean(),
                "long put IV": tr.long_put_iv.mean(),
                "total CAGR (cash 6.5%)": tot["CAGR"],
                "total max DD": tot["MaxDD"],
                "DSR": p,
                "DSR SR0 (monthly)": sr0,
                "SR monthly": srm,
                "months": len(g),
                "skew_g3": ro.skew(),
                "kurt_g4": ro.kurt() + 3,
            }
        )
    s = pd.DataFrame(rows)
    s["IV skew paid (long - short)"] = s["long put IV"] - s["short put IV"]
    return s


def trial_srs(df, cfg: dict, ctx, period) -> dict:
    """Monthly Sharpe of every logged trial."""
    srs = {}
    for n in cfg["phase2"]["variants"]:
        ro = df[df.rule == n].option_return_on_capital_pct
        srs[n] = ro.mean() / ro.std()
    cyc = ctx["cyc"][ctx["cyc"].period == period].reset_index(drop=True)
    for rule in bt.RULES:
        t = simulate(
            {"name": rule, "kind": "ref", "rule": rule, "skip": "phase1"},
            cyc,
            ctx,
            cfg,
            cfg["cash_rate"],
            mark=False,
        )
        ro = (t.net - t.interest) / t.capital_before
        srs[f"phase1_{rule}"] = ro.mean() / ro.std()
    return srs


PCT = [
    "option CAGR",
    "worst month",
    "worst 3m",
    "CVaR95",
    "CVaR99",
    "max DD",
    "win rate",
    "avg win",
    "avg loss",
    "break-even win rate",
    "break-even margin",
    "avg credit % cap",
    "avg max risk % cap",
    "costs % gross credit",
    "avg worst MTM",
    "avg margin % cap",
    "max margin % cap",
    "short put IV",
    "long put IV",
    "IV skew paid (long - short)",
    "total CAGR (cash 6.5%)",
    "total max DD",
    "DSR",
]


def fmt(s, cols) -> pd.DataFrame:
    """Format a summary table for Markdown."""
    d = s[cols].copy()
    for c in cols:
        if c in PCT:
            d[c] = d[c].map(lambda v: "" if pd.isna(v) else f"{v:.1%}")
        elif d[c].dtype.kind == "f":
            d[c] = d[c].map(lambda v: "" if pd.isna(v) else f"{v:.2f}")
    return d.to_markdown(index=False)


def choose(s, cfg: dict) -> tuple:
    """The pre-registered choice rule applied to design results."""
    c = cfg["phase2"]["choice"]
    t = s[s.trial == "yes"]
    ok = t[
        (t["worst month"] >= c["max_worst_month"])
        & (t["break-even margin"] >= c["min_breakeven_margin"])
    ]
    lines = [
        "# Phase 2 choice (design cycles only; written before validation)\n",
        "Rule (pre-registered): highest option-only Sharpe among the 6 variants whose worst month "
        "is no worse "
        f"than {c['max_worst_month']:.0%} of capital and whose break-even margin is at least "
        f"{c['min_breakeven_margin'] * 100:.0f} percentage points.\n",
        fmt(t, ["variant", "option Sharpe", "worst month", "break-even margin", "option CAGR"]),
        "",
    ]
    if ok.empty:
        lines.append(
            "**No variant qualifies.** The validation run is descriptive for all six variants.\n"
        )
        name = None
    else:
        b = ok.loc[ok["option Sharpe"].idxmax()]
        name = b.variant
        lines.append(
            f"**Chosen: {name}**: option-only Sharpe {b['option Sharpe']:.2f}, worst month "
            f"{b['worst month']:.1%}, break-even margin {b['break-even margin'] * 100:.1f} pts; "
            f"qualifying variants: {', '.join(ok.variant)}.\n"
        )
    return name, "\n".join(lines)


def chart_equity(df, path, title) -> None:
    """Equity curves of the variants."""
    fig, ax = plt.subplots(figsize=(11, 5.5))
    for n, g in df.groupby("rule", sort=False):
        x = np.r_[pd.Timestamp(g.entry_date.iloc[0]), pd.to_datetime(g.next_entry).values]
        y = np.r_[1.0, (1 + g.option_return_on_capital_pct / 100).cumprod().values]
        ax.plot(
            x,
            y,
            label=n,
            lw=1.0 if n.startswith("ref_") else 1.6,
            ls="--" if n.startswith("ref_") else "-",
        )
    ax.set_yscale("log")
    ax.set_title(title)
    ax.legend(fontsize=8, ncol=2)
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(path, dpi=130)
    plt.close(fig)


def chart_bars(g, path, title) -> None:
    """Monthly P&L bars of the chosen variant."""
    x = pd.to_datetime(g.expiry_date)
    y = g.option_return_on_capital_pct
    fig, ax = plt.subplots(figsize=(12, 4.5))
    ax.bar(x, y, width=25, color=np.where(y < 0, "tab:red", "tab:blue"))
    n = 0
    for d, p in zip(x, y, strict=False):
        if p < -4:
            ax.annotate(
                f"{d:%b %Y}\n{p:.1f}%",
                (d, p),
                textcoords="offset points",
                xytext=(0, -6 - 18 * (n % 2)),
                ha="center",
                va="top",
                fontsize=7,
            )
            n += 1
    ax.set_ylim(min(y.min() * 1.6, -1), y.max() * 1.3)
    ax.axhline(0, color="k", lw=0.8)
    ax.set_ylabel("option P&L net, % of capital")
    ax.set_title(title, fontsize=10)
    ax.grid(alpha=0.3, axis="y")
    fig.tight_layout()
    fig.savefig(path, dpi=130)
    plt.close(fig)


def skips_text(df) -> str:
    """Skipped months as text."""
    sk = df[(df.skipped == "yes")][["rule", "entry_date", "skip_reason", "index_move_pct"]]
    fb = df[df.fallback_used == "yes"].groupby("rule").size()
    lines = [
        "Fallback months (strike taken further out of the money): "
        + (", ".join(f"{k} {v}" for k, v in fb.items()) if len(fb) else "none")
        + ".\n"
    ]
    if len(sk):
        sk = sk.assign(index_move_pct=sk.index_move_pct.map(lambda v: f"{v:+.1f}%"))
        lines += ["Skipped months:\n", sk.to_markdown(index=False), ""]
    else:
        lines.append("No month skipped.\n")
    return lines


def reading(s, cfg: dict, period) -> list:
    """Plain-language reading of the Phase 2 results."""
    t = s.set_index("variant")
    var = list(cfg["phase2"]["variants"])
    ref = t.loc["ref_put_spread_fallback"]
    best = t.loc[var]["option Sharpe"].idxmax()
    best_delta = max(t.loc["d20_h2", "option Sharpe"], t.loc["d15_h2", "option Sharpe"])
    delta_verdict = "helped" if best_delta > ref["option Sharpe"] else "did not help"
    out = [
        f"- Best delta variant by option-only Sharpe: {best} ({t.loc[best, 'option Sharpe']:.2f}, "
        "CAGR "
        f"{t.loc[best, 'option CAGR']:.1%}) vs Phase 1 put spread with the fallback rule "
        f"({ref['option Sharpe']:.2f}, {ref['option CAGR']:.1%}) and with the Phase 1 skip rule "
        f"({t.loc['ref_put_spread_p1skip', 'option Sharpe']:.2f}, "
        f"{t.loc['ref_put_spread_p1skip', 'option CAGR']:.1%}).",
        "- Delta strikes: "
        + "; ".join(f"{v} Sharpe {t.loc[v, 'option Sharpe']:.2f}" for v in ("d20_h2", "d15_h2"))
        + " (fixed 5% hedge width, closest to Phase 1) vs "
        f"{ref['option Sharpe']:.2f} for the fixed 0.95/0.90 "
        "spread: delta strikes "
        f"{delta_verdict}.",
        "- Hedge: "
        + "; ".join(
            f"|delta| {d}: H1 {t.loc[f'd{d}_h1', 'option Sharpe']:.2f}, H2 "
            f"{t.loc[f'd{d}_h2', 'option Sharpe']:.2f}, "
            f"H3 {t.loc[f'd{d}_h3', 'option Sharpe']:.2f}"
            for d in ("20", "15")
        )
        + " (option-only Sharpe). Cheaper hedging "
        + (
            "helped"
            if max(t.loc[["d20_h1", "d20_h3", "d15_h1", "d15_h3"], "option Sharpe"])
            > max(t.loc[["d20_h2", "d15_h2"], "option Sharpe"])
            else "did not help"
        )
        + " relative to the 5%-wide hedge.",
        "- Skew: the long put's IV exceeds the short put's by "
        + "; ".join(
            f"{v} {t.loc[v, 'IV skew paid (long - short)'] * 100:+.1f} vol pts"
            for v in var
            if pd.notna(t.loc[v, "long put IV"])
        )
        + ". This is the skew premium the hedge pays back.",
        "- Cash: "
        + "; ".join(f"{v} total {t.loc[v, 'total CAGR (cash 6.5%)']:.1%}" for v in var)
        + f" a year with idle cash at {cfg['cash_rate']:.1%}, "
        f"against {cfg['cash_rate']:.1%} for cash alone. "
        f"Variants with option-only CAGR above zero (i.e. beating cash after costs): "
        f"{', '.join(v for v in var if t.loc[v, 'option CAGR'] > 0) or 'none'}.",
    ]
    return out


def write_csv(df) -> None:
    """Write the monthly Phase 2 file."""
    out = df.drop(columns="next_entry").copy()
    num = out.select_dtypes("number").columns
    out[num] = out[num].round(2)
    for c in ("short_put_iv", "long_put_iv", "short_put_delta", "long_put_delta"):
        out[c] = df[c].round(4)
    out.to_csv(OUT / "monthly_pnl_phase2.csv", index=False)


def design(cfg: dict) -> None:
    """Phase 2 on design data."""
    OUT.mkdir(parents=True, exist_ok=True)
    if (OUT / "validation_runs.log").exists():
        logger.info("Validation already run; design results are frozen.")
        return
    ctx = load(cfg)
    df, trades, cyc = run_period(cfg, ctx, "design")
    write_csv(df)
    rec = reconcile(df)
    srs = trial_srs(df, cfg, ctx, "design")
    s = summarise(df, cfg, srs)
    s.to_csv(OUT / "summary_design.csv", index=False)
    name, choice = choose(s, cfg)
    (OUT / "choice.md").write_text(choice)
    chart_equity(
        df,
        OUT / "equity_design.png",
        "Option-only P&L (no cash interest), design cycles, log scale",
    )
    if name:
        chart_bars(
            df[df.rule == name],
            OUT / "monthly_pnl_chosen.png",
            f"{name}: monthly option P&L net of costs, design cycles (labels: losses worse than 4% "
            "of capital)",
        )
    main_cols = [
        "variant",
        "option CAGR",
        "option Sharpe",
        "worst month",
        "worst 3m",
        "CVaR95",
        "CVaR99",
        "max DD",
        "skew",
        "win rate",
        "avg win",
        "avg loss",
        "break-even win rate",
        "break-even margin",
        "avg credit % cap",
        "avg max risk % cap",
        "costs % gross credit",
        "skipped",
        "fallback",
        "avg worst MTM",
        "total CAGR (cash 6.5%)",
        "total max DD",
    ]
    md = (
        [
            "# Phase 2 report\n",
            f"Design: {len(cyc)} cycles, entries {cyc.entry.min():%Y-%m-%d} to "
            f"{cyc.entry.max():%Y-%m-%d}. Option-only "
            "returns (option_pnl_net / capital at cycle start, no cash interest) are the headline; "
            "their Sharpe has no "
            "risk-free deduction. Variants d20/d15 = short put |delta|; H1 = long put |delta| "
            "0.05, H2 = long put 5% of "
            "S0 below, H3 = naked put sized for a 25% fall. ref_* = Phase 1 rules (not trials), "
            "with the Phase 1 skip "
            "rule (p1skip) or the fallback rule.\n",
            "## Design results\n",
            fmt(s, main_cols),
            "",
            "Avg max risk: spreads = planned max loss; naked (H3, strangle) = loss if the index "
            "settles 25% below S0. "
            "Avg worst MTM = average over traded cycles of the worst daily mark-to-market P&L (% "
            "of capital).\n",
            "## Skips and fallbacks (design)\n",
        ]
        + skips_text(df)
        + [
            "## Skew diagnostic (design, average IV at entry)\n",
            fmt(
                s[s.variant.isin(list(cfg["phase2"]["variants"]) + ["ref_put_spread_fallback"])],
                ["variant", "short put IV", "long put IV", "IV skew paid (long - short)"],
            ),
            "",
            "## Margin (design)\n",
            fmt(s, ["variant", "avg margin % cap", "max margin % cap"]),
            "",
            "## Deflated Sharpe ratio (design)\n",
            "Inputs: monthly Sharpe of each series; number of observations; skewness and kurtosis "
            "of its monthly option "
            f"returns; variance of the monthly Sharpe across the {len(srs)} cumulative trials on "
            "design cycles "
            f"({', '.join(f'{k} {v:.3f}' for k, v in srs.items())}); trials N = {len(srs)}. SR0 is "
            "the expected maximum "
            "Sharpe of N trials with no skill (Bailey and Lopez de Prado).\n",
            fmt(
                s,
                [
                    "variant",
                    "SR monthly",
                    "DSR SR0 (monthly)",
                    "skew_g3",
                    "kurt_g4",
                    "months",
                    "DSR",
                ],
            ),
            "",
            "## Reading (design)\n",
        ]
        + reading(s, cfg, "design")
        + ["", choice.replace("# Phase 2 choice", "## Choice"), "## Checks\n"]
        + rec
    )
    (OUT / "phase2_report.md").write_text("\n".join(md) + "\n")
    logger.info("\n".join(md))


def validate(cfg: dict) -> None:
    """Phase 2 validation, run once."""
    log = OUT / "validation_runs.log"
    if log.exists() and log.read_text().strip():
        logger.info("Validation already run once; not running again. Log:\n" + log.read_text())
        return
    assert (OUT / "choice.md").exists(), "choice.md must be written and committed before validation"
    name = None
    for line in (OUT / "choice.md").read_text().splitlines():
        if line.startswith("**Chosen: "):
            name = line.split("**Chosen: ")[1].split("**")[0]
    ctx = load(cfg)
    dv = pd.read_csv(OUT / "monthly_pnl_phase2.csv")
    dv = dv[dv.period == "design"]
    df, trades, cyc = run_period(cfg, ctx, "validation")
    rec = reconcile(df)
    srs = trial_srs(df, cfg, ctx, "validation")
    s = summarise(df, cfg, srs)
    s.to_csv(OUT / "summary_validation.csv", index=False)
    both = pd.concat([dv, df.drop(columns="next_entry")], ignore_index=True)
    num = both.select_dtypes("number").columns
    both[num] = both[num].round(4)
    both.to_csv(OUT / "monthly_pnl_phase2.csv", index=False)
    if name:
        chart_bars(
            df[df.rule == name],
            OUT / "monthly_pnl_chosen_validation.png",
            f"{name}: monthly option P&L net of costs, validation cycles",
        )
    cols = [
        "variant",
        "option CAGR",
        "option Sharpe",
        "worst month",
        "CVaR99",
        "max DD",
        "win rate",
        "break-even margin",
        "avg credit % cap",
        "avg max risk % cap",
        "skipped",
        "fallback",
        "avg worst MTM",
        "total CAGR (cash 6.5%)",
        "DSR",
    ]
    label = (
        "**Validation; aggregate results for this period were seen in Phase 1, so not a clean "
        "test.**"
        + (
            ""
            if name
            else " No variant qualified on design, so this run is descriptive for all six."
        )
    )
    md = (
        [
            "\n## Validation (run 1)\n",
            label + f" {len(cyc)} cycles, entries {cyc.entry.min():%Y-%m-%d} to "
            f"{cyc.entry.max():%Y-%m-%d}.\n",
            fmt(s, cols),
            "",
            "Skips and fallbacks (validation):\n",
        ]
        + skips_text(df)
        + ["Reading (validation):\n"]
        + reading(s, cfg, "validation")
    )
    if name:
        t = s.set_index("variant")
        dsg = pd.read_csv(OUT / "summary_design.csv").set_index("variant")
        md.append(
            f"- Chosen variant {name}: option-only Sharpe {dsg.loc[name, 'option Sharpe']:.2f} on "
            "design, "
            f"{t.loc[name, 'option Sharpe']:.2f} on validation; option CAGR "
            f"{dsg.loc[name, 'option CAGR']:.1%} -> "
            f"{t.loc[name, 'option CAGR']:.1%}; worst month {t.loc[name, 'worst month']:.1%}; DSR "
            f"{t.loc[name, 'DSR']:.2f}."
        )
    md += ["", "Validation checks:\n"] + rec
    with open(OUT / "phase2_report.md", "a") as f:
        f.write("\n".join(md) + "\n")
    with open(log, "a") as f:
        f.write(
            f"run 1 at {datetime.now():%Y-%m-%d %H:%M:%S}, {len(cyc)} cycles "
            f"{cyc.entry.min():%Y-%m-%d} to "
            f"{cyc.expiry.max():%Y-%m-%d}, chosen {name}\n"
            + fmt(s, ["variant", "option CAGR", "option Sharpe", "worst month", "CVaR99", "DSR"])
            + "\n"
        )
    logger.info("\n".join(md))


def ncdf(x) -> float:
    """Standard normal CDF."""
    return 0.5 * (1 + erf(x / sqrt(2)))


def hand_iv(price, s, k, t, r, q) -> tuple:
    """Implied volatility by bisection, by hand, for the checks."""
    lo, hi = 1e-4, 5.0
    for _ in range(200):
        v = (lo + hi) / 2
        a = (log(s / k) + (r - q + v * v / 2) * t) / (v * sqrt(t))
        p = k * exp(-r * t) * ncdf(-(a - v * sqrt(t))) - s * exp(-q * t) * ncdf(-a)
        lo, hi = (v, hi) if p < price else (lo, v)
    a = (log(s / k) + (r - q + v * v / 2) * t) / (v * sqrt(t))
    return v, -exp(-q * t) * ncdf(-a)


def check(cfg: dict) -> None:
    """Phase 2 checks."""
    ctx = load(cfg)
    p2 = cfg["phase2"]
    out = ["# Phase 2 checks\n"]
    cyc = ctx["cyc"]
    vend = pd.Timestamp(p2["validation_end"])
    hold = data.cycles(*data.load())
    hold = hold[hold.expiry > vend]
    assert not cyc.entry.isin(hold.entry).any() and ctx["opt"].date.max() <= vend
    des = cyc[cyc.period == "design"]
    val = cyc[cyc.period == "validation"]
    assert (
        des.entry.max() <= pd.Timestamp(p2["design_end"]) < val.entry.min()
        and des.expiry.max() < val.expiry.min()
    )
    runs = (
        (OUT / "validation_runs.log").read_text().count("run ")
        if (OUT / "validation_runs.log").exists()
        else 0
    )
    assert runs <= 1
    out.append(
        f"- split: design {len(des)} cycles (entry to {des.entry.max():%Y-%m-%d}), validation "
        f"{len(val)} cycles "
        f"(from {val.entry.min():%Y-%m-%d}); no holdout cycle loaded and no option data after "
        f"{vend:%Y-%m-%d}; validation runs logged: {runs}."
    )

    rng = np.random.default_rng(1)
    c = des.iloc[rng.integers(len(des))]
    s0 = float(ctx["ix"].close[c.entry])
    t = (c.expiry - c.entry).days / 365
    ch = bt.chain(ctx["opt"], c.entry, c.contract)
    assert (ch.date == c.entry).all()
    g = greeks(traded(ch, "PE"), s0, t, cfg)
    for _, r in g.sample(3, random_state=1).iterrows():
        v, d = hand_iv(r.close, s0, r.strike, t, cfg["rf"], p2["div_yield"])
        assert abs(v - r.iv) < 1e-6 and abs(d - r.delta) < 1e-6
        out.append(
            f"- delta {c.entry:%Y-%m-%d} K {r.strike:.0f}: price {r.close}, IV code {r.iv:.6f} / "
            f"hand {v:.6f}, "
            f"delta code {r.delta:.6f} / hand {d:.6f}: OK"
        )

    for n, v in variants(cfg).items():
        tr = simulate(v, des.reset_index(drop=True), ctx, cfg, cfg["cash_rate"], mark=False)
        done = tr[tr.skipped == ""]
        for i in rng.choice(done.index, 3, replace=False):
            row = done.loc[i]
            hand = 0.0
            for j in range(1, 5):
                lg = row.get(f"leg{j}")
                if isinstance(lg, str):
                    side, o, k = lg.split()
                    val_ = (
                        max(0.0, float(k) - row.settle)
                        if o == "P"
                        else max(0.0, row.settle - float(k))
                    )
                    hand += val_ if side == "B" else -val_
            assert abs(hand - row.payoff_unit) < 1e-9
        loss = -(done.units * (done.credit + done.payoff_unit)) / done.capital_before
        if v.get("hedge") in ("H1", "H2"):
            assert (loss <= cfg["max_loss_pct"] + 1e-9).all()
        if v.get("hedge") == "H3":
            k = done.leg1.str.split().str[2].astype(float)
            at = (
                done.units
                * (k - (1 - p2["stress_drop"]) * done.S0 - done.credit)
                / done.capital_before
            )
            assert (at - cfg["max_loss_pct"]).abs().max() < 1e-9 and (done.margin_pct <= 1).all()
        out.append(
            f"- {n}: payoff by hand OK for 3 cycles; worst trading loss {loss.max():.2%} of capital"
            + (
                "; loss at 0.75 x S0 = 10.00% exactly; max margin " + f"{done.margin_pct.max():.1%}"
                if v.get("hedge") == "H3"
                else ""
            )
        )
    out.append(
        "- no look-ahead: chains, IV, delta and sizing use only the entry-day bhavcopy and the "
        "entry-day index close "
        "(chain() asserts date == entry); settlement is used only for payoff and marking only for "
        "diagnostics."
    )

    dev = pd.concat([des, val]).reset_index(drop=True)
    for rule in bt.RULES:
        t1 = pd.read_csv(f"results/trades_{rule}.csv")
        t2 = simulate(
            {"name": rule, "kind": "ref", "rule": rule, "skip": "phase1"},
            dev,
            ctx,
            cfg,
            cfg["cash_rate"],
            mark=False,
        )
        gap = np.abs(t1.capital_after.values - t2.capital_after.values).max()
        assert gap < 0.01, (rule, gap)
        out.append(
            f"- Phase 1 {rule} reproduced with the Phase 2 engine and Phase 1 skip rule over 201 "
            f"cycles: max capital gap Rs {gap:.2e}"
        )
    (OUT / "checks.md").write_text("\n".join(out) + "\n")
    logger.info("\n".join(out))
