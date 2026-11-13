from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.stats import norm

from optsell import backtest as bt
from optsell import data, marking
from optsell import phase2 as p2
from optsell import phase3 as p3
from optsell.pricing import bs, d1, iv

matplotlib.use("Agg")
logger = logging.getLogger(__name__)

OUT = Path("results/census")
ITEMS = p3.ITEMS + ["etf_cost"]
REFS = {
    "ref_base": [[["P", -1, 1, 0.95], ["P", 1, 1, 0.90]], "defined", False],
    "ref_iron_condor": [
        [["P", -1, 1, 0.95], ["P", 1, 1, 0.90], ["C", -1, 1, 1.05], ["C", 1, 1, 1.10]],
        "defined",
        False,
    ],
    "ref_strangle": [[["P", -1, 1, 0.95], ["C", -1, 1, 1.05]], "notional", False],
}
COLS = (
    [
        "rule",
        "strategy",
        "variant",
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
        "legs",
        "net_credit_or_debit",
        "capital_start",
        "units",
        "notional",
        "margin_used",
        "margin_pct_of_capital",
        "idle_cash",
        "max_loss_planned",
        "risk_pct_of_capital",
        "credit_gross",
        "slippage_cost",
        "credit_net",
        "settlement_payout",
        "option_pnl_before_charges",
    ]
    + ITEMS
    + [
        "total_charges",
        "total_costs",
        "costs_pct_of_credit_gross",
        "index_leg_pnl",
        "futures_hedge_pnl",
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
        "relative_to_tri_pct",
        "stop_triggered",
        "trigger_date",
        "exit_date",
        "exit_cost",
        "pnl_if_held",
        "stop_effect",
        "exit_flag",
        "fallback_used",
        "sizing_note",
        "hedge_rebalances",
        "futures_gaps",
    ]
)


def strategies(cfg: dict, refs=True) -> dict:
    """The 12 census strategy families plus their stop variants."""
    out = {}
    for n, (legs, sz, stop) in cfg["census"]["strategies"].items():
        out[n] = {"strategy": n, "variant": "base", "legs": legs, "sizing": sz, "stop": False}
        if stop:
            out[f"{n}_e1"] = {
                "strategy": n,
                "variant": "e1",
                "legs": legs,
                "sizing": sz,
                "stop": True,
            }
    if refs:
        for n, (legs, sz, _stop) in REFS.items():
            out[n] = {"strategy": n, "variant": "ref", "legs": legs, "sizing": sz, "stop": False}
    return out


def load(cfg: dict) -> dict:
    """Shared inputs for the census (chains, marks, cycles)."""
    ctx = p2.load(cfg)
    vend = pd.Timestamp(cfg["phase2"]["validation_end"])
    fo, _ = data.load()
    fut = fo[(fo.instr == "FUTIDX") & (fo.date <= vend) & (fo.close > 0)]
    ctx["fut"] = fut.set_index(["expiry", "date"]).close.sort_index()
    sub = ctx["opt"][ctx["opt"].date.isin(ctx["cyc"].entry)]
    ctx["byday"] = {d: g for d, g in sub.groupby("date")}
    far = []
    for c in ctx["cyc"].itertuples():
        day = ctx["byday"][c.entry]
        m = c.contract.to_period("M") + 1
        cand = day.expiry[day.expiry.dt.to_period("M") == m]
        far.append(cand.max() if len(cand) else pd.NaT)
    ctx["cyc"]["far"] = far
    ctx["bk"] = marking.book(ctx["opt"], set(ctx["cyc"].contract) | set(ctx["cyc"].far.dropna()))
    return ctx


def chain(ctx, entry, contract) -> pd.DataFrame:
    """Option chain for an entry day and contract."""
    ch = ctx["byday"][entry]
    ch = ch[ch.expiry == contract]
    assert (ch.date == entry).all()
    return ch


def payoff(legs, s) -> float:
    """Settlement payoff per unit of a set of legs at index level s."""
    return sum(leg["side"] * leg["q"] * bt.intrinsic(leg["opt"], leg["k"], s) for leg in legs)


def fill(legs, cc) -> None:
    """Entry fills with slippage, in place."""
    for leg in legs:
        slip = max(cc["slip_min"], cc["slip_pct"] * leg["close"])
        leg["px"] = max(0.0, leg["close"] - slip) if leg["side"] < 0 else leg["close"] + slip
        leg["slip"] = leg["px"] - leg["close"] if leg["side"] > 0 else leg["close"] - leg["px"]


def pick(spec, ch, s0, cfg: dict) -> tuple:
    """Strikes of a strategy spec on the entry day."""
    legs, fb = [], False
    for o, side, q, m in spec:
        r, f = p2.pick_money(ch, o, m * s0, cfg, "fallback")
        if r is None:
            return None, False, f"no traded {o} strike near {m:.2f} x S0"
        legs.append({"opt": o, "side": side, "q": q, "k": float(r.strike), "close": float(r.close)})
        fb = fb or f
    return legs, fb, ""


def naked(legs) -> int:
    """Net number of uncovered short options."""
    n = 0
    for o in ("P", "C"):
        n += max(
            0,
            sum(leg["q"] for leg in legs if leg["opt"] == o and leg["side"] < 0)
            - sum(leg["q"] for leg in legs if leg["opt"] == o and leg["side"] > 0),
        )
    return n


def option_fees(legs, units, entry, cc, exits=None, itm=True) -> dict:
    """Brokerage, STT, exchange, SEBI, stamp and GST for a cycle's fills."""
    fills = [(entry, leg["px"], units * leg["q"], leg["side"] < 0) for leg in legs]
    if exits:
        fills += [
            (x["date"], x["px"], units * leg["q"], leg["side"] > 0)
            for leg, x in zip(legs, exits, strict=False)
            if x is not None
        ]
    held = (
        sum(
            leg["q"] * bt.intrinsic(leg["opt"], leg["k"], legs[0]["settle"]) * units
            for leg in legs
            if leg["side"] > 0
        )
        if itm
        else 0.0
    )
    it = p3.fees(fills, held, cc)
    it["etf_cost"] = 0.0
    return it


def stress_loss(legs, credit, s0, sizing, cs) -> float:
    """Loss per unit under the sizing stress move (-25% / +20%)."""
    lv = {
        "stress_down": [1 - cs["stress_down"]],
        "stress_up": [1 + cs["stress_up"]],
        "stress_both": [1 - cs["stress_down"], 1 + cs["stress_up"]],
    }[sizing]
    return max(-payoff(legs, m * s0) - credit for m in lv)


def size(st, legs, credit, s0, capital, cfg: dict) -> tuple | None:
    """Units so the strategy's planned loss equals 10% of capital."""
    cs = cfg["census"]
    note = ""
    sz = st["sizing"]
    if sz == "defined":
        grid = [0.0] + [leg["k"] for leg in legs] + [10 * s0]
        maxloss = -min(payoff(legs, s) for s in grid) - credit
        if maxloss <= 0:
            return None
        units = cfg["max_loss_pct"] * capital / maxloss
        if (
            st["strategy"] in cs.get("cap_defined", [])
            and units * s0 > cs["notional_cap"] * capital
        ):
            units = cs["notional_cap"] * capital / s0
            note = "notional capped at 1.5x"
        margin = units * maxloss
        risk = margin
    else:
        if sz.startswith("stress"):
            loss = stress_loss(legs, credit, s0, sz, cs)
            if loss <= 0:
                return None
            units = cfg["max_loss_pct"] * capital / loss
            if units * s0 > cs["notional_cap"] * capital:
                units = cs["notional_cap"] * capital / s0
                note = "notional capped at 1.5x"
        else:
            units = capital / s0
        margin = cs["naked_margin"] * units * s0 * naked(legs)
        risk = units * stress_loss(legs, credit, s0, "stress_both", cs)
    if margin > capital:
        f = capital / margin
        units, margin, risk = units * f, capital, risk * f
        note = (note + "; " if note else "") + "margin capped at capital"
    return units, margin, risk, note


