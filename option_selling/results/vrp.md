# Variance risk premium diagnostic (development cycles only)

ATM = listed strike nearest S0 on the entry day for the target expiry; IV by Black-Scholes, r = 6.5%, no dividend yield, T = calendar days / 365. RV = annualised std of daily log returns of NIFTY 50 from entry close to expiry close (sqrt 252).

Months: 200. Mean IV 19.1%, mean RV 17.3%. **Mean IV - RV +1.77%** (median +2.59%); IV above RV in **71%** of months. Call IV 17.9%, put IV 20.3%.

## By year

|   entry |   months |    iv |    rv |   iv_minus_rv |   share_pos |
|--------:|---------:|------:|------:|--------------:|------------:|
|    2008 |   12.000 | 0.404 | 0.406 |        -0.002 |       0.583 |
|    2009 |   11.000 | 0.345 | 0.310 |         0.035 |       0.818 |
|    2010 |   13.000 | 0.195 | 0.161 |         0.033 |       0.769 |
|    2011 |   12.000 | 0.224 | 0.200 |         0.023 |       0.750 |
|    2012 |   12.000 | 0.176 | 0.136 |         0.039 |       1.000 |
|    2013 |   12.000 | 0.168 | 0.175 |        -0.007 |       0.333 |
|    2014 |   12.000 | 0.152 | 0.126 |         0.026 |       0.667 |
|    2015 |   11.000 | 0.170 | 0.157 |         0.013 |       0.636 |
|    2016 |   13.000 | 0.148 | 0.143 |         0.005 |       0.538 |
|    2017 |   12.000 | 0.112 | 0.087 |         0.025 |       0.833 |
|    2018 |   12.000 | 0.139 | 0.124 |         0.015 |       0.750 |
|    2019 |   12.000 | 0.144 | 0.132 |         0.012 |       0.750 |
|    2020 |   11.000 | 0.268 | 0.262 |         0.006 |       0.727 |
|    2021 |   13.000 | 0.174 | 0.145 |         0.029 |       0.846 |
|    2022 |   12.000 | 0.176 | 0.163 |         0.013 |       0.667 |
|    2023 |   11.000 | 0.115 | 0.094 |         0.019 |       0.750 |
|    2024 |    9.000 | 0.139 | 0.128 |         0.011 |       0.667 |

## India VIX at entry vs realised vol
125 months from 2014-05: mean VIX 16.9%, mean RV 14.2%, VIX - RV +2.78%, VIX above RV in 79% of months.
