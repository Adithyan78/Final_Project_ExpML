# automl_trainer — model selection + training (AutoExplainAI stage 4-5)

Consumes the outputs of the Dataset Analyzer and Preprocessing modules, finds the best classical-ML
model (no deep learning) for the dataset, and saves it with a full audit trail.

## Inputs (from earlier modules)
| File | From | Used for |
|---|---|---|
| train_processed.csv, test_processed.csv | Preprocessing | training / final test |
| y_train.csv, y_test.csv (1 column each) | Preprocessing (**must be added**) | targets |
| dataset_profile.json | Analyzer | imbalance, target association, outliers, skew, task type |
| feature_provenance.json | Preprocessing | one-hot share, categorical vs numeric sources |

## Flow
1. Validate inputs, infer task (classification / regression).
2. Build a dataset context from profile + provenance + data.
3. Score the model pool with `rules.yaml` (editable knowledge base) -> shortlist with reasons.
4. Rung 0: cheap CV screen of all shortlisted models + dummy baseline (subsampled if data is large);
   prune weak models and anything not beating the baseline.
5. Rung 1: full-data CV of the survivors (only when rung 0 subsampled).
6. Randomized-search tuning of the top-N.
7. Confirm every finalist (tuned vs default) on FRESH CV folds, so tuning can't inflate scores.
8. Optional soft-voting ensemble; it must beat the best single model by `ensemble_min_gain`.
9. Pick the winner by CV primary metric (ties: secondary metric, stability, speed).
10. Fit on train, score ONCE on the test set. Save model bundle, reports, checksummed manifest.

## Use
    python -m automl_trainer --input-dir output --profile dataset_profile.json --out-dir model_output

    import automl_trainer as at
    res = at.run_from_directory("output", "model_output", profile_path="dataset_profile.json")
    bundle = at.load_bundle("model_output/best_model.joblib")
    at.predict(bundle, new_preprocessed_df)

Config: `--config cfg.yaml` (see `config.py`), custom rules: `--rules my_rules.yaml`.

## Outputs
best_model.joblib, models/*.joblib, leaderboard.csv, run_summary.json, selection_report.json,
training_results.json, test_evaluation.json, manifest.json (sha256 of every file).

## Extending
New model: add a `ModelSpec` in `registry.py` and points in `rules.yaml`. New rule: edit `rules.yaml`.
Optional extras: `pip install xgboost lightgbm` (auto-detected).

## Tests
    pip install pytest && python -m pytest automl_trainer/tests
