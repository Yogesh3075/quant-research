# Phase 5 fixes: June 2023 contract relabel

**Cause.** NSE renamed the June 2023 monthly contract (2023-06-29 -> 2023-06-28) on 2023-06-28, after the 2023-05-26 entry. The cycle builder looked up the settled label, which had no rows on the entry day, so the cycle was skipped.

**Fix.** `data.relabel` maps every label that NSE renamed mid-life to the label the contract finally settled under (same calendar month, the old label stops trading the day before the new one starts). On the entry day the target is therefore the next month's monthly contract as listed that day, and that same contract is followed (marks, stops, settlement) to its actual last trading day. Labels whose contract simply expired early for a holiday (Dec 2008, Apr 2009, Apr 2014) are not relabels and are unchanged.

**Relabels found (old -> settled label, last day of the old label):** 2014-02-27 -> 2014-02-26, 2018-03-29 -> 2018-03-28, 2023-03-30 -> 2023-03-29, 2023-06-29 -> 2023-06-28, 2025-09-25 -> 2025-09-30, 2025-12-24 -> 2025-12-30, 2026-03-26 -> 2026-03-30, 2026-03-31 -> 2026-03-30, 2026-06-25 -> 2026-06-30. Only the June 2023 one falls inside a held cycle (entry 2023-05-26); the others happen before the relevant entry (or affect only holdout contracts, which this recompute does not touch). The S9 far leg already used the month-based lookup.

**Recompute.** `python main.py bugfix-recompute` recomputes design and validation for every rule; results are in `*_bugfix.csv` next to the committed files; the logged validation and holdout runs were not re-run, and one line was appended to each validation log. Deflated Sharpe in the `_bugfix` summaries uses the other phases' committed trial Sharpe values for the trial variance.

## Per rule: the 2023-05-26 cycle and the rows around it

Max |diff| = largest change in monthly return (percentage points) before the cycle and after it (after it, units scale with the new capital and a Rs 20 brokerage is fixed, so tiny differences are expected). Decision changes after the cycle are allowed only where an expanding filter threshold now includes that cycle.

