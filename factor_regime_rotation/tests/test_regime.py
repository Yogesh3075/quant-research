import numpy as np
import pandas as pd
import pytest

from regime.backtest import metrics, nw_tstat, simulate, weights_defensive, weights_regime

CFG = {
    "regime": {"trend_months": 12, "vol_days": 63, "min_median_months": 36},
    "traded": ["momentum", "quality", "value", "lowvol"],
    "backtest": {"top_n": 2, "min_regime_months": 12, "min_history_months": 60},
    "hmm": {
        "states": 2,
        "covariance": "full",
        "iterations": 50,
        "seeds": [0, 1],
        "stressed_above": 0.5,
        "defensive": ["quality", "lowvol"],
    },
    "calendar": "nifty50",
}


def daily_index(start: str, months: int) -> pd.Series:
    days = pd.bdate_range(start, periods=months * 21)
    rng = np.random.default_rng(1)
    return pd.Series(100 * np.exp(np.cumsum(rng.normal(0.0004, 0.01, len(days)))), days)


def test_regime_at_t_ignores_later_prices():
    from regime.regimes import make_regimes

    daily = daily_index("2005-01-03", 80)
    month_ends = daily.groupby(daily.index.to_period("M")).tail(1).index
    t = month_ends[60]
    base = make_regimes(daily.reindex(month_ends), daily, CFG).loc[t]
    shocked = daily.copy()
    shocked[shocked.index > t] *= 0.5  # a crash after t
    after = make_regimes(shocked.reindex(month_ends), shocked, CFG).loc[t]
    pd.testing.assert_series_equal(base, after)


def test_regime_weights_ignore_returns_after_t():
    months = pd.date_range("2010-01-31", periods=48, freq="ME")
    rng = np.random.default_rng(2)
    rets = pd.DataFrame(rng.normal(0.01, 0.04, (48, 4)), months, CFG["traded"])
    labels = pd.Series(np.where(np.arange(48) % 3 == 0, "up/high", "up/low"), months)
    t = months[36]
    base, _ = weights_regime(rets, labels, "up/low", t, CFG)
    future = rets.copy()
    future.loc[future.index > t, "value"] = 0.50  # value soars after t
    after, _ = weights_regime(future, labels, "up/low", t, CFG)
    pd.testing.assert_series_equal(base, after)
    assert base.sum() == pytest.approx(1.0)


def test_hmm_is_refitted_on_data_up_to_each_decision_date(monkeypatch):
    import regime.hmm_regime as hmm

    daily = daily_index("2005-01-03", 66).rename("nifty50").to_frame()
    month_ends = daily.groupby(daily.index.to_period("M")).tail(1).index
    monthly = daily.reindex(month_ends)
    seen = []

    def spy(X, cfg):
        seen.append(X.index.max())
        return {"p_stressed": 0.0}, pd.Series("calm", index=X.index)

    monkeypatch.setattr(hmm, "state_at", spy)
    states, _ = hmm.fit_all(monthly, daily, CFG)
    decisions = list(states.index)
    assert decisions == list(month_ends[60:-1])
    # each fit sees nothing after its own decision date
    assert seen == decisions


def test_switching_cost_scales_with_turnover():
    months = pd.date_range("2020-01-31", periods=3, freq="ME")
    rets = pd.DataFrame(0.0, months, CFG["traded"])
    w = pd.DataFrame(
        [[1.0, 0.0, 0.0, 0.0], [0.0, 1.0, 0.0, 0.0]], index=months[:2], columns=CFG["traded"]
    )
    no_expense = pd.Series(0.0, CFG["traded"])
    out = simulate(w, rets, switch=0.002, expense=no_expense)
    assert out.turnover.tolist() == [0.0, 1.0]  # full switch = 100% one-way turnover
    assert out.ret.iloc[1] == pytest.approx(-0.002)
    doubled = simulate(w, rets, switch=0.004, expense=no_expense)
    assert doubled.ret.iloc[1] == pytest.approx(2 * out.ret.iloc[1])


def test_defensive_switch_goes_to_quality_and_low_vol_only_when_stressed():
    stressed = weights_defensive(0.9, CFG)
    calm = weights_defensive(0.1, CFG)
    assert stressed.to_dict() == {"momentum": 0.0, "quality": 0.5, "value": 0.0, "lowvol": 0.5}
    assert set(calm) == {0.25}


def test_metrics_on_a_known_series():
    months = pd.date_range("2020-01-31", periods=4, freq="ME")
    r = pd.Series([0.10, -0.20, 0.05, 0.05], months)
    m = metrics(r, rf=0.0)
    assert m["max_dd_%"] == pytest.approx(-20.0)
    assert m["sharpe"] == pytest.approx(r.mean() / r.std() * np.sqrt(12))
    x = np.array([0.01, -0.02, 0.03, 0.00, 0.02])
    # with no lags the Newey-West t is the plain t with the population variance
    assert nw_tstat(x, 0) == pytest.approx(x.mean() / (x.std() / np.sqrt(len(x))))
