# Effect of the Phase 3 data-rule fixes

Development period only; holdout locked. Before = Phase 2 as committed; after = the same code with the fixes below.

## Headline diagnostics

| measure | before | after | change |
|---|---|---|---|
| IC score (mean) | 0.0441 | 0.0442 | 0.0001 |
| IC score (t) | 3.0775 | 3.0779 | 0.0004 |
| IC z_12_1 (mean) | 0.0516 | 0.0518 | 0.0002 |
| IC z_12_1 (t) | 3.2574 | 3.2644 | 0.007 |
| IC z_6_1 (mean) | 0.0339 | 0.0339 | -0.0 |
| IC z_6_1 (t) | 2.6363 | 2.6298 | -0.0065 |
| Q5 top minus bottom (mean) | 0.0116 | 0.0115 | -0.0001 |
| Q5 top minus bottom (t) | 2.5914 | 2.5539 | -0.0374 |
| Q5 top minus universe (mean) | 0.0065 | 0.0065 | -0.0 |
| Q5 top minus universe (t) | 3.3671 | 3.3429 | -0.0242 |
| IC decay t+1 (mean) | 0.0441 | 0.0442 | 0.0001 |
| IC decay t+1 (t) | 3.0775 | 3.0779 | 0.0004 |
| IC decay t+2 (mean) | 0.0521 | 0.0524 | 0.0003 |
| IC decay t+2 (t) | 3.8497 | 3.8621 | 0.0124 |
| IC decay t+3 (mean) | 0.0549 | 0.0552 | 0.0003 |
| IC decay t+3 (t) | 3.8742 | 3.8861 | 0.0119 |
| IC decay t+6 (mean) | 0.0427 | 0.0432 | 0.0005 |
| IC decay t+6 (t) | 2.5365 | 2.5558 | 0.0193 |
| IC decay t+12 (mean) | 0.0064 | 0.0072 | 0.0008 |
| IC decay t+12 (t) | 0.4406 | 0.4903 | 0.0497 |


## 1. Suspect moves (real if NSE confirms on at least median volume, even if reversed)

| stock_id | date | move_before | cls_before | move_after | cls_after | why |
|---|---|---|---|---|---|---|
| ALOKINDS | 2020-02-19 | 4.1061 | suspect | 4.1061 | suspect | not in NSE raw close |
| BANDHANBNK | 2020-03-26 | 0.3932 | suspect | 0.3932 | real | NSE raw close shows it, volume at or above median, reversed within 5 days |
| CDSL | 2017-07-03 | -0.4992 | suspect | -0.4992 | suspect | not in NSE raw close, low volume |
| INDUSINDBK | 2020-03-26 | 0.4467 | suspect | 0.4467 | real | NSE raw close shows it, volume at or above median, reversed within 5 days |
| JETAIRWAYS | 2019-06-18 | -0.4079 | suspect | -0.4079 | real | NSE raw close shows it, volume at or above median, reversed within 5 days |
| NEUEON | 2013-09-11 |  |  | 8.5263 | suspect | low volume |
| PCJEWELLER | 2018-05-07 | 0.3756 | suspect | 0.3756 | real | NSE raw close shows it, volume at or above median, reversed within 5 days |
| YESBANK | 2020-03-06 | -0.5611 | suspect | -0.5611 | real | NSE raw close shows it, volume at or above median, reversed within 5 days |
| YESBANK | 2020-03-17 | 0.5809 | suspect | 0.5809 | real | NSE raw close shows it, volume at or above median, reversed within 5 days |


## 2. Execution on regular sessions

Special sessions (29): weekend sessions and weekday sessions with turnover below 25% of the trailing 20-session median (Muhurat trading). They are used for marking prices, never for execution. Execution dates on a special session now: 0.

| date | turnover | reason |
|---|---|---|
| 2010-02-06 | 18222168549.97 | weekend session |
| 2011-10-26 | 21835007020.39 | low-turnover session |
| 2012-01-07 | 10941603540.79 | weekend session |
| 2012-03-03 | 12544962788.14 | weekend session |
| 2012-04-28 | 9073456673.43 | weekend session |
| 2012-09-08 | 10449784172.21 | weekend session |
| 2013-05-11 | 10066321003.759998 | weekend session |
| 2013-11-03 | 21833370162.909996 | weekend session |
| 2014-03-22 | 13088328204.09 | weekend session |
| 2014-10-23 | 25990917536.07 | low-turnover session |
| 2015-02-28 | 213474782988.97 | weekend session |
| 2015-11-11 | 27870978013.86 | low-turnover session |
| 2016-10-30 | 34606354345.27 | weekend session |
| 2017-10-19 | 57307619742.840004 | low-turnover session |
| 2018-11-07 | 39537759048.020004 | low-turnover session |
| 2019-10-27 | 58000927540.76 | weekend session |
| 2020-02-01 | 376232259858.41 | weekend session |
| 2020-11-14 | 94835460154.13 | weekend session |
| 2021-11-04 | 115206411494.72 | low-turnover session |
| 2022-10-24 | 104275449424.42 | low-turnover session |
| 2023-11-12 | 139752875913.51 | weekend session |
| 2024-01-20 | 802131589462.28 | weekend session |
| 2024-03-02 | 103380490798.35 | weekend session |
| 2024-05-18 | 153142017413.49 | weekend session |
| 2024-11-01 | 180475841703.11 | low-turnover session |
| 2025-02-01 | 1015619540807.7 | weekend session |
| 2025-10-21 | 195522292289.96 | low-turnover session |
| 2026-02-01 | 1166947173189.6401 | weekend session |
| 2026-11-08 | 231126820983.95 | weekend session |


