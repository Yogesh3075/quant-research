from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from optsell import data
from optsell.pricing import iv

matplotlib.use("Agg")
logger = logging.getLogger(__name__)

RES = Path("results")
RULES = ["put_spread", "iron_condor", "strangle"]


def rate_on(table, d):
    """Value of a dated step table (e.g. STT rate) in force on day d."""
    r = table[0][1]
    for start, v in table:
        if d >= pd.Timestamp(start):
            r = v
    return r


def load_all(cfg: dict) -> tuple:
    """Option chains, index and monthly cycles for the Phase 1 backtest."""
    fo, ix = data.load()
    opt = fo[fo.instr == "OPTIDX"][["date", "expiry", "strike", "opt", "close", "volume", "lot"]]
    c = data.cycles(fo, ix)
    assert c.settle.notna().all(), c[c.settle.isna()]
    n = cfg["holdout_cycles"]
    c["period"] = ["dev"] * (len(c) - n) + ["holdout"] * n
    return opt, ix, c


def chain(opt, entry, expiry) -> pd.DataFrame:
    """The option chain for one entry day and expiry."""
    ch = opt[(opt.date == entry) & (opt.expiry == expiry)]
    assert (ch.date <= entry).all()
    return ch


def pick(ch, opt, target, band):
    """Nearest traded strike to the target, else the next one further out of the money."""
    c = ch[ch.opt == ("PE" if opt == "P" else "CE")].sort_values("strike").reset_index(drop=True)
    if c.empty:
        return None
    i = int((c.strike - target).abs().idxmin())
    step = -1 if opt == "P" else 1
    while 0 <= i < len(c):
        r = c.iloc[i]
        if abs(r.strike - target) > band * target:
            return None
        if r.close > 0 and r.volume > 0:
            return r
        i += step
    return None


def intrinsic(opt, k, s) -> float:
    """Intrinsic value of a put or call at settlement price s."""
    return max(0.0, k - s) if opt == "P" else max(0.0, s - k)


def legs_for(rule, ch, s0, cfg: dict) -> tuple:
    """Legs of a Phase 1 rule (put spread, iron condor, strangle) on the entry day."""
    legs = []
    for opt, side, m in cfg["rules"][rule]:
        r = pick(ch, opt, m * s0, cfg["strike_band"])
        if r is None:
            return None, f"no valid {opt} strike within {cfg['strike_band']:.0%} of {m:.2f} x S0"
        slip = max(cfg["costs"]["slip_min"], cfg["costs"]["slip_pct"] * r.close)
        px = max(0.0, r.close - slip) if side < 0 else r.close + slip
        legs.append(
            {
                "opt": opt,
                "side": side,
                "k": float(r.strike),
                "close": float(r.close),
                "px": px,
                "slip": px - r.close if side > 0 else r.close - px,
                "lot": r.lot,
            }
        )
    return legs, ""


def trade(
    rule, legs, s0, settle, capital, days_held, entry, cfg: dict, cash_rate, lot_round=False
) -> dict | None:
    """One cycle: units, credit, slippage, charges, settlement and P&L of a rule."""
    cc = cfg["costs"]
    credit = sum(-leg["side"] * leg["px"] for leg in legs)
    if rule == "strangle":
        units = cfg["strangle_notional"] * capital / s0
    else:
        puts = [leg["k"] for leg in legs if leg["opt"] == "P"]
        calls = [leg["k"] for leg in legs if leg["opt"] == "C"]
        width = max(max(puts) - min(puts), (max(calls) - min(calls)) if calls else 0)
        maxloss = width - credit
        if maxloss <= 0:
            return None
        units = cfg["max_loss_pct"] * capital / maxloss
    if lot_round:
        lot = legs[0]["lot"]
        if not lot > 0:
            return None
        units = np.floor(units / lot) * lot
    margin = 2 * cfg["strangle_margin"] * units * s0 if rule == "strangle" else units * maxloss
    payoff = sum(leg["side"] * intrinsic(leg["opt"], leg["k"], settle) for leg in legs)
    sell_prem = sum(leg["px"] * units for leg in legs if leg["side"] < 0)
    buy_prem = sum(leg["px"] * units for leg in legs if leg["side"] > 0)
    turnover = sell_prem + buy_prem
    brokerage = cc["brokerage"] * len(legs)
    exch = rate_on(cc["exch"], entry) * turnover
    sebi = cc["sebi"] * turnover
    charges = (
        rate_on(cc["stt_sell"], entry) * sell_prem
        + sum(
            cc["stt_itm"] * intrinsic(leg["opt"], leg["k"], settle) * units
            for leg in legs
            if leg["side"] > 0
        )
        + brokerage
        + exch
        + sebi
        + cc["stamp"] * buy_prem
        + cc["gst"] * (brokerage + exch + sebi)
    )
    slippage = sum(leg["slip"] * units for leg in legs)
    interest = cash_rate * max(0.0, capital - margin) * days_held / 365
    gross = units * (credit + payoff) + slippage
    net = units * (credit + payoff) - charges + interest
    return {
        "units": units,
        "credit": credit,
        "payoff_unit": payoff,
        "margin": margin,
        "margin_pct": margin / capital,
        "gross": gross,
        "slippage": slippage,
        "charges": charges,
        "costs": slippage + charges,
        "interest": interest,
        "net": net,
        "maxloss_plan": None if rule == "strangle" else units * maxloss,
    }


