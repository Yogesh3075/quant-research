from __future__ import annotations

import hashlib
import logging
import re
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import requests
import yaml

from optsell import backtest as bt
from optsell import data
from optsell import phase3 as p3
from optsell import phase4 as p4
from optsell.config import CONFIG_PATH

logger = logging.getLogger(__name__)

LIVE = Path("results/live")
LOG = Path("results/phase4/paper_trading_log.csv")
FROZEN = {
    "e1f1": ("results/phase3/frozen_rule.md", "results/phase3/frozen_config_e1f1.yaml"),
    "p1": ("results/phase4/frozen_rule_p1.md", "results/phase4/frozen_config_p3.yaml"),
    "s7": ("results/phase4/frozen_rule_p1.md", "results/phase4/frozen_config_p3.yaml"),
}
LOGCOLS = [
    "month",
    "rule",
    "status",
    "entry_date",
    "expiry_date",
    "index_at_entry",
    "india_vix",
    "prem_ratio",
    "decision_e1f1",
    "decision_p3",
    "decision_p1",
    "decision_s7",
    "reason",
    "filter_gap",
    "filter_threshold",
    "strikes",
    "short_strike",
    "long_strike",
    "short_close",
    "long_close",
    "short_contracts",
    "long_contracts",
    "short_oi",
    "long_oi",
    "credit",
    "credit_per_unit",
    "lot_size",
    "lot_source",
    "lots",
    "units",
    "capital_before",
    "max_loss",
    "max_loss_pct",
    "margin",
    "stop_level_rs",
    "stop_spread_value",
    "short_fill",
    "long_fill",
    "fill_time",
    "short_slip_vs_close",
    "long_slip_vs_close",
    "short_exit_fill",
    "long_exit_fill",
    "stop_triggered",
    "trigger_date",
    "exit_date",
    "exit_reason",
    "exit_cost",
    "pnl",
    "capital_after",
    "backtest_expected_pnl",
    "diff_vs_backtest",
    "notes",
]


def sha(path) -> str:
    """SHA-256 of a file."""
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def frozen(rule) -> dict:
    """Frozen config of a rule, after checking its hash; exits on a mismatch."""
    md, conf = FROZEN[rule]
    want = re.search(r"SHA-256 `([0-9a-f]{64})`", Path(md).read_text()).group(1)
    got = sha(conf)
    if got != want:
        raise SystemExit(
            f"FROZEN CONFIG CHANGED for {rule}: {conf} has SHA-256 {got}, but {md} records {want}. "
            "Stop."
        )
    cfg = yaml.safe_load(Path(conf).read_text())
    cfg.setdefault("phase4", {})
    return cfg


def spec(rule, cfg: dict) -> dict:
    """Rule parameters for the paper-trading decision."""
    if rule == "e1f1":
        return {"legs": p4.PS, "sizing": "spread", "prem": None, "ivrv": True, "stop": "credit"}
    if rule == "p1":
        return {
            "legs": p4.PS,
            "sizing": "spread",
            "prem": cfg["phase4"]["prem_min"],
            "ivrv": False,
            "stop": None,
        }
    return {
        "legs": [["P", -1, 1, 0.95]],
        "sizing": "notional",
        "prem": None,
        "ivrv": False,
        "stop": "credit",
    }


def rules() -> list:
    """Rules the tool covers (e1f1, P1, and S7 if enabled)."""
    w = yaml.safe_load(CONFIG_PATH.read_text()).get("live", {})
    return ["e1f1", "p1"] + (["s7"] if w.get("include_s7", False) else [])


def get_day(d, fetch=True) -> tuple:
    """One day's bhavcopy (downloaded if needed and allowed)."""
    f = data.RAW / "fo" / f"{d:%Y%m%d}.zip"
    man = [
        m
        for m in data.manual_files()
        if d.strftime("%d%b%Y").upper() in m.name.upper() or f"{d:%Y%m%d}" in m.name
    ]
    if not f.exists() and not man and fetch:
        s = requests.Session()
        s.headers.update(data.UA)
        body, _ = data.fetch(s, data.fo_urls(d), lambda b: b[:2] == b"PK", 1.0)
        if body is not None:
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_bytes(body)
        ib, _ = data.fetch(s, data.idx_urls(d), lambda b: b[:10].startswith(b"Index Name"), 1.0)
        if ib is not None:
            (data.RAW / "index").mkdir(parents=True, exist_ok=True)
            (data.RAW / "index" / f"{d:%Y%m%d}.csv").write_bytes(ib)
    src = f if f.exists() else (man[0] if man else None)
    if src is None:
        return None, None
    fo = data.parse_fo(src)
    ip = data.RAW / "index" / f"{d:%Y%m%d}.csv"
    ixr = data.parse_index(ip) if ip.exists() else None
    if ixr is None or pd.isna(ixr["close_nse"]):
        und = fo.und.dropna()
        ixr = {"date": d, "close_nse": float(und.iloc[0]) if len(und) else np.nan, "vix": np.nan}
    return fo, ixr


