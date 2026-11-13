# Long-only pairs on the point-in-time Nifty 500

Development 2011-2022 is the decision period. 2023 to Nov 2026 is a **seen holdout**: the rebuild already looked at it, so it is not out of sample.

## Step 1: leg split of the rebuild's development trades

Each leg is Rs 50,000. Excess is measured against the equal-weight Nifty 500 (point-in-time members) over the same holding days. For the short leg, excess = EW return − stock return, so it is positive when the shorted stock lagged the market.

| Metric | long | short |
|---|---|---|
| Trades | 610 | 610 |
| Total gross P&L (Rs) | 421,080 | -33,875 |
| Total net P&L (Rs) | 303,732 | -149,682 |
| Mean net P&L per trade (Rs) | 498 | -245 |
| Win rate (net > 0) | 45.90% | 49.67% |
| Mean excess vs EW Nifty 500 per trade | 0.29% | 0.98% |
| t-stat of excess | 0.59 | 2.13 |
| Excess win rate | 46.89% | 53.28% |

## Development

| Metric | A (vs 50/50 buy-and-hold) | A benchmark: 50/50 buy-and-hold (vs cash) | B hedged (vs cash) | B-unhedged (vs EW Nifty 500) | EW Nifty 500 (vs cash) |
|---|---|---|---|---|---|
| CAGR | 7.65% | 6.32% | 0.41% | 2.27% | 10.36% |
| Sharpe | 0.45 | 0.41 | 0.10 | 0.32 | 0.63 |
| Max drawdown | -54.20% | -47.37% | -16.78% | -23.91% | -56.12% |
| Excess vs benchmark (% / month) | 0.12% | 0.76% | 0.05% | -0.83% | 1.05% |
| t-stat of excess | 0.88 | 1.25 | 0.34 | -1.90 | 1.84 |
| Turnover (x capital / yr) | 7.06 | 0.00 | 10.39 | 5.20 | 0.00 |
| Cost drag (% capital / yr) | 1.36% | 0.00% | 1.15% | 0.99% | 0.00% |
| Beta to Nifty 500 (monthly) | 1.18 | 1.20 | 0.10 | 0.34 | 1.22 |

## Seen holdout

| Metric | A (vs 50/50 buy-and-hold) | A benchmark: 50/50 buy-and-hold (vs cash) | B hedged (vs cash) | B-unhedged (vs EW Nifty 500) | EW Nifty 500 (vs cash) |
|---|---|---|---|---|---|
| CAGR | 13.96% | 14.30% | -0.73% | 2.22% | 16.92% |
| Sharpe | 1.18 | 1.23 | -0.12 | 0.38 | 1.04 |
| Max drawdown | -14.05% | -12.99% | -12.85% | -11.02% | -23.49% |
| Excess vs benchmark (% / month) | -0.02% | 1.16% | -0.04% | -1.21% | 1.42% |
| t-stat of excess | -0.13 | 2.08 | -0.14 | -2.20 | 1.78 |
| Turnover (x capital / yr) | 6.87 | 0.00 | 10.54 | 5.28 | 0.00 |
| Cost drag (% capital / yr) | 1.60% | 0.00% | 1.39% | 1.23% | 0.00% |
| Beta to Nifty 500 (monthly) | 0.78 | 0.73 | 0.14 | 0.41 | 1.18 |

## A minus benchmark per slot (one slot = one pair for one 6-month window)

| Period | Slot-windows | Mean excess per window | t-stat | Share of slots beating benchmark |
|---|---:|---:|---:|---:|
| development | 480 | 1.35% | 1.75 | 53% |
| seen holdout | 160 | -0.23% | -0.16 | 48% |

## Trials and deflated Sharpe

| trial | formation_months | entry_z | dev_sharpe | dev_cagr | dev_max_dd | trades | dev_sharpe_fo | chosen | variant | best_of_9_on_dev |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 6 | 1.5 | -0.642 | -0.0551 | -0.591 | 685 | -0.105 | False | long-short pairs (rebuild) | False |
| 2 | 6 | 2.0 | -0.459 | -0.0301 | -0.4251 | 541 | 0.039 | False | long-short pairs (rebuild) | False |
| 3 | 6 | 2.5 | -0.683 | -0.0367 | -0.4225 | 438 | -0.207 | False | long-short pairs (rebuild) | False |
| 4 | 12 | 1.5 | 0.068 | 0.0023 | -0.2014 | 767 | 0.485 | False | long-short pairs (rebuild) | False |
| 5 | 12 | 2.0 | 0.251 | 0.0122 | -0.1247 | 610 | 0.476 | True | long-short pairs (rebuild) | False |
| 6 | 12 | 2.5 | -0.055 | -0.0039 | -0.139 | 495 | 0.214 | False | long-short pairs (rebuild) | False |
| 7 | 12 | 2.0 | 0.453 | 0.0765 | -0.542 | 1269 | nan | False | long-only A: pair switching | True |
| 8 | 12 | 2.0 | 0.102 | 0.0041 | -0.1678 | 610 | nan | False | long-only B: cheap leg + Nifty futures hedge | False |
| 9 | 12 | 2.0 | 0.322 | 0.0227 | -0.2391 | 610 | nan | False | long-only B-unhedged | False |

Best development variant out of 9: **long-only A: pair switching** (trial 7), with a development Sharpe of 0.45. The best of 9 zero-skill trials would be expected to reach 0.64. **Deflated Sharpe: 0.26**. Its Sharpe on the seen holdout was 1.18.

Trials 1-6 enter at |z| > 1.5, 2.0 or 2.5. For trials 7-9, `entry_z` is the switch/entry threshold (2.0). Ranking by raw Sharpe mixes market-neutral and long-only variants, so A ranks first largely because of market beta.

## Conclusion

**No edge.** A (pair switching) beat its 50/50 buy-and-hold benchmark by 0.12% a month in development (t = 0.88) and by -0.02% a month in the seen holdout (t = -0.13). Its Sharpe (0.45 in development) is almost all market exposure: the buy-and-hold benchmark alone had 0.41, and the deflated Sharpe over 9 trials is 0.26. B (cheap leg, hedged with Nifty futures) had a Sharpe of 0.10 in development and -0.12 in the seen holdout. B-unhedged trailed the equal-weight Nifty 500 by 0.83% a month in development, mostly because it is in cash much of the time (beta 0.34).

**Was the money in the long leg?** In rupees, yes: the long leg made Rs 303,732 net and the short leg lost Rs 149,682. But that is the market rising in 2011-2022. Measured against the equal-weight Nifty 500 over the same days, the long leg added only 0.29% a trade (t = 0.59). The short leg added 0.98% (t = 2.13), because the rich stock tended to lag. So the little relative-value signal there is came mostly from the short leg, which is exactly the leg a long-only version drops. The trade-level t-stats treat overlapping trades as independent, so they overstate significance.