| phase | rule | period | 2023-05-26 cycle | max diff before | max diff after | decision changes after | status |
|---|---|---|---|---|---|---|---|
| phase1 | put_spread | dev | before: skipped (no valid P strike within 1% of 0.95 x S0), +0.623%; after:  traded, +0.758% | 0.0000 | 0.0000 | 0 | OK |
| phase1 | iron_condor | dev | before: skipped (no valid P strike within 1% of 0.95 x S0), +0.623%; after:  skipped, +0.623% | 0.0000 | 0.0000 | 0 | OK |
| phase1 | strangle | dev | before: skipped (no valid P strike within 1% of 0.95 x S0), +0.623%; after:  traded, +0.648% | 0.0000 | 0.0000 | 0 | OK |
| phase2 | d20_h1 | design | cycle not in period | 0.0000 | 0.0000 | 0 | OK |
| phase2 | d20_h1 | validation | before: skipped (no traded put at or beyond |delta| 0.20), +0.000%; after:  traded, +0.770% | 0.0049 | 0.0050 | 0 | OK |
| phase2 | d20_h2 | design | cycle not in period | 0.0000 | 0.0000 | 0 | OK |
| phase2 | d20_h2 | validation | before: skipped (no traded put at or beyond |delta| 0.20), +0.000%; after:  traded, +0.680% | 0.0050 | 0.0050 | 0 | OK |
| phase2 | d20_h3 | design | cycle not in period | 0.0000 | 0.0000 | 0 | OK |
| phase2 | d20_h3 | validation | before: skipped (no traded put at or beyond |delta| 0.20), +0.000%; after:  traded, +0.180% | 0.0049 | 0.0046 | 0 | OK |
| phase2 | d15_h1 | design | cycle not in period | 0.0000 | 0.0000 | 0 | OK |
| phase2 | d15_h1 | validation | before: skipped (no traded put at or beyond |delta| 0.15), +0.000%; after:  traded, +0.590% | 0.0048 | 0.0035 | 0 | OK |
| phase2 | d15_h2 | design | cycle not in period | 0.0000 | 0.0000 | 0 | OK |
| phase2 | d15_h2 | validation | before: skipped (no traded put at or beyond |delta| 0.15), +0.000%; after:  traded, +0.460% | 0.0049 | 0.0049 | 0 | OK |
| phase2 | d15_h3 | design | cycle not in period | 0.0000 | 0.0000 | 0 | OK |
| phase2 | d15_h3 | validation | before: skipped (no traded put at or beyond |delta| 0.15), +0.000%; after:  traded, +0.140% | 0.0050 | 0.0049 | 0 | OK |
| phase2 | ref_put_spread_p1skip | design | cycle not in period | 0.0000 | 0.0000 | 0 | OK |
| phase2 | ref_put_spread_p1skip | validation | before: skipped (no traded P strike near 0.95 x S0), +0.000%; after:  traded, +0.200% | 0.0050 | 0.0048 | 0 | OK |
| phase2 | ref_put_spread_fallback | design | cycle not in period | 0.0000 | 0.0000 | 0 | OK |
| phase2 | ref_put_spread_fallback | validation | before: skipped (no traded P strike near 0.95 x S0), +0.000%; after:  traded, +0.200% | 0.0050 | 0.0048 | 0 | OK |
| phase2 | ref_strangle_p1skip | design | cycle not in period | 0.0000 | 0.0000 | 0 | OK |
| phase2 | ref_strangle_p1skip | validation | before: skipped (no traded P strike near 0.95 x S0), +0.000%; after:  traded, +0.210% | 0.0048 | 0.0049 | 0 | OK |
| phase2 | ref_strangle_fallback | design | cycle not in period | 0.0000 | 0.0000 | 0 | OK |
| phase2 | ref_strangle_fallback | validation | before: skipped (no traded P strike near 0.95 x S0), +0.000%; after:  traded, +0.210% | 0.0048 | 0.0049 | 0 | OK |
| phase3 | base | design | cycle not in period | 0.0000 | 0.0000 | 0 | OK |
| phase3 | base | validation | before: skipped (no traded P strike near 0.95 x S0), +0.000%; after:  traded, +0.195% | 0.0000 | 0.0000 | 0 | OK |
| phase3 | e1 | design | cycle not in period | 0.0000 | 0.0000 | 0 | OK |
| phase3 | e1 | validation | before: skipped (no traded P strike near 0.95 x S0), +0.000%; after:  traded, +0.195% | 0.0000 | 0.0001 | 0 | OK |
| phase3 | f1 | design | cycle not in period | 0.0000 | 0.0000 | 0 | OK |
| phase3 | f1 | validation | before: skipped (no traded P strike near 0.95 x S0), +0.000%; after:  skipped, +0.000% | 0.0000 | 0.0000 | 0 | OK |
| phase3 | e1f1 | design | cycle not in period | 0.0000 | 0.0000 | 0 | OK |
| phase3 | e1f1 | validation | before: skipped (no traded P strike near 0.95 x S0), +0.000%; after:  skipped, +0.000% | 0.0000 | 0.0000 | 0 | OK |
| census | s1_short_put | design | cycle not in period | 0.0000 | 0.0000 | 0 | OK |
| census | s1_short_put | validation | before: skipped (no traded P strike near 0.95 x S0), +0.000%; after: S1 P 17550 @29 traded, +0.075% | 0.0000 | 0.0000 | 0 | OK |
| census | s1_short_put_e1 | design | cycle not in period | 0.0000 | 0.0000 | 0 | OK |
| census | s1_short_put_e1 | validation | before: skipped (no traded P strike near 0.95 x S0), +0.000%; after: S1 P 17550 @29 traded, +0.075% | 0.0000 | 0.0000 | 0 | OK |
| census | s2_short_call | design | cycle not in period | 0.0000 | 0.0000 | 0 | OK |
| census | s2_short_call | validation | before: skipped (no traded C strike near 1.05 x S0), +0.000%; after: S1 C 19400 @12 traded, +0.039% | 0.0000 | 0.0000 | 0 | OK |
| census | s2_short_call_e1 | design | cycle not in period | 0.0000 | 0.0000 | 0 | OK |
| census | s2_short_call_e1 | validation | before: skipped (no traded C strike near 1.05 x S0), +0.000%; after: S1 C 19400 @12 traded, +0.039% | 0.0000 | 0.0000 | 0 | OK |
| census | s3_short_straddle | design | cycle not in period | 0.0000 | 0.0000 | 0 | OK |
| census | s3_short_straddle | validation | before: skipped (no traded C strike near 1.00 x S0), +0.000%; after: S1 C 18500 @267.15; S1 P 18500 @194.45 traded, -0.063% | 0.0000 | 0.0001 | 0 | OK |
| census | s3_short_straddle_e1 | design | cycle not in period | 0.0000 | 0.0000 | 0 | OK |
| census | s3_short_straddle_e1 | validation | before: skipped (no traded C strike near 1.00 x S0), +0.000%; after: S1 C 18500 @267.15; S1 P 18500 @194.45 traded, -0.063% | 0.0000 | 0.0001 | 0 | OK |
| census | s4_short_strangle | design | cycle not in period | 0.0000 | 0.0000 | 0 | OK |
| census | s4_short_strangle | validation | before: skipped (no traded P strike near 0.95 x S0), +0.000%; after: S1 P 17550 @29; S1 C 19400 @12 traded, +0.105% | 0.0000 | 0.0000 | 0 | OK |
| census | s4_short_strangle_e1 | design | cycle not in period | 0.0000 | 0.0000 | 0 | OK |
| census | s4_short_strangle_e1 | validation | before: skipped (no traded P strike near 0.95 x S0), +0.000%; after: S1 P 17550 @29; S1 C 19400 @12 traded, +0.105% | 0.0000 | 0.0000 | 0 | OK |
| census | s5_bear_call_spread | design | cycle not in period | 0.0000 | 0.0000 | 0 | OK |
| census | s5_bear_call_spread | validation | before: skipped (no traded C strike near 1.05 x S0), +0.000%; after: S1 C 19400 @12; B1 C 21000 @3.3 traded, +0.043% | 0.0000 | 0.0000 | 0 | OK |
| census | s5_bear_call_spread_e1 | design | cycle not in period | 0.0000 | 0.0000 | 0 | OK |
| census | s5_bear_call_spread_e1 | validation | before: skipped (no traded C strike near 1.05 x S0), +0.000%; after: S1 C 19400 @12; B1 C 21000 @3.3 traded, +0.044% | 0.0000 | 0.0000 | 0 | OK |
| census | s6_iron_butterfly | design | cycle not in period | 0.0000 | 0.0000 | 0 | OK |
| census | s6_iron_butterfly | validation | before: skipped (no traded C strike near 1.00 x S0), +0.000%; after: S1 C 18500 @267.15; S1 P 18500 @194.45; B1 C 19400 @12; B1 P 17550 @29 traded, -0.554% | 0.0000 | 0.0001 | 0 | OK |
| census | s6_iron_butterfly_e1 | design | cycle not in period | 0.0000 | 0.0000 | 0 | OK |
| census | s6_iron_butterfly_e1 | validation | before: skipped (no traded C strike near 1.00 x S0), +0.000%; after: S1 C 18500 @267.15; S1 P 18500 @194.45; B1 C 19400 @12; B1 P 17550 @29 traded, -0.554% | 0.0000 | 0.0001 | 0 | OK |
| census | s7_cash_secured_put | design | cycle not in period | 0.0000 | 0.0000 | 0 | OK |
| census | s7_cash_secured_put | validation | before: skipped (no traded P strike near 0.95 x S0), +0.000%; after: S1 P 17550 @29 traded, +0.150% | 0.0000 | 0.0000 | 0 | OK |
| census | s7_cash_secured_put_e1 | design | cycle not in period | 0.0000 | 0.0000 | 0 | OK |
| census | s7_cash_secured_put_e1 | validation | before: skipped (no traded P strike near 0.95 x S0), +0.000%; after: S1 P 17550 @29 traded, +0.150% | 0.0000 | 0.0000 | 0 | OK |
| census | s8_put_ratio | design | cycle not in period | 0.0000 | 0.0000 | 0 | OK |
| census | s8_put_ratio | validation | before: skipped (no traded P strike near 0.95 x S0), +0.000%; after: B1 P 17550 @29; S2 P 16650 @10.1 traded, -0.061% | 0.0000 | 0.0001 | 0 | OK |
| census | s8_put_ratio_e1 | design | cycle not in period | 0.0000 | 0.0000 | 0 | OK |
| census | s8_put_ratio_e1 | validation | before: skipped (no traded P strike near 0.95 x S0), +0.000%; after: B1 P 17550 @29; S2 P 16650 @10.1 traded, -0.061% | 0.0000 | 0.0001 | 0 | OK |
| census | s9_calendar | design | cycle not in period | 0.0000 | 0.0000 | 0 | OK |
| census | s9_calendar | validation | before: skipped (no put strike traded in both near and far month), +0.000%; after: S1 P 18500 @194.45; B1 P 18500 @261.5 traded, -2.935% | 0.0000 | 0.0010 | 0 | OK |
| census | s10_covered_call | design | cycle not in period | 0.0000 | 0.0000 | 0 | OK |
| census | s10_covered_call | validation | before: skipped (no traded C strike near 1.05 x S0), +0.000%; after: S1 C 19400 @12 traded, +4.012% | 0.0000 | 0.0001 | 0 | OK |
| census | s11_collar | design | cycle not in period | 0.0000 | 0.0000 | 0 | OK |
| census | s11_collar | validation | before: skipped (no traded C strike near 1.05 x S0), +0.000%; after: S1 C 19400 @12; B1 P 17550 @29 traded, +3.848% | 0.0000 | 0.0001 | 0 | OK |
| census | s12_delta_hedged_straddle | design | cycle not in period | 0.0000 | 0.0000 | 0 | OK |
| census | s12_delta_hedged_straddle | validation | before: skipped (no traded C strike near 1.00 x S0), +0.000%; after: S1 C 18500 @267.15; S1 P 18500 @194.45 traded, +0.412% | 0.0000 | 0.0001 | 0 | OK |
| census | ref_base | design | cycle not in period | 0.0000 | 0.0000 | 0 | OK |
| census | ref_base | validation | before: skipped (no traded P strike near 0.95 x S0), +0.000%; after: S1 P 17550 @29; B1 P 16650 @10.1 traded, +0.195% | 0.0000 | 0.0000 | 0 | OK |
| census | ref_iron_condor | design | cycle not in period | 0.0000 | 0.0000 | 0 | OK |
| census | ref_iron_condor | validation | before: skipped (no traded P strike near 0.95 x S0), +0.000%; after: S1 P 17550 @29; B1 P 16650 @10.1; S1 C 19400 @12; B1 C 21000 @3.3 traded, +0.151% | 0.0000 | 0.0000 | 0 | OK |
| census | ref_strangle | design | cycle not in period | 0.0000 | 0.0000 | 0 | OK |
| census | ref_strangle | validation | before: skipped (no traded P strike near 0.95 x S0), +0.000%; after: S1 P 17550 @29; S1 C 19400 @12 traded, +0.210% | 0.0000 | 0.0001 | 0 | OK |
| census | ref_e1f1 | design | cycle not in period | 0.0000 | 0.0000 | 0 | OK | (e1f1 reference: decision changes come from its expanding filter threshold, checked in phase3)
| census | ref_e1f1 | validation | before: skipped (no traded P strike near 0.95 x S0), +0.000%; after:  skipped, +0.000% | 0.0000 | 0.0000 | 0 | OK | (e1f1 reference: decision changes come from its expanding filter threshold, checked in phase3)
| phase4 | ref_base | design | cycle not in period | 0.0000 | 0.0000 | 0 | OK |
| phase4 | ref_base | validation | before: skipped (no traded P strike near 0.95 x S0), +0.000%; after:  traded, +0.195% | 0.0000 | 0.0000 | 0 | OK |
| phase4 | ref_s7_e1 | design | cycle not in period | 0.0000 | 0.0000 | 0 | OK |
| phase4 | ref_s7_e1 | validation | before: skipped (no traded P strike near 0.95 x S0), +0.000%; after:  traded, +0.150% | 0.0000 | 0.0000 | 0 | OK |
| phase4 | p1 | design | cycle not in period | 0.0000 | 0.0000 | 0 | OK |
| phase4 | p1 | validation | before: skipped (no traded P strike near 0.95 x S0), +0.000%; after:  skipped, +0.000% | 0.0000 | 0.0000 | 0 | OK |
| phase4 | p2 | design | cycle not in period | 0.0000 | 0.0000 | 0 | OK |
| phase4 | p2 | validation | before: skipped (no traded P strike near 0.95 x S0), +0.000%; after:  traded, +0.195% | 0.0000 | 0.0001 | 0 | OK |
| phase4 | p3 | design | cycle not in period | 0.0000 | 0.0000 | 0 | OK |
| phase4 | p3 | validation | before: skipped (no traded P strike near 0.95 x S0), +0.000%; after:  skipped, +0.000% | 0.0000 | 0.0000 | 0 | OK |
| phase4 | sens_p3_0.10 | design | cycle not in period | 0.0000 | 0.0000 | 0 | OK |
| phase4 | sens_p3_0.10 | validation | before: skipped (no traded P strike near 0.95 x S0), +0.000%; after:  skipped, +0.000% | 0.0000 | 0.0000 | 0 | OK |
| phase4 | sens_p3_0.15 | design | cycle not in period | 0.0000 | 0.0000 | 0 | OK |
| phase4 | sens_p3_0.15 | validation | before: skipped (no traded P strike near 0.95 x S0), +0.000%; after:  skipped, +0.000% | 0.0000 | 0.0000 | 0 | OK |
| phase4 | ref_e1f1 | design | cycle not in period | 0.0000 | 0.0000 | 0 | OK | (e1f1: see phase3)
| phase4 | ref_e1f1 | validation | before: skipped (no traded P strike near 0.95 x S0), +0.000%; after:  skipped, +0.000% | 0.0000 | 0.0000 | 0 | OK | (e1f1: see phase3)

