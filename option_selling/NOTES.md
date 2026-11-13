# Nifty monthly option selling: research backtest

Hypothetical research backtest. **Not investment advice and not a trading recommendation.** No broker connection, no live orders.

## Question
Does systematically selling one-month Nifty 50 index options earn a premium (the variance risk premium) after realistic costs, and how large are the losses in crashes? Three rules were fixed in `configs/config.yaml` before any run; nothing was tuned after seeing results.

**Variance risk premium.** Option buyers pay for protection against large moves, so implied volatility is on average above the volatility that is later realised. A seller collects this difference as compensation for bearing crash risk, which shows up as rare, large losses.

## Run
```
pip install -e .
python scripts/run.py download   # NSE bhavcopies + index files (hours, 1 s pause per request), then builds data/processed
python scripts/run.py check      # results/data_check.md, results/backtest_checks.md
python scripts/run.py vrp        # results/vrp.md, results/iv_vs_rv.png
python scripts/run.py backtest   # development period only: results/backtest_dev.md, trades_<rule>.csv, charts
python scripts/run.py holdout    # last 24 cycles, runs once, logs to results/holdout_runs.log
python scripts/run.py monthly    # monthly P&L CSVs (development + stored holdout trades), results/monthly_pnl_*.csv
python scripts/run.py diagnostics  # development-only diagnostics, results/diagnostics.md
```
`all` runs download, check, vrp and backtest (not the holdout).

## Data
- **Options:** NSE daily F&O bhavcopy from the NSE archive (`nsearchives.nseindia.com`), one file per trading day, old format to 5 July 2024 and the UDiFF format after, both mapped to one set of columns (`data.parse_fo`). Files placed by hand in `data/raw/manual/` are read too. Only `NIFTY` index options and futures are kept. **End-of-day only: there are no bid/ask prices, so slippage is an assumption**, and the "close" of a thinly traded strike can be a stale last trade from earlier in the day.
- **Index:** NIFTY 50 close from NSE's `ind_close_all_DDMMYYYY.csv` archive (available from mid-2012); before that from Yahoo `^NSEI`. NIFTY 50 TRI from the factor-regime-rotation project (path in `configs/config.yaml`). India VIX from the same NSE index files (only where NSE includes it).
- **Expiries:** read from the bhavcopy `expiry` column, never assumed. The monthly expiry is the last expiry that actually traded in each calendar month. The list is in `results/monthly_expiries.csv` and `results/data_check.md`.
- **Final settlement price:** settle price of the expiring NIFTY future on expiry day (equals the index close; the difference is reported in the data check).

## Rules (fixed before running)
- **Entry:** first trading day after each monthly expiry, at the close; sell options on the next monthly expiry; hold to expiry; cash-settled at intrinsic value against the final settlement price.
- **Strike choice:** nearest listed strike to the target (moneyness x S0, S0 = index close on entry day) with close > 0 and contracts traded > 0; otherwise the next strike further out of the money; if none within 1% of the target, the month is skipped and logged.
- **Rule 1, put spread:** sell put 0.95 S0, buy put 0.90 S0.
- **Rule 2, iron condor:** rule 1 plus sell call 1.05 S0, buy call 1.10 S0.
- **Rule 3, short strangle (naked, comparison only):** sell put 0.95 S0 and call 1.05 S0.
- **Sizing:** Rs 10,00,000 start. Rules 1–2: units such that maximum loss (larger spread width minus net credit) = 10% of current capital; margin = that max loss. Rule 3: units = capital / S0 per option; margin 15% of notional per side (VERIFY), i.e. 30% of capital. Fractional units in the main result. Cash not used as margin earns 6.5% a year (VERIFY); a 0% version is reported too.
- **Holdout:** the last 24 monthly cycles, scored once at the end.

