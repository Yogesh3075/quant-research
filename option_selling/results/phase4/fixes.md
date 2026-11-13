# Phase 4 fixes

## 1. S9 calendar valuation

Cause, from the five worst S9 months: (a) **wrong far contract**: the far leg was looked up on the near expiry day by its entry-day label; NSE relabelled the February 2014 contract (2014-02-27 -> 2014-02-26, holiday), so on 2014-01-30 the old label had no rows and the entry-day close was carried for a month (entry 2013-12-27, -49.4%); (b) **stale close**: the far put had zero contracts traded on the exit day and its bhavcopy close was days old (entry 2018-09-28: close 575 vs NSE settle 806). Fix: on the near expiry day the far contract is the monthly of the following month as listed that day; its close is used only if contracts traded > 0; otherwise it is valued by Black-Scholes (r 6.5%, no dividend) with the ATM implied volatility of that same contract that day (Phase 1 method; the expiring near month has no usable IV on its expiry day), India VIX as a fallback, and the row is flagged in `exit_flag` (bs_atm_iv / bs_vix). The other large losses used traded closes (deep in-the-money far puts traded at or below intrinsic after falls) and are unchanged.

Before the fix:

| period     | entry_date   | legs                                   |   index_at_entry |   index_at_expiry |   units |   settlement_payout |   option_return_on_capital_pct | exit_flag   |   payout_per_unit |
|:-----------|:-------------|:---------------------------------------|-----------------:|------------------:|--------:|--------------------:|-------------------------------:|:------------|------------------:|
| design     | 2013-12-27   | S1 P 6300 @77.9; B1 P 6300 @104.3      |          6313.8  |           6073.7  |  201.85 |            24625.4  |                         -49.44 | yes         |            122    |
| design     | 2018-09-28   | S1 P 10950 @186.55; B1 P 10950 @254.05 |         10930.5  |          10124.9  |    5.75 |             1438.33 |                         -44.77 | no          |            250.1  |
| design     | 2015-02-27   | S1 P 8850 @169.5; B1 P 8850 @205       |          8844.6  |           8342.15 |   37.95 |             4191.49 |                         -36.7  | no          |            110.45 |
| design     | 2014-11-28   | S1 P 8600 @88.25; B1 P 8600 @127.2     |          8588.25 |           8174.1  |   58.33 |             5054.14 |                         -31.68 | no          |             86.65 |
| validation | 2020-02-28   | S1 P 11200 @285.75; B1 P 11200 @346.65 |         11201.8  |           8641.45 | 1098.9  |            64340.6  |                         -27.13 | no          |             58.55 |

After the fix:

| period     | entry_date   | legs                                   |   index_at_entry |   index_at_expiry |   units |   settlement_payout |   option_return_on_capital_pct | exit_flag   |   payout_per_unit |
|:-----------|:-------------|:---------------------------------------|-----------------:|------------------:|--------:|--------------------:|-------------------------------:|:------------|------------------:|
| design     | 2015-02-27   | S1 P 8850 @169.5; B1 P 8850 @205       |          8844.6  |           8342.15 |   68.5  |             7565.79 |                         -36.52 | no          |            110.45 |
| design     | 2014-11-28   | S1 P 8600 @88.25; B1 P 8600 @127.2     |          8588.25 |           8174.1  |  104.73 |             9074.65 |                         -31.56 | no          |             86.65 |
| validation | 2020-02-28   | S1 P 11200 @285.75; B1 P 11200 @346.65 |         11201.8  |           8641.45 | 1098.9  |            64340.6  |                         -27.13 | no          |             58.55 |
| validation | 2024-09-27   | S1 P 26200 @288.15; B1 P 26200 @418.5  |         26179    |          24205.3  |  222.2  |            44496.1  |                         -26.99 | no          |            200.25 |
| design     | 2016-10-28   | S1 P 8600 @100.65; B1 P 8600 @140.3    |          8638    |           7965.5  |   59.58 |             3446.9  |                         -26.46 | no          |             57.85 |

### Old vs new summary (design)

