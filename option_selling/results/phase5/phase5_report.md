# Phase 5 report: selling paired with buying

H1a = P1 + 0.85 put hedge (15% of credit); H1b = e1f1 + the same hedge; H2 = mirror (sell the 0.95/0.90 put spread when prem_ratio >= 0.12, buy it when < 0.06 with a 2% debit, else cash). ref_* are references; sens_* are sensitivity only. Option-only returns (no cash interest); Sharpe over all months with cash months = 0, no risk-free deduction. Both periods are **in-sample for this idea**; the holdout is not used.

## Design (in-sample for this idea): 132 cycles, entries 2008-02-01 to 2018-12-28

| rule      | option CAGR   |   Sharpe all months | worst month   | worst 3m   | CVaR95   | CVaR99   | max DD   | win rate   |   months selling |   months buying |   months in cash |   stops | costs % gross premium   | total CAGR (cash 6.5%)   |   NW t vs P1 |   NW t vs e1f1 | DSR   |
|:----------|:--------------|--------------------:|:--------------|:-----------|:---------|:---------|:---------|:-----------|-----------------:|----------------:|-----------------:|--------:|:------------------------|:-------------------------|-------------:|---------------:|:------|
| ref_p1    | 5.0%          |                1.12 | -10.0%        | -9.0%      | -1.4%    | -5.0%    | -10.0%   | 97.1%      |               35 |               0 |               97 |       0 | 9.1%                    | 11.8%                    |              |           1.46 | 48.4% |
| ref_e1f1  | 3.2%          |                0.73 | -5.2%         | -8.1%      | -3.5%    | -4.5%    | -11.8%   | 77.3%      |               66 |               0 |               66 |      13 | 11.7%                   | 9.8%                     |        -1.46 |                | 11.7% |
| ref_base  | 2.2%          |                0.32 | -10.0%        | -9.0%      | -7.5%    | -10.0%   | -18.8%   | 86.2%      |              130 |               0 |                2 |       0 | 8.4%                    | 8.4%                     |        -1.31 |          -0.4  | 0.8%  |
| h1a       | 4.1%          |                0.97 | -10.3%        | -9.5%      | -1.5%    | -5.2%    | -10.3%   | 94.3%      |               35 |               0 |               97 |       0 | 11.2%                   | 10.8%                    |        -3.72 |           0.7  | 38.0% |
| h1b       | 2.1%          |                0.53 | -5.4%         | -8.1%      | -3.6%    | -4.7%    | -12.3%   | 75.8%      |               66 |               0 |               66 |      13 | 14.7%                   | 8.7%                     |        -2.31 |          -4.38 | 3.8%  |
| h2        | 5.1%          |                0.39 | -10.0%        | -9.0%      | -3.1%    | -6.0%    | -32.6%   | 44.0%      |               35 |              56 |               41 |       0 | 8.6%                    | 11.9%                    |         0.24 |           0.59 | 0.1%  |
| ref_s7_e1 | 4.3%          |                0.8  | -11.1%        | -8.8%      | -3.9%    | -7.3%    | -11.1%   | 81.8%      |              132 |               0 |                0 |      21 | 4.8%                    | 10.3%                    |        -0.44 |           0.8  | 20.8% |

Deflated Sharpe uses 38 trials; variance of monthly Sharpe across them = 0.0231.

Hedge leg alone (H1a, H1b):

| rule   |   months hedged |   months the 0.85 put expired in the money |   total paid (Rs) |   total received (Rs) |   net cost a year, % of capital |   unhedged months (no 0.85 put) |
|:-------|----------------:|-------------------------------------------:|------------------:|----------------------:|--------------------------------:|--------------------------------:|
| h1a    |              32 |                                          0 |            138149 |                     0 |                            0.89 |                               3 |
| h1b    |              61 |                                          0 |            149375 |                     0 |                            1.01 |                               5 |

Hedge leg net payoff (% of capital) in the 10 worst NIFTY TRI months (blank = no hedge that month):

