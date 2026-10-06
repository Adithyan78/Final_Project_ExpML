"""
AutoExplainAI — Module 1: Dataset Analyzer

Purpose
-------
Analyze a tabular CSV/DataFrame and produce a JSON-serializable dataset
profile for downstream modules.

This version intentionally uses an in-memory pandas DataFrame instead of
chunking/streaming. That keeps the implementation simple and, importantly,
makes Pearson correlations row-aligned and exact for the loaded dataset.

Core functions
--------------
1. Type inference
2. Missing-value analysis
3. Cardinality analysis
4. Rare-category analysis
5. Outlier detection + skewness
6. Class balance
7. Pearson numeric correlation
8. Target association
9. Duplicate detection
10. ID-like detection
11. Quality flags
12. Profile assembler

The analyzer DOES NOT clean, transform, encode, scale, or modify the input
dataset.
"""

from __future__ import annotations

import json
import math
import re
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd


# ============================================================================
# CONFIGURATION
# ============================================================================

class AnalyzerConfig:
    """Configuration for DatasetAnalyzer."""

    # Type inference
    low_cardinality_ratio: float = 0.05
    low_cardinality_max_unique: int = 50
    text_min_avg_length: float = 30.0
    text_min_unique_ratio: float = 0.30
    datetime_parse_threshold: float = 0.90
    datetime_sample_size: int = 100

    # Rare categories
    rare_category_threshold: float = 0.01
    max_rare_categories_sample: int = 10
    max_tracked_categories: int = 10000

    # ID-like detection
    id_like_min_unique: int = 50
    id_like_unique_ratio: float = 0.95

    # Class imbalance
    imbalance_threshold: float = 0.15
    max_target_classes: int = 50

    # Correlation
    high_correlation_threshold: float = 0.85

    # Target association
    leakage_threshold: float = 0.95

    # Output
    round_digits: int = 4


# ============================================================================
# GENERAL HELPERS
# ============================================================================

def _is_numeric_dtype(series: pd.Series) -> bool:
    return pd.api.types.is_numeric_dtype(series)


def _is_datetime_dtype(series: pd.Series) -> bool:
    return pd.api.types.is_datetime64_any_dtype(series)


def _safe_float(value: Any) -> Optional[float]:
    """Convert a value to a normal Python float, or None if impossible."""
    if value is None:
        return None

    try:
        value = float(value)
    except (TypeError, ValueError):
        return None

    if not math.isfinite(value):
        return None

    return value


def _round(value: Any, digits: int = 4) -> Optional[float]:
    value = _safe_float(value)
    if value is None:
        return None
    return round(value, digits)


def _json_safe(value: Any) -> Any:
    """
    Convert pandas/NumPy values recursively into JSON-safe Python values.
    """
    if value is None:
        return None

    if isinstance(value, (np.integer,)):
        return int(value)

    if isinstance(value, (np.floating,)):
        value = float(value)
        return None if not math.isfinite(value) else value

    if isinstance(value, (np.bool_,)):
        return bool(value)

    if isinstance(value, pd.Timestamp):
        return value.isoformat()

    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}

    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]

    if isinstance(value, float) and not math.isfinite(value):
        return None

    return value


def _normalize_for_category(value: Any) -> str:
    """
    Convert a category into a stable string representation for JSON output
    and contingency tables.
    """
    if pd.isna(value):
        return "__MISSING__"

    if isinstance(value, float):
        if value.is_integer():
            return str(int(value))

    return str(value)


# ============================================================================
# 1. TYPE INFERENCE
# ============================================================================