def simulate(rule, cyc, opt, ix, cfg: dict, cash_rate, lot_round=False) -> pd.DataFrame:
    """Run a rule over all cycles, compounding capital."""
    capital = cfg["capital"]
    rows = []
    for _, c in cyc.iterrows():
        s0 = float(ix.close[c.entry])
        row = {
            "entry": c.entry,
            "expiry": c.expiry,
            "next_entry": c.next_entry,
            "S0": s0,
            "settle": c.settle,
            "capital_before": capital,
        }
        days_held = (c.next_entry - c.entry).days
        legs, why = legs_for(rule, chain(opt, c.entry, c.contract), s0, cfg)
        t = None
        if legs is not None and capital > 0:
            t = trade(
                rule, legs, s0, c.settle, capital, days_held, c.entry, cfg, cash_rate, lot_round
            )
            if t is None:
                why = "no lot size in data" if lot_round else "max loss not positive"
        if t is None:
            interest = cash_rate * max(capital, 0) * days_held / 365
            row.update(
                {"skipped": why or "capital exhausted", "net": interest, "interest": interest}
            )
        else:
            for j, leg in enumerate(legs):
                row[f"leg{j + 1}"] = (
                    f"{'S' if leg['side'] < 0 else 'B'} {leg['opt']} {leg['k']:.0f}"
                )
                row[f"leg{j + 1}_close"] = leg["close"]
                row[f"leg{j + 1}_px"] = round(leg["px"], 2)
            row.update(t)
            row["settle_value"] = t["units"] * t["payoff_unit"]
            row["skipped"] = ""
        capital = capital + row["net"]
        row["capital_after"] = capital
        row["ret"] = row["net"] / row["capital_before"] if row["capital_before"] > 0 else 0.0
        rows.append(row)
    return pd.DataFrame(rows)


def cash_returns(cyc, rate):
    """Return on idle cash over each cycle at an annual rate."""
    return (1 + rate) ** ((cyc.next_entry - cyc.entry).dt.days / 365) - 1


def tri_returns(cyc, ix):
    """NIFTY 50 TRI return over each cycle (entry to next entry)."""
    tri = ix.tri.ffill()
    return pd.Series(
        tri.reindex(cyc.next_entry).values / tri.reindex(cyc.entry).values - 1, index=cyc.index
    )


