# Diagnostics (development period only)

201 monthly cycles, 2008-02-01 to 2024-10-31. Option return = option_pnl_net / capital at the start of the cycle (no cash interest); its Sharpe is mean / std x sqrt(12) with no risk-free deduction. All other Sharpe ratios are in excess of 6.5% cash.

## 1. Option P&L without cash interest

| rule        | CAGR   |   Sharpe | MaxDD   | Worst month   | Worst 3m   | CVaR99   |
|:------------|:-------|---------:|:--------|:--------------|:-----------|:---------|
| put_spread  | 2.3%   |     0.36 | -20.3%  | -10.0%        | -9.4%      | -10.0%   |
| iron_condor | -2.3%  |    -0.13 | -60.9%  | -10.1%        | -19.1%     | -10.1%   |
| strangle    | 1.2%   |     0.18 | -22.9%  | -22.9%        | -18.7%     | -16.0%   |

Yearly option return (compounded option_pnl_net / capital, % of capital):

|   year | put_spread   | iron_condor   | strangle   |
|-------:|:-------------|:--------------|:-----------|
|   2008 | 1.6%         | 24.9%         | 11.2%      |
|   2009 | 21.8%        | 4.5%          | 9.1%       |
|   2010 | 0.2%         | -9.4%         | -0.2%      |
|   2011 | -11.7%       | -24.1%        | -6.1%      |
|   2012 | 7.6%         | 8.7%          | 6.5%       |
|   2013 | 0.3%         | -6.2%         | 0.5%       |
|   2014 | 6.2%         | -5.0%         | 0.9%       |
|   2015 | 2.2%         | 10.3%         | 6.4%       |
|   2016 | -6.7%        | -14.1%        | -4.6%      |
|   2017 | 3.3%         | 2.7%          | 2.2%       |
|   2018 | -4.4%        | -8.4%         | -2.2%      |
|   2019 | 6.1%         | 6.1%          | 4.1%       |
|   2020 | -1.3%        | -28.6%        | -16.2%     |
|   2021 | 9.3%         | 2.7%          | 4.9%       |
|   2022 | 8.9%         | 11.3%         | 8.0%       |
|   2023 | 1.5%         | 1.0%          | -0.2%      |
|   2024 | -1.8%        | 0.5%          | -0.0%      |

Reading: put_spread compounds at 2.3% a year from options alone (Sharpe 0.36), with 5 losing years of 17; iron_condor compounds at -2.3% a year from options alone (Sharpe -0.13), with 7 losing years of 17; strangle compounds at 1.2% a year from options alone (Sharpe 0.18), with 7 losing years of 17. Compare with 6.5% a year on cash.

## 2. Return on margin used

| rule        | avg monthly return on margin   | total (sum pnl / sum margin)   | worst month on margin   |
|:------------|:-------------------------------|:-------------------------------|:------------------------|
| put_spread  | 2.3%                           | 2.0%                           | -100.3%                 |
| iron_condor | -1.5%                          | -2.4%                          | -100.8%                 |
| strangle    | 0.5%                           | 0.2%                           | -76.4%                  |

By year (sum of option_pnl_net / sum of margin used in traded months):

|   year | put_spread   | iron_condor   | strangle   |
|-------:|:-------------|:--------------|:-----------|
|   2008 | 2.0%         | 25.8%         | 2.9%       |
|   2009 | 21.9%        | 5.9%          | 3.3%       |
|   2010 | 0.1%         | -8.1%         | -0.1%      |
|   2011 | -11.1%       | -24.2%        | -1.7%      |
|   2012 | 6.6%         | 7.3%          | 1.7%       |
|   2013 | 0.3%         | -5.3%         | 0.1%       |
|   2014 | 5.4%         | -5.2%         | 0.2%       |
|   2015 | 2.0%         | 9.0%          | 1.9%       |
|   2016 | -5.4%        | -12.0%        | -1.2%      |
|   2017 | 2.7%         | 2.2%          | 0.6%       |
|   2018 | -3.8%        | -7.2%         | -0.6%      |
|   2019 | 4.9%         | 5.0%          | 1.1%       |
|   2020 | -1.1%        | -29.9%        | -5.4%      |
|   2021 | 7.3%         | 2.4%          | 1.3%       |
|   2022 | 7.1%         | 9.5%          | 2.1%       |
|   2023 | 1.9%         | 2.5%          | -0.1%      |
|   2024 | -2.0%        | 1.1%          | -0.0%      |

