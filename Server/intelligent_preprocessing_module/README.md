# Intelligent Preprocessing Module

A reusable, **YAML-driven** preprocessing engine. No preprocessing logic is
hardcoded in Python — a versioned rules file decides *what* to do to each
column, and a generic engine executes it, tracks provenance, and logs every
decision.

```python
from preprocessing_module import PreprocessingEngine

engine = PreprocessingEngine()
result = engine.fit_transform(X_train, y_train, analyzer_profile, user_config=None)
X_test_final = engine.transform(X_test)
```

**Design principle:** `YAML decides -> Python executes -> provenance tracks -> logs record.`

## Architecture

```
Analyzer Profile (per-column stats: type, missing_pct, cardinality, ...)
      |
      v
YAML Rule Engine  (condition evaluator + priority resolution + user overrides)
      |
      v
Preprocessing Decisions   (one per column, per stage: missing / scaling / encoding)
      |
      v
sklearn ColumnTransformer / Pipeline   (built from decisions via an action registry)
      |
      v
Feature Provenance   (every output feature -> source column -> transformation)
      |
      v
VarianceThreshold  ->  Mutual Information  ->  Column-aware Top-K
      |
      v
Final Features + Logs
```

## Package layout

```
preprocessing_module/
  engine.py                 PreprocessingEngine (fit_transform / transform)
  condition_evaluator.py     Safe AST-whitelist evaluator for rule conditions
  rule_schema.py             Rule / RuleSet dataclasses + validation
  rule_loader.py              Loads YAML (path, string, or dict) into a RuleSet
  rule_engine.py              Per-column, per-stage decision resolution
  action_registry.py          Extensible action name -> sklearn builder registry
  pipeline_builder.py         Decisions -> a single fitted ColumnTransformer
  provenance.py               Output feature -> source column -> transformation
  feature_selection.py        VarianceThreshold -> MI -> column-aware Top-K
  profile_adapter.py           Analyzer-profile JSON -> per-column rule "facts"
  exceptions.py               RuleValidationError, ConditionEvaluationError, ...
  transformers/
    target_encoder.py         LeakageSafeTargetEncoder (fit on train only)
  config/
    default_rules.yaml        Shipped default rules (versioned, "1.0")
    default_feature_selection.yaml

tests/
  fixtures/
    titanic.csv                Real Titanic dataset (test fixture only)
    titanic_profile.json       The analyzer profile you supplied
  test_condition_evaluator.py
  test_rule_loader_validation.py
  test_rule_engine_priorities_overrides.py
  test_missing_and_encoding.py
  test_scaling.py
  test_provenance.py
  test_feature_selection.py
  test_leakage_and_determinism.py
  test_end_to_end_titanic.py

demo.py                       Small runnable end-to-end example
requirements.txt
```

## The rules file

```yaml
version: "1.0"
rules:
  - id: high_missing_drop
    priority: 800
    stage: missing
    condition: "column.missing_pct > 60"
    action: "drop_column"
    reason: "Column {col} is missing in over 60% of rows."
```

- **`condition`** is evaluated by a hand-rolled, AST-whitelist evaluator
  (`condition_evaluator.py`) — never Python's raw `eval`. Only attribute
  access on the single name `column` is permitted (e.g. `column.missing_pct`,
  `column.type`, `column.cardinality`, `column.flags`); no function calls,
  no dunder access, no arbitrary names. Malformed or unsafe conditions raise
  `ConditionEvaluationError` at **load time**, not deep inside a `fit()` call.
- **`stage`** is one of `missing`, `scaling`, `encoding`. A column's stages
  run in that fixed order; a `drop_column` at the `missing` stage
  short-circuits every later stage for that column (logged as `"skipped"`,
  not silently omitted).
- **`priority`**: for a given column + stage, every matching rule is a
  candidate; the **highest-priority match wins** (ties broken by rule `id`
  for determinism).
- Ships with a default rules file (`config/default_rules.yaml`) covering
  identifier-like columns, high/moderate/low missingness (numeric +
  categorical), outlier-aware scaling (RobustScaler vs StandardScaler), and
  cardinality-aware encoding (OneHot vs target encoding) — all data-driven,
  none of it Titanic-specific.

## User overrides (take precedence over YAML)

```python
user_config = {
    "Age": {"action": "impute_mean"},                 # applies to whichever stage impute_mean belongs to
    "Fare": {"missing_action": "impute_median",         # or be explicit per stage
             "scaling_action": "robust_scale"},
}
```

## Action registry

Every action a rule or override can name lives in `action_registry.py`,
tagged with its pipeline stage and a builder returning an
sklearn-compatible transformer (or the `DROP` / `"passthrough"` sentinels).
Adding a new action (e.g. a power transform) means adding one entry there —
nothing in the rule engine, schema, or evaluator needs to change.

Built-in actions: `drop_column`, `impute_median`, `impute_mean`,
`impute_most_frequent`, `impute_constant`, `no_impute`, `standard_scale`,
`robust_scale`, `minmax_scale`, `no_scale`, `one_hot`, `ordinal_encode`,
`target_encode` (leakage-safe, smoothed, fit on training data only),
`no_encode`.

## Feature provenance

After the `ColumnTransformer` is fitted, every output feature is traced
back to its source column and the transformation(s) applied:

```json
{"output_feature": "Sex_male", "source_column": "Sex", "transformation": "one_hot"}
```

## Feature selection

1. **VarianceThreshold** drops near-constant output features.
2. **`mutual_info_classif`** scores every *surviving* feature against
   `y_train` — stored for every one of them, not just the winners.
3. **Column-aware Top-K**: individual feature scores are aggregated back to
   their **source column** (`max` / `mean` / `sum`, configurable). Columns
   are ranked by that aggregated score, and the top-K *columns* are kept —
   if a column survives, **all** of its remaining output features are kept
   with it (a 3-level one-hot column is never split across the cut line).

```yaml
feature_selection:
  variance:
    enabled: true
    threshold: 0.01
  mutual_information:
    enabled: true
    top_k: 10
    random_state: 42
    aggregation: max
```

## Leakage protection

- `X_train` / `y_train` are the only things fitted on. `.transform()` never
  refits anything (imputer statistics, scaler params, one-hot categories,
  and target-encoding maps are all frozen after `fit_transform`).
- `mutual_info_classif` only ever sees `y_train`.
- The custom `LeakageSafeTargetEncoder` is fit only on training data; a
  category never seen during training maps to the training-set global mean
  at transform time, never to anything derived from test data.
- The target column is dropped from `X` (with a logged reason) even if the
  caller accidentally leaves it in, before any rule ever sees it.
- Verified by `tests/test_leakage_and_determinism.py`, including a test
  that intentionally corrupts test-set values to prove imputation/scaling
  parameters don't shift when `.transform()` is called.

## Running the tests

```bash
pip install -r requirements.txt
PYTHONPATH=. pytest tests/ -q
```

68 tests, all passing, covering: condition-evaluator safety, rule-file
schema validation, priority/override resolution, missing-value handling,
scaling, encoding, provenance, feature selection (including a synthetic
grouped-one-hot case), leakage protection, and determinism — using the
supplied Titanic analyzer profile as the primary fixture (not hardcoded
into any production code path).

## Running the demo

```bash
PYTHONPATH=. python3 demo.py
```