def infer_column_type(
    series: pd.Series,
    config: AnalyzerConfig = AnalyzerConfig(),
) -> str:
    """
    Infer one of:
        numeric
        categorical
        datetime
        text

    Rules:
    - Numeric dtype with very low cardinality -> categorical.
    - Datetime dtype -> datetime.
    - Object/string columns that parse cleanly as dates -> datetime.
    - High-cardinality, long object/string columns -> text.
    - Remaining object/category columns -> categorical.
    """

    # Explicit datetime dtype
    if _is_datetime_dtype(series):
        return "datetime"

    # Numeric columns
    if _is_numeric_dtype(series):
        non_null = series.dropna()
        n_rows = len(series)
        n_unique = non_null.nunique(dropna=True)

        if n_rows == 0:
            return "numeric"

        unique_ratio = n_unique / n_rows

        if (
            n_unique < config.low_cardinality_max_unique
            and unique_ratio < config.low_cardinality_ratio
        ):
            return "categorical"

        return "numeric"

    # String/object/category columns
    non_null = series.dropna()

    if len(non_null) == 0:
        return "categorical"

    # Datetime detection.
    # Only attempt this on strings/objects; categorical columns with arbitrary
    # category labels are not automatically converted to dates.
    if pd.api.types.is_object_dtype(series) or pd.api.types.is_string_dtype(series):
        sample = non_null.astype(str).head(config.datetime_sample_size)

        if len(sample) > 0:
            parsed = pd.to_datetime(sample, errors="coerce")
            parse_ratio = parsed.notna().mean()

            if parse_ratio >= config.datetime_parse_threshold:
                return "datetime"

    # Text detection
    string_values = non_null.astype(str)
    avg_length = float(string_values.str.len().mean())

    n_unique = non_null.nunique(dropna=True)
    unique_ratio = n_unique / len(series)

    if (
        avg_length >= config.text_min_avg_length
        and unique_ratio >= config.text_min_unique_ratio
    ):
        return "text"

    return "categorical"


# ============================================================================
# 2. MISSING VALUE ANALYSIS
# ============================================================================

def analyze_missing_values(
    series: pd.Series,
    round_digits: int = 4,
) -> Dict[str, Any]:
    """Return missing count and missing percentage."""
    n_rows = len(series)
    missing_count = int(series.isna().sum())

    missing_pct = (
        (missing_count / n_rows) * 100
        if n_rows > 0
        else 0.0
    )

    return {
        "missing_count": missing_count,
        "missing_pct": round(missing_pct, round_digits),
    }


# ============================================================================
# 3. CARDINALITY + RARE CATEGORIES
# ============================================================================

def analyze_cardinality(
    series: pd.Series,
    inferred_type: str = "categorical",
    config: AnalyzerConfig = AnalyzerConfig(),
    round_digits: int = 4,
) -> Dict[str, Any]:
    """
    Analyze unique values and rare categories.

    n_rare_categories is the ACTUAL number of rare categories.
    rare_categories_sample contains only a small display sample.
    """

    n_rows = len(series)
    n_unique = int(series.nunique(dropna=True))

    unique_ratio = (
        n_unique / n_rows
        if n_rows > 0
        else 0.0
    )

    result: Dict[str, Any] = {
        "n_unique": n_unique,
        "unique_ratio": round(unique_ratio, round_digits),
        "top_category_share": 0.0,
        "n_rare_categories": 0,
        "rare_categories_sample": [],
    }

    # Cardinality is useful for every column, but rare-category analysis
    # is only meaningful for categorical columns.
    if inferred_type != "categorical":
        return result

    non_null = series.dropna()

    if len(non_null) == 0:
        return result

    # Category frequency analysis.
    # For very high-cardinality columns, value_counts is still exact for an
    # in-memory DataFrame. The tracking limit is used only as a safety guard.
    counts = non_null.value_counts(dropna=True)

    if len(counts) > config.max_tracked_categories:
        # Keep the most frequent categories for top-share calculation.
        # Rare-category count can still be determined directly from the
        # frequency values without storing every category in the output.
        counts_for_output = counts.head(config.max_tracked_categories)
    else:
        counts_for_output = counts

    total = len(non_null)

    if len(counts) > 0:
        result["top_category_share"] = round(
            float(counts.iloc[0] / total),
            round_digits,
        )

    rare_mask = (counts / total) < config.rare_category_threshold
    rare_values = counts.index[rare_mask]

    # IMPORTANT:
    # Count ALL rare categories, but expose only a small sample.
    result["n_rare_categories"] = int(len(rare_values))

    sample = [
        _json_safe(value)
        for value in list(rare_values[:config.max_rare_categories_sample])
    ]

    result["rare_categories_sample"] = sample

    return result


# ============================================================================
# 4. OUTLIER + SKEWNESS ANALYSIS
# ============================================================================

