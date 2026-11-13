from __future__ import annotations

import hashlib
import logging
from datetime import datetime
from pathlib import Path

import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from optsell import backtest as bt
from optsell import data, report
from optsell import phase2 as p2
from optsell.config import CONFIG_PATH

matplotlib.use("Agg")
logger = logging.getLogger(__name__)

OUT = Path("results/phase3")
BASE = {"name": "base", "kind": "ref", "rule": "put_spread", "skip": "fallback"}
ITEMS = ["brokerage", "stt", "exchange_charges", "sebi_fees", "stamp_duty", "gst"]
EXTRA = [
    "traded",
    "filter_iv",
    "filter_rv",
    "filter_gap",
    "filter_threshold",
    "stop_triggered",
    "trigger_date",
    "exit_date",
    "exit_cost",
    "pnl_if_held",
    "stop_effect",
    "exit_flag",
    "fallback_used",
]


def variants(cfg: dict) -> dict:
    """Base, stop (e1), filter (f1) and both (e1f1)."""
    v = {"base": {"stop": False, "filter": False}}
    v.update({n: {"stop": s, "filter": f} for n, (s, f) in cfg["phase3"]["variants"].items()})
    return v


def trailing_rv(ix, d, n) -> float:
    """Realised vol over the n trading days before d."""
    s = ix.close.dropna()
    s = s[s.index <= d].iloc[-(n + 1) :]
    return np.log(s).diff().dropna().std() * np.sqrt(252)


def gaps(ctx, cyc, cfg: dict) -> pd.DataFrame:
    """ATM IV minus trailing RV at each entry, and its expanding median."""
    v = bt.vrp_table(ctx["opt"], ctx["ix"], cyc, cfg)
    g = pd.DataFrame({"entry": cyc.entry.values, "iv": v.iv.values})
    g["rv"] = [trailing_rv(ctx["ix"], d, cfg["phase3"]["rv_days"]) for d in g.entry]
    g["gap"] = g.iv - g.rv
    thr = []
    for i in range(len(g)):
        prev = g.gap.iloc[:i].dropna()
        thr.append(prev.median() if len(prev) >= cfg["phase3"]["min_history"] else np.nan)
    g["threshold"] = thr
    return g.set_index("entry")


def fees(fills, itm, cc) -> dict:
    """Charge items of a cycle's fills."""
    it = dict.fromkeys(ITEMS, 0.0)
    for d, px, u, sell in fills:
        v = px * u
        it["brokerage"] += cc["brokerage"]
        if sell:
            it["stt"] += bt.rate_on(cc["stt_sell"], d) * v
        else:
            it["stamp_duty"] += cc["stamp"] * v
        it["exchange_charges"] += bt.rate_on(cc["exch"], d) * v
        it["sebi_fees"] += cc["sebi"] * v
    it["stt"] += cc["stt_itm"] * itm
    it["gst"] = cc["gst"] * (it["brokerage"] + it["exchange_charges"] + it["sebi_fees"])
    return it


def leg_series(bk, contract, leg) -> pd.Series:
    """Daily closes of one leg up to its contract's expiry."""
    try:
        s = bk.loc[(contract, "PE" if leg["opt"] == "P" else "CE", leg["k"])]
    except KeyError:
        s = pd.Series(dtype=float)
    return s[s > 0]


def stop(legs, tr, c, days, ctx, cfg: dict) -> dict | None:
    """Exit at the next close once the mark-to-market loss reaches 2x the net credit."""
    u, mult = tr["units"], cfg["phase3"]["stop_mult"]
    raw = [leg_series(ctx["bk"], c.contract, leg) for leg in legs]
    marks = []
    for leg, s in zip(legs, raw, strict=False):
        m = s.reindex(days)
        m.iloc[0] = leg["close"]
        marks.append(m.ffill().values)
    pnl = sum(leg["side"] * (m - leg["px"]) * u for leg, m in zip(legs, marks, strict=False))
    limit = mult * u * tr["credit"]
    for d in range(1, len(days) - 2):
        if -pnl[d] >= limit:
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
            dt, cl = days[-1], bt.intrinsic(leg["opt"], leg["k"], c.settle)
            flag = True
        slip = max(cfg["costs"]["slip_min"], cfg["costs"]["slip_pct"] * cl)
        px = cl + slip if leg["side"] < 0 else max(0.0, cl - slip)
        out.append(
            {"date": dt, "close": cl, "px": px, "slip": px - cl if leg["side"] < 0 else cl - px}
        )
    return {
        "trigger": days[d],
        "trigger_pnl": pnl[d],
        "exit": max(o["date"] for o in out),
        "legs": out,
        "flag": flag,
    }


