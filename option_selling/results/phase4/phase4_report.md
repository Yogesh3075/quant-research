# Phase 4 report

Base structure: Phase 1 put spread (0.95 / 0.90, max loss 10%, fallback rule). P1 = trade only if prem_ratio >= 0.12; P2 = exit at the next close if NIFTY 50 closes below the short strike; **P3 = P1 + P2 (primary hypothesis)**. ref_* = references (recomputed in the Phase 4 engine). Option-only returns (no cash interest); Sharpe without risk-free deduction, over all months (cash months count as 0) and over traded months only. Cost stress: entry slippage x2 when India VIX at entry > 20 (ATM IV before May 2014) and x2 on every stop exit.

## Design (in-sample for this idea)

132 cycles, entries 2008-02-01 to 2018-12-28.

| rule      | option CAGR   |   Sharpe all months |   Sharpe traded months | worst month   | worst 3m   | CVaR95   | CVaR99   | max DD   | win rate   | break-even win rate   | break-even margin   |   months traded |   avg prem_ratio traded |   stops |   stops helped |   stops hurt |   median trigger day | costs % gross credit   | total CAGR (cash 6.5%)   |   NW t vs base |   NW t vs e1f1 |
|:----------|:--------------|--------------------:|-----------------------:|:--------------|:-----------|:---------|:---------|:---------|:-----------|:----------------------|:--------------------|----------------:|------------------------:|--------:|---------------:|-------------:|---------------------:|:-----------------------|:-------------------------|---------------:|---------------:|
| ref_base  | 2.2%          |                0.32 |                   0.32 | -10.0%        | -9.0%      | -7.5%    | -10.0%   | -18.8%   | 86.2%      | 82.1%                 | 4.0%                |             130 |                    0.09 |       0 |              0 |            0 |                      | 8.4%                   | 8.4%                     |                |          -0.4  |
| ref_e1f1  | 3.2%          |                0.73 |                   1.06 | -5.2%         | -8.1%      | -3.5%    | -4.5%    | -11.8%   | 77.3%      | 60.3%                 | 17.0%               |              66 |                    0.11 |      13 |              6 |            7 |                    6 | 11.7%                  | 9.8%                     |           0.4  |                |
| ref_s7_e1 | 4.3%          |                0.8  |                   0.8  | -11.1%        | -8.8%      | -3.9%    | -7.3%    | -11.1%   | 81.8%      | 67.3%                 | 14.6%               |             132 |                         |      21 |             11 |           10 |                    6 | 4.8%                   | 10.3%                    |           1.06 |           0.8  |
| p1        | 5.0%          |                1.12 |                   2.55 | -10.0%        | -9.0%      | -1.4%    | -5.0%    | -10.0%   | 97.1%      | 84.0%                 | 13.2%               |              35 |                    0.18 |       0 |              0 |            0 |                      | 9.1%                   | 11.8%                    |           1.31 |           1.46 |
| p2        | 0.6%          |                0.13 |                   0.13 | -4.9%         | -7.6%      | -4.1%    | -4.7%    | -12.8%   | 75.4%      | 73.4%                 | 2.0%                |             130 |                    0.09 |      32 |             13 |           19 |                    9 | 13.5%                  | 6.7%                     |          -0.83 |          -1.44 |
| p3        | 2.0%          |                0.58 |                   1.17 | -4.4%         | -7.0%      | -2.5%    | -3.7%    | -9.2%    | 71.4%      | 54.4%                 | 17.0%               |              35 |                    0.18 |      13 |              1 |           12 |                   10 | 13.9%                  | 8.7%                     |          -0.19 |          -0.67 |

Under the cost stress:

