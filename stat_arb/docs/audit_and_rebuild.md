*Detailed audit and rebuild notes. File and command names follow the current package layout (`src/pairs/`, `scripts/`).*

# Pairs Trading on NSE F&O Stocks: Cointegration + Z-Score Mean Reversion

## Question
Do intra-sector, cointegrated pairs of liquid Indian stocks give a profitable
z-score mean-reversion strategy after costs, **out of sample**?

**Short answer: no, not with this rule set.** The best pairs look reasonable in the
sample they were chosen on, but that is about what the best of ~100 zero-skill pairs
would look like. Out of sample, the in-sample winners lose money.

## Data
- Daily adjusted closes from Yahoo Finance (`yfinance`), 2016-01-01 to 2026-04-15.
- Sectors: Yahoo Finance sector field (current, not point-in-time).
- Universe: today's NSE F&O list hard-coded in `src/pairs/original/scan.py` (176 names). After
  download failures (renamed/delisted symbols such as TATAMOTORS, GMRINFRA, PEL, LTIM)
  and the 80%-history filter, **159 stocks** are used.
- The raw data is not committed. `src/pairs/original/yahoo.py` rebuilds it.

## Method
1. **Universe:** F&O stocks only, so both legs can be traded with stock futures.
2. **Pair search (in-sample only, before 2023-01-01):** all intra-sector pairs, then
   Pearson correlation of prices ≥ 0.80, then Engle-Granger cointegration p ≤ 0.05.
3. **Spread:** `log(Y) − (α + β·log(X))`, with α and β from a 60-day rolling OLS fitted
   on the previous 60 days.
4. **Signal:** 60-day rolling z-score of the spread. Enter at |z| > 2.0, exit at |z| ≤ 0.5.
   There is no stop-loss and no time stop.
5. **PnL:** the position set at day t's close earns day t+1's return; returns are per 1
   unit of Y notional, hedged with β units of X.
6. **Costs:** 15 bps per leg per side (entry and exit), on both legs. That is
   `0.15% × (1 + |β|)` per entry or exit, about 0.6% of Y notional per round trip when β ≈ 1.
7. **Out-of-sample:** 2023-01-01 to 2026-04-15 (39 months). OOS data is never used to choose pairs.

## Audit findings

| # | Item | Status | Detail |
|---|------|--------|--------|
| 1 | Look-ahead in rolling β / z-score | OK | β is fitted on `[i-60, i)` and z uses data up to the close of day i. The position is lagged one day (`src/pairs/original/backtest.py`, `pos_ts.shift(1)`). |
| 1 | Look-ahead in pair selection | **Problem (fixed)** | The original code ran the correlation and cointegration tests on the full 10 years, then reported a backtest over the same 10 years. There was no out-of-sample period. Selection now uses data before `SPLIT_DATE` only. |
| 1 | PCA, DBSCAN, OU half-life, Hurst, stop-loss | **Not in code** | The pipeline is: sector grouping, correlation filter, Engle-Granger test, z-score rule. None of these other steps exist in this repo. |
| 2 | Selection on results | **Problem** | The "Holy Grail" filter (Sharpe > 1.5, DD > −15%) picked pairs by their backtest over the same data they were tested on. No pair ever passed it, in the original run or now. There is no set of "3 final pairs" in the code. Trial count: 1,496 intra-sector pairs; 597 passed correlation; 99 passed cointegration and were backtested (75 in the original full-sample run). |
| 3 | Survivorship | **Problem (documented, not fixed)** | The F&O list, the Nifty 500 list and the sectors are all today's. Stocks that dropped out of F&O or were delisted are missing. This biases results upward. |
| 4 | Costs | **Problem (fixed)** | The code commented "0.15% per leg" but charged only one leg: `trades * TC`. It now charges `trades * TC * (1 + |β|)`. The daily rebalancing of β while a position is open is still uncharged. |
| 4 | Shorting | Partly OK | The F&O filter means the short leg could use stock futures. But the backtest uses cash prices and fractional β-weighted notional. It ignores lot sizes, margin (~15–25% per leg), roll costs and the futures basis. |
| 5 | Sharpe definition | Non-standard | The original "Sharpe" is CAGR / annualised vol. The reports now also give the standard `mean/std × √252` on daily returns ("Sharpe (daily)"). The two differ by less than 0.1 here. |
| 5 | Significance | **Not significant** | Best full-sample pair (HDFCBANK/ICICIBANK): daily Sharpe 0.53, t = 1.68. The best of 75 zero-skill pairs over 8.2 years is expected to show Sharpe ≈ 1.0. Top-3 in-sample pairs, out of sample: Sharpe −0.28, t = −0.50, 95% block-bootstrap CI [−1.38, 0.62]. |
| – | Minor | Note | `prices[tickers].dropna()` starts a whole sector at its youngest stock's listing date (Financial Services has only 8.2 years). "Asset Y (Long)/Asset X (Short)" was mislabelled because the strategy trades both directions; renamed to Asset Y / Asset X. "Total Trades" counts entries plus exits, so 2 per round trip. |

## Results

Reproduction: the original code was run on rebuilt Yahoo data. Its distribution matches
the committed report (`results/original_run/`): 75 pairs in both runs, best Sharpe 0.66
vs 0.60, median −0.18 vs −0.15, and 0 Holy-Grail pairs in both. Yahoo has revised its
price adjustments since, so individual pair numbers differ slightly.

"Sharpe" below is CAGR/vol, as in the original code.