Reading: put_spread averages 2.3% a month on margin, worst month -100%; iron_condor averages -1.5% a month on margin, worst month -101%; strangle averages 0.5% a month on margin, worst month -76%.

## 3. Leverage (units and margin x1, x2, x3; same strikes and prices; idle cash at 6.5%)

| rule        | leverage   | CAGR   |   Sharpe | MaxDD   | Worst month   | Worst 3m   | CVaR99   | stopped   |
|:------------|:-----------|:-------|---------:|:--------|:--------------|:-----------|:---------|:----------|
| put_spread  | 1x         | 8.5%   |     0.3  | -15.9%  | -9.6%         | -8.0%      | -9.6%    | no        |
| put_spread  | 2x         | 9.7%   |     0.29 | -35.3%  | -19.7%        | -17.8%     | -19.6%   | no        |
| put_spread  | 3x         | 10.2%  |     0.28 | -52.2%  | -29.8%        | -27.6%     | -29.7%   | no        |
| iron_condor | 1x         | 3.7%   |    -0.16 | -31.4%  | -9.7%         | -17.8%     | -9.6%    | no        |
| iron_condor | 2x         | -0.8%  |    -0.17 | -77.7%  | -19.8%        | -35.1%     | -19.7%   | no        |
| iron_condor | 3x         | -6.8%  |    -0.17 | -94.7%  | -29.9%        | -50.4%     | -29.8%   | no        |
| strangle    | 1x         | 6.0%   |    -0    | -22.5%  | -22.5%        | -17.7%     | -15.6%   | no        |
| strangle    | 2x         | 3.9%   |    -0.01 | -45.6%  | -45.6%        | -39.3%     | -31.8%   | no        |
| strangle    | 3x         | -0.1%  |    -0.01 | -68.7%  | -68.7%        | -63.4%     | -47.9%   | no        |

Reading: Sharpe by leverage: put_spread 0.30 / 0.29 / 0.28; iron_condor -0.16 / -0.17 / -0.17; strangle -0.00 / -0.01 / -0.01. Sharpe does not improve with leverage (largest change 0.02): leverage scales the gains and the losses together, and the worst month and CVaR grow roughly in proportion. Brokerage is a fixed Rs 20 per order and is scaled with the rest, a negligible approximation.

## 4. Slippage sensitivity (x0.5 = max(0.25, 1.5%); x2 = max(1, 6%); charges unchanged)

| rule        | slippage   | CAGR   |   Sharpe | MaxDD   | Worst month   | Worst 3m   | CVaR99   | option-only CAGR   |
|:------------|:-----------|:-------|---------:|:--------|:--------------|:-----------|:---------|:-------------------|
| put_spread  | x0.5       | 9.0%   |     0.36 | -15.5%  | -9.6%         | -8.0%      | -9.6%    | 2.8%               |
| put_spread  | x1         | 8.5%   |     0.3  | -15.9%  | -9.6%         | -8.0%      | -9.6%    | 2.3%               |
| put_spread  | x2         | 7.5%   |     0.18 | -16.6%  | -9.6%         | -8.0%      | -9.6%    | 1.4%               |
| iron_condor | x0.5       | 4.6%   |    -0.09 | -30.8%  | -9.7%         | -17.8%     | -9.6%    | -1.5%              |
| iron_condor | x1         | 3.7%   |    -0.16 | -31.4%  | -9.7%         | -17.8%     | -9.6%    | -2.3%              |
| iron_condor | x2         | 2.1%   |    -0.31 | -34.8%  | -9.7%         | -17.8%     | -9.6%    | -3.8%              |
| strangle    | x0.5       | 6.2%   |     0.02 | -22.4%  | -22.4%        | -17.5%     | -15.6%   | 1.5%               |
| strangle    | x1         | 6.0%   |    -0    | -22.5%  | -22.5%        | -17.7%     | -15.6%   | 1.2%               |
| strangle    | x2         | 5.5%   |    -0.05 | -22.6%  | -22.6%        | -18.0%     | -15.8%   | 0.8%               |

Reading: option-only CAGR at slippage x0.5 / x1 / x2: put_spread 2.8% / 2.3% / 1.4%; iron_condor -1.5% / -2.3% / -3.8%; strangle 1.5% / 1.2% / 0.8%. Going from x0.5 to x2 slippage changes option-only CAGR by -1.4 pts (put_spread), -2.4 pts (iron_condor), -0.7 pts (strangle), compared with option-only CAGRs at x1 of 2.3%, -2.3%, 1.2%.