def analyze_numeric_distribution(
    series: pd.Series,
    round_digits: int = 4,
) -> Dict[str, Any]:
    """
    Analyze a numeric column using the IQR method.

    Outliers:
        x < Q1 - 1.5*IQR
        x > Q3 + 1.5*IQR

    Skewness is calculated using pandas' unbiased sample skewness.
    Missing values are excluded from distribution statistics.
    """

    numeric = pd.to_numeric(series, errors="coerce").dropna()

    if len(numeric) == 0:
        return {
            "outlier_count": 0,
            "outlier_pct": 0.0,
            "skew": None,
            "q1": None,
            "q3": None,
            "lower_bound": None,
            "upper_bound": None,
        }

    q1 = float(numeric.quantile(0.25))
    q3 = float(numeric.quantile(0.75))
    iqr = q3 - q1

    lower_bound = q1 - 1.5 * iqr
    upper_bound = q3 + 1.5 * iqr

    outlier_mask = (
        (numeric < lower_bound)
        | (numeric > upper_bound)
    )

    outlier_count = int(outlier_mask.sum())

    outlier_pct = (
        outlier_count / len(numeric) * 100
        if len(numeric) > 0
        else 0.0
    )

    # pandas Series.skew() gives the usual unbiased sample skewness.
    skew_value = numeric.skew()

    return {
        "outlier_count": outlier_count,
        "outlier_pct": round(outlier_pct, round_digits),
        "skew": _round(skew_value, round_digits),
        "q1": _round(q1, round_digits),
        "q3": _round(q3, round_digits),
        "lower_bound": _round(lower_bound, round_digits),
        "upper_bound": _round(upper_bound, round_digits),
    }


# ============================================================================
# 5. CLASS BALANCE
# ============================================================================

def analyze_class_balance(
    target: pd.Series,
    config: AnalyzerConfig = AnalyzerConfig(),
    round_digits: int = 4,
) -> Dict[str, Any]:
    """
    Calculate target class proportions.

    Imbalance is flagged when the smallest class proportion is below the
    configured threshold (default: 15%).
    """

    non_null = target.dropna()

    if len(non_null) == 0:
        return {
            "class_balance": {},
            "imbalance_flag": False,
        }

    counts = non_null.value_counts()

    proportions = counts / len(non_null)

    class_balance = {
        _normalize_for_category(label): round(
            float(prop),
            round_digits,
        )
        for label, prop in proportions.items()
    }

    # A very high number of target classes is not a conventional
    # classification problem, so don't force a binary/multiclass imbalance
    # interpretation onto it.
    if len(counts) > config.max_target_classes:
        imbalance_flag = False
    else:
        smallest_class = float(proportions.min())
        imbalance_flag = smallest_class < config.imbalance_threshold

    return {
        "class_balance": class_balance,
        "imbalance_flag": bool(imbalance_flag),
    }


# ============================================================================
# 6. PEARSON NUMERIC CORRELATION
# ============================================================================

def analyze_numeric_correlations(
    df: pd.DataFrame,
    numeric_columns: List[str],
    config: AnalyzerConfig = AnalyzerConfig(),
    round_digits: int = 4,
) -> Tuple[List[Dict[str, Any]], List[List[Any]]]:
    """
    Calculate pairwise Pearson correlations on the inferred numeric columns.

    Because the full DataFrame is used, values remain row-aligned.

    Returns:
        all_correlations
        high_correlation_pairs
    """

    if len(numeric_columns) < 2:
        return [], []

    numeric_df = df[numeric_columns].apply(
        pd.to_numeric,
        errors="coerce",
    )

    corr = numeric_df.corr(method="pearson")

    all_correlations: List[Dict[str, Any]] = []
    high_correlation_pairs: List[List[Any]] = []

    for i, col_a in enumerate(numeric_columns):
        for col_b in numeric_columns[i + 1:]:
            value = corr.loc[col_a, col_b]

            if pd.isna(value):
                continue

            value_float = float(value)

            all_correlations.append({
                "feature_1": col_a,
                "feature_2": col_b,
                "correlation": round(value_float, round_digits),
            })

            if abs(value_float) >= config.high_correlation_threshold:
                high_correlation_pairs.append([
                    col_a,
                    col_b,
                    round(value_float, round_digits),
                ])

    return all_correlations, high_correlation_pairs


