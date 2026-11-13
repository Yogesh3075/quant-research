# Backtest: development (201 cycles, 2008-02-01 to 2024-10-31)

## Main result (fractional units, cash at 6.5%)

|             | CAGR   | Vol   |   Sharpe |   Sortino | MaxDD   | DD peak    | DD trough   | Worst month   | Worst 3m   |   Skew | Win rate   | Avg win   | Avg loss   | CVaR95   | CVaR99   |   Skipped |   Costs Rs | Costs/gross profit   | Avg margin   | Max margin   |
|:------------|:-------|:------|---------:|----------:|:--------|:-----------|:------------|:--------------|:-----------|-------:|:-----------|:----------|:-----------|:---------|:---------|----------:|-----------:|:---------------------|:-------------|:-------------|
| put_spread  | 8.5%   | 7.2%  |     0.3  |      0.34 | -15.9%  | 2010-12-31 | 2011-11-25  | -9.6%         | -8.0%      |  -3.13 | 90.5%      | 1.3%      | -4.7%      | -6.4%    | -9.6%    |        13 |    258,628 | 24.5%                | 10.0%        | 10.0%        |
| iron_condor | 3.7%   | 11.9% |    -0.16 |     -0.2  | -31.4%  | 2020-02-28 | 2021-02-26  | -9.7%         | -17.8%     |  -1.16 | 78.6%      | 1.7%      | -4.7%      | -9.6%    | -9.6%    |        26 |    405,570 |                      | 10.0%        | 10.0%        |
| strangle    | 6.0%   | 9.7%  |    -0    |     -0    | -22.5%  | 2008-09-26 | 2008-10-31  | -22.5%        | -17.7%     |  -3.84 | 81.6%      | 1.3%      | -3.1%      | -7.4%    | -15.6%   |         3 |    131,205 | 34.7%                | 30.0%        | 30.0%        |
| TRI         | 10.8%  | 20.1% |     0.3  |      0.43 | -49.1%  | 2008-02-01 | 2008-12-01  | -27.6%        | -38.3%     |  -0.71 | 59.2%      | 4.5%      | -4.1%      | -12.6%   | -21.7%   |           |            |                      |              |              |
| Cash 6.5%   | 6.5%   | 0.2%  |     0    |           | 0.0%    | 2008-02-01 | 2008-02-01  | 0.4%          | 1.4%       |   0.53 | 100.0%     | 0.5%      |            | 0.4%     | 0.4%     |           |            |                      |              |              |

Sharpe and Sortino are on monthly returns in excess of 6.5% cash, annualised by sqrt(12). Max drawdown on month-end capital. CVaR = average of the worst 5% / 1% of months.

## Cash on idle capital at 0%

|             | CAGR   | Vol   |   Sharpe | MaxDD   | Worst month   | CVaR99   |
|:------------|:-------|:------|---------:|:--------|:--------------|:---------|
| put_spread  | 2.3%   | 7.1%  |    -0.53 | -20.3%  | -10.0%        | -10.0%   |
| iron_condor | -2.3%  | 11.9% |    -0.67 | -61.1%  | -10.1%        | -10.1%   |
| strangle    | 1.2%   | 9.7%  |    -0.48 | -22.9%  | -22.9%        | -16.0%   |
| TRI         | 10.8%  | 20.1% |     0.3  | -49.1%  | -27.6%        | -21.7%   |
| Cash 6.5%   | 6.5%   | 0.2%  |     0    | 0.0%    | 0.4%          | 0.4%     |

## Whole lots

Lot sizes by date are missing for 185 of 201 cycles (the bhavcopy has a lot column only in the UDiFF files from July 2024), so the whole-lot version is skipped for this period.

## Stress months