**Unexpected changes: 0**

## Summary rows: old -> new (fields that changed)

| phase | rule | changes |
|---|---|---|
| phase1 dev | put_spread | CAGR: 0.0851 -> 0.0852; Sharpe: 0.2991 -> 0.3002 |
| phase1 dev | iron_condor | unchanged |
| phase1 dev | strangle | CAGR: 0.0597 -> 0.0597; Sharpe: -0.0001 -> 0.0001 |
| phase1 dev | TRI | unchanged |
| phase1 dev | Cash 6.5% | unchanged |
| phase2 design | d20_h1 | unchanged |
| phase2 design | d20_h2 | unchanged |
| phase2 design | d20_h3 | unchanged |
| phase2 design | d15_h1 | unchanged |
| phase2 design | d15_h2 | unchanged |
| phase2 design | d15_h3 | unchanged |
| phase2 design | ref_put_spread_p1skip | unchanged |
| phase2 design | ref_put_spread_fallback | unchanged |
| phase2 design | ref_strangle_p1skip | unchanged |
| phase2 design | ref_strangle_fallback | unchanged |
| phase2 validation | d20_h1 | option CAGR: 0.0315 -> 0.0329; option Sharpe: 0.4662 -> 0.4846; win rate: 0.9104 -> 0.9118; skipped: 2.0000 -> 1.0000; DSR: 0.5450 -> 0.5538 |
| phase2 validation | d20_h2 | option CAGR: 0.0343 -> 0.0356; option Sharpe: 0.5104 -> 0.5270; win rate: 0.8955 -> 0.8971; skipped: 2.0000 -> 1.0000; DSR: 0.5758 -> 0.5828 |
| phase2 validation | d20_h3 | option CAGR: 0.0170 -> 0.0173; option Sharpe: 0.3757 -> 0.3824; win rate: 0.9118 -> 0.9130; skipped: 1.0000 -> 0.0000; DSR: 0.4763 -> 0.4772 |
| phase2 validation | d15_h1 | option CAGR: 0.0252 -> 0.0263; option Sharpe: 0.4060 -> 0.4214; win rate: 0.9254 -> 0.9265; skipped: 2.0000 -> 1.0000; DSR: 0.5005 -> 0.5075 |
| phase2 validation | d15_h2 | option CAGR: 0.0259 -> 0.0267; option Sharpe: 0.4665 -> 0.4800; win rate: 0.9254 -> 0.9265; skipped: 2.0000 -> 1.0000; DSR: 0.5431 -> 0.5482 |
| phase2 validation | d15_h3 | option CAGR: 0.0336 -> 0.0338; option Sharpe: 0.4194 -> 0.4221; win rate: 0.9265 -> 0.9275; skipped: 1.0000 -> 0.0000; DSR: 0.5180 -> 0.5142 |
| phase2 validation | ref_put_spread_p1skip | option CAGR: 0.0383 -> 0.0386; option Sharpe: 0.6969 -> 0.7031; win rate: 0.9375 -> 0.9385; skipped: 5.0000 -> 4.0000; DSR: 0.6797 -> 0.6794 |
| phase2 validation | ref_put_spread_fallback | option CAGR: 0.0398 -> 0.0402; option Sharpe: 0.7242 -> 0.7304; win rate: 0.9394 -> 0.9403; skipped: 3.0000 -> 2.0000; DSR: 0.6926 -> 0.6922 |
| phase2 validation | ref_strangle_p1skip | option CAGR: -0.0027 -> -0.0023; option Sharpe: 0.0113 -> 0.0157; win rate: 0.8088 -> 0.8116; skipped: 1.0000 -> 0.0000; DSR: 0.1761 -> 0.1761 |
| phase2 validation | ref_strangle_fallback | option CAGR: -0.0027 -> -0.0023; option Sharpe: 0.0113 -> 0.0157; win rate: 0.8088 -> 0.8116; skipped: 1.0000 -> 0.0000; DSR: 0.1761 -> 0.1761 |
| phase3 design | base | unchanged |
| phase3 design | e1 | unchanged |
| phase3 design | f1 | unchanged |
| phase3 design | e1f1 | unchanged |
| phase3 validation | base | option CAGR: 0.0398 -> 0.0402; option Sharpe: 0.7242 -> 0.7304; win rate: 0.9394 -> 0.9403; months traded: 66.0000 -> 67.0000; DSR: 0.5086 -> 0.5116 |
| phase3 validation | e1 | option CAGR: 0.0421 -> 0.0424; option Sharpe: 1.1215 -> 1.1313; win rate: 0.8636 -> 0.8657; months traded: 66.0000 -> 67.0000; DSR: 0.7679 -> 0.7716 |
| phase3 validation | f1 | months filtered: 33.0000 -> 34.0000; DSR: 0.7728 -> 0.7722 |
| phase3 validation | e1f1 | months filtered: 33.0000 -> 34.0000; DSR: 0.7216 -> 0.7209 |
| census design | s1_short_put | DSR: 0.0259 -> 0.0223 |
| census design | s1_short_put_e1 | DSR: 0.2653 -> 0.2456 |
| census design | s2_short_call | DSR: 0.0006 -> 0.0005 |
| census design | s2_short_call_e1 | DSR: 0.0000 -> 0.0000 |
| census design | s3_short_straddle | DSR: 0.0003 -> 0.0002 |
| census design | s3_short_straddle_e1 | DSR: 0.0002 -> 0.0001 |
| census design | s4_short_strangle | DSR: 0.0131 -> 0.0108 |
| census design | s4_short_strangle_e1 | DSR: 0.0182 -> 0.0147 |
| census design | s5_bear_call_spread | DSR: 0.0000 -> 0.0000 |
| census design | s5_bear_call_spread_e1 | DSR: 0.0000 -> 0.0000 |
| census design | s6_iron_butterfly | unchanged |
| census design | s6_iron_butterfly_e1 | unchanged |
| census design | s7_cash_secured_put | DSR: 0.0223 -> 0.0191 |
| census design | s7_cash_secured_put_e1 | DSR: 0.2642 -> 0.2450 |
| census design | s8_put_ratio | DSR: 0.0172 -> 0.0131 |
| census design | s8_put_ratio_e1 | DSR: 0.0038 -> 0.0028 |
| census design | s9_calendar | unchanged |
| census design | s10_covered_call | DSR: 0.0655 -> 0.0565 |
| census design | s11_collar | DSR: 0.0346 -> 0.0288 |
| census design | s12_delta_hedged_straddle | DSR: 0.0097 -> 0.0079 |
| census design | ref_base | DSR: 0.0149 -> 0.0124 |
| census design | ref_iron_condor | DSR: 0.0002 -> 0.0001 |
| census design | ref_strangle | DSR: 0.0109 -> 0.0089 |
| census design | ref_e1f1 | DSR: 0.1677 -> 0.1499 |
| census validation | s1_short_put | option CAGR: 0.0133 -> 0.0135; option Sharpe: 0.3317 -> 0.3348; win rate: 0.9559 -> 0.9565; months traded: 68.0000 -> 69.0000; DSR: 0.0327 -> 0.0330 |
| census validation | s1_short_put_e1 | option CAGR: 0.0217 -> 0.0218; option Sharpe: 1.0199 -> 1.0265; win rate: 0.8824 -> 0.8841; months traded: 68.0000 -> 69.0000; DSR: 0.1665 -> 0.1695 |
| census validation | s2_short_call | option CAGR: -0.0181 -> -0.0181; option Sharpe: -0.5591 -> -0.5569; win rate: 0.7794 -> 0.7826; months traded: 68.0000 -> 69.0000 |
| census validation | s2_short_call_e1 | option CAGR: -0.0183 -> -0.0182; option Sharpe: -0.6568 -> -0.6543; win rate: 0.6765 -> 0.6812; months traded: 68.0000 -> 69.0000 |
| census validation | s3_short_straddle | option CAGR: -0.0075 -> -0.0076; option Sharpe: -0.1068 -> -0.1088; win rate: 0.6029 -> 0.5942; months traded: 68.0000 -> 69.0000; DSR: 0.0002 -> 0.0002 |
| census validation | s3_short_straddle_e1 | option CAGR: 0.0016 -> 0.0015; option Sharpe: 0.0573 -> 0.0549; win rate: 0.6029 -> 0.5942; months traded: 68.0000 -> 69.0000; DSR: 0.0014 -> 0.0013 |
| census validation | s4_short_strangle | option CAGR: 0.0015 -> 0.0017; option Sharpe: 0.0562 -> 0.0603; win rate: 0.8088 -> 0.8116; months traded: 68.0000 -> 69.0000; DSR: 0.0019 -> 0.0020 |
| census validation | s4_short_strangle_e1 | option CAGR: 0.0098 -> 0.0100; option Sharpe: 0.3512 -> 0.3575; win rate: 0.7647 -> 0.7681; months traded: 68.0000 -> 69.0000; DSR: 0.0172 -> 0.0176 |
| census validation | s5_bear_call_spread | option CAGR: -0.0595 -> -0.0594; option Sharpe: -0.6865 -> -0.6856; win rate: 0.7500 -> 0.7541; months traded: 60.0000 -> 61.0000 |
| census validation | s5_bear_call_spread_e1 | option CAGR: -0.0452 -> -0.0451; option Sharpe: -0.6776 -> -0.6764; win rate: 0.6500 -> 0.6557; months traded: 60.0000 -> 61.0000 |
| census validation | s6_iron_butterfly | option CAGR: -0.0395 -> -0.0404; option Sharpe: -0.4225 -> -0.4337; worst month: -0.0458 -> -0.0458; CVaR99: -0.0458 -> -0.0458; win rate: 0.5000 -> 0.4928; months traded: 68.0000 -> 69.0000; DSR: 0.0000 -> 0.0000 |
| census validation | s6_iron_butterfly_e1 | option CAGR: -0.0395 -> -0.0404; option Sharpe: -0.4225 -> -0.4337; worst month: -0.0458 -> -0.0458; CVaR99: -0.0458 -> -0.0458; win rate: 0.5000 -> 0.4928; months traded: 68.0000 -> 69.0000; DSR: 0.0000 -> 0.0000 |
| census validation | s7_cash_secured_put | option CAGR: 0.0205 -> 0.0208; option Sharpe: 0.3004 -> 0.3038; win rate: 0.9559 -> 0.9565; months traded: 68.0000 -> 69.0000; DSR: 0.0296 -> 0.0299 |
| census validation | s7_cash_secured_put_e1 | option CAGR: 0.0382 -> 0.0385; option Sharpe: 1.1081 -> 1.1163; win rate: 0.8824 -> 0.8841; months traded: 68.0000 -> 69.0000; DSR: 0.2895 -> 0.2944 |
| census validation | s8_put_ratio | option CAGR: -0.0205 -> -0.0206; option Sharpe: -0.4998 -> -0.5025; win rate: 0.0758 -> 0.0746; months traded: 66.0000 -> 67.0000; DSR: 0.0000 -> 0.0000 |
| census validation | s8_put_ratio_e1 | option CAGR: -0.0206 -> -0.0207; option Sharpe: -0.5028 -> -0.5055; win rate: 0.0606 -> 0.0597; months traded: 66.0000 -> 67.0000; DSR: 0.0000 -> 0.0000 |
| census validation | s9_calendar | option CAGR: -0.2614 -> -0.2652; option Sharpe: -0.8543 -> -0.8720; win rate: 0.3676 -> 0.3623; months traded: 68.0000 -> 69.0000; DSR: 0.0000 -> 0.0000 |
| census validation | s10_covered_call | option CAGR: 0.1328 -> 0.1406; option Sharpe: 0.8921 -> 0.9350; win rate: 0.6324 -> 0.6377; months traded: 68.0000 -> 69.0000; DSR: 0.2233 -> 0.2484 |
| census validation | s11_collar | option CAGR: 0.1082 -> 0.1155; option Sharpe: 0.9619 -> 1.0155; win rate: 0.6029 -> 0.6087; months traded: 68.0000 -> 69.0000; DSR: 0.2097 -> 0.2463 |
| census validation | s12_delta_hedged_straddle | option CAGR: 0.0160 -> 0.0167; option Sharpe: 0.3234 -> 0.3368; win rate: 0.6176 -> 0.6232; months traded: 68.0000 -> 69.0000; DSR: 0.0158 -> 0.0171 |
| census validation | ref_base | option CAGR: 0.0398 -> 0.0402; option Sharpe: 0.7242 -> 0.7304; win rate: 0.9394 -> 0.9403; months traded: 66.0000 -> 67.0000; DSR: 0.1761 -> 0.1781 |
| census validation | ref_iron_condor | option CAGR: -0.0241 -> -0.0238; option Sharpe: -0.1849 -> -0.1823; win rate: 0.7586 -> 0.7627; months traded: 58.0000 -> 59.0000; DSR: 0.0001 -> 0.0001 |
| census validation | ref_strangle | option CAGR: -0.0027 -> -0.0023; option Sharpe: 0.0113 -> 0.0157; win rate: 0.8088 -> 0.8116; months traded: 68.0000 -> 69.0000; DSR: 0.0010 -> 0.0010 |
| census validation | ref_e1f1 | DSR: 0.3732 -> 0.3712 |
| phase4 design normal | ref_base | unchanged |
| phase4 design normal | ref_e1f1 | unchanged |
| phase4 design normal | ref_s7_e1 | unchanged |
| phase4 design normal | p1 | unchanged |
| phase4 design normal | p2 | unchanged |
| phase4 design normal | p3 | unchanged |
| phase4 design stress | ref_base | unchanged |
| phase4 design stress | ref_e1f1 | unchanged |
| phase4 design stress | ref_s7_e1 | unchanged |
| phase4 design stress | p1 | unchanged |
| phase4 design stress | p2 | unchanged |
| phase4 design stress | p3 | unchanged |
| phase4 validation normal | ref_base | option CAGR: 0.0398 -> 0.0402; Sharpe all months: 0.7242 -> 0.7304; months traded: 66.0000 -> 67.0000; DSR: 0.1308 -> 0.1335 |
| phase4 validation normal | ref_e1f1 | DSR: 0.3059 -> 0.3054 |
| phase4 validation normal | ref_s7_e1 | option CAGR: 0.0382 -> 0.0385; Sharpe all months: 1.1081 -> 1.1163; months traded: 68.0000 -> 69.0000; DSR: 0.1877 -> 0.1935 |
| phase4 validation normal | p1 | DSR: 0.4180 -> 0.4163 |
| phase4 validation normal | p2 | option CAGR: 0.0446 -> 0.0450; Sharpe all months: 1.2366 -> 1.2470; months traded: 66.0000 -> 67.0000; DSR: 0.3734 -> 0.3798 |
| phase4 validation normal | p3 | DSR: 0.2828 -> 0.2813 |
| phase4 validation stress | ref_base | option CAGR: 0.0350 -> 0.0354; Sharpe all months: 0.6529 -> 0.6592; months traded: 66.0000 -> 67.0000 |
| phase4 validation stress | ref_e1f1 | unchanged |
| phase4 validation stress | ref_s7_e1 | option CAGR: 0.0362 -> 0.0365; Sharpe all months: 1.0612 -> 1.0695; months traded: 68.0000 -> 69.0000 |
| phase4 validation stress | p1 | unchanged |
| phase4 validation stress | p2 | option CAGR: 0.0383 -> 0.0386; Sharpe all months: 1.0493 -> 1.0592; months traded: 66.0000 -> 67.0000 |
| phase4 validation stress | p3 | unchanged |
