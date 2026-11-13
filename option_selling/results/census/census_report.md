# Strategy census report

Design: 132 cycles, entries 2008-02-01 to 2018-12-28. One fixed version per family (see `preregistration.md`); headline = option-only return (no cash interest; S10/S11 include the index leg, S12 the futures hedge), Sharpe without risk-free deduction. ref_* are references, not trials.

## Data checks (design)

- Far-month (S9): the near-month ATM put strike also traded in the far month on 97 of 132 cycles (73%). **Fewer than 80% of cycles: S9 results rest on a fallback strike or skips in many months.**
- Futures (S12): near-month NIFTY future close missing on 0 cycle-days. The hedge future is each cycle's own contract, so the roll is on each expiry day (2008-02-28 to 2019-01-31, 132 rolls).

## Design results

| strategy                  | option CAGR   |   option Sharpe | worst month   | worst 3m   | CVaR95   | CVaR99   | max DD   |   skew | win rate   | avg win   | avg loss   | break-even win rate   | break-even margin   | avg credit % cap   | avg risk % cap   | avg margin % cap   |   months traded |   months skipped |   stops |   stops helped | costs % gross credit   | total CAGR (cash 6.5%)   |   corr with base |   NW t vs base | DSR   |
|:--------------------------|:--------------|----------------:|:--------------|:-----------|:---------|:---------|:---------|-------:|:-----------|:----------|:-----------|:----------------------|:--------------------|:-------------------|:-----------------|:-------------------|----------------:|-----------------:|--------:|---------------:|:-----------------------|:-------------------------|-----------------:|---------------:|:------|
| s1_short_put              | 1.4%          |            0.3  | -14.1%        | -12.9%     | -3.9%    | -8.6%    | -14.1%   |  -6.74 | 87.1%      | 0.4%      | -2.0%      | 81.8%                 | 5.3%                | 0.4%               | 10.0%            | 7.8%               |             132 |                0 |       0 |              0 | 3.5%                   | 7.6%                     |             0.5  |          -0.49 | 2.6%  |
| s1_short_put_e1           | 2.5%          |            0.8  | -6.3%         | -4.9%      | -2.1%    | -4.0%    | -6.3%    |  -2.25 | 81.8%      | 0.5%      | -0.9%      | 66.3%                 | 15.5%               | 0.4%               | 10.0%            | 7.8%               |             132 |                0 |      21 |             11 | 5.0%                   | 8.9%                     |             0.61 |          -0    | 26.5% |
| s2_short_call             | 0.2%          |            0.07 | -9.0%         | -15.2%     | -4.2%    | -6.5%    | -16.0%   |  -2.63 | 83.3%      | 0.4%      | -1.9%      | 82.2%                 | 1.1%                | 0.5%               | 10.0%            | 10.5%              |             132 |                0 |       0 |              0 | 3.6%                   | 6.2%                     |            -0.09 |          -0.74 | 0.1%  |
| s2_short_call_e1          | -0.5%         |           -0.09 | -10.2%        | -15.9%     | -3.8%    | -7.0%    | -22.6%   |  -3.19 | 73.5%      | 0.4%      | -1.3%      | 75.5%                 | -2.0%               | 0.5%               | 10.0%            | 10.5%              |             132 |                0 |      30 |             10 | 6.3%                   | 5.5%                     |            -0.12 |          -1    | 0.0%  |
| s3_short_straddle         | -0.2%         |            0.01 | -14.4%        | -12.4%     | -5.4%    | -10.2%   | -21.7%   |  -1.18 | 55.3%      | 1.3%      | -1.6%      | 55.1%                 | 0.2%                | 2.3%               | 10.0%            | 14.8%              |             132 |                0 |       0 |              0 | 3.2%                   | 5.4%                     |             0.39 |          -0.98 | 0.0%  |
| s3_short_straddle_e1      | -0.6%         |           -0.02 | -16.9%        | -15.0%     | -5.8%    | -11.4%   | -22.0%   |  -1.96 | 55.3%      | 1.3%      | -1.7%      | 55.8%                 | -0.5%               | 2.3%               | 10.0%            | 14.8%              |             132 |                0 |       4 |              1 | 3.6%                   | 5.1%                     |             0.37 |          -1.05 | 0.0%  |
| s4_short_strangle         | 2.0%          |            0.31 | -14.7%        | -11.9%     | -4.8%    | -10.3%   | -14.7%   |  -2.03 | 77.3%      | 0.8%      | -1.8%      | 70.1%                 | 7.2%                | 0.9%               | 10.0%            | 16.3%              |             132 |                0 |       0 |              0 | 3.6%                   | 7.6%                     |             0.35 |          -0.14 | 1.3%  |
| s4_short_strangle_e1      | 2.4%          |            0.44 | -8.0%         | -8.1%      | -3.7%    | -6.9%    | -8.1%    |   0.8  | 72.7%      | 0.8%      | -1.3%      | 62.5%                 | 10.2%               | 0.9%               | 10.0%            | 16.3%              |             132 |                0 |      25 |             12 | 5.0%                   | 8.2%                     |             0.38 |           0.03 | 1.8%  |
| s5_bear_call_spread       | -3.3%         |           -0.28 | -10.0%        | -27.2%     | -10.0%   | -10.0%   | -45.3%   |  -2.32 | 81.7%      | 0.8%      | -5.0%      | 85.7%                 | -4.0%               | 0.9%               | 10.0%            | 10.0%              |             131 |                1 |       0 |              0 | 8.2%                   | 2.6%                     |            -0.17 |          -1.23 | 0.0%  |
| s5_bear_call_spread_e1    | -4.5%         |           -0.48 | -10.9%        | -24.0%     | -7.9%    | -10.5%   | -49.5%   |  -1.9  | 70.2%      | 0.8%      | -3.2%      | 78.9%                 | -8.7%               | 0.9%               | 10.0%            | 10.0%              |             131 |                1 |      36 |             10 | 15.1%                  | 1.4%                     |            -0.22 |          -1.78 | 0.0%  |
| s6_iron_butterfly         | -22.3%        |           -0.74 | -10.3%        | -27.5%     | -10.2%   | -10.3%   | -96.7%   |   1.06 | 37.9%      | 6.9%      | -7.1%      | 50.4%                 | -12.6%              | 13.1%              | 10.0%            | 10.0%              |             132 |                0 |       0 |              0 | 8.4%                   | -17.5%                   |             0.27 |          -2.84 | 0.0%  |
| s6_iron_butterfly_e1      | -22.3%        |           -0.74 | -10.3%        | -27.5%     | -10.2%   | -10.3%   | -96.7%   |   1.06 | 37.9%      | 6.9%      | -7.1%      | 50.4%                 | -12.6%              | 13.1%              | 10.0%            | 10.0%              |             132 |                0 |       0 |              0 | 8.4%                   | -17.5%                   |             0.27 |          -2.84 | 0.0%  |
| s7_cash_secured_put       | 2.1%          |            0.28 | -25.2%        | -23.2%     | -7.2%    | -15.6%   | -25.2%   |  -6.81 | 87.1%      | 0.8%      | -3.7%      | 82.3%                 | 4.8%                | 0.8%               | 19.2%            | 15.0%              |             132 |                0 |       0 |              0 | 3.3%                   | 7.9%                     |             0.52 |           0.03 | 2.2%  |
| s7_cash_secured_put_e1    | 4.3%          |            0.8  | -11.1%        | -8.8%      | -3.9%    | -7.3%    | -11.1%   |  -2.69 | 81.8%      | 0.8%      | -1.7%      | 67.3%                 | 14.6%               | 0.8%               | 19.2%            | 15.0%              |             132 |                0 |      21 |             11 | 4.8%                   | 10.3%                    |             0.63 |           1.06 | 26.4% |
| s8_put_ratio              | 1.9%          |            0.57 | -0.8%         | -1.3%      | -0.6%    | -0.7%    | -5.2%    |   2.85 | 23.1%      | 1.4%      | -0.2%      | 13.3%                 | 9.8%                | -0.2%              | 10.0%            | 15.2%              |             130 |                2 |       0 |              0 | 21.5%                  | 7.7%                     |            -0.81 |          -0.2  | 1.7%  |
| s8_put_ratio_e1           | 1.2%          |            0.35 | -2.8%         | -1.9%      | -1.0%    | -1.8%    | -5.2%    |   2.51 | 19.2%      | 1.6%      | -0.3%      | 13.8%                 | 5.4%                | -0.2%              | 10.0%            | 15.2%              |             130 |                2 |       6 |              0 | 25.7%                  | 6.9%                     |            -0.83 |          -0.43 | 0.4%  |
| s9_calendar               | -45.2%        |           -1.37 | -49.4%        | -63.1%     | -34.1%   | -47.1%   | -99.9%   |  -1.24 | 31.8%      | 5.8%      | -8.9%      | 60.5%                 | -28.7%              | -10.0%             | 10.0%            | 10.0%              |             132 |                0 |       0 |              0 | 27.8%                  | -41.7%                   |             0.41 |          -5.13 | 0.0%  |
| s10_covered_call          | 8.8%          |            0.55 | -25.3%        | -32.2%     | -12.8%   | -19.8%   | -38.8%   |  -1.21 | 62.1%      | 4.0%      | -4.3%      | 51.9%                 | 10.3%               | 0.6%               | 39.4%            | 0.0%               |             132 |                0 |       0 |              0 | 4.6%                   | 8.8%                     |             0.64 |           1.72 | 6.6%  |
| s11_collar                | 6.2%          |            0.5  | -9.7%         | -15.8%     | -7.5%    | -8.9%    | -28.9%   |  -0.18 | 58.3%      | 3.4%      | -3.4%      | 49.7%                 | 8.6%                | -0.2%              | 40.2%            | 0.0%               |             132 |                0 |       0 |              0 | 23.5%                  | 6.2%                     |             0.51 |           1.27 | 3.5%  |
| s12_delta_hedged_straddle | 1.3%          |            0.3  | -8.2%         | -9.3%      | -3.6%    | -6.3%    | -9.7%    |  -1.74 | 59.1%      | 0.9%      | -1.0%      | 52.8%                 | 6.3%                | 4.4%               |                  | 40.1%              |             132 |                0 |       0 |              0 | 5.4%                   | 5.4%                     |             0.35 |          -0.44 | 1.0%  |
| ref_base                  | 2.2%          |            0.32 | -10.0%        | -9.0%      | -7.5%    | -10.0%   | -18.8%   |  -2.73 | 86.2%      | 0.9%      | -4.4%      | 82.1%                 | 4.0%                | 0.9%               | 10.0%            | 10.0%              |             130 |                2 |       0 |              0 | 8.4%                   | 8.4%                     |             1    |                | 1.5%  |
| ref_iron_condor           | -1.2%         |           -0.02 | -10.1%        | -23.2%     | -10.0%   | -10.1%   | -41.3%   |  -0.82 | 72.1%      | 1.8%      | -4.7%      | 72.5%                 | -0.4%               | 2.1%               | 10.0%            | 10.0%              |             129 |                3 |       0 |              0 | 8.3%                   | 4.8%                     |             0.47 |          -0.86 | 0.0%  |
| ref_strangle              | 2.2%          |            0.27 | -22.9%        | -18.7%     | -8.0%    | -15.7%   | -22.9%   |  -3.4  | 77.3%      | 1.2%      | -3.1%      | 71.9%                 | 5.4%                | 1.4%               | 18.5%            | 30.0%              |             132 |                0 |       0 |              0 | 3.4%                   | 7.0%                     |             0.4  |           0.1  | 1.1%  |
| ref_e1f1                  | 3.2%          |            0.73 | -5.2%         | -8.1%      | -3.5%    | -4.5%    | -11.8%   |  -0.92 | 77.3%      | 1.3%      | -1.9%      | 60.3%                 | 17.0%               | 1.2%               | 10.0%            | 10.0%              |              66 |               66 |      13 |              6 | 11.7%                  | 9.8%                     |             0.63 |           0.4  | 16.8% |

