# Phase 5 pre-registration (committed before any Phase 5 backtest)

- **Common:** fixed cycle builder (June 2023 relabel fix), Phase 1 costs, Phase 2 fallback for illiquid strikes, idle cash 6.5% a year (VERIFY; idle = capital minus margin, or minus the debit in buy months), design (entries 2008-01 to 2018-12) and validation (entries 2019-01 to the cycle expiring 2024-10-31), both labelled **"in-sample for this idea"**. The holdout (entries Nov 2024 onward) is not loaded. Frozen rules are unchanged.
- **Trials 36-38 (cumulative 38):**
  - **H1a, tail hedge on P1:** in every month P1 trades (prem_ratio >= 0.12), also buy the put nearest 0.85 x S0 on the same expiry (Phase 1 search, then the Phase 2 fallback further out of the money). Hedge units so premium paid including slippage = 15% of P1's net credit after slippage that month (rupees); its charges are extra. Held to expiry and settled, never closed early. The spread is sized exactly as P1. If no 0.85 put traded, the spread trades unhedged that month (logged).
  - **H1b, tail hedge on e1f1:** the same hedge in every month e1f1 trades; if e1f1's 2x-credit stop closes the spread, the hedge stays open to expiry.
  - **H2, mirror rule:** prem_ratio (Phase 4 definition) >= 0.12: sell the 0.95/0.90 put spread exactly as P1; < 0.06: buy the same spread (buy the 0.95 put, sell the 0.90 put) with units so the debit paid including slippage and entry charges = 2% of capital (STT on an in-the-money long put at expiry is extra); otherwise cash. Held to expiry, no stops.
- **References (not trials):** P1, frozen e1f1, base put spread, S7 cash-secured put + 2x stop (must reproduce their bugfix-recomputed results).
- **Diagnostics (not trials):** H2's buy months alone and sell months alone; the hedge leg alone in H1a and H1b.
- **Sensitivity only (not trials, no choice):** H1a with hedge budget 10% and 25% of credit; H2 with buy threshold 0.05 and 0.08.
- **Metrics:** option-only return (no cash interest) is the headline; Sharpe over all months with cash months = 0; deflated Sharpe at 38 trials uses the bugfix-recomputed trial Sharpe values of Phases 1-4 and the census.