def marks_stop(legs, units, credit, c, days, ctx, cfg: dict) -> dict | None:
    """Daily marks and the 2x-credit stop for one cycle."""
    raw = [p3.leg_series(ctx["bk"], c.contract, leg) for leg in legs]
    pnl = np.zeros(len(days))
    for leg, s in zip(legs, raw, strict=False):
        m = s.reindex(days)
        m.iloc[0] = leg["close"]
        pnl += leg["side"] * leg["q"] * (m.ffill().values - leg["px"]) * units
    limit = cfg["phase3"]["stop_mult"] * units * credit
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
            dt, cl, flag = days[-1], bt.intrinsic(leg["opt"], leg["k"], c.settle), True
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


def empty() -> dict:
    """A row of zero charge items."""
    r = dict.fromkeys(ITEMS, 0.0)
    r.update(
        {
            "index_leg_pnl": 0.0,
            "futures_hedge_pnl": 0.0,
            "fut_slip": 0.0,
            "stop_triggered": "no",
            "sizing_note": "",
        }
    )
    return r


def cycle_generic(st, c, capital, ctx, cfg: dict, rate) -> dict:
    """One cycle of a census strategy (sizing, stop, costs, P&L)."""
    cc = cfg["costs"]
    s0 = float(ctx["ix"].close[c.entry])
    legs, fb, why = pick(st["legs"], chain(ctx, c.entry, c.contract), s0, cfg)
    if legs is None:
        return why
    fill(legs, cc)
    for leg in legs:
        leg["settle"] = c.settle
    credit = sum(-leg["side"] * leg["q"] * leg["px"] for leg in legs)
    if st["sizing"] == "index":
        units, margin, note = capital / s0, 0.0, ""
        risk = (
            units * stress_loss(legs, credit, s0, "stress_both", cfg["census"])
            + capital * cfg["census"]["stress_down"]
        )
    else:
        z = size(st, legs, credit, s0, capital, cfg)
        if z is None:
            return "sizing loss not positive"
        units, margin, risk, note = z
    days_total = (c.next_entry - c.entry).days
    r = empty()
    r.update(
        {
            "legs_obj": legs,
            "units": units,
            "credit": credit,
            "margin": margin,
            "risk": risk,
            "sizing_note": note,
            "fallback_used": "yes" if fb else "no",
            "payoff_unit": payoff(legs, c.settle),
            "slippage": sum(leg["slip"] * leg["q"] for leg in legs) * units,
        }
    )
    r.update(option_fees(legs, units, c.entry, cc))
    r["pnl_if_held"] = units * (credit + r["payoff_unit"]) - sum(r[i] for i in ITEMS)
    idle = 0.0 if st["sizing"] == "index" else capital
    r["interest"] = rate * (idle - margin) * days_total / 365 if st["sizing"] != "index" else 0.0
    if st["sizing"] == "index":
        r["index_leg_pnl"] = capital * c.tri_ret
        r["etf_cost"] = cfg["census"]["etf_cost"] * capital * days_total / 365
    if st["stop"]:
        if credit <= 0:
            r["sizing_note"] = (note + "; " if note else "") + "net debit: no stop"
        else:
            days = ctx["days"][(ctx["days"] >= c.entry) & (ctx["days"] <= c.expiry)]
            s = marks_stop(legs, units, credit, c, days, ctx, cfg)
            if s:
                r["payoff_unit"] = sum(
                    leg["side"] * leg["q"] * x["close"]
                    for leg, x in zip(legs, s["legs"], strict=False)
                )
                exit_slip = (
                    sum(x["slip"] * leg["q"] for leg, x in zip(legs, s["legs"], strict=False))
                    * units
                )
                it = option_fees(legs, units, c.entry, cc, s["legs"], itm=False)
                entry_it = option_fees(legs, units, c.entry, cc, None, itm=False)
                r.update(it)
                r["slippage"] += exit_slip
                held = (s["exit"] - c.entry).days
                r["interest"] = rate * (capital * days_total - margin * held) / 365
                opt_net = (
                    units * (credit + r["payoff_unit"]) - exit_slip - sum(it[i] for i in ITEMS)
                )
                r.update(
                    {
                        "stop_triggered": "yes",
                        "trigger_date": s["trigger"].date(),
                        "exit_date": s["exit"].date(),
                        "trigger_pnl": s["trigger_pnl"],
                        "exit_flag": "yes" if s["flag"] else "no",
                        "exit_cost": exit_slip
                        + sum(it[i] for i in ITEMS)
                        - sum(entry_it[i] for i in ITEMS),
                        "stop_effect": "helped" if opt_net > r["pnl_if_held"] else "hurt",
                    }
                )
    return r


def cycle_calendar(st, c, capital, ctx, cfg: dict, rate) -> dict:
    """One cycle of the calendar spread (far leg valued at the near expiry)."""
    cc = cfg["costs"]
    s0 = float(ctx["ix"].close[c.entry])
    if pd.isna(c.far):
        return "far-month contract not listed"
    nr = p2.traded(chain(ctx, c.entry, c.contract), "PE")
    fr = p2.traded(chain(ctx, c.entry, c.far), "PE")
    both = nr[nr.strike.isin(fr.strike)]
    if both.empty:
        return "no put strike traded in both near and far month"
    k = float(both.loc[(both.strike - s0).abs().idxmin()].strike)
    legs = [
        {"opt": "P", "side": -1, "q": 1, "k": k, "close": float(nr[nr.strike == k].close.iloc[0])},
        {"opt": "P", "side": 1, "q": 1, "k": k, "close": float(fr[fr.strike == k].close.iloc[0])},
    ]
    fill(legs, cc)
    for leg in legs:
        leg["settle"] = c.settle
    debit = legs[1]["px"] - legs[0]["px"]
    if debit <= 0:
        return "calendar debit not positive"
    units = cfg["max_loss_pct"] * capital / debit
    cl, flag = far_value(c, k, ctx, cfg)
    slip = max(cc["slip_min"], cc["slip_pct"] * cl)
    ex = {
        "date": c.expiry,
        "close": cl,
        "px": max(0.0, cl - slip),
        "slip": cl - max(0.0, cl - slip),
    }
    r = empty()
    r.update(
        {
            "legs_obj": legs,
            "units": units,
            "credit": -debit,
            "margin": units * debit,
            "risk": units * debit,
            "fallback_used": "no",
            "payoff_unit": -bt.intrinsic("P", k, c.settle) + cl,
            "slippage": (legs[0]["slip"] + legs[1]["slip"] + ex["slip"]) * units,
            "exit_flag": flag,
        }
    )
    it = option_fees(legs, units, c.entry, cc, [None, ex], itm=False)
    r.update(it)
    r["interest"] = rate * (capital - r["margin"]) * (c.next_entry - c.entry).days / 365
    r["pnl_if_held"] = np.nan
    return r