def simulate(name, v, cyc, ctx, cfg: dict, gp, rate) -> pd.DataFrame:
    """Run a Phase 3 variant over all cycles."""
    cc = cfg["costs"]
    capital = cfg["capital"]
    rows = []
    for _, c in cyc.iterrows():
        s0 = float(ctx["ix"].close[c.entry])
        t = (c.expiry - c.entry).days / 365
        days_total = (c.next_entry - c.entry).days
        g = gp.loc[c.entry]
        row = {
            "entry": c.entry,
            "expiry": c.expiry,
            "next_entry": c.next_entry,
            "S0": s0,
            "settle": c.settle,
            "capital_before": capital,
            "filter_iv": g.iv,
            "filter_rv": g.rv,
            "filter_gap": g.gap,
            "filter_threshold": g.threshold,
            "stop_triggered": "no",
            "fallback_used": "no",
            "traded": "no",
        }
        why = ""
        if v["filter"] and pd.notna(g.gap) and pd.notna(g.threshold) and g.gap <= g.threshold:
            why = "filtered: IV - RV gap not above the expanding median"
            legs = None
        else:
            legs, fb, why = p2.select(BASE, bt.chain(ctx["opt"], c.entry, c.contract), s0, t, cfg)
        tr = (
            p2.trade(BASE, legs, s0, c.settle, capital, days_total, c.entry, cfg, rate)
            if legs
            else None
        )
        if legs and tr is None:
            why = "sizing denominator not positive"
        if tr is None:
            interest = rate * capital * days_total / 365
            row.update({"skipped": why, "net": interest, "interest": interest})
        else:
            u = tr["units"]
            for j, leg in enumerate(legs):
                row[f"leg{j + 1}"] = (
                    f"{'S' if leg['side'] < 0 else 'B'} {leg['opt']} {leg['k']:.0f}"
                )
                row[f"leg{j + 1}_close"] = leg["close"]
                row[f"leg{j + 1}_px"] = leg["px"]
            row.update(tr)
            row.update(
                {
                    "skipped": "",
                    "traded": "yes",
                    "fallback_used": "yes" if fb else "no",
                    "pnl_if_held": u * (tr["credit"] + tr["payoff_unit"]) - tr["charges"],
                }
            )
            row.update(report.charge_items(legs, u, c.settle, c.entry, cc))
            d = ctx["days"][(ctx["days"] >= c.entry) & (ctx["days"] <= c.expiry)]
            st = stop(legs, tr, c, d, ctx, cfg) if v["stop"] else None
            if st:
                payoff = sum(
                    leg["side"] * x["close"] for leg, x in zip(legs, st["legs"], strict=False)
                )
                exit_slip = sum(x["slip"] for x in st["legs"]) * u
                fills = [(c.entry, leg["px"], u, leg["side"] < 0) for leg in legs]
                fills += [
                    (x["date"], x["px"], u, leg["side"] > 0)
                    for leg, x in zip(legs, st["legs"], strict=False)
                ]
                it = fees(fills, 0.0, cc)
                entry_it = fees(fills[: len(legs)], 0.0, cc)
                charges = sum(it.values())
                held_days = (st["exit"] - c.entry).days
                interest = rate * (capital * days_total - tr["margin"] * held_days) / 365
                net = u * (tr["credit"] + payoff) - exit_slip - charges + interest
                opt_net = net - interest
                row.update(it)
                row.update(
                    {
                        "payoff_unit": payoff,
                        "slippage": tr["slippage"] + exit_slip,
                        "charges": charges,
                        "costs": tr["slippage"] + exit_slip + charges,
                        "interest": interest,
                        "net": net,
                        "gross": u * (tr["credit"] + payoff) + tr["slippage"],
                        "stop_triggered": "yes",
                        "trigger_date": st["trigger"].date(),
                        "exit_date": st["exit"].date(),
                        "trigger_pnl": st["trigger_pnl"],
                        "exit_flag": "yes" if st["flag"] else "no",
                        "exit_cost": exit_slip + charges - sum(entry_it.values()),
                        "stop_effect": "helped" if opt_net > row["pnl_if_held"] else "hurt",
                    }
                )
            row["settle_value"] = u * row["payoff_unit"]
        capital += row["net"]
        row["capital_after"] = capital
        row["ret"] = row["net"] / row["capital_before"]
        rows.append(row)
    return pd.DataFrame(rows)


def run_period(cfg: dict, ctx, period, gp) -> tuple:
    """Run every variant on one period."""
    cyc = ctx["cyc"][ctx["cyc"].period == period].reset_index(drop=True)
    rc = p2.context(ctx, cyc, cfg)
    out, trades = [], {}
    for n, v in variants(cfg).items():
        t = simulate(n, v, cyc, ctx, cfg, gp, cfg["cash_rate"])
        trades[n] = t
        r = pd.DataFrame(report.rows(n, period, t, rc, cfg))
        for c in ITEMS:
            r[c] = t[c].fillna(0.0).values if c in t else 0.0
        stopped = (t.stop_triggered == "yes").values
        r.loc[stopped, "outcome"] = "stopped"
        r.loc[stopped, "win"] = np.where(r.loc[stopped, "option_pnl_net"] > 0, "yes", "no")
        r["skip_reason"] = t.skipped.fillna("").values
        for c in EXTRA + ["trigger_pnl"]:
            r[c] = t[c].values if c in t else np.nan
        r["tri_ret"] = rc["cyc"].tri_ret.values
        out.append(r)
    df = pd.concat(out, ignore_index=True)
    for c in report.COLS:
        if c not in df:
            df[c] = np.nan
    return df[report.COLS + EXTRA + ["trigger_pnl", "tri_ret", "next_entry"]], cyc