def context(d, fetch=False) -> dict:
    """Data up to and including day d only (asserted)."""
    d = pd.Timestamp(d)
    fo = pd.read_parquet(data.PROC / "nifty_fo.parquet")
    ix = pd.read_csv(data.PROC / "index.csv", parse_dates=["date"], index_col="date")
    if d > fo.date.max():
        extra, rows = [], []
        for x in pd.bdate_range(fo.date.max() + pd.Timedelta(days=1), d):
            a, b = get_day(x, fetch and x == d)
            if a is not None:
                extra.append(a)
                rows.append(b)
        if extra:
            fo = pd.concat([fo] + extra, ignore_index=True)
            r = pd.DataFrame(rows).set_index("date")
            r["close"] = r.close_nse
            ix = pd.concat([ix, r[["close", "close_nse", "vix"]]])
    fo = data.relabel(fo[fo.date <= d])
    ix = ix[ix.index <= d]
    ix = ix[~ix.index.duplicated(keep="last")]
    assert fo.date.max() <= d and ix.index.max() <= d
    opt = fo[fo.instr == "OPTIDX"][
        ["date", "expiry", "strike", "opt", "close", "volume", "lot", "oi"]
    ]
    days = pd.DatetimeIndex(sorted(fo.date.unique()))
    return {"fo": fo, "opt": opt, "ix": ix, "days": days, "d": d}


def entry_info(ctx) -> dict | None:
    """Whether d is an entry day, and the target contract."""
    fo, d, days = ctx["fo"], ctx["d"], ctx["days"]
    if d not in days:
        return None
    exps = data.monthly_expiries(fo)
    act = {e: data.expiry_day(fo, e) for e in exps}
    prev = max(e for e, a in act.items() if a < d)
    first = days[days > act[prev]][0]
    day = ctx["opt"][ctx["opt"].date == d]
    m = prev.to_period("M") + 1
    target = day.expiry[day.expiry.dt.to_period("M") == m].max()
    return {
        "is_entry": first == d,
        "prev": prev,
        "prev_day": act[prev],
        "first": first,
        "target": target,
    }


def hist_cycles(ctx, d, target) -> pd.DataFrame:
    """Past cycles up to d, for the expanding filter threshold."""
    c = data.cycles(ctx["fo"], ctx["ix"])
    c = c[c.entry < d]
    now = pd.DataFrame(
        [{"entry": d, "expiry": target, "contract": target, "settle": np.nan, "next_entry": target}]
    )
    return pd.concat([c, now], ignore_index=True)


def chain(ctx, d, contract) -> pd.DataFrame:
    """Option chain on day d for a contract."""
    ch = ctx["opt"][(ctx["opt"].date == d) & (ctx["opt"].expiry == contract)]
    assert (ch.date == d).all()
    return ch


def lot_size(ctx, d, contract, legs, cfg: dict) -> tuple:
    """Lot size: bhavcopy column, then NSE's lot file, then the config."""
    ch = chain(ctx, d, contract)
    x = ch[(ch.strike == legs[0]["k"]) & (ch.opt == "PE")].lot.dropna()
    if len(x):
        return int(x.iloc[0]), "NSE bhavcopy (UDiFF lot column, that day)"
    try:
        r = requests.get(
            "https://nsearchives.nseindia.com/content/fo/fo_mktlots.csv",
            headers=data.UA,
            timeout=20,
        )
        t = pd.read_csv(pd.io.common.StringIO(r.text))
        t.columns = t.columns.str.strip()
        row = t[t.SYMBOL.str.strip() == "NIFTY"].iloc[0]
        col = contract.strftime("%b-%y").upper()
        return int(str(row[col]).strip()), "NSE fo_mktlots.csv"
    except Exception:
        lot = yaml.safe_load(CONFIG_PATH.read_text()).get("live", {}).get("lot_size")
        logger.info(
            f"WARNING: lot size not available from NSE; using live.lot_size = {lot} from "
            "configs/config.yaml. Verify it on NSE."
        )
        return lot, "config live.lot_size (VERIFY)"