def far_value(c, k, ctx, cfg: dict) -> tuple:
    """Value of the far-month leg on the near expiry day."""
    day = ctx["opt"][ctx["opt"].date == c.expiry]
    m = c.contract.to_period("M") + 1
    lab = day.expiry[day.expiry.dt.to_period("M") == m].max()
    x = day[
        (day.expiry == lab)
        & (day.strike == k)
        & (day.opt == "PE")
        & (day.close > 0)
        & (day.volume > 0)
    ]
    if len(x):
        return float(x.close.iloc[0]), "no"
    s = float(ctx["ix"].close[c.expiry])
    t = (lab - c.expiry).days / 365
    ch = day[(day.expiry == lab) & (day.close > 0)]
    ivs = []
    for o, code in (("C", "CE"), ("P", "PE")):
        z = ch[ch.opt == code]
        if len(z):
            r = z.iloc[(z.strike - s).abs().argmin()]
            ivs.append(iv(r.close, s, r.strike, t, cfg["rf"], o))
    v, flag = np.nanmean(ivs) if ivs and not np.isnan(ivs).all() else np.nan, "bs_atm_iv"
    if np.isnan(v):
        v, flag = float(ctx["ix"].vix.get(c.expiry, np.nan)) / 100, "bs_vix"
    return float(bs(s, k, t, cfg["rf"], v, "P")), flag


def call_delta(s, k, t, r, vol, q) -> float:
    """Black-Scholes call delta."""
    return np.exp(-q * t) * norm.cdf(d1(s, k, t, r, vol, q))


def hedge_path(legs, units, c, ctx, cfg: dict) -> tuple:
    """Daily delta hedge with the near-month future."""
    days = ctx["days"][(ctx["days"] >= c.entry) & (ctx["days"] <= c.expiry)]
    r, q = cfg["rf"], cfg["phase2"]["div_yield"]
    series = [p3.leg_series(ctx["bk"], c.contract, leg) for leg in legs]
    prev = [np.nan, np.nan]
    hs, fs, gaps = [], [], 0
    lastf = np.nan
    for i, d in enumerate(days[:-1]):
        s = float(ctx["ix"].close[d])
        t = (c.expiry - d).days / 365
        dl = []
        for j, (leg, ser) in enumerate(zip(legs, series, strict=False)):
            cl = leg["close"] if i == 0 else ser.get(d, np.nan)
            v = iv(cl, s, leg["k"], t, r, leg["opt"], q) if pd.notna(cl) else np.nan
            if pd.notna(v):
                cd = call_delta(s, leg["k"], t, r, v, q)
                prev[j] = cd if leg["opt"] == "C" else cd - np.exp(-q * t)
            dl.append(prev[j])
        hs.append(units * np.nansum(dl))
        f = ctx["fut"].get((c.contract, d), np.nan)
        if pd.isna(f):
            gaps += 1
            f = lastf
        lastf = f
        fs.append(f)
    return days, np.array(hs), np.array(fs), gaps


def cycle_hedged(st, c, capital, ctx, cfg: dict, rate) -> dict:
    """One cycle of the delta-hedged straddle."""
    r = cycle_generic({**st, "sizing": "notional", "stop": False}, c, capital, ctx, cfg, rate)
    if isinstance(r, str):
        return r
    cs, cc = cfg["census"], cfg["costs"]
    days, hs, fs, gaps = hedge_path(r["legs_obj"], r["units"], c, ctx, cfg)
    fpath = np.r_[fs, c.settle]
    pnl = float(np.sum(hs * np.diff(fpath)))
    trades = np.diff(np.r_[0.0, hs])
    fees = dict.fromkeys(p3.ITEMS, 0.0)
    for d, dq, f in zip(days[:-1], trades, fs, strict=False):
        if abs(dq) < 1e-12:
            continue
        v = abs(dq) * f
        fees["brokerage"] += cc["brokerage"]
        if dq < 0:
            fees["stt"] += bt.rate_on(cs["fut_stt_sell"], d) * v
        else:
            fees["stamp_duty"] += cs["fut_stamp"] * v
        fees["exchange_charges"] += bt.rate_on(cs["fut_exch"], d) * v
        fees["sebi_fees"] += cc["sebi"] * v
    fees["gst"] = cc["gst"] * (fees["brokerage"] + fees["exchange_charges"] + fees["sebi_fees"])
    for k in p3.ITEMS:
        r[k] += fees[k]
    fslip = cs["fut_slippage_pts"] * float(np.abs(trades).sum())
    fmargin = cs["fut_margin"] * float(np.nanmax(np.abs(hs) * fs)) if len(hs) else 0.0
    r["margin"] += fmargin
    if r["margin"] > capital:
        r["sizing_note"] = "margin above capital (not capped for the hedge)"
    r.update(
        {
            "futures_hedge_pnl": pnl,
            "fut_slip": fslip,
            "slippage": r["slippage"] + fslip,
            "hedge_rebalances": int((np.abs(trades) > 1e-12).sum()),
            "futures_gaps": gaps,
            "risk": np.nan,
            "pnl_if_held": np.nan,
            "hedge_path": (days, hs, fs),
        }
    )
    r["interest"] = rate * (capital - r["margin"]) * (c.next_entry - c.entry).days / 365
    return r


def legs_text(legs) -> str:
    """Legs as text for the monthly file."""
    return "; ".join(
        f"{'S' if leg['side'] < 0 else 'B'}{leg['q']} {leg['opt']} {leg['k']:.0f} @{leg['close']:g}"
        for leg in legs
    )