## Costs (all VERIFY, in `configs/config.yaml`)
| item | assumption |
|---|---|
| slippage | sell at close − max(0.5, 3% of close), buy at close + same, per unit |
| STT on options sold (on premium) | 0.017% to 31 May 2016; 0.05% from 1 Jun 2016; 0.0625% from 1 Apr 2023; 0.1% from 1 Oct 2024; 0.15% from 1 Apr 2026 (the last step from memory of Budget 2026, VERIFY) |
| STT on long options expiring in the money | 0.125% of intrinsic value |
| brokerage | Rs 20 per order, one order per leg at entry (expiry is cash settled) |
| exchange transaction charge | 0.05% of premium; 0.03503% from 1 Oct 2024 |
| SEBI fee | Rs 10 per crore of premium |
| stamp duty | 0.003% of premium bought |
| GST | 18% of brokerage + exchange + SEBI charges |

Simplifications: STT on notional (Jan–May 2008) is treated as on premium; stamp duty and GST rates are applied at today's levels for the whole period.

## Data coverage
- 4,668 trading days of NSE F&O bhavcopy, 2008-01-01 to 2026-11-09, all downloaded from the NSE archive (no blocking; no manual files). NSE has no file for 2 days (2013-10-09, 2021-03-30).
- 226 monthly expiries (2008-01-31 to 2026-10-27): Thursday until Aug 2025, then Tuesday; holiday shifts to Wednesday or Monday. Four contracts expired on a different day from their label (Nov 2008, Dec 2008, Apr 2009, Apr 2014); the actual last trading day is used. The final settlement price equals the index close on all 224 expiries where both exist.
- 225 complete monthly cycles: **development 201** (entries 2008-02-01 to 2024-09-27, expiries to 2024-10-31), **holdout 24** (entries 2024-11-01 to 2026-09-30).
- Full checks: `results/data_check.md`, `results/backtest_checks.md`.

## Diagnostic: implied vs realised volatility (development, 200 months)
Mean ATM implied vol 19.1%, mean realised vol to expiry 17.3%: **IV − RV = +1.8 vol points on average (median +2.6), and IV was above RV in 71% of months.** It was positive in 15 of 17 years (negative in 2008 and 2013). Puts are priced richer than calls (20.3% vs 17.9% IV). India VIX (from May 2014, 125 months) averaged 2.8 points above the realised vol that followed and was above it in 79% of months. See `results/vrp.md`, `results/iv_vs_rv.png`.

## Development results (201 cycles, Feb 2008 – Oct 2024, fractional units, idle cash at 6.5%)
| | CAGR | Vol | Sharpe | Sortino | Max DD | Worst month | Worst 3m | Skew | Win rate | Avg win | Avg loss | CVaR95 | CVaR99 | Skipped | Costs / gross profit |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Put spread | 8.5% | 7.2% | 0.30 | 0.34 | −15.9% (Dec 2010–Nov 2011) | −9.6% | −8.0% | −3.1 | 90.5% | +1.3% | −4.7% | −6.4% | −9.6% | 13 | 24.5% |
| Iron condor | 3.7% | 11.9% | −0.16 | −0.20 | −31.4% (Feb 2020–Feb 2021) | −9.7% | −17.8% | −1.2 | 78.6% | +1.7% | −4.7% | −9.6% | −9.6% | 26 | n/a (gross < 0) |
| Short strangle | 6.0% | 9.7% | 0.00 | 0.00 | −22.5% (Oct 2008) | −22.5% | −17.7% | −3.8 | 81.6% | +1.3% | −3.1% | −7.4% | −15.6% | 3 | 34.7% |
| NIFTY 50 TRI | 10.8% | 20.1% | 0.30 | 0.43 | −49.1% (2008) | −27.6% | −38.3% | −0.7 | 59.2% | +4.5% | −4.1% | −12.6% | −21.7% | | |
| Cash 6.5% | 6.5% | 0.2% | 0 | | 0% | | | | | | | | | | |

