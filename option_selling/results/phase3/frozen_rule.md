# Frozen rule (after Phase 3; no further changes): e1f1

Frozen 2026-11-10 10:03. Config SHA-256 `6356585ac093ad142cb57af7ee7fb02428062a9a6f5da4f6f5ca52ad76c856b0`. Data in hand to 2026-11-09; tuning used data to 2024-10-31 only (the Phase 1 holdout, Nov 2024 onward, was scored once in Phase 1 and not used since).

## Trade
- Instrument: NIFTY 50 index options, monthly expiry only (the last expiry of each calendar month as listed by NSE; actual expiry day = last trading day of the contract).
- Entry: first trading day after each monthly expiry, at the close; options on the next monthly expiry; S0 = NIFTY 50 close on the entry day.
- Sell the put nearest 0.95 x S0; buy the put nearest 0.9 x S0. A strike must have close > 0 and contracts traded > 0 that day; start at the listed strike nearest the target and move further out of the money; if none within 1% of target, take the nearest traded strike further out of the money than the target; skip the month only if none exists.
- Size: units so that (spread width - net credit after slippage) x units = 10% of current capital. Margin assumed = that max loss.
- Hold to expiry; cash-settled at intrinsic value against the final settlement price (index close on expiry day).
- Stop: at each close after entry, mark both legs at the bhavcopy close; if the mark-to-market loss (from the entry fills) >= 2.0 x net credit received, close both legs at the next trading day's close; ignore a trigger on the day before expiry; stay in cash until the next entry.
- Filter: trade only if ATM IV (strike nearest S0, mean of call and put Black-Scholes IV, r 6.5%) minus realised vol of the previous 21 trading days is above the median of that gap over all earlier entries (needs 24 earlier cycles).

## Costs (VERIFY before trading)
- Slippage per unit: sell at close - max(0.5, 3% of close); buy at close + the same.
- STT on premium sold: 0.0170% from 2008-01-01, 0.0500% from 2016-06-01, 0.0625% from 2023-04-01, 0.1000% from 2024-10-01, 0.1500% from 2026-04-01; STT on long options expiring in the money 0.125% of intrinsic value.
- Brokerage Rs 20 per order; exchange charge 0.0500% from 2008-01-01, 0.0350% from 2024-10-01 of premium; SEBI 0.0001%; stamp duty 0.003% on premium bought; GST 18% on brokerage + exchange + SEBI.
- Idle cash earns 6.5% a year (assumption).

## Capital
- Paper capital Rs 1,000,000; fractional units in the backtest. Live, units must be rounded down to whole lots (NSE lot size on the entry date), which at this capital means very few lots.

Frozen config file: `results/phase3/frozen_config_e1f1.yaml` (extracted from commit 59de823), SHA-256 `6356585ac093ad142cb57af7ee7fb02428062a9a6f5da4f6f5ca52ad76c856b0`, equal to the hash above; paper trading uses exactly this config.
