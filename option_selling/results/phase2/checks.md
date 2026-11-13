# Phase 2 checks

- split: design 132 cycles (entry to 2018-12-28), validation 69 cycles (from 2019-02-01); no holdout cycle loaded and no option data after 2024-10-31; validation runs logged: 1.
- delta 2013-04-01 K 4700: price 0.65, IV code 0.299726 / hand 0.299726, delta code -0.004619 / hand -0.004619: OK
- delta 2013-04-01 K 5100: price 1.85, IV code 0.213300 / hand 0.213300, delta code -0.016264 / hand -0.016264: OK
- delta 2013-04-01 K 5000: price 1.15, IV code 0.229367 / hand 0.229367, delta code -0.009936 / hand -0.009936: OK
- d20_h1: payoff by hand OK for 3 cycles; worst trading loss 10.00% of capital
- d20_h2: payoff by hand OK for 3 cycles; worst trading loss 10.00% of capital
- d20_h3: payoff by hand OK for 3 cycles; worst trading loss 3.14% of capital; loss at 0.75 x S0 = 10.00% exactly; max margin 21.6%
- d15_h1: payoff by hand OK for 3 cycles; worst trading loss 10.00% of capital
- d15_h2: payoff by hand OK for 3 cycles; worst trading loss 10.00% of capital
- d15_h3: payoff by hand OK for 3 cycles; worst trading loss 3.14% of capital; loss at 0.75 x S0 = 10.00% exactly; max margin 60.4%
- ref_put_spread_p1skip: payoff by hand OK for 3 cycles; worst trading loss 10.00% of capital
- ref_put_spread_fallback: payoff by hand OK for 3 cycles; worst trading loss 10.00% of capital
- ref_strangle_p1skip: payoff by hand OK for 3 cycles; worst trading loss 22.92% of capital
- ref_strangle_fallback: payoff by hand OK for 3 cycles; worst trading loss 22.92% of capital
- no look-ahead: chains, IV, delta and sizing use only the entry-day bhavcopy and the entry-day index close (chain() asserts date == entry); settlement is used only for payoff and marking only for diagnostics.
- Phase 1 put_spread reproduced with the Phase 2 engine and Phase 1 skip rule over 201 cycles: max capital gap Rs 0.00e+00
- Phase 1 iron_condor reproduced with the Phase 2 engine and Phase 1 skip rule over 201 cycles: max capital gap Rs 9.31e-10
- Phase 1 strangle reproduced with the Phase 2 engine and Phase 1 skip rule over 201 cycles: max capital gap Rs 0.00e+00
