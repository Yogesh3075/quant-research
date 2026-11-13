# Phase 2 report

Design: 132 cycles, entries 2008-02-01 to 2018-12-28. Option-only returns (option_pnl_net / capital at cycle start, no cash interest) are the headline; their Sharpe has no risk-free deduction. Variants d20/d15 = short put |delta|; H1 = long put |delta| 0.05, H2 = long put 5% of S0 below, H3 = naked put sized for a 25% fall. ref_* = Phase 1 rules (not trials), with the Phase 1 skip rule (p1skip) or the fallback rule.

## Design results

| variant                 | option CAGR   |   option Sharpe | worst month   | worst 3m   | CVaR95   | CVaR99   | max DD   |   skew | win rate   | avg win   | avg loss   | break-even win rate   | break-even margin   | avg credit % cap   | avg max risk % cap   | costs % gross credit   |   skipped |   fallback | avg worst MTM   | total CAGR (cash 6.5%)   | total max DD   |
|:------------------------|:--------------|----------------:|:--------------|:-----------|:---------|:---------|:---------|-------:|:-----------|:----------|:-----------|:----------------------|:--------------------|:-------------------|:---------------------|:-----------------------|----------:|-----------:|:----------------|:-------------------------|:---------------|
| d20_h1                  | -2.5%         |           -0.22 | -10.0%        | -13.9%     | -9.4%    | -10.0%   | -37.2%   |  -2.62 | 83.7%      | 0.9%      | -5.9%      | 86.5%                 | -2.8%               | 0.9%               | 10.0%                | 5.9%                   |         9 |         17 | -1.5%           | 3.4%                     | -18.8%         |
| d20_h2                  | -1.3%         |           -0.1  | -10.0%        | -11.8%     | -8.5%    | -10.0%   | -30.4%   |  -2.54 | 84.3%      | 0.9%      | -5.5%      | 85.4%                 | -1.2%               | 0.9%               | 10.0%                | 6.4%                   |         5 |         17 | -1.5%           | 4.7%                     | -15.9%         |
| d20_h3                  | 2.0%          |            0.69 | -3.1%         | -2.9%      | -2.2%    | -3.1%    | -5.3%    |  -0.68 | 85.4%      | 0.4%      | -1.4%      | 76.3%                 | 9.1%                | 0.4%               | 10.0%                | 3.4%                   |         2 |         17 | -0.4%           | 8.3%                     | -2.7%          |
| d15_h1                  | -2.1%         |           -0.19 | -10.0%        | -13.4%     | -9.3%    | -10.0%   | -34.2%   |  -2.99 | 87.0%      | 0.8%      | -6.2%      | 89.2%                 | -2.2%               | 0.8%               | 10.0%                | 7.2%                   |         9 |          3 | -1.3%           | 3.9%                     | -17.5%         |
| d15_h2                  | -1.0%         |           -0.1  | -10.0%        | -9.4%      | -7.2%    | -10.0%   | -23.3%   |  -3.19 | 86.9%      | 0.7%      | -4.8%      | 88.0%                 | -1.2%               | 0.7%               | 10.0%                | 6.8%                   |        10 |          3 | -1.1%           | 5.1%                     | -15.6%         |
| d15_h3                  | 2.4%          |            0.69 | -3.1%         | -2.7%      | -2.0%    | -3.1%    | -5.3%    |   4.2  | 88.5%      | 0.4%      | -1.4%      | 76.9%                 | 11.5%               | 0.4%               | 10.0%                | 3.5%                   |         2 |          3 | -0.3%           | 8.6%                     | -3.0%          |
| ref_put_spread_p1skip   | 1.5%          |            0.24 | -10.0%        | -9.0%      | -7.5%    | -10.0%   | -20.3%   |  -2.72 | 85.5%      | 0.9%      | -4.4%      | 82.4%                 | 3.1%                | 0.9%               | 10.0%                | 8.5%                   |         8 |          0 | -1.3%           | 7.7%                     | -15.9%         |
| ref_put_spread_fallback | 2.2%          |            0.32 | -10.0%        | -9.0%      | -7.5%    | -10.0%   | -18.8%   |  -2.73 | 86.2%      | 0.9%      | -4.4%      | 82.1%                 | 4.0%                | 0.9%               | 10.0%                | 8.4%                   |         2 |          6 | -1.3%           | 8.4%                     | -14.4%         |
| ref_strangle_p1skip     | 2.0%          |            0.25 | -22.9%        | -18.7%     | -8.0%    | -15.7%   | -22.9%   |  -3.48 | 77.7%      | 1.2%      | -3.2%      | 72.7%                 | 5.0%                | 1.4%               | 18.6%                | 3.4%                   |         2 |          0 | -1.3%           | 6.8%                     | -22.5%         |
| ref_strangle_fallback   | 2.2%          |            0.27 | -22.9%        | -18.7%     | -8.0%    | -15.7%   | -22.9%   |  -3.4  | 77.3%      | 1.2%      | -3.1%      | 71.9%                 | 5.4%                | 1.4%               | 18.5%                | 3.4%                   |         0 |          2 | -1.3%           | 7.0%                     | -22.5%         |

