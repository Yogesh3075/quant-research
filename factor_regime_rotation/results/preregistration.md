# Pre-registration: holdout test (Phase 3)

Written and committed on 5 Nov 2026, before the holdout data has been loaded by any strategy code. The matching settings are in `config.yaml`. Nothing below changes after the holdout is scored.

## Holdout

- **Locked month-ends:** 29 Nov 2024 to 30 Oct 2026 (24). No phase so far has loaded them.
- **Scored months:** the 24 monthly returns from Nov 2024 to Oct 2026.
  - The first position is decided at 31 Oct 2024, the last development month-end, using only data up to that date, and held over Nov 2024.
  - The last position is decided at 30 Sep 2026 and held over Oct 2026.
  - Development's last decision (30 Sep 2024) was held over Oct 2024, so starting here leaves no month unscored.
- **Walk-forward:** the same as in development. The expanding window continues into the holdout, and the HMM is refitted every month-end on data up to t. The regime labels, the momentum signal and the regime rankings all keep updating the same way.
- **One run only:** `python main.py holdout` refuses to run if `results/holdout_runs.log` already shows a run.

## Strategies scored (fixed list)

| # | strategy | trial | rule |
| --- | --- | --- | --- |
| 1 | Equal weight | reference | 25% each in momentum, quality, value, lowvol |
| 2 | Factor momentum | trial 1 | top 2 by trailing 12-month return, 50% each |
| 3 | Regime rule | trial 2 | top 2 by average return minus EW in past months of the same rule-based regime (trend × volatility); fewer than 12 such months means EW |
| 4 | HMM regime rule | trial 3 | the same ranking with the 2-state HMM state |
| 5 | HMM defensive switch | trial 4 | p(stressed) > 0.5 means 50% quality + 50% lowvol, otherwise EW |
| 6 | Static momentum + quality | trial 5 | 50% momentum + 50% quality, rebalanced monthly |

Trial 5 was **chosen after seeing development data**. In Phase 2 the HMM regime rule held momentum + quality in 166 of 174 months, so its development edge looked like a fixed tilt and not timing. The holdout tests that tilt on data it has never seen. Its development numbers are reported with this label.

Benchmarks: NIFTY 200 TRI and NIFTY 50 TRI, with no costs (index, not investable as is). Alpha 30 is not traded because it is a near-duplicate of momentum.

## Costs (VERIFY)

| factor | ETF assumed | expense ratio a year |
| --- | --- | --- |
| momentum | ICICI Pru Nifty 200 Momentum 30 ETF | 0.76% |
| quality | Kotak Nifty200 Quality 30 ETF | 0.25% |
| value | ICICI Pru Nifty200 Value 30 ETF | 0.26% |
| lowvol | ICICI Pru Nifty 100 Low Volatility 30 ETF | 0.36% |

- Expenses are charged monthly on the weights held.
- Switching costs 0.20% per unit of one-way turnover.
- The risk-free rate is 6.5% a year.
- **Cost sensitivity** (reported as sensitivity, not used to select anything): expense ratios ×0.5 and ×1.5, and switching at 0.10% and 0.40%, one at a time.

## What is reported

For every strategy and benchmark on the holdout:
- total return, CAGR, volatility, Sharpe and maximum drawdown;
- one-way turnover;
- the monthly difference against equal weight, with a Newey-West t-statistic (3 lags) and the share of months ahead;
- the month-by-month returns.

With 24 months these tests have very low power. A difference would need to be large to show up as significant, and an insignificant result is not evidence that two strategies are equal. No strategy is declared the winner on the holdout alone. The holdout is read alongside the development and live-period results, and the count of 5 trials is kept in view.