# ============================================================================
# 7. ASSOCIATION HELPERS
# ============================================================================

def _cramers_v(
    x: pd.Series,
    y: pd.Series,
) -> Optional[float]:
    """
    Bias-corrected Cramér's V for two categorical variables.

    Returns a value approximately between 0 and 1.
    """

    data = pd.DataFrame({
        "x": x,
        "y": y,
    }).dropna()

    if data.empty:
        return None

    table = pd.crosstab(data["x"], data["y"])

    if table.shape[0] < 2 or table.shape[1] < 2:
        return 0.0

    observed = table.to_numpy(dtype=float)

    n = observed.sum()

    if n <= 0:
        return None

    row_sums = observed.sum(axis=1, keepdims=True)
    col_sums = observed.sum(axis=0, keepdims=True)

    expected = row_sums @ col_sums / n

    with np.errstate(divide="ignore", invalid="ignore"):
        chi2 = np.nansum(
            np.where(
                expected > 0,
                (observed - expected) ** 2 / expected,
                0.0,
            )
        )

    phi2 = chi2 / n

    r, k = observed.shape

    # Bias correction from Bergsma & Wicher style correction.
    correction = ((k - 1) * (r - 1)) / max(n - 1, 1)

    phi2_corrected = max(
        0.0,
        phi2 - correction,
    )

    r_corrected = r - ((r - 1) ** 2) / max(n - 1, 1)
    k_corrected = k - ((k - 1) ** 2) / max(n - 1, 1)

    denominator = min(
        k_corrected - 1,
        r_corrected - 1,
    )

    if denominator <= 0:
        return 0.0

    value = math.sqrt(phi2_corrected / denominator)

    return max(0.0, min(1.0, value))


def _correlation_ratio(
    categories: pd.Series,
    numeric: pd.Series,
) -> Optional[float]:
    """
    Correlation ratio (eta) between a categorical variable and numeric
    variable.

    Returns a value approximately between 0 and 1.
    """

    data = pd.DataFrame({
        "category": categories,
        "numeric": pd.to_numeric(numeric, errors="coerce"),
    }).dropna()

    if data.empty:
        return None

    values = data["numeric"].to_numpy(dtype=float)
    groups = data["category"]

    if len(values) == 0:
        return None

    overall_mean = values.mean()

    denominator = np.sum((values - overall_mean) ** 2)

    if denominator <= 0:
        return 0.0

    numerator = 0.0

    for _, group in data.groupby("category", observed=True):
        group_values = group["numeric"].to_numpy(dtype=float)

        if len(group_values) == 0:
            continue

        group_mean = group_values.mean()

        numerator += len(group_values) * (
            group_mean - overall_mean
        ) ** 2

    eta = math.sqrt(max(0.0, numerator / denominator))

    return max(0.0, min(1.0, eta))


def _pearson_association(
    x: pd.Series,
    y: pd.Series,
) -> Optional[float]:
    """Pearson correlation between two numeric series."""
    data = pd.DataFrame({
        "x": pd.to_numeric(x, errors="coerce"),
        "y": pd.to_numeric(y, errors="coerce"),
    }).dropna()

    if len(data) < 2:
        return None

    value = data["x"].corr(data["y"], method="pearson")

    if pd.isna(value):
        return None

    return float(value)


# ============================================================================
# 8. TARGET ASSOCIATION
# ============================================================================