def nw_t(x, lags) -> tuple:
    """Newey-West t-statistic of a mean (or mean difference)."""
    x = np.asarray(x, float)
    m = x.mean()
    e = x - m
    s = (e * e).mean() + 2 * sum(
        (1 - leg / (lags + 1)) * (e[leg:] * e[:-leg]).mean() for leg in range(1, lags + 1)
    )
    return m, m / np.sqrt(s / len(x))


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
    s2 = pd.read_csv(f"results/phase2/summary_{period}.csv").set_index("variant")
    for n in cfg["phase2"]["variants"]:
        srs[f"phase2_{n}"] = s2.loc[n, "SR monthly"]
    for n in cfg["phase3"]["variants"]:
        ro = df[df.rule == n].option_return_on_capital_pct
        srs[f"phase3_{n}"] = ro.mean() / ro.std()
    return srs


def summarise(df, cfg: dict, srs) -> tuple:
    """Summary statistics and deflated Sharpe of each variant."""
    rows = []
    base = df[df.rule == "base"].option_return_on_capital_pct.values / 100
    g0 = df[df.rule == "base"]
    cy = pd.DataFrame(
        {"entry": pd.to_datetime(g0.entry_date).values, "next_entry": g0.next_entry.values}
    )
    tri = g0.tri_ret.values
    cash = bt.cash_returns(cy, cfg["cash_rate"]).values
    for n, g in df.groupby("rule", sort=False):
        ro = g.option_return_on_capital_pct.values / 100
        m = bt.metrics(pd.Series(ro), cy, pd.Series(np.zeros(len(g))))
        tot = bt.metrics(
            pd.Series(g.return_on_capital_pct.values / 100), cy, bt.cash_returns(cy, cfg["rf"])
        )
        tr = g[g.traded == "yes"]
        w, lo = tr[tr.option_pnl_net > 0], tr[tr.option_pnl_net <= 0]
        aw = (w.option_pnl_net / w.capital_start).mean()
        al = -(lo.option_pnl_net / lo.capital_start).mean() if len(lo) else 0.0
        be = al / (al + aw)
        win = len(w) / len(tr)
        srm = ro.mean() / ro.std()
        dsr, sr0 = p2.dsr(
            srm,
            len(ro),
            pd.Series(ro).skew(),
            pd.Series(ro).kurt() + 3,
            np.var(list(srs.values()), ddof=1),
            len(srs),
        )
        diff, t = nw_t(ro - base, cfg["phase3"]["nw_lags"]) if n != "base" else (np.nan, np.nan)
        rows.append(
            {
                "variant": n,
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
                "months traded": len(tr),
                "months filtered": int(g.skip_reason.str.startswith("filtered").sum()),
                "months skipped (no strike)": int(
                    ((g.traded == "no") & ~g.skip_reason.str.startswith("filtered")).sum()
                ),
                "stops": int((g.stop_triggered == "yes").sum()),
                "costs % gross credit": tr.total_costs.sum() / tr.credit_gross.sum(),
                "total CAGR (cash 6.5%)": tot["CAGR"],
                "total max DD": tot["MaxDD"],
                "corr with TRI": np.corrcoef(ro, tri)[0, 1],
                "mean diff vs base": diff,
                "NW t vs base": t,
                "months": len(g),
                "SR monthly": srm,
                "DSR SR0 (monthly)": sr0,
                "DSR": dsr,
            }
        )
    s = pd.DataFrame(rows)
    ex = tri - cash
    mk = {
        "TRI CAGR": (1 + pd.Series(tri)).prod()
        ** (365.25 / (cy.next_entry.iloc[-1] - cy.entry.iloc[0]).days)
        - 1,
        "TRI excess over cash, mean monthly": ex.mean(),
        "TRI excess Sharpe": ex.mean() / ex.std() * np.sqrt(12),
        "TRI Sharpe (no rf)": tri.mean() / tri.std() * np.sqrt(12),
    }
    return s, mk


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
    "costs % gross credit",
    "total CAGR (cash 6.5%)",
    "total max DD",
    "mean diff vs base",
    "DSR",
]
COLS = [
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
    "months traded",
    "months filtered",
    "months skipped (no strike)",
    "stops",
    "costs % gross credit",
    "total CAGR (cash 6.5%)",
    "total max DD",
    "corr with TRI",
    "mean diff vs base",
    "NW t vs base",
    "DSR",
]


def fmt(s, cols) -> pd.DataFrame:
    """Format a summary table for Markdown."""
    d = s[cols].copy()
    for c in cols:
        if c in PCT:
            d[c] = d[c].map(
                lambda v, c=c: (
                    "" if pd.isna(v) else f"{v:.2%}" if c == "mean diff vs base" else f"{v:.1%}"
                )
            )
        elif d[c].dtype.kind == "f":
            d[c] = d[c].map(lambda v: "" if pd.isna(v) else f"{v:.2f}")
    return d.to_markdown(index=False)


def stops_table(df) -> pd.DataFrame:
    """Every stop: trigger day, exit, effect vs holding."""
    s = df[df.stop_triggered == "yes"].copy()
    return pd.DataFrame(
        {
            "variant": s.rule,
            "period": s.period,
            "entry": s.entry_date,
            "trigger": s.trigger_date,
            "exit": s.exit_date,
            "exit_flag": s.exit_flag,
            "loss_at_trigger_pct": 100 * s.trigger_pnl / s.capital_start,
            "loss_at_exit_pct": s.option_return_on_capital_pct,
            "pnl_if_held_pct": 100 * s.pnl_if_held / s.capital_start,
            "index_move_pct": s.index_move_pct,
            "stop_effect": s.stop_effect,
        }
    )