|            |   TRI % |    h1a |    h1b |
|:-----------|--------:|-------:|-------:|
| 2008-09-26 |  -27.55 | nan    | nan    |
| 2008-05-30 |  -15    |  -0.24 |  -0.24 |
| 2011-07-29 |  -13.28 | nan    |  -0.11 |
| 2011-10-28 |  -12.12 | nan    | nan    |
| 2010-12-31 |  -10.13 | nan    | nan    |
| 2008-08-29 |   -8.46 |  -0.32 |  -0.32 |
| 2018-09-28 |   -8.15 | nan    | nan    |
| 2016-01-29 |   -7.03 | nan    | nan    |
| 2008-10-31 |   -7.02 |  -0.43 |  -0.43 |
| 2013-07-26 |   -6.94 | nan    | nan    |

H2 buy leg and sell leg:

|   buy months | paid off (net > 0)   |   avg win % |   avg loss % |   total % (sum) |   sell months |   sell months total % (sum) |   sell months worst % |
|-------------:|:---------------------|------------:|-------------:|----------------:|--------------:|----------------------------:|----------------------:|
|           56 | 11%                  |       18.34 |        -1.96 |           12.03 |            35 |                       54.89 |                -10.01 |

H2 top 5 buy months by payoff:

| entry_date   |   index_move_pct |   buy_debit |   buy_payoff |   option_return_on_capital_pct |
|:-------------|-----------------:|------------:|-------------:|-------------------------------:|
| 2016-10-28   |            -7.79 |     57859.1 |       720271 |                          22.87 |
| 2010-12-31   |            -8.64 |     33446.1 |       539542 |                          30.22 |
| 2018-08-31   |            -6.02 |     58635.7 |       538475 |                          16.34 |
| 2016-01-01   |            -6.76 |     52721.7 |       476354 |                          16.05 |
| 2015-07-31   |            -6.84 |     43344.1 |       411831 |                          16.98 |

Sensitivity only (not trials):

| rule          | option CAGR   |   Sharpe all months | worst month   | CVaR99   |   months selling |   months buying |
|:--------------|:--------------|--------------------:|:--------------|:---------|-----------------:|----------------:|
| sens_h1a_0.10 | 4.4%          |                1.02 | -10.2%        | -5.1%    |               35 |               0 |
| sens_h1a_0.25 | 3.5%          |                0.86 | -10.4%        | -5.4%    |               35 |               0 |
| sens_h2_0.05  | 6.1%          |                0.46 | -10.0%        | -6.0%    |               35 |              46 |
| sens_h2_0.08  | 10.2%         |                0.58 | -10.0%        | -6.0%    |               35 |              77 |

Reading:

- h1a vs P1: worst month -10.3% vs -10.0%, CVaR 99% -5.2% vs -5.0%, option CAGR 4.1% vs 5.0%. The hedge leg cost a net 0.89% of capital a year and expired in the money in 0 of 32 hedged months; it did not reduce the worst month.
- h1b vs e1f1: worst month -5.4% vs -5.2%, CVaR 99% -4.7% vs -4.5%, option CAGR 2.1% vs 3.2%. The hedge leg cost a net 1.01% of capital a year and expired in the money in 0 of 61 hedged months; it did not reduce the worst month.
- h2 mirror: 56 buy months, paid off in 11%, buy months summed to +12.03% of capital (sell months +54.89%). The buying earned money overall. h2 option CAGR 5.1% vs P1 5.0%.
- Beat P1 on both Sharpe and option CAGR: none. Beat e1f1 on both: h1a.
- Paired Newey-West t: h1a -3.72 vs P1, 0.70 vs e1f1; h1b -2.31 vs P1, -4.38 vs e1f1; h2 0.24 vs P1, 0.59 vs e1f1.

Checks:

- credit_gross - slippage - payout - charges + interest = total_pnl: max gap Rs 0.000000 -> PASS
- capital_end = capital_start + total_pnl: max gap Rs 0.000000 -> PASS
- charge items sum to total_charges: max gap Rs 0.000000 -> PASS
- capital_start = previous capital_end: max gap Rs 0.000000 -> PASS

## Validation (in-sample for this idea): 69 cycles, entries 2019-02-01 to 2024-09-27

| rule      | option CAGR   |   Sharpe all months | worst month   | worst 3m   | CVaR95   | CVaR99   | max DD   | win rate   |   months selling |   months buying |   months in cash |   stops | costs % gross premium   | total CAGR (cash 6.5%)   |   NW t vs P1 |   NW t vs e1f1 | DSR   |
|:----------|:--------------|--------------------:|:--------------|:-----------|:---------|:---------|:---------|:-----------|-----------------:|----------------:|-----------------:|--------:|:------------------------|:-------------------------|-------------:|---------------:|:------|
| ref_p1    | 2.9%          |                1.38 | 0.0%          | 0.0%       | 0.0%     | 0.0%     | 0.0%     | 100.0%     |               10 |               0 |               59 |       0 | 10.3%                   | 9.7%                     |              |           0.13 | 31.9% |
| ref_e1f1  | 2.7%          |                1.1  | -4.1%         | -2.8%      | -1.3%    | -4.1%    | -4.1%    | 94.1%      |               34 |               0 |               35 |       1 | 6.9%                    | 9.3%                     |        -0.13 |                | 27.4% |
| ref_base  | 4.0%          |                0.73 | -10.0%        | -9.4%      | -4.8%    | -10.0%   | -10.0%   | 94.0%      |               67 |               0 |                2 |       0 | 7.7%                    | 10.3%                    |         0.54 |           0.79 | 11.4% |
| h1a       | 2.5%          |                1.38 | 0.0%          | 0.0%       | 0.0%     | 0.0%     | 0.0%     | 100.0%     |               10 |               0 |               59 |       0 | 12.5%                   | 9.2%                     |        -2.23 |          -0.2  | 31.9% |
| h1b       | 2.2%          |                0.93 | -4.2%         | -3.1%      | -1.4%    | -4.2%    | -4.2%    | 94.1%      |               34 |               0 |               35 |       1 | 8.9%                    | 8.7%                     |        -0.48 |          -4.15 | 19.6% |
| h2        | -6.1%         |               -0.36 | -2.0%         | -5.9%      | -2.0%    | -2.0%    | -47.4%   | 21.6%      |               10 |              41 |               18 |       0 | 7.2%                    | 0.1%                     |        -1.36 |          -1.23 | 0.1%  |
| ref_s7_e1 | 3.8%          |                1.12 | -2.5%         | -2.4%      | -1.8%    | -2.5%    | -2.8%    | 88.4%      |               69 |               0 |                0 |       7 | 4.5%                    | 9.8%                     |         0.98 |           0.75 | 15.1% |

Deflated Sharpe uses 38 trials; variance of monthly Sharpe across them = 0.0401.

Hedge leg alone (H1a, H1b):

| rule   |   months hedged |   months the 0.85 put expired in the money |   total paid (Rs) |   total received (Rs) |   net cost a year, % of capital |   unhedged months (no 0.85 put) |
|:-------|----------------:|-------------------------------------------:|------------------:|----------------------:|--------------------------------:|--------------------------------:|
| h1a    |              10 |                                          0 |           29694.5 |                     0 |                            0.44 |                               0 |
| h1b    |              29 |                                          0 |           34812.9 |                     0 |                            0.49 |                               5 |

Hedge leg net payoff (% of capital) in the 10 worst NIFTY TRI months (blank = no hedge that month):