Sharpe and Sortino: excess over 6.5% cash, monthly, × √12. With **idle cash at 0%**: put spread 2.3% CAGR, iron condor −2.3% (max DD −61%), strangle 1.2%.

Where the money came from (development, rupees, starting from Rs 10 lakh):

| | option P&L before costs | slippage | other charges | interest on idle cash | final capital |
|---|---|---|---|---|---|
| Put spread | 10.6 lakh | 2.4 lakh | 0.16 lakh | 21.3 lakh | 39.3 lakh |
| Iron condor | −1.8 lakh | 3.8 lakh | 0.27 lakh | 14.2 lakh | 18.4 lakh |
| Short strangle | 3.8 lakh | 1.2 lakh | 0.13 lakh | 14.0 lakh | 26.4 lakh |

Margin use: rules 1–2 always 10% of capital (= max loss); strangle 30% of capital (15% per side, VERIFY). The whole-lot version is skipped in development: lot sizes by date are only in the bhavcopy from July 2024.

Skipped months (no traded strike within 1% of target): put spread 13 (11 for lack of a 0.90 put), iron condor 26 (adds 12 for lack of a 1.10 call), strangle 3. All are in the thin early years or in single months later.

## Stress months (development)
| event | entry → expiry | index move | TRI | put spread | iron condor | strangle |
|---|---|---|---|---|---|---|
| Oct 2008 | 2008-09-26 → 2008-10-29 | −32.3% | −27.6% | +0.6% (skipped) | +0.6% (skipped) | **−22.5%** |
| Oct 2008 | 2008-10-31 → 2008-11-28 | −4.5% | −7.0% | +3.4% | +7.6% | +10.9% |
| Aug 2015 | 2015-07-31 → 2015-08-27 | −6.8% | −6.2% | −3.1% | −2.5% | −1.0% |
| Aug 2015 | 2015-08-28 → 2015-09-24 | −1.7% | −2.5% | +1.8% | +2.9% | +1.8% |
| Feb–Mar 2020 | 2020-01-31 → 2020-02-27 | −2.7% | −6.3% | +0.9% | +1.5% | +1.0% |
| Feb–Mar 2020 | 2020-02-28 → 2020-03-26 | −22.9% | −22.5% | −9.6% | −9.6% | **−16.2%** |
| Feb–Mar 2020 | 2020-03-27 → 2020-04-30 | +13.9% | +7.3% | +2.8% | −9.5% | +2.5% |
| 4 Jun 2024 | 2024-05-31 → 2024-06-27 | +6.7% | +6.8% | +1.5% | −1.0% | +0.2% |

**The October 2008 crash was missed by luck:** on 2008-09-26 no 0.90 put traded within 1% of target, so both protected rules skipped that month under the fixed liquidity rule. Had they traded, the loss would have been about the full 10% of capital. The 10 worst months of each rule with the index move are in `results/backtest_dev.md`; for the iron condor, 7 of the 10 are sharp **rallies** (+10% to +19%, e.g. May 2009 election result), not crashes.

## Plain reading
- **A premium exists**: implied volatility was above realised in about 7 months out of 10, by roughly 2 vol points on average.
- **But it is small after costs and leverage limits.** The option P&L itself is modest; most of every rule's return is the 6.5% interest on idle capital. With cash at 0%, all three rules earn 1–2% a year or lose money. Against the right benchmark (cash at 6.5%), only the put spread adds anything (Sharpe 0.30), the strangle adds nothing, and the iron condor loses: the call side gives back more in sharp rallies than it collects.
- **Costs matter**: slippage (an assumption, since there are no bid/ask data) plus charges take about a quarter of the put spread's gross option profit and about a third of the strangle's; for the condor they exceed it.
- **The worst months**: the protected rules lose up to their planned ~10% of capital in a month, and do so several times (2008, 2011 twice, 2020). The naked strangle lost 22.5% in Oct 2008 and 16% in Mar 2020 at only 1× notional; at the leverage that the 15% margin allows, these would be ruinous.
- **Sharpe understates the risk of option selling.** Returns have a long left tail (skew −3 to −4, win rates of 80–90% with average losses 3–4 times the average win). A few months decide the result, and a sample of 17 years contains only a handful of them.
- **End-of-day data flatters execution**: the "close" of a thin strike may be a stale trade; real fills at entry would often be worse than close ± 3%.
- This is a hypothetical backtest, not investment advice and not a trading recommendation.