def decide(rule, ctx, d, target, capital, cfg: dict, gp=None) -> tuple:
    """TRADE or SKIP for a rule on an entry day, with legs and units."""
    v = spec(rule, cfg)
    s0 = float(ctx["ix"].close[d])
    ch = chain(ctx, d, target)
    legs, fb, why = p4.pick(v["legs"], ch, s0, cfg)
    out = {
        "rule": rule,
        "entry_date": d.date(),
        "expiry_date": target.date(),
        "index_at_entry": s0,
        "india_vix": ctx["ix"].vix.get(d, np.nan),
        "capital_before": capital,
    }
    prem = (
        (legs[0]["close"] - legs[1]["close"]) / (legs[0]["k"] - legs[1]["k"])
        if legs and len(legs) == 2
        else np.nan
    )
    out["prem_ratio"] = prem
    if legs is None:
        return {**out, "decision": "SKIP", "reason": why}, None
    if v["prem"] is not None and prem < v["prem"]:
        return {
            **out,
            "decision": "SKIP",
            "reason": f"prem_ratio {prem:.3f} < {v['prem']:.2f}",
        }, None
    if v["ivrv"]:
        g = gp.loc[d]
        out.update(
            {"filter_gap": g.gap, "filter_threshold": g.threshold, "atm_iv": g.iv, "rv21": g.rv}
        )
        if pd.notna(g.gap) and pd.notna(g.threshold) and g.gap <= g.threshold:
            return {
                **out,
                "decision": "SKIP",
                "reason": f"IV-RV gap {g.gap:.4f} <= expanding median {g.threshold:.4f}",
            }, None
    p4.fill(legs, cfg["costs"], 1.0)
    credit = sum(-leg["side"] * leg["q"] * leg["px"] for leg in legs)
    if v["sizing"] == "spread":
        per = (max(leg["k"] for leg in legs) - min(leg["k"] for leg in legs)) - credit
        units = cfg["max_loss_pct"] * capital / per
        margin_per = per
    else:
        per = np.nan
        units = capital / s0
        margin_per = cfg["census"]["naked_margin"] * s0
    for leg in legs:
        r = ch[(ch.strike == leg["k"]) & (ch.opt == ("PE" if leg["opt"] == "P" else "CE"))].iloc[0]
        leg["oi"] = r.oi
    out.update(
        {
            "decision": "TRADE",
            "reason": "fallback strike used" if fb else "",
            "legs": legs,
            "credit_per_unit": credit,
            "units": units,
            "maxloss_per_unit": per,
            "margin_per_unit": margin_per,
        }
    )
    return out, legs


def size_lots(out, legs, lot, src, cfg: dict, rule) -> dict:
    """Round units down to whole lots and recompute max loss and margin."""
    lots = int(np.floor(out["units"] / lot)) if lot else 0
    u = lots * lot
    cap = out["capital_before"]
    out.update({"lot_size": lot, "lot_source": src, "lots": lots, "units_rounded": u})
    if spec(rule, cfg)["sizing"] == "spread":
        out["max_loss"] = u * out["maxloss_per_unit"]
        out["margin"] = out["max_loss"]
        out["stop_spread_value"] = 3 * out["credit_per_unit"] if spec(rule, cfg)["stop"] else np.nan
    else:
        out["max_loss"] = np.nan
        out["margin"] = u * out["margin_per_unit"]
        out["stop_spread_value"] = 3 * out["credit_per_unit"] if spec(rule, cfg)["stop"] else np.nan
    out["max_loss_pct"] = 100 * out["max_loss"] / cap if pd.notna(out["max_loss"]) else np.nan
    out["stop_level_rs"] = 2 * out["credit_per_unit"] * u if spec(rule, cfg)["stop"] else np.nan
    out["credit"] = out["credit_per_unit"] * u
    return out


def read_log() -> pd.DataFrame:
    """The paper-trading log."""
    if LOG.exists() and LOG.stat().st_size:
        t = pd.read_csv(LOG, dtype=object)
        for c in LOGCOLS:
            if c not in t:
                t[c] = np.nan
        return t[LOGCOLS]
    return pd.DataFrame(columns=LOGCOLS)


def capital_of(rule, cfg: dict) -> float:
    """Current paper capital of a rule."""
    t = read_log()
    t = t[(t.rule == rule) & t.capital_after.notna()]
    return float(t.capital_after.iloc[-1]) if len(t) else float(cfg["capital"])