def metrics(r, cyc, rf_r) -> dict:
    """CAGR, vol, Sharpe, Sortino, drawdown, tail and win statistics of cycle returns."""
    r = pd.Series(r.values, index=cyc.next_entry.values)
    rf_r = pd.Series(rf_r.values, index=r.index)
    eq = (1 + r).cumprod()
    years = (cyc.next_entry.iloc[-1] - cyc.entry.iloc[0]).days / 365.25
    ex = r - rf_r
    full = pd.concat([pd.Series([1.0], index=[cyc.entry.iloc[0]]), eq])
    dd = full / full.cummax() - 1
    trough = dd.idxmin()
    peak = full[:trough].idxmax()
    three = (1 + r).rolling(3).apply(np.prod, raw=True) - 1
    srt = np.sort(r.values)

    def cvar(q):
        return srt[: max(1, int(np.ceil(q * len(srt))))].mean()

    down = np.sqrt(np.mean(np.minimum(ex.values, 0) ** 2))
    wins, losses = r[r > 0], r[r < 0]
    return {
        "CAGR": eq.iloc[-1] ** (1 / years) - 1 if eq.iloc[-1] > 0 else -1.0,
        "Vol": r.std() * np.sqrt(12),
        "Sharpe": ex.mean() / r.std() * np.sqrt(12),
        "Sortino": ex.mean() / down * np.sqrt(12) if down > 0 else np.nan,
        "MaxDD": dd.min(),
        "DD peak": f"{peak:%Y-%m-%d}",
        "DD trough": f"{trough:%Y-%m-%d}",
        "Worst month": r.min(),
        "Worst 3m": three.min(),
        "Skew": r.skew(),
        "Win rate": (r > 0).mean(),
        "Avg win": wins.mean() if len(wins) else np.nan,
        "Avg loss": losses.mean() if len(losses) else np.nan,
        "CVaR95": cvar(0.05),
        "CVaR99": cvar(0.01),
    }


def summarise(trades, cyc, ix, cfg: dict, cash_rate) -> pd.DataFrame:
    """Summary statistics of every rule and the benchmarks."""
    rf_r = cash_returns(cyc, cfg["rf"])
    out = {}
    for rule, t in trades.items():
        m = metrics(t.ret, cyc, rf_r)
        done = t[t.skipped == ""]
        gp = done.gross.sum()
        m.update(
            {
                "Skipped": int((t.skipped != "").sum()),
                "Costs Rs": done.costs.sum(),
                "Costs/gross profit": done.costs.sum() / gp if gp > 0 else np.nan,
                "Avg margin": done.margin_pct.mean(),
                "Max margin": done.margin_pct.max(),
            }
        )
        out[rule] = m
    out["TRI"] = metrics(tri_returns(cyc, ix), cyc, rf_r)
    out[f"Cash {cfg['cash_rate']:.1%}"] = metrics(cash_returns(cyc, cfg["cash_rate"]), cyc, rf_r)
    return pd.DataFrame(out).T


def fmt(df) -> pd.DataFrame:
    """Format a summary table for Markdown."""
    d = df.copy()
    pct = [
        "CAGR",
        "Vol",
        "MaxDD",
        "Worst month",
        "Worst 3m",
        "Win rate",
        "Avg win",
        "Avg loss",
        "CVaR95",
        "CVaR99",
        "Costs/gross profit",
        "Avg margin",
        "Max margin",
    ]
    for c in d.columns:
        if c in pct:
            d[c] = d[c].map(lambda v: "" if pd.isna(v) else f"{v:.1%}")
        elif c in ("Sharpe", "Sortino", "Skew"):
            d[c] = d[c].map(lambda v: "" if pd.isna(v) else f"{v:.2f}")
        elif c == "Costs Rs":
            d[c] = d[c].map(lambda v: "" if pd.isna(v) else f"{v:,.0f}")
        elif c == "Skipped":
            d[c] = d[c].map(lambda v: "" if pd.isna(v) else f"{int(v)}")
    return d.to_markdown()


def stress(trades, cyc, ix, cfg: dict) -> pd.DataFrame:
    """Each rule's result in the named stress months."""
    rows = []
    tri = tri_returns(cyc, ix)
    for name, (a, b) in cfg["stress"].items():
        a, b = pd.Timestamp(a), pd.Timestamp(b)
        hit = cyc[(cyc.entry <= b) & (cyc.expiry >= a)]
        for i, c in hit.iterrows():
            row = {
                "event": name,
                "entry": f"{c.entry:%Y-%m-%d}",
                "expiry": f"{c.expiry:%Y-%m-%d}",
                "index move": f"{c.settle / ix.close[c.entry] - 1:+.1%}",
                "TRI": f"{tri[i]:+.1%}",
            }
            for rule, t in trades.items():
                row[rule] = f"{t.ret[i]:+.1%}"
            rows.append(row)
    return pd.DataFrame(rows)


