from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from optsell.backtest import intrinsic, rate_on
from optsell.data import monthly_expiries
from optsell.phase3 import fees, stop

COSTS = {
    "slip_min": 0.5,
    "slip_pct": 0.03,
    "stt_sell": [["2008-01-01", 0.00017], ["2016-06-01", 0.0005]],
    "stt_itm": 0.00125,
    "brokerage": 20,
    "exch": [["2008-01-01", 0.0005]],
    "sebi": 0.000001,
    "stamp": 0.00003,
    "gst": 0.18,
}
CFG = {"phase3": {"stop_mult": 2.0}, "costs": COSTS}
DAYS = pd.bdate_range("2020-03-02", periods=12)
CONTRACT = DAYS[-1]
SHORT = {"opt": "P", "k": 95, "side": -1, "px": 2.0, "close": 2.0}
LONG = {"opt": "P", "k": 90, "side": 1, "px": 1.0, "close": 1.0}


def option_rows(dates, expiries):
    return pd.DataFrame({
        "instr": "OPTIDX", "date": pd.to_datetime(dates), "expiry": pd.to_datetime(expiries),
    })  # fmt: skip


def test_monthly_expiry_is_the_last_expiry_that_actually_traded():
    # January: weekly expiries; the monthly one is the last (30 Jan)
    jan = option_rows(
        ["2020-01-02", "2020-01-09", "2020-01-16", "2020-01-23", "2020-01-30"],
        ["2020-01-09", "2020-01-09", "2020-01-16", "2020-01-23", "2020-01-30"],
    )
    jan_last = option_rows(["2020-01-30", "2020-01-30"], ["2020-01-30", "2020-02-26"])
    # February: listed for the 27th, but a holiday moved the last trading day to the 26th
    feb = option_rows(["2020-02-03", "2020-02-26"], ["2020-02-27", "2020-02-26"])
    march = option_rows(["2020-03-26"], ["2020-03-26"])
    fo = pd.concat([jan, jan_last, feb, march], ignore_index=True)
    expiries = list(monthly_expiries(fo))
    assert expiries == [pd.Timestamp(d) for d in ("2020-01-30", "2020-02-26", "2020-03-26")]


def book(short_closes, long_closes):
    """Daily closes indexed like marking.book: (contract, PE/CE, strike) -> series by date."""
    idx = pd.MultiIndex.from_tuples(
        [(CONTRACT, "PE", 95, d) for d in DAYS] + [(CONTRACT, "PE", 90, d) for d in DAYS]
    )
    return pd.Series(np.r_[short_closes, long_closes], index=idx)


def run_stop(short_closes, long_closes):
    trade = {"units": 100.0, "credit": 1.0}  # net credit 1 per unit: stop at a loss of 2 per unit
    cycle = SimpleNamespace(contract=CONTRACT, settle=100.0)
    return stop([SHORT, LONG], trade, cycle, DAYS, {"bk": book(short_closes, long_closes)}, CFG)


def test_stop_triggers_at_twice_the_credit_and_exits_next_close():
    short = np.full(12, 2.0)
    long = np.full(12, 1.0)
    short[4:] = 4.0  # loss on day 4: -(4 - 2) + (1 - 1) = -2 per unit = 2x credit
    result = run_stop(short, long)
    assert result["trigger"] == DAYS[4]
    assert result["exit"] == DAYS[5]  # filled at the next close, not the trigger close
    assert result["trigger_pnl"] == pytest.approx(-200.0)

    almost = short.copy()
    almost[4:] = 3.9  # a loss of 1.9x credit never triggers
    assert run_stop(almost, long) is None


def test_stop_decision_ignores_prices_after_the_trigger():
    short, long = np.full(12, 2.0), np.full(12, 1.0)
    short[4:] = 4.0
    shocked = short.copy()
    shocked[6:] = 50.0  # a crash after the stop fired
    a, b = run_stop(short, long), run_stop(shocked, long)
    assert a["trigger"] == b["trigger"] and a["trigger_pnl"] == b["trigger_pnl"]
    # a trigger on the day before expiry is ignored: the position is held to settlement
    late = np.full(12, 2.0)
    late[10:] = 10.0
    assert run_stop(late, long) is None


def test_charges_on_both_legs_follow_the_dated_rates():
    day = pd.Timestamp("2020-03-02")
    sell = (day, 2.0, 100.0, True)  # short leg: premium 200
    buy = (day, 1.0, 100.0, False)  # long leg: premium 100
    items = fees([sell, buy], itm=0.0, cc=COSTS)
    assert items["brokerage"] == 2 * 20  # one order per leg
    assert items["stt"] == pytest.approx(0.0005 * 200)  # STT on the sold premium only
    assert items["stamp_duty"] == pytest.approx(0.00003 * 100)  # stamp duty on the bought premium
    assert items["exchange_charges"] == pytest.approx(0.0005 * 300)  # both legs
    assert rate_on(COSTS["stt_sell"], pd.Timestamp("2016-05-31")) == 0.00017


def test_intrinsic_value_at_settlement():
    assert intrinsic("P", 95, 90.0) == 5.0
    assert intrinsic("P", 95, 100.0) == 0.0
    assert intrinsic("C", 105, 110.0) == 5.0