Avg max risk: spreads = planned max loss; naked (H3, strangle) = loss if the index settles 25% below S0. Avg worst MTM = average over traded cycles of the worst daily mark-to-market P&L (% of capital).

## Skips and fallbacks (design)

Fallback months (strike taken further out of the money): d15_h1 3, d15_h2 3, d15_h3 3, d20_h1 17, d20_h2 17, d20_h3 17, ref_put_spread_fallback 6, ref_strangle_fallback 2.

Skipped months:

| rule                    | entry_date   | skip_reason                                                    | index_move_pct   |
|:------------------------|:-------------|:---------------------------------------------------------------|:-----------------|
| d20_h1                  | 2008-02-01   | no traded put at or beyond |delta| 0.05 below the short strike | -0.6%            |
| d20_h1                  | 2008-02-29   | no traded put at or beyond |delta| 0.05 below the short strike | -7.5%            |
| d20_h1                  | 2008-03-28   | no traded put at or beyond |delta| 0.05 below the short strike | +1.2%            |
| d20_h1                  | 2008-06-27   | no traded put at or beyond |delta| 0.20                        | +4.7%            |
| d20_h1                  | 2008-09-26   | no traded put at or beyond |delta| 0.20                        | -32.3%           |
| d20_h1                  | 2008-10-31   | no traded put at or beyond |delta| 0.05 below the short strike | -4.5%            |
| d20_h1                  | 2008-12-01   | no traded put at or beyond |delta| 0.05 below the short strike | +8.7%            |
| d20_h1                  | 2008-12-26   | no traded put at or beyond |delta| 0.05 below the short strike | -1.2%            |
| d20_h1                  | 2009-01-30   | no traded put at or beyond |delta| 0.05 below the short strike | -3.1%            |
| d20_h2                  | 2008-02-01   | no traded put at or below short strike - 5% of S0              | -0.6%            |
| d20_h2                  | 2008-02-29   | no traded put at or below short strike - 5% of S0              | -7.5%            |
| d20_h2                  | 2008-06-27   | no traded put at or beyond |delta| 0.20                        | +4.7%            |
| d20_h2                  | 2008-09-26   | no traded put at or beyond |delta| 0.20                        | -32.3%           |
| d20_h2                  | 2008-12-01   | no traded put at or below short strike - 5% of S0              | +8.7%            |
| d20_h3                  | 2008-06-27   | no traded put at or beyond |delta| 0.20                        | +4.7%            |
| d20_h3                  | 2008-09-26   | no traded put at or beyond |delta| 0.20                        | -32.3%           |
| d15_h1                  | 2008-02-01   | no traded put at or beyond |delta| 0.05 below the short strike | -0.6%            |
| d15_h1                  | 2008-02-29   | no traded put at or beyond |delta| 0.05 below the short strike | -7.5%            |
| d15_h1                  | 2008-03-28   | no traded put at or beyond |delta| 0.05 below the short strike | +1.2%            |
| d15_h1                  | 2008-06-27   | no traded put at or beyond |delta| 0.15                        | +4.7%            |
| d15_h1                  | 2008-09-26   | no traded put at or beyond |delta| 0.15                        | -32.3%           |
| d15_h1                  | 2008-10-31   | no traded put at or beyond |delta| 0.05 below the short strike | -4.5%            |
| d15_h1                  | 2008-12-01   | no traded put at or beyond |delta| 0.05 below the short strike | +8.7%            |
| d15_h1                  | 2008-12-26   | no traded put at or beyond |delta| 0.05 below the short strike | -1.2%            |
| d15_h1                  | 2009-01-30   | no traded put at or beyond |delta| 0.05 below the short strike | -3.1%            |
| d15_h2                  | 2008-02-01   | no traded put at or below short strike - 5% of S0              | -0.6%            |
| d15_h2                  | 2008-02-29   | no traded put at or below short strike - 5% of S0              | -7.5%            |
| d15_h2                  | 2008-03-28   | no traded put at or below short strike - 5% of S0              | +1.2%            |
| d15_h2                  | 2008-06-27   | no traded put at or beyond |delta| 0.15                        | +4.7%            |
| d15_h2                  | 2008-09-26   | no traded put at or beyond |delta| 0.15                        | -32.3%           |
| d15_h2                  | 2008-10-31   | no traded put at or below short strike - 5% of S0              | -4.5%            |
| d15_h2                  | 2008-12-01   | no traded put at or below short strike - 5% of S0              | +8.7%            |
| d15_h2                  | 2008-12-26   | no traded put at or below short strike - 5% of S0              | -1.2%            |
| d15_h2                  | 2009-01-30   | no traded put at or below short strike - 5% of S0              | -3.1%            |
| d15_h2                  | 2010-01-29   | no traded put at or below short strike - 5% of S0              | -0.5%            |
| d15_h3                  | 2008-06-27   | no traded put at or beyond |delta| 0.15                        | +4.7%            |
| d15_h3                  | 2008-09-26   | no traded put at or beyond |delta| 0.15                        | -32.3%           |
| ref_put_spread_p1skip   | 2008-06-27   | no traded P strike near 0.90 x S0                              | +4.7%            |
| ref_put_spread_p1skip   | 2008-09-26   | no traded P strike near 0.90 x S0                              | -32.3%           |
| ref_put_spread_p1skip   | 2009-06-26   | no traded P strike near 0.95 x S0                              | +4.5%            |
| ref_put_spread_p1skip   | 2009-11-27   | no traded P strike near 0.90 x S0                              | +5.2%            |
| ref_put_spread_p1skip   | 2010-04-30   | no traded P strike near 0.90 x S0                              | -5.2%            |
| ref_put_spread_p1skip   | 2011-09-30   | no traded P strike near 0.90 x S0                              | +5.0%            |
| ref_put_spread_p1skip   | 2012-06-29   | no traded P strike near 0.90 x S0                              | -4.5%            |
| ref_put_spread_p1skip   | 2014-09-26   | no traded P strike near 0.90 x S0                              | +2.5%            |
| ref_put_spread_fallback | 2008-06-27   | no traded P strike near 0.90 x S0                              | +4.7%            |
| ref_put_spread_fallback | 2008-09-26   | no traded P strike near 0.90 x S0                              | -32.3%           |
| ref_strangle_p1skip     | 2009-03-27   | no traded C strike near 1.05 x S0                              | +11.8%           |
| ref_strangle_p1skip     | 2009-06-26   | no traded P strike near 0.95 x S0                              | +4.5%            |

