# Phase 2 choice (design cycles only; written before validation)

Rule (pre-registered): highest option-only Sharpe among the 6 variants whose worst month is no worse than -12% of capital and whose break-even margin is at least 3 percentage points.

| variant   |   option Sharpe | worst month   | break-even margin   | option CAGR   |
|:----------|----------------:|:--------------|:--------------------|:--------------|
| d20_h1    |           -0.22 | -10.0%        | -2.8%               | -2.5%         |
| d20_h2    |           -0.1  | -10.0%        | -1.2%               | -1.3%         |
| d20_h3    |            0.69 | -3.1%         | 9.1%                | 2.0%          |
| d15_h1    |           -0.19 | -10.0%        | -2.2%               | -2.1%         |
| d15_h2    |           -0.1  | -10.0%        | -1.2%               | -1.0%         |
| d15_h3    |            0.69 | -3.1%         | 11.5%               | 2.4%          |

**Chosen: d20_h3**: option-only Sharpe 0.69, worst month -3.1%, break-even margin 9.1 pts; qualifying variants: d20_h3, d15_h3.

## Notes on the choice (facts from the design data; the pre-registered rule is applied unchanged)

- d20_h3 and d15_h3 are effectively tied: option-only Sharpe 0.6861 vs 0.6856.
- Both H3 variants skipped the 2008-09-26 cycle (index -32.3%): no traded put at or beyond the target delta existed that day, so the fallback had nothing to take. Their worst month therefore excludes the October 2008 crash. Sized to lose 10% at a 25% fall, a naked put would have lost more than 10% in that cycle.
- d20_h3: notional averaged 0.53x capital, max 1.44x (entry 2008-10-31, short put IV 86%, margin 22% of capital, option return that month +4.3%). Stress sizing gives large positions when the short strike sits close to 0.75 x S0 (high-volatility months).
- d15_h3: notional averaged 0.58x capital, max 4.03x (entry 2008-10-31, short put IV 93%, margin 60% of capital, option return that month +8.9%). Stress sizing gives large positions when the short strike sits close to 0.75 x S0 (high-volatility months).
