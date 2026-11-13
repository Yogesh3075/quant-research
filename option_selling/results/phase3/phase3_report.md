# Phase 3 report

Design: 132 cycles, entries 2008-02-01 to 2018-12-28. Base = Phase 1 put spread with the Phase 2 fallback rule. e1 = stop at 2x credit, exit next close; f1 = trade only if ATM IV - trailing 21-day RV is above the expanding median; e1f1 = both. Option-only returns (no cash interest) are the headline; their Sharpe has no risk-free deduction (the margin's interest is earned separately, so this is an excess-over-cash return).

## Design results

| variant   | option CAGR   |   option Sharpe | worst month   | worst 3m   | CVaR95   | CVaR99   | max DD   |   skew | win rate   | avg win   | avg loss   | break-even win rate   | break-even margin   |   months traded |   months filtered |   months skipped (no strike) |   stops | costs % gross credit   | total CAGR (cash 6.5%)   | total max DD   |   corr with TRI | mean diff vs base   |   NW t vs base | DSR   |
|:----------|:--------------|----------------:|:--------------|:-----------|:---------|:---------|:---------|-------:|:-----------|:----------|:-----------|:----------------------|:--------------------|----------------:|------------------:|-----------------------------:|--------:|:-----------------------|:-------------------------|:---------------|----------------:|:--------------------|---------------:|:------|
| base      | 2.2%          |            0.32 | -10.0%        | -9.0%      | -7.5%    | -10.0%   | -18.8%   |  -2.73 | 86.2%      | 0.9%      | -4.4%      | 82.1%                 | 4.0%                |             130 |                 0 |                            2 |       0 | 8.4%                   | 8.4%                     | -14.4%         |            0.58 |                     |                | 16.6% |
| e1        | 3.8%          |            0.72 | -5.2%         | -8.1%      | -4.2%    | -5.0%    | -11.8%   |  -1.29 | 78.5%      | 1.0%      | -2.0%      | 67.2%                 | 11.2%               |             130 |                 0 |                            2 |      26 | 11.4%                  | 10.1%                    | -9.5%          |            0.57 | 0.11%               |           0.92 | 58.3% |
| f1        | 2.8%          |            0.49 | -10.0%        | -10.0%     | -5.3%    | -10.0%   | -11.7%   |  -3.36 | 86.4%      | 1.2%      | -4.2%      | 77.3%                 | 9.1%                |              66 |                64 |                            2 |       0 | 9.0%                   | 9.3%                     | -9.9%          |            0.44 | 0.03%               |           0.32 | 33.8% |
| e1f1      | 3.2%          |            0.73 | -5.2%         | -8.1%      | -3.5%    | -4.5%    | -11.8%   |  -0.92 | 77.3%      | 1.3%      | -1.9%      | 60.3%                 | 17.0%               |              66 |                64 |                            2 |      13 | 11.7%                  | 9.8%                     | -9.5%          |            0.42 | 0.06%               |           0.4  | 59.6% |

Market over the same cycles: NIFTY 50 TRI CAGR 8.0%, Sharpe 0.47; TRI minus cash: mean 0.31% a month, Sharpe 0.18.

## Stops (design)

| variant   | period   | entry      | trigger    | exit       | exit_flag   |   loss_at_trigger_pct |   loss_at_exit_pct |   pnl_if_held_pct |   index_move_pct | stop_effect   |
|:----------|:---------|:-----------|:-----------|:-----------|:------------|----------------------:|-------------------:|------------------:|-----------------:|:--------------|
| e1        | design   | 2008-02-01 | 2008-02-13 | 2008-02-14 | no          |                 -5.02 |              -3.77 |              2.39 |            -0.6  | hurt          |
| e1        | design   | 2008-02-29 | 2008-03-04 | 2008-03-05 | no          |                 -2.34 |              -3.88 |             -4.41 |            -7.53 | helped        |
| e1        | design   | 2008-03-28 | 2008-03-31 | 2008-04-01 | no          |                 -3.09 |              -0.6  |              1.51 |             1.17 | hurt          |
| e1        | design   | 2008-05-30 | 2008-06-09 | 2008-06-10 | no          |                 -3.94 |              -5.17 |            -10.01 |           -11.38 | helped        |
| e1        | design   | 2010-04-30 | 2010-05-07 | 2010-05-10 | no          |                 -1.94 |              -0.23 |              0.86 |            -5.21 | hurt          |
| e1        | design   | 2010-12-31 | 2011-01-07 | 2011-01-10 | no          |                 -1.33 |              -2.98 |             -6.41 |            -8.64 | helped        |
| e1        | design   | 2011-04-29 | 2011-05-05 | 2011-05-06 | no          |                 -2.51 |              -1.25 |             -2.19 |            -5.86 | helped        |
| e1        | design   | 2011-07-29 | 2011-08-05 | 2011-08-08 | no          |                 -2.12 |              -3.26 |            -10.01 |           -11.72 | helped        |
| e1        | design   | 2011-10-28 | 2011-11-15 | 2011-11-16 | no          |                 -2.02 |              -2.53 |            -10.01 |           -11.27 | helped        |
| e1        | design   | 2012-04-27 | 2012-05-10 | 2012-05-11 | no          |                 -1.88 |              -2.42 |              0.88 |            -5.13 | hurt          |
| e1        | design   | 2013-02-01 | 2013-02-26 | 2013-02-27 | no          |                 -0.49 |              -0.18 |             -0.07 |            -5.1  | hurt          |
| e1        | design   | 2013-04-01 | 2013-04-09 | 2013-04-10 | no          |                 -0.97 |              -0.49 |              0.27 |             3.71 | hurt          |
| e1        | design   | 2013-05-31 | 2013-06-13 | 2013-06-14 | no          |                 -1.88 |              -0.64 |             -0.01 |            -5.07 | hurt          |
| e1        | design   | 2013-07-26 | 2013-08-02 | 2013-08-05 | no          |                 -1.46 |              -1.31 |             -6.12 |            -8.11 | helped        |
| e1        | design   | 2013-11-01 | 2013-11-12 | 2013-11-13 | no          |                 -1.33 |              -1.8  |              0.62 |            -3.41 | hurt          |
| e1        | design   | 2014-11-28 | 2014-12-12 | 2014-12-15 | no          |                 -0.49 |              -0.42 |              0.15 |            -4.82 | hurt          |
| e1        | design   | 2015-05-04 | 2015-05-06 | 2015-05-07 | no          |                 -1.1  |              -1.29 |              0.46 |            -0.16 | hurt          |
| e1        | design   | 2015-05-29 | 2015-06-03 | 2015-06-04 | no          |                 -1.27 |              -1.36 |              0.62 |            -0.42 | hurt          |
| e1        | design   | 2015-07-31 | 2015-08-24 | 2015-08-25 | no          |                 -5.63 |              -4.52 |             -3.56 |            -6.84 | hurt          |
| e1        | design   | 2016-01-01 | 2016-01-04 | 2016-01-05 | no          |                 -0.64 |              -0.69 |             -2.59 |            -6.76 | helped        |
| e1        | design   | 2016-01-29 | 2016-02-10 | 2016-02-11 | no          |                 -1.53 |              -4.8  |             -5.46 |            -7.84 | helped        |
| e1        | design   | 2016-10-28 | 2016-11-11 | 2016-11-15 | no          |                 -0.83 |              -2.43 |             -4.51 |            -7.79 | helped        |
| e1        | design   | 2017-07-28 | 2017-08-11 | 2017-08-14 | no          |                 -0.55 |              -0.3  |              0.26 |            -0.96 | hurt          |
| e1        | design   | 2018-01-29 | 2018-02-06 | 2018-02-07 | no          |                 -1.97 |              -2.5  |             -2.63 |            -6.72 | helped        |
| e1        | design   | 2018-08-31 | 2018-09-11 | 2018-09-12 | no          |                 -0.64 |              -0.26 |             -1.89 |            -6.02 | helped        |
| e1        | design   | 2018-09-28 | 2018-10-05 | 2018-10-08 | no          |                 -2.1  |              -1.92 |             -4.23 |            -7.37 | helped        |
| e1f1      | design   | 2008-02-01 | 2008-02-13 | 2008-02-14 | no          |                 -5.02 |              -3.77 |              2.39 |            -0.6  | hurt          |
| e1f1      | design   | 2008-02-29 | 2008-03-04 | 2008-03-05 | no          |                 -2.34 |              -3.88 |             -4.41 |            -7.53 | helped        |
| e1f1      | design   | 2008-03-28 | 2008-03-31 | 2008-04-01 | no          |                 -3.09 |              -0.6  |              1.51 |             1.17 | hurt          |
| e1f1      | design   | 2008-05-30 | 2008-06-09 | 2008-06-10 | no          |                 -3.94 |              -5.17 |            -10.01 |           -11.38 | helped        |
| e1f1      | design   | 2010-04-30 | 2010-05-07 | 2010-05-10 | no          |                 -1.94 |              -0.23 |              0.86 |            -5.21 | hurt          |
| e1f1      | design   | 2011-07-29 | 2011-08-05 | 2011-08-08 | no          |                 -2.12 |              -3.26 |            -10.01 |           -11.72 | helped        |
| e1f1      | design   | 2013-02-01 | 2013-02-26 | 2013-02-27 | no          |                 -0.49 |              -0.18 |             -0.07 |            -5.1  | hurt          |
| e1f1      | design   | 2013-11-01 | 2013-11-12 | 2013-11-13 | no          |                 -1.33 |              -1.8  |              0.62 |            -3.41 | hurt          |
| e1f1      | design   | 2014-11-28 | 2014-12-12 | 2014-12-15 | no          |                 -0.49 |              -0.42 |              0.15 |            -4.82 | hurt          |
| e1f1      | design   | 2017-07-28 | 2017-08-11 | 2017-08-14 | no          |                 -0.55 |              -0.3  |              0.26 |            -0.96 | hurt          |
| e1f1      | design   | 2018-01-29 | 2018-02-06 | 2018-02-07 | no          |                 -1.97 |              -2.5  |             -2.63 |            -6.72 | helped        |
| e1f1      | design   | 2018-08-31 | 2018-09-11 | 2018-09-12 | no          |                 -0.64 |              -0.26 |             -1.89 |            -6.02 | helped        |
| e1f1      | design   | 2018-09-28 | 2018-10-05 | 2018-10-08 | no          |                 -2.1  |              -1.92 |             -4.23 |            -7.37 | helped        |

## Deflated Sharpe ratio (design, 12 cumulative trials)

Inputs: monthly option-only Sharpe of each series, months, skewness and kurtosis of its monthly returns; variance of monthly Sharpe across the 12 trials on design cycles (phase1_put_spread 0.068, phase1_iron_condor -0.034, phase1_strangle 0.072, phase2_d20_h1 -0.064, phase2_d20_h2 -0.028, phase2_d20_h3 0.198, phase2_d15_h1 -0.055, phase2_d15_h2 -0.029, phase2_d15_h3 0.198, phase3_e1 0.209, phase3_f1 0.142, phase3_e1f1 0.212).

| variant   |   SR monthly |   DSR SR0 (monthly) |   months | DSR   |
|:----------|-------------:|--------------------:|---------:|:------|
| base      |         0.09 |                0.19 |      132 | 16.6% |
| e1        |         0.21 |                0.19 |      132 | 58.3% |
| f1        |         0.14 |                0.19 |      132 | 33.8% |
| e1f1      |         0.21 |                0.19 |      132 | 59.6% |

## Reading (design)

- e1: option-only Sharpe 0.72 vs base 0.32; CAGR 3.8% vs 2.2%; worst month -5.2% vs -10.0%; mean monthly difference +0.11% (Newey-West t 0.92, 132 months).
- f1: option-only Sharpe 0.49 vs base 0.32; CAGR 2.8% vs 2.2%; worst month -10.0% vs -10.0%; mean monthly difference +0.03% (Newey-West t 0.32, 132 months).
- e1f1: option-only Sharpe 0.73 vs base 0.32; CAGR 3.2% vs 2.2%; worst month -5.2% vs -10.0%; mean monthly difference +0.06% (Newey-West t 0.40, 132 months).
- Stops in e1: 26, helped 13, hurt 13. Helped in: 2008-02-29 (index -7.5%), 2008-05-30 (index -11.4%), 2010-12-31 (index -8.6%), 2011-04-29 (index -5.9%), 2011-07-29 (index -11.7%), 2011-10-28 (index -11.3%), 2013-07-26 (index -8.1%), 2016-01-01 (index -6.8%), 2016-01-29 (index -7.8%), 2016-10-28 (index -7.8%), 2018-01-29 (index -6.7%), 2018-08-31 (index -6.0%), 2018-09-28 (index -7.4%). Net effect of all stops vs holding: +3.09 lakh.
- Stops in e1f1: 13, helped 6, hurt 7. Helped in: 2008-02-29 (index -7.5%), 2008-05-30 (index -11.4%), 2011-07-29 (index -11.7%), 2018-01-29 (index -6.7%), 2018-08-31 (index -6.0%), 2018-09-28 (index -7.4%). Net effect of all stops vs holding: +0.96 lakh.
- Filter: f1 sat out 64 of 132 months; the base earned -0.07% of capital on average in those months vs +0.49% in the months f1 traded.
- Market: NIFTY 50 TRI CAGR 8.0%; TRI excess over cash Sharpe 0.18. Option-only Sharpe (an excess-over-cash return, since the margin earns interest separately): base 0.32, e1 0.72, f1 0.49, e1f1 0.73. Correlation of monthly option return with the TRI: base 0.58, e1 0.57, f1 0.44, e1f1 0.42.
- Best Sharpe: e1f1. Variants with positive option-only CAGR (beating cash after costs): base, e1, f1, e1f1.

## Choice (design cycles only; written before validation)

Rule (pre-registered): keep a variant only if its design option-only Sharpe beats the base and its worst month and CVaR 99% are no worse than the base's; if several qualify take the highest Sharpe; if none, the frozen rule is the base put spread.

| variant   |   option Sharpe | worst month   | CVaR99   | option CAGR   |
|:----------|----------------:|:--------------|:---------|:--------------|
| base      |            0.32 | -10.0%        | -10.0%   | 2.2%          |
| e1        |            0.72 | -5.2%         | -5.0%    | 3.8%          |
| f1        |            0.49 | -10.0%        | -10.0%   | 2.8%          |
| e1f1      |            0.73 | -5.2%         | -4.5%    | 3.2%          |

- e1: Sharpe 0.723 > base 0.320; worst month -5.17% ok base -10.01%; CVaR99 -4.98% ok base -10.01% -> qualifies
- f1: Sharpe 0.491 > base 0.320; worst month -10.01% ok base -10.01%; CVaR99 -10.01% worse than base -10.01% -> does not qualify
- e1f1: Sharpe 0.733 > base 0.320; worst month -5.17% ok base -10.01%; CVaR99 -4.52% ok base -10.01% -> qualifies

**Chosen: e1f1**


### Notes on the choice (facts from the design data; the pre-registered rule is applied unchanged)

- e1f1 and e1 are close: Sharpe 0.733 vs 0.723; e1f1 traded 66 months vs 130, option CAGR 3.2% vs 3.8%.
- f1 failed only on CVaR 99%: -10.01038% vs base -10.01038% : equal to five decimal places, so the strict "no worse" test failed on floating-point noise. This does not change the choice: f1's Sharpe is below both e1 and e1f1.
- None of the differences vs the base is statistically significant: Newey-West t e1 0.92, f1 0.32, e1f1 0.40 over 132 months.
- All variants share the base's skipped cycles (no traded strike): 2008-06-27 (index +4.7%), 2008-09-26 (index -32.3%). The October 2008 crash is not in any result.

## Checks

- credit_gross - slippage - payout - charges + interest = total_pnl: max gap Rs 0.000000 -> PASS
- capital_end = capital_start + total_pnl: max gap Rs 0.000000 -> PASS
- charge items sum to total_charges: max gap Rs 0.000000 -> PASS
- capital_start = previous capital_end: max gap Rs 0.000000 -> PASS

## Validation (run 1)

**Validation; aggregate results for this period were seen in Phase 1, so not a clean test.** 69 cycles, entries 2019-02-01 to 2024-09-27. Chosen rule (from design): **e1f1**.

| variant   | option CAGR   |   option Sharpe | worst month   | worst 3m   | CVaR95   | CVaR99   | max DD   |   skew | win rate   | avg win   | avg loss   | break-even win rate   | break-even margin   |   months traded |   months filtered |   months skipped (no strike) |   stops | costs % gross credit   | total CAGR (cash 6.5%)   | total max DD   |   corr with TRI | mean diff vs base   |   NW t vs base | DSR   |
|:----------|:--------------|----------------:|:--------------|:-----------|:---------|:---------|:---------|-------:|:-----------|:----------|:-----------|:----------------------|:--------------------|----------------:|------------------:|-----------------------------:|--------:|:-----------------------|:-------------------------|:---------------|----------------:|:--------------------|---------------:|:------|
| base      | 4.0%          |            0.72 | -10.0%        | -9.4%      | -4.8%    | -10.0%   | -10.0%   |  -4.63 | 93.9%      | 0.7%      | -4.8%      | 87.4%                 | 6.5%                |              66 |                 0 |                            3 |       0 | 7.7%                   | 10.3%                    | -9.6%          |            0.71 |                     |                | 50.9% |
| e1        | 4.2%          |            1.12 | -4.1%         | -4.3%      | -3.1%    | -4.1%    | -5.0%    |  -1.88 | 86.4%      | 0.7%      | -1.8%      | 71.5%                 | 14.8%               |              66 |                 0 |                            3 |       8 | 9.6%                   | 10.5%                    | -4.0%          |            0.61 | 0.01%               |           0.07 | 76.8% |
| f1        | 3.0%          |            1.25 | -4.1%         | -2.8%      | -1.0%    | -4.1%    | -4.1%    |  -3.2  | 97.1%      | 0.6%      | -4.1%      | 86.4%                 | 10.7%               |              34 |                33 |                            2 |       0 | 6.4%                   | 9.6%                     | -3.6%          |            0.3  | -0.09%              |          -0.59 | 77.3% |
| e1f1      | 2.7%          |            1.1  | -4.1%         | -2.8%      | -1.3%    | -4.1%    | -4.1%    |  -2.95 | 94.1%      | 0.7%      | -2.7%      | 80.3%                 | 13.8%               |              34 |                33 |                            2 |       1 | 6.9%                   | 9.3%                     | -3.6%          |            0.29 | -0.11%              |          -0.77 | 72.2% |

Market over the same cycles: NIFTY 50 TRI CAGR 16.4%, Sharpe 0.98; TRI minus cash: Sharpe 0.61.

Stops (validation):

| variant   | period     | entry      | trigger    | exit       | exit_flag   |   loss_at_trigger_pct |   loss_at_exit_pct |   pnl_if_held_pct |   index_move_pct | stop_effect   |
|:----------|:-----------|:-----------|:-----------|:-----------|:------------|----------------------:|-------------------:|------------------:|-----------------:|:--------------|
| e1        | validation | 2019-07-26 | 2019-08-01 | 2019-08-02 | no          |                 -0.68 |              -0.71 |              0.28 |            -2.98 | hurt          |
| e1        | validation | 2019-09-27 | 2019-10-07 | 2019-10-09 | no          |                 -1.1  |              -0.37 |              0.51 |             3.17 | hurt          |
| e1        | validation | 2019-12-27 | 2020-01-08 | 2020-01-09 | no          |                 -0.49 |              -0.05 |              0.24 |            -1.71 | hurt          |
| e1        | validation | 2020-02-28 | 2020-03-09 | 2020-03-11 | no          |                 -3.24 |              -3.03 |            -10.04 |           -22.86 | helped        |
| e1        | validation | 2022-04-29 | 2022-05-09 | 2022-05-10 | no          |                 -1.87 |              -2.25 |             -0.17 |            -5.45 | hurt          |
| e1        | validation | 2022-05-27 | 2022-06-16 | 2022-06-17 | no          |                 -2.65 |              -2.86 |              1.16 |            -3.5  | hurt          |
| e1        | validation | 2024-07-26 | 2024-08-05 | 2024-08-06 | no          |                 -1.79 |              -1.24 |              0.37 |             1.28 | hurt          |
| e1        | validation | 2024-09-27 | 2024-10-03 | 2024-10-04 | no          |                 -0.62 |              -1.28 |             -4.83 |            -7.54 | helped        |
| e1f1      | validation | 2024-07-26 | 2024-08-05 | 2024-08-06 | no          |                 -1.79 |              -1.24 |              0.37 |             1.28 | hurt          |

Reading (validation):

- e1: option-only Sharpe 1.12 vs base 0.72; CAGR 4.2% vs 4.0%; worst month -4.1% vs -10.0%; mean monthly difference +0.01% (Newey-West t 0.07, 69 months).
- f1: option-only Sharpe 1.25 vs base 0.72; CAGR 3.0% vs 4.0%; worst month -4.1% vs -10.0%; mean monthly difference -0.09% (Newey-West t -0.59, 69 months).
- e1f1: option-only Sharpe 1.10 vs base 0.72; CAGR 2.7% vs 4.0%; worst month -4.1% vs -10.0%; mean monthly difference -0.11% (Newey-West t -0.77, 69 months).
- Stops in e1: 8, helped 2, hurt 6. Helped in: 2020-02-28 (index -22.9%), 2024-09-27 (index -7.5%). Net effect of all stops vs holding: -0.02 lakh.
- Stops in e1f1: 1, helped 0, hurt 1. Helped in: none. Net effect of all stops vs holding: -0.27 lakh.
- Filter: f1 sat out 33 of 69 months; the base earned +0.19% of capital on average in those months vs +0.51% in the months f1 traded.
- Market: NIFTY 50 TRI CAGR 16.4%; TRI excess over cash Sharpe 0.61. Option-only Sharpe (an excess-over-cash return, since the margin earns interest separately): base 0.72, e1 1.12, f1 1.25, e1f1 1.10. Correlation of monthly option return with the TRI: base 0.71, e1 0.61, f1 0.30, e1f1 0.29.
- Best Sharpe: f1. Variants with positive option-only CAGR (beating cash after costs): base, e1, f1, e1f1.

Validation checks:

- credit_gross - slippage - payout - charges + interest = total_pnl: max gap Rs 0.000000 -> PASS
- capital_end = capital_start + total_pnl: max gap Rs 0.000000 -> PASS
- charge items sum to total_charges: max gap Rs 0.000000 -> PASS
- capital_start = previous capital_end: max gap Rs 0.000000 -> PASS

Frozen rule: **e1f1**, see `frozen_rule.md`.
