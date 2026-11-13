# Backtest: holdout (24 cycles, 2024-11-01 to 2026-10-27)

## Main result (fractional units, cash at 6.5%)

|             | CAGR   | Vol   |   Sharpe |   Sortino | MaxDD   | DD peak    | DD trough   | Worst month   | Worst 3m   |   Skew | Win rate   | Avg win   | Avg loss   | CVaR95   | CVaR99   |   Skipped |   Costs Rs | Costs/gross profit   | Avg margin   | Max margin   |
|:------------|:-------|:------|---------:|----------:|:--------|:-----------|:------------|:--------------|:-----------|-------:|:-----------|:----------|:-----------|:---------|:---------|----------:|-----------:|:---------------------|:-------------|:-------------|
| put_spread  | 3.1%   | 7.5%  |    -0.39 |     -0.4  | -9.5%   | 2026-02-25 | 2026-04-01  | -9.5%         | -8.5%      |  -4.19 | 91.7%      | 0.8%      | -5.6%      | -5.6%    | -9.5%    |         5 |      5,502 |                      | 10.0%        | 10.0%        |
| iron_condor | 3.2%   | 7.4%  |    -0.4  |     -0.42 | -8.6%   | 2026-02-25 | 2026-04-01  | -8.6%         | -7.7%      |  -3.54 | 87.5%      | 0.9%      | -4.2%      | -5.5%    | -8.6%    |        10 |      8,078 |                      | 10.0%        | 10.0%        |
| strangle    | 3.8%   | 5.3%  |    -0.46 |     -0.47 | -6.6%   | 2026-02-25 | 2026-04-01  | -6.6%         | -5.5%      |  -4.24 | 87.5%      | 0.7%      | -2.7%      | -3.7%    | -6.6%    |         0 |      4,432 |                      | 30.0%        | 30.0%        |
| TRI         | -2.3%  | 13.9% |    -0.55 |     -0.66 | -13.4%  | 2025-11-26 | 2026-04-01  | -11.0%        | -13.1%     |  -0.72 | 50.0%      | 2.7%      | -2.9%      | -8.8%    | -11.0%   |           |            |                      |              |              |
| Cash 6.5%   | 6.5%   | 0.2%  |     0    |           | 0.0%    | 2024-11-01 | 2024-11-01  | 0.5%          | 1.5%       |   0.8  | 100.0%     | 0.5%      |            | 0.5%     | 0.5%     |           |            |                      |              |              |

Sharpe and Sortino are on monthly returns in excess of 6.5% cash, annualised by sqrt(12). Max drawdown on month-end capital. CVaR = average of the worst 5% / 1% of months.

## Cash on idle capital at 0%

|             | CAGR   | Vol   |   Sharpe | MaxDD   | Worst month   | CVaR99   |
|:------------|:-------|:------|---------:|:--------|:--------------|:---------|
| put_spread  | -2.9%  | 7.6%  |    -1.17 | -10.0%  | -10.0%        | -10.0%   |
| iron_condor | -3.0%  | 7.4%  |    -1.22 | -10.4%  | -9.2%         | -9.2%    |
| strangle    | -0.8%  | 5.4%  |    -1.3  | -7.0%   | -7.0%         | -7.0%    |
| TRI         | -2.3%  | 13.9% |    -0.55 | -13.4%  | -11.0%        | -11.0%   |
| Cash 6.5%   | 6.5%   | 0.2%  |     0    | 0.0%    | 0.5%          | 0.5%     |

## Whole lots

Whole lots (units rounded down to the NSE lot size on the entry date, from the UDiFF lot column):

| rule        | CAGR   |   Sharpe | MaxDD   | Worst month   |   months traded |   months with 0 lots |   no lot data |
|:------------|:-------|---------:|:--------|:--------------|----------------:|---------------------:|--------------:|
| put_spread  | 4.4%   |    -0.37 | -6.2%   | -6.2%         |              19 |                    0 |             0 |
| iron_condor | 4.3%   |    -0.35 | -6.2%   | -6.2%         |              13 |                    1 |             0 |
| strangle    | 6.9%   |     1.3  | 0.0%    | 0.5%          |               3 |                   21 |             0 |

## Stress months

No stress month in this period.

## 10 worst months per rule