## Skew diagnostic (design, average IV at entry)

| variant                 | short put IV   | long put IV   | IV skew paid (long - short)   |
|:------------------------|:---------------|:--------------|:------------------------------|
| d20_h1                  | 21.4%          | 24.9%         | 3.6%                          |
| d20_h2                  | 22.5%          | 26.0%         | 3.5%                          |
| d20_h3                  | 23.3%          |               |                               |
| d15_h1                  | 22.2%          | 24.9%         | 2.8%                          |
| d15_h2                  | 22.1%          | 25.7%         | 3.7%                          |
| d15_h3                  | 24.2%          |               |                               |
| ref_put_spread_fallback | 23.4%          | 26.9%         | 3.5%                          |

## Margin (design)

| variant                 | avg margin % cap   | max margin % cap   |
|:------------------------|:-------------------|:-------------------|
| d20_h1                  | 10.0%              | 10.0%              |
| d20_h2                  | 10.0%              | 10.0%              |
| d20_h3                  | 7.9%               | 21.6%              |
| d15_h1                  | 10.0%              | 10.0%              |
| d15_h2                  | 10.0%              | 10.0%              |
| d15_h3                  | 8.8%               | 60.4%              |
| ref_put_spread_p1skip   | 10.0%              | 10.0%              |
| ref_put_spread_fallback | 10.0%              | 10.0%              |
| ref_strangle_p1skip     | 30.0%              | 30.0%              |
| ref_strangle_fallback   | 30.0%              | 30.0%              |

## Deflated Sharpe ratio (design)

