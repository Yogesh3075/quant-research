# HMM diagnostics

2-state Gaussian HMM (full covariance, 200 iterations, best of seeds [0, 1, 2, 3, 4]) on NIFTY 50 TRI monthly log return and realised volatility, refitted every month-end on all months up to t.

## Last development fit (2024-09-30, 233 months)

| state | mean monthly log return % | sd of monthly return % | mean realised vol % (annualised) | p(stay) | expected duration (months) |
| --- | --- | --- | --- | --- | --- |
| calm | 1.50 | 4.44 | 14.4 | 0.972 | 35.6 |
| stressed | -0.17 | 11.24 | 36.8 | 0.860 | 7.1 |

Transition matrix (row = from, column = to):

| from / to | calm | stressed |
| --- | --- | --- |
| calm | 0.972 | 0.028 |
| stressed | 0.140 | 0.860 |

## Filtered state at each decision month-end (174 months)

- Stressed (p > 0.5): 5 months (3%); calm: 169 (97%).
- State flips: 4.
- Agreement with the Phase 1 volatility label (stressed = high): 81% of 174 months.
- HMM regime rule fell back to equal weight (fewer than 12 past months in the state): 0 months.
- HMM defensive switch: no fallback rule (it is always defined).
