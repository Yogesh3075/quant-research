# Quant research on Indian equities and derivatives

I'm Yogesh Shaligram, an independent trader learning systematic research. Each project uses point-in-time data, realistic Indian costs, walk-forward testing, a locked holdout scored once, and a log of every trial, including the ones that failed.

| Project | Question | Result |
|---|---|---|
| [Momentum](momentum_research) | Does 12-1 / 6-1 momentum earn a premium on the point-in-time Nifty 500 after costs? | Edge: 0.93% a month over equal weight in walk-forward out-of-sample months (t = 2.89), largely the known momentum factor; the 23-month holdout gave 0.62% a month (t = 1.56). |
| [Option selling](option_selling) | Does selling Nifty index options earn the variance risk premium after costs? | Edge, small and chosen after the fact: the P1 put spread made 11.8% a year on ₹10 lakh in design (5.0% above cash, max drawdown −10%); the frozen e1f1 rule beat cash in the holdout, 7.3% against 6.5%. |
| [Factor Regime Rotation](factor_regime_rotation) | Does HMM regime timing beat a static mix of factor indices? | No edge: a static equal-weight mix beat every timing model after costs, and all five rules trailed it on the holdout. |
| [ML vs linear blend](nifty500-ml-factors) | Does LightGBM rank Nifty 500 stocks better than a linear blend of the same features? | No edge: similar IC, about twice the turnover, no net gain (−0.06% a month, t = −0.23). |
| [Pairs trading](stat_arb) | Do cointegrated same-sector pairs make money after costs? | No edge: an audit found look-ahead and one-leg costs, and the rebuild's holdout Sharpe was −0.54. |

## How I validate

- Index membership is rebuilt for every date from NSE notices and bhavcopies, never taken from today's list, which would inflate Nifty 500 returns by about 5.4% a year.
- Costs include STT, exchange fees, stamp duty, GST, brokerage and liquidity-tiered slippage on every leg; the assumptions are marked VERIFY.
- Parameters are chosen on development data only; the holdout is fixed before the first run, scored once and logged, and the scripts refuse a second run.
- Every trial is logged, and pre-registered where possible; deflated Sharpe ratios use the full count, and results chosen after the fact, or "seen", are labelled.

## Setup

Python 3.11 or later. Each project is a self-contained package (`momentum`, `optsell`, `regime`, `mlfactors`, `pairs`) with its own `pyproject.toml`, scripts and tests.

```bash
pip install -e momentum_research        # or any one project; `make install` installs all five with dev tools
make test                               # each project's tests: fast, no data needed
make lint                               # ruff check and format check
```

The data is not in this repository: it is several GB of raw files, exchange data is not mine to redistribute, and every project rebuilds its own data from the original sources (NSE archives, niftyindices.com, Yahoo Finance, the Internet Archive and IIMA's factor library). Each project's README gives the commands. Small result tables, trial logs and charts are committed, so every reported number can be traced to a file. `make charts` redraws the README charts from those files.

*Hypothetical backtests. Not investment advice.*
