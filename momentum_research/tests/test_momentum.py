import numpy as np
import pandas as pd
import pytest

from momentum.transform.backtest import drawdown, trade_costs
from momentum.transform.diagnostics import nw_t
from momentum.transform.momentum import asof_price
from momentum.transform.portfolio import select

COSTS = {
    "costs": {
        "brokerage": 0.0,
        "stt": 0.001,
        "exchange_txn": 0.0000297,
        "sebi_fee": 0.000001,
        "stamp_duty_buy": 0.00015,
        "gst": 0.18,
        "dp_charge_per_sell": 15.93,
        "slippage_tiers": [[25, 5], [10, 10], [5, 20], [0, 20]],
    },
    "backtest": {"scenarios": {"base": {"statutory": True, "slippage_multiple": 1}}},
}


def test_signal_price_ignores_later_prices_and_stale_quotes():
    days = pd.bdate_range("2020-01-01", periods=30)
    prices = pd.Series(np.arange(100.0, 130.0), days)
    t = days[19]
    price, when = asof_price(prices, t, days, max_stale=5)
    shocked = prices.copy()
    shocked[days > t] *= 10  # a jump after the signal date
    assert asof_price(shocked, t, days, max_stale=5) == (price, when)
    assert (price, when) == (119.0, t)

    stale = prices.copy()
    stale[days[10] :] = np.nan  # last trade 9 days before t
    price, when = asof_price(stale, t, days, max_stale=5)
    assert np.isnan(price) and when == days[9]


def test_costs_scale_with_traded_value_on_both_sides():
    liquid = 30e7  # Rs 30 crore median traded value: 5 bps slippage
    buy = trade_costs(COSTS, "buy", 100_000, liquid, "base")
    sell = trade_costs(COSTS, "sell", 100_000, liquid, "base")
    assert buy["slippage"] == pytest.approx(100_000 * 5 / 1e4)
    assert buy["stt"] == sell["stt"] == pytest.approx(100.0)  # STT on both sides
    assert buy["stamp"] > 0 and sell["stamp"] == 0  # stamp duty on buys only
    assert sell["dp"] == 15.93 and buy["dp"] == 0  # DP charge per sell
    doubled = trade_costs(COSTS, "buy", 200_000, liquid, "base")
    assert doubled["total"] == pytest.approx(2 * buy["total"])
    illiquid = trade_costs(COSTS, "buy", 100_000, 1e7, "base")
    assert illiquid["slippage"] == pytest.approx(4 * buy["slippage"])  # 20 bps tier


def test_buffer_keeps_holdings_and_sector_cap_binds():
    ranked = pd.DataFrame({"file_id": list("ABCDEF"), "rank": [1, 2, 3, 4, 5, 6]})
    sector = {"A": "x", "B": "x", "C": "x", "D": "y", "E": "y", "F": "z"}
    # F is held and still within the buffer (rank 6 <= 6), so it is kept ahead of new names
    chosen = select(ranked, held=["F"], forced=[], sector=sector, n=3, buffer=6, cap=2)
    assert chosen == ["F", "A", "B"]
    # with no holdings the third 'x' name is skipped because the sector is full
    assert select(ranked, [], [], sector, n=3, buffer=6, cap=2) == ["A", "B", "D"]


def test_drawdown_and_newey_west_on_known_series():
    days = pd.bdate_range("2020-01-01", periods=5)
    eq = pd.DataFrame({"equity": [100.0, 120.0, 90.0, 95.0, 130.0]}, days)
    dd, info = drawdown(eq)
    assert dd.min() == pytest.approx(-0.25)
    x = np.array([0.01, -0.02, 0.03, 0.00, 0.02])
    # with no lags the Newey-West t is mean / (population sd / sqrt(n))
    assert nw_t(x, 0) == pytest.approx(x.mean() / (x.std() / np.sqrt(len(x))))


def test_universe_is_point_in_time():
    from momentum.transform.momentum import members_at

    jan, feb = pd.Timestamp("2020-01-31"), pd.Timestamp("2020-02-29")
    base = pd.DataFrame({
        "date": [jan, jan, feb, feb],
        "file_id": ["A", "B", "A", "B"],
        "member": [True, True, False, True],  # A left the index in February
        "excluded_reason": [None, None, None, None],
    })  # fmt: skip
    assert set(members_at(base, pd.Timestamp("2020-01-31")).file_id) == {"A", "B"}
    # a signal on any day in February sees only February's members
    assert set(members_at(base, pd.Timestamp("2020-02-28")).file_id) == {"B"}