## Holdout (run 1, the only run; 24 cycles, entries 2024-11-01 to 2026-09-30)
Scored once on 2026-11-09, logged in `results/holdout_runs.log`; details in `results/backtest_holdout.md`.

| | CAGR | Vol | Sharpe | Max DD | Worst month | CVaR99 | Win rate | Skipped |
|---|---|---|---|---|---|---|---|---|
| Put spread | 3.1% | 7.5% | −0.39 | −9.5% | −9.5% | −9.5% | 91.7% | 5 |
| Iron condor | 3.2% | 7.4% | −0.40 | −8.6% | −8.6% | −8.6% | 87.5% | 10 |
| Short strangle | 3.8% | 5.3% | −0.46 | −6.6% | −6.6% | −6.6% | 87.5% | 0 |
| NIFTY 50 TRI | −2.3% | 13.9% | −0.55 | −13.4% | −11.0% | −11.0% | 50.0% | |
| Cash 6.5% | 6.5% | | | | | | | |

- All three rules trailed cash. Their option P&L before costs was negative (put spread −0.57 lakh, condor −0.55 lakh, strangle −0.14 lakh); interest on idle cash (about 1 lakh each) is the whole positive return. With cash at 0%: −2.9%, −3.0%, −0.8% a year.
- One month decided it: entry 2026-02-25 → expiry 2026-03-30, index −12.4%; the put spread lost 9.5% of capital, wiping out about two years of small wins.
- IV − RV in the holdout: +0.8 vol points on average, IV above RV in 67% of months: a thinner premium than in development.
- Whole lots (lot size from the UDiFF files): put spread 4.4% CAGR, iron condor 4.3%. With Rs 10 lakh, the strangle (1× notional ≈ 40 units) is below one lot (65–75) in 21 of 24 months, so it mostly did not trade.
- No stress-test month falls in the holdout.

## Monthly P&L file
`python scripts/run.py monthly` writes `results/monthly_pnl_<rule>.csv` (225 rows each) and `results/monthly_pnl_all.csv` (675 rows, with a `rule` column), one row per monthly cycle, development and holdout (`period`). Holdout rows are built from the stored `trades_<rule>_holdout.csv` files; the holdout was not re-run. `results/monthly_pnl_summary.csv` has totals and averages per rule and period; `results/monthly_pnl_checks.md` has the reconciliation checks (all pass).

Columns, by group (rupees unless `_pct` / `_pts`):
- **Cycle:** rule, period, cycle_no, entry_date, expiry_date (actual expiry day), days_to_expiry, skipped, skip_reason.
- **Market:** index_at_entry (S0), index_at_expiry (final settlement price), index_move_pct, india_vix_at_entry (from May 2014), atm_iv_at_entry_pct, realised_vol_pct, iv_minus_rv_pts.
- **Legs** (blank where the rule has no such leg): strikes; entry prices = bhavcopy close per unit; short_put / short_call_contracts_traded on the entry day; *_settle_value = intrinsic value per unit at expiry.
- **Position:** capital_start, units, lots and lot_size (only from July 2024, when the bhavcopy has a lot column; lots = units rounded down, for information only), notional (units × S0 per short leg), margin_used (spreads: max loss; strangle: 15% of notional per side), margin_pct_of_capital, idle_cash, max_loss_planned ("unlimited" for the strangle).
- **P&L:** credit_gross (premium received − paid at close × units) − slippage_cost = credit_net; settlement_payout (what the position paid at expiry, net of long legs); option_pnl_before_charges = credit_net − settlement_payout.
- **Charges:** brokerage, stt (on premium sold + on long legs expiring in the money), exchange_charges, sebi_fees, stamp_duty, gst, total_charges; total_costs = slippage + charges; costs_pct_of_credit_gross. The items are recomputed from the stored legs, prices and units with the cost formulas and checked to sum to the stored total.
- **Result:** option_pnl_net = option_pnl_before_charges − total_charges; cash_interest on idle cash at 6.5%; total_pnl; return_on_capital_pct and option_return_on_capital_pct (without interest); return_on_margin_pct; capital_end, cumulative_pnl, drawdown_from_peak_pct (within the period); win (option_pnl_net > 0); outcome: *full profit* (no settlement payout), *max loss* (the planned maximum loss was reached), *partial loss* (some payout, the month can still be net positive), *skipped*; nifty_tri_return_pct over the same cycle (entry to next entry).

