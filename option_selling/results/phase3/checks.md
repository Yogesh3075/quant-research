# Phase 3 checks

- split: design 132 cycles; filter gaps computed only for design entries; no holdout cycle loaded, no option data after 2024-10-31; validation runs logged: 1.
- filter 2011-04-01: IV 0.1878, RV21 0.1709, gap 0.0169 (code 0.0169); threshold = median of 38 earlier gaps (entries 2008-02 to 2011-02-25, all before entry) = 0.0295 (code 0.0295): OK
- filter 2012-01-27: IV 0.1980, RV21 0.1709, gap 0.0271 (code 0.0271); threshold = median of 48 earlier gaps (entries 2008-02 to 2011-12-30, all before entry) = 0.0264 (code 0.0264): OK
- filter 2017-04-28: IV 0.0967, RV21 0.0779, gap 0.0188 (code 0.0188); threshold = median of 111 earlier gaps (entries 2008-02 to 2017-03-31, all before entry) = 0.0162 (code 0.0162): OK
- credit_gross - slippage - payout - charges + interest = total_pnl: max gap Rs 0.000000 -> PASS
- capital_end = capital_start + total_pnl: max gap Rs 0.000000 -> PASS
- charge items sum to total_charges: max gap Rs 0.000000 -> PASS
- capital_start = previous capital_end: max gap Rs 0.000000 -> PASS
- stop e1 2015-07-31: by-hand trigger 2015-08-24 (loss >= 2 x credit Rs 8,420) = code 2015-08-24; exit 2015-08-25 = next trading day after the trigger: OK
- stop e1 2015-05-29: by-hand trigger 2015-06-03 (loss >= 2 x credit Rs 14,600) = code 2015-06-03; exit 2015-06-04 = next trading day after the trigger: OK
- stop e1 2013-05-31: by-hand trigger 2013-06-13 (loss >= 2 x credit Rs 12,126) = code 2013-06-13; exit 2013-06-14 = next trading day after the trigger: OK
- base reproduces Phase 2 ref_put_spread_fallback on design: max capital gap Rs 0.0049
- base reproduces Phase 2 ref_put_spread_fallback on validation (stored rows): max capital gap Rs 0.0000