def worst(trades, cyc, ix) -> pd.DataFrame:
    """The worst cycles of each rule, with the index move."""
    out = []
    for rule, t in trades.items():
        w = t.nsmallest(10, "ret")
        d = pd.DataFrame(
            {
                "rule": rule,
                "entry": w.entry.dt.strftime("%Y-%m-%d"),
                "expiry": w.expiry.dt.strftime("%Y-%m-%d"),
                "return": w.ret.map("{:+.1%}".format),
                "index move": (w.settle / w.S0 - 1).map("{:+.1%}".format),
            }
        )
        out.append(d)
    return pd.concat(out)


def run_period(cfg: dict, period, opt, ix, cyc) -> tuple:
    """Run all rules on one period (development or holdout)."""
    cyc = cyc[cyc.period == period].reset_index(drop=True)
    sfx = "" if period == "dev" else "_holdout"
    trades = {r: simulate(r, cyc, opt, ix, cfg, cfg["cash_rate"]) for r in RULES}
    for r, t in trades.items():
        t.to_csv(RES / f"trades_{r}{sfx}.csv", index=False)
    main = summarise(trades, cyc, ix, cfg, cfg["cash_rate"])
    zero = summarise({r: simulate(r, cyc, opt, ix, cfg, 0.0) for r in RULES}, cyc, ix, cfg, 0.0)
    lots = {r: simulate(r, cyc, opt, ix, cfg, cfg["cash_rate"], lot_round=True) for r in RULES}
    return cyc, trades, main, zero, lots


def lot_note(lots, cyc, ix, cfg: dict) -> str:
    """Note on whole-lot sizing (lot sizes exist in the data only from July 2024)."""
    nolot = int((lots[RULES[0]].skipped == "no lot size in data").sum())
    if nolot:
        return (
            f"Lot sizes by date are missing for {nolot} of {len(cyc)} cycles (the bhavcopy has a "
            "lot column only "
            "in the UDiFF files from July 2024), so the whole-lot version is skipped for this "
            "period.\n"
        )
    rows = []
    for r, t in lots.items():
        done = t[t.skipped == ""]
        zero_lots = int((done.units == 0).sum())
        m = metrics(t.ret, cyc, cash_returns(cyc, cfg["rf"]))
        rows.append(
            {
                "rule": r,
                "CAGR": f"{m['CAGR']:.1%}",
                "Sharpe": f"{m['Sharpe']:.2f}",
                "MaxDD": f"{m['MaxDD']:.1%}",
                "Worst month": f"{m['Worst month']:.1%}",
                "months traded": len(done) - zero_lots,
                "months with 0 lots": zero_lots,
                "no lot data": int((t.skipped == "no lot size in data").sum()),
            }
        )
    return (
        "Whole lots (units rounded down to the NSE lot size on the entry date, from the UDiFF lot "
        "column):\n\n" + pd.DataFrame(rows).to_markdown(index=False) + "\n"
    )


def charts(trades, cyc, ix, sfx="") -> None:
    """Equity curves and monthly return histograms."""
    fig, ax = plt.subplots(figsize=(10, 5.5))
    x = pd.concat([pd.Series([cyc.entry.iloc[0]]), cyc.next_entry]).values
    for r, t in trades.items():
        ax.plot(x, np.r_[1.0, (1 + t.ret).cumprod().values], label=r)
    ax.plot(
        x,
        np.r_[1.0, (1 + tri_returns(cyc, ix)).cumprod().values],
        label="NIFTY 50 TRI",
        color="grey",
    )
    ax.set_yscale("log")
    ax.set_title("Growth of 1 (log scale)")
    ax.legend()
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(RES / f"equity{sfx}.png", dpi=130)
    plt.close(fig)

    fig, axes = plt.subplots(1, 3, figsize=(13, 4), sharey=True)
    for ax, (r, t) in zip(axes, trades.items(), strict=False):
        ax.hist(t.ret * 100, bins=40, color="tab:blue")
        ax.axvline(0, color="k", lw=0.8)
        ax.set_title(f"{r}: min {t.ret.min():.1%}")
        ax.set_xlabel("monthly return, %")
    axes[0].set_ylabel("months")
    fig.tight_layout()
    fig.savefig(RES / f"monthly_returns_hist{sfx}.png", dpi=130)
    plt.close(fig)


