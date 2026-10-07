# Declared downstream ML utility

FULL utility requires an explicit modelled target and task:
BINARY_CLASSIFICATION, MULTICLASS_CLASSIFICATION or REGRESSION. Identifiers,
excluded/free-text fields, datetime targets and the configured group key are
rejected as targets. Numerical targets require regression; categorical/boolean
targets require classification. Binary tasks require exactly two training classes.
Missing synthetic classes, unseen target classes, null targets and constant
regression targets produce stable non-retryable domain errors.

SDMetrics ML-efficacy APIs are documented Beta in the inspected version. Production
comparison therefore uses transparent **scikit-learn 1.9.1** pipelines, not those
Beta APIs or AutoML.

## TRTR and TSTR

TRTR trains on the real training partition; TSTR trains on synthetic records.
They use the same architecture and evaluate on the **identical untouched real
holdout**. Each pipeline separately fits its preprocessing to its own training
input. Neither holdout features nor labels reach .fit, model selection or tuning.
Instrumented tests wrap preprocessing and estimator fitting to verify positions,
counts and unchanged holdout; Phase 3 synthesis tests separately verify the
synthesizer fits only training. Evaluation does not retrain synthesis engines.

Numeric features use median imputation and StandardScaler. Categorical features
use constant imputation and OneHotEncoder(handle_unknown="ignore"). Optional
datetime_features converts dates to UTC Unix seconds without learned holdout
statistics; by default datetime features are excluded. Identifiers, excluded
columns, group key and target are excluded from features. Classification uses
LogisticRegression(max_iter=500, solver="lbfgs", random_state=seed); regression
uses Ridge(alpha=1, solver="lsqr"). There is no holdout hyperparameter search.

Reports store each metric independently: binary F1/accuracy/precision/recall and
ROC-AUC when meaningful; multiclass macro F1/accuracy/weighted F1; regression
R²/MAE/RMSE. Indexed class_0/class_1 aggregate counts preserve target imbalance
without dumping sensitive labels. Pipeline family, preprocessing, features,
excluded columns, seeds, partition sizes and fit_scope are persisted.

## Comparisons

All deltas are TSTR minus TRTR. Higher-is-better F1/accuracy ratios are TSTR/TRTR;
lower-is-better MAE/RMSE ratios are TRTR/TSTR. R² has delta only because a ratio
can mislead with negative baselines. Near-zero denominators (numerical guard
1e-12, not quality threshold) yield unavailable ratios. The policy key
`tstr_trtr_ratio` uses F1 for binary, macro F1 for multiclass and the explicitly
labeled TRTR/TSTR MAE comparison for regression. It is not percent useful.

Insufficient holdout or group leakage makes utility advisory. Repeatedly using
the same holdout to optimize synthesis in later human experiments can contaminate
it; this evaluation run performs no such feedback loop. Utility evidence is for
this declared task/model/data/split, not clinical validity or general-purpose utility.
