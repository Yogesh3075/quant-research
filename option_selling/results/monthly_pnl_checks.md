# Monthly P&L file checks

- credit_gross - slippage - payout - charges + interest = total_pnl: max gap Rs 0.000000 -> PASS
- capital_end = capital_start + total_pnl: max gap Rs 0.000000 -> PASS
- capital_start = previous capital_end: max gap Rs 0.000000 -> PASS
- charge items sum to stored total_charges: max gap Rs 0.000000 -> PASS
- last development capital_end vs fresh development backtest, put_spread: gap Rs 0.000000 -> PASS
- last development capital_end vs fresh development backtest, iron_condor: gap Rs 0.000000 -> PASS
- last development capital_end vs fresh development backtest, strangle: gap Rs 0.000000 -> PASS

Rows: 675 (put_spread 225, iron_condor 225, strangle 225).
Holdout rows built from the stored trades_<rule>_holdout.csv files; the holdout command was not run. Columns entirely blank in the holdout: none.