def run(name, st, cyc, ctx, cfg: dict, rate, period, mk) -> tuple:
    """Run one census strategy over a period's cycles."""
    capital = cfg["capital"]
    peak = capital
    rows, paths = [], {}
    fn = {"debit": cycle_calendar, "hedged": cycle_hedged}.get(st["sizing"], cycle_generic)
    for n, c in enumerate(cyc.itertuples(), 1):
        s0 = float(ctx["ix"].close[c.entry])
        v = mk.loc[c.entry]
        row = {
            "rule": name,
            "strategy": st["strategy"],
            "variant": st["variant"],
            "period": period,
            "cycle_no": n,
            "entry_date": c.entry.date(),
            "expiry_date": c.expiry.date(),
            "days_to_expiry": (c.expiry - c.entry).days,
            "index_at_entry": s0,
            "index_at_expiry": c.settle,
            "index_move_pct": 100 * (c.settle / s0 - 1),
            "india_vix_at_entry": v.vix * 100 if pd.notna(v.vix) else np.nan,
            "atm_iv_at_entry_pct": 100 * v.iv,
            "realised_vol_pct": 100 * v.rv,
            "iv_minus_future_rv_pts": 100 * v.vrp,
            "capital_start": capital,
            "nifty_tri_return_pct": 100 * c.tri_ret,
            "next_entry": c.next_entry,
            "stop_triggered": "no",
        }
        r = fn(st, c, capital, ctx, cfg, rate) if capital > 0 else "capital exhausted"
        days_total = (c.next_entry - c.entry).days
        if isinstance(r, str):
            interest = rate * max(capital, 0) * days_total / 365
            row.update(
                {
                    "skipped": "yes",
                    "skip_reason": r,
                    "units": 0.0,
                    "notional": 0.0,
                    "margin_used": 0.0,
                    "margin_pct_of_capital": 0.0,
                    "idle_cash": capital,
                    "net_credit_or_debit": 0.0,
                    "credit_gross": 0.0,
                    "slippage_cost": 0.0,
                    "settlement_payout": 0.0,
                    "index_leg_pnl": 0.0,
                    "futures_hedge_pnl": 0.0,
                    "cash_interest": interest,
                    "outcome": "skipped",
                    "win": "no",
                    "fallback_used": "no",
                    **dict.fromkeys(ITEMS, 0.0),
                }
            )
        else:
            u, legs = r["units"], r["legs_obj"]
            nshort = sum(leg["q"] for leg in legs if leg["side"] < 0)
            row.update(
                {
                    "skipped": "no",
                    "skip_reason": "",
                    "legs": legs_text(legs),
                    "units": u,
                    "net_credit_or_debit": u * r["credit"],
                    "notional": capital
                    if st["sizing"] == "index"
                    else u * s0 * max(naked(legs), 1 if nshort else 0),
                    "margin_used": r["margin"],
                    "margin_pct_of_capital": 100 * r["margin"] / capital,
                    "idle_cash": 0.0
                    if st["sizing"] == "index"
                    else max(0.0, capital - r["margin"]),
                    "max_loss_planned": r["risk"],
                    "risk_pct_of_capital": 100 * r["risk"] / capital
                    if pd.notna(r["risk"])
                    else np.nan,
                    "credit_gross": u * sum(-leg["side"] * leg["q"] * leg["close"] for leg in legs),
                    "slippage_cost": r["slippage"],
                    "settlement_payout": -u * r["payoff_unit"] + 0.0,
                    "index_leg_pnl": r["index_leg_pnl"],
                    "futures_hedge_pnl": r["futures_hedge_pnl"],
                    "cash_interest": r["interest"],
                    "fallback_used": r["fallback_used"],
                    "sizing_note": r["sizing_note"],
                    **{k: r[k] for k in ITEMS},
                }
            )
            for k in (
                "stop_triggered",
                "trigger_date",
                "exit_date",
                "exit_cost",
                "pnl_if_held",
                "stop_effect",
                "exit_flag",
                "trigger_pnl",
                "hedge_rebalances",
                "futures_gaps",
            ):
                if k in r:
                    row[k] = r[k]
            if "hedge_path" in r:
                paths[c.entry] = r
        row["credit_net"] = (
            row["credit_gross"]
            - row["slippage_cost"]
            + (r["fut_slip"] if isinstance(r, dict) else 0.0)
        )
        row["option_pnl_before_charges"] = (
            row["credit_gross"] - row["slippage_cost"] - row["settlement_payout"]
        )
        row["total_charges"] = sum(row[k] for k in ITEMS)
        row["total_costs"] = row["slippage_cost"] + row["total_charges"]
        row["costs_pct_of_credit_gross"] = (
            100 * row["total_costs"] / abs(row["credit_gross"]) if row["credit_gross"] else np.nan
        )
        row["option_pnl_net"] = (
            row["option_pnl_before_charges"]
            - row["total_charges"]
            + row["index_leg_pnl"]
            + row["futures_hedge_pnl"]
        )
        row["total_pnl"] = row["option_pnl_net"] + row["cash_interest"]
        row["capital_end"] = capital + row["total_pnl"]
        row["return_on_capital_pct"] = 100 * row["total_pnl"] / capital
        row["option_return_on_capital_pct"] = 100 * row["option_pnl_net"] / capital
        row["return_on_margin_pct"] = (
            100 * row["option_pnl_net"] / row["margin_used"] if row["margin_used"] else np.nan
        )
        row["relative_to_tri_pct"] = (
            row["option_return_on_capital_pct"] - row["nifty_tri_return_pct"]
            if st["sizing"] == "index"
            else np.nan
        )
        if row["skipped"] == "no":
            row["win"] = "yes" if row["option_pnl_net"] > 0 else "no"
            if row["stop_triggered"] == "yes":
                row["outcome"] = "stopped"
            elif row["settlement_payout"] <= 0:
                row["outcome"] = "full profit"
            elif (
                st["sizing"] == "defined"
                and row["option_pnl_before_charges"] <= -row["max_loss_planned"] + 1
            ):
                row["outcome"] = "max loss"
            else:
                row["outcome"] = "partial loss"
        capital = row["capital_end"]
        peak = max(peak, capital)
        row["cumulative_pnl"] = capital - cfg["capital"]
        row["drawdown_from_peak_pct"] = 100 * (capital / peak - 1)
        rows.append(row)
    df = pd.DataFrame(rows)
    for col in COLS + ["trigger_pnl"]:
        if col not in df:
            df[col] = np.nan
    return df, paths


def e1f1_rows(cyc, ctx, cfg: dict, period) -> pd.DataFrame:
    """The frozen e1f1 rule's rows, as a reference."""
    pctx = {k: ctx[k] for k in ("opt", "ix", "cyc", "days", "bk")}
    cy = ctx["cyc"] if period == "validation" else ctx["cyc"][ctx["cyc"].period == "design"]
    gp = p3.gaps(pctx, cy.reset_index(drop=True), cfg)
    t = p3.simulate("e1f1", {"stop": True, "filter": True}, cyc, pctx, cfg, gp, cfg["cash_rate"])
    tr = t.skipped == ""
    cg = np.where(tr, (t.leg1_close - t.leg2_close) * t.units, 0.0) if "leg1_close" in t else 0.0
    return pd.DataFrame(
        {
            "rule": "ref_e1f1",
            "strategy": "ref_e1f1",
            "variant": "ref",
            "period": period,
            "entry_date": t.entry.dt.date,
            "next_entry": t.next_entry,
            "skipped": np.where(tr, "no", "yes"),
            "skip_reason": t.skipped,
            "capital_start": t.capital_before,
            "capital_end": t.capital_after,
            "option_pnl_net": t.net - t.interest,
            "cash_interest": t.interest,
            "total_pnl": t.net,
            "option_return_on_capital_pct": 100 * (t.net - t.interest) / t.capital_before,
            "return_on_capital_pct": 100 * t.ret,
            "stop_triggered": t.stop_triggered,
            "credit_gross": cg,
            "total_costs": t.costs.fillna(0.0),
            "net_credit_or_debit": (t.units * t.credit).fillna(0.0),
            "margin_pct_of_capital": 100 * t.margin_pct.fillna(0.0),
            "max_loss_planned": t.maxloss_plan,
            "risk_pct_of_capital": 100 * t.maxloss_plan / t.capital_before,
            "nifty_tri_return_pct": 100 * cyc.tri_ret.values,
            "stop_effect": t.get("stop_effect"),
        }
    )


def run_period(cfg: dict, ctx, period) -> tuple:
    """Run every census strategy on one period."""
    cyc = ctx["cyc"][ctx["cyc"].period == period].reset_index(drop=True)
    cyc["tri_ret"] = bt.tri_returns(cyc, ctx["ix"])
    mk = bt.vrp_table(ctx["opt"], ctx["ix"], cyc, cfg).set_index("entry")
    out, paths = [], {}
    for n, st in strategies(cfg).items():
        df, p = run(n, st, cyc, ctx, cfg, cfg["cash_rate"], period, mk)
        out.append(df)
        paths[n] = p
        logger.info(f"  {period} {n}: done")
    out.append(e1f1_rows(cyc, ctx, cfg, period))
    return pd.concat(out, ignore_index=True), cyc, paths


