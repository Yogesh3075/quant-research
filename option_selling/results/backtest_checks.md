# Backtest checks

- payoff put_spread 2018-02-23: legs ['S P 9950', 'B P 9400'], S = 10113.70, by hand 0.00 per unit = code 0.00: OK
- payoff iron_condor 2018-02-23: legs ['S P 9950', 'B P 9400', 'S C 11000', 'B C 11600'], S = 10113.70, by hand 0.00 per unit = code 0.00: OK
- payoff strangle 2018-02-23: legs ['S P 9950', 'S C 11000'], S = 10113.70, by hand 0.00 per unit = code 0.00: OK
- payoff put_spread 2016-05-27: legs ['S P 7750', 'B P 7300'], S = 8287.75, by hand 0.00 per unit = code 0.00: OK
- payoff iron_condor 2016-05-27: legs ['S P 7750', 'B P 7300', 'S C 8550', 'B C 9000'], S = 8287.75, by hand 0.00 per unit = code 0.00: OK
- payoff strangle 2016-05-27: legs ['S P 7750', 'S C 8550'], S = 8287.75, by hand 0.00 per unit = code 0.00: OK
- payoff put_spread 2021-03-26: legs ['S P 13800', 'B P 13050'], S = 14894.90, by hand 0.00 per unit = code 0.00: OK
- payoff iron_condor 2021-03-26: legs ['S P 13800', 'B P 13050', 'S C 15250', 'B C 15950'], S = 14894.90, by hand 0.00 per unit = code 0.00: OK
- payoff strangle 2021-03-26: legs ['S P 13800', 'S C 15250'], S = 14894.90, by hand 0.00 per unit = code 0.00: OK
- no look-ahead: strike choice uses only the entry-day chain (asserted for 201 cycles); S0 = index close on entry day; units use capital before the trade; settlement used only for payoff.
- holdout isolation: development = 201 cycles to expiry 2024-10-31; holdout = 24 cycles from entry 2024-11-01; no development trade uses a holdout month; holdout runs logged so far: 0.
- max loss put_spread: worst trading loss 10.00% of capital (plan 10%); worst net month incl. costs 9.58%: OK
- max loss iron_condor: worst trading loss 10.00% of capital (plan 10%); worst net month incl. costs 9.67%: OK