| event        | entry      | expiry     | index move   | TRI    | put_spread   | iron_condor   | strangle   |
|:-------------|:-----------|:-----------|:-------------|:-------|:-------------|:--------------|:-----------|
| Oct 2008     | 2008-09-26 | 2008-10-29 | -32.3%       | -27.6% | +0.6%        | +0.6%         | -22.5%     |
| Oct 2008     | 2008-10-31 | 2008-11-28 | -4.5%        | -7.0%  | +3.4%        | +7.6%         | +10.9%     |
| Aug 2015     | 2015-07-31 | 2015-08-27 | -6.8%        | -6.2%  | -3.1%        | -2.5%         | -1.0%      |
| Aug 2015     | 2015-08-28 | 2015-09-24 | -1.7%        | -2.5%  | +1.8%        | +2.9%         | +1.8%      |
| Feb-Mar 2020 | 2020-01-31 | 2020-02-27 | -2.7%        | -6.3%  | +0.9%        | +1.5%         | +1.0%      |
| Feb-Mar 2020 | 2020-02-28 | 2020-03-26 | -22.9%       | -22.5% | -9.6%        | -9.6%         | -16.2%     |
| Feb-Mar 2020 | 2020-03-27 | 2020-04-30 | +13.9%       | +7.3%  | +2.8%        | -9.5%         | +2.5%      |
| 4 Jun 2024   | 2024-05-31 | 2024-06-27 | +6.7%        | +6.8%  | +1.5%        | -1.0%         | +0.2%      |

## 10 worst months per rule

| rule        | entry      | expiry     | return   | index move   |
|:------------|:-----------|:-----------|:---------|:-------------|
| put_spread  | 2020-02-28 | 2020-03-26 | -9.6%    | -22.9%       |
| put_spread  | 2008-05-30 | 2008-06-26 | -9.6%    | -11.4%       |
| put_spread  | 2011-07-29 | 2011-08-25 | -9.6%    | -11.7%       |
| put_spread  | 2011-10-28 | 2011-11-24 | -9.6%    | -11.3%       |
| put_spread  | 2010-12-31 | 2011-01-27 | -6.0%    | -8.6%        |
| put_spread  | 2013-07-26 | 2013-08-29 | -5.6%    | -8.1%        |
| put_spread  | 2016-01-29 | 2016-02-25 | -5.0%    | -7.8%        |
| put_spread  | 2024-09-27 | 2024-10-31 | -4.3%    | -7.5%        |
| put_spread  | 2016-10-28 | 2016-11-24 | -4.1%    | -7.8%        |
| put_spread  | 2008-02-29 | 2008-03-27 | -4.0%    | -7.5%        |
| iron_condor | 2009-05-04 | 2009-05-28 | -9.7%    | +18.7%       |
| iron_condor | 2020-02-28 | 2020-03-26 | -9.6%    | -22.9%       |
| iron_condor | 2009-02-27 | 2009-03-26 | -9.6%    | +11.5%       |
| iron_condor | 2011-12-30 | 2012-01-25 | -9.6%    | +11.5%       |
| iron_condor | 2020-10-30 | 2020-11-26 | -9.6%    | +11.5%       |
| iron_condor | 2021-01-29 | 2021-02-25 | -9.6%    | +10.7%       |
| iron_condor | 2011-10-28 | 2011-11-24 | -9.6%    | -11.3%       |
| iron_condor | 2011-07-29 | 2011-08-25 | -9.6%    | -11.7%       |
| iron_condor | 2020-03-27 | 2020-04-30 | -9.5%    | +13.9%       |
| iron_condor | 2011-02-25 | 2011-03-31 | -9.5%    | +10.0%       |
| strangle    | 2008-09-26 | 2008-10-29 | -22.5%   | -32.3%       |
| strangle    | 2020-02-28 | 2020-03-26 | -16.2%   | -22.9%       |
| strangle    | 2009-05-04 | 2009-05-28 | -8.2%    | +18.7%       |
| strangle    | 2011-07-29 | 2011-08-25 | -5.5%    | -11.7%       |
| strangle    | 2011-10-28 | 2011-11-24 | -5.0%    | -11.3%       |
| strangle    | 2010-08-27 | 2010-09-30 | -4.9%    | +11.5%       |
| strangle    | 2020-10-30 | 2020-11-26 | -4.8%    | +11.5%       |
| strangle    | 2021-01-29 | 2021-02-25 | -3.7%    | +10.7%       |
| strangle    | 2011-12-30 | 2012-01-25 | -3.6%    | +11.5%       |
| strangle    | 2008-05-30 | 2008-06-26 | -3.5%    | -11.4%       |