## 5. Sub-periods (option P&L only, no cash interest)

| rule        | period    | CAGR   |   Sharpe | MaxDD   | Worst month   | Worst 3m   | CVaR99   |
|:------------|:----------|:-------|---------:|:--------|:--------------|:-----------|:---------|
| put_spread  | 2008-2015 | 3.2%   |     0.41 | -20.3%  | -10.0%        | -9.0%      | -10.0%   |
| iron_condor | 2008-2015 | -0.6%  |     0.03 | -36.5%  | -10.1%        | -19.1%     | -10.1%   |
| strangle    | 2008-2015 | 3.4%   |     0.35 | -22.9%  | -22.9%        | -18.7%     | -22.9%   |
| put_spread  | 2016-end  | 1.5%   |     0.3  | -11.6%  | -10.0%        | -9.4%      | -7.7%    |
| iron_condor | 2016-end  | -3.8%  |    -0.36 | -44.1%  | -10.1%        | -18.3%     | -10.1%   |
| strangle    | 2016-end  | -0.7%  |    -0.06 | -19.6%  | -16.5%        | -15.8%     | -10.8%   |

Reading: option-only CAGR 2008-2015 vs 2016-end: put_spread 3.2% vs 1.5%; iron_condor -0.6% vs -3.8%; strangle 3.4% vs -0.7%.

## 6. Win-rate illusion (traded months, option return as % of capital)

| rule        | months won   | profit from best 10 months   | losses from worst 5 months   | avg win   | avg loss   | net option return (sum)   |
|:------------|:-------------|:-----------------------------|:-----------------------------|:----------|:-----------|:--------------------------|
| put_spread  | 88.3%        | 19.6%                        | 47.7%                        | 0.8%      | -4.4%      | 42.9%                     |
| iron_condor | 72.6%        | 33.7%                        | 22.4%                        | 1.6%      | -4.7%      | -26.4%                    |
| strangle    | 78.8%        | 31.9%                        | 46.0%                        | 1.0%      | -3.1%      | 29.0%                     |

Reading: put_spread wins 88% of months, but the worst 5 months are 48% of all losses and an average loss is 5.2x an average win; iron_condor wins 73% of months, but the worst 5 months are 22% of all losses and an average loss is 3.0x an average win; strangle wins 79% of months, but the worst 5 months are 46% of all losses and an average loss is 3.0x an average win.

## 7. Skipped months (no traded strike within 1% of target)