def analyze_target_association(
    df: pd.DataFrame,
    target_column: str,
    column_types: Dict[str, str],
    config: AnalyzerConfig = AnalyzerConfig(),
    round_digits: int = 4,
) -> Dict[str, Dict[str, Any]]:
    """
    Measure association between every feature and the target.

    If target is categorical:
        categorical feature → Cramér's V
        numeric feature     → correlation ratio

    If target is numeric:
        numeric feature     → Pearson correlation
        categorical feature → correlation ratio

    Text/datetime features are skipped because this Module 1 version does
    not attempt text or temporal feature extraction.
    """

    if target_column not in df.columns:
        return {}

    target_type = column_types.get(target_column)

    if target_type not in {"numeric", "categorical"}:
        return {}

    results: Dict[str, Dict[str, Any]] = {}

    for column in df.columns:
        if column == target_column:
            continue

        feature_type = column_types.get(column)

        if feature_type not in {"numeric", "categorical"}:
            continue

        score: Optional[float] = None
        method: Optional[str] = None

        if target_type == "categorical":
            if feature_type == "categorical":
                score = _cramers_v(df[column], df[target_column])
                method = "cramers_v"

            elif feature_type == "numeric":
                score = _correlation_ratio(
                    df[target_column].astype(str),
                    pd.to_numeric(df[column], errors="coerce"),
                )
                method = "correlation_ratio"

        elif target_type == "numeric":
            if feature_type == "numeric":
                score = _pearson_association(
                    df[column],
                    df[target_column],
                )
                method = "pearson"

            elif feature_type == "categorical":
                score = _correlation_ratio(
                    df[column].astype(str),
                    pd.to_numeric(df[target_column], errors="coerce"),
                )
                method = "correlation_ratio"

        if score is None or method is None:
            continue

        score_abs = abs(score)

        results[column] = {
            "method": method,
            "score": round(score_abs, round_digits),
            "leakage_risk": bool(
                score_abs >= config.leakage_threshold
            ),
        }

    return results


# ============================================================================
# 9. DUPLICATE DETECTION
# ============================================================================

def count_duplicate_rows(df: pd.DataFrame) -> int:
    """Count duplicate rows excluding the first occurrence."""
    if df.empty:
        return 0

    return int(df.duplicated().sum())


# ============================================================================
# 10. ID-LIKE DETECTION
# ============================================================================

def is_id_like(
    series: pd.Series,
    column_name: str,
    config: AnalyzerConfig = AnalyzerConfig(),
) -> bool:
    """
    Detect likely identifier columns.

    Primary rule:
        n_unique >= configured minimum AND unique_ratio >= configured ratio

    Also considers common ID-like column names.
    """

    n_rows = len(series)

    if n_rows == 0:
        return False

    n_unique = int(series.nunique(dropna=True))
    unique_ratio = n_unique / n_rows

    name = column_name.strip().lower()

    common_id_pattern = re.search(
        r"(^id$|_id$|id_|identifier|uuid|guid)",
        name,
    )

    ratio_based = (
        n_unique >= config.id_like_min_unique
        and unique_ratio >= config.id_like_unique_ratio
    )

    return bool(ratio_based or common_id_pattern)


# ============================================================================
# 11. QUALITY FLAGS
# ============================================================================

def build_column_flags(
    column_name: str,
    profile: Dict[str, Any],
    inferred_type: str,
    target_column: Optional[str],
    config: AnalyzerConfig,
) -> List[str]:
    """Create human-readable flags for a column."""

    flags: List[str] = []

    if target_column == column_name:
        flags.append("target")

    if profile.get("id_like", False):
        flags.append("id_like")

    missing_pct = float(profile.get("missing_pct", 0.0))

    if missing_pct >= 60.0:
        flags.append("high_missing")
    elif missing_pct >= 5.0:
        flags.append("moderate_missing")

    if inferred_type == "numeric":
        outlier_pct = float(profile.get("outlier_pct", 0.0))

        if outlier_pct >= 10.0:
            flags.append("high_outliers")
        elif outlier_pct > 0:
            flags.append("has_outliers")

    n_rare = int(profile.get("n_rare_categories", 0))

    if n_rare > 0:
        flags.append(f"{n_rare}_rare_categories")

    return flags


def build_quality_flags(
    column_profiles: Dict[str, Dict[str, Any]],
    high_correlation_pairs: List[List[Any]],
    target_info: Optional[Dict[str, Any]],
) -> List[str]:
    """Flatten important column/dataset issues into one quality_flags list."""

    flags: List[str] = []

    for column_name, profile in column_profiles.items():
        for flag in profile.get("flags", []):
            flags.append(f"{column_name}:{flag}")

    if target_info and target_info.get("imbalance_flag"):
        flags.append("target:class_imbalance")

    for pair in high_correlation_pairs:
        if len(pair) >= 3:
            flags.append(
                f"high_correlation:{pair[0]}-{pair[1]}"
            )

    return flags