def choose(s) -> tuple:
    """The pre-registered choice rule."""
    t = s.set_index("variant")
    b = t.loc["base"]
    ok = [
        n
        for n in t.index
        if n != "base"
        and t.loc[n, "option Sharpe"] > b["option Sharpe"]
        and t.loc[n, "worst month"] >= b["worst month"]
        and t.loc[n, "CVaR99"] >= b["CVaR99"]
    ]
    lines = [
        "# Phase 3 choice (design cycles only; written before validation)\n",
        "Rule (pre-registered): keep a variant only if its design option-only Sharpe beats the "
        "base and its worst "
        "month and CVaR 99% are no worse than the base's; if several qualify take the highest "
        "Sharpe; if none, the "
        "frozen rule is the base put spread.\n",
        fmt(s, ["variant", "option Sharpe", "worst month", "CVaR99", "option CAGR"]),
        "",
    ]
    for n in t.index:
        if n == "base":
            continue
        why = []
        why.append(
            f"Sharpe {t.loc[n, 'option Sharpe']:.3f} "
            f"{'>' if t.loc[n, 'option Sharpe'] > b['option Sharpe'] else '<='} base "
            f"{b['option Sharpe']:.3f}"
        )
        why.append(
            f"worst month {t.loc[n, 'worst month']:.2%} "
            f"{'ok' if t.loc[n, 'worst month'] >= b['worst month'] else 'worse than'} base "
            f"{b['worst month']:.2%}"
        )
        why.append(
            f"CVaR99 {t.loc[n, 'CVaR99']:.2%} "
            f"{'ok' if t.loc[n, 'CVaR99'] >= b['CVaR99'] else 'worse than'} base {b['CVaR99']:.2%}"
        )
        lines.append(f"- {n}: {'; '.join(why)} -> {'qualifies' if n in ok else 'does not qualify'}")
    name = max(ok, key=lambda n: t.loc[n, "option Sharpe"]) if ok else "base"
    lines.append(
        f"\n**Chosen: {name}**"
        + ("" if ok else " (no variant qualifies; the frozen rule is the base put spread)")
        + "\n"
    )
    return name, "\n".join(lines)


def reading(s, mk, df, period) -> list:
    """Plain-language reading of the Phase 3 results."""
    t = s.set_index("variant")
    b = t.loc["base"]
    st = df[df.stop_triggered == "yes"]
    out = []
    for n in ("e1", "f1", "e1f1"):
        out.append(
            f"- {n}: option-only Sharpe {t.loc[n, 'option Sharpe']:.2f} vs base "
            f"{b['option Sharpe']:.2f}; CAGR "
            f"{t.loc[n, 'option CAGR']:.1%} vs {b['option CAGR']:.1%}; worst month "
            f"{t.loc[n, 'worst month']:.1%} vs "
            f"{b['worst month']:.1%}; mean monthly difference {t.loc[n, 'mean diff vs base']:+.2%} "
            "(Newey-West t "
            f"{t.loc[n, 'NW t vs base']:.2f}, {int(t.loc[n, 'months'])} months)."
        )
    for n in ("e1", "e1f1"):
        x = st[st.rule == n]
        if len(x):
            h = x[x.stop_effect == "helped"]
            out.append(
                f"- Stops in {n}: {len(x)}, helped {len(h)}, hurt {len(x) - len(h)}. Helped in: "
                + (
                    ", ".join(
                        f"{d} (index {m:+.1f}%)"
                        for d, m in zip(h.entry_date, h.index_move_pct, strict=False)
                    )
                    or "none"
                )
                + (
                    ". Net effect of all stops vs holding: "
                    f"{(x.option_pnl_net - x.pnl_if_held).sum() / 1e5:+.2f} lakh."
                )
            )
        else:
            out.append(f"- Stops in {n}: none triggered.")
    f = df[(df.rule == "f1")]
    base = df[df.rule == "base"]
    base_when_filtered = base[
        base.entry_date.isin(f[f.skip_reason.str.startswith("filtered")].entry_date)
    ].option_return_on_capital_pct.mean()
    base_when_traded = base[
        base.entry_date.isin(f[f.traded == "yes"].entry_date)
    ].option_return_on_capital_pct.mean()
    out.append(
        f"- Filter: f1 sat out {int(t.loc['f1', 'months filtered'])} of "
        f"{int(t.loc['f1', 'months'])} months; the base "
        "earned "
        f"{base_when_filtered:+.2f}% of capital on average in those months "
        "vs "
        f"{base_when_traded:+.2f}% in the months f1 traded."
    )
    out.append(
        f"- Market: NIFTY 50 TRI CAGR {mk['TRI CAGR']:.1%}; TRI excess over cash Sharpe "
        f"{mk['TRI excess Sharpe']:.2f}. "
        "Option-only Sharpe (an excess-over-cash return, since the margin earns interest "
        "separately): base "
        f"{b['option Sharpe']:.2f}, "
        + ", ".join(f"{n} {t.loc[n, 'option Sharpe']:.2f}" for n in ("e1", "f1", "e1f1"))
        + ". Correlation of monthly option return with the TRI: "
        + ", ".join(f"{n} {t.loc[n, 'corr with TRI']:.2f}" for n in t.index)
        + "."
    )
    best = t.drop("base")["option Sharpe"].idxmax()
    if t.loc[best, "option Sharpe"] <= b["option Sharpe"]:
        best_text = "Nothing beats the base on option-only Sharpe."
    else:
        best_text = f"Best Sharpe: {best}."
    out.append(
        "- "
        f"{best_text}"
        f" Variants with positive option-only CAGR (beating cash after costs): "
        f"{', '.join(n for n in t.index if t.loc[n, 'option CAGR'] > 0) or 'none'}."
    )
    return out