Inputs: monthly Sharpe of each series; number of observations; skewness and kurtosis of its monthly option returns; variance of the monthly Sharpe across the 9 cumulative trials on design cycles (d20_h1 -0.064, d20_h2 -0.028, d20_h3 0.198, d15_h1 -0.055, d15_h2 -0.029, d15_h3 0.198, phase1_put_spread 0.068, phase1_iron_condor -0.034, phase1_strangle 0.072); trials N = 9. SR0 is the expected maximum Sharpe of N trials with no skill (Bailey and Lopez de Prado).

| variant                 |   SR monthly |   DSR SR0 (monthly) |   skew_g3 |   kurt_g4 |   months | DSR   |
|:------------------------|-------------:|--------------------:|----------:|----------:|---------:|:------|
| d20_h1                  |        -0.06 |                0.16 |     -2.62 |      8.8  |      132 | 0.3%  |
| d20_h2                  |        -0.03 |                0.16 |     -2.54 |      8.49 |      132 | 1.4%  |
| d20_h3                  |         0.2  |                0.16 |     -0.68 |     10.21 |      132 | 66.1% |
| d15_h1                  |        -0.06 |                0.16 |     -2.99 |     10.89 |      132 | 0.4%  |
| d15_h2                  |        -0.03 |                0.16 |     -3.19 |     13.18 |      132 | 1.3%  |
| d15_h3                  |         0.2  |                0.16 |      4.2  |     46.14 |      132 | 72.1% |
| ref_put_spread_p1skip   |         0.07 |                0.16 |     -2.72 |     11.9  |      132 | 17.3% |
| ref_put_spread_fallback |         0.09 |                0.16 |     -2.73 |     11.83 |      132 | 25.4% |
| ref_strangle_p1skip     |         0.07 |                0.16 |     -3.48 |     31.01 |      132 | 19.2% |
| ref_strangle_fallback   |         0.08 |                0.16 |     -3.4  |     30.13 |      132 | 21.0% |

## Reading (design)

- Best delta variant by option-only Sharpe: d20_h3 (0.69, CAGR 2.0%) vs Phase 1 put spread with the fallback rule (0.32, 2.2%) and with the Phase 1 skip rule (0.24, 1.5%).
- Delta strikes: d20_h2 Sharpe -0.10; d15_h2 Sharpe -0.10 (fixed 5% hedge width, closest to Phase 1) vs 0.32 for the fixed 0.95/0.90 spread: delta strikes did not help.
- Hedge: |delta| 20: H1 -0.22, H2 -0.10, H3 0.69; |delta| 15: H1 -0.19, H2 -0.10, H3 0.69 (option-only Sharpe). Cheaper hedging helped relative to the 5%-wide hedge.
- Skew: the long put's IV exceeds the short put's by d20_h1 +3.6 vol pts; d20_h2 +3.5 vol pts; d15_h1 +2.8 vol pts; d15_h2 +3.7 vol pts. This is the skew premium the hedge pays back.
- Cash: d20_h1 total 3.4%; d20_h2 total 4.7%; d20_h3 total 8.3%; d15_h1 total 3.9%; d15_h2 total 5.1%; d15_h3 total 8.6% a year with idle cash at 6.5%, against 6.5% for cash alone. Variants with option-only CAGR above zero (i.e. beating cash after costs): d20_h3, d15_h3.

## Choice (design cycles only; written before validation)

Rule (pre-registered): highest option-only Sharpe among the 6 variants whose worst month is no worse than -12% of capital and whose break-even margin is at least 3 percentage points.

| variant   |   option Sharpe | worst month   | break-even margin   | option CAGR   |
|:----------|----------------:|:--------------|:--------------------|:--------------|
| d20_h1    |           -0.22 | -10.0%        | -2.8%               | -2.5%         |
| d20_h2    |           -0.1  | -10.0%        | -1.2%               | -1.3%         |
| d20_h3    |            0.69 | -3.1%         | 9.1%                | 2.0%          |
| d15_h1    |           -0.19 | -10.0%        | -2.2%               | -2.1%         |
| d15_h2    |           -0.1  | -10.0%        | -1.2%               | -1.0%         |
| d15_h3    |            0.69 | -3.1%         | 11.5%               | 2.4%          |

**Chosen: d20_h3**: option-only Sharpe 0.69, worst month -3.1%, break-even margin 9.1 pts; qualifying variants: d20_h3, d15_h3.


### Notes on the choice (facts from the design data; the pre-registered rule is applied unchanged)