Avg risk: defined-risk = max loss; others = loss at the worse of -25% / +20% at settlement (S10/S11 incl. the index leg; S12 not computed). Costs as % of the absolute gross premium.

Sizing notes (cycles): s8_put_ratio_e1: net debit: no stop (119)

## Reading (design)

- Earn after costs (option-only CAGR above zero, i.e. beat cash): s1_short_put, s1_short_put_e1, s2_short_call, s4_short_strangle, s4_short_strangle_e1, s7_cash_secured_put, s7_cash_secured_put_e1, s8_put_ratio, s8_put_ratio_e1, s10_covered_call, s11_collar, s12_delta_hedged_straddle. Negative: s2_short_call_e1, s3_short_straddle, s3_short_straddle_e1, s5_bear_call_spread, s5_bear_call_spread_e1, s6_iron_butterfly, s6_iron_butterfly_e1, s9_calendar.
- Worst tails (CVaR 99%): s9_calendar -47.1% (worst month -49.4%); s10_covered_call -19.8% (worst month -25.3%); s7_cash_secured_put -15.6% (worst month -25.2%); s3_short_straddle_e1 -11.4% (worst month -16.9%); s5_bear_call_spread_e1 -10.5% (worst month -10.9%).
- Stop by family (option-only Sharpe / worst month, without -> with stop): s1_short_put 0.30 / -14.1% -> 0.80 / -6.3% (21 stops, 11 helped); s2_short_call 0.07 / -9.0% -> -0.09 / -10.2% (30 stops, 10 helped); s3_short_straddle 0.01 / -14.4% -> -0.02 / -16.9% (4 stops, 1 helped); s4_short_strangle 0.31 / -14.7% -> 0.44 / -8.0% (25 stops, 12 helped); s5_bear_call_spread -0.28 / -10.0% -> -0.48 / -10.9% (36 stops, 10 helped); s6_iron_butterfly -0.74 / -10.3% -> -0.74 / -10.3% (0 stops, 0 helped); s7_cash_secured_put 0.28 / -25.2% -> 0.80 / -11.1% (21 stops, 11 helped); s8_put_ratio 0.57 / -0.8% -> 0.35 / -2.8% (6 stops, 0 helped).
- Lowest correlation with the base put spread: s8_put_ratio_e1 -0.83 (Sharpe 0.35); s8_put_ratio -0.81 (Sharpe 0.57); s5_bear_call_spread_e1 -0.22 (Sharpe -0.48); s5_bear_call_spread -0.17 (Sharpe -0.28).
- Option-only Sharpe above the base put spread (0.32): s1_short_put_e1, s4_short_strangle_e1, s7_cash_secured_put_e1, s8_put_ratio, s8_put_ratio_e1, s10_covered_call, s11_collar. Above the frozen e1f1 rule (0.73): s1_short_put_e1, s7_cash_secured_put_e1.
- s10_covered_call: CAGR 8.8%, +0.8% a year vs TRI buy-and-hold; worst month -25.3%.
- s11_collar: CAGR 6.2%, -1.8% a year vs TRI buy-and-hold; worst month -9.7%.