| rule      | option CAGR   |   Sharpe all months | worst month   | CVaR99   | max DD   | total CAGR (cash 6.5%)   |
|:----------|:--------------|--------------------:|:--------------|:---------|:---------|:-------------------------|
| ref_base  | 1.4%          |                0.22 | -10.0%        | -10.0%   | -19.4%   | 7.5%                     |
| ref_e1f1  | 1.0%          |                0.23 | -7.2%         | -6.5%    | -18.6%   | 7.4%                     |
| ref_s7_e1 | 3.9%          |                0.71 | -11.6%        | -7.6%    | -11.6%   | 9.8%                     |
| p1        | 4.2%          |                1.01 | -10.0%        | -5.0%    | -10.0%   | 11.0%                    |
| p2        | -0.8%         |               -0.11 | -5.4%         | -5.3%    | -17.0%   | 5.3%                     |
| p3        | 1.0%          |                0.28 | -5.4%         | -4.5%    | -13.1%   | 7.6%                     |

Deflated Sharpe (35 cumulative trials; inputs: each series' monthly Sharpe, months, skewness, kurtosis; variance of monthly Sharpe across the 35 trials in this period = 0.0233):

| rule      |   SR monthly |   DSR SR0 (monthly) | DSR   |
|:----------|-------------:|--------------------:|:------|
| ref_base  |         0.09 |                0.33 | 0.9%  |
| ref_e1f1  |         0.21 |                0.33 | 12.5% |
| ref_s7_e1 |         0.23 |                0.33 | 21.7% |
| p1        |         0.32 |                0.33 | 49.4% |
| p2        |         0.04 |                0.33 | 0.1%  |
| p3        |         0.17 |                0.33 | 4.4%  |

Sensitivity only (P3 prem_ratio threshold; not trials):

| rule         | option CAGR   |   Sharpe all months | worst month   |   months traded |
|:-------------|:--------------|--------------------:|:--------------|----------------:|
| sens_p3_0.10 | 2.2%          |                0.59 | -4.4%         |              41 |
| sens_p3_0.15 | 1.2%          |                0.37 | -4.4%         |              24 |
| p3           | 2.0%          |                0.58 | -4.4%         |              35 |

P3 trades by prem_ratio bucket:

| bucket     |   months traded |   mean return % |   compounded % |   stops |
|:-----------|----------------:|----------------:|---------------:|--------:|
| 0.12-0.15  |              11 |            0.84 |           9.53 |       3 |
| 0.15-0.20  |              13 |            1.2  |          16.55 |       2 |
| above 0.20 |              11 |           -0.21 |          -2.61 |       8 |

P3 trades by year:

|   year |   months traded |   mean return % |   compounded % |   stops |
|-------:|----------------:|----------------:|---------------:|--------:|
|   2008 |               9 |           -0.42 |          -4.01 |       6 |
|   2009 |              11 |            0.42 |           4.56 |       5 |
|   2010 |               3 |            1.37 |           4.16 |       0 |
|   2011 |               5 |            1.96 |          10.17 |       0 |
|   2012 |               2 |            1.16 |           2.33 |       1 |
|   2013 |               2 |            1.5  |           3.02 |       0 |
|   2014 |               1 |            2.03 |           2.03 |       0 |
|   2015 |               1 |           -0.99 |          -0.99 |       1 |
|   2016 |               1 |            1.35 |           1.35 |       0 |

Reading:

- P3 (primary): option CAGR 2.0%, Sharpe all months 0.58 (traded months 1.17), worst month -4.4%, traded 35 of 132 months. Base: 2.2% / 0.32 / -10.0%; e1f1: 3.2% / 0.73 / -5.2%.
- P3 beats the base and **does not beat** e1f1 on Sharpe over all months (paired Newey-West t -0.19 vs base, -0.67 vs e1f1).
- P1 alone: CAGR 5.0%, Sharpe 1.12, worst month -10.0%, months traded 35, stops 0 (0 helped, 0 hurt).
- P2 alone: CAGR 0.6%, Sharpe 0.13, worst month -4.9%, months traded 130, stops 32 (13 helped, 19 hurt).
- Cost stress (option CAGR / Sharpe, normal -> stressed): ref_base 2.2% / 0.32 -> 1.4% / 0.22; ref_e1f1 3.2% / 0.73 -> 1.0% / 0.23; ref_s7_e1 4.3% / 0.80 -> 3.9% / 0.71; p1 5.0% / 1.12 -> 4.2% / 1.01; p2 0.6% / 0.13 -> -0.8% / -0.11; p3 2.0% / 0.58 -> 1.0% / 0.28.
- P3 trades only 35 of 132 months; its result rests on few trades. Sharpe over all months counts the cash months as zero option return, which lowers volatility and flatters a rule that rarely trades; on option CAGR P3 earns 2.0% vs 2.2% for the base and 3.2% for e1f1 (less than at least one of them).
- P3's index stop: 13 stops, 1 helped and 12 hurt vs holding to expiry; net effect -3.56 lakh.

Checks:

- credit_gross - slippage - payout - charges + interest = total_pnl: max gap Rs 0.000000 -> PASS
- capital_end = capital_start + total_pnl: max gap Rs 0.000000 -> PASS
- charge items sum to total_charges: max gap Rs 0.000000 -> PASS
- capital_start = previous capital_end: max gap Rs 0.000000 -> PASS

## Validation (in-sample for this idea)

69 cycles, entries 2019-02-01 to 2024-09-27.

| rule      | option CAGR   |   Sharpe all months |   Sharpe traded months | worst month   | worst 3m   | CVaR95   | CVaR99   | max DD   | win rate   | break-even win rate   | break-even margin   |   months traded |   avg prem_ratio traded |   stops |   stops helped |   stops hurt |   median trigger day | costs % gross credit   | total CAGR (cash 6.5%)   |   NW t vs base |   NW t vs e1f1 |
|:----------|:--------------|--------------------:|-----------------------:|:--------------|:-----------|:---------|:---------|:---------|:-----------|:----------------------|:--------------------|----------------:|------------------------:|--------:|---------------:|-------------:|---------------------:|:-----------------------|:-------------------------|---------------:|---------------:|
| ref_base  | 4.0%          |                0.72 |                   0.74 | -10.0%        | -9.4%      | -4.8%    | -10.0%   | -10.0%   | 93.9%      | 87.4%                 | 6.5%                |              66 |                    0.07 |       0 |              0 |            0 |                      | 7.7%                   | 10.3%                    |                |           0.77 |
| ref_e1f1  | 2.7%          |                1.1  |                   1.64 | -4.1%         | -2.8%      | -1.3%    | -4.1%    | -4.1%    | 94.1%      | 80.3%                 | 13.8%               |              34 |                    0.06 |       1 |              0 |            1 |                    6 | 6.9%                   | 9.3%                     |          -0.77 |                |
| ref_s7_e1 | 3.8%          |                1.11 |                   1.12 | -2.5%         | -2.4%      | -1.8%    | -2.5%    | -2.8%    | 88.2%      | 71.1%                 | 17.1%               |              68 |                         |       7 |              2 |            5 |                    6 | 4.5%                   | 9.8%                     |          -0.12 |           0.73 |
| p1        | 2.9%          |                1.38 |                  16.36 | 0.0%          | 0.0%       | 0.0%     | 0.0%     | 0.0%     | 100.0%     | 0.0%                  | 100.0%              |              10 |                    0.16 |       0 |              0 |            0 |                      | 10.3%                  | 9.7%                     |          -0.53 |           0.13 |
| p2        | 4.5%          |                1.24 |                   1.27 | -4.1%         | -4.5%      | -3.1%    | -4.1%    | -5.2%    | 90.9%      | 77.8%                 | 13.1%               |              66 |                    0.07 |       5 |              2 |            3 |                    6 | 9.7%                   | 10.8%                    |           0.23 |           1.41 |
| p3        | 2.5%          |                1.3  |                   8.18 | -0.1%         | -0.1%      | -0.0%    | -0.1%    | -0.1%    | 90.0%      | 3.5%                  | 86.5%               |              10 |                    0.16 |       1 |              0 |            1 |                    4 | 11.8%                  | 9.3%                     |          -0.78 |          -0.16 |

Under the cost stress:

| rule      | option CAGR   |   Sharpe all months | worst month   | CVaR99   | max DD   | total CAGR (cash 6.5%)   |
|:----------|:--------------|--------------------:|:--------------|:---------|:---------|:-------------------------|
| ref_base  | 3.5%          |                0.65 | -10.0%        | -10.0%   | -10.0%   | 9.7%                     |
| ref_e1f1  | 2.6%          |                1.06 | -4.1%         | -4.1%    | -4.1%    | 9.1%                     |
| ref_s7_e1 | 3.6%          |                1.06 | -2.7%         | -2.7%    | -3.0%    | 9.6%                     |
| p1        | 2.5%          |                1.39 | 0.0%          | 0.0%     | 0.0%     | 9.3%                     |
| p2        | 3.8%          |                1.05 | -4.1%         | -4.1%    | -5.6%    | 10.1%                    |
| p3        | 2.1%          |                1.16 | -1.0%         | -1.0%    | -1.0%    | 8.9%                     |

Deflated Sharpe (35 cumulative trials; inputs: each series' monthly Sharpe, months, skewness, kurtosis; variance of monthly Sharpe across the 35 trials in this period = 0.0380):

| rule      |   SR monthly |   DSR SR0 (monthly) | DSR   |
|:----------|-------------:|--------------------:|:------|
| ref_base  |         0.21 |                0.42 | 13.1% |
| ref_e1f1  |         0.32 |                0.42 | 30.6% |
| ref_s7_e1 |         0.32 |                0.42 | 18.8% |
| p1        |         0.4  |                0.42 | 41.8% |
| p2        |         0.36 |                0.42 | 37.3% |
| p3        |         0.38 |                0.42 | 28.3% |

Sensitivity only (P3 prem_ratio threshold; not trials):

| rule         | option CAGR   |   Sharpe all months | worst month   |   months traded |
|:-------------|:--------------|--------------------:|:--------------|----------------:|
| sens_p3_0.10 | 2.3%          |                0.82 | -3.0%         |              16 |
| sens_p3_0.15 | 1.0%          |                0.72 | -0.1%         |               4 |
| p3           | 2.5%          |                1.3  | -0.1%         |              10 |

P3 trades by prem_ratio bucket:

| bucket     |   months traded |   mean return % |   compounded % |   stops |
|:-----------|----------------:|----------------:|---------------:|--------:|
| 0.12-0.15  |               6 |            1.41 |           8.77 |       0 |
| 0.15-0.20  |               2 |            1.94 |           3.91 |       0 |
| above 0.20 |               2 |            1.07 |           2.15 |       1 |

P3 trades by year:

|   year |   months traded |   mean return % |   compounded % |   stops |
|-------:|----------------:|----------------:|---------------:|--------:|
|   2019 |               1 |            1.28 |           1.28 |       0 |
|   2020 |               6 |            1.47 |           9.13 |       1 |
|   2021 |               2 |            1.41 |           2.85 |       0 |
|   2022 |               1 |            1.56 |           1.56 |       0 |

Reading:

- P3 (primary): option CAGR 2.5%, Sharpe all months 1.30 (traded months 8.18), worst month -0.1%, traded 10 of 69 months. Base: 4.0% / 0.72 / -10.0%; e1f1: 2.7% / 1.10 / -4.1%.
- P3 beats the base and beats e1f1 on Sharpe over all months (paired Newey-West t -0.78 vs base, -0.16 vs e1f1).
- P1 alone: CAGR 2.9%, Sharpe 1.38, worst month 0.0%, months traded 10, stops 0 (0 helped, 0 hurt).
- P2 alone: CAGR 4.5%, Sharpe 1.24, worst month -4.1%, months traded 66, stops 5 (2 helped, 3 hurt).
- Cost stress (option CAGR / Sharpe, normal -> stressed): ref_base 4.0% / 0.72 -> 3.5% / 0.65; ref_e1f1 2.7% / 1.10 -> 2.6% / 1.06; ref_s7_e1 3.8% / 1.11 -> 3.6% / 1.06; p1 2.9% / 1.38 -> 2.5% / 1.39; p2 4.5% / 1.24 -> 3.8% / 1.05; p3 2.5% / 1.30 -> 2.1% / 1.16.
- P3 trades only 10 of 69 months; its result rests on few trades. Sharpe over all months counts the cash months as zero option return, which lowers volatility and flatters a rule that rarely trades; on option CAGR P3 earns 2.5% vs 4.0% for the base and 2.7% for e1f1 (less than at least one of them).
- P3's index stop: 1 stops, 0 helped and 1 hurt vs holding to expiry; net effect -0.24 lakh.

Checks:

- credit_gross - slippage - payout - charges + interest = total_pnl: max gap Rs 0.000000 -> PASS
- capital_end = capital_start + total_pnl: max gap Rs 0.000000 -> PASS
- charge items sum to total_charges: max gap Rs 0.000000 -> PASS
- capital_start = previous capital_end: max gap Rs 0.000000 -> PASS

## Holdout (run 1)

**Holdout; aggregate results of the Phase 1 rules on this period were seen earlier.** 24 cycles, entries 2024-11-01 to 2026-09-30, last expiry 2026-10-27.

| rule      | option CAGR   |   Sharpe all months |   Sharpe traded months | worst month   | worst 3m   | CVaR95   | CVaR99   | max DD   | win rate   | break-even win rate   | break-even margin   |   months traded |   avg prem_ratio traded |   stops |   stops helped |   stops hurt |   median trigger day | costs % gross credit   | total CAGR (cash 6.5%)   |   NW t vs base |   NW t vs e1f1 |
|:----------|:--------------|--------------------:|-----------------------:|:--------------|:-----------|:---------|:---------|:---------|:-----------|:----------------------|:--------------------|----------------:|------------------------:|--------:|---------------:|-------------:|---------------------:|:-----------------------|:-------------------------|---------------:|---------------:|
| ref_base  | -2.9%         |               -0.34 |                  -0.38 | -10.0%        | -10.0%     | -6.2%    | -10.0%   | -10.0%   | 89.5%      | 93.6%                 | -4.1%               |              19 |                    0.04 |       0 |              0 |            0 |                      | 6.6%                   | 3.1%                     |                |          -0.81 |
| ref_e1f1  | 0.7%          |                1.5  |                   5.85 | 0.0%          | 0.0%       | 0.0%     | 0.0%     | 0.0%     | 100.0%     | 0.0%                  | 100.0%              |               5 |                    0.03 |       0 |              0 |            0 |                      | 7.4%                   | 7.3%                     |           0.81 |                |
| ref_s7_e1 | 1.1%          |                0.7  |                   0.7  | -1.3%         | -1.1%      | -1.2%    | -1.3%    | -1.3%    | 87.5%      | 79.3%                 | 8.2%                |              24 |                         |       4 |              2 |            2 |                  7.5 | 6.0%                   | 7.0%                     |           0.97 |           0.53 |
| p1        | 1.1%          |                0.71 |                        | 0.0%          | 0.0%       | 0.0%     | 0.0%     | 0.0%     | 100.0%     | 0.0%                  | 100.0%              |               1 |                    0.19 |       0 |              0 |            0 |                      | 4.2%                   | 7.8%                     |           0.78 |           0.36 |
| p2        | 1.5%          |                0.53 |                   0.6  | -2.3%         | -1.9%      | -2.1%    | -2.3%    | -2.3%    | 89.5%      | 83.2%                 | 6.3%                |              19 |                    0.04 |       1 |              1 |            0 |                  7   | 8.0%                   | 7.7%                     |           1.11 |           0.52 |
| p3        | 1.1%          |                0.71 |                        | 0.0%          | 0.0%       | 0.0%     | 0.0%     | 0.0%     | 100.0%     | 0.0%                  | 100.0%              |               1 |                    0.19 |       0 |              0 |            0 |                      | 4.2%                   | 7.8%                     |           0.78 |           0.36 |

Under the cost stress:

| rule      | option CAGR   |   Sharpe all months | worst month   | CVaR99   | max DD   | total CAGR (cash 6.5%)   |
|:----------|:--------------|--------------------:|:--------------|:---------|:---------|:-------------------------|
| ref_base  | -2.9%         |               -0.35 | -10.0%        | -10.0%   | -10.0%   | 3.1%                     |
| ref_e1f1  | 0.7%          |                1.5  | 0.0%          | 0.0%     | 0.0%     | 7.3%                     |
| ref_s7_e1 | 1.0%          |                0.65 | -1.3%         | -1.3%    | -1.3%    | 6.9%                     |
| p1        | 1.0%          |                0.71 | 0.0%          | 0.0%     | 0.0%     | 7.8%                     |
| p2        | 1.4%          |                0.49 | -2.3%         | -2.3%    | -2.3%    | 7.6%                     |
| p3        | 1.0%          |                0.71 | 0.0%          | 0.0%     | 0.0%     | 7.8%                     |

Months traded in the holdout: P1 1, P3 1 of 24. **With fewer than 6 traded months, the holdout cannot judge P1, P3.**

Reading (holdout):

- P3 (primary): option CAGR 1.1%, Sharpe all months 0.71 (traded months nan), worst month 0.0%, traded 1 of 24 months. Base: -2.9% / -0.34 / -10.0%; e1f1: 0.7% / 1.50 / 0.0%.
- P3 beats the base and **does not beat** e1f1 on Sharpe over all months (paired Newey-West t 0.78 vs base, 0.36 vs e1f1).
- P1 alone: CAGR 1.1%, Sharpe 0.71, worst month 0.0%, months traded 1, stops 0 (0 helped, 0 hurt).
- P2 alone: CAGR 1.5%, Sharpe 0.53, worst month -2.3%, months traded 19, stops 1 (1 helped, 0 hurt).
- Cost stress (option CAGR / Sharpe, normal -> stressed): ref_base -2.9% / -0.34 -> -2.9% / -0.35; ref_e1f1 0.7% / 1.50 -> 0.7% / 1.50; ref_s7_e1 1.1% / 0.70 -> 1.0% / 0.65; p1 1.1% / 0.71 -> 1.0% / 0.71; p2 1.5% / 0.53 -> 1.4% / 0.49; p3 1.1% / 0.71 -> 1.0% / 0.71.
- P3 trades only 1 of 24 months; its result rests on few trades. Sharpe over all months counts the cash months as zero option return, which lowers volatility and flatters a rule that rarely trades; on option CAGR P3 earns 1.1% vs -2.9% for the base and 0.7% for e1f1 (more).

Holdout checks:

- credit_gross - slippage - payout - charges + interest = total_pnl: max gap Rs 0.000000 -> PASS
- capital_end = capital_start + total_pnl: max gap Rs 0.000000 -> PASS
- charge items sum to total_charges: max gap Rs 0.000000 -> PASS
- capital_start = previous capital_end: max gap Rs 0.000000 -> PASS

Deflated Sharpe is not computed for the holdout: the other 32 trials were never run on it, so the trial variance is unknown, and 24 months are too few.

Run note: two earlier attempts crashed while drawing a chart before the log was written and before any result was read; see `holdout_runs.log`.
