# Pre-registration: Nifty 500 momentum

Written and committed before any signal statistic was computed. Values are mirrored in `Configs/config.yaml`
(`split`, `momentum`, `portfolio`, `diagnostics`); the config is what the code reads.

## Question
Does 12-1 / 6-1 price momentum earn a premium on the point-in-time Nifty 500, after realistic costs, and what
explains it?

## Calendar and split
- Trading calendar: NIFTY 50 index trading days, including weekend special sessions (budget days, Muhurat trading).
- Signal date t: last trading day of each month, from January 2011 to the latest complete month.
- Execution: the close of the next trading day after t. When that day is a special session (e.g. Muhurat trading on
  1 November 2024) it is still the execution day; this is noted, not changed.
- Development: signal months 2011-01 to 2024-10 (166 months).
- Locked holdout: signal months 2024-11 onward (about 24 months). Returns over any period starting at or after the
  first holdout execution date (2 December 2024) are holdout returns. No statistic, chart or table may use them until
  the single holdout run in the final testing phase. The code enforces this (`Transform/split.py`: `guard` raises unless
  `split.holdout_unlocked` is true and `--holdout` is given; neither exists before that phase).
- Diagnostics whose return month would fall in the holdout (for example IC decay at t+12 for late development months)
  drop those observations instead of reading them.

## Factor (fixed)
- `mom_12_1 = P(t-21) / P(t-252) - 1`, `mom_6_1 = P(t-21) / P(t-126) - 1`. P = adjusted close (dividends, splits,
  bonuses; see the Phase 1 reports). Lags in trading days of the NIFTY 50 calendar; each lag price is the last close on
  or before the lag date, no older than 5 trading days.
- Across eligible stocks at t: clip each measure at the 1st and 99th percentile, z-score (ddof 1),
  score = z(0.5 z_12_1 + 0.5 z_6_1). Rank 1 = highest score.

## Eligibility at t (fixed)
- Member of the point-in-time Nifty 500 on t and not excluded by the universe decisions (placeholders, second share
  classes, uncertain spells).
- A price on t, and on both lag dates as defined above; at least 252 trading days of price history.
- Median daily traded value over the trailing 63 trading days of at least Rs 5 crore (VERIFY: placeholder threshold).
- No quarantined price event, unadjusted demerger/rights or unadjusted corporate action inside the look-back
  (t-252, t] (Phase 1c `lookback_exclusions.csv`).

## Returns for diagnostics
- From the execution close after t to the execution close after the next signal date, adjusted close.
- A stock that stops trading inside the period earns its return to its last close.
- Ex-date returns of unadjusted demergers/rights/corporate actions in a holding period are set to 0 and flagged.

## Portfolio rule (fixed now, used from Phase 3)
Top 30 by rank, equal weight, sector cap 25% (NSE industry), buffer: a holding stays while its rank is 45 or better,
monthly rebalance at the execution close.

## Diagnostics planned for Phase 2 (development months only; no trials)
IC (Spearman) of score, z_12_1 and z_6_1 with next-period returns (mean, Newey-West t with 3 lags, share positive, ICIR,
by year); quintile and decile returns (monotonicity, top-minus-bottom, top-minus-universe with Newey-West t, by year);
IC decay at t+1, 2, 3, 6, 12; spreads within liquidity terciles; survivorship comparison against today's list.

## Trial log
`Data/processed/results/trial_log.csv` records every tested variant from Phase 3 on. Phase 2 adds no trials.

---

# Addendum (Phase 3), written before any backtest

## Rule changes from Phase 3a (data)
- Execution is the close of the next **regular** session after the signal date. Weekend and special sessions (Muhurat
  trading, budget Saturdays) are used for marking prices, never for execution.
- A price move confirmed by NSE's raw close on at least median volume is real even if it reverses; only moves that fail
  this are quarantined.
- Suspensions (trading stops and resumes within 60 days): a holding stays held with no price and is valued at the first
  close after trading resumes; it cannot be bought while suspended. A stop longer than 60 days is an exit at the last close.

## Trial 1 (primary)
At each monthly signal date, eligible stocks ranked by momentum score. Hold 30 names, equal weight.
- Buffer: a current holding stays while it is still eligible and its rank is 45 or better. New names fill up to 30 from
  the top of the ranking.
- Sector cap 25% (NSE industry from Phase 1; `Unclassified` is its own sector). With 30 equal weights this is at most
  7 names per sector. Kept holdings are taken first in rank order and a kept name that would breach the cap is dropped;
  a new name that would breach it is skipped for the next-ranked one.
- A holding that cannot be traded on the execution day (suspended, no price) stays as it is and counts toward the 30.
- Execute at the next regular session's close. Weights drift between rebalances; at each rebalance all tradable
  holdings return to equal weight.

## Trial 2 (alternative)
The same rule rebalanced quarterly, at signal months March, June, September and December (the first portfolio is formed
at the first signal month, January 2011). Reason, written now: Phase 2's IC peaks at t+3 and stays positive to t+6, so a
slower rebalance may keep most of the signal at much lower cost. No other variants.

## Simulation
- Capital Rs 10,00,000. Fractional shares in the main result; a whole-share version (shares rounded down at the raw
  close) is reported alongside.
