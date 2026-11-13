# Price momentum on the point-in-time Nifty 500, 2011-2026

*Hypothetical backtest. Costs are assumptions marked VERIFY. Not investment advice.*

## Question

Does 12-1 / 6-1 price momentum earn a premium on the point-in-time Nifty 500 after realistic costs, and is that premium anything more than the known momentum factor?

## Data

- Universe: Nifty 500 membership rebuilt for every month-end from 2010 from NSE / niftyindices.com index-change notices (parsed, a few transcribed by hand, each citing its notice), checked backwards from today's list and forwards from the earliest list.
- Prices: Yahoo adjusted closes cross-checked day by day with NSE's daily bhavcopy (4,183 files); NSE corporate actions; a series built from NSE closes where the sources disagree. Benchmarks: NIFTY 500 and NIFTY 50 TRI from niftyindices.com.
- Industries: NSE constituent files archived by the Internet Archive, mapped to NSE's current industry list.
- Factors: IIMA's Indian Fama-French and momentum factors (Agarwalla, Jacob and Varma).

## Method

Score = z(0.5 z(12-1) + 0.5 z(6-1)) across eligible stocks (members, Rs 5 crore median traded value, 252 days of history, no quarantined or unadjusted corporate event in the look-back). Signals at month-ends, execution at the next regular session's close. Portfolio: top 30 equal weight, buffer to rank 45, sector cap 25%, monthly; costs: STT, exchange, SEBI, stamp, GST, DP charge and liquidity-tiered slippage. Development 2011-01 to 2024-10; walk-forward with expanding windows, 1-month embargo and 12-month tests; holdout 2024-11 onward run once on a configuration frozen and committed beforehand. 20 trials in total, each logged before it ran.

## Results

**Signal.** Mean monthly rank IC 0.044 (t = 3.08); Q5 minus Q1 1.15% a month (t = 2.55); Q5 minus universe 0.65% (t = 3.34). IC peaks three months out and is near zero at twelve.

**Portfolio (development, base costs).** Primary CAGR 21.80%, Sharpe 0.72, max drawdown -37.38%; equal weight 11.22%, Sharpe 0.31. Difference 0.75% a month (t = 2.91). Costs 1.28% a year at 3.1x one-way turnover. Quarterly rebalancing: CAGR 23.63%, Sharpe 0.79.

**Walk-forward.** Out of sample the fixed primary beats equal weight by 0.93% a month (t = 2.89); selecting from the 18-combination grid fold by fold gives 0.68% (t = 2.04), so selection adds nothing. Most chosen: blend, N50, quarterly (3), z_12_1, N50, quarterly (2), blend, N50, monthly (2). Deflated Sharpe at 18 trials: fixed primary 0.98.

**Holdout (run 1).** Frozen configuration blend, N50, quarterly: 0.62% a month over equal weight (t = 1.56) over 23 months. With so few months only a difference of about 1.14% a month would reach t = 2; the holdout neither confirms nor rejects the development result.

**Controls.** The Fama-MacBeth momentum slope is 0.43% a month per standard deviation (t = 2.80) alone and 0.49% (t = 3.91) after size, beta, volatility, sector and short-term reversal. Sector-neutral and size-neutral versions keep the excess (0.67% and 0.83% a month).

**Spanning.** Against IIMA's market factor alone the primary's alpha is 5.81% a year (t = 2.00); adding SMB, HML and WML leaves 0.67% (t = 0.26) over 166 months. Q5 minus Q1 correlates 0.76 with WML. The strategy is a liquid, implementable version of Indian momentum, not a separate source of return.

**Capacity and states.** With trades capped at 5% of median traded value, CAGR is 21.80% at Rs 0.1 crore, 21.93% at Rs 1 crore, 21.49% at Rs 10 crore, 18.04% at Rs 100 crore. The excess over equal weight is 0.89% a month after rising markets and 0.17% after falling ones.

## Results table

| period | strategy | CAGR | Sharpe | max drawdown | vs equal weight, per month (t) |
|---|---|---|---|---|---|
| Development (2011-01 to 2024-10) | Primary (blend, 30, monthly) | 21.80% | 0.72 | -37.38% | 0.75% (2.91) |
| Development (2011-01 to 2024-10) | Selection (blend, N50, quarterly) | 23.68% | 0.82 | -36.78% | 0.86% (3.72) |
| Development (2011-01 to 2024-10) | Equal weight (eligible) | 11.22% | 0.31 | -55.32% |  |
| Walk-forward out of sample (2016-02 to 2024-10) | Primary (blend, 30, monthly) | 28.72% | 0.94 | -27.00% | 0.93% (2.89) |
| Walk-forward out of sample (2016-02 to 2024-10) | Selection (chosen per fold) | 24.77% | 0.8 | -35.88% | 0.68% (2.04) |
| Walk-forward out of sample (2016-02 to 2024-10) | Equal weight (eligible) | 15.84% | 0.51 | -51.62% |  |
| Holdout, run 1 (23 months) | Primary (blend, 30, monthly) | -3.21% | -0.3 | -26.57% | 0.24% (0.59) |
| Holdout, run 1 (23 months) | Selection (blend, N50, quarterly) | 1.67% | -0.1 | -25.37% | 0.62% (1.56) |
| Holdout, run 1 (23 months) | Equal weight (eligible) | -5.19% | -0.49 | -19.01% |  |


## Limitations

- Cost rates and the 6.5% risk-free rate are assumptions to verify; slippage is a tiered estimate, not a market-impact model.
- Yahoo prices are used where they match NSE; NSE's corporate-action records miss some events; 62 unadjusted demergers/rights are handled by exclusion.
- Delisted holdings are sold at the last close; merger or buyback proceeds may differ.
- The Sep 2010 review notice and one 2012 notice are missing; industries for 1.4% of eligible member-months are unclassified.
- The holdout has 23 months and little power.

## Next

Verify the cost schedule against a broker's contract notes; model market impact with order-book data; test a residual-momentum signal that removes the WML exposure; extend the holdout as months accrue (each extension logged as a new run).
