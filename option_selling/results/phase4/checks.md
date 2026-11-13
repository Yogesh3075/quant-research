# Phase 4 checks

- in-sample runs load no option data after 2024-10-31; holdout runs logged: 1.
- no rule input reads `iv_minus_future_rv_pts` or the after-entry realised vol: in the rule code they appear only as output columns; the e1f1 filter uses ATM IV at entry and the trailing 21-day RV.
- prem_ratio 2014-10-31: (15.45 - 4.4) / (7900 - 7500) = 0.0276 = code 0.0276
- prem_ratio 2015-07-31: (18.85 - 4.05) / (8100 - 7700) = 0.0370 = code 0.0370
- prem_ratio 2018-04-02: (26.8 - 6.55) / (9700 - 9200) = 0.0405 = code 0.0405
- index stop 2008-03-28: short strike 4700; closes 04-02 4754, 04-03 4772, 04-04 4647, 04-07 4761; first close below on 2008-04-04; exit 2008-04-07 = next trading day close: OK
- index stop 2016-01-01: short strike 7550; closes 01-08 7601, 01-11 7564, 01-12 7510, 01-13 7562; first close below on 2016-01-12; exit 2016-01-13 = next trading day close: OK
- index stop 2008-02-29: short strike 4950; closes 02-29 5224, 03-03 4953, 03-04 4864, 03-05 4921; first close below on 2008-03-04; exit 2008-03-05 = next trading day close: OK
- ref_base reproduces committed ref_put_spread_fallback (design): max capital gap Rs 0.0049
- ref_e1f1 reproduces committed e1f1 (design): max capital gap Rs 0.0000
- ref_s7_e1 reproduces committed s7_cash_secured_put_e1 (design): max capital gap Rs 0.0000
- ref_base reproduces committed ref_put_spread_fallback (validation): max capital gap Rs 0.0000
- ref_e1f1 reproduces committed e1f1 (validation): max capital gap Rs 0.0000
- ref_s7_e1 reproduces committed s7_cash_secured_put_e1 (validation): max capital gap Rs 0.0000
- credit_gross - slippage - payout - charges + interest = total_pnl: max gap Rs 0.000000 -> PASS
- capital_end = capital_start + total_pnl: max gap Rs 0.000000 -> PASS
- charge items sum to total_charges: max gap Rs 0.000000 -> PASS
- capital_start = previous capital_end: max gap Rs 0.000000 -> PASS