def write_csv(df, path) -> None:
    """Write the monthly Phase 3 file."""
    out = df.drop(columns=["next_entry", "tri_ret", "trigger_pnl"]).copy()
    num = out.select_dtypes("number").columns
    out[num] = out[num].round(4)
    out.to_csv(path, index=False)


def chart_equity(df, path, title) -> None:
    """Equity curves of the variants."""
    fig, ax = plt.subplots(figsize=(11, 5.5))
    g0 = None
    for n, g in df.groupby("rule", sort=False):
        x = np.r_[pd.Timestamp(g.entry_date.iloc[0]), pd.to_datetime(g.next_entry).values]
        ax.plot(
            x,
            np.r_[1.0, (1 + g.option_return_on_capital_pct / 100).cumprod().values],
            label=f"{n} (option only)",
        )
        g0 = g
    x = np.r_[pd.Timestamp(g0.entry_date.iloc[0]), pd.to_datetime(g0.next_entry).values]
    ax.plot(x, np.r_[1.0, (1 + g0.tri_ret).cumprod().values], color="grey", label="NIFTY 50 TRI")
    ax.set_yscale("log")
    ax.set_title(title)
    ax.legend(fontsize=8)
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(path, dpi=130)
    plt.close(fig)


def chart_stops(st, path) -> None:
    """Stop effect chart."""
    fig, ax = plt.subplots(figsize=(6.5, 6))
    for n, g in st.groupby("variant"):
        ax.scatter(g.pnl_if_held_pct, g.loss_at_exit_pct, label=n, s=30)
        for _, r in g.iterrows():
            ax.annotate(
                str(r.entry)[:7],
                (r.pnl_if_held_pct, r.loss_at_exit_pct),
                fontsize=6,
                xytext=(3, 3),
                textcoords="offset points",
            )
    lim = [
        min(st.pnl_if_held_pct.min(), st.loss_at_exit_pct.min()) - 1,
        max(st.pnl_if_held_pct.max(), st.loss_at_exit_pct.max()) + 1,
    ]
    ax.plot(lim, lim, "k--", lw=0.8)
    ax.set_xlabel("option P&L if held to expiry, % of capital")
    ax.set_ylabel("option P&L with the stop, % of capital")
    ax.set_title("Each stop: above the line = stop helped", fontsize=10)
    ax.legend()
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(path, dpi=130)
    plt.close(fig)


def reconcile(df) -> list:
    """Reconciliation checks."""
    return p2.reconcile(df)


def ctx_for(cfg: dict, period) -> tuple:
    """Inputs and filter gaps for a period."""
    ctx = p2.load(cfg)
    cyc = ctx["cyc"] if period == "validation" else ctx["cyc"][ctx["cyc"].period == "design"]
    gp = gaps(ctx, cyc.reset_index(drop=True), cfg)
    return ctx, gp


def design(cfg: dict) -> None:
    """Phase 3 on design data."""
    OUT.mkdir(parents=True, exist_ok=True)
    if (OUT / "validation_runs.log").exists():
        logger.info("Validation already run; design results are frozen.")
        return
    ctx, gp = ctx_for(cfg, "design")
    df, cyc = run_period(cfg, ctx, "design", gp)
    rec = reconcile(df)
    write_csv(df, OUT / "monthly_pnl_phase3.csv")
    srs = trial_srs(cfg, ctx, "design", df)
    s, mk = summarise(df, cfg, srs)
    s.to_csv(OUT / "summary_design.csv", index=False)
    st = stops_table(df)
    st.round(4).to_csv(OUT / "stops.csv", index=False)
    name, choice = choose(s)
    (OUT / "choice.md").write_text(choice)
    chart_equity(
        df,
        OUT / "equity_design.png",
        "Design cycles: option-only P&L (no cash interest) and NIFTY 50 TRI, log scale",
    )
    if len(st):
        chart_stops(st, OUT / "stops_effect.png")
    md = (
        [
            "# Phase 3 report\n",
            f"Design: {len(cyc)} cycles, entries {cyc.entry.min():%Y-%m-%d} to "
            f"{cyc.entry.max():%Y-%m-%d}. Base = Phase 1 put "
            "spread with the Phase 2 fallback rule. e1 = stop at 2x credit, exit next close; f1 = "
            "trade only if ATM IV - "
            "trailing 21-day RV is above the expanding median; e1f1 = both. Option-only returns "
            "(no cash interest) are "
            "the headline; their Sharpe has no risk-free deduction (the margin's interest is "
            "earned separately, so this "
            "is an excess-over-cash return).\n",
            "## Design results\n",
            fmt(s, COLS),
            "",
            f"Market over the same cycles: NIFTY 50 TRI CAGR {mk['TRI CAGR']:.1%}, Sharpe "
            f"{mk['TRI Sharpe (no rf)']:.2f}; "
            f"TRI minus cash: mean {mk['TRI excess over cash, mean monthly']:.2%} a month, Sharpe "
            f"{mk['TRI excess Sharpe']:.2f}.\n",
            "## Stops (design)\n",
            st[st.period == "design"].round(2).to_markdown(index=False) if len(st) else "None.",
            "",
            "## Deflated Sharpe ratio (design, 12 cumulative trials)\n",
            "Inputs: monthly option-only Sharpe of each series, months, skewness and kurtosis of "
            "its monthly returns; "
            f"variance of monthly Sharpe across the {len(srs)} trials on design cycles "
            f"({', '.join(f'{k} {v:.3f}' for k, v in srs.items())}).\n",
            fmt(s, ["variant", "SR monthly", "DSR SR0 (monthly)", "months", "DSR"]),
            "",
            "## Reading (design)\n",
        ]
        + reading(s, mk, df, "design")
        + ["", choice.replace("# Phase 3 choice", "## Choice"), "## Checks\n"]
        + rec
    )
    (OUT / "phase3_report.md").write_text("\n".join(md) + "\n")
    logger.info("\n".join(md))