# ============================================================================
# 12. PROFILE ASSEMBLER
# ============================================================================

class DatasetAnalyzer:
    """
    Main analyzer.

    The input is kept as an in-memory DataFrame. No values are modified.
    """

    def __init__(
        self,
        df: pd.DataFrame,
        target_column: Optional[str] = None,
        config: Optional[AnalyzerConfig] = None,
    ):
        if not isinstance(df, pd.DataFrame):
            raise TypeError("df must be a pandas DataFrame")

        if df.empty:
            raise ValueError("Dataset is empty")

        self.df = df.copy()
        self.target_column = target_column
        self.config = config or AnalyzerConfig()

        if target_column is not None and target_column not in self.df.columns:
            raise ValueError(
                f"Target column '{target_column}' not found in dataset"
            )

    @classmethod
    def from_csv(
        cls,
        file_path: str,
        target_column: Optional[str] = None,
        config: Optional[AnalyzerConfig] = None,
        **read_csv_kwargs: Any,
    ) -> "DatasetAnalyzer":
        """Load a CSV into memory and create an analyzer."""
        df = pd.read_csv(file_path, **read_csv_kwargs)

        return cls(
            df=df,
            target_column=target_column,
            config=config,
        )

    def analyze(self) -> Dict[str, Any]:
        """Run the complete Module 1 analysis."""

        df = self.df
        config = self.config

        # ------------------------------------------------------------
        # Duplicate detection
        # ------------------------------------------------------------
        duplicate_count = count_duplicate_rows(df)

        # ------------------------------------------------------------
        # Type inference
        # ------------------------------------------------------------
        column_types: Dict[str, str] = {}

        for column in df.columns:
            column_types[column] = infer_column_type(
                df[column],
                config=config,
            )

        numeric_columns = [
            column
            for column in df.columns
            if column_types[column] == "numeric"
        ]

        categorical_columns = [
            column
            for column in df.columns
            if column_types[column] == "categorical"
        ]

        datetime_columns = [
            column
            for column in df.columns
            if column_types[column] == "datetime"
        ]

        text_columns = [
            column
            for column in df.columns
            if column_types[column] == "text"
        ]

        # ------------------------------------------------------------
        # Column profiles
        # ------------------------------------------------------------
        column_profiles: Dict[str, Dict[str, Any]] = {}

        for column in df.columns:
            series = df[column]
            inferred_type = column_types[column]

            missing = analyze_missing_values(
                series,
                round_digits=config.round_digits,
            )

            cardinality = analyze_cardinality(
                series,
                inferred_type=inferred_type,
                config=config,
                round_digits=config.round_digits,
            )

            id_like = is_id_like(
                series,
                column_name=column,
                config=config,
            )

            profile: Dict[str, Any] = {
                "dtype": str(series.dtype),
                "inferred_type": inferred_type,
                "n_unique": cardinality["n_unique"],
                "unique_ratio": cardinality["unique_ratio"],
                "missing_count": missing["missing_count"],
                "missing_pct": missing["missing_pct"],
                "top_category_share": cardinality["top_category_share"],
                "n_rare_categories": cardinality["n_rare_categories"],
                "rare_categories_sample": cardinality[
                    "rare_categories_sample"
                ],
            }

            if id_like:
                profile["id_like"] = True

            if inferred_type == "numeric":
                distribution = analyze_numeric_distribution(
                    series,
                    round_digits=config.round_digits,
                )
                profile.update(distribution)

                # This explicitly indicates that the distribution statistics
                # were calculated over the complete in-memory column.
                profile["statistics_sampled"] = False

            flags = build_column_flags(
                column_name=column,
                profile=profile,
                inferred_type=inferred_type,
                target_column=self.target_column,
                config=config,
            )

            profile["flags"] = flags

            column_profiles[column] = profile

        # ------------------------------------------------------------
        # Class balance
        # ------------------------------------------------------------
        target_info: Optional[Dict[str, Any]] = None

        if self.target_column is not None:
            target_type = column_types[self.target_column]

            if target_type in {"numeric", "categorical"}:
                balance = analyze_class_balance(
                    df[self.target_column],
                    config=config,
                    round_digits=config.round_digits,
                )

                target_info = {
                    "name": self.target_column,
                    **balance,
                }

        # ------------------------------------------------------------
        # Numeric correlations
        # ------------------------------------------------------------
        numeric_correlations, high_correlation_pairs = (
            analyze_numeric_correlations(
                df=df,
                numeric_columns=numeric_columns,
                config=config,
                round_digits=config.round_digits,
            )
        )

        # ------------------------------------------------------------
        # Target association
        # ------------------------------------------------------------
        target_association: Dict[str, Dict[str, Any]] = {}

        if self.target_column is not None:
            target_association = analyze_target_association(
                df=df,
                target_column=self.target_column,
                column_types=column_types,
                config=config,
                round_digits=config.round_digits,
            )

        # ------------------------------------------------------------
        # Overview
        # ------------------------------------------------------------
        overview = {
            "n_rows": int(df.shape[0]),
            "n_cols": int(df.shape[1]),
            "n_duplicate_rows": duplicate_count,
            "categorical_columns": len(categorical_columns),
            "numeric_columns": len(numeric_columns),
            "datetime_columns": len(datetime_columns),
            "text_columns": len(text_columns),
        }

        # ------------------------------------------------------------
        # Quality flags
        # ------------------------------------------------------------
        quality_flags = build_quality_flags(
            column_profiles=column_profiles,
            high_correlation_pairs=high_correlation_pairs,
            target_info=target_info,
        )

        # ------------------------------------------------------------
        # Final profile
        # ------------------------------------------------------------
        profile = {
            "overview": overview,
            "columns": column_profiles,
            "target": target_info,
            "numeric_correlations": numeric_correlations,
            "high_correlation_pairs": high_correlation_pairs,
            "target_association": target_association,
            "quality_flags": quality_flags,
            "warnings": [],
        }

        return _json_safe(profile)