## Crash months and correlation (combination inputs)

Option return (% of capital) in the 10 worst NIFTY TRI months of the period, base put spread and the four lowest-correlation strategies:

| entry_date   |   tri_pct |   ref_base |   s8_put_ratio_e1 |   s8_put_ratio |   s5_bear_call_spread_e1 |   s5_bear_call_spread |
|:-------------|----------:|-----------:|------------------:|---------------:|-------------------------:|----------------------:|
| 2008-09-26   |    -27.55 |       0    |              0    |           0    |                     2.93 |                  2.93 |
| 2008-05-30   |    -15    |     -10.01 |              1.98 |           1.98 |                     1.11 |                  1.11 |
| 2011-07-29   |    -13.28 |     -10.01 |              4.33 |           4.33 |                     0.59 |                  0.59 |
| 2011-10-28   |    -12.12 |     -10.01 |              4.8  |           4.8  |                     0.91 |                  0.91 |
| 2010-12-31   |    -10.13 |      -6.41 |              3.1  |           3.1  |                     0.54 |                  0.54 |
| 2008-08-29   |     -8.46 |       0.23 |              0.35 |           0.35 |                     2.06 |                  2.06 |
| 2018-09-28   |     -8.15 |      -4.23 |              2.35 |           2.35 |                     0.36 |                  0.36 |
| 2016-01-29   |     -7.03 |      -5.46 |              2.8  |           2.8  |                     0.23 |                  0.23 |
| 2008-10-31   |     -7.02 |       2.86 |              3.22 |           3.22 |                     4.05 |                  4.05 |
| 2013-07-26   |     -6.94 |      -6.12 |              2.89 |           2.89 |                     0.64 |                  0.64 |