def reconcile(df) -> list:
    """Reconciliation checks: P&L items add up, capital chains."""
    d = df[df.rule != "ref_e1f1"]
    lhs = (
        d.credit_gross
        - d.slippage_cost
        - d.settlement_payout
        - d.total_charges
        + d.index_leg_pnl
        + d.futures_hedge_pnl
        + d.cash_interest
    )
    gaps = {
        "credit_gross - slippage - payout - charges + index leg + futures hedge + interest "
        "= total_pnl": (lhs - d.total_pnl).abs().max(),
        "capital_end = capital_start + total_pnl": (d.capital_start + d.total_pnl - d.capital_end)
        .abs()
        .max(),
        "charge items sum to total_charges": (d[ITEMS].sum(axis=1) - d.total_charges).abs().max(),
    }
    ch = 0.0
    for _, g in d.groupby(["rule", "period"]):
        ch = max(ch, np.abs(g.capital_start.values[1:] - g.capital_end.values[:-1]).max())
    gaps["capital_start = previous capital_end"] = ch
    return [f"- {k}: max gap Rs {v:.6f} -> {'PASS' if v < 1 else 'FAIL'}" for k, v in gaps.items()]


def trial_srs(cfg: dict, ctx, period, df) -> dict:
    """Monthly Sharpe of every logged trial, for the deflated Sharpe."""
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
    for n in cfg["phase2"]["variants"]:
        srs[f"phase2_{n}"] = s2.loc[n, "SR monthly"]
    for n in cfg["phase3"]["variants"]:
        srs[f"phase3_{n}"] = s3.loc[n, "SR monthly"]
    for n in strategies(cfg, refs=False):
        ro = df[df.rule == n].option_return_on_capital_pct
        srs[f"census_{n}"] = ro.mean() / ro.std()
    return srs


