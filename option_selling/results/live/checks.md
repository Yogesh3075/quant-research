# Live tool checks

- live.py never reads `iv_minus_future_rv_pts`; context() truncates option and index data at the given date and asserts it.
- frozen config hash check fails loudly on a modified config: "FROZEN CONFIG CHANGED for _t: results/live/_tmp_config.yaml has SHA-256 9f37a2c3c5fde2e234..."
- e1f1 2011-11-25 (design): decision TRADE, strikes 4500/4200, units 656.910 = backtest 656.910, held to expiry; P&L Rs 34,288.19 = backtest Rs 34,288.19: OK
- e1f1 2014-09-01 (design): decision SKIP (IV-RV gap 0.0063 <= expanding median 0.0216) = backtest skip (filtered: IV - RV gap not above the expanding median): OK
- e1f1 2013-02-01 (design): decision TRADE, strikes 5700/5400, units 630.516 = backtest 630.516, stop trigger 2013-02-26 = backtest, exit 2013-02-27; P&L Rs -3,413.25 = backtest Rs -3,413.25: OK
- p1 2020-07-31 (validation): decision TRADE, strikes 10500/9950, units 250.534 = backtest 250.534, held to expiry; P&L Rs 17,046.66 = backtest Rs 17,046.66: OK
- p1 2022-04-29 (validation): decision SKIP (prem_ratio 0.083 < 0.12) = backtest skip (filtered: prem_ratio 0.083 < 0.12): OK
- e1f1 2021-07-30 (validation): decision TRADE, strikes 14950/14200, units 172.515 = backtest 172.515, held to expiry; P&L Rs 3,084.67 = backtest Rs 3,084.67: OK