def report(cfg: dict, period, cyc, trades, main, zero, lots, ix) -> str:
    """Markdown report of one period."""
    st = stress(trades, cyc, ix, cfg)
    lines = [
        f"# Backtest: {period} ({len(cyc)} cycles, {cyc.entry.iloc[0]:%Y-%m-%d} to "
        f"{cyc.expiry.iloc[-1]:%Y-%m-%d})\n",
        f"## Main result (fractional units, cash at {cfg['cash_rate']:.1%})\n",
        fmt(main),
        "",
        "Sharpe and Sortino are on monthly returns in excess of 6.5% cash, annualised by sqrt(12). "
        "Max drawdown on month-end capital. CVaR = average of the worst 5% / 1% of months.\n",
        "## Cash on idle capital at 0%\n",
        fmt(zero[["CAGR", "Vol", "Sharpe", "MaxDD", "Worst month", "CVaR99"]]),
        "",
        "## Whole lots\n",
        lot_note(lots, cyc, ix, cfg),
        "## Stress months\n",
        st.to_markdown(index=False) if len(st) else "No stress month in this period.",
        "",
        "## 10 worst months per rule\n",
        worst(trades, cyc, ix).to_markdown(index=False),
        "",
    ]
    skipped = pd.concat(
        [t.loc[t.skipped != "", ["entry", "skipped"]].assign(rule=r) for r, t in trades.items()]
    )
    skipped["entry"] = skipped.entry.dt.strftime("%Y-%m-%d")
    lines += [
        "## Skipped months\n",
        skipped.to_markdown(index=False) if len(skipped) else "None.",
        "",
    ]
    return "\n".join(lines)


def run(cfg: dict) -> None:
    """Phase 1 development backtest: report, trades and charts."""
    RES.mkdir(exist_ok=True)
    opt, ix, cyc = load_all(cfg)
    c, trades, main, zero, lots = run_period(cfg, "dev", opt, ix, cyc)
    charts(trades, c, ix)
    (RES / "backtest_dev.md").write_text(
        report(cfg, "development", c, trades, main, zero, lots, ix)
    )
    logger.info(
        fmt(
            main[
                [
                    "CAGR",
                    "Sharpe",
                    "MaxDD",
                    "Worst month",
                    "CVaR99",
                    "Win rate",
                    "Costs/gross profit",
                    "Skipped",
                ]
            ]
        )
    )
    logger.info("wrote results/backtest_dev.md")


def holdout(cfg: dict) -> None:
    """Score the Phase 1 holdout once and log it; refuses a second run."""
    log = RES / "holdout_runs.log"
    if log.exists() and log.read_text().strip():
        logger.info("Holdout already scored once; not running again. Log:\n" + log.read_text())
        return
    opt, ix, cyc = load_all(cfg)
    c, trades, main, zero, lots = run_period(cfg, "holdout", opt, ix, cyc)
    charts(trades, c, ix, "_holdout")
    v = vrp_table(opt, ix, c, cfg)
    text = report(cfg, "holdout", c, trades, main, zero, lots, ix)
    text += (
        f"\n## IV minus RV in holdout\nMean ATM IV - RV {v.vrp.mean():+.2%} (vol points), "
        f"IV above RV in {(v.vrp > 0).mean():.0%} of {v.vrp.notna().sum()} months.\n"
    )
    (RES / "backtest_holdout.md").write_text(text)
    short = main[["CAGR", "Sharpe", "MaxDD", "Worst month", "CVaR99", "Win rate"]]
    with open(log, "a") as f:
        f.write(
            f"run 1 at {datetime.now():%Y-%m-%d %H:%M:%S}, cycles {c.entry.iloc[0]:%Y-%m-%d} to "
            f"{c.expiry.iloc[-1]:%Y-%m-%d}\n{fmt(short)}\n"
        )
    logger.info(fmt(short))
    logger.info("wrote results/backtest_holdout.md and results/holdout_runs.log")


