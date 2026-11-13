# Does LightGBM beat a linear factor blend on the point-in-time Nifty 500?

Walk-forward from 2015 (expanding window, retrained yearly, 1-month embargo). **Development** = feature dates 2015-2022. **Seen** = 2023 to Sep 2026; momentum results for this period were already looked at, so it is not out of sample. Portfolios: top 30, equal weight, 25% sector cap, hold until rank > 45, 10 bps + 5/10/20 bps slippage per side. Returns are monthly, from the feature-date close.

## Development (2015-2022)

| Metric | Momentum baseline | Linear blend (12 features) | LightGBM | Equal-weight universe |
|---|---|---|---|---|
| IC mean | 0.040 | 0.064 | 0.052 |  |
| IC t-stat (NW) | 2.34 | 2.99 | 3.60 |  |
| ICIR (monthly) | 0.24 | 0.29 | 0.36 |  |
| Top quintile − universe (% / month) | 0.63% | 0.31% | 0.37% |  |
| Top quintile t-stat (NW) | 2.76 | 1.16 | 1.57 |  |
| CAGR | 18.49% | 15.34% | 13.83% | 9.70% |
| Sharpe | 0.84 | 1.01 | 0.78 | 0.53 |
| Max drawdown | -26.15% | -21.98% | -26.93% | -47.89% |
| Excess over EW (% / month) | 0.67% | 0.30% | 0.25% | 0.00% |
| Excess t-stat (NW) | 2.08 | 1.00 | 0.84 |  |
| Turnover (one-way, x / yr) | 3.18 | 3.35 | 7.49 | 0.94 |
| Cost drag (% / yr) | 1.29% | 1.09% | 3.03% | 0.44% |
| Months | 96 | 96 | 96 | 96 |

## Seen (2023 to Sep 2026)

| Metric | Momentum baseline | Linear blend (12 features) | LightGBM | Equal-weight universe |
|---|---|---|---|---|
| IC mean | 0.033 | 0.042 | 0.040 |  |
| IC t-stat (NW) | 2.00 | 1.94 | 3.19 |  |
| ICIR (monthly) | 0.24 | 0.26 | 0.35 |  |
| Top quintile − universe (% / month) | 0.58% | -0.01% | 0.15% |  |
| Top quintile t-stat (NW) | 1.91 | -0.02 | 0.97 |  |
| CAGR | 21.17% | 12.16% | 15.35% | 16.15% |
| Sharpe | 0.89 | 0.86 | 0.89 | 0.88 |
| Max drawdown | -26.69% | -18.59% | -26.04% | -23.19% |
| Excess over EW (% / month) | 0.47% | -0.35% | -0.07% | 0.00% |
| Excess t-stat (NW) | 1.10 | -0.78 | -0.28 |  |
| Turnover (one-way, x / yr) | 3.52 | 4.07 | 8.62 | 0.57 |
| Cost drag (% / yr) | 1.12% | 1.23% | 2.97% | 0.23% |
| Months | 45 | 45 | 45 | 45 |

## Head-to-head: LightGBM minus linear blend (net monthly returns)

| Period | Mean (% / month) | t-stat (NW) | Months |
|---|---:|---:|---:|
| development | -0.06% | -0.23 | 96 |
| seen | 0.28% | 0.59 | 45 |

## Feature importance (LightGBM)

| feature | gain_share_dev | mean_abs_shap_dev | mean_abs_shap_seen | linear_sign_dev_years |
|---|---|---|---|---|
| beta_ew | 0.1097 | 0.0144 | 0.0039 | 0+ / 8- |
| mom_12_1 | 0.0948 | 0.0123 | 0.012 | 8+ / 0- |
| vol_1m | 0.0917 | 0.0106 | 0.0057 | 0+ / 8- |
| dist_52w_high | 0.0843 | 0.0101 | 0.0046 | 8+ / 0- |
| vol_12m | 0.0894 | 0.0084 | 0.0146 | 0+ / 8- |
| mom_6_1 | 0.0751 | 0.0081 | 0.0035 | 8+ / 0- |
| ind_rel_mom_6_1 | 0.0732 | 0.0079 | 0.005 | 8+ / 0- |
| ret_1m | 0.0793 | 0.0071 | 0.0057 | 5+ / 3- |
| log_traded_value | 0.068 | 0.0069 | 0.0038 | 7+ / 1- |
| max_ret_1m | 0.0819 | 0.0065 | 0.0038 | 0+ / 8- |
| ret_3m | 0.0803 | 0.0061 | 0.0039 | 8+ / 0- |
| amihud | 0.0723 | 0.0061 | 0.0034 | 0+ / 8- |