| rule        | entry      | expiry     | return   | index move   |
|:------------|:-----------|:-----------|:---------|:-------------|
| put_spread  | 2026-02-25 | 2026-03-30 | -9.5%    | -12.4%       |
| put_spread  | 2026-08-26 | 2026-09-29 | -1.7%    | -6.2%        |
| put_spread  | 2024-11-01 | 2024-11-28 | +0.5%    | -1.6%        |
| put_spread  | 2025-08-01 | 2025-08-28 | +0.5%    | -0.3%        |
| put_spread  | 2025-10-01 | 2025-10-28 | +0.5%    | +4.4%        |
| put_spread  | 2026-01-28 | 2026-02-24 | +0.5%    | +0.3%        |
| put_spread  | 2025-12-31 | 2026-01-27 | +0.5%    | -3.7%        |
| put_spread  | 2025-10-29 | 2025-11-25 | +0.6%    | -0.6%        |
| put_spread  | 2026-07-29 | 2026-08-25 | +0.6%    | +0.3%        |
| put_spread  | 2025-03-28 | 2025-04-30 | +0.6%    | +3.5%        |
| iron_condor | 2026-02-25 | 2026-03-30 | -8.6%    | -12.4%       |
| iron_condor | 2025-02-28 | 2025-03-27 | -2.3%    | +6.6%        |
| iron_condor | 2026-08-26 | 2026-09-29 | -1.5%    | -6.2%        |
| iron_condor | 2024-11-01 | 2024-11-28 | +0.5%    | -1.6%        |
| iron_condor | 2025-05-02 | 2025-05-29 | +0.5%    | +2.0%        |
| iron_condor | 2025-10-01 | 2025-10-28 | +0.5%    | +4.4%        |
| iron_condor | 2025-12-31 | 2026-01-27 | +0.5%    | -3.7%        |
| iron_condor | 2025-08-01 | 2025-08-28 | +0.5%    | -0.3%        |
| iron_condor | 2025-10-29 | 2025-11-25 | +0.5%    | -0.6%        |
| iron_condor | 2026-01-28 | 2026-02-24 | +0.5%    | +0.3%        |
| strangle    | 2026-02-25 | 2026-03-30 | -6.6%    | -12.4%       |
| strangle    | 2025-02-28 | 2025-03-27 | -0.9%    | +6.6%        |
| strangle    | 2026-08-26 | 2026-09-29 | -0.6%    | -6.2%        |
| strangle    | 2025-12-31 | 2026-01-27 | +0.4%    | -3.7%        |
| strangle    | 2025-10-01 | 2025-10-28 | +0.5%    | +4.4%        |
| strangle    | 2025-10-29 | 2025-11-25 | +0.5%    | -0.6%        |
| strangle    | 2026-07-29 | 2026-08-25 | +0.5%    | +0.3%        |
| strangle    | 2025-08-01 | 2025-08-28 | +0.6%    | -0.3%        |
| strangle    | 2026-07-01 | 2026-07-28 | +0.6%    | -0.1%        |
| strangle    | 2025-08-29 | 2025-09-30 | +0.6%    | +0.8%        |

## Skipped months

| entry      | skipped                                  | rule        |
|:-----------|:-----------------------------------------|:------------|
| 2024-11-01 | no valid P strike within 1% of 0.90 x S0 | put_spread  |
| 2025-03-28 | no valid P strike within 1% of 0.90 x S0 | put_spread  |
| 2025-08-01 | no valid P strike within 1% of 0.90 x S0 | put_spread  |
| 2025-10-01 | no valid P strike within 1% of 0.90 x S0 | put_spread  |
| 2026-01-28 | no valid P strike within 1% of 0.90 x S0 | put_spread  |
| 2024-11-01 | no valid P strike within 1% of 0.90 x S0 | iron_condor |
| 2025-03-28 | no valid P strike within 1% of 0.90 x S0 | iron_condor |
| 2025-05-02 | no valid C strike within 1% of 1.10 x S0 | iron_condor |
| 2025-06-27 | no valid C strike within 1% of 1.10 x S0 | iron_condor |
| 2025-08-01 | no valid P strike within 1% of 0.90 x S0 | iron_condor |
| 2025-10-01 | no valid P strike within 1% of 0.90 x S0 | iron_condor |
| 2025-10-29 | no valid C strike within 1% of 1.10 x S0 | iron_condor |
| 2025-12-31 | no valid C strike within 1% of 1.10 x S0 | iron_condor |
| 2026-01-28 | no valid P strike within 1% of 0.90 x S0 | iron_condor |
| 2026-07-29 | no valid C strike within 1% of 1.10 x S0 | iron_condor |

## IV minus RV in holdout
Mean ATM IV - RV +0.76% (vol points), IV above RV in 67% of 24 months.