| version   | strategy             | option CAGR   |   option Sharpe | worst month   | CVaR99   | max DD   | win rate   | avg credit % cap   | avg margin % cap   | costs % gross credit   |
|:----------|:---------------------|:--------------|----------------:|:--------------|:---------|:---------|:-----------|:-------------------|:-------------------|:-----------------------|
| old       | s6_iron_butterfly    | -22.3%        |           -0.74 | -10.3%        | -10.3%   | -96.7%   | 37.9%      | 13.1%              | 10.0%              | 8.4%                   |
| old       | s6_iron_butterfly_e1 | -22.3%        |           -0.74 | -10.3%        | -10.3%   | -96.7%   | 37.9%      | 13.1%              | 10.0%              | 8.4%                   |
| old       | s9_calendar          | -45.2%        |           -1.37 | -49.4%        | -47.1%   | -99.9%   | 31.8%      | -10.0%             | 10.0%              | 27.8%                  |
| new       | s6_iron_butterfly    | -8.3%         |           -0.89 | -4.9%         | -4.7%    | -67.1%   | 37.9%      | 4.3%               | 3.6%               | 6.5%                   |
| new       | s6_iron_butterfly_e1 | -8.3%         |           -0.89 | -4.9%         | -4.7%    | -67.1%   | 37.9%      | 4.3%               | 3.6%               | 6.5%                   |
| new       | s9_calendar          | -38.9%        |           -1.31 | -36.5%        | -34.0%   | -99.6%   | 32.6%      | -10.0%             | 10.0%              | 27.9%                  |

### Old vs new summary (validation)

| version   | strategy             | option CAGR   |   option Sharpe | worst month   | CVaR99   | max DD   | win rate   | avg credit % cap   | avg margin % cap   | costs % gross credit   |
|:----------|:---------------------|:--------------|----------------:|:--------------|:---------|:---------|:-----------|:-------------------|:-------------------|:-----------------------|
| old       | s6_iron_butterfly    | -14.5%        |           -0.49 | -10.3%        | -10.3%   | -71.9%   | 50.0%      | 12.4%              | 10.0%              | 5.9%                   |
| old       | s6_iron_butterfly_e1 | -14.5%        |           -0.49 | -10.3%        | -10.3%   | -71.9%   | 50.0%      | 12.4%              | 10.0%              | 5.9%                   |
| old       | s9_calendar          | -26.1%        |           -0.85 | -27.1%        | -27.1%   | -85.9%   | 36.8%      | -10.0%             | 10.0%              | 33.9%                  |
| new       | s6_iron_butterfly    | -3.9%         |           -0.42 | -4.6%         | -4.6%    | -31.4%   | 50.0%      | 4.1%               | 3.5%               | 5.4%                   |
| new       | s6_iron_butterfly_e1 | -3.9%         |           -0.42 | -4.6%         | -4.6%    | -31.4%   | 50.0%      | 4.1%               | 3.5%               | 5.4%                   |
| new       | s9_calendar          | -26.1%        |           -0.85 | -27.1%        | -27.1%   | -85.9%   | 36.8%      | -10.0%             | 10.0%              | 33.9%                  |

## 2. S6 iron butterfly sizing

Units are now capped so that units x S0 per short side <= 1.5 x capital (`census.cap_defined` in config), as for the stress-sized strategies; before, a small max loss per unit (wing width - credit) made units and costs very large. Old vs new rows for S6 are in the tables above.

Capped cycles: s6_iron_butterfly design: 132, s6_iron_butterfly validation: 68, s6_iron_butterfly_e1 design: 132, s6_iron_butterfly_e1 validation: 68.

Other census strategies' summary rows are unchanged as committed; their deflated Sharpe ratios used the pre-fix S6/S9 Sharpe values in the trial variance (the S6/S9 rows above use the corrected values).


S9 far-leg valuation after the fix: design bs_atm_iv: 2, design no: 130, validation no: 68 (no = traded close).

## 3. Column rename

`iv_minus_rv_pts` -> `iv_minus_future_rv_pts` in `report.py`, `census.py` and the header of every monthly P&L file. It uses realised volatility after entry, so it is a diagnostic only; no rule reads it (checked in `python main.py check`).

## 4. Found, not fixed (needs your decision)

NSE relabelled the June 2023 monthly expiry (2023-06-29 -> 2023-06-28) after the 2023-05-26 entry date. Cycles look up the realised label, so on entry day the chain was empty and the 2023-05-26 cycle (index +2.6% that month) was skipped as 'no traded strike' in Phase 1, Phase 2, Phase 3 (including the frozen e1f1 validation) and the census. Other relabellings found (2008-12, 2009-04, 2014-02, 2014-04, 2018-03, 2023-03, and 2025-26 holdout contracts) happen before the relevant entry or are expiry-day shifts already handled. Fixing it would change one validation month in every committed result, so it is left as is; Phase 4 uses the same cycle builder so its results stay comparable.

