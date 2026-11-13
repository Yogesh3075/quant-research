Chosen after seeing Phase 4 design and validation results (post-hoc); P3 was the pre-registered primary.

# Paper-trading candidate: P1 (minimum premium, no stop)

Config: `results/phase4/frozen_config_p3.yaml`, SHA-256 `68db0b6f0b5cd7f076791e1c6942514ae52771107acdfedae0f0f933803d6abe` (P1 uses `phase4.prem_min` and no stop). Data in hand to 2026-11-09; design and validation to 2024-10-31. In the Phase 4 holdout P1 traded 1 of 24 months, so the holdout says nothing about it.

## Trade
- NIFTY 50 index options, monthly expiry only; entry at the close of the first trading day after each monthly expiry; options on the next monthly expiry (the next month's monthly contract as listed that day, followed to its actual last trading day); S0 = NIFTY 50 close that day.
- Sell the put nearest 0.95 x S0, buy the put nearest 0.9 x S0 (close > 0 and contracts traded > 0; Phase 1 search within 1% of target, then the nearest traded strike further out of the money; skip only if none).
- **Premium filter:** prem_ratio = (short put close - long put close) / (short strike - long strike), entry-day closes before slippage; trade only if prem_ratio >= 0.12; otherwise cash.
- Size: units so (spread width - net credit after slippage) x units = 10% of current capital; margin = that maximum loss.
- No stop: hold to expiry; cash-settled against the final settlement price.

## Costs (VERIFY before trading)
- Slippage per unit: sell at close - max(0.5, 3% of close), buy at close + the same.
- STT on premium sold: 0.0170% from 2008-01-01, 0.0500% from 2016-06-01, 0.0625% from 2023-04-01, 0.1000% from 2024-10-01, 0.1500% from 2026-04-01; long options expiring in the money 0.125% of intrinsic. Brokerage Rs 20 per order; exchange 0.0500% from 2008-01-01, 0.0350% from 2024-10-01; SEBI 0.0001%; stamp 0.003%; GST 18%.
- Idle cash 6.5% a year (assumption). Live units rounded down to whole lots.