## 3. Symbols that reappear under a new symbol (same issuer)

Added to `Configs/manual_symbol_changes.csv`:

| old | new | date | evidence |
|---|---|---|---|
| CASTROL | CASTROLIND | 2014-03-14 | notice ind_prs21022014: trading suspended from 28 Feb 2014 for capital reduction; bhavcopy: last CASTROL row 26 Feb 2014 (INE172A01019), first CASTROLIND row 14 Mar 2014 (INE172A01027, same issuer) |
| ESSARSHIP | ESSARPORTS | 2011-05-31 | bhavcopy: last ESSARSHIP 17 May 2011, first ESSARPORTS 31 May 2011 (BE); same issuer INE282A (relisted_check, Phase 1c) |
| HIMACHLFUT | HFCL | 2011-03-09 | bhavcopy: last HIMACHLFUT 7 Feb 2011, first HFCL 9 Mar 2011 (BE); issuer INE548A is HFCL in today's NSE list |
| KIRLOSOIL | KIRLOSIND | 2010-06-24 | bhavcopy: last KIRLOSOIL 20 Apr 2010, first KIRLOSIND 24 Jun 2010; issuer INE250A is KIRLOSIND in today's NSE list |
| FUTUREVENT | FVIL | 2013-07-04 | bhavcopy: last FUTUREVENT 20 Jun 2013 (INE220J01017), first FVIL 4 Jul 2013 (INE220J01025, BE) |
| SUJANATOW | SUJANATWR | 2013-09-11 | bhavcopy: last SUJANATOW 6 Aug 2013 (INE333I01010), first SUJANATWR 11 Sep 2013 (INE333I01036) |
| SUPPETRO | SPLPETRO | 2022-05-24 | bhavcopy: last SUPPETRO 6 Apr 2022 (INE663A01017), first SPLPETRO 24 May 2022 (INE663A01025, BE) |


Still delisting cases, deliberately not merged: re-listings years later with a new ISIN (CHEMPLAST 2012 -> 2021, HEXAWARE 2020 -> 2025), the same symbol absent from NSE's bhavcopy for 2.5 years (KENNAMET, KIRLFER), and KIRLOSIND, whose 65-day gap after the KIRLOSOIL change exceeds the 60-day suspension limit.

| stock_id | file_id | last_price_date | traded_again | listed_today |
|---|---|---|---|---|
| CHEMPLAST | INE488A01027 | 2012-06-15 |  | CHEMPLASTS |
| HEXAWARE | INE093A01033 | 2020-10-30 |  | HEXT |
| KENNAMET | INE717A01029 | 2023-10-25 |  | KENNAMET |
| KIRLFER | INE884B01025 | 2023-10-25 |  | KIRLFER |
| KIRLOSIND | INE250A01039 | 2010-04-20 |  | KIRLOSIND |


## 4. Suspensions (held, not sold; valued at the first close after trading resumes)

Stops of at least 5 index sessions with trading again within 60 days.

| file_id | last_close | resume | missing_sessions | stock_id |
|---|---|---|---|---|
| INE270A01029 | 2020-01-30 | 2020-02-19 | 14 | ALOKINDS |
| INE363A01022 | 2010-02-23 | 2010-04-07 | 27 | ASIANHOTNR |
| INE871C01038 | 2015-03-02 | 2015-04-15 | 27 | AVANTIFEED |
| INE172A01027 | 2014-02-26 | 2014-03-14 | 10 | CASTROLIND |
| INE149A01033 | 2017-08-23 | 2017-09-25 | 21 | CHOLAHLDNG |
| INE335K01011 | 2020-02-03 | 2020-02-24 | 13 | COFFEEDAY |
| INE00R701025 | 2019-01-04 | 2019-01-23 | 12 | DALBHARAT |
| INE221B01012 | 2013-07-29 | 2013-08-12 | 8 | DYNAMATECH |
| INE221B01012 | 2013-08-13 | 2013-08-28 | 9 | DYNAMATECH |
| INE282A01016 | 2011-05-17 | 2011-05-31 | 9 | ESSARPORTS |
| INE220J01017 | 2013-06-20 | 2013-07-04 | 9 | FCONSUMER |
| INE548A01028 | 2011-02-07 | 2011-03-09 | 20 | HFCL |
| INE732A01036 | 2010-03-08 | 2010-04-20 | 27 | KIRLOSBROS |
| INE333I01044 | 2013-08-06 | 2013-09-11 | 22 | NEUEON |
| INE420C01059 | 2011-10-03 | 2011-10-17 | 8 | PAISALO |
| INE663A01033 | 2022-04-06 | 2022-05-24 | 30 | SPLPETRO |
| INE206B01013 | 2013-08-14 | 2013-08-29 | 9 | ZODIACLOTH |


## 5. Lag prices

Each lag price is the last close on or before the lag date if it is at most 5 trading days old (test: 5 days old used = True, 6 days old rejected = True). Member-months ineligible for a stale or missing lag price: 10.
