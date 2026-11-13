# Resume numbers: what survives the audit

Audit date: 2026-11-12. Data: Yahoo Finance adjusted closes, 2016-01-01 to 2026-04-15.

## Claims checked

| Resume claim | Holds? | Correct figure | Source |
|---|---|---|---|
| OOS Sharpe > 1.0 | **No** | The code had no OOS period. With in-sample selection, the top-3 pairs' OOS Sharpe is **−0.28** (t = −0.50). No pair reaches Sharpe > 1 even in-sample (best 0.73). | `audit.py` output; `results/FnO_StatArb_Report.csv` |
| Max drawdown < 18% | **No** (as a strategy claim) | Top-3 OOS max DD is −14.6%, but the return is negative (−8.3%). In the original full-sample run, no pair had Sharpe > 1 together with DD < 18%. | `audit.py` |
| 327 stocks | **Partly** | That's plausibly the count of Nifty 500 names with ≥ 80% of 10-year history: today's list gives 346. The traded universe in the code is the **F&O subset: 159 stocks**. | `main.py` filter; rebuilt check |
| 3 pairs | **No** | The code has no 3-pair selection. The "Holy Grail" filter selects **0** pairs. | `main.py`; `results/original_run/` |
| PCA + DBSCAN, OU half-life, Hurst | **No** | None of these is in the code. The method is a correlation filter plus the Engle-Granger test. | `main.py` |

## Numbers you can state

- Universe: 159 liquid NSE F&O stocks, 11 sectors, 10 years of daily data.
- Search: 1,496 intra-sector pairs → 597 with correlation ≥ 0.8 → 99 cointegrated (p ≤ 0.05), all chosen on 2016–2022 data.
- Strategy: 60-day rolling-OLS hedge ratio, z-score entry at 2.0 and exit at 0.5, 15 bps per leg per side.
- Out of sample (Jan 2023–Apr 2026, 39 months): the top 3 in-sample pairs returned Sharpe −0.28. All 99 pairs together returned Sharpe −0.80.
- Found and fixed two bugs: look-ahead in pair selection, and costs charged on one leg only. Also showed that the best in-sample Sharpe (≈0.7) is below what selection alone produces from ~75–100 noise pairs (≈1.0).

## Suggested resume line

> Built a cointegration pairs-trading pipeline on 159 NSE F&O stocks (1,496 intra-sector
> pairs, Engle-Granger, rolling-OLS z-score). Audited it for look-ahead and cost bugs.
> With in-sample selection, the best pairs' out-of-sample Sharpe fell from 0.97 to −0.28
> over 39 months, which showed the in-sample edge was selection bias.