| Run | Pairs | Best Sharpe | Median Sharpe | Pairs with Sharpe > 1 and DD > −18% |
|-----|------:|------------:|--------------:|-----------------------------:|
| Committed report (original data, full sample) | 75 | 0.60 | −0.15 | 0 |
| Original code, rebuilt data (full sample, 1-leg cost) | 75 | 0.66 | −0.18 | 0 |
| + cost on both legs (full sample) | 75 | 0.57 | −0.25 | 0 |
| In-sample selection, **in-sample** 2016–2022 | 99 | 0.73 | −0.13 | 0 |
| In-sample selection, **out-of-sample** 2023–Apr 2026 | 99 | 0.97* | −0.28 | 0 |

\*The best OOS pair (HAVELLS/INDIGO) had an in-sample Sharpe of −0.32. You could only have
picked it by looking at OOS results, so it is not evidence of skill.

**Top 3 pairs by in-sample Sharpe** (chosen before the OOS period, equal weight):

| | Sharpe (daily) | t-stat | 95% bootstrap CI | Max DD | Round trips |
|---|---:|---:|---:|---:|---:|
| In-sample 2016–2022 | 0.97 | 2.54 | [0.41, 1.60] | – | – |
| Out-of-sample 2023–Apr 2026 | **−0.28** | −0.50 | [−1.38, 0.62] | −14.6% | 59 |

Pairs: HDFCBANK/KOTAKBANK, JKCEMENT/ULTRACEMCO, HDFCLIFE/MANAPPURAM. The equal-weight OOS
portfolio of all 99 in-sample-selected pairs: Sharpe −0.80, t = −1.42.

## Limitations
- Survivorship: today's F&O and index lists, today's sectors.
- One train/test split (2023-01-01) and 39 months of OOS: a short window with wide error bars.
- Execution: cash closes, no futures basis, lot sizes, margin or roll. No slippage
  beyond the 15 bps per leg per side.
- The data comes from Yahoo. It is free but has gaps (6 symbols failed) and revisions.
- Few pairs survive. Any "top 3" is a small, heavily selected sample.

## How to run
```bash
pip install -e .
python scripts/original.py data    # downloads prices + sectors (~10 min, mostly sector lookups)
python scripts/original.py scan    # in-sample selection, IS/OOS backtest -> results/FnO_StatArb_Report.csv
python scripts/original.py audit   # before/after table and significance tests
```

## Files
- `src/pairs/original/scan.py`: universe filter, in-sample pair selection, IS/OOS report.
- `src/pairs/original/backtest.py`: single-pair rolling-OLS z-score backtest and KPIs.
- `src/pairs/original/audit.py`: reproduces the original full-sample run and runs the tests above.
- `src/pairs/original/yahoo.py`: rebuilds the input CSVs from Yahoo Finance.
- `results/original_run/`: the reports committed before this audit (full-sample, original code).
- `results/resume_numbers.md`: numbers that survive the audit.

---

# Rebuild: pairs trading on the point-in-time Nifty 500

The audit above covers the original code, which is unchanged. `src/pairs/rebuild.py` is a separate rebuild. It uses the point-in-time Nifty 500 from 2011 to Nov 2026, has no look-ahead, charges costs on both legs, and keeps a locked holdout.

**Method:** a 12-month formation window and a 6-month trading window, rolled forward every 6 months. Candidate pairs must be Nifty 500 members on the formation date, in the same sector, with full price history and a median traded value of at least Rs 5 crore. Pairs pass an Engle-Granger test (p < 0.05) with an OLS hedge ratio on log prices and a half-life of 5 to 60 days. The top 20 by p-value are kept, with each stock in at most 2 pairs. Entry is at |z| > 2 using the formation mean and std, exit when z crosses 0, stop at |z| > 4, and anything still open closes at window end. Rs 10 lakh is split across 20 slots, with equal rupees long and short. Costs are 10 bps per leg per side, plus 5/10/20 bps slippage by size. The point-in-time F&O list comes from NSE F&O bhavcopies.

**Validation:** 6 logged trials (entry z 1.5/2.0/2.5 × formation 6/12 months) on 2011-2022. One variant was chosen on development Sharpe and run once on the 2023 to Nov 2026 holdout.

| | Development 2011-2022 | Holdout 2023 to Nov 2026 |
|---|---:|---:|
| Sharpe, all pairs | 0.25 | **−0.54** |
| Sharpe, F&O subset (shortable) | 0.48 | −0.17 |
| CAGR / max drawdown, all pairs | 1.2% / −12.5% | −3.3% / −16.4% |
| Deflated Sharpe (6 trials) | 0.18 | – |

**Conclusion: no edge.** Full tables, trade statistics and caveats are in `results/summary.md`.

```bash
python scripts/rebuild.py data      # copy inputs from ../momentum_research into data/, fetch NSE F&O lists
python scripts/rebuild.py dev       # 6 trials on 2011-2022 -> results/trial_log.csv, chosen_variant.json
python scripts/rebuild.py holdout   # run once; refuses to run again (results/holdout_lock.json)
```

## Long-only variants

`src/pairs/long_only.py` reuses the rebuild's data, pair selection and costs. It tests three long-only variants: A, pair switching against a 50/50 buy-and-hold benchmark; B, the cheap leg only, hedged with Nifty 50 futures; and B without the hedge. It also splits the rebuild's development trades into their long and short legs. 2023 onwards is labelled a *seen holdout*, because the rebuild had already looked at it. The trial log now has 9 trials.

**Result: no edge.** A beat its buy-and-hold benchmark by 0.12% a month in development (t = 0.88) and by −0.02% a month in the seen holdout. B had a Sharpe of 0.10 in development and −0.12 in the seen holdout. Against the market, the excess return came from the short leg, not the long leg. Details are in `results/long_only/summary_long_only.md`.

```bash
python scripts/long_only.py         # writes results/long_only/ and appends trials 7-9 to results/trial_log.csv
```