| rule        | entry_date   | expiry_date   | skip_reason                              | index_move_pct   |
|:------------|:-------------|:--------------|:-----------------------------------------|:-----------------|
| put_spread  | 2008-06-27   | 2008-07-31    | no valid P strike within 1% of 0.90 x S0 | +4.7%            |
| put_spread  | 2008-09-26   | 2008-10-29    | no valid P strike within 1% of 0.90 x S0 | -32.3%           |
| put_spread  | 2009-06-26   | 2009-07-30    | no valid P strike within 1% of 0.95 x S0 | +4.5%            |
| put_spread  | 2009-11-27   | 2009-12-31    | no valid P strike within 1% of 0.90 x S0 | +5.2%            |
| put_spread  | 2010-04-30   | 2010-05-27    | no valid P strike within 1% of 0.90 x S0 | -5.2%            |
| put_spread  | 2011-09-30   | 2011-10-25    | no valid P strike within 1% of 0.90 x S0 | +5.0%            |
| put_spread  | 2012-06-29   | 2012-07-26    | no valid P strike within 1% of 0.90 x S0 | -4.5%            |
| put_spread  | 2014-09-26   | 2014-10-30    | no valid P strike within 1% of 0.90 x S0 | +2.5%            |
| put_spread  | 2021-11-26   | 2021-12-30    | no valid P strike within 1% of 0.90 x S0 | +1.0%            |
| put_spread  | 2023-01-27   | 2023-02-23    | no valid P strike within 1% of 0.90 x S0 | -0.5%            |
| put_spread  | 2023-02-24   | 2023-03-29    | no valid P strike within 1% of 0.90 x S0 | -2.2%            |
| put_spread  | 2023-05-26   | 2023-06-28    | no valid P strike within 1% of 0.95 x S0 | +2.6%            |
| put_spread  | 2023-10-27   | 2023-11-30    | no valid P strike within 1% of 0.90 x S0 | +5.7%            |
| iron_condor | 2008-04-25   | 2008-05-29    | no valid C strike within 1% of 1.10 x S0 | -5.4%            |
| iron_condor | 2008-06-27   | 2008-07-31    | no valid P strike within 1% of 0.90 x S0 | +4.7%            |
| iron_condor | 2008-09-26   | 2008-10-29    | no valid P strike within 1% of 0.90 x S0 | -32.3%           |
| iron_condor | 2009-03-27   | 2009-04-29    | no valid C strike within 1% of 1.05 x S0 | +11.8%           |
| iron_condor | 2009-06-26   | 2009-07-30    | no valid P strike within 1% of 0.95 x S0 | +4.5%            |
| iron_condor | 2009-11-27   | 2009-12-31    | no valid P strike within 1% of 0.90 x S0 | +5.2%            |
| iron_condor | 2010-04-30   | 2010-05-27    | no valid P strike within 1% of 0.90 x S0 | -5.2%            |
| iron_condor | 2011-09-30   | 2011-10-25    | no valid P strike within 1% of 0.90 x S0 | +5.0%            |
| iron_condor | 2012-06-29   | 2012-07-26    | no valid P strike within 1% of 0.90 x S0 | -4.5%            |
| iron_condor | 2014-09-26   | 2014-10-30    | no valid P strike within 1% of 0.90 x S0 | +2.5%            |
| iron_condor | 2014-10-31   | 2014-11-27    | no valid C strike within 1% of 1.10 x S0 | +2.1%            |
| iron_condor | 2021-11-26   | 2021-12-30    | no valid P strike within 1% of 0.90 x S0 | +1.0%            |
| iron_condor | 2022-07-29   | 2022-08-25    | no valid C strike within 1% of 1.10 x S0 | +2.1%            |
| iron_condor | 2023-01-27   | 2023-02-23    | no valid P strike within 1% of 0.90 x S0 | -0.5%            |
| iron_condor | 2023-02-24   | 2023-03-29    | no valid P strike within 1% of 0.90 x S0 | -2.2%            |
| iron_condor | 2023-04-28   | 2023-05-25    | no valid C strike within 1% of 1.10 x S0 | +1.4%            |
| iron_condor | 2023-05-26   | 2023-06-28    | no valid P strike within 1% of 0.95 x S0 | +2.6%            |
| iron_condor | 2023-06-30   | 2023-07-27    | no valid C strike within 1% of 1.10 x S0 | +2.5%            |
| iron_condor | 2023-10-27   | 2023-11-30    | no valid P strike within 1% of 0.90 x S0 | +5.7%            |
| iron_condor | 2023-12-01   | 2023-12-28    | no valid C strike within 1% of 1.10 x S0 | +7.5%            |
| iron_condor | 2023-12-29   | 2024-01-25    | no valid C strike within 1% of 1.10 x S0 | -1.7%            |
| iron_condor | 2024-03-01   | 2024-03-28    | no valid C strike within 1% of 1.10 x S0 | -0.1%            |
| iron_condor | 2024-04-01   | 2024-04-25    | no valid C strike within 1% of 1.10 x S0 | +0.5%            |
| iron_condor | 2024-06-28   | 2024-07-25    | no valid C strike within 1% of 1.10 x S0 | +1.6%            |
| iron_condor | 2024-07-26   | 2024-08-29    | no valid C strike within 1% of 1.10 x S0 | +1.3%            |
| iron_condor | 2024-09-27   | 2024-10-31    | no valid C strike within 1% of 1.10 x S0 | -7.5%            |
| strangle    | 2009-03-27   | 2009-04-29    | no valid C strike within 1% of 1.05 x S0 | +11.8%           |
| strangle    | 2009-06-26   | 2009-07-30    | no valid P strike within 1% of 0.95 x S0 | +4.5%            |
| strangle    | 2023-05-26   | 2023-06-28    | no valid P strike within 1% of 0.95 x S0 | +2.6%            |

42 rule-months were skipped; in 4 of these cycles the index fell more than 5% (2008-04-25 -5.4%, 2008-09-26 -32.3%, 2010-04-30 -5.2%, 2024-09-27 -7.5%). These skips may hide losses a live trader would have taken: with a less strict liquidity rule, or a quote rather than a last trade, the position would have been opened. No hypothetical P&L is estimated for them.