## 5. Unchanged results (SHA-256 against a snapshot taken before the fixes)

| file | status |
|---|---|
| results/backtest_checks.md | unchanged (same SHA-256) |
| results/backtest_dev.md | unchanged (same SHA-256) |
| results/backtest_holdout.md | unchanged (same SHA-256) |
| results/census/census_report.md | old content unchanged, note appended |
| results/census/checks.md | unchanged (same SHA-256) |
| results/census/co_loss_pairs.csv | identical after excluding S6/S9 and the renamed column |
| results/census/correlation_design.csv | identical after excluding S6/S9 and the renamed column |
| results/census/crash_table.csv | identical after excluding S6/S9 and the renamed column |
| results/census/monthly_pnl_census.csv | identical after excluding S6/S9 and the renamed column |
| results/census/preregistration.md | unchanged (same SHA-256) |
| results/census/shortlist.md | unchanged (same SHA-256) |
| results/census/summary_design.csv | identical after excluding S6/S9 and the renamed column |
| results/census/summary_validation.csv | identical after excluding S6/S9 and the renamed column |
| results/census/validation_runs.log | unchanged (same SHA-256) |
| results/data_check.md | unchanged (same SHA-256) |
| results/diagnostics.md | unchanged (same SHA-256) |
| results/diagnostics_tables.csv | unchanged (same SHA-256) |
| results/entry_day_chain.csv | unchanged (same SHA-256) |
| results/holdout_runs.log | unchanged (same SHA-256) |
| results/monthly_expiries.csv | unchanged (same SHA-256) |
| results/monthly_pnl_all.csv | identical after excluding S6/S9 and the renamed column |
| results/monthly_pnl_checks.md | unchanged (same SHA-256) |
| results/monthly_pnl_iron_condor.csv | identical after excluding S6/S9 and the renamed column |
| results/monthly_pnl_put_spread.csv | identical after excluding S6/S9 and the renamed column |
| results/monthly_pnl_strangle.csv | identical after excluding S6/S9 and the renamed column |
| results/monthly_pnl_summary.csv | unchanged (same SHA-256) |
| results/phase2/checks.md | unchanged (same SHA-256) |
| results/phase2/choice.md | unchanged (same SHA-256) |
| results/phase2/monthly_pnl_phase2.csv | identical after excluding S6/S9 and the renamed column |
| results/phase2/phase2_report.md | unchanged (same SHA-256) |
| results/phase2/split.md | unchanged (same SHA-256) |
| results/phase2/summary_design.csv | unchanged (same SHA-256) |
| results/phase2/summary_validation.csv | unchanged (same SHA-256) |
| results/phase2/validation_runs.log | unchanged (same SHA-256) |
| results/phase3/checks.md | unchanged (same SHA-256) |
| results/phase3/choice.md | unchanged (same SHA-256) |
| results/phase3/frozen_rule.md | unchanged (same SHA-256) |
| results/phase3/monthly_pnl_phase3.csv | identical after excluding S6/S9 and the renamed column |
| results/phase3/phase3_report.md | unchanged (same SHA-256) |
| results/phase3/preregistration.md | unchanged (same SHA-256) |
| results/phase3/stops.csv | unchanged (same SHA-256) |
| results/phase3/summary_design.csv | unchanged (same SHA-256) |
| results/phase3/summary_validation.csv | unchanged (same SHA-256) |
| results/phase3/validation_runs.log | unchanged (same SHA-256) |
| results/trades_iron_condor.csv | unchanged (same SHA-256) |
| results/trades_iron_condor_holdout.csv | unchanged (same SHA-256) |
| results/trades_put_spread.csv | unchanged (same SHA-256) |
| results/trades_put_spread_holdout.csv | unchanged (same SHA-256) |
| results/trades_strangle.csv | unchanged (same SHA-256) |
| results/trades_strangle_holdout.csv | unchanged (same SHA-256) |
| results/trials.csv | unchanged (same SHA-256) |
| results/vrp.csv | unchanged (same SHA-256) |
| results/vrp.md | unchanged (same SHA-256) |
