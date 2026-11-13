# Numbers worth quoting

Each number is copied from the file named with it. Hypothetical backtest on index data; most pre-2020 history is NSE's back-calculation.

| # | number | source |
| --- | --- | --- |
| 1 | 7 NSE index Total Return series, 5,357 trading days each (Apr 2005 to Nov 2026); trailing 1, 3 and 5-year returns match NSE's published figures to two decimals for all 5 factor indices | `results/data_check.md` |
| 2 | 174-month expanding walk-forward (May 2010 to Oct 2024) with the 2-state HMM refitted at every month-end; 5 trials in total, all fixed before the 24-month holdout was loaded and scored once | `results/backtest_summary.csv`, `results/trials.csv`, `results/preregistration.md`, `results/holdout_runs.log` |
| 3 | Equal-weight factor mix: 16.5% CAGR against 13.0% for NIFTY 200 TRI in development, ahead by 0.24% a month (Newey-West t = 2.51) | `results/backtest_summary.csv` |
| 4 | Holdout (Nov 2024 to Oct 2026): all 5 timing and tilt rules trailed equal weight; the rule-based regime rule was worst, at -0.71% a month (t = -3.98) | `results/holdout_result.csv` |
| 5 | The HMM flagged "stressed" in only 5 of 174 development month-ends (3%: Mar to Jun 2020, Jun 2024), so it worked as a crisis detector, not a market cycle | `results/hmm_diagnostics.md` |
| 6 | Static momentum + quality tilt: +0.07% a month against equal weight in development (t = 0.63), then -0.34% a month on the holdout (t = -1.55; total return -12.8% against -5.0%) | `results/backtest_summary.csv`, `results/holdout_result.csv` |