def frozen(cfg: dict, name) -> str:
    """Write the frozen rule file with the config hash and data dates."""
    h = hashlib.sha256(CONFIG_PATH.read_bytes()).hexdigest()
    fo_end = pd.read_parquet("data/processed/nifty_fo.parquet", columns=["date"]).date.max()
    v = variants(cfg)[name]
    c, p3 = cfg["costs"], cfg["phase3"]
    lines = [
        f"# Frozen rule (after Phase 3; no further changes): {name}\n",
        f"Frozen {datetime.now():%Y-%m-%d %H:%M}. Config SHA-256 `{h}`. Data in hand to "
        f"{fo_end:%Y-%m-%d}; tuning used data to "
        f"{cfg['phase2']['validation_end']} only (the Phase 1 holdout, Nov 2024 onward, was scored "
        "once in Phase 1 and not used since).\n",
        "## Trade",
        "- Instrument: NIFTY 50 index options, monthly expiry only (the last expiry of each "
        "calendar month as listed by NSE; actual expiry day = last trading day of the contract).",
        "- Entry: first trading day after each monthly expiry, at the close; options on the next "
        "monthly expiry; S0 = NIFTY 50 close on the entry day.",
        f"- Sell the put nearest {cfg['rules']['put_spread'][0][2]} x S0; buy the put nearest "
        f"{cfg['rules']['put_spread'][1][2]} x S0. A strike must have close > 0 and contracts "
        "traded > 0 that day; start at the listed strike nearest the target and move further out "
        f"of the money; if none within {cfg['strike_band']:.0%} of target, take the nearest traded "
        "strike further out of the money than the target; skip the month only if none exists.",
        "- Size: units so that (spread width - net credit after slippage) x units = "
        f"{cfg['max_loss_pct']:.0%} of current capital. Margin assumed = that max loss.",
        "- Hold to expiry; cash-settled at intrinsic value against the final settlement price "
        "(index close on expiry day).",
    ]
    if v["stop"]:
        lines.append(
            "- Stop: at each close after entry, mark both legs at the bhavcopy close; if the "
            f"mark-to-market loss (from the entry fills) >= {p3['stop_mult']} x net credit "
            "received, close both legs at the next trading day's close; ignore a trigger on the "
            "day before expiry; stay in cash until the next entry."
        )
    else:
        lines.append("- No stop-loss: positions are held to expiry.")
    if v["filter"]:
        lines.append(
            "- Filter: trade only if ATM IV (strike nearest S0, mean of call and put "
            f"Black-Scholes IV, r {cfg['rf']:.1%}) minus realised vol of the previous "
            f"{p3['rv_days']} trading days is above the median of that gap over all earlier "
            f"entries (needs {p3['min_history']} earlier cycles)."
        )
    else:
        lines.append("- No entry filter: trade every month.")
    lines += [
        "",
        "## Costs (VERIFY before trading)",
        f"- Slippage per unit: sell at close - max({c['slip_min']}, {c['slip_pct']:.0%} of close); "
        "buy at close + the same.",
        f"- STT on premium sold: {', '.join(f'{r:.4%} from {d}' for d, r in c['stt_sell'])}; STT "
        f"on long options expiring in the money {c['stt_itm']:.3%} of intrinsic value.",
        f"- Brokerage Rs {c['brokerage']} per order; exchange charge "
        f"{', '.join(f'{r:.4%} from {d}' for d, r in c['exch'])} of premium; SEBI {c['sebi']:.4%}; "
        f"stamp duty {c['stamp']:.3%} on premium bought; GST {c['gst']:.0%} on brokerage + "
        "exchange + SEBI.",
        f"- Idle cash earns {cfg['cash_rate']:.1%} a year (assumption).",
        "",
        "## Capital",
        f"- Paper capital Rs {cfg['capital']:,}; fractional units in the backtest. Live, units "
        "must be rounded down to whole lots (NSE lot size on the entry date), which at this "
        "capital means very few lots.",
    ]
    return "\n".join(lines) + "\n"