Full tables: `correlation_design.csv`, `crash_table.csv`, `co_loss_pairs.csv`.

## Deflated Sharpe ratio (design, 32 cumulative trials)

Inputs: each series' monthly Sharpe, months, skewness, kurtosis; variance of monthly Sharpe across the 32 trials (Phase 1: 3, Phase 2: 6, Phase 3: 3, census: 20) = 0.0214.

| strategy                  |   SR monthly |   DSR SR0 (monthly) |   months | DSR   |
|:--------------------------|-------------:|--------------------:|---------:|:------|
| s1_short_put              |         0.09 |                0.31 |      132 | 2.6%  |
| s1_short_put_e1           |         0.23 |                0.31 |      132 | 26.5% |
| s2_short_call             |         0.02 |                0.31 |      132 | 0.1%  |
| s2_short_call_e1          |        -0.03 |                0.31 |      132 | 0.0%  |
| s3_short_straddle         |         0    |                0.31 |      132 | 0.0%  |
| s3_short_straddle_e1      |        -0.01 |                0.31 |      132 | 0.0%  |
| s4_short_strangle         |         0.09 |                0.31 |      132 | 1.3%  |
| s4_short_strangle_e1      |         0.13 |                0.31 |      132 | 1.8%  |
| s5_bear_call_spread       |        -0.08 |                0.31 |      132 | 0.0%  |
| s5_bear_call_spread_e1    |        -0.14 |                0.31 |      132 | 0.0%  |
| s6_iron_butterfly         |        -0.22 |                0.31 |      132 | 0.0%  |
| s6_iron_butterfly_e1      |        -0.22 |                0.31 |      132 | 0.0%  |
| s7_cash_secured_put       |         0.08 |                0.31 |      132 | 2.2%  |
| s7_cash_secured_put_e1    |         0.23 |                0.31 |      132 | 26.4% |
| s8_put_ratio              |         0.16 |                0.31 |      132 | 1.7%  |
| s8_put_ratio_e1           |         0.1  |                0.31 |      132 | 0.4%  |
| s9_calendar               |        -0.4  |                0.31 |      132 | 0.0%  |
| s10_covered_call          |         0.16 |                0.31 |      132 | 6.6%  |
| s11_collar                |         0.15 |                0.31 |      132 | 3.5%  |
| s12_delta_hedged_straddle |         0.09 |                0.31 |      132 | 1.0%  |
| ref_base                  |         0.09 |                0.31 |      132 | 1.5%  |
| ref_iron_condor           |        -0.01 |                0.31 |      132 | 0.0%  |
| ref_strangle              |         0.08 |                0.31 |      132 | 1.1%  |
| ref_e1f1                  |         0.21 |                0.31 |      132 | 16.8% |

## Shortlist (design cycles only; written before validation)

Rule (pre-registered): option-only Sharpe above the base put spread's (0.32), worst month no worse than -12% of capital, break-even margin at least 3 points. Candidates: the 20 census trials.