How to read it: compare `option_pnl_net` (what selling options earned after costs) with `cash_interest` (what the idle capital earned anyway). Sort by `option_return_on_capital_pct` to see the few months that decide the result.

Diagnostics on the development period (option P&L without interest, return on margin, leverage 1x/2x/3x, slippage x0.5/x2, 2008–2015 vs 2016+, win-rate illusion, skipped months): [results/diagnostics.md](results/diagnostics.md), tables in `results/diagnostics_tables.csv`, chart `results/monthly_pnl.png`.

## Phase 2: delta-based strikes and cheaper hedging
Pre-registered split and 6 variants (short put |delta| 0.20 / 0.15 x hedge H1 long put |delta| 0.05, H2 long put 5% of S0 below, H3 naked put sized so a 25% fall loses 10%): `results/phase2/split.md`, `results/trials.csv` (9 cumulative trials). Design = entries 2008–2018, validation = 2019 to Oct 2024 (run once; seen in aggregate in Phase 1, so not a clean test); the holdout is not used. Daily mark-to-market per cycle in `marking.py`. Commands: `python scripts/run.py phase2` (design), `python scripts/run.py phase2-validate` (once). Results, choice and plain reading: [results/phase2/phase2_report.md](results/phase2/phase2_report.md); monthly rows with deltas, IVs and marking: `results/phase2/monthly_pnl_phase2.csv`.

## Phase 3: stop-loss and premium filter (last tuning phase)
Pre-registration: `results/phase3/preregistration.md` (trials 10–12; 12 cumulative). Variants on the Phase 1 put spread (Phase 2 fallback rule): e1 stop at 2x credit (exit next close), f1 trade only if ATM IV − trailing 21-day RV is above its expanding median, e1f1 both. Commands: `python scripts/run.py phase3` (design), `python scripts/run.py phase3-validate` (once). Report: [results/phase3/phase3_report.md](results/phase3/phase3_report.md); every stop: `results/phase3/stops.csv`. **The rule set is frozen in [results/phase3/frozen_rule.md](results/phase3/frozen_rule.md)** (config hash and data dates inside); no further changes before paper trading.

## Strategy census (one fixed version of each family)
12 strategies (short put, short call, straddle, strangle, bear call spread, iron butterfly, cash-secured put, put ratio, calendar, covered call, collar, delta-hedged straddle) + 8 stop variants = 20 trials (32 cumulative), same cycles, costs and split; no tuning; the frozen rule is unchanged. Pre-registration: `results/census/preregistration.md`; shortlist rule and notes: `results/census/shortlist.md`. Commands: `python scripts/run.py census` (design), `python scripts/run.py census-validate` (once). Report: [results/census/census_report.md](results/census/census_report.md); combination inputs: `correlation_design.csv`, `crash_table.csv`, `co_loss_pairs.csv`.