# ============================================================================
# CONVENIENCE FUNCTION
# ============================================================================

def analyze_dataset(
    data: Any,
    target_column: Optional[str] = None,
    config: Optional[AnalyzerConfig] = None,
    **read_csv_kwargs: Any,
) -> Dict[str, Any]:
    """
    Convenience wrapper.

    Supported input:
        - pandas DataFrame
        - CSV file path
    """

    if isinstance(data, pd.DataFrame):
        analyzer = DatasetAnalyzer(
            df=data,
            target_column=target_column,
            config=config,
        )

    elif isinstance(data, (str, bytes)):
        analyzer = DatasetAnalyzer.from_csv(
            file_path=str(data),
            target_column=target_column,
            config=config,
            **read_csv_kwargs,
        )

    else:
        raise TypeError(
            "data must be a pandas DataFrame or CSV file path"
        )

    return analyzer.analyze()


# ============================================================================
# SAVE / PRINT HELPERS
# ============================================================================

def save_profile(
    profile: Dict[str, Any],
    output_path: str = "dataset_profile.json",
) -> None:
    """Save a dataset profile as formatted JSON."""
    with open(output_path, "w", encoding="utf-8") as file:
        json.dump(
            profile,
            file,
            indent=2,
            ensure_ascii=False,
        )


def print_profile(profile: Dict[str, Any]) -> None:
    """Print the profile as formatted JSON."""
    print(
        json.dumps(
            profile,
            indent=2,
            ensure_ascii=False,
        )
    )


# ============================================================================
# TEST / DEMO
# ============================================================================

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="AutoExplainAI Module 1 — Dataset Analyzer"
    )

    parser.add_argument(
        "csv",
        nargs="?",
        help="Path to CSV dataset",
    )

    parser.add_argument(
        "--target",
        default=None,
        help="Target column name",
    )

    parser.add_argument(
        "--output",
        default="dataset_profile.json",
        help="Output JSON file",
    )

    args = parser.parse_args()

    if not args.csv:
        print(
            "Usage:\n"
            "  python dataset_analyzer.py Titanic-Dataset.csv "
            "--target Survived\n"
        )
        raise SystemExit(0)

    profile = analyze_dataset(
        args.csv,
        target_column=args.target,
    )

    save_profile(
        profile,
        output_path=args.output,
    )

    print_profile(profile)
