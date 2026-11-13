# Data check

Run on 2026-11-05. Source: niftyindices.com, Total Returns Index (daily).
Calendar for missing days and month-ends: nifty50 trading days.

## Daily series

| index | first | last | days | missing vs cal | longest gap | extra vs cal | duplicates | clashes | non-positive | moves >10% | days stale |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| momentum | 2005-04-01 | 2026-11-05 | 5357 | 0 | 0 | 0 | 0 | 0 | 0 | 3 | 0 |
| quality | 2005-04-01 | 2026-11-05 | 5357 | 0 | 0 | 0 | 0 | 0 | 0 | 2 | 0 |
| value | 2005-04-01 | 2026-11-05 | 5357 | 0 | 0 | 0 | 0 | 0 | 0 | 4 | 0 |
| lowvol | 2005-04-01 | 2026-11-05 | 5357 | 0 | 0 | 0 | 0 | 0 | 0 | 2 | 0 |
| alpha | 2005-04-01 | 2026-11-05 | 5357 | 0 | 0 | 0 | 0 | 0 | 0 | 8 | 0 |
| nifty200 | 2005-04-01 | 2026-11-05 | 5357 | 0 | 0 | 0 | 0 | 0 | 0 | 4 | 0 |
| nifty50 | 2005-04-01 | 2026-11-05 | 5357 | 0 | 0 | 0 | 0 | 0 | 0 | 3 | 0 |

Missing and longest gap (in calendar trading days) count only within each index's own first and last date. Extra: days the index has but the calendar does not. Duplicates: repeated dates in the raw responses (identical repeats are kept once). Clashes: one date with two different values (both dropped).

## Daily moves larger than 10%

| index | date | return % |
| --- | --- | --- |
| momentum | 2008-01-21 | -14.01 |
| momentum | 2009-05-18 | 12.56 |
| momentum | 2020-03-23 | -12.78 |
| quality | 2009-05-18 | 13.77 |
| quality | 2020-03-23 | -10.30 |
| value | 2008-01-21 | -12.86 |
| value | 2009-05-18 | 15.62 |
| value | 2015-08-24 | -10.28 |
| value | 2024-06-04 | -13.15 |
| lowvol | 2009-05-18 | 13.41 |
| lowvol | 2020-03-23 | -10.37 |
| alpha | 2008-01-21 | -17.30 |
| alpha | 2008-01-22 | -10.02 |
| alpha | 2008-01-23 | 11.52 |
| alpha | 2008-01-25 | 10.97 |
| alpha | 2008-10-24 | -10.41 |
| alpha | 2009-05-18 | 13.61 |
| alpha | 2020-03-23 | -13.36 |
| alpha | 2024-06-04 | -11.95 |
| nifty200 | 2008-01-21 | -10.32 |
| nifty200 | 2008-10-24 | -11.27 |
| nifty200 | 2009-05-18 | 16.75 |
| nifty200 | 2020-03-23 | -12.78 |
| nifty50 | 2008-10-24 | -12.20 |
| nifty50 | 2009-05-18 | 17.74 |
| nifty50 | 2020-03-23 | -12.91 |

## Monthly series

259 month-ends from 2005-04-29 to 2026-10-30 (last NIFTY 50 trading day of each month; an unfinished running month is left out).

| index | months | first month-end | empty months before start | empty months after start |
| --- | --- | --- | --- | --- |
| momentum | 259 | 2005-04-29 | 0 | 0 |
| quality | 259 | 2005-04-29 | 0 | 0 |
| value | 259 | 2005-04-29 | 0 | 0 |
| lowvol | 259 | 2005-04-29 | 0 | 0 |
| alpha | 259 | 2005-04-29 | 0 | 0 |
| nifty200 | 259 | 2005-04-29 | 0 | 0 |
| nifty50 | 259 | 2005-04-29 | 0 | 0 |

Correlation of monthly returns, factor indices:

|  | momentum | quality | value | lowvol | alpha |
| --- | --- | --- | --- | --- | --- |
| momentum | 1.00 | 0.86 | 0.75 | 0.86 | 0.97 |
| quality | 0.86 | 1.00 | 0.76 | 0.94 | 0.88 |
| value | 0.75 | 0.76 | 1.00 | 0.79 | 0.77 |
| lowvol | 0.86 | 0.94 | 0.79 | 1.00 | 0.87 |
| alpha | 0.97 | 0.88 | 0.77 | 0.87 | 1.00 |

Pairs above 0.9: momentum/alpha 0.97, quality/lowvol 0.94

## Sanity check against NSE Index Dashboard (to 2026-06-30)

Ours: from TRI at the last trading day on or before each date. 1y absolute, 3y and 5y CAGR, in %. If the dashboard showed price returns, ours would be higher by about the dividend yield; flag if any gap is above 3.0 pp a year.

| index | 1y ours | 1y NSE | 3y ours | 3y NSE | 5y ours | 5y NSE | max diff pp | flag |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| momentum | -2.54 | -2.54 | 14.09 | 14.09 | 12.61 | 12.61 | 0.00 |  |
| quality | -5.46 | -5.46 | 9.44 | 9.44 | 9.62 | 9.62 | 0.00 |  |
| value | 15.39 | 15.39 | 30.35 | 30.35 | 27.55 | 27.55 | 0.00 |  |
| lowvol | -1.23 | -1.23 | 11.95 | 11.95 | 11.40 | 11.40 | 0.00 |  |
| alpha | 1.73 | 1.73 | 20.07 | 20.07 | 17.85 | 17.85 | 0.00 |  |

## Launch dates

History before each index's launch date is back-calculated by NSE, not live.

| index | launch date |
| --- | --- |
| momentum | 25 Aug 2020 |
| quality | 17 Apr 2018 |
| lowvol | 08 Jul 2016 |
| value | check factsheet |
| alpha | check factsheet |