| strategy                  |   option Sharpe | worst month   | break-even margin   | option CAGR   |
|:--------------------------|----------------:|:--------------|:--------------------|:--------------|
| s1_short_put              |            0.3  | -14.1%        | 5.3%                | 1.4%          |
| s1_short_put_e1           |            0.8  | -6.3%         | 15.5%               | 2.5%          |
| s2_short_call             |            0.07 | -9.0%         | 1.1%                | 0.2%          |
| s2_short_call_e1          |           -0.09 | -10.2%        | -2.0%               | -0.5%         |
| s3_short_straddle         |            0.01 | -14.4%        | 0.2%                | -0.2%         |
| s3_short_straddle_e1      |           -0.02 | -16.9%        | -0.5%               | -0.6%         |
| s4_short_strangle         |            0.31 | -14.7%        | 7.2%                | 2.0%          |
| s4_short_strangle_e1      |            0.44 | -8.0%         | 10.2%               | 2.4%          |
| s5_bear_call_spread       |           -0.28 | -10.0%        | -4.0%               | -3.3%         |
| s5_bear_call_spread_e1    |           -0.48 | -10.9%        | -8.7%               | -4.5%         |
| s6_iron_butterfly         |           -0.74 | -10.3%        | -12.6%              | -22.3%        |
| s6_iron_butterfly_e1      |           -0.74 | -10.3%        | -12.6%              | -22.3%        |
| s7_cash_secured_put       |            0.28 | -25.2%        | 4.8%                | 2.1%          |
| s7_cash_secured_put_e1    |            0.8  | -11.1%        | 14.6%               | 4.3%          |
| s8_put_ratio              |            0.57 | -0.8%         | 9.8%                | 1.9%          |
| s8_put_ratio_e1           |            0.35 | -2.8%         | 5.4%                | 1.2%          |
| s9_calendar               |           -1.37 | -49.4%        | -28.7%              | -45.2%        |
| s10_covered_call          |            0.55 | -25.3%        | 10.3%               | 8.8%          |
| s11_collar                |            0.5  | -9.7%         | 8.6%                | 6.2%          |
| s12_delta_hedged_straddle |            0.3  | -8.2%         | 6.3%                | 1.3%          |

**Shortlist (6): s1_short_put_e1, s4_short_strangle_e1, s7_cash_secured_put_e1, s8_put_ratio, s8_put_ratio_e1, s11_collar**


### Notes (facts from the design data; the pre-registered rule is applied unchanged)

- October 2008 cycle (entry 2008-09-26, index -32.3%): traded by s1_short_put_e1 (-6.3%), s4_short_strangle_e1 (-8.0%), s7_cash_secured_put_e1 (-11.1%), s11_collar (-0.4%); skipped (no traded strike) by s8_put_ratio, s8_put_ratio_e1, and by the base put spread and the frozen e1f1 rule. Comparisons with the base therefore flatter the base and any strategy that skipped that month.
- s8_put_ratio entered at a net debit in 92% of traded cycles (so its stop variant rarely applies), loses only if the index falls more than about 15% (1 long 0.95 put vs 2 short 0.90 puts), and the only design fall that large (Oct 2008) was skipped. Its small worst month has never met its real tail.
- s11_collar holds the index: its return includes the index leg (CAGR -1.8% a year vs TRI buy-and-hold).
- s6_iron_butterfly_e1 equals s6_iron_butterfly: its maximum loss per unit (wing width - credit) is below 2 x credit, so the stop can never trigger.
- s9_calendar: sizing assumed max loss = debit, but after falls the deep in-the-money far put traded below intrinsic on the near expiry day (17 of 132 design cycles), so losses reached several times the debit; one cycle (entry 2013-12-27) used a carried far close (flagged).
- Deflated Sharpe at 32 trials is below 30% for every strategy. Paired Newey-West t vs the base: largest positive 1.72 (s10_covered_call); no strategy is significantly better than the base; the most negative are s9_calendar -5.13, s6_iron_butterfly -2.84.

## Checks

- credit_gross - slippage - payout - charges + index leg + futures hedge + interest = total_pnl: max gap Rs 0.000000 -> PASS
- capital_end = capital_start + total_pnl: max gap Rs 0.000000 -> PASS
- charge items sum to total_charges: max gap Rs 0.000000 -> PASS
- capital_start = previous capital_end: max gap Rs 0.000000 -> PASS

## Validation (run 1)

**Validation; aggregate results for this period were seen in Phase 1, so not a clean test.** 69 cycles, entries 2019-02-01 to 2024-09-27. Shortlist (from design): s1_short_put_e1, s4_short_strangle_e1, s7_cash_secured_put_e1, s8_put_ratio, s8_put_ratio_e1, s11_collar.

