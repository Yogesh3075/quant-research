"""Draw one README chart per project from result files already on disk. No backtest is rerun."""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mt
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]  # repo root
S1, S2, S3, S4 = "#2a78d6", "#eb6834", "#1baf7a", "#eda100"  # categorical slots 1-4, fixed order
GRAY, INK, INK2, SURF = "#8a8984", "#0b0b0b", "#52514e", "#fcfcfb"

plt.rcParams.update(
    {
        "figure.facecolor": SURF,
        "axes.facecolor": SURF,
        "savefig.facecolor": SURF,
        "font.size": 10,
        "axes.edgecolor": "#d6d5d0",
        "axes.labelcolor": INK2,
        "xtick.color": INK2,
        "ytick.color": INK2,
        "axes.grid": True,
        "grid.color": "#ebeae6",
        "grid.linewidth": 0.8,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "lines.linewidth": 2,
        "legend.frameon": False,
        "axes.titlesize": 11,
        "axes.titleweight": "bold",
        "axes.titlecolor": INK,
        "axes.titlelocation": "left",
    }
)
LAKH = mt.FuncFormatter(lambda v, _: f"₹{v / 1e5:,.0f} L")


def shade(ax, start, end, label):
    ax.axvspan(pd.Timestamp(start), pd.Timestamp(end), color="#efeee9", zorder=0, lw=0)
    ax.text(
        pd.Timestamp(start),
        1.0,
        f" {label}",
        transform=ax.get_xaxis_transform(),
        va="top",
        ha="left",
        color=INK2,
        fontsize=8.5,
    )


def save(fig, path):
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
    print("wrote", path.relative_to(ROOT))


# momentum: primary vs equal weight on Rs 10 lakh (development daily + holdout run 1 monthly)
R = ROOT / "momentum_research/results"
fig, ax = plt.subplots(figsize=(8, 4))
for name, folder, hcol, c in [
    ("Momentum, top 30 (primary)", "primary_base", "fixed primary", S1),
    ("Equal weight, eligible Nifty 500", "equal_weight_base", "equal weight", GRAY),
]:
    d = (
        pd.read_csv(R / f"phase3/{folder}/equity_daily.csv", parse_dates=["date"])
        .set_index("date")
        .equity
    )
    h = pd.read_csv(R / "phase4/holdout_returns_run1.csv")
    hidx = pd.PeriodIndex(h.HistoricalDate, freq="M").to_timestamp("M")
    hs = pd.Series(d.iloc[-1] * (1 + h[hcol].values).cumprod(), index=hidx)
    ax.plot(pd.concat([d, hs]), color=c, label=name, lw=2 if c == S1 else 1.6)
shade(ax, hidx[0] - pd.offsets.MonthEnd(1), hidx[-1], "holdout run 1")
ax.set_yscale("log")
ax.yaxis.set_major_formatter(LAKH)
ax.yaxis.set_minor_formatter(mt.NullFormatter())
ax.set_title("₹10 lakh in the momentum portfolio vs equal weight, after costs (log scale)")
ax.legend(loc="upper left")
save(fig, ROOT / "momentum_research/docs/equity_curve.png")

# option selling: P1 vs cash vs Nifty 50 TRI on Rs 10 lakh (all 225 cycles, from stored monthly P&L)
m = pd.read_csv(
    ROOT / "option_selling/results/phase4/monthly_pnl_phase4.csv",
    low_memory=False,
    parse_dates=["entry_date", "expiry_date"],
)
p1 = m[m.rule == "p1"].copy()
p1["period"] = pd.Categorical(p1.period, ["design", "validation", "holdout"], ordered=True)
p1 = p1.sort_values(["period", "entry_date"])
x = p1.expiry_date
fig, ax = plt.subplots(figsize=(8, 4))
ax.plot(
    x,
    1e6 * (1 + p1.return_on_capital_pct / 100).cumprod(),
    color=S1,
    label="P1 put spread (total, incl. 6.5% on idle cash)",
)
ax.plot(
    x,
    1e6 * (1 + p1.cash_interest / p1.idle_cash).cumprod(),
    color=GRAY,
    ls="--",
    lw=1.6,
    label="Cash at 6.5%",
)
ax.plot(
    x,
    1e6 * (1 + p1.nifty_tri_return_pct / 100).cumprod(),
    color=S2,
    lw=1.6,
    label="Nifty 50 TRI (buy and hold)",
)
for per, lab in [("validation", "validation"), ("holdout", "holdout")]:
    q = p1[p1.period == per]
    shade(ax, q.entry_date.min(), q.expiry_date.max(), lab)
