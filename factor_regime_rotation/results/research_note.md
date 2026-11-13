# Factor Regime Rotation: research note

*Hypothetical backtest on index data. Not investment advice. All numbers on this page are generated from the files in `results/` by `python main.py note`.*

**Main conclusion.** Over 2010 to 2024 an equal-weight mix of four Nifty factor indices clearly beat the market indices, but none of the 5 rules that tried to time or tilt the factors beat simply holding all four equally, and on the 24 unseen holdout months every one of them did worse than equal weight.

## 1. Question and data

Do Indian factor indices behave differently in different market regimes, and does a monthly allocation that follows the regime beat a fixed equal-weight mix after costs?

The data is the daily Total Returns Index of NSE's factor and market indices, downloaded from niftyindices.com: 5,357 trading days from 01 Apr 2005 to 05 Nov 2026. The series match NSE's own published 1, 3 and 5-year returns to two decimals. Before each index's launch date the history is **back-calculated by NSE**, not real performance. The known launch dates are Momentum 30 (25 Aug 2020), Quality 30 (17 Apr 2018) and Low Volatility 30 (08 Jul 2016). For Value 30, the factsheet still needs checking.

## 2. Method

- **Traded factors:** momentum, quality, value, lowvol. Alpha 30 is excluded because its monthly returns correlate 0.97 with momentum.
- **Rule-based regimes** (NIFTY 50, data up to t only): trend (12-month return above or below 0) crossed with volatility (63-day volatility above or below its expanding median). There are 197 labelled development months, and 65% of them are up/low.
- **HMM regimes:** a 2-state Gaussian hidden Markov model on the NIFTY 50 monthly log return and realised volatility, refitted every month on data up to t. The current state is the filtered probability.
- **Strategies:** equal weight; factor momentum (top 2 by 12-month return); regime rule and HMM regime rule (top 2 by past performance in the current regime or state); HMM defensive switch (quality + lowvol when p(stressed) > 0.5); static momentum + quality (50/50).
- **Walk-forward:** expanding window. The first decision is at Apr 2010, and each position is decided at month-end t and held over the next month.
- **Costs:** ETF expense ratios per factor (momentum 0.76%, quality 0.25%, value 0.26%, lowvol 0.36% a year) and 0.20% per unit of one-way turnover. Both need checking.
- **Locked holdout:** the last 24 month-ends, scored once (run 1, 2026-11-05T23:12:54, decisions 2024-10-31 to 2026-09-30, scored months 2024-11-29 to 2026-10-30 (24)).
- **Trials:** 5 rules were tested in total. The static momentum + quality rule was chosen after seeing development data.

## 3. Results

**Development** (2010-05 to 2024-10, 174 months; mostly back-calculated history):

| strategy | total return % | CAGR % | vol % | Sharpe | max DD % | turnover / yr | vs EW %/month (t) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Equal weight | 814.8 | 16.5 | 16.3 | 0.64 | -27.7 | 0.11 |  |
| Factor momentum | 959.3 | 17.7 | 15.5 | 0.73 | -22.0 | 1.47 | +0.08 (0.58) |
| Regime rule | 864.5 | 16.9 | 16.1 | 0.66 | -22.6 | 1.61 | +0.03 (0.23) |
| HMM regime rule | 980.3 | 17.8 | 14.7 | 0.77 | -19.9 | 0.27 | +0.08 (0.66) |
| HMM defensive switch | 811.9 | 16.5 | 16.2 | 0.64 | -27.7 | 0.24 | -0.00 (-0.28) |
| Static momentum + quality * | 976.3 | 17.8 | 14.6 | 0.77 | -19.9 | 0.06 | +0.07 (0.63) |
| NIFTY 200 TRI † | 491.2 | 13.0 | 17.0 | 0.44 | -28.9 |  | -0.24 (-2.51) |
| NIFTY 50 TRI † | 448.3 | 12.5 | 16.7 | 0.41 | -29.1 |  | -0.29 (-2.27) |

**Live period** (2020-09 to 2024-10, 50 months; after the last known launch date; inside development):

| strategy | total return % | CAGR % | vol % | Sharpe | max DD % | turnover / yr | vs EW %/month (t) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Equal weight | 196.3 | 29.8 | 14.5 | 1.45 | -11.6 | 0.11 |  |
| Factor momentum | 222.2 | 32.4 | 15.2 | 1.52 | -12.7 | 1.51 | +0.18 (0.70) |
| Regime rule | 152.3 | 24.9 | 14.7 | 1.16 | -17.5 | 1.74 | -0.32 (-1.93) |
| HMM regime rule | 162.3 | 26.0 | 14.4 | 1.25 | -17.0 | 0.31 | -0.25 (-1.54) |
| HMM defensive switch | 197.3 | 29.9 | 14.5 | 1.46 | -11.6 | 0.35 | +0.01 (0.96) |
| Static momentum + quality * | 160.7 | 25.9 | 14.4 | 1.25 | -17.0 | 0.08 | -0.26 (-1.66) |
| NIFTY 200 TRI † | 141.8 | 23.6 | 14.1 | 1.13 | -10.5 |  | -0.42 (-2.12) |
| NIFTY 50 TRI † | 123.3 | 21.3 | 13.8 | 1.02 | -9.9 |  | -0.59 (-2.22) |

