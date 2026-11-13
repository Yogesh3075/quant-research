import numpy as np
import pandas as pd
import pytest

from pairs import universe
from pairs.metrics import max_drawdown, sharpe
from pairs.original.backtest import LOOKBACK, run_stat_arb_backtest
from pairs.selection import half_life
from pairs.trading import FEE, LEG, SLIPPAGE, trade_window

DAYS = pd.bdate_range("2020-01-01", periods=60)


def use_universe(monkeypatch, prices: pd.DataFrame) -> None:
    membership = pd.DataFrame({
        "file_id": list(prices.columns),
        "start_date": pd.Timestamp("2015-01-01"),
        "end_date": pd.NaT,
    })  # fmt: skip
    monkeypatch.setattr(universe, "PRICES", prices)
    monkeypatch.setattr(universe, "MEMBERSHIP", membership)


def pair_row(**overrides) -> pd.DataFrame:
    row = {
        "formation_date": DAYS[0], "y": "Y", "x": "X", "pair": "Y-X", "sector": "S",
        "hedge_ratio": 1.0, "alpha": 0.0, "mu": 0.0, "sd": 0.01, "p_value": 0.01,
        "half_life": 10.0, "fo_eligible": True, "bucket_y": "large", "bucket_x": "large",
    }  # fmt: skip
    return pd.DataFrame([{**row, **overrides}])


def diverging_prices() -> pd.DataFrame:
    """Y jumps 3% above X on day 10 (z = 3), converges on day 20."""
    y = np.full(len(DAYS), 100.0)
    y[10:20] = 103.0
    return pd.DataFrame({"Y": y, "X": 100.0}, index=DAYS)


def test_trade_fills_at_the_next_close_and_ignores_later_prices(monkeypatch):
    prices = diverging_prices()
    use_universe(monkeypatch, prices)
    trades, _ = trade_window(pair_row(), DAYS[0] - pd.Timedelta(days=1), DAYS[-1], entry_z=2.0)
    first = trades[0]
    assert first["entry_date"] == DAYS[11]  # signal at day 10's close, filled at day 11's
    assert first["exit_date"] == DAYS[21]

    shocked = prices.copy()
    shocked.loc[DAYS[30] :, "Y"] *= 2.0  # a large move after the first trade closed
    use_universe(monkeypatch, shocked)
    trades_after, _ = trade_window(pair_row(), DAYS[0] - pd.Timedelta(days=1), DAYS[-1], 2.0)
    assert trades_after[0]["net_pnl"] == pytest.approx(first["net_pnl"])


def test_costs_are_charged_on_both_legs_at_entry_and_exit(monkeypatch):
    use_universe(monkeypatch, diverging_prices())
    pair = pair_row(bucket_y="large", bucket_x="small")
    trades, _ = trade_window(pair, DAYS[0] - pd.Timedelta(days=1), DAYS[-1], entry_z=2.0)
    t = trades[0]
    per_side = (FEE + SLIPPAGE["large"]) + (FEE + SLIPPAGE["small"])
    # entry at 103/100 and exit at 100/100: each leg trades about LEG rupees each way
    assert t["costs"] == pytest.approx(2 * LEG * per_side, rel=0.02)
    assert t["gross_pnl"] - t["costs"] == pytest.approx(t["net_pnl"])


def test_stock_is_out_of_the_universe_after_its_exit_date(monkeypatch):
    membership = pd.DataFrame({
        "file_id": ["A", "B"],
        "start_date": pd.to_datetime(["2015-01-01", "2015-01-01"]),
        "end_date": pd.to_datetime(["2020-06-30", None]),
    })  # fmt: skip
    monkeypatch.setattr(universe, "MEMBERSHIP", membership)
    assert set(universe.members_on(pd.Timestamp("2020-06-29")).file_id) == {"A", "B"}
    assert set(universe.members_on(pd.Timestamp("2020-07-01")).file_id) == {"B"}
    # known issue, documented in the README: the exit day itself still counts as a member day
    assert "A" in set(universe.members_on(pd.Timestamp("2020-06-30")).file_id)


def test_half_life_of_an_ar1_spread():
    rng = np.random.default_rng(0)
    phi, n = 0.9, 20_000
    spread = np.zeros(n)
    for i in range(1, n):
        spread[i] = phi * spread[i - 1] + rng.normal()
    assert half_life(spread) == pytest.approx(np.log(2) / -np.log(phi), rel=0.05)
    explosive = 1.05 ** np.arange(100)  # grows away from its mean: no half-life
    assert half_life(explosive) == np.inf


def test_original_engine_has_no_look_ahead():
    rng = np.random.default_rng(1)
    days = pd.bdate_range("2019-01-01", periods=300)
    x = pd.Series(100 * np.exp(np.cumsum(rng.normal(0, 0.01, 300))), days)
    y = x * np.exp(rng.normal(0, 0.02, 300))
    base, _ = run_stat_arb_backtest(y, x)
    y_shocked = y.copy()
    y_shocked.iloc[200:] *= 1.5
    after, _ = run_stat_arb_backtest(y_shocked, x)
    # returns up to day 199 depend only on prices up to day 199
    pd.testing.assert_series_equal(base.iloc[:200], after.iloc[:200])
    assert (base.iloc[:LOOKBACK] == 0).all()


def test_sharpe_and_max_drawdown_on_a_known_series():
    r = pd.Series([0.10, -0.20, 0.05, 0.05])
    assert sharpe(r) == pytest.approx(r.mean() / r.std() * np.sqrt(252))
    assert max_drawdown(r) == pytest.approx(-0.20)
    assert sharpe(pd.Series([0.0, 0.0])) == 0.0