def realised_vol(ix, a, b) -> float:
    """Annualised realised volatility of the index between two dates."""
    s = ix.close.dropna()
    s = s[(s.index >= a) & (s.index <= b)]
    return np.log(s).diff().dropna().std() * np.sqrt(252)


def vrp_table(opt, ix, cyc, cfg: dict) -> pd.DataFrame:
    """ATM implied vol vs the realised vol that followed, per cycle."""
    rows = []
    for _, c in cyc.iterrows():
        s0 = float(ix.close[c.entry])
        ch = chain(opt, c.entry, c.contract)
        t = (c.expiry - c.entry).days / 365
        ivs = {}
        for o, code in (("C", "CE"), ("P", "PE")):
            x = ch[(ch.opt == code) & (ch.close > 0)]
            if x.empty:
                ivs[o] = np.nan
                continue
            r = x.iloc[(x.strike - s0).abs().argmin()]
            ivs[o] = iv(r.close, s0, r.strike, t, cfg["rf"], o)
        rows.append(
            {
                "entry": c.entry,
                "expiry": c.expiry,
                "S0": s0,
                "iv_call": ivs["C"],
                "iv_put": ivs["P"],
                "rv": realised_vol(ix, c.entry, c.expiry),
                "vix": ix.vix.get(c.entry, np.nan) / 100,
            }
        )
    v = pd.DataFrame(rows)
    v["iv"] = v[["iv_call", "iv_put"]].mean(axis=1)
    v["vrp"] = v.iv - v.rv
    return v


def vrp(cfg: dict) -> None:
    """Variance risk premium report and chart."""
    RES.mkdir(exist_ok=True)
    opt, ix, cyc = load_all(cfg)
    c = cyc[cyc.period == "dev"].reset_index(drop=True)
    v = vrp_table(opt, ix, c, cfg)
    v.to_csv(RES / "vrp.csv", index=False)
    by = v.groupby(v.entry.dt.year).agg(
        months=("vrp", "count"),
        iv=("iv", "mean"),
        rv=("rv", "mean"),
        iv_minus_rv=("vrp", "mean"),
        share_pos=("vrp", lambda x: (x > 0).mean()),
    )
    vx = v.dropna(subset=["vix"])
    lines = [
        "# Variance risk premium diagnostic (development cycles only)\n",
        "ATM = listed strike nearest S0 on the entry day for the target expiry; IV by "
        "Black-Scholes, r = 6.5%, "
        "no dividend yield, T = calendar days / 365. RV = annualised std of daily log returns of "
        "NIFTY 50 from "
        "entry close to expiry close (sqrt 252).\n",
        f"Months: {v.vrp.notna().sum()}. Mean IV {v.iv.mean():.1%}, mean RV {v.rv.mean():.1%}. "
        f"**Mean IV - RV {v.vrp.mean():+.2%}** (median {v.vrp.median():+.2%}); IV above RV in "
        f"**{(v.vrp > 0).mean():.0%}** of months. Call IV {v.iv_call.mean():.1%}, put IV "
        f"{v.iv_put.mean():.1%}.\n",
        "## By year\n",
        by.to_markdown(floatfmt=".3f"),
        "",
    ]
    if len(vx):
        lines.append(
            f"## India VIX at entry vs realised vol\n{len(vx)} months from {vx.entry.min():%Y-%m}: "
            "mean VIX "
            f"{vx.vix.mean():.1%}, mean RV {vx.rv.mean():.1%}, VIX - RV "
            f"{(vx.vix - vx.rv).mean():+.2%}, "
            f"VIX above RV in {(vx.vix > vx.rv).mean():.0%} of months.\n"
        )
    (RES / "vrp.md").write_text("\n".join(lines))

    fig, axes = plt.subplots(1, 2, figsize=(13, 4.5))
    axes[0].plot(v.entry, v.iv * 100, label="ATM implied vol at entry")
    axes[0].plot(v.entry, v.rv * 100, label="realised vol to expiry")
    if len(vx):
        axes[0].plot(vx.entry, vx.vix * 100, label="India VIX at entry", alpha=0.6, lw=0.8)
    axes[0].set_ylabel("% annualised")
    axes[0].legend()
    axes[0].grid(alpha=0.3)
    axes[1].scatter(v.iv * 100, v.rv * 100, s=12)
    m = max(v.iv.max(), v.rv.max()) * 100
    axes[1].plot([0, m], [0, m], "k--", lw=0.8)
    axes[1].set_xlabel("implied vol %")
    axes[1].set_ylabel("realised vol %")
    axes[1].set_title(f"IV above RV in {(v.vrp > 0).mean():.0%} of months")
    fig.tight_layout()
    fig.savefig(RES / "iv_vs_rv.png", dpi=130)
    plt.close(fig)
    logger.info(lines[2])
    logger.info(by.to_string(float_format=lambda x: f"{x:.3f}"))
    logger.info("wrote results/vrp.md, results/iv_vs_rv.png")