def validate(cfg: dict) -> None:
    """Phase 3 validation, run once; freezes the chosen rule."""
    log = OUT / "validation_runs.log"
    if log.exists() and log.read_text().strip():
        logger.info("Validation already run once; not running again. Log:\n" + log.read_text())
        return
    assert (OUT / "choice.md").exists(), "choice.md must be committed before validation"
    name = (OUT / "choice.md").read_text().split("**Chosen: ")[1].split("**")[0]
    ctx, gp = ctx_for(cfg, "validation")
    df, cyc = run_period(cfg, ctx, "validation", gp)
    rec = reconcile(df)
    srs = trial_srs(cfg, ctx, "validation", df)
    s, mk = summarise(df, cfg, srs)
    s["chosen"] = np.where(s.variant == name, "yes", "")
    s.to_csv(OUT / "summary_validation.csv", index=False)
    dv = pd.read_csv(OUT / "monthly_pnl_phase3.csv")
    dv = dv[dv.period == "design"]
    out = df.drop(columns=["next_entry", "tri_ret", "trigger_pnl"])
    both = pd.concat([dv, out], ignore_index=True)
    num = both.select_dtypes("number").columns
    both[num] = both[num].round(4)
    both.to_csv(OUT / "monthly_pnl_phase3.csv", index=False)
    st = pd.concat([pd.read_csv(OUT / "stops.csv"), stops_table(df).round(4)], ignore_index=True)
    st.to_csv(OUT / "stops.csv", index=False)
    if len(st):
        chart_stops(st, OUT / "stops_effect.png")
    md = (
        [
            "\n## Validation (run 1)\n",
            "**Validation; aggregate results for this period were seen in Phase 1, so not a clean "
            f"test.** {len(cyc)} cycles, "
            f"entries {cyc.entry.min():%Y-%m-%d} to {cyc.entry.max():%Y-%m-%d}. Chosen rule (from "
            f"design): **{name}**.\n",
            fmt(s, COLS),
            "",
            f"Market over the same cycles: NIFTY 50 TRI CAGR {mk['TRI CAGR']:.1%}, Sharpe "
            f"{mk['TRI Sharpe (no rf)']:.2f}; "
            f"TRI minus cash: Sharpe {mk['TRI excess Sharpe']:.2f}.\n",
            "Stops (validation):\n",
            stops_table(df).round(2).to_markdown(index=False)
            if (df.stop_triggered == "yes").any()
            else "None.",
            "",
            "Reading (validation):\n",
        ]
        + reading(s, mk, df, "validation")
        + ["", "Validation checks:\n"]
        + rec
        + ["", f"Frozen rule: **{name}**, see `frozen_rule.md`."]
    )
    with open(OUT / "phase3_report.md", "a") as f:
        f.write("\n".join(md) + "\n")
    (OUT / "frozen_rule.md").write_text(frozen(cfg, name))
    with open(log, "a") as f:
        f.write(
            f"run 1 at {datetime.now():%Y-%m-%d %H:%M:%S}, {len(cyc)} cycles "
            f"{cyc.entry.min():%Y-%m-%d} to "
            f"{cyc.expiry.max():%Y-%m-%d}, chosen {name}\n"
            + fmt(s, ["variant", "option CAGR", "option Sharpe", "worst month", "CVaR99", "DSR"])
            + "\n"
        )
    logger.info("\n".join(md))


def bisect_iv(price, s, k, t, r, o) -> float:
    """Implied volatility by bisection, for the checks."""
    lo, hi = 1e-4, 5.0
    for _ in range(200):
        v = (lo + hi) / 2
        a = (np.log(s / k) + (r + v * v / 2) * t) / (v * np.sqrt(t))
        b = a - v * np.sqrt(t)
        p = (
            (s * p2.ncdf(a) - k * np.exp(-r * t) * p2.ncdf(b))
            if o == "C"
            else (k * np.exp(-r * t) * p2.ncdf(-b) - s * p2.ncdf(-a))
        )
        lo, hi = (v, hi) if p < price else (lo, v)
    return v