| strategy                  | shortlisted   | option CAGR   |   option Sharpe | worst month   | worst 3m   | CVaR95   | CVaR99   | max DD   |   skew | win rate   | avg win   | avg loss   | break-even win rate   | break-even margin   | avg credit % cap   | avg risk % cap   | avg margin % cap   |   months traded |   months skipped |   stops |   stops helped | costs % gross credit   | total CAGR (cash 6.5%)   |   corr with base |   NW t vs base | DSR   |
|:--------------------------|:--------------|:--------------|----------------:|:--------------|:-----------|:---------|:---------|:---------|-------:|:-----------|:----------|:-----------|:----------------------|:--------------------|:-------------------|:-----------------|:-------------------|----------------:|-----------------:|--------:|---------------:|:-----------------------|:-------------------------|-----------------:|---------------:|:------|
| s1_short_put              |               | 1.3%          |            0.33 | -8.9%         | -8.7%      | -2.7%    | -8.9%    | -8.9%    |  -5.35 | 95.6%      | 0.3%      | -3.6%      | 92.5%                 | 3.1%                | 0.3%               | 10.0%            | 7.7%               |              68 |                1 |       0 |              0 | 3.8%                   | 7.6%                     |             0.88 |          -2.44 | 3.3%  |
| s1_short_put_e1           | yes           | 2.2%          |            1.02 | -1.3%         | -1.2%      | -0.9%    | -1.3%    | -1.5%    |   3.64 | 88.2%      | 0.3%      | -0.7%      | 69.8%                 | 18.4%               | 0.3%               | 10.0%            | 7.7%               |              68 |                1 |       7 |              2 | 4.8%                   | 8.5%                     |             0.55 |          -0.9  | 16.7% |
| s2_short_call             |               | -1.8%         |           -0.56 | -4.2%         | -5.9%      | -3.3%    | -4.2%    | -12.4%   |  -3.05 | 77.9%      | 0.2%      | -1.4%      | 87.6%                 | -9.6%               | 0.3%               | 10.0%            | 10.3%              |              68 |                1 |       0 |              0 | 3.9%                   | 4.1%                     |            -0.17 |          -2.35 | 0.0%  |
| s2_short_call_e1          |               | -1.8%         |           -0.66 | -3.9%         | -4.8%      | -2.8%    | -3.9%    | -12.7%   |  -2.75 | 67.6%      | 0.2%      | -0.9%      | 81.4%                 | -13.8%              | 0.3%               | 10.0%            | 10.3%              |              68 |                1 |      20 |              9 | 7.0%                   | 4.2%                     |            -0.21 |          -2.41 | 0.0%  |
| s3_short_straddle         |               | -0.7%         |           -0.11 | -9.0%         | -8.3%      | -4.3%    | -9.0%    | -13.8%   |  -2.64 | 60.3%      | 0.8%      | -1.4%      | 62.5%                 | -2.2%               | 1.9%               | 10.0%            | 14.3%              |              68 |                1 |       0 |              0 | 3.3%                   | 4.9%                     |             0.67 |          -2.42 | 0.0%  |
| s3_short_straddle_e1      |               | 0.2%          |            0.06 | -4.1%         | -5.5%      | -3.1%    | -4.1%    | -9.6%    |  -0.74 | 60.3%      | 0.8%      | -1.2%      | 59.3%                 | 1.0%                | 1.9%               | 10.0%            | 14.3%              |              68 |                1 |       1 |              1 | 3.5%                   | 5.9%                     |             0.48 |          -1.7  | 0.1%  |
| s4_short_strangle         |               | 0.1%          |            0.06 | -8.9%         | -8.5%      | -3.7%    | -8.9%    | -9.3%    |  -4.83 | 80.9%      | 0.4%      | -1.5%      | 79.8%                 | 1.1%                | 0.6%               | 10.0%            | 15.9%              |              68 |                1 |       0 |              0 | 3.9%                   | 5.8%                     |             0.78 |          -2.59 | 0.2%  |
| s4_short_strangle_e1      | yes           | 1.0%          |            0.35 | -3.7%         | -3.3%      | -2.4%    | -3.7%    | -5.4%    |  -1.54 | 76.5%      | 0.4%      | -0.9%      | 70.0%                 | 6.5%                | 0.6%               | 10.0%            | 15.9%              |              68 |                1 |      11 |              4 | 5.1%                   | 6.8%                     |             0.61 |          -1.59 | 1.7%  |
| s5_bear_call_spread       |               | -5.9%         |           -0.69 | -10.0%        | -15.1%     | -8.8%    | -10.0%   | -32.4%   |  -2.92 | 75.0%      | 0.5%      | -3.8%      | 87.8%                 | -12.8%              | 0.6%               | 10.0%            | 10.0%              |              60 |                9 |       0 |              0 | 7.6%                   | -0.2%                    |            -0.18 |          -2.28 | 0.0%  |
| s5_bear_call_spread_e1    |               | -4.5%         |           -0.68 | -10.0%        | -10.6%     | -6.4%    | -10.0%   | -27.7%   |  -2.86 | 65.0%      | 0.6%      | -2.3%      | 79.9%                 | -14.9%              | 0.6%               | 10.0%            | 10.0%              |              60 |                9 |      19 |              9 | 12.5%                  | 1.4%                     |            -0.21 |          -2.4  | 0.0%  |
| s6_iron_butterfly         |               | -14.5%        |           -0.49 | -10.3%        | -25.4%     | -10.1%   | -10.3%   | -71.9%   |   0.09 | 50.0%      | 5.6%      | -7.6%      | 57.9%                 | -7.9%               | 12.4%              | 10.0%            | 10.0%              |              68 |                1 |       0 |              0 | 5.9%                   | -9.2%                    |             0.16 |          -1.45 | 0.0%  |
| s6_iron_butterfly_e1      |               | -14.5%        |           -0.49 | -10.3%        | -25.4%     | -10.1%   | -10.3%   | -71.9%   |   0.09 | 50.0%      | 5.6%      | -7.6%      | 57.9%                 | -7.9%               | 12.4%              | 10.0%            | 10.0%              |              68 |                1 |       0 |              0 | 5.9%                   | -9.2%                    |             0.16 |          -1.45 | 0.0%  |
| s7_cash_secured_put       |               | 2.0%          |            0.3  | -17.0%        | -16.6%     | -5.2%    | -17.0%   | -17.0%   |  -6.3  | 95.6%      | 0.5%      | -7.0%      | 92.9%                 | 2.7%                | 0.5%               | 19.4%            | 15.0%              |              68 |                1 |       0 |              0 | 3.5%                   | 7.8%                     |             0.9  |          -1.69 | 3.0%  |
| s7_cash_secured_put_e1    | yes           | 3.8%          |            1.11 | -2.5%         | -2.4%      | -1.8%    | -2.5%    | -2.8%    |   2.11 | 88.2%      | 0.5%      | -1.3%      | 71.1%                 | 17.1%               | 0.5%               | 19.4%            | 15.0%              |              68 |                1 |       7 |              2 | 4.5%                   | 9.8%                     |             0.61 |          -0.12 | 28.9% |
| s8_put_ratio              | yes           | -2.0%         |           -0.5  | -7.6%         | -7.9%      | -2.3%    | -7.6%    | -13.3%   |  -2.85 | 7.6%       | 1.8%      | -0.3%      | 15.8%                 | -8.2%               | -0.1%              | 9.9%             | 15.2%              |              66 |                3 |       0 |              0 | 15.7%                  | 3.5%                     |             0.48 |          -2.95 | 0.0%  |
| s8_put_ratio_e1           | yes           | -2.1%         |           -0.5  | -7.6%         | -7.9%      | -2.3%    | -7.6%    | -13.3%   |  -2.84 | 6.1%       | 2.2%      | -0.3%      | 12.9%                 | -6.8%               | -0.1%              | 9.9%             | 15.2%              |              66 |                3 |       1 |              0 | 16.5%                  | 3.5%                     |             0.48 |          -2.95 | 0.0%  |
| s9_calendar               |               | -26.1%        |           -0.85 | -27.1%        | -34.4%     | -24.6%   | -27.1%   | -85.9%   |  -0.82 | 36.8%      | 6.1%      | -6.9%      | 53.2%                 | -16.5%              | -10.0%             | 10.0%            | 10.0%              |              68 |                1 |       0 |              0 | 33.9%                  | -21.5%                   |             0.48 |          -2.39 | 0.0%  |
| s10_covered_call          |               | 13.3%         |            0.89 | -22.0%        | -28.3%     | -10.0%   | -22.0%   | -28.3%   |  -2.12 | 63.2%      | 3.7%      | -3.2%      | 46.2%                 | 17.0%               | 0.4%               | 39.6%            | 0.0%               |              68 |                1 |       0 |              0 | 4.9%                   | 13.4%                    |             0.75 |           1.83 | 22.3% |
| s11_collar                | yes           | 10.8%         |            0.96 | -6.3%         | -13.6%     | -5.1%    | -6.3%    | -15.7%   |  -0.2  | 60.3%      | 3.2%      | -2.5%      | 44.2%                 | 16.1%               | -0.2%              | 40.2%            | 0.0%               |              68 |                1 |       0 |              0 | 22.3%                  | 10.9%                    |             0.38 |           1.58 | 21.0% |
| s12_delta_hedged_straddle |               | 1.6%          |            0.32 | -7.3%         | -8.5%      | -4.4%    | -7.3%    | -11.4%   |  -2.01 | 61.8%      | 0.9%      | -1.1%      | 54.7%                 | 7.0%                | 3.7%               |                  | 40.5%              |              68 |                1 |       0 |              0 | 5.2%                   | 5.6%                     |             0.61 |          -1.16 | 1.6%  |
| ref_base                  |               | 4.0%          |            0.72 | -10.0%        | -9.4%      | -4.8%    | -10.0%   | -10.0%   |  -4.63 | 93.9%      | 0.7%      | -4.8%      | 87.4%                 | 6.5%                | 0.7%               | 10.0%            | 10.0%              |              66 |                3 |       0 |              0 | 7.7%                   | 10.3%                    |             1    |                | 17.6% |
| ref_iron_condor           |               | -2.4%         |           -0.18 | -10.1%        | -18.3%     | -10.0%   | -10.1%   | -35.5%   |  -2.11 | 75.9%      | 1.2%      | -4.5%      | 79.1%                 | -3.3%               | 1.5%               | 10.0%            | 10.0%              |              58 |               11 |       0 |              0 | 8.2%                   | 3.6%                     |             0.34 |          -1.39 | 0.0%  |
| ref_strangle              |               | -0.3%         |            0.01 | -16.5%        | -15.8%     | -7.0%    | -16.5%   | -19.5%   |  -5.25 | 80.9%      | 0.7%      | -2.8%      | 80.7%                 | 0.2%                | 0.9%               | 19.0%            | 30.0%              |              68 |                1 |       0 |              0 | 3.6%                   | 4.4%                     |             0.78 |          -1.88 | 0.1%  |
| ref_e1f1                  |               | 2.7%          |            1.1  | -4.1%         | -2.8%      | -1.3%    | -4.1%    | -4.1%    |  -2.95 | 94.1%      | 0.7%      | -2.7%      | 80.3%                 | 13.8%               | 0.7%               | 10.0%            | 10.0%              |              34 |               35 |       1 |              0 | 6.9%                   | 9.3%                     |             0.39 |          -0.77 | 37.3% |

