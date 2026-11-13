# Pairs trading on the point-in-time Nifty 500: summary

Chosen variant: 12-month formation, entry |z| > 2.0 (picked on development Sharpe only, 2026-11-12T19:28:10).

| Metric | development, all pairs | development, F&O subset | holdout, all pairs | holdout, F&O subset |
|---|---|---|---|---|
| Period | 2011-01 to 2022-12 | 2011-01 to 2022-12 | 2023-01 to 2026-11 | 2023-01 to 2026-11 |
| CAGR | 1.2% | 1.6% | -3.3% | -0.3% |
| Sharpe | 0.25 | 0.48 | -0.54 | -0.17 |
| t-stat | 0.86 | 1.63 | -1.05 | -0.33 |
| Max drawdown | -12.5% | -9.0% | -16.4% | -3.6% |
| Trades | 610 | 306 | 199 | 44 |
| Win rate | 50.5% | 53.9% | 43.2% | 40.9% |
| Avg holding days | 28.15 | 27.36 | 27.49 | 28.30 |
| Converged (exit at mean) | 36.2% | 39.9% | 35.2% | 34.1% |
| Stopped out | 46.6% | 46.4% | 46.7% | 47.7% |
| Window end | 17.0% | 13.7% | 18.1% | 18.2% |
| Delisted / suspended | 1 | 0 | 0 | 0 |
| Turnover (x capital / yr) | 10.38 | 5.18 | 10.56 | 2.33 |
| Cost drag (% capital / yr) | 2.0% | 0.9% | 2.4% | 0.4% |
| Gross P&L (Rs) | 387,205 | 317,178 | -27,126 | 2,922 |
| Net P&L (Rs) | 154,050 | 212,877 | -120,164 | -13,173 |
| Corr with Nifty 500 (monthly) | 0.14 | 0.17 | 0.20 | 0.12 |

Sharpe uses daily returns on Rs 10 lakh (idle capital earns 0), annualised by sqrt(252).

## Deflated Sharpe (6 trials)

| Period | Sharpe | Expected max Sharpe of 6 zero-skill trials | Deflated Sharpe (prob. true SR > 0) |
|---|---:|---:|---:|
| development | 0.25 | 0.51 | 0.18 |
| holdout | -0.54 | 0.51 | 0.02 |

## Development trials

| trial | formation_months | entry_z | dev_sharpe | dev_cagr | dev_max_dd | trades | dev_sharpe_fo | run_at | chosen |
|---|---|---|---|---|---|---|---|---|---|
| 1 | 6 | 1.5 | -0.642 | -0.0551 | -0.591 | 685 | -0.105 | 2026-11-12T19:26:05 | False |
| 2 | 6 | 2.0 | -0.459 | -0.0301 | -0.4251 | 541 | 0.039 | 2026-11-12T19:26:06 | False |
| 3 | 6 | 2.5 | -0.683 | -0.0367 | -0.4225 | 438 | -0.207 | 2026-11-12T19:26:07 | False |
| 4 | 12 | 1.5 | 0.068 | 0.0023 | -0.2014 | 767 | 0.485 | 2026-11-12T19:28:07 | False |
| 5 | 12 | 2.0 | 0.251 | 0.0122 | -0.1247 | 610 | 0.476 | 2026-11-12T19:28:09 | True |
| 6 | 12 | 2.5 | -0.055 | -0.0039 | -0.139 | 495 | 0.214 | 2026-11-12T19:28:10 | False |

## Pairs per window (averages)

| period | members | eligible_stocks | candidates_tested | cointegrated | half_life_ok | selected | selected_fo |
|---|---|---|---|---|---|---|---|
| development | 500.0 | 260.0 | 2976.0 | 260.0 | 235.0 | 20.0 | 10.0 |
| holdout | 501.0 | 472.0 | 9301.0 | 856.0 | 772.0 | 20.0 | 5.0 |

## Conclusion

**No edge.** The chosen variant's development Sharpe was 0.25 (t = 0.86). That is below the 0.51 you'd expect from the best of 6 zero-skill trials, so the deflated Sharpe is 0.18. In the holdout, run once, the Sharpe was -0.54 (t = -1.05): net P&L of Rs -120,164 on Rs 10 lakh, or Rs -27,126 before costs. The F&O subset, the part you could actually short overnight, had a holdout Sharpe of -0.17. About 47% of trades hit the |z| > 4 stop, and their losses roughly cancel the gains from the trades that converged. Costs (2.4% of capital a year) then push the result below zero.

## Notes on method

- Universe: point-in-time Nifty 500 membership, adjusted closes and traded value from the `momentum_research` project (copied into `data/`, not committed).
- Sector: `industry` from `membership.csv`. It is blank for most past members, so blanks are filled from the same project's `industry.csv` (archived NSE constituent files). Stocks still 'Unclassified' are dropped.
- F&O eligibility is point-in-time: the stock-futures list in NSE's F&O bhavcopy on each formation date.
- Size bucket (for slippage) uses the rank by median traded value among Nifty 500 members on the formation date: 1-100 large, 101-250 mid, the rest small. Market cap was not available.
- Signals use day t's close; trades fill at day t+1's close. Each leg is Rs 50,000 (equal rupees long and short), fractional shares, no lot sizes or margin.
- A pair that is stopped out or stops trading is not reopened in the same window. Hedge ratios are only used for the z-score; sizing is dollar-neutral, as specified. 16% of trades have a hedge ratio <= 0.
- The F&O subset uses the same Rs 10 lakh and 20 slots, so its non-F&O slots sit idle.