def summarise(df, cyc, cfg: dict, srs) -> pd.DataFrame:
    """Summary statistics of each strategy."""
    rows = []
    base = df[df.rule == "ref_base"].option_return_on_capital_pct.values / 100
    cy = cyc[["entry", "next_entry"]]
    tri = cyc.tri_ret.values
    for n, g in df.groupby("rule", sort=False):
        ro = g.option_return_on_capital_pct.values / 100
        m = bt.metrics(pd.Series(ro), cy, pd.Series(np.zeros(len(g))))
        tot = bt.metrics(
            pd.Series(g.return_on_capital_pct.values / 100), cy, bt.cash_returns(cy, cfg["rf"])
        )
        tr = g[g.skipped == "no"]
        pnl = tr.option_pnl_net / tr.capital_start
        aw = pnl[pnl > 0].mean()
        al = -pnl[pnl <= 0].mean() if (pnl <= 0).any() else 0.0
        be = al / (al + aw) if aw > 0 else np.nan
        win = (pnl > 0).mean()
        srm = ro.mean() / ro.std()
        dsr, sr0 = p2.dsr(
            srm,
            len(ro),
            pd.Series(ro).skew(),
            pd.Series(ro).kurt() + 3,
            np.var(list(srs.values()), ddof=1),
            len(srs),
        )
        diff, t = (
            p3.nw_t(ro - base, cfg["phase3"]["nw_lags"]) if n != "ref_base" else (np.nan, np.nan)
        )
        st = g.stop_triggered == "yes"
        rows.append(
            {
                "strategy": n,
                "family": g.strategy.iloc[0],
                "variant": g.variant.iloc[0],
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
                "avg credit % cap": (tr.net_credit_or_debit / tr.capital_start).mean(),
                "avg risk % cap": tr.risk_pct_of_capital.mean() / 100,
                "avg margin % cap": tr.margin_pct_of_capital.mean() / 100,
                "months traded": len(tr),
                "months skipped": int((g.skipped == "yes").sum()),
                "stops": int(st.sum()),
                "stops helped": int((g.stop_effect == "helped").sum()),
                "costs % gross credit": tr.total_costs.sum() / tr.credit_gross.abs().sum()
                if tr.credit_gross.abs().sum()
                else np.nan,
                "total CAGR (cash 6.5%)": tot["CAGR"],
                "NW t vs base": t,
                "mean diff vs base": diff,
                "corr with base": np.corrcoef(ro, base)[0, 1],
                "corr with TRI": np.corrcoef(ro, tri)[0, 1],
                "CAGR minus TRI CAGR": m["CAGR"]
                - (
                    (1 + pd.Series(tri)).prod()
                    ** (365.25 / (cy.next_entry.iloc[-1] - cy.entry.iloc[0]).days)
                    - 1
                ),
                "months": len(g),
                "SR monthly": srm,
                "DSR SR0 (monthly)": sr0,
                "DSR": dsr,
            }
        )
    return pd.DataFrame(rows)


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
    "avg risk % cap",
    "avg margin % cap",
    "costs % gross credit",
    "total CAGR (cash 6.5%)",
    "DSR",
    "CAGR minus TRI CAGR",
    "mean diff vs base",
]
MAIN = [
    "strategy",
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
    "avg risk % cap",
    "avg margin % cap",
    "months traded",
    "months skipped",
    "stops",
    "stops helped",
    "costs % gross credit",
    "total CAGR (cash 6.5%)",
    "corr with base",
    "NW t vs base",
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


def combo_inputs(df, cyc) -> tuple:
    """Correlations, crash table and co-loss pairs for combinations."""
    piv = df.pivot_table(
        index="entry_date", columns="rule", values="option_return_on_capital_pct", sort=False
    )
    piv = piv[list(dict.fromkeys(df.rule))]
    corr = piv.corr()
    tri = pd.Series(cyc.tri_ret.values * 100, index=cyc.entry.dt.date)
    worst, best = tri.nsmallest(10), tri.nlargest(10)
    crash = pd.concat(
        [
            piv.loc[worst.index].assign(case="10 worst TRI months", tri_pct=worst.values),
            piv.loc[best.index].assign(case="10 best TRI months", tri_pct=best.values),
        ]
    )
    crash.index.name = "entry_date"
    rules = list(piv.columns)
    co = [
        {"a": a, "b": b, "months both lost > 3%": int(((piv[a] < -3) & (piv[b] < -3)).sum())}
        for i, a in enumerate(rules)
        for b in rules[i + 1 :]
    ]
    return corr, crash, pd.DataFrame(co)


def data_checks(ctx, cyc) -> tuple:
    """Data checks for the census inputs."""
    nr, both = 0, 0
    for c in cyc.itertuples():
        n = p2.traded(chain(ctx, c.entry, c.contract), "PE")
        if n.empty or pd.isna(c.far):
            continue
        s0 = float(ctx["ix"].close[c.entry])
        k = n.loc[(n.strike - s0).abs().idxmin()].strike
        f = p2.traded(chain(ctx, c.entry, c.far), "PE")
        nr += 1
        both += int(k in f.strike.values)
    cov = both / len(cyc)
    gaps, rolls = [], []
    for c in cyc.itertuples():
        d = ctx["days"][(ctx["days"] >= c.entry) & (ctx["days"] <= c.expiry)]
        for x in d:
            if (c.contract, x) not in ctx["fut"].index:
                gaps.append((c.entry.date(), x.date()))
        rolls.append(c.expiry.date())
    lines = [
        f"- Far-month (S9): the near-month ATM put strike also traded in the far month on {both} "
        f"of {len(cyc)} cycles "
        f"({cov:.0%})."
        + (
            " **Fewer than 80% of cycles: S9 results rest on a fallback strike or skips in many "
            "months.**"
            if cov < 0.8
            else ""
        ),
        f"- Futures (S12): near-month NIFTY future close missing on {len(gaps)} cycle-days"
        + (
            f" ({', '.join(f'{a}: {b}' for a, b in gaps[:10])}{' ...' if len(gaps) > 10 else ''}); "
            "the last close is carried."
            if gaps
            else "."
        )
        + (
            " The hedge future is each cycle's own contract, so the roll is on each expiry day "
            f"({rolls[0]} to {rolls[-1]}, {len(rolls)} rolls)."
        ),
    ]
    return lines, cov, gaps


def reading(s, df, period) -> list:
    """Plain-language reading of the census results."""
    t = s.set_index("strategy")
    trials = t[t.trial == "yes"]
    b, e = t.loc["ref_base"], t.loc["ref_e1f1"]
    out = []
    pos = trials[trials["option CAGR"] > 0].index.tolist()
    out.append(
        "- Earn after costs (option-only CAGR above zero, i.e. beat cash): "
        f"{', '.join(pos) or 'none'}. Negative: "
        f"{', '.join(trials[trials['option CAGR'] <= 0].index) or 'none'}."
    )
    worst = trials.nsmallest(5, "CVaR99")
    out.append(
        "- Worst tails (CVaR 99%): "
        + "; ".join(
            f"{n} {v:.1%} (worst month {t.loc[n, 'worst month']:.1%})"
            for n, v in worst["CVaR99"].items()
        )
        + "."
    )
    fam = [n for n in trials.index if f"{n}_e1" in t.index]
    out.append(
        "- Stop by family (option-only Sharpe / worst month, without -> with stop): "
        + "; ".join(
            f"{n} {t.loc[n, 'option Sharpe']:.2f} / {t.loc[n, 'worst month']:.1%} -> "
            f"{t.loc[n + '_e1', 'option Sharpe']:.2f} / "
            f"{t.loc[n + '_e1', 'worst month']:.1%} ({int(t.loc[n + '_e1', 'stops'])} stops, "
            f"{int(t.loc[n + '_e1', 'stops helped'])} helped)"
            for n in fam
        )
        + "."
    )
    low = trials.nsmallest(4, "corr with base")
    out.append(
        "- Lowest correlation with the base put spread: "
        + "; ".join(
            f"{n} {v:.2f} (Sharpe {t.loc[n, 'option Sharpe']:.2f})"
            for n, v in low["corr with base"].items()
        )
        + "."
    )
    beat_b = trials[trials["option Sharpe"] > b["option Sharpe"]].index.tolist()
    beat_e = trials[trials["option Sharpe"] > e["option Sharpe"]].index.tolist()
    out.append(
        f"- Option-only Sharpe above the base put spread ({b['option Sharpe']:.2f}): "
        f"{', '.join(beat_b) or 'none'}. "
        f"Above the frozen e1f1 rule ({e['option Sharpe']:.2f}): {', '.join(beat_e) or 'none'}."
        + (" **No strategy beats the base put spread.**" if not beat_b else "")
        + (" **No strategy beats the frozen rule.**" if not beat_e else "")
    )
    for n in ("s10_covered_call", "s11_collar"):
        out.append(
            f"- {n}: CAGR {t.loc[n, 'option CAGR']:.1%}, {t.loc[n, 'CAGR minus TRI CAGR']:+.1%} a "
            f"year vs TRI buy-and-hold; worst month {t.loc[n, 'worst month']:.1%}."
        )
    return out


def low_corr_crash(s, crash) -> list:
    """Lowest-correlation strategies in the worst index months."""
    t = s.set_index("strategy")
    trials = t[t.trial == "yes"]
    low = list(trials.nsmallest(4, "corr with base").index)
    c = crash[crash.case == "10 worst TRI months"]
    return (
        "Option return (% of capital) in the 10 worst NIFTY TRI months of the period, base put "
        "spread and the four "
        "lowest-correlation strategies:\n\n"
        + c[["tri_pct", "ref_base"] + low].round(2).to_markdown()
        + "\n"
    )


def charts(s, df, short) -> None:
    """Census charts."""
    fig, ax = plt.subplots(figsize=(10, 7))
    for _, r in s.iterrows():
        ref = r.strategy.startswith("ref_")
        ax.scatter(
            r["worst month"] * 100,
            r["option Sharpe"],
            color="grey" if ref else ("tab:red" if r.strategy in short else "tab:blue"),
            s=30,
        )
        ax.annotate(
            r.strategy,
            (r["worst month"] * 100, r["option Sharpe"]),
            fontsize=7,
            xytext=(3, 3),
            textcoords="offset points",
        )
    ax.axvline(-12, color="k", ls="--", lw=0.8)
    ax.set_xlabel("worst month, % of capital (option-only)")
    ax.set_ylabel("option-only Sharpe")
    ax.set_title(
        "Design cycles: Sharpe vs worst month (red = shortlisted, grey = reference)", fontsize=10
    )
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(OUT / "sharpe_vs_worst_month_design.png", dpi=130)
    plt.close(fig)
    fig, ax = plt.subplots(figsize=(11, 5.5))
    for n in list(short) + ["ref_base", "ref_e1f1", "ref_strangle"]:
        g = df[df.rule == n]
        x = np.r_[pd.Timestamp(g.entry_date.iloc[0]), pd.to_datetime(g.next_entry).values]
        ax.plot(
            x,
            np.r_[1.0, (1 + g.option_return_on_capital_pct / 100).cumprod().values],
            label=n,
            ls="--" if n.startswith("ref_") else "-",
        )
    g = df[df.rule == "ref_base"]
    x = np.r_[pd.Timestamp(g.entry_date.iloc[0]), pd.to_datetime(g.next_entry).values]
    ax.plot(
        x,
        np.r_[1.0, (1 + g.nifty_tri_return_pct / 100).cumprod().values],
        color="grey",
        label="NIFTY 50 TRI",
    )
    ax.set_yscale("log")
    ax.set_title(
        "Design cycles: option-only P&L (no cash interest), shortlist and references, log scale",
        fontsize=10,
    )
    ax.legend(fontsize=8)
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(OUT / "equity_design.png", dpi=130)
    plt.close(fig)


def shortlist(s, cfg: dict) -> tuple:
    """Shortlist rule applied to the design results."""
    t = s[s.trial == "yes"]
    b = s.set_index("strategy").loc["ref_base"]
    ok = t[
        (t["option Sharpe"] > b["option Sharpe"])
        & (t["worst month"] >= -0.12)
        & (t["break-even margin"] >= 0.03)
    ]
    lines = [
        "# Census shortlist (design cycles only; written before validation)\n",
        "Rule (pre-registered): option-only Sharpe above the base put spread's "
        f"({b['option Sharpe']:.2f}), worst month "
        "no worse than -12% of capital, break-even margin at least 3 points. Candidates: the 20 "
        "census trials.\n",
        fmt(t, ["strategy", "option Sharpe", "worst month", "break-even margin", "option CAGR"]),
        "",
        f"**Shortlist ({len(ok)}): {', '.join(ok.strategy) if len(ok) else 'none'}**\n",
    ]
    return list(ok.strategy), "\n".join(lines)


def write_csv(df, path) -> None:
    """Write the monthly census file."""
    out = df.drop(columns=["next_entry", "trigger_pnl"], errors="ignore")
    out = out[[c for c in COLS if c in out]]
    num = out.select_dtypes("number").columns
    out[num] = out[num].round(4)
    out.to_csv(path, index=False)


def outputs(df, cyc, cfg: dict, ctx, period, dc) -> tuple:
    """Report sections and files for one period."""
    rec = reconcile(df)
    srs = trial_srs(cfg, ctx, period, df)
    s = summarise(df, cyc, cfg, srs)
    s.to_csv(OUT / f"summary_{period}.csv", index=False)
    return s, srs, rec


def design(cfg: dict) -> None:
    """Census on design data."""
    OUT.mkdir(parents=True, exist_ok=True)
    if (OUT / "validation_runs.log").exists():
        logger.info("Validation already run; design results are frozen.")
        return
    ctx = load(cfg)
    des = ctx["cyc"][ctx["cyc"].period == "design"].reset_index(drop=True)
    dc, cov, gaps = data_checks(ctx, des)
    logger.info("\n".join(dc))
    df, cyc, paths = run_period(cfg, ctx, "design")
    write_csv(df, OUT / "monthly_pnl_census.csv")
    s, srs, rec = outputs(df, cyc, cfg, ctx, "design", dc)
    corr, crash, co = combo_inputs(df, cyc)
    corr.round(3).to_csv(OUT / "correlation_design.csv")
    crash.round(3).to_csv(OUT / "crash_table.csv")
    co.to_csv(OUT / "co_loss_pairs.csv", index=False)
    short, txt = shortlist(s, cfg)
    (OUT / "shortlist.md").write_text(txt)
    charts(s, df, short)
    notes = df[(df.sizing_note.fillna("") != "")].groupby(["rule", "sizing_note"]).size()
    md = (
        [
            "# Strategy census report\n",
            f"Design: {len(cyc)} cycles, entries {cyc.entry.min():%Y-%m-%d} to "
            f"{cyc.entry.max():%Y-%m-%d}. One fixed version per "
            "family (see `preregistration.md`); headline = option-only return (no cash interest; "
            "S10/S11 include the index leg, "
            "S12 the futures hedge), Sharpe without risk-free deduction. ref_* are references, not "
            "trials.\n",
            "## Data checks (design)\n",
        ]
        + dc
        + [
            "",
            "## Design results\n",
            fmt(s, MAIN),
            "",
            "Avg risk: defined-risk = max loss; others = loss at the worse of -25% / +20% at "
            "settlement (S10/S11 incl. the "
            "index leg; S12 not computed). Costs as % of the absolute gross premium.\n",
            "Sizing notes (cycles): "
            + ("; ".join(f"{a}: {b} ({n})" for (a, b), n in notes.items()) or "none")
            + "\n",
            "## Reading (design)\n",
        ]
        + reading(s, df, "design")
        + [
            "",
            "## Crash months and correlation (combination inputs)\n",
            low_corr_crash(s, crash),
            "Full tables: `correlation_design.csv`, `crash_table.csv`, `co_loss_pairs.csv`.\n",
            "## Deflated Sharpe ratio (design, 32 cumulative trials)\n",
            "Inputs: each series' monthly Sharpe, months, skewness, kurtosis; variance of monthly "
            f"Sharpe across the {len(srs)} "
            "trials (Phase 1: 3, Phase 2: 6, Phase 3: 3, census: 20) = "
            f"{np.var(list(srs.values()), ddof=1):.4f}.\n",
            fmt(s, ["strategy", "SR monthly", "DSR SR0 (monthly)", "months", "DSR"]),
            "",
            txt.replace("# Census shortlist", "## Shortlist"),
            "## Checks\n",
        ]
        + rec
    )
    (OUT / "census_report.md").write_text("\n".join(md) + "\n")
    logger.info("\n".join(md))


def validate(cfg: dict) -> None:
    """Census validation, run once."""
    log = OUT / "validation_runs.log"
    if log.exists() and log.read_text().strip():
        logger.info("Validation already run once; not running again. Log:\n" + log.read_text())
        return
    assert (OUT / "shortlist.md").exists()
    short = (
        (OUT / "shortlist.md").read_text().split("**Shortlist")[1].split(": ", 1)[1].split("**")[0]
    )
    short = [] if short == "none" else short.split(", ")
    ctx = load(cfg)
    df, cyc, paths = run_period(cfg, ctx, "validation")
    s, srs, rec = outputs(df, cyc, cfg, ctx, "validation", None)
    s["shortlisted"] = np.where(s.strategy.isin(short), "yes", "")
    s.to_csv(OUT / "summary_validation.csv", index=False)
    dv = pd.read_csv(OUT / "monthly_pnl_census.csv")
    write_csv(df, OUT / "_v.csv")
    both = pd.concat([dv, pd.read_csv(OUT / "_v.csv")], ignore_index=True)
    (OUT / "_v.csv").unlink()
    both.to_csv(OUT / "monthly_pnl_census.csv", index=False)
    vs = s.copy()
    vs.insert(1, "shortlisted", vs.pop("shortlisted"))
    t = vs.set_index("strategy")
    dsg = pd.read_csv(OUT / "summary_design.csv").set_index("strategy")
    md = [
        "\n## Validation (run 1)\n",
        "**Validation; aggregate results for this period were seen in Phase 1, so not a clean "
        f"test.** {len(cyc)} cycles, "
        f"entries {cyc.entry.min():%Y-%m-%d} to {cyc.entry.max():%Y-%m-%d}. Shortlist (from "
        f"design): {', '.join(short) or 'none'}.\n",
        fmt(vs, ["strategy", "shortlisted"] + MAIN[1:]),
        "",
        "Reading (validation):\n",
    ] + reading(s, df, "validation")
    for n in short:
        md.append(
            f"- Shortlisted {n}: Sharpe {dsg.loc[n, 'option Sharpe']:.2f} on design -> "
            f"{t.loc[n, 'option Sharpe']:.2f} on "
            f"validation (base {t.loc['ref_base', 'option Sharpe']:.2f}, e1f1 "
            f"{t.loc['ref_e1f1', 'option Sharpe']:.2f}); "
            f"worst month {t.loc[n, 'worst month']:.1%}; DSR {t.loc[n, 'DSR']:.2f}."
        )
    md += ["", "Validation checks:\n"] + rec
    with open(OUT / "census_report.md", "a") as f:
        f.write("\n".join(md) + "\n")
    with open(log, "a") as f:
        f.write(
            f"run 1 at {datetime.now():%Y-%m-%d %H:%M:%S}, {len(cyc)} cycles "
            f"{cyc.entry.min():%Y-%m-%d} to "
            f"{cyc.expiry.max():%Y-%m-%d}, shortlist {', '.join(short) or 'none'}\n"
            + fmt(
                vs,
                [
                    "strategy",
                    "shortlisted",
                    "option CAGR",
                    "option Sharpe",
                    "worst month",
                    "CVaR99",
                    "DSR",
                ],
            )
            + "\n"
        )
    logger.info("\n".join(md))


def hand_iv(price, s, k, t, r, q, o) -> float:
    """Implied volatility by bisection, written out by hand for the checks."""
    lo, hi = 1e-4, 5.0
    for _ in range(200):
        v = (lo + hi) / 2
        a = (np.log(s / k) + (r - q + v * v / 2) * t) / (v * np.sqrt(t))
        b = a - v * np.sqrt(t)
        p = (
            (s * np.exp(-q * t) * p2.ncdf(a) - k * np.exp(-r * t) * p2.ncdf(b))
            if o == "C"
            else (k * np.exp(-r * t) * p2.ncdf(-b) - s * np.exp(-q * t) * p2.ncdf(-a))
        )
        lo, hi = (v, hi) if p < price else (lo, v)
    a = (np.log(s / k) + (r - q + v * v / 2) * t) / (v * np.sqrt(t))
    return np.exp(-q * t) * p2.ncdf(a) - (0 if o == "C" else np.exp(-q * t))


def check(cfg: dict) -> None:
    """Census checks."""
    out = ["# Census checks\n"]
    ctx = load(cfg)
    p = cfg["phase2"]
    vend = pd.Timestamp(p["validation_end"])
    hold = data.cycles(*data.load())
    assert (
        not ctx["cyc"].entry.isin(hold[hold.expiry > vend].entry).any()
        and ctx["opt"].date.max() <= vend
    )
    assert ctx["fut"].index.get_level_values("date").max() <= vend
    runs = (
        (OUT / "validation_runs.log").read_text().count("run ")
        if (OUT / "validation_runs.log").exists()
        else 0
    )
    assert runs <= 1
    des = ctx["cyc"][ctx["cyc"].period == "design"].reset_index(drop=True)
    des["tri_ret"] = bt.tri_returns(des, ctx["ix"])
    mk = bt.vrp_table(ctx["opt"], ctx["ix"], des, cfg).set_index("entry")
    out.append(
        f"- split: design {len(des)} cycles; no holdout cycle, option or futures data after "
        f"{vend:%Y-%m-%d}; "
        f"validation runs logged: {runs}."
    )
    rng = np.random.default_rng(5)
    allrows = []
    for n, st in strategies(cfg).items():
        df, paths = run(n, st, des, ctx, cfg, cfg["cash_rate"], "design", mk)
        allrows.append(df)
        done = df[df.skipped == "no"]
        for i in rng.choice(done.index, 2, replace=False):
            r = done.loc[i]
            if r.stop_triggered == "yes":
                continue
            hand = 0.0
            for part in r.legs.split("; "):
                sq, o, k, _ = part.split()
                side, q, k = (-1 if sq[0] == "S" else 1), int(sq[1:]), float(k)
                if st["sizing"] == "debit" and side > 0:
                    c = des[des.entry == pd.Timestamp(r.entry_date)].iloc[0]
                    x = ctx["opt"][
                        (ctx["opt"].expiry == c.far)
                        & (ctx["opt"].strike == k)
                        & (ctx["opt"].opt == "PE")
                        & (ctx["opt"].close > 0)
                        & (ctx["opt"].date <= c.expiry)
                    ].sort_values("date")
                    hand += float(x.close.iloc[-1])
                    continue
                hand += (
                    side
                    * q
                    * (
                        max(0.0, k - r.index_at_expiry)
                        if o == "P"
                        else max(0.0, r.index_at_expiry - k)
                    )
                )
            code = -r.settlement_payout / r.units
            assert abs(code - hand) < 1e-6, (n, r.entry_date, code, hand)
        if st["sizing"] == "defined":
            plan = done.max_loss_planned / done.capital_start
            assert (plan <= cfg["max_loss_pct"] + 1e-9).all()
            assert (
                done.option_pnl_before_charges / done.capital_start >= -cfg["max_loss_pct"] - 1e-9
            ).all() or st["stop"]
        if st["sizing"].startswith("stress") and not st["stop"]:
            capped = done.sizing_note.fillna("") != ""
            ok = (done.risk_pct_of_capital[~capped] <= 100 * cfg["max_loss_pct"] + 1e-6).all()
            assert ok
        if st["sizing"] in ("notional", "index"):
            free = done.sizing_note.fillna("") == ""
            assert (
                np.abs(done.units * done.index_at_entry / done.capital_start - 1)[free] < 1e-9
            ).all()
        assert (done.margin_used <= done.capital_start + 1e-6).all(), n
        out.append(
            f"- {n}: payoff by hand OK for 2 cycles; max margin "
            f"{done.margin_pct_of_capital.max():.1f}% of capital; "
            "worst option loss before charges "
            f"{(-done.option_pnl_before_charges / done.capital_start).max():.2%}"
        )
        if st["sizing"] == "hedged":
            c = des[des.entry == pd.Timestamp(rng.choice(done.entry_date))].iloc[0]
            rr = paths[c.entry]
            legs, u = rr["legs_obj"], rr["units"]
            days, hs, fs = rr["hedge_path"]
            hand_h, hand_f, prev = [], [], {}
            for j, d in enumerate(days[:-1]):
                sdl = 0.0
                for leg in legs:
                    x = ctx["opt"][
                        (ctx["opt"].date == d)
                        & (ctx["opt"].expiry == c.contract)
                        & (ctx["opt"].strike == leg["k"])
                        & (ctx["opt"].opt == ("CE" if leg["opt"] == "C" else "PE"))
                        & (ctx["opt"].close > 0)
                    ].close
                    cl = leg["close"] if j == 0 else (float(x.iloc[0]) if len(x) else None)
                    if cl is not None:
                        prev[leg["opt"]] = hand_iv(
                            cl,
                            float(ctx["ix"].close[d]),
                            leg["k"],
                            (c.expiry - d).days / 365,
                            cfg["rf"],
                            cfg["phase2"]["div_yield"],
                            leg["opt"],
                        )
                    sdl += prev[leg["opt"]]
                hand_h.append(u * sdl)
                hand_f.append(float(ctx["fut"].loc[(c.contract, d)]))
            hp = float(np.sum(np.array(hand_h) * np.diff(np.r_[hand_f, c.settle])))
            assert np.allclose(hand_h, hs, atol=1e-4) and abs(hp - rr["futures_hedge_pnl"]) < 1e-2
            out.append(
                f"- s12 hedge {c.entry:%Y-%m-%d}: {len(hand_h)} daily deltas recomputed by hand "
                "(IV by bisection, "
                f"Black-Scholes delta) match; futures P&L by hand Rs {hp:,.2f} = code Rs "
                f"{rr['futures_hedge_pnl']:,.2f}; "
                f"each hedge uses that day's close only"
            )
    out.append(
        "- no look-ahead: legs, IV and sizing use the entry-day chain (chain() asserts date == "
        "entry) and the entry-day "
        "index close; hedge deltas use each day's own closes; settlement only for payoff."
    )
    df = pd.concat(allrows, ignore_index=True)
    out += reconcile(df)
    ref = pd.read_csv("results/phase2/monthly_pnl_phase2.csv")
    ref = ref[(ref.rule == "ref_put_spread_fallback") & (ref.period == "design")]
    gap = np.abs(df[df.rule == "ref_base"].capital_end.values - ref.capital_end.values).max()
    assert gap < 0.01
    out.append(
        "- base put spread (census engine) reproduces Phase 2 ref_put_spread_fallback on design: "
        f"max capital gap Rs {gap:.4f}"
    )
    e = e1f1_rows(des, ctx, cfg, "design")
    p3r = pd.read_csv("results/phase3/monthly_pnl_phase3.csv")
    p3r = p3r[(p3r.rule == "e1f1") & (p3r.period == "design")]
    gap = np.abs(e.capital_end.values - p3r.capital_end.values).max()
    assert gap < 0.01
    out.append(f"- frozen e1f1 reproduces Phase 3 on design: max capital gap Rs {gap:.4f}")
    (OUT / "checks.md").write_text("\n".join(out) + "\n")
    logger.info("\n".join(out))