def check(cfg: dict) -> None:
    """Phase 3 checks."""
    out = ["# Phase 3 checks\n"]
    ctx, gp = ctx_for(cfg, "design")
    p = cfg["phase2"]
    vend = pd.Timestamp(p["validation_end"])
    hold = data.cycles(*data.load())
    assert (
        not ctx["cyc"].entry.isin(hold[hold.expiry > vend].entry).any()
        and ctx["opt"].date.max() <= vend
    )
    des = ctx["cyc"][ctx["cyc"].period == "design"].reset_index(drop=True)
    assert des.entry.max() <= pd.Timestamp(p["design_end"]) and gp.index.max() <= des.entry.max()
    runs = (
        (OUT / "validation_runs.log").read_text().count("run ")
        if (OUT / "validation_runs.log").exists()
        else 0
    )
    assert runs <= 1
    out.append(
        f"- split: design {len(des)} cycles; filter gaps computed only for design entries; no "
        "holdout cycle "
        f"loaded, no option data after {vend:%Y-%m-%d}; validation runs logged: {runs}."
    )

    rng = np.random.default_rng(3)
    for i in sorted(rng.choice(np.arange(30, len(des)), 3, replace=False)):
        c = des.iloc[i]
        s0 = float(ctx["ix"].close[c.entry])
        t = (c.expiry - c.entry).days / 365
        ch = bt.chain(ctx["opt"], c.entry, c.contract)
        ivs = []
        for o, code in (("C", "CE"), ("P", "PE")):
            x = ch[(ch.opt == code) & (ch.close > 0)]
            r = x.iloc[(x.strike - s0).abs().argmin()]
            ivs.append(bisect_iv(r.close, s0, r.strike, t, cfg["rf"], o))
        cl = ctx["ix"].close.dropna()
        cl = cl[cl.index <= c.entry].values[-22:]
        lr = np.diff(np.log(cl))
        rv = np.sqrt(((lr - lr.mean()) ** 2).sum() / (len(lr) - 1)) * np.sqrt(252)
        gap = np.mean(ivs) - rv
        earlier = gp[gp.index < c.entry].gap.dropna()
        thr = np.median(earlier.values)
        g = gp.loc[c.entry]
        assert abs(gap - g.gap) < 1e-6 and abs(thr - g.threshold) < 1e-12 and len(lr) == 21
        out.append(
            f"- filter {c.entry:%Y-%m-%d}: IV {np.mean(ivs):.4f}, RV21 {rv:.4f}, gap {gap:.4f} "
            f"(code {g.gap:.4f}); "
            f"threshold = median of {len(earlier)} earlier gaps (entries "
            f"{earlier.index.min():%Y-%m} to "
            f"{earlier.index.max():%Y-%m-%d}, all before entry) = {thr:.4f} (code "
            f"{g.threshold:.4f}): OK"
        )

    df, _ = run_period(cfg, ctx, "design", gp)
    rec = reconcile(df)
    assert all("PASS" in r for r in rec)
    out += rec
    st = df[(df.rule == "e1") & (df.stop_triggered == "yes")]
    days = ctx["days"]
    for _, r in st.sample(min(3, len(st)), random_state=3).iterrows():
        e, x = pd.Timestamp(r.entry_date), pd.Timestamp(r.expiry_date)
        d = days[(days >= e) & (days <= x)]
        c = des[des.entry == e].iloc[0]
        legs = []
        for side, name in ((-1, "short_put"), (1, "long_put")):
            k = float(r[f"{name}_strike"])
            q = (
                ctx["opt"][
                    (ctx["opt"].expiry == c.contract)
                    & (ctx["opt"].strike == k)
                    & (ctx["opt"].opt == "PE")
                    & (ctx["opt"].close > 0)
                ]
                .set_index("date")
                .close
            )
            cl0 = r[f"{name}_entry_price"]
            slip = max(cfg["costs"]["slip_min"], cfg["costs"]["slip_pct"] * cl0)
            legs.append((side, q, cl0 - slip if side < 0 else cl0 + slip))
        u = r.units
        credit = (legs[0][2] - legs[1][2]) * u
        trig = None
        for n in range(1, len(d) - 2):
            pnl = 0.0
            for side, q, px in legs:
                m = q[q.index <= d[n]]
                pnl += side * (m.iloc[-1] - px) * u
            if -pnl >= cfg["phase3"]["stop_mult"] * credit:
                trig = n
                break
        assert trig is not None and d[trig].date() == pd.Timestamp(r.trigger_date).date()
        nxt = d[trig + 1]
        assert pd.Timestamp(r.exit_date) >= nxt and (
            r.exit_flag == "yes" or pd.Timestamp(r.exit_date) == nxt
        )
        out.append(
            f"- stop e1 {r.entry_date}: by-hand trigger {d[trig]:%Y-%m-%d} (loss >= 2 x credit Rs "
            f"{credit:,.0f}) = code "
            f"{r.trigger_date}; exit {r.exit_date} = next trading day after the trigger"
            + (" (flagged: a leg had no close that day)" if r.exit_flag == "yes" else "")
            + ": OK"
        )

    ref = pd.read_csv("results/phase2/monthly_pnl_phase2.csv")
    ref = ref[ref.rule == "ref_put_spread_fallback"]
    base = df[df.rule == "base"]
    gap = np.abs(base.capital_end.values - ref[ref.period == "design"].capital_end.values).max()
    assert gap < 0.01
    out.append(
        f"- base reproduces Phase 2 ref_put_spread_fallback on design: max capital gap Rs {gap:.4f}"
    )
    if runs:
        m3 = pd.read_csv(OUT / "monthly_pnl_phase3.csv")
        b3 = m3[(m3.rule == "base") & (m3.period == "validation")].capital_end.values
        g2 = np.abs(b3 - ref[ref.period == "validation"].capital_end.values).max()
        assert g2 < 0.01
        out.append(
            "- base reproduces Phase 2 ref_put_spread_fallback on validation (stored rows): max "
            f"capital gap Rs {g2:.4f}"
        )
    (OUT / "checks.md").write_text("\n".join(out) + "\n")
    logger.info("\n".join(out))