def signal(d=None, write=True, capital=None, fetch=True) -> None:
    """Entry-day signal for every rule; writes the signal sheet and planned rows."""
    d = pd.Timestamp(d or datetime.now().date())
    ctx = context(d, fetch=fetch)
    if d not in ctx["days"]:
        logger.info(
            f"No F&O bhavcopy for {d:%Y-%m-%d} yet. NSE publishes after the close: try again after "
            "about 7 pm IST "
            "(or place the file in data/raw/manual/)."
        )
        return None
    info = entry_info(ctx)
    if not info["is_entry"]:
        logger.info(
            f"{d:%Y-%m-%d} is not an entry day (the entry day after the "
            f"{info['prev_day']:%Y-%m-%d} expiry was "
            f"{info['first']:%Y-%m-%d}). Next entry: the first trading day after the "
            f"{info['target']:%Y-%m-%d} monthly "
            "expiry (confirm the actual expiry date on NSE)."
        )
        return None
    res = []
    for rule in rules():
        cfg = frozen(rule)
        gp = (
            p3.gaps(ctx, hist_cycles(ctx, d, info["target"]).reset_index(drop=True), cfg)
            if spec(rule, cfg)["ivrv"]
            else None
        )
        cap = capital if capital is not None else capital_of(rule, cfg)
        out, legs = decide(rule, ctx, d, info["target"], cap, cfg, gp)
        if legs:
            lot, src = lot_size(ctx, d, info["target"], legs, cfg)
            out = size_lots(out, legs, lot, src, cfg, rule)
            if out["lots"] == 0:
                out["decision"] = "NO LOTS"
                out["reason"] = (
                    f"units {out['units']:.1f} < one lot of {lot}: trade not possible at this "
                    "capital"
                )
        res.append(out)
    lines = [
        f"# Signal {d:%Y-%m-%d}: options on the {info['target']:%Y-%m-%d} monthly expiry\n",
        f"NIFTY 50 close {float(ctx['ix'].close[d]):,.2f}; India VIX "
        f"{ctx['ix'].vix.get(d, np.nan)}. Paper trading only.\n",
        "| rule | decision | reason | legs (strike: close, contracts, OI) | net credit/unit | lots "
        "x lot size | max loss | margin est. | stop |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for o in res:
        if o.get("legs"):
            lg = "; ".join(
                f"{'S' if leg['side'] < 0 else 'B'} {leg['k']:.0f}P: {leg['close']}, "
                f"{leg['volume']:.0f}, "
                f"{leg['oi']:.0f}"
                for leg in o["legs"]
            )
            ml = (
                f"Rs {o['max_loss']:,.0f} ({o['max_loss_pct']:.1f}%)"
                if pd.notna(o.get("max_loss"))
                else "unlimited"
            )
            st = (
                f"exit if loss >= Rs {o['stop_level_rs']:,.0f} (spread value >= "
                f"{o['stop_spread_value']:.2f}/unit)"
                if pd.notna(o.get("stop_level_rs"))
                else "none (hold to expiry)"
            )
            lines.append(
                f"| {o['rule']} | {o['decision']} | {o['reason']} | {lg} | "
                f"{o['credit_per_unit']:.2f} | "
                f"{o['lots']} x {o['lot_size']} ({o['lot_source']}) | {ml} | Rs {o['margin']:,.0f} "
                f"| {st} |"
            )
        else:
            lines.append(f"| {o['rule']} | {o['decision']} | {o['reason']} | | | | | | |")
        if o["rule"] == "e1f1" and "filter_gap" in o:
            lines.append(
                f"| | | e1f1 filter: ATM IV {o['atm_iv']:.4f} - RV21 {o['rv21']:.4f} = gap "
                f"{o['filter_gap']:.4f}; "
                f"threshold {o['filter_threshold']:.4f} | | | | | | |"
            )
        if o["rule"] in ("p1",):
            lines.append(
                f"| | | p1 prem_ratio {o['prem_ratio']:.4f} vs "
                f"{frozen('p1')['phase4']['prem_min']} | | | | | | |"
            )
    text = "\n".join(lines) + "\n"
    logger.info(text)
    if write:
        LIVE.mkdir(parents=True, exist_ok=True)
        (LIVE / f"{d:%Y-%m}_signal.md").write_text(text)
        t = read_log()
        for o in res:
            row = {c: o.get(c, np.nan) for c in LOGCOLS}
            row.update(
                {
                    "month": f"{d:%Y-%m}",
                    "status": "planned"
                    if o["decision"] == "TRADE"
                    else o["decision"].lower().replace(" ", "_"),
                    f"decision_{o['rule']}": o["decision"],
                }
            )
            if o.get("legs"):
                row.update(
                    {
                        "strikes": "/".join(f"{leg['k']:.0f}" for leg in o["legs"]),
                        "short_strike": o["legs"][0]["k"],
                        "short_close": o["legs"][0]["close"],
                        "short_contracts": o["legs"][0]["volume"],
                        "short_oi": o["legs"][0]["oi"],
                    }
                )
                if len(o["legs"]) > 1:
                    row.update(
                        {
                            "long_strike": o["legs"][1]["k"],
                            "long_close": o["legs"][1]["close"],
                            "long_contracts": o["legs"][1]["volume"],
                            "long_oi": o["legs"][1]["oi"],
                        }
                    )
                row["units"] = o["units_rounded"]
            t = pd.concat([t, pd.DataFrame([row])], ignore_index=True)
        t.to_csv(LOG, index=False)
    return res


def open_rows(t) -> pd.DataFrame:
    """Open trades in the log."""
    return t[t.status.isin(["planned", "open", "stop_triggered"])]


def legs_of(row, cfg: dict) -> list:
    """Legs of a logged trade."""
    cc = cfg["costs"]
    out = []
    for nm, side in (("short", -1), ("long", 1)):
        if pd.isna(row.get(f"{nm}_strike")) or row.get(f"{nm}_strike") in ("", "nan"):
            continue
        cl = float(row[f"{nm}_close"])
        slip = max(cc["slip_min"], cc["slip_pct"] * cl)
        px = (
            float(row[f"{nm}_fill"])
            if pd.notna(row.get(f"{nm}_fill")) and row.get(f"{nm}_fill") != ""
            else (max(0.0, cl - slip) if side < 0 else cl + slip)
        )
        out.append(
            {
                "name": nm,
                "opt": "P",
                "side": side,
                "q": 1,
                "k": float(row[f"{nm}_strike"]),
                "close": cl,
                "px": px,
                "slip": (cl - px) if side < 0 else (px - cl),
            }
        )
    return out


def last_close(ctx, contract, leg, d) -> tuple:
    """Last close of a leg on or before d."""
    s = ctx["opt"][
        (ctx["opt"].expiry == contract)
        & (ctx["opt"].strike == leg["k"])
        & (ctx["opt"].opt == "PE")
        & (ctx["opt"].close > 0)
        & (ctx["opt"].date <= d)
    ]
    return float(s.sort_values("date").close.iloc[-1]), s.date.max()


def mark(row, ctx, d, cfg: dict, next_day=None) -> dict:
    """Mark-to-market and stop status of an open trade."""
    contract = pd.Timestamp(row["expiry_date"])
    legs = legs_of(row, cfg)
    u = float(row["units"])
    credit = sum(-leg["side"] * leg["px"] for leg in legs)
    pnl, stale = 0.0, []
    for leg in legs:
        cl, dt = last_close(ctx, contract, leg, d)
        pnl += leg["side"] * (cl - leg["px"]) * u
        if dt != d:
            stale.append(f"{leg['name']} close carried from {dt:%Y-%m-%d}")
    rule = row["rule"]
    trig = False
    if spec(rule, cfg)["stop"] and d > pd.Timestamp(row["entry_date"]):
        nd = (
            next_day
            if next_day is not None
            else pd.bdate_range(d + pd.Timedelta(days=1), periods=1)[0]
        )
        last = (
            data.expiry_day(ctx["fo"], contract) if contract <= ctx["fo"].date.max() else contract
        )
        trig = -pnl >= cfg["phase3"]["stop_mult"] * u * credit and nd < last
    return {"pnl": pnl, "credit": credit * u, "trigger": bool(trig), "stale": stale}


def settle_pnl(row, ctx, d, cfg: dict, how, exit_closes=None) -> tuple:
    """P&L of a closed trade with the backtest cost model."""
    cc = cfg["costs"]
    contract = pd.Timestamp(row["expiry_date"])
    legs = legs_of(row, cfg)
    u = float(row["units"])
    entry = pd.Timestamp(row["entry_date"])
    fills = [(entry, leg["px"], u, leg["side"] < 0) for leg in legs]
    if how == "expiry":
        s = data.settlement(ctx["fo"], ctx["ix"], contract, d)
        val = [bt.intrinsic("P", leg["k"], s) for leg in legs]
        itm = sum(v * u for leg, v in zip(legs, val, strict=False) if leg["side"] > 0)
        it = p3.fees(fills, itm, cc)
        pnl = (
            sum(-leg["side"] * leg["px"] * u for leg in legs)
            + sum(leg["side"] * v * u for leg, v in zip(legs, val, strict=False))
            - sum(it.values())
        )
        return pnl, 0.0, s
    exits, slip = [], 0.0
    for leg in legs:
        cl = exit_closes[leg["name"]] if exit_closes else last_close(ctx, contract, leg, d)[0]
        fx = row.get(f"{leg['name']}_exit_fill")
        if pd.notna(fx) and fx != "":
            px = float(fx)
        else:
            sl = max(cc["slip_min"], cc["slip_pct"] * cl)
            px = cl + sl if leg["side"] < 0 else max(0.0, cl - sl)
        exits.append((d, px, u, leg["side"] > 0))
        slip += abs(px - cl) * u
    it = p3.fees(fills + exits, 0.0, cc)
    entry_it = p3.fees(fills, 0.0, cc)
    pnl = (
        sum(-leg["side"] * leg["px"] * u for leg in legs)
        + sum(leg["side"] * x[1] * u for leg, x in zip(legs, exits, strict=False))
        - sum(it.values())
    )
    return pnl, slip + sum(it.values()) - sum(entry_it.values()), np.nan


def expected(row, ctx, d, cfg: dict, how):
    """The backtest's P&L for the same trade, for comparison."""
    r = dict(row)
    for nm in ("short", "long"):
        r[f"{nm}_fill"] = np.nan
        r[f"{nm}_exit_fill"] = np.nan
    return settle_pnl(r, ctx, d, cfg, how)[0]


def monitor(d=None, write=True, fetch=True) -> list:
    """Daily marks for open trades."""
    d = pd.Timestamp(d or datetime.now().date())
    ctx = context(d, fetch=fetch)
    if d not in ctx["days"]:
        logger.info(f"No bhavcopy for {d:%Y-%m-%d} yet: try again after about 7 pm IST.")
        return
    t = read_log()
    rows = []
    for i, row in open_rows(t).iterrows():
        cfg = frozen(row["rule"])
        m = mark(row, ctx, d, cfg)
        k = float(row["short_strike"])
        s = float(ctx["ix"].close[d])
        cap = float(row["capital_before"])
        status = (
            "STOP: exit at tomorrow's close"
            if m["trigger"] and row["status"] != "stop_triggered"
            else (
                "stop already triggered: exit today"
                if row["status"] == "stop_triggered"
                else "hold"
            )
        )
        logger.info(
            f"{row['rule']}: P&L Rs {m['pnl']:,.0f} ({100 * m['pnl'] / cap:+.2f}% of capital); "
            f"NIFTY {s:,.0f} is "
            f"{100 * (s / k - 1):+.2f}% from the short strike {k:.0f}; {status}"
            + (f" [{'; '.join(m['stale'])}]" if m["stale"] else "")
        )
        rows.append(
            {
                "date": d.date(),
                "rule": row["rule"],
                "entry_date": row["entry_date"],
                "pnl": m["pnl"],
                "pnl_pct": 100 * m["pnl"] / cap,
                "nifty": s,
                "short_strike": k,
                "status": status,
            }
        )
        if write:
            if m["trigger"] and row["status"] != "stop_triggered":
                t.loc[i, ["status", "stop_triggered", "trigger_date"]] = [
                    "stop_triggered",
                    "yes",
                    str(d.date()),
                ]
            elif row["status"] == "planned":
                t.loc[i, "status"] = "open"
    if not rows:
        logger.info("No open paper position.")
    if write and rows:
        LIVE.mkdir(parents=True, exist_ok=True)
        f = LIVE / "daily_marks.csv"
        pd.concat([pd.read_csv(f) if f.exists() else pd.DataFrame(), pd.DataFrame(rows)]).to_csv(
            f, index=False
        )
        t.to_csv(LOG, index=False)
    return rows


def close(d=None, write=True, fetch=True, expiry=False) -> None:
    """Close trades on a stop exit or at expiry."""
    d = pd.Timestamp(d or datetime.now().date())
    ctx = context(d, fetch=fetch)
    if d not in ctx["days"]:
        logger.info(f"No bhavcopy for {d:%Y-%m-%d} yet: try again after about 7 pm IST.")
        return
    t = read_log()
    for i, row in open_rows(t).iterrows():
        cfg = frozen(row["rule"])
        contract = pd.Timestamp(row["expiry_date"])
        if row["status"] == "stop_triggered" and d > pd.Timestamp(row["trigger_date"]):
            how, why = "stop", "stop exit (next close after trigger)"
        elif d >= contract or expiry:
            how, why = "expiry", "settled at expiry"
        else:
            logger.info(
                f"{row['rule']}: nothing to close on {d:%Y-%m-%d} (no stop exit due, not the "
                "expiry day)."
            )
            continue
        pnl, cost, s = settle_pnl(row, ctx, d, cfg, how)
        exp = expected(row, ctx, d, cfg, how)
        cap = float(row["capital_before"]) + pnl
        logger.info(
            f"{row['rule']}: {why}; P&L Rs {pnl:,.0f}; backtest-expected Rs {exp:,.0f} (diff "
            f"{pnl - exp:+,.0f}); "
            f"paper capital Rs {cap:,.0f}"
        )
        if write:
            t.loc[
                i,
                [
                    "status",
                    "exit_date",
                    "exit_reason",
                    "exit_cost",
                    "pnl",
                    "capital_after",
                    "backtest_expected_pnl",
                    "diff_vs_backtest",
                ],
            ] = ["closed", str(d.date()), why, cost, pnl, cap, exp, pnl - exp]
    if write:
        t.to_csv(LOG, index=False)


def fill(rule, leg, price, lots, when=None, exit_=False) -> None:
    """Record a paper fill."""
    t = read_log()
    o = open_rows(t)
    o = o[o.rule == rule]
    if o.empty:
        raise SystemExit(f"No open or planned {rule} trade in the log.")
    i = o.index[-1]
    nm = "short" if leg.startswith("short") else "long"
    if exit_:
        t.loc[i, f"{nm}_exit_fill"] = price
    else:
        t.loc[i, f"{nm}_fill"] = price
        cl = float(t.loc[i, f"{nm}_close"])
        t.loc[i, f"{nm}_slip_vs_close"] = (cl - price) if nm == "short" else (price - cl)
        if when:
            t.loc[i, "fill_time"] = when
    lot = float(t.loc[i, "lot_size"]) if pd.notna(t.loc[i, "lot_size"]) else np.nan
    if pd.notna(lot) and int(lots) * lot != float(t.loc[i, "units"]):
        t.loc[i, "notes"] = f"fill lots {lots} differ from planned units {t.loc[i, 'units']}"
    t.to_csv(LOG, index=False)
    logger.info(
        f"Recorded {rule} {nm} {'exit' if exit_ else 'entry'} fill {price} x {lots} lots"
        + ("" if exit_ else f"; slippage vs close {t.loc[i, f'{nm}_slip_vs_close']}")
    )


def status() -> None:
    """Paper-trading summary per rule."""
    t = read_log()
    for rule in rules():
        cfg = frozen(rule)
        g = t[t.rule == rule]
        c = g[g.status == "closed"]
        pnl = c.pnl.astype(float)
        o = open_rows(g)
        logger.info(
            f"{rule}: paper capital Rs {capital_of(rule, cfg):,.0f}; trades {len(c)}, wins "
            f"{(pnl > 0).sum()}, losses "
            f"{(pnl <= 0).sum()}, total P&L Rs {pnl.sum():,.0f}; live vs backtest-expected Rs "
            f"{c.diff_vs_backtest.astype(float).sum():+,.0f}; open: "
            + (
                ", ".join(f"{r.entry_date} {r.strikes} ({r.status})" for r in o.itertuples())
                or "none"
            )
        )


def cli(cmd: str, args: list) -> None:
    """Dispatch a paper-trading command with its --options."""
    a = {}
    i = 0
    while i < len(args):
        if args[i].startswith("--"):
            k = args[i][2:]
            if i + 1 < len(args) and not args[i + 1].startswith("--"):
                a[k] = args[i + 1]
                i += 2
            else:
                a[k] = True
                i += 1
        else:
            i += 1
    for r in rules():
        frozen(r)
    if cmd == "signal":
        signal(a.get("date"))
    elif cmd == "monitor":
        monitor(a.get("date"))
    elif cmd == "close":
        close(a.get("date"), expiry=bool(a.get("expiry")))
    elif cmd == "fill":
        fill(
            a["rule"],
            a["leg"],
            float(a["price"]),
            int(a.get("lots", 1)),
            a.get("time"),
            bool(a.get("exit")),
        )
    elif cmd == "status":
        status()


def check() -> None:
    """Reproduce six historical decisions exactly and test the hash check."""
    out = ["# Live tool checks\n"]
    src = Path(__file__).read_text()
    src = src[: src.index("def check(")]
    assert "iv_minus_future" not in src and "realised_vol(" not in src
    out.append(
        "- live.py never reads `iv_minus_future_rv_pts`; context() truncates option and index data "
        "at the given date and asserts it."
    )
    frozen("e1f1")  # raises if the frozen config was modified
    tmp = Path("results/live/_tmp_config.yaml")
    tmp.parent.mkdir(parents=True, exist_ok=True)
    tmp.write_text(Path(FROZEN["e1f1"][1]).read_text() + "\n# modified\n")
    FROZEN["_t"] = (FROZEN["e1f1"][0], str(tmp))
    try:
        frozen("_t")
        raise AssertionError("modified config not detected")
    except SystemExit as e:
        out.append(
            f'- frozen config hash check fails loudly on a modified config: "{str(e)[:90]}..."'
        )
    finally:
        tmp.unlink()
        FROZEN.pop("_t")
    p3m = pd.read_csv("results/phase3/monthly_pnl_phase3_bugfix.csv")
    p4m = pd.read_csv("results/phase4/monthly_pnl_phase4_bugfix.csv")
    e = p3m[p3m.rule == "e1f1"]
    p = p4m[p4m.rule == "p1"]

    def pick_(g, per, cond):
        return g[(g.period == per) & cond(g)].entry_date.iloc[
            len(g[(g.period == per) & cond(g)]) // 2
        ]

    cases = [
        (
            "e1f1",
            "design",
            pick_(e, "design", lambda g: (g.traded == "yes") & (g.stop_triggered == "no")),
        ),
        (
            "e1f1",
            "design",
            pick_(e, "design", lambda g: g.skip_reason.fillna("").str.startswith("filtered")),
        ),
        ("e1f1", "design", pick_(e, "design", lambda g: g.stop_triggered == "yes")),
        ("p1", "validation", pick_(p, "validation", lambda g: g.traded == "yes")),
        ("p1", "validation", pick_(p, "validation", lambda g: g.skipped == "yes")),
        (
            "e1f1",
            "validation",
            pick_(e, "validation", lambda g: (g.traded == "yes") & (g.stop_triggered == "no")),
        ),
    ]
    for rule, per, d in cases:
        ref = e if rule == "e1f1" else p
        r = ref[ref.entry_date == d].iloc[0]
        cfg = frozen(rule)
        cyc = data.cycles(*data.load())
        c = cyc[cyc.entry == pd.Timestamp(d)].iloc[0]
        ctx = context(c.expiry, fetch=False)
        ctx_d = context(pd.Timestamp(d), fetch=False)
        info = entry_info(ctx_d)
        assert info["is_entry"] and info["target"] == c.contract
        gp = (
            p3.gaps(
                ctx_d,
                hist_cycles(ctx_d, pd.Timestamp(d), info["target"]).reset_index(drop=True),
                cfg,
            )
            if rule == "e1f1"
            else None
        )
        o, legs = decide(
            rule, ctx_d, pd.Timestamp(d), info["target"], float(r.capital_start), cfg, gp
        )
        traded = "yes" if legs else "no"
        assert traded == r.traded, (rule, d, traded, r.traded)
        msg = f"- {rule} {d} ({per}): decision {o['decision']}"
        if legs:
            assert legs[0]["k"] == r.short_put_strike and legs[1]["k"] == r.long_put_strike
            assert abs(o["units"] - r.units) < 1e-3, (o["units"], r.units)
            msg += (
                f", strikes {legs[0]['k']:.0f}/{legs[1]['k']:.0f}, units {o['units']:.3f} = "
                f"backtest {r.units:.3f}"
            )
            row = {
                "rule": rule,
                "entry_date": d,
                "expiry_date": str(c.contract.date()),
                "units": o["units"],
                "short_strike": legs[0]["k"],
                "long_strike": legs[1]["k"],
                "short_close": legs[0]["close"],
                "long_close": legs[1]["close"],
                "capital_before": r.capital_start,
                "status": "open",
            }
            days = ctx["days"][(ctx["days"] >= c.entry) & (ctx["days"] <= c.expiry)]
            trig = None
            if spec(rule, cfg)["stop"]:
                for j in range(1, len(days) - 1):
                    if mark(row, ctx, days[j], cfg, next_day=days[j + 1])["trigger"]:
                        trig = days[j]
                        break
            want = r.get("trigger_date")
            assert (trig is None and (pd.isna(want) or want == "")) or (
                trig is not None and str(trig.date()) == str(want)
            ), (trig, want)
            if trig is not None:
                ex = days[list(days).index(trig) + 1]
                pnl, _, _ = settle_pnl(row, ctx, ex, cfg, "stop")
                msg += f", stop trigger {trig:%Y-%m-%d} = backtest, exit {ex:%Y-%m-%d}"
            else:
                pnl, _, _ = settle_pnl(row, ctx, c.expiry, cfg, "expiry")
                msg += ", held to expiry"
            assert abs(pnl - r.option_pnl_net) < 1, (pnl, r.option_pnl_net)
            msg += f"; P&L Rs {pnl:,.2f} = backtest Rs {r.option_pnl_net:,.2f}"
        else:
            msg += f" ({o['reason']}) = backtest skip ({r.skip_reason})"
        out.append(msg + ": OK")
    LIVE.mkdir(parents=True, exist_ok=True)
    (LIVE / "checks.md").write_text("\n".join(out) + "\n")
    logger.info("\n".join(out))
