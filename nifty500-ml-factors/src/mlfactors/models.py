"""Walk-forward predictions for the three pre-specified models (no tuning).

Train on every month from 2011 to the end of year Y-1, drop the last training month as an embargo,
and predict every month of year Y. Retrain once a year; the first test year is 2015.
"""

import logging

import lightgbm as lgb
import numpy as np
import pandas as pd
import shap

from mlfactors.data import DATA_DIR, FEATURES, RESULTS_DIR

logger = logging.getLogger(__name__)

LAST_FEATURE_DATE = "2026-09-30"  # later month-ends have no complete next month yet
FIRST_TEST_YEAR, DEV_LAST_YEAR = 2015, 2022
X_COLS = ["r_" + f for f in FEATURES]
LGB_PARAMS = dict(
    objective="regression",
    num_leaves=15,
    learning_rate=0.05,
    min_data_in_leaf=200,
    bagging_fraction=0.8,
    bagging_freq=1,
    feature_fraction=0.8,
    seed=42,
    deterministic=True,
    num_threads=4,
    verbose=-1,
)
N_ESTIMATORS = 300
SHAP_SAMPLE_ROWS = 500
CLIP_QUANTILES = (0.01, 0.99)


def momentum_score(month: pd.DataFrame) -> pd.Series:
    """Momentum project score: z(0.5 z(12-1) + 0.5 z(6-1)), inputs clipped at 1st/99th pct."""
    ok = month.mom_12_1.notna() & month.mom_6_1.notna()
    z = {}
    for c in ["mom_12_1", "mom_6_1"]:
        x = month.loc[ok, c].clip(
            month.loc[ok, c].quantile(CLIP_QUANTILES[0]),
            month.loc[ok, c].quantile(CLIP_QUANTILES[1]),
        )
        z[c] = (x - x.mean()) / x.std(ddof=1)
    combo = 0.5 * z["mom_12_1"] + 0.5 * z["mom_6_1"]
    return ((combo - combo.mean()) / combo.std(ddof=1)).reindex(month.index)


def monthly_ic(panel: pd.DataFrame, col: str) -> float:
    """Mean over months of the correlation between a ranked column and the ranked target."""
    return panel.groupby("date").apply(lambda m: m[col].corr(m.r_fwd_ret)).mean()


def linear_blend_signs(train: pd.DataFrame) -> pd.Series:
    """Sign of each feature's mean training IC; the blend is the equal-weight signed average."""
    return pd.Series({c: np.sign(monthly_ic(train, c)) for c in X_COLS})


def training_window(panel: pd.DataFrame, year: int) -> pd.DataFrame:
    """All months before `year`, minus the last one (a one-month embargo before the test year)."""
    train = panel[panel.date < f"{year}-01-01"]
    return train[train.date < train.date.max()]


def run_walk_forward() -> None:
    """Write predictions.parquet, feature_importance.csv and interactions.csv."""
    RESULTS_DIR.mkdir(exist_ok=True)
    panel = pd.read_parquet(DATA_DIR / "panel.parquet")
    panel = panel[panel.date <= LAST_FEATURE_DATE].reset_index(drop=True)
    panel["pred_momentum"] = panel.groupby("date", group_keys=False).apply(momentum_score)

    preds, gains, signs, shap_rows, interactions = [], [], [], [], []
    for year in range(FIRST_TEST_YEAR, panel.date.dt.year.max() + 1):
        train = training_window(panel, year)
        test = panel[panel.date.dt.year == year].copy()

        year_signs = linear_blend_signs(train)
        test["pred_linear"] = (test[X_COLS] * year_signs).mean(axis=1)
        signs.append(year_signs.rename(year))

        model = lgb.train(
            LGB_PARAMS, lgb.Dataset(train[X_COLS], train.r_fwd_ret), num_boost_round=N_ESTIMATORS
        )
        test["pred_lgbm"] = model.predict(test[X_COLS])
        gains.append(pd.Series(model.feature_importance("gain"), X_COLS, name=year))
        contrib = model.predict(test[X_COLS], pred_contrib=True)[:, :-1]
        shap_rows.append(pd.DataFrame(np.abs(contrib), columns=X_COLS).assign(year=year))
        if year <= DEV_LAST_YEAR:
            sample = test[X_COLS].sample(min(SHAP_SAMPLE_ROWS, len(test)), random_state=42)
            values = shap.TreeExplainer(model).shap_interaction_values(sample)
            interactions.append(np.abs(values).mean(axis=0))
        preds.append(
            test[["date", "next_date", "file_id", "pred_momentum", "pred_linear", "pred_lgbm"]]
        )
        logger.info(
            "%d: trained on %s to %s (%d rows), predicted %d rows",
            year, f"{train.date.min():%Y-%m}", f"{train.date.max():%Y-%m}", len(train), len(test),
        )  # fmt: skip

    pd.concat(preds).to_parquet(DATA_DIR / "predictions.parquet", index=False)

    gain = pd.concat(gains, axis=1)
    shap_values = pd.concat(shap_rows)
    signs = pd.concat(signs, axis=1)
    dev_years = [y for y in signs.columns if y <= DEV_LAST_YEAR]
    sign_counts = [
        f"{int((signs.loc[c, dev_years] > 0).sum())}+ / {int((signs.loc[c, dev_years] < 0).sum())}-"
        for c in X_COLS
    ]
    importance = pd.DataFrame({
        "feature": FEATURES,
        "gain_share_dev": (gain[dev_years] / gain[dev_years].sum()).mean(axis=1).values,
        "mean_abs_shap_dev": shap_values[shap_values.year <= DEV_LAST_YEAR][X_COLS].mean().values,
        "mean_abs_shap_seen": shap_values[shap_values.year > DEV_LAST_YEAR][X_COLS].mean().values,
        "linear_sign_dev_years": sign_counts,
    }).sort_values("mean_abs_shap_dev", ascending=False)  # fmt: skip
    importance.round(6).to_csv(RESULTS_DIR / "feature_importance.csv", index=False)

    mean_interaction = np.mean(interactions, axis=0)
    # SHAP splits each interaction equally between (i, j) and (j, i): the pair total is 2x one cell
    pairs = [
        (FEATURES[i], FEATURES[j], 2 * mean_interaction[i, j])
        for i in range(len(FEATURES))
        for j in range(i + 1, len(FEATURES))
    ]
    pd.DataFrame(
        pairs, columns=["feature_a", "feature_b", "mean_abs_shap_interaction"]
    ).sort_values("mean_abs_shap_interaction", ascending=False).round(6).to_csv(
        RESULTS_DIR / "interactions.csv", index=False
    )
    logger.info("\n%s", importance.round(4).to_string(index=False))
