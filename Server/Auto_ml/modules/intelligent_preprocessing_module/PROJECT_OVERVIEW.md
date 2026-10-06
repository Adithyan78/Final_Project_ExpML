# Intelligent Preprocessing Module

## 1. Purpose

This project is a reusable, YAML-driven preprocessing engine for tabular machine learning data. Instead of hardcoding preprocessing decisions in Python, it reads rules from YAML, evaluates them against per-column metadata, decides which transformations to apply, builds a scikit-learn pipeline, and tracks every step for provenance and debugging.

In practical terms, the module answers a single question:

> Given a dataset and a profile describing each column, what preprocessing should be applied to each feature before model training and inference?

It is designed to be:

- data-driven
- configurable through YAML
- safe against target leakage
- deterministic and explainable
- extensible through an action registry

---

## 2. What the code does

At a high level, the system performs the following:

1. Reads an analyzer profile describing each feature, such as:
   - column type (numeric or categorical)
   - missing percentage
   - cardinality
   - flags or metadata
2. Loads a ruleset from YAML (or from an in-memory dictionary/string).
3. Validates rule structure and condition safety.
4. Evaluates each column against rules for stages like:
   - missing-value handling
   - scaling
   - encoding
5. Resolves precedence between:
   - user overrides
   - YAML rules
   - default actions
6. Builds a `ColumnTransformer` pipeline from those decisions.
7. Fits the pipeline on training data only.
8. Applies feature selection after transformation using variance filtering and mutual information.
9. Keeps provenance for every transformed feature so it can be traced back to the original source column.
10. Exposes a `transform()` method that applies the saved fitted preprocessing to new data without refitting.

---

## 3. Core design ideas

### 3.1 YAML decides, Python executes

The engine does not encode dataset-specific logic in Python. Instead, rule files define the behavior. A sample rule looks like this:

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

This makes the preprocessing process:

- configurable
- versioned
- auditable
- easier to review and modify without changing the code

### 3.2 Rule resolution is deterministic

For each column and stage, the engine selects the winning decision using a precedence model:

1. explicit user override
2. highest-priority matching YAML rule
3. default action if nothing matches

If a column is dropped in the missing-value stage, later stages for that column are skipped and recorded as skipped instead of silently omitted.

### 3.3 Safety-first behavior

The code is built to avoid common data leakage issues:

- target columns are dropped from feature data before preprocessing
- trained preprocessing parameters are frozen during `transform()`
- target encoding is fit only on training data
- feature selection uses only training labels and not test data
- unsafe rule conditions are not evaluated with raw Python `eval()`

---

## 4. Main modules and responsibilities

### `PreprocessingEngine`

This is the public entry point. It orchestrates rule loading, decision generation, pipeline fitting, transformation, and feature selection.

Main methods:

- `fit_transform(X_train, y_train, analyzer_profile, user_config=None)`
- `transform(X)`

The returned result includes:

- processed training data
- preprocessing log
- feature selection log
- feature ranking
- provenance metadata
- fitted preprocessor

### `rule_loader.py`

Loads rules from:

- a YAML file path
- a YAML string
- an already-parsed dictionary

It validates the input and converts it into a structured ruleset.

### `rule_schema.py`

Defines the schema for rules and validates:

- required fields
- allowed stages
- valid action names
- condition consistency
- file versioning

### `rule_engine.py`

This is where each column is evaluated against rule logic. It creates a decision list per column and resolves conflicts by stage and priority.

### `action_registry.py`

Every supported transformation is registered here. Examples include:

- `drop_column`
- `impute_median`
- `impute_mean`
- `impute_most_frequent`
- `impute_constant`
- `standard_scale`
- `robust_scale`
- `minmax_scale`
- `one_hot`
- `ordinal_encode`
- `target_encode`
- `no_impute`
- `no_scale`
- `no_encode`

This registry makes the system extensible without changing the rule engine.

### `pipeline_builder.py`

Takes the selected actions for each column and creates a single `ColumnTransformer` pipeline for the full dataset.

### `provenance.py`

Tracks the relationship between transformed output features and their source columns. This allows users to answer questions like:

> Which original column produced this encoded feature?

### `feature_selection.py`

After preprocessing, the module applies:

1. variance thresholding
2. mutual information scoring
3. column-aware top-k selection

This keeps the most informative columns while preserving grouped one-hot outputs.

### `condition_evaluator.py`

Evaluates rule conditions using a restricted safe-evaluation approach rather than raw Python `eval()`. It allows only trusted operations on a single `column` object and blocks arbitrary code execution.

### `profile_adapter.py`

Converts the analyzer profile into column-level facts used when evaluating rules.

---

## 5. Typical execution flow

```python
from preprocessing_module import PreprocessingEngine

engine = PreprocessingEngine()
result = engine.fit_transform(X_train, y_train, analyzer_profile, user_config=None)
X_test_final = engine.transform(X_test)
```

### Step-by-step

1. `fit_transform()` validates input.
2. It removes the target column if present in `X_train`.
3. It builds per-column facts from the analyzer profile.
4. It evaluates rules and user overrides for every column.
5. It constructs a `ColumnTransformer`.
6. It fits the transformer on training data.
7. It generates transformed features and provenance.
8. It performs feature selection with variance + MI.
9. It stores the fitted state so `transform()` can be called later.

---

## 6. Leakage protection and correctness

A major focus of this project is preventing information leakage:

- the target column is dropped before any modeling step
- training parameters are not recalculated during `transform()`
- target encoding uses training-only statistics
- feature selection is based only on the training labels
- transform-time behavior is deterministic and reproducible

This is especially important when using validation or holdout datasets.

---

## 7. User override support

The engine allows per-column overrides such as:

```python
user_config = {
    "Age": {"action": "impute_mean"},
    "Fare": {"missing_action": "impute_median", "scaling_action": "robust_scale"}
}
```

These values take precedence over YAML-defined rules but still pass through the same validation and registry checks.

---

## 8. Feature provenance

The engine stores mappings from transformed feature names back to their source columns. For example:

```json
{"output_feature": "Sex_male", "source_column": "Sex", "transformation": "one_hot"}
```

This makes debugging and explainability much easier because the user can see what produced each final model feature.

---

## 9. Why this project is useful

This project is useful when you want:

- rule-based preprocessing without hardcoding logic
- reusable preprocessing for multiple datasets
- explainability and traceability of transformed features
- safer ML pipelines than ad hoc preprocessing code
- easier experimentation with new preprocessing actions

It is especially suitable for analytical environments where preprocessing rules need to be reviewed, versioned, and adjusted without rewriting the whole execution pipeline.

---

## 10. Example scenario

The demo uses the Titanic dataset and an analyzer profile to:

- identify numeric vs categorical columns
- decide how to impute missing values
- decide whether to scale numeric features
- decide how to encode categorical columns
- select the most informative columns
- transform validation data using the fitted rules

This makes the project a practical framework for tabular data preprocessing in applied ML workflows.

---

## 11. Summary

The Intelligent Preprocessing Module is a domain-specific data preprocessing framework that converts a dataset profile and YAML rules into a fitted, explainable, leakage-safe transformation pipeline. It blends rule-driven configuration, scikit-learn preprocessing, feature provenance tracking, and careful validation to produce a robust ML preprocessing layer.

The project’s central idea is simple:

> define data handling in declarative rules, let the engine execute them consistently, and keep enough metadata to understand every transformed feature.