**Holdout** (2024-11 to 2026-10, 24 months; scored once):

| strategy | total return % | CAGR % | vol % | Sharpe | max DD % | turnover / yr | vs EW %/month (t) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Equal weight | -5.0 | -2.5 | 16.3 | -0.47 | -14.7 | 0.10 |  |
| Factor momentum | -13.0 | -6.7 | 16.7 | -0.71 | -18.8 | 2.55 | -0.36 (-1.27) |
| Regime rule | -20.0 | -10.6 | 16.6 | -0.97 | -19.7 | 2.80 | -0.71 (-3.98) |
| HMM regime rule | -14.1 | -7.3 | 17.5 | -0.71 | -18.2 | 1.06 | -0.40 (-1.86) |
| HMM defensive switch | -6.0 | -3.0 | 16.0 | -0.51 | -14.7 | 0.58 | -0.05 (-1.13) |
| Static momentum + quality * | -12.8 | -6.6 | 17.5 | -0.67 | -18.2 | 0.07 | -0.34 (-1.55) |
| NIFTY 200 TRI † | -1.2 | -0.6 | 15.5 | -0.37 | -14.2 |  | +0.15 (0.61) |
| NIFTY 50 TRI † | -2.6 | -1.3 | 14.2 | -0.47 | -14.7 |  | +0.08 (0.21) |

\* chosen after seeing development data. † index, not investable as is, no costs. "vs EW" is the mean monthly return difference against equal weight with a Newey-West t-statistic (3 lags).

## 4. Findings

**A diversified factor mix against the market.** Against NIFTY 200, equal weight was: development, ahead by 0.24% a month (t = 2.51); live period, ahead by 0.42% a month (t = 2.12); holdout, behind by 0.15% a month (t = -0.61). The development and live gaps come from holding the factor indices, not from timing, and mostly from back-calculated years. On the holdout equal weight's CAGR was -2.5%, and the edge over the market did not appear.

**Timing against equal weight.** No rule beat equal weight with a t-statistic above 2 in any period.

- Factor momentum: development, ahead by 0.08% a month (t = 0.58); live period, ahead by 0.18% a month (t = 0.70); holdout, behind by 0.36% a month (t = -1.27).
- Regime rule: development, ahead by 0.03% a month (t = 0.23); live period, behind by 0.32% a month (t = -1.93); holdout, behind by 0.71% a month (t = -3.98).
- HMM regime rule: development, ahead by 0.08% a month (t = 0.66); live period, behind by 0.25% a month (t = -1.54); holdout, behind by 0.40% a month (t = -1.86).
- HMM defensive switch: development, behind by 0.00% a month (t = -0.28); live period, ahead by 0.01% a month (t = 0.96); holdout, behind by 0.05% a month (t = -1.13).
- Static momentum + quality: development, ahead by 0.07% a month (t = 0.63); live period, behind by 0.26% a month (t = -1.66); holdout, behind by 0.34% a month (t = -1.55).

Differences with t below -2: Regime rule (holdout, t = -3.98). With 5 trials and few months, even these should be read with care.

In the cost sensitivity (expenses ×0.5 and ×1.5, switching 0.10% and 0.40%), a rule's sign against equal weight changes in 0 of 15 rule-and-period cases.

**What the HMM detected.** The model works as a crisis detector, not a market cycle. In the last development fit:
- The calm state has a mean monthly log return of 1.50% and realised volatility of 14%.
- The stressed state has -0.17% and 37%.
- Only 5 of 174 development decisions (3%) were stressed (Mar 2020, Apr 2020, May 2020, Jun 2020, Jun 2024). In the holdout it was stressed in 1 of 24 decisions.

In development the HMM regime rule held momentum + quality in 166 of 174 months, and the defensive switch was equal weight in 169 of 174 months.

**The static tilt on unseen data.** Static momentum + quality was ahead by 0.07% a month (t = 0.63) against equal weight in development. The HMM regime rule was ahead by 0.08% a month (t = 0.66), almost the same, which supports the view that its edge was the tilt. On the holdout the tilt was behind by 0.34% a month (t = -1.55), with a total return of -12.8% against -5.0% for equal weight. The development edge did not carry over.

## 5. Limitations

- Most of the development history is NSE's back-calculation, not live index performance. Index rules designed later may fit the earlier data better than they would have in real time.
- There are few regime episodes. Up/low is 65% of labelled months, and the HMM was stressed in only 5 development decisions, so regime-conditional averages rest on few months.
- The holdout is short (24 months), so the tests have very low power. A lack of significance there is not evidence that strategies are equal.
- Costs are approximate (ETF expense ratios from factsheets, a rough switching cost). Against Phase 2's flat rate, development CAGR changed by -0.24 to -0.12 points. Tracking error and taxes are not modelled.
- This is a hypothetical backtest of indices, not a record of investable returns, and not investment advice.

## 6. What to test next

- Factor timing with signals that have more episodes: valuation spreads between factors, or factor momentum with a shorter look-back, tested on the same pre-registered walk-forward.
- A longer live record: re-score all rules once a further 24 months of post-launch data exist, without changing them.
- Implementation detail: ETF tracking difference and taxes on switching, which would weigh against the higher-turnover rules.