def check(cfg: dict) -> None:
    """Backtest checks: expiries, settlement, strike choice, costs, reconciliation."""
    opt, ix, cyc = load_all(cfg)
    dev = cyc[cyc.period == "dev"].reset_index(drop=True)
    hold = cyc[cyc.period == "holdout"]
    trades = {r: simulate(r, dev, opt, ix, cfg, cfg["cash_rate"]) for r in RULES}
    out = ["# Backtest checks\n"]

    rng = np.random.default_rng(0)
    done = trades["iron_condor"][trades["iron_condor"].skipped == ""]
    for i in rng.choice(done.index, 3, replace=False):
        for r, t in trades.items():
            row = t.loc[i]
            if row.skipped:
                continue
            s, hand = row.settle, 0.0
            for j in range(1, 5):
                leg = row.get(f"leg{j}")
                if not isinstance(leg, str):
                    continue
                side, o, k = leg.split()
                k = float(k)
                val = max(0.0, k - s) if o == "P" else max(0.0, s - k)
                hand += val if side == "B" else -val
            assert abs(hand - row.payoff_unit) < 1e-9, (r, i)
            legs = [row.get(f"leg{j}") for j in range(1, 5) if isinstance(row.get(f"leg{j}"), str)]
            out.append(
                f"- payoff {r} {row.entry:%Y-%m-%d}: legs "
                f"{legs}, "
                f"S = {s:.2f}, by hand {hand:.2f} per unit = code {row.payoff_unit:.2f}: OK"
            )

    for _, c in dev.iterrows():
        ch = chain(opt, c.entry, c.contract)
        assert (ch.date == c.entry).all() and c.entry < c.expiry
    out.append(
        f"- no look-ahead: strike choice uses only the entry-day chain (asserted for {len(dev)} "
        "cycles); "
        "S0 = index close on entry day; units use capital before the trade; settlement used only "
        "for payoff."
    )

    assert dev.expiry.max() < hold.entry.min()
    assert all(len(t) == len(dev) and t.entry.max() < hold.entry.min() for t in trades.values())
    runs = (
        (RES / "holdout_runs.log").read_text().count("run ")
        if (RES / "holdout_runs.log").exists()
        else 0
    )
    assert runs <= 1
    out.append(
        f"- holdout isolation: development = {len(dev)} cycles to expiry "
        f"{dev.expiry.max():%Y-%m-%d}; holdout = "
        f"{len(hold)} cycles from entry {hold.entry.min():%Y-%m-%d}; no development trade uses a "
        "holdout month; "
        f"holdout runs logged so far: {runs}."
    )

    for r in ("put_spread", "iron_condor"):
        t = trades[r][trades[r].skipped == ""]
        loss = -(t.units * (t.credit + t.payoff_unit))
        excess = loss - t.maxloss_plan
        assert (excess < 1e-6).all(), r
        worst_r = (-(t.net) / t.capital_before).max()
        out.append(
            f"- max loss {r}: worst trading loss {(loss / t.capital_before).max():.2%} of capital "
            f"(plan {cfg['max_loss_pct']:.0%}); worst net month incl. costs {worst_r:.2%}: OK"
        )
    (RES / "backtest_checks.md").write_text("\n".join(out) + "\n")
    logger.info("\n".join(out))