Reading (validation):

- Earn after costs (option-only CAGR above zero, i.e. beat cash): s1_short_put, s1_short_put_e1, s3_short_straddle_e1, s4_short_strangle, s4_short_strangle_e1, s7_cash_secured_put, s7_cash_secured_put_e1, s10_covered_call, s11_collar, s12_delta_hedged_straddle. Negative: s2_short_call, s2_short_call_e1, s3_short_straddle, s5_bear_call_spread, s5_bear_call_spread_e1, s6_iron_butterfly, s6_iron_butterfly_e1, s8_put_ratio, s8_put_ratio_e1, s9_calendar.
- Worst tails (CVaR 99%): s9_calendar -27.1% (worst month -27.1%); s10_covered_call -22.0% (worst month -22.0%); s7_cash_secured_put -17.0% (worst month -17.0%); s6_iron_butterfly -10.3% (worst month -10.3%); s6_iron_butterfly_e1 -10.3% (worst month -10.3%).
- Stop by family (option-only Sharpe / worst month, without -> with stop): s1_short_put 0.33 / -8.9% -> 1.02 / -1.3% (7 stops, 2 helped); s2_short_call -0.56 / -4.2% -> -0.66 / -3.9% (20 stops, 9 helped); s3_short_straddle -0.11 / -9.0% -> 0.06 / -4.1% (1 stops, 1 helped); s4_short_strangle 0.06 / -8.9% -> 0.35 / -3.7% (11 stops, 4 helped); s5_bear_call_spread -0.69 / -10.0% -> -0.68 / -10.0% (19 stops, 9 helped); s6_iron_butterfly -0.49 / -10.3% -> -0.49 / -10.3% (0 stops, 0 helped); s7_cash_secured_put 0.30 / -17.0% -> 1.11 / -2.5% (7 stops, 2 helped); s8_put_ratio -0.50 / -7.6% -> -0.50 / -7.6% (1 stops, 0 helped).
- Lowest correlation with the base put spread: s5_bear_call_spread_e1 -0.21 (Sharpe -0.68); s2_short_call_e1 -0.21 (Sharpe -0.66); s5_bear_call_spread -0.18 (Sharpe -0.69); s2_short_call -0.17 (Sharpe -0.56).
- Option-only Sharpe above the base put spread (0.72): s1_short_put_e1, s7_cash_secured_put_e1, s10_covered_call, s11_collar. Above the frozen e1f1 rule (1.10): s7_cash_secured_put_e1.
- s10_covered_call: CAGR 13.3%, -3.1% a year vs TRI buy-and-hold; worst month -22.0%.
- s11_collar: CAGR 10.8%, -5.6% a year vs TRI buy-and-hold; worst month -6.3%.
- Shortlisted s1_short_put_e1: Sharpe 0.80 on design -> 1.02 on validation (base 0.72, e1f1 1.10); worst month -1.3%; DSR 0.17.
- Shortlisted s4_short_strangle_e1: Sharpe 0.44 on design -> 0.35 on validation (base 0.72, e1f1 1.10); worst month -3.7%; DSR 0.02.
- Shortlisted s7_cash_secured_put_e1: Sharpe 0.80 on design -> 1.11 on validation (base 0.72, e1f1 1.10); worst month -2.5%; DSR 0.29.
- Shortlisted s8_put_ratio: Sharpe 0.57 on design -> -0.50 on validation (base 0.72, e1f1 1.10); worst month -7.6%; DSR 0.00.
- Shortlisted s8_put_ratio_e1: Sharpe 0.35 on design -> -0.50 on validation (base 0.72, e1f1 1.10); worst month -7.6%; DSR 0.00.
- Shortlisted s11_collar: Sharpe 0.50 on design -> 0.96 on validation (base 0.72, e1f1 1.10); worst month -6.3%; DSR 0.21.

Validation checks:

- credit_gross - slippage - payout - charges + index leg + futures hedge + interest = total_pnl: max gap Rs 0.000000 -> PASS
- capital_end = capital_start + total_pnl: max gap Rs 0.000000 -> PASS
- charge items sum to total_charges: max gap Rs 0.000000 -> PASS
- capital_start = previous capital_end: max gap Rs 0.000000 -> PASS

## Phase 4 correction
The S6 and S9 rows in the tables above are pre-fix. S9 valued the far leg with a stale or wrong-contract close in some months, and S6 had no notional cap. Corrected rows are in `summary_design.csv`, `summary_validation.csv`, `monthly_pnl_census.csv` and the combination tables; details and old vs new in `results/phase4/fixes.md`.