## Phase 4: fixes, minimum premium, index stop, one holdout check
Fixes (S9 far-leg valuation, S6 notional cap, `iv_minus_rv_pts` renamed `iv_minus_future_rv_pts`, all other results checked unchanged): `results/phase4/fixes.md`. Pre-registration: `results/phase4/preregistration.md` (trials 33–35, P3 = minimum premium + index stop as the primary hypothesis). Commands: `python scripts/run.py phase4` (design + validation, both in-sample for this idea), `python scripts/run.py phase4-holdout` (once). Report: [results/phase4/phase4_report.md](results/phase4/phase4_report.md); P3 rule for paper trading: [results/phase4/frozen_rule_v2.md](results/phase4/frozen_rule_v2.md); paper-trading sheet: `results/phase4/paper_trading_log.csv`. The Phase 3 frozen rule (e1f1) is unchanged.

## Phase 5: June 2023 fix, then pairing selling with buying
Relabel fix (`data.relabel`; NSE renamed the June 2023 contract after the 2023-05-26 entry) and its bugfix recompute (`python scripts/run.py bugfix-recompute`, results in `*_bugfix.csv`; logged runs not re-run): `results/phase5/fixes2.md`. Frozen config files: `results/phase3/frozen_config_e1f1.yaml`, `results/phase4/frozen_config_p3.yaml`; post-hoc paper candidate `results/phase4/frozen_rule_p1.md`. Pre-registration: `results/phase5/preregistration.md` (trials 36–38: tail hedge on P1 and on e1f1, mirror rule). `python scripts/run.py phase5` writes [results/phase5/phase5_report.md](results/phase5/phase5_report.md), `crash_table.csv`, `by_year.csv`.

## Monthly routine (paper trading only)
The tool covers the frozen e1f1 rule and the post-hoc P1 candidate (S7 + stop optional: `live.include_s7`). It reads rule parameters only from `results/phase3/frozen_config_e1f1.yaml` and `results/phase4/frozen_config_p3.yaml`, and stops if either file's SHA-256 differs from the hash in its frozen rule file. It uses the backtest's own functions; `python scripts/run.py check` reproduces six historical months (decisions, strikes, units, stop dates, P&L) exactly.

1. **Entry day** (first trading day after a monthly expiry), after about 7 pm IST when NSE has published the bhavcopy: `python scripts/run.py signal --date YYYY-MM-DD`. It prints TRADE/SKIP per rule with the reason, strikes, closes, contracts and open interest, whole lots, max loss, margin estimate and stop level, writes `results/live/<YYYY-MM>_signal.md` and adds `planned` rows to `results/phase4/paper_trading_log.csv`. If the file is not out yet, it says so; a file placed in `data/raw/manual/` is also read.
2. **Record fills** (your paper price from the broker's live quote near the close): `python scripts/run.py fill --rule e1f1 --leg short_put --price 123.4 --lots 1 [--time 15:25]`; exit fills with `--exit`.
3. **Each trading evening** while a trade is open: `python scripts/run.py monitor --date YYYY-MM-DD` (P&L, distance of NIFTY to the short strike, stop status; writes `results/live/daily_marks.csv`). "STOP: exit at tomorrow's close" means exit at the next day's close. The "day before expiry" exception uses the next weekday, so check NSE holidays.
4. **Exit day** (the day after a stop trigger, or the expiry day): `python scripts/run.py close --date YYYY-MM-DD` (add `--expiry` if NSE moved the expiry earlier than the listed date). It records P&L with the backtest cost model, the backtest-expected P&L and the difference, and the new paper capital.
5. **Monthly:** `python scripts/run.py status`.

Reminders: paper trading only; no broker connection or orders. Verify STT, exchange charges and stamp duty against current rules; verify the lot size (the tool uses the bhavcopy lot column, then NSE's `fo_mktlots.csv`, then `live.lot_size` with a warning) and the actual margin with your broker. Paper capital grows only by option P&L (no assumed interest).
