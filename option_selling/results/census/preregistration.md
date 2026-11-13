# Strategy census: pre-registration (committed before any census run)

One fixed version of each family, no tuning. 12 strategies + 8 stop variants = 20 new trials (13–32; cumulative 32). References (not trials): base put spread (Phase 2 fallback version), frozen e1f1 rule, Phase 1 iron condor and Phase 1 strangle (fallback rule), NIFTY 50 TRI buy-and-hold, cash. Split as Phases 2–3: design = entries 2008-01 to 2018-12 (132 cycles), validation = entries 2019-01 to the cycle expiring 2024-10-31 (69 cycles), run once. Holdout not loaded. The frozen rule is not changed.

## Common
- Entry at the close of the first trading day after a monthly expiry; legs on the next monthly expiry. Strikes: nearest traded strike to moneyness x S0 (Phase 1 search), then the Phase 2 fallback (nearest traded strike further out of the money; skip only if none, logged). ATM = target 1.0 x S0 by the same search (a call's out-of-the-money side is above, a put's below).
- Option costs as Phase 1. Futures (S12): 1 index point per unit per trade, STT on futures sold, exchange, SEBI, stamp duty on futures bought, Rs 20 brokerage per order, GST (rates in `config.yaml`, all VERIFY).
- Headline: strategy P&L without cash interest, as % of capital at cycle start (S10/S11: index leg + options; S12: options + futures hedge). Total return adds 6.5% on idle cash (capital minus margin).
- Margin: defined-risk structures = maximum loss; naked short side = 15% of units x S0 per naked side (S1, S2, S7: one side; S3, S4: two; S8: one uncovered short); S12 = two naked sides + 12% of the largest futures notional in the cycle; S10/S11 = 0 (index held in full, no idle cash). If margin exceeds capital, units are cut so it equals capital (logged).
- Sizing: defined = max loss over all settlement prices (payoff evaluated at 0, every strike and far above) minus net credit, x units = 10% of capital. Stress = loss at settlement at the stress level(s) (index -25% and/or +20%) minus net credit, x units = 10% of capital, with units x S0 <= 1.5 x capital per short side (cap logged). Notional = units x S0 = 1x capital.
- Risk % of capital: defined = max loss; others = loss at the worse of -25% / +20% at settlement (S10/S11 including the index leg); S12 not computed (hedged).
- Stop variant (S1–S8, `_e1`): Phase 3 method (mark at closes, loss >= 2 x net credit after entry slippage, exit at the next close with costs; trigger on the day before expiry ignored). S8: only if net credit at entry, else held and logged.
- "Costs % of gross credit": costs / |gross premium| (debit structures use the absolute premium).

## Strategy-specific
- **S8 put ratio:** stress loss at -25% = units x (0.10 S0 - net credit) for exact 0.95/0.90 strikes.
- **S9 calendar:** strike = nearest S0 among puts traded on the entry day in both the near (next monthly) and the far (the monthly after) contract; skip if none. Sell near at close - slippage, buy far at close + slippage; units = 10% of capital / net debit per unit; margin = debit. On the near expiry day the near leg settles at intrinsic and the far leg is sold at its close (last close on or before that day if missing, flagged). Coverage check: share of design cycles where the near-month ATM put strike also trades in the far month.
- **S10 covered call / S11 collar:** long NIFTY 50 TRI with notional = capital from entry to the next entry (TRI return), ETF cost 0.05% a year; sell 1.05 call (S11: also buy 0.95 put) with units = capital / S0. Also reported relative to TRI buy-and-hold.
- **S12 delta-hedged straddle:** sell ATM call + put, units = capital / S0. At each close from entry to the day before expiry, hedge = units x (call delta + put delta) in the near-month NIFTY future (the cycle's contract; it expires with the options, so the roll is the expiry day). Delta: Black-Scholes with each leg's own IV from its close that day (r 6.5%, q 1.3%, T = calendar days / 365; missing close: previous delta kept). Futures P&L = sum of hedge x change in the futures close, last step to the final settlement price; futures costs on every change in the hedge.

## Shortlist rule (design only; committed in `shortlist.md` before validation)
Among the 20 trials: option-only Sharpe above the base put spread's, worst month no worse than -12% of capital, break-even margin >= 3 points. Validation then runs once for all strategies, shortlist marked.