## Skipped months

| entry      | skipped                                  | rule        |
|:-----------|:-----------------------------------------|:------------|
| 2008-06-27 | no valid P strike within 1% of 0.90 x S0 | put_spread  |
| 2008-09-26 | no valid P strike within 1% of 0.90 x S0 | put_spread  |
| 2009-06-26 | no valid P strike within 1% of 0.95 x S0 | put_spread  |
| 2009-11-27 | no valid P strike within 1% of 0.90 x S0 | put_spread  |
| 2010-04-30 | no valid P strike within 1% of 0.90 x S0 | put_spread  |
| 2011-09-30 | no valid P strike within 1% of 0.90 x S0 | put_spread  |
| 2012-06-29 | no valid P strike within 1% of 0.90 x S0 | put_spread  |
| 2014-09-26 | no valid P strike within 1% of 0.90 x S0 | put_spread  |
| 2021-11-26 | no valid P strike within 1% of 0.90 x S0 | put_spread  |
| 2023-01-27 | no valid P strike within 1% of 0.90 x S0 | put_spread  |
| 2023-02-24 | no valid P strike within 1% of 0.90 x S0 | put_spread  |
| 2023-05-26 | no valid P strike within 1% of 0.95 x S0 | put_spread  |
| 2023-10-27 | no valid P strike within 1% of 0.90 x S0 | put_spread  |
| 2008-04-25 | no valid C strike within 1% of 1.10 x S0 | iron_condor |
| 2008-06-27 | no valid P strike within 1% of 0.90 x S0 | iron_condor |
| 2008-09-26 | no valid P strike within 1% of 0.90 x S0 | iron_condor |
| 2009-03-27 | no valid C strike within 1% of 1.05 x S0 | iron_condor |
| 2009-06-26 | no valid P strike within 1% of 0.95 x S0 | iron_condor |
| 2009-11-27 | no valid P strike within 1% of 0.90 x S0 | iron_condor |
| 2010-04-30 | no valid P strike within 1% of 0.90 x S0 | iron_condor |
| 2011-09-30 | no valid P strike within 1% of 0.90 x S0 | iron_condor |
| 2012-06-29 | no valid P strike within 1% of 0.90 x S0 | iron_condor |
| 2014-09-26 | no valid P strike within 1% of 0.90 x S0 | iron_condor |
| 2014-10-31 | no valid C strike within 1% of 1.10 x S0 | iron_condor |
| 2021-11-26 | no valid P strike within 1% of 0.90 x S0 | iron_condor |
| 2022-07-29 | no valid C strike within 1% of 1.10 x S0 | iron_condor |
| 2023-01-27 | no valid P strike within 1% of 0.90 x S0 | iron_condor |
| 2023-02-24 | no valid P strike within 1% of 0.90 x S0 | iron_condor |
| 2023-04-28 | no valid C strike within 1% of 1.10 x S0 | iron_condor |
| 2023-05-26 | no valid P strike within 1% of 0.95 x S0 | iron_condor |
| 2023-06-30 | no valid C strike within 1% of 1.10 x S0 | iron_condor |
| 2023-10-27 | no valid P strike within 1% of 0.90 x S0 | iron_condor |
| 2023-12-01 | no valid C strike within 1% of 1.10 x S0 | iron_condor |
| 2023-12-29 | no valid C strike within 1% of 1.10 x S0 | iron_condor |
| 2024-03-01 | no valid C strike within 1% of 1.10 x S0 | iron_condor |
| 2024-04-01 | no valid C strike within 1% of 1.10 x S0 | iron_condor |
| 2024-06-28 | no valid C strike within 1% of 1.10 x S0 | iron_condor |
| 2024-07-26 | no valid C strike within 1% of 1.10 x S0 | iron_condor |
| 2024-09-27 | no valid C strike within 1% of 1.10 x S0 | iron_condor |
| 2009-03-27 | no valid C strike within 1% of 1.05 x S0 | strangle    |
| 2009-06-26 | no valid P strike within 1% of 0.95 x S0 | strangle    |
| 2023-05-26 | no valid P strike within 1% of 0.95 x S0 | strangle    |