`gain_share_dev`: average share of total gain across the 8 development models. `mean_abs_shap`: mean |SHAP| on test predictions. `linear_sign_dev_years`: how often the linear blend gave the feature a positive or negative sign.

In plain words: by mean |SHAP| the model leaned most on beta_ew, mom_12_1, vol_1m, dist_52w_high. Grouping the features, the development SHAP mass splits as: momentum 43%, low volatility / low beta 38%, liquidity / size 12%, short-term reversal 7%.

Top 3 SHAP interaction pairs (development models, 500 test rows per year):

| feature_a | feature_b | mean_abs_shap_interaction |
|---|---|---|
| mom_12_1 | beta_ew | 0.00435 |
| ret_1m | beta_ew | 0.00426 |
| mom_12_1 | ind_rel_mom_6_1 | 0.00409 |

## Spanning test: LightGBM net return − RF on IIMA four factors (Newey-West, 3 lags)

| Period | months | alpha (% / yr) | alpha t | b_MF | b_SMB | b_HML | b_WML | t_WML | R2 |
|---|---|---|---|---|---|---|---|---|---|
| development | 96 | 2.31% | 0.81 | 0.97 | 0.27 | 0.01 | 0.01 | 0.16 | 0.87 |
| seen (to 2025-12) | 35 | -1.73% | -0.45 | 0.86 | 0.27 | 0.17 | 0.23 | 1.72 | 0.83 |
| all (to 2025-12) | 131 | 1.37% | 0.56 | 0.95 | 0.27 | 0.05 | 0.05 | 1.06 | 0.86 |

## Trials and deflated Sharpe

| trial | model | settings | dev_ic | dev_sharpe | dev_excess_pm | run_at | best_on_dev |
|---|---|---|---|---|---|---|---|
| 1 | Momentum baseline | z(0.5 z(12-1) + 0.5 z(6-1)), clip 1/99 | 0.0404 | 0.8363 | 0.0067 | 2026-11-12T22:04:11 | False |
| 2 | Linear blend (12 features) | sign of training IC x 12 rank features, equal weight | 0.0637 | 1.0066 | 0.003 | 2026-11-12T22:04:11 | True |
| 3 | LightGBM | lightgbm.train, 300 rounds, objective=regression, num_leaves=15, learning_rate=0.05, min_data_in_leaf=200, bagging_fraction=0.8, bagging_freq=1, feature_fraction=0.8, seed=42, deterministic=True | 0.0525 | 0.7784 | 0.0025 | 2026-11-12T22:04:11 | False |

Best development model: **Linear blend (12 features)** (development Sharpe 1.01). Expected best Sharpe of 3 zero-skill trials: 0.10. **Deflated Sharpe on raw returns: 0.99.** That mostly says a long-only Nifty 500 portfolio had a positive Sharpe; all three trials hold the market, so they differ little and the bar is low. On returns in excess of the equal-weight universe (Sharpe 0.31, expected best of 3 zero-skill trials 0.19), the **deflated Sharpe is 0.64**.

## Conclusion

ML did not add anything after costs. LightGBM ranked stocks about as well as the linear blend of the same 12 features: development IC 0.052 against 0.064, with the steadier IC (ICIR 0.36 against 0.29). But its portfolio traded 7.5x a year against 3.4x and paid 3.0% a year in costs. Net, it beat the equal-weight universe by only 0.25% a month in development (t = 0.84) and by -0.07% in the seen period. Head-to-head, LightGBM minus the linear blend was -0.06% a month in development (t = -0.23) and 0.28% in the seen period (t = 0.59): no evidence either way. Against the IIMA four factors, LightGBM's alpha is 1.4% a year (t = 0.56). The plain momentum baseline did best on the one comparison that matters for a long-only investor: 0.67% a month over equal weight in development (t = 2.08) and 0.47% in the seen period. LightGBM mostly rediscovered momentum and low volatility/low beta. It found little in reversal: the 1-month return was given a positive sign in 5 of 8 years, so it is not a reversal signal in this universe.
