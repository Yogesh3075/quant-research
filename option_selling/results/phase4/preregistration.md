# Phase 4 pre-registration (committed before any Phase 4 backtest)

- **Base structure (all variants):** Phase 1 put spread: sell the put nearest 0.95 x S0, buy the put nearest 0.90 x S0 on the next monthly expiry, entry at the close of the first trading day after a monthly expiry, units so the maximum loss = 10% of capital, Phase 2 fallback for illiquid strikes, Phase 1 costs, idle cash at 6.5%.
- **prem_ratio** = (short put close - long put close) / (short strike - long strike), bhavcopy closes on the entry day, before slippage.
- **Trials 33-35 (cumulative 35):**
  - **P1 minimum premium:** trade only if prem_ratio >= 0.12, otherwise cash that cycle (logged); held to expiry.
  - **P2 index stop:** trade every month; if the NIFTY 50 close on a trading day after entry and before the expiry day is below the short put strike, close both legs at the next trading day's close (slippage and all charges); if that next day is the expiry day, settle normally. A leg with no close that day uses its next close (flagged). Replaces the 2x-credit stop.
  - **P3 = P1 + P2. P3 is the primary hypothesis, fixed now.** P1 and P2 show each part's contribution; no selection among them after seeing results.
- **References (not trials):** base put spread (fallback), frozen e1f1, census S7 cash-secured put + 2x-credit stop. All are recomputed with the Phase 4 engine (so the cost stress applies to them) and must reproduce their committed results exactly without the stress.
- **Sensitivity only:** P3 with prem_ratio thresholds 0.10 and 0.15 (not trials, not used for any choice).
- **Cost stress (every variant and reference):** entry slippage x2 when India VIX at entry > 20; NSE VIX data start in May 2014, so before that the ATM implied volatility at entry (Phase 1 method) is the proxy; and x2 slippage on every stop exit.
- **Periods:** design (entries 2008-01 to 2018-12) and validation (entries 2019-01 to the cycle expiring 2024-10-31), both labelled **"in-sample for this idea"** (both were seen when the idea was formed). **Holdout:** entries from 2024-11-01 through the last complete cycle (expiry 2026-10-27, 24 cycles), run once with `python main.py phase4-holdout`, labelled "holdout; aggregate results of the Phase 1 rules on this period were seen earlier".
- `frozen_rule_v2.md` is written for P3 regardless of results; `frozen_rule.md` (e1f1) is unchanged.