ax.yaxis.set_major_formatter(LAKH)
ax.set_title("₹10 lakh: P1 rule vs cash and the Nifty, 2008-2026")
ax.legend(loc="upper left")
save(fig, ROOT / "option_selling/docs/p1_equity.png")

# factor regime rotation: Nifty 200 TRI and HMM filtered p(stressed), development
f = pd.read_csv(ROOT / "factor_regime_rotation/results/monthly_returns.csv", parse_dates=["date"])
fig, (a1, a2) = plt.subplots(
    2, 1, figsize=(8, 4.6), sharex=True, gridspec_kw={"height_ratios": [2, 1]}
)
a1.plot(f.date, 1e6 * (1 + f.nifty200_ret).cumprod(), color=S1)
a1.yaxis.set_major_formatter(LAKH)
a1.set_title("Nifty 200 TRI on ₹10 lakh (top) vs HMM filtered p(stressed), 2010-2024")
a2.fill_between(f.date, f.hmm_p_stressed, color=S2, alpha=0.35, lw=0)
a2.plot(f.date, f.hmm_p_stressed, color=S2, lw=1.4)
a2.axhline(0.5, color=GRAY, ls="--", lw=1)
a2.text(f.date.iloc[0], 0.53, "0.5: switch threshold", color=INK2, fontsize=8.5, va="bottom")
a2.set_ylim(0, 1)
a2.set_ylabel("p(stressed)")
save(fig, ROOT / "factor_regime_rotation/docs/hmm_vs_nifty200.png")

# ML vs linear: cumulative net growth of the four portfolios
g = pd.read_csv(ROOT / "nifty500-ml-factors/results/monthly_returns.csv")
g["m"] = pd.PeriodIndex(g.return_month, freq="M").to_timestamp("M")
fig, ax = plt.subplots(figsize=(8, 4))
for col, lab, c, lw in [
    ("momentum_net", "Momentum", S1, 2),
    ("linear_net", "Linear blend", S2, 2),
    ("lgbm_net", "LightGBM", S3, 2),
    ("ew_net", "Equal weight", GRAY, 1.6),
]:
    ax.plot(g.m, 1e6 * (1 + g[col]).cumprod(), color=c, lw=lw, label=lab)
seen = g[g.period != "development"]
shade(ax, seen.m.min() - pd.offsets.MonthEnd(1), seen.m.max(), "seen (not out of sample)")
ax.yaxis.set_major_formatter(LAKH)
ax.set_title("₹10 lakh in each top-30 portfolio, net of costs")
ax.legend(loc="upper left")
save(fig, ROOT / "nifty500-ml-factors/docs/net_growth.png")

# stat arb: rebuild, all pairs vs F&O subset
s = pd.read_csv(ROOT / "stat_arb/results/monthly_returns.csv")
s["m"] = pd.PeriodIndex(s.month, freq="M").to_timestamp("M")
fig, ax = plt.subplots(figsize=(8, 4))
ax.plot(s.m, 1e6 * (1 + s.all_pairs).cumprod(), color=S1, label="All pairs")
ax.plot(s.m, 1e6 * (1 + s.fo_subset).cumprod(), color=S2, label="F&O subset (shortable)")
ax.axhline(1e6, color=GRAY, lw=1)
h = s[s.period != "development"]
shade(ax, h.m.min() - pd.offsets.MonthEnd(1), h.m.max(), "locked holdout")
ax.yaxis.set_major_formatter(mt.FuncFormatter(lambda v, _: f"₹{v / 1e5:,.1f} L"))
ax.set_title("₹10 lakh in the rebuilt pairs strategy, net of costs")
ax.legend(loc="upper left")
save(fig, ROOT / "stat_arb/docs/equity.png")