- Positions are held in total-return units at the adjusted close, so dividends are reinvested in the stock.
- Costs (all VERIFY, `costs` in the config): STT 0.1% each side, NSE transaction charge, SEBI fee, stamp duty 0.015% on
  buys, GST 18% on brokerage + exchange charge + SEBI fee, a DP charge per stock per sell day; brokerage 0 (assumption:
  a zero-brokerage delivery account). Slippage by the 63-day median traded value at the trade date: >= Rs 25 crore 5 bps,
  Rs 10-25 crore 10 bps, Rs 5-10 crore 20 bps (below Rs 5 crore, only possible on sells, also 20 bps).
- Scenarios: zero (no costs), base, high (2x slippage).
- Benchmarks: (i) equal weight of all eligible stocks, rebalanced monthly with the same costs; (ii) NIFTY 500 TRI and
  (iii) NIFTY 50 TRI, both without costs, labelled "index".
- Delistings: sold at the last available close. Unadjusted demerger/rights/corporate-action ex-date returns are set to 0
  while held. Quarantine and eligibility as in Phase 2.
- Period: development only, from the first execution (February 2011) to the execution close after the last development
  signal date (the first holdout execution date, 2 December 2024). Monthly returns are measured between execution closes.

## Results planned
CAGR, volatility, Sharpe (risk-free 6.5%, VERIFY), Sortino, max drawdown, Calmar, worst month, turnover, holdings,
sector weights, costs by component; difference vs equal weight (Newey-West t, 3 lags); alpha and beta on the
equal-weight benchmark and on NIFTY 500 TRI; break-even slippage multiple; calendar years; worst months; deflated Sharpe
ratio with 2 trials; profit concentration.

---

# Addendum (Phase 4), written before the walk-forward and the holdout

## Grid (18 combinations, fixed now)
signal {blend 50/50 (default), 12-1 only, 6-1 only} x holdings N {20, 30, 50} x rebalance {monthly, quarterly}.
Buffer: a holding stays while it is eligible and ranked 1.5 N or better (30, 45, 75), for both monthly and quarterly
(as in Phase 3). Ranking for "12-1 only" / "6-1 only" uses z_12_1 / z_6_1 of the same eligible set. Sector cap 25%
(at most floor(0.25 N) names per sector: 5, 7, 12), base costs, eligibility unchanged. The two Phase 3 trials
(blend, 30, monthly and blend, 30, quarterly) are inside the grid; cumulative trials = 18.

## Folds
Expanding window inside development (signal months 2011-01 to 2024-10). First training window 60 months
(2011-01 to 2015-12); a 1-month embargo; test windows of 12 months stepping 12 (first test 2016-02 to 2017-01). The last
test window is cut at 2024-10 (9 months); 9 folds. Each test window starts in cash; the cost of entering is reported.

## Selection
On each training window only: the combination with the highest net Sharpe (base costs, monthly returns, risk-free 6.5%).
Tie-break: higher mean IC of the chosen signal on the training months, then lower turnover. Training results come from
one run per combination from 2011-01 (an expanding window always starts there), cut at the training end.

## Holdout (run once)
Frozen config: the same selection rule on the full development period. Written to
`Data/processed/results/phase4/frozen_config.json` with a config hash and the data end date, and committed before the
holdout run. The holdout covers signal months 2024-11 to the last month with a complete holding period. It is run once
for the frozen selection, the fixed primary, quarterly, equal weight, NIFTY 500 TRI and NIFTY 50 TRI, each starting in
cash. The run is logged before any chart is drawn; a second run needs `--unlock-holdout` and is reported as run 2.

---

# Addendum (Phase 5), written before the institutional tests

## Two fixed variants (no grid, no selection); cumulative trials = 20
- **Sector-neutral (trial 19):** at each signal date the momentum score is z-scored within each sector of the eligible
  set (ddof 1; a sector with fewer than 3 eligible stocks gets 0), then the primary's rules (top 30, buffer 45, sector cap
  25%, monthly, base costs).
- **Size-neutral (trial 20):** the score is z-scored within point-in-time traded-value terciles (63-day median daily
  traded value at the signal date), then the primary's rules.
- Both are evaluated on the full development period and on the walk-forward test months (each test window from cash),
  with no selection.

## Tests (development months only)
1. Fama-MacBeth: monthly cross-sections of next-period returns on (A) score; (B) + log median traded value; (C) + beta and
   volatility over 252 days (daily returns vs NIFTY 500 price index, at least 200 observations); (D) + sector dummies;
   (E) + previous month's return (21 trading days). Mean slopes with Newey-West t (3 lags); full development and
   walk-forward test months; model D by year.
2. Neutral variants vs the primary and equal weight (Phase 3 metrics).
3. Exposures of the primary's holdings: traded-value percentile, liquidity terciles, beta and volatility vs the eligible
   universe, top 5 sector over/underweights.
4. Capacity: the primary at Rs 10 lakh, 1 crore, 10 crore and 100 crore with trades capped at 5% of the 63-day median
   daily traded value (an unfilled buy stays in cash; an unfilled sell stays held and is retried at the next rebalance).
5. Momentum states: primary minus equal weight after the NIFTY 500 TRI's trailing 12-month return (to the signal date)
   was up vs down; the 2020 episode month by month; rolling 12-month beta to equal weight.
6. Spanning: the primary's monthly return over the risk-free rate and the Q5-minus-Q1 spread regressed on IIMA's MF,
   SMB, HML, WML. Alignment: the return of signal month t (execution after the end of month t to execution after the end
   of month t+1) is matched to IIMA's calendar month t+1. Excess returns use IIMA's RF. Only overlapping development
   months are used.