|            |   TRI % |   h1a |    h1b |
|:-----------|--------:|------:|-------:|
| 2020-02-28 |  -22.47 |   nan | nan    |
| 2024-09-27 |   -7.06 |   nan | nan    |
| 2020-01-31 |   -6.33 |   nan | nan    |
| 2020-08-28 |   -5.1  |   nan |  -0.1  |
| 2022-04-29 |   -4.15 |   nan | nan    |
| 2019-06-28 |   -4.04 |   nan |  -0.06 |
| 2021-10-29 |   -3.59 |   nan |  -0.09 |
| 2022-05-27 |   -3.38 |   nan | nan    |
| 2022-04-01 |   -3.18 |   nan | nan    |
| 2023-09-29 |   -2.91 |   nan | nan    |

H2 buy leg and sell leg:

|   buy months | paid off (net > 0)   |   avg win % |   avg loss % |   total % (sum) |   sell months |   sell months total % (sum) |   sell months worst % |
|-------------:|:---------------------|------------:|-------------:|----------------:|--------------:|----------------------------:|----------------------:|
|           41 | 2%                   |       32.77 |           -2 |          -47.23 |            10 |                        16.7 |                  1.28 |

H2 top 5 buy months by payoff:

| entry_date   |   index_move_pct |   buy_debit |   buy_payoff |   option_return_on_capital_pct |
|:-------------|-----------------:|------------:|-------------:|-------------------------------:|
| 2024-09-27   |            -7.54 |     15084.2 |       262533 |                          32.77 |
| 2019-02-01   |            -0.93 |     20000   |            0 |                          -2    |
| 2019-03-01   |             6.5  |     19697.7 |            0 |                          -2    |
| 2019-03-29   |             0.15 |     19400   |            0 |                          -2    |
| 2019-05-31   |            -0.68 |     19459   |            0 |                          -2    |

Sensitivity only (not trials):

| rule          | option CAGR   |   Sharpe all months | worst month   | CVaR99   |   months selling |   months buying |
|:--------------|:--------------|--------------------:|:--------------|:---------|-----------------:|----------------:|
| sens_h1a_0.10 | 2.6%          |                1.38 | 0.0%          | 0.0%     |               10 |               0 |
| sens_h1a_0.25 | 2.2%          |                1.38 | 0.0%          | 0.0%     |               10 |               0 |
| sens_h2_0.05  | -2.3%         |               -0.1  | -2.0%         | -2.0%    |               10 |              30 |
| sens_h2_0.08  | -6.0%         |               -0.32 | -2.0%         | -2.0%    |               10 |              47 |

Reading:

- h1a vs P1: worst month 0.0% vs 0.0%, CVaR 99% 0.0% vs 0.0%, option CAGR 2.5% vs 2.9%. The hedge leg cost a net 0.44% of capital a year and expired in the money in 0 of 10 hedged months; it did not reduce the worst month.
- h1b vs e1f1: worst month -4.2% vs -4.1%, CVaR 99% -4.2% vs -4.1%, option CAGR 2.2% vs 2.7%. The hedge leg cost a net 0.49% of capital a year and expired in the money in 0 of 29 hedged months; it did not reduce the worst month.
- h2 mirror: 41 buy months, paid off in 2%, buy months summed to -47.23% of capital (sell months +16.70%). The buying bled: it lost money overall. h2 option CAGR -6.1% vs P1 2.9%.
- Beat P1 on both Sharpe and option CAGR: none. Beat e1f1 on both: none. **Neither the hedges nor the mirror rule beats P1 or e1f1.**
- Paired Newey-West t: h1a -2.23 vs P1, -0.20 vs e1f1; h1b -0.48 vs P1, -4.15 vs e1f1; h2 -1.36 vs P1, -1.23 vs e1f1.

Checks:

- credit_gross - slippage - payout - charges + interest = total_pnl: max gap Rs 0.000000 -> PASS
- capital_end = capital_start + total_pnl: max gap Rs 0.000000 -> PASS
- charge items sum to total_charges: max gap Rs 0.000000 -> PASS
- capital_start = previous capital_end: max gap Rs 0.000000 -> PASS

## Crash table highlights (option return, % of capital)

design: 10 worst NIFTY TRI months

