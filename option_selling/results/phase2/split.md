# Phase 2 data split (written and committed before any Phase 2 run)

| part | rule | cycles | entries | last expiry |
|---|---|---|---|---|
| Design | entry 2008-01 to 2018-12 | 132 | 2008-02-01 to 2018-12-28 | 2019-01-31 |
| Validation | entry from 2019-01, expiry up to 2024-10-31 (last Phase 1 development cycle) | 69 | 2019-02-01 to 2024-09-27 | 2024-10-31 |
| Holdout | expiry after 2024-10-31 | 24 | not loaded in Phase 2 | |

- All comparisons and the choice of rule use design cycles only.
- Validation runs once, after the choice is frozen and committed, logged in `results/phase2/validation_runs.log`. **Validation; aggregate results for this period were seen in Phase 1, so not a clean test.**
- The Phase 1 holdout (Nov 2024 onward) is not used in this phase: those cycles are dropped and option data after 2024-10-31 is cut before any Phase 2 computation.
- Each part is run separately from Rs 10,00,000.
- Trials: Phase 1 had 3 (put spread, iron condor, short strangle). Phase 2 adds 6 (short put |delta| 0.20 / 0.15 x hedge H1 / H2 / H3): cumulative 9. Reference lines (Phase 1 put spread and strangle with the Phase 1 skip rule and with the fallback rule) are not new trials.
