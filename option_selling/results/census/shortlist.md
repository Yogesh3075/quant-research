# Census shortlist (design cycles only; written before validation)

Rule (pre-registered): option-only Sharpe above the base put spread's (0.32), worst month no worse than -12% of capital, break-even margin at least 3 points. Candidates: the 20 census trials.

| strategy                  |   option Sharpe | worst month   | break-even margin   | option CAGR   |
|:--------------------------|----------------:|:--------------|:--------------------|:--------------|
| s1_short_put              |            0.3  | -14.1%        | 5.3%                | 1.4%          |
| s1_short_put_e1           |            0.8  | -6.3%         | 15.5%               | 2.5%          |
| s2_short_call             |            0.07 | -9.0%         | 1.1%                | 0.2%          |
| s2_short_call_e1          |           -0.09 | -10.2%        | -2.0%               | -0.5%         |
| s3_short_straddle         |            0.01 | -14.4%        | 0.2%                | -0.2%         |
| s3_short_straddle_e1      |           -0.02 | -16.9%        | -0.5%               | -0.6%         |
| s4_short_strangle         |            0.31 | -14.7%        | 7.2%                | 2.0%          |
| s4_short_strangle_e1      |            0.44 | -8.0%         | 10.2%               | 2.4%          |
| s5_bear_call_spread       |           -0.28 | -10.0%        | -4.0%               | -3.3%         |
| s5_bear_call_spread_e1    |           -0.48 | -10.9%        | -8.7%               | -4.5%         |
| s6_iron_butterfly         |           -0.74 | -10.3%        | -12.6%              | -22.3%        |
| s6_iron_butterfly_e1      |           -0.74 | -10.3%        | -12.6%              | -22.3%        |
| s7_cash_secured_put       |            0.28 | -25.2%        | 4.8%                | 2.1%          |
| s7_cash_secured_put_e1    |            0.8  | -11.1%        | 14.6%               | 4.3%          |
| s8_put_ratio              |            0.57 | -0.8%         | 9.8%                | 1.9%          |
| s8_put_ratio_e1           |            0.35 | -2.8%         | 5.4%                | 1.2%          |
| s9_calendar               |           -1.37 | -49.4%        | -28.7%              | -45.2%        |
| s10_covered_call          |            0.55 | -25.3%        | 10.3%               | 8.8%          |
| s11_collar                |            0.5  | -9.7%         | 8.6%                | 6.2%          |
| s12_delta_hedged_straddle |            0.3  | -8.2%         | 6.3%                | 1.3%          |

**Shortlist (6): s1_short_put_e1, s4_short_strangle_e1, s7_cash_secured_put_e1, s8_put_ratio, s8_put_ratio_e1, s11_collar**

## Notes (facts from the design data; the pre-registered rule is applied unchanged)

- October 2008 cycle (entry 2008-09-26, index -32.3%): traded by s1_short_put_e1 (-6.3%), s4_short_strangle_e1 (-8.0%), s7_cash_secured_put_e1 (-11.1%), s11_collar (-0.4%); skipped (no traded strike) by s8_put_ratio, s8_put_ratio_e1, and by the base put spread and the frozen e1f1 rule. Comparisons with the base therefore flatter the base and any strategy that skipped that month.
- s8_put_ratio entered at a net debit in 92% of traded cycles (so its stop variant rarely applies), loses only if the index falls more than about 15% (1 long 0.95 put vs 2 short 0.90 puts), and the only design fall that large (Oct 2008) was skipped. Its small worst month has never met its real tail.
- s11_collar holds the index: its return includes the index leg (CAGR -1.8% a year vs TRI buy-and-hold).
- s6_iron_butterfly_e1 equals s6_iron_butterfly: its maximum loss per unit (wing width - credit) is below 2 x credit, so the stop can never trigger.
- s9_calendar: sizing assumed max loss = debit, but after falls the deep in-the-money far put traded below intrinsic on the near expiry day (17 of 132 design cycles), so losses reached several times the debit; one cycle (entry 2013-12-27) used a carried far close (flagged).
- Deflated Sharpe at 32 trials is below 30% for every strategy. Paired Newey-West t vs the base: largest positive 1.72 (s10_covered_call); no strategy is significantly better than the base; the most negative are s9_calendar -5.13, s6_iron_butterfly -2.84.
