# Phase 3 choice (design cycles only; written before validation)

Rule (pre-registered): keep a variant only if its design option-only Sharpe beats the base and its worst month and CVaR 99% are no worse than the base's; if several qualify take the highest Sharpe; if none, the frozen rule is the base put spread.

| variant   |   option Sharpe | worst month   | CVaR99   | option CAGR   |
|:----------|----------------:|:--------------|:---------|:--------------|
| base      |            0.32 | -10.0%        | -10.0%   | 2.2%          |
| e1        |            0.72 | -5.2%         | -5.0%    | 3.8%          |
| f1        |            0.49 | -10.0%        | -10.0%   | 2.8%          |
| e1f1      |            0.73 | -5.2%         | -4.5%    | 3.2%          |

- e1: Sharpe 0.723 > base 0.320; worst month -5.17% ok base -10.01%; CVaR99 -4.98% ok base -10.01% -> qualifies
- f1: Sharpe 0.491 > base 0.320; worst month -10.01% ok base -10.01%; CVaR99 -10.01% worse than base -10.01% -> does not qualify
- e1f1: Sharpe 0.733 > base 0.320; worst month -5.17% ok base -10.01%; CVaR99 -4.52% ok base -10.01% -> qualifies

**Chosen: e1f1**

## Notes on the choice (facts from the design data; the pre-registered rule is applied unchanged)

- e1f1 and e1 are close: Sharpe 0.733 vs 0.723; e1f1 traded 66 months vs 130, option CAGR 3.2% vs 3.8%.
- f1 failed only on CVaR 99%: -10.01038% vs base -10.01038% : equal to five decimal places, so the strict "no worse" test failed on floating-point noise. This does not change the choice: f1's Sharpe is below both e1 and e1f1.
- None of the differences vs the base is statistically significant: Newey-West t e1 0.92, f1 0.32, e1f1 0.40 over 132 months.
- All variants share the base's skipped cycles (no traded strike): 2008-06-27 (index +4.7%), 2008-09-26 (index -32.3%). The October 2008 crash is not in any result.