| entry_date   |   ref_p1 |   ref_e1f1 |   ref_base |    h1a |   h1b |     h2 |   ref_s7_e1 |   tri_pct |
|:-------------|---------:|-----------:|-----------:|-------:|------:|-------:|------------:|----------:|
| 2008-09-26   |     0    |       0    |       0    |   0    |  0    |   0    |      -11.14 |    -27.55 |
| 2008-05-30   |   -10.01 |      -5.17 |     -10.01 | -10.26 | -5.41 | -10.01 |       -3.36 |    -15    |
| 2011-07-29   |     0    |      -3.26 |     -10.01 |   0    | -3.38 |   0    |       -2.63 |    -13.28 |
| 2011-10-28   |     0    |       0    |     -10.01 |   0    |  0    |   0    |       -2.9  |    -12.12 |
| 2010-12-31   |     0    |       0    |      -6.41 |   0    |  0    |  30.22 |       -1.87 |    -10.13 |
| 2008-08-29   |     0.23 |       0.23 |       0.23 |  -0.1  | -0.1  |   0.23 |        0.72 |     -8.46 |
| 2018-09-28   |     0    |      -1.92 |      -4.23 |   0    | -1.92 |   0    |       -1.27 |     -8.15 |
| 2016-01-29   |     0    |       0    |      -5.46 |   0    |  0    |   0    |       -3.16 |     -7.03 |
| 2008-10-31   |     2.86 |       2.86 |       2.86 |   2.42 |  2.42 |   2.86 |        5.61 |     -7.02 |
| 2013-07-26   |     0    |       0    |      -6.12 |   0    |  0    |   0    |       -0.78 |     -6.94 |

design: average over the 10 worst / 10 best TRI months: ref_p1 -0.69 / +1.63; ref_e1f1 -0.73 / +1.31; ref_base -4.92 / +1.79; h1a -0.79 / +1.39; h1b -0.84 / +1.11; h2 +2.33 / +1.43; ref_s7_e1 -2.08 / +1.51

validation: 10 worst NIFTY TRI months

| entry_date   |   ref_p1 |   ref_e1f1 |   ref_base |   h1a |   h1b |    h2 |   ref_s7_e1 |   tri_pct |
|:-------------|---------:|-----------:|-----------:|------:|------:|------:|------------:|----------:|
| 2020-02-28   |        0 |       0    |     -10.04 |     0 |  0    |  0    |       -2.54 |    -22.47 |
| 2024-09-27   |        0 |       0    |      -4.83 |     0 |  0    | 32.77 |       -0.97 |     -7.06 |
| 2020-01-31   |        0 |       0.5  |       0.5  |     0 |  0.5  | -2    |        0.3  |     -6.33 |
| 2020-08-28   |        0 |      -4.1  |      -4.1  |     0 | -4.19 |  0    |       -1.69 |     -5.1  |
| 2022-04-29   |        0 |       0    |      -0.17 |     0 |  0    |  0    |       -1.24 |     -4.15 |
| 2019-06-28   |        0 |       0.37 |       0.37 |     0 |  0.31 | -2    |        0.25 |     -4.04 |
| 2021-10-29   |        0 |       0.57 |       0.57 |     0 |  0.48 | -2    |        0.35 |     -3.59 |
| 2022-05-27   |        0 |       0    |       1.16 |     0 |  0    |  0    |       -1.6  |     -3.38 |
| 2022-04-01   |        0 |       0    |       0.74 |     0 |  0    |  0    |        0.49 |     -3.18 |
| 2023-09-29   |        0 |       0    |       0.18 |     0 |  0    | -2    |        0.12 |     -2.91 |

validation: average over the 10 worst / 10 best TRI months: ref_p1 +0.00 / +0.87; ref_e1f1 -0.27 / +0.82; ref_base -1.56 / +1.23; h1a +0.00 / +0.74; h1b -0.29 / +0.71; h2 +2.48 / +0.47; ref_s7_e1 -0.65 / +1.31

Full tables: `crash_table.csv`, `by_year.csv`.