- d20_h3 and d15_h3 are effectively tied: option-only Sharpe 0.6861 vs 0.6856.
- Both H3 variants skipped the 2008-09-26 cycle (index -32.3%): no traded put at or beyond the target delta existed that day, so the fallback had nothing to take. Their worst month therefore excludes the October 2008 crash. Sized to lose 10% at a 25% fall, a naked put would have lost more than 10% in that cycle.
- d20_h3: notional averaged 0.53x capital, max 1.44x (entry 2008-10-31, short put IV 86%, margin 22% of capital, option return that month +4.3%). Stress sizing gives large positions when the short strike sits close to 0.75 x S0 (high-volatility months).
- d15_h3: notional averaged 0.58x capital, max 4.03x (entry 2008-10-31, short put IV 93%, margin 60% of capital, option return that month +8.9%). Stress sizing gives large positions when the short strike sits close to 0.75 x S0 (high-volatility months).

## Checks

- credit_gross - slippage - payout - charges + interest = total_pnl: max gap Rs 0.000000 -> PASS
- capital_end = capital_start + total_pnl: max gap Rs 0.000000 -> PASS
- charge items sum to total_charges: max gap Rs 0.000000 -> PASS
- capital_start = previous capital_end: max gap Rs 0.000000 -> PASS

## Validation (run 1)

**Validation; aggregate results for this period were seen in Phase 1, so not a clean test.** 69 cycles, entries 2019-02-01 to 2024-09-27.

| variant                 | option CAGR   |   option Sharpe | worst month   | CVaR99   | max DD   | win rate   | break-even margin   | avg credit % cap   | avg max risk % cap   |   skipped |   fallback | avg worst MTM   | total CAGR (cash 6.5%)   | DSR   |
|:------------------------|:--------------|----------------:|:--------------|:---------|:---------|:-----------|:--------------------|:-------------------|:---------------------|----------:|-----------:|:----------------|:-------------------------|:------|
| d20_h1                  | 3.2%          |            0.47 | -10.0%        | -10.0%   | -11.9%   | 91.0%      | 4.5%                | 0.9%               | 10.0%                |         2 |          0 | -0.9%           | 9.4%                     | 54.5% |
| d20_h2                  | 3.4%          |            0.51 | -10.0%        | -10.0%   | -10.0%   | 89.6%      | 5.7%                | 0.9%               | 10.0%                |         2 |          0 | -0.9%           | 9.7%                     | 57.6% |
| d20_h3                  | 1.7%          |            0.38 | -8.9%         | -8.9%    | -8.9%    | 91.2%      | 5.8%                | 0.4%               | 10.0%                |         1 |          0 | -0.4%           | 8.0%                     | 47.6% |
| d15_h1                  | 2.5%          |            0.41 | -10.0%        | -10.0%   | -11.4%   | 92.5%      | 3.7%                | 0.7%               | 10.0%                |         2 |          0 | -0.8%           | 8.7%                     | 50.0% |
| d15_h2                  | 2.6%          |            0.47 | -10.0%        | -10.0%   | -10.0%   | 92.5%      | 4.5%                | 0.6%               | 10.0%                |         2 |          0 | -0.6%           | 8.8%                     | 54.3% |
| d15_h3                  | 3.4%          |            0.42 | -8.8%         | -8.8%    | -8.8%    | 92.6%      | 10.8%               | 0.5%               | 10.0%                |         1 |          0 | -0.4%           | 9.6%                     | 51.8% |
| ref_put_spread_p1skip   | 3.8%          |            0.7  | -10.0%        | -10.0%   | -10.0%   | 93.8%      | 6.4%                | 0.7%               | 10.0%                |         5 |          0 | -0.7%           | 10.1%                    | 68.0% |
| ref_put_spread_fallback | 4.0%          |            0.72 | -10.0%        | -10.0%   | -10.0%   | 93.9%      | 6.5%                | 0.7%               | 10.0%                |         3 |          2 | -0.7%           | 10.3%                    | 69.3% |
| ref_strangle_p1skip     | -0.3%         |            0.01 | -16.5%        | -16.5%   | -19.5%   | 80.9%      | 0.2%                | 0.9%               | 19.0%                |         1 |          0 | -1.0%           | 4.4%                     | 17.6% |
| ref_strangle_fallback   | -0.3%         |            0.01 | -16.5%        | -16.5%   | -19.5%   | 80.9%      | 0.2%                | 0.9%               | 19.0%                |         1 |          0 | -1.0%           | 4.4%                     | 17.6% |

Skips and fallbacks (validation):

Fallback months (strike taken further out of the money): ref_put_spread_fallback 2.

Skipped months:

| rule                    | entry_date   | skip_reason                                                    | index_move_pct   |
|:------------------------|:-------------|:---------------------------------------------------------------|:-----------------|
| d20_h1                  | 2020-03-27   | no traded put at or beyond |delta| 0.05 below the short strike | +13.9%           |
| d20_h1                  | 2023-05-26   | no traded put at or beyond |delta| 0.20                        | +2.6%            |
| d20_h2                  | 2023-01-27   | no traded put at or below short strike - 5% of S0              | -0.5%            |
| d20_h2                  | 2023-05-26   | no traded put at or beyond |delta| 0.20                        | +2.6%            |
| d20_h3                  | 2023-05-26   | no traded put at or beyond |delta| 0.20                        | +2.6%            |
| d15_h1                  | 2020-03-27   | no traded put at or beyond |delta| 0.05 below the short strike | +13.9%           |
| d15_h1                  | 2023-05-26   | no traded put at or beyond |delta| 0.15                        | +2.6%            |
| d15_h2                  | 2023-01-27   | no traded put at or below short strike - 5% of S0              | -0.5%            |
| d15_h2                  | 2023-05-26   | no traded put at or beyond |delta| 0.15                        | +2.6%            |
| d15_h3                  | 2023-05-26   | no traded put at or beyond |delta| 0.15                        | +2.6%            |
| ref_put_spread_p1skip   | 2021-11-26   | no traded P strike near 0.90 x S0                              | +1.0%            |
| ref_put_spread_p1skip   | 2023-01-27   | no traded P strike near 0.90 x S0                              | -0.5%            |
| ref_put_spread_p1skip   | 2023-02-24   | no traded P strike near 0.90 x S0                              | -2.2%            |
| ref_put_spread_p1skip   | 2023-05-26   | no traded P strike near 0.95 x S0                              | +2.6%            |
| ref_put_spread_p1skip   | 2023-10-27   | no traded P strike near 0.90 x S0                              | +5.7%            |
| ref_put_spread_fallback | 2023-01-27   | no traded P strike near 0.90 x S0                              | -0.5%            |
| ref_put_spread_fallback | 2023-05-26   | no traded P strike near 0.95 x S0                              | +2.6%            |
| ref_put_spread_fallback | 2023-10-27   | no traded P strike near 0.90 x S0                              | +5.7%            |
| ref_strangle_p1skip     | 2023-05-26   | no traded P strike near 0.95 x S0                              | +2.6%            |
| ref_strangle_fallback   | 2023-05-26   | no traded P strike near 0.95 x S0                              | +2.6%            |

Reading (validation):

- Best delta variant by option-only Sharpe: d20_h2 (0.51, CAGR 3.4%) vs Phase 1 put spread with the fallback rule (0.72, 4.0%) and with the Phase 1 skip rule (0.70, 3.8%).
- Delta strikes: d20_h2 Sharpe 0.51; d15_h2 Sharpe 0.47 (fixed 5% hedge width, closest to Phase 1) vs 0.72 for the fixed 0.95/0.90 spread: delta strikes did not help.
- Hedge: |delta| 20: H1 0.47, H2 0.51, H3 0.38; |delta| 15: H1 0.41, H2 0.47, H3 0.42 (option-only Sharpe). Cheaper hedging did not help relative to the 5%-wide hedge.
- Skew: the long put's IV exceeds the short put's by d20_h1 +3.6 vol pts; d20_h2 +3.5 vol pts; d15_h1 +3.0 vol pts; d15_h2 +3.8 vol pts. This is the skew premium the hedge pays back.
- Cash: d20_h1 total 9.4%; d20_h2 total 9.7%; d20_h3 total 8.0%; d15_h1 total 8.7%; d15_h2 total 8.8%; d15_h3 total 9.6% a year with idle cash at 6.5%, against 6.5% for cash alone. Variants with option-only CAGR above zero (i.e. beating cash after costs): d20_h1, d20_h2, d20_h3, d15_h1, d15_h2, d15_h3.
- Chosen variant d20_h3: option-only Sharpe 0.69 on design, 0.38 on validation; option CAGR 2.0% -> 1.7%; worst month -8.9%; DSR 0.48.

Validation checks:

- credit_gross - slippage - payout - charges + interest = total_pnl: max gap Rs 0.000000 -> PASS
- capital_end = capital_start + total_pnl: max gap Rs 0.000000 -> PASS
- charge items sum to total_charges: max gap Rs 0.000000 -> PASS
- capital_start = previous capital_end: max gap Rs 0.000000 -> PASS
