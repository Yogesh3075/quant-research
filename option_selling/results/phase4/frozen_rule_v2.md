# Frozen rule v2: P3 (minimum premium + index stop)

Written 2026-11-10 11:07 regardless of results (the decision to paper trade is the owner's). Config SHA-256 `68db0b6f0b5cd7f076791e1c6942514ae52771107acdfedae0f0f933803d6abe`. Data in hand to 2026-11-09; design and validation to 2024-10-31; holdout scored once in Phase 4. `results/phase3/frozen_rule.md` (e1f1) is unchanged.

## Trade
- NIFTY 50 index options, monthly expiry only (last expiry of each calendar month as listed by NSE; actual expiry = the contract's last trading day).
- Entry: close of the first trading day after each monthly expiry; options on the next monthly expiry; S0 = NIFTY 50 close that day.
- Sell the put nearest 0.95 x S0, buy the put nearest 0.9 x S0. A strike needs close > 0 and contracts traded > 0 that day; search from the listed strike nearest the target further out of the money within 1% of target; else the nearest traded strike further out of the money than the target; skip only if none.
- **Premium filter:** prem_ratio = (short put close - long put close) / (short strike - long strike), entry-day closes before slippage. Trade only if prem_ratio >= 0.12; otherwise hold cash that cycle.
- Size: units so (spread width - net credit after slippage) x units = 10% of current capital; margin = that maximum loss.
- **Index stop:** at each NIFTY 50 close after entry and before the expiry day, if the close is below the short put strike, close both legs at the next trading day's close; if that day is the expiry day, let it settle. Otherwise hold to expiry; cash-settled against the final settlement price.

## Costs (VERIFY before trading)
- Slippage per unit: sell at close - max(0.5, 3% of close), buy at close + the same (stop exits included).
- STT on premium sold: 0.0170% from 2008-01-01, 0.0500% from 2016-06-01, 0.0625% from 2023-04-01, 0.1000% from 2024-10-01, 0.1500% from 2026-04-01; on long options expiring in the money 0.125% of intrinsic.
- Brokerage Rs 20 per order; exchange 0.0500% from 2008-01-01, 0.0350% from 2024-10-01; SEBI 0.0001%; stamp 0.003% on premium bought; GST 18%.
- Idle cash 6.5% a year (assumption).

## Capital
- Paper capital Rs 1,000,000; live units are rounded down to whole lots (NSE lot size on the entry date).

Frozen config file: `results/phase4/frozen_config_p3.yaml` (copy of config.yaml at the Phase 4 freeze), SHA-256 `68db0b6f0b5cd7f076791e1c6942514ae52771107acdfedae0f0f933803d6abe`, equal to the hash above; paper trading uses exactly this config.
