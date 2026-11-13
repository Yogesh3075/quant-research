# Numbers worth quoting

Hypothetical backtest results; costs are assumptions (VERIFY). Each number names the file it comes from.

| what | number | file | table / row |
|---|---|---|---|
| Rank IC of the momentum score with next-month returns | 0.044 (t = 3.08) | results/phase2/ic_summary.csv | IC, row score |
| Top quintile minus eligible universe, gross | 0.65% a month (t = 3.34) | results/phase2/spread_5.csv | top_minus_universe |
| Primary minus equal weight after base costs, development | 0.75% a month (t = 2.91) | results/phase3/table_vs_equal_weight.csv | primary, base |
| Primary minus equal weight, walk-forward test months (out of sample) | 0.93% a month (t = 2.89) | results/phase4/walkforward_summary.csv | primary |
| Holdout (frozen selection minus equal weight) | 0.62% a month (t = 1.56, 23 months) | results/phase4/holdout_summary_run1.csv | frozen selection |
| Fama-MacBeth momentum slope with all controls (model E) | 0.49% a month per 1 sd (t = 3.91) | results/phase5/fm.csv | model E, score, development |
| Four-factor alpha of the primary vs IIMA MF, SMB, HML, WML | 0.67% a year (t = 0.26); market-only alpha 5.81% (t = 2.00) | results/phase5/spanning.csv | primary minus RF |
| Correlation of Q5 minus Q1 with IIMA WML | 0.76 | results/phase5/spanning.csv | Q5 minus Q1, corr_with_wml |
| Survivorship inflation of the universe return (today's list vs point in time) | 5.38% a year | results/phase2/survivorship.csv | universe_return, x12 |
| Trials run (all logged before running) | 20 | results/trial_log.csv | all rows |
