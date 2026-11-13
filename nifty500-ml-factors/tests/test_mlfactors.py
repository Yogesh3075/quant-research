import numpy as np
import pandas as pd
import pytest

from mlfactors.data import build_panel, members_on
from mlfactors.metrics import max_drawdown, sharpe
from mlfactors.models import training_window
from mlfactors.portfolio import FEE, backtest

N_STOCKS = 4


def write_inputs(data_dir, prices: pd.DataFrame) -> None:
    ids = list(prices.columns)
    prices.to_parquet(data_dir / "adj_close.parquet")
    pd.DataFrame(1e9, prices.index, ids).to_parquet(data_dir / "traded_value.parquet")
    pd.DataFrame({"stock_id": ids, "file_id": ids}).to_csv(data_dir / "securities.csv", index=False)
    pd.DataFrame({"stock_id": ids, "industry": ["A", "A", "B", "B"]}).to_csv(
        data_dir / "industry.csv", index=False
    )
    membership = {"stock_id": ids, "start_date": "2009-01-01", "end_date": "", "eligible": True}
    pd.DataFrame({**membership, "industry": "A"}).to_csv(data_dir / "membership.csv", index=False)
    pd.DataFrame(columns=["date", "file_id"]).to_csv(data_dir / "return_overrides.csv", index=False)


def synthetic_prices(days: pd.DatetimeIndex) -> pd.DataFrame:
    rng = np.random.default_rng(0)
    steps = rng.normal(0.0005, 0.01, (len(days), N_STOCKS))
    return pd.DataFrame(
        100 * np.exp(steps.cumsum(axis=0)), days, [f"S{i}" for i in range(N_STOCKS)]
    )


def test_features_ignore_prices_after_the_feature_date(tmp_path):
    days = pd.bdate_range("2010-01-01", "2011-06-30")
    prices = synthetic_prices(days)
    (tmp_path / "a").mkdir()
    (tmp_path / "b").mkdir()
    write_inputs(tmp_path / "a", prices)
    shocked = prices.copy()
    shocked.loc["2011-05-02":] *= 3.0  # a large move after the April month-end
    write_inputs(tmp_path / "b", shocked)

    base = build_panel(tmp_path / "a").set_index(["date", "file_id"])
    after = build_panel(tmp_path / "b").set_index(["date", "file_id"])
    feature_cols = ["mom_12_1", "mom_6_1", "ret_3m", "ret_1m", "vol_12m", "vol_1m", "beta_ew"]
    april = pd.Timestamp("2011-04-29")
    pd.testing.assert_frame_equal(base.loc[april, feature_cols], after.loc[april, feature_cols])
    # the target is the only column allowed to see the following month
    assert not np.allclose(base.loc[april, "fwd_ret"], after.loc[april, "fwd_ret"])


def test_stock_is_not_a_member_on_or_after_its_exit_date():
    membership = pd.DataFrame({
        "file_id": ["X", "Y"],
        "start_date": pd.to_datetime(["2015-01-01", "2015-01-01"]),
        "end_date": pd.to_datetime(["2016-03-31", None]),
    })  # fmt: skip
    assert set(members_on(membership, pd.Timestamp("2016-03-30")).file_id) == {"X", "Y"}
    assert set(members_on(membership, pd.Timestamp("2016-03-31")).file_id) == {"Y"}
    assert set(members_on(membership, pd.Timestamp("2017-01-31")).file_id) == {"Y"}


def test_training_window_drops_the_test_year_and_one_embargo_month():
    panel = pd.DataFrame({"date": pd.date_range("2012-01-31", "2015-12-31", freq="ME")})
    train = training_window(panel, 2015)
    assert train.date.max() == pd.Timestamp("2014-11-30")


def test_costs_are_charged_on_both_sides_of_a_switch():
    month_ends = pd.to_datetime(["2020-01-31", "2020-02-29"])
    panel = pd.DataFrame({
        "date": np.repeat(month_ends, 2),
        "file_id": ["A", "B", "A", "B"],
        "score": [1.0, np.nan, np.nan, 1.0],  # hold A, then switch to B
        "fwd_ret": [0.0, 0.0, 0.0, 0.0],
        "industry": ["X", "Y", "X", "Y"],
        "traded_value_63d": [1e9, 1e9, 1e9, 1e9],  # >= 25 crore: 5 bps slippage
    })  # fmt: skip
    result = backtest(panel, "score")
    per_side = FEE + 0.0005
    assert result.cost.iloc[0] == pytest.approx(1.0 * per_side)  # buy A
    assert result.cost.iloc[1] == pytest.approx(2.0 * per_side)  # sell A and buy B
    assert result.turnover.iloc[1] == pytest.approx(1.0)


def test_sharpe_and_max_drawdown_on_a_known_series():
    returns = pd.Series([0.10, -0.20, 0.05, 0.05])
    assert sharpe(returns) == pytest.approx(returns.mean() / returns.std(ddof=1) * np.sqrt(12))
    # peak 1.10, trough 0.88: a 20% drawdown
    assert max_drawdown(returns) == pytest.approx(-0.20)
