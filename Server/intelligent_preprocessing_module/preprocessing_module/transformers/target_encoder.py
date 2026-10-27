"""
A minimal, dependency-free target encoder.

We avoid a third-party dependency (e.g. `category_encoders`) so the module
has no new hard requirements.

The encoder:

  * is fit ONLY from the data passed to `.fit()` / `.fit_transform()`
    (i.e. training data, when called from inside the engine) -- it never
    looks at anything else,

  * uses additive (m-estimate) smoothing towards the global training-set
    mean/probability of the target, so rare categories don't get a noisy,
    overfit estimate,

  * maps any category seen only at `.transform()` time (i.e. not present
    during `.fit()`) to the global training mean/probability, never raising
    and never peeking at test-time statistics,

  * supports numeric, binary categorical, and multiclass categorical targets,

  * is deterministic: identical input always produces identical output.
"""

from __future__ import annotations

from typing import Optional

import numpy as np
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.utils.validation import check_is_fitted


class LeakageSafeTargetEncoder(BaseEstimator, TransformerMixin):
    """Smoothed target encoding for a single categorical column.

    Parameters
    ----------
    smoothing : float
        Higher values pull rare categories' encoded value closer to the
        global target mean/probability.
    """

    def __init__(self, smoothing: float = 10.0):
        self.smoothing = smoothing

    def fit(self, X, y=None):
        if y is None:
            raise ValueError(
                "LeakageSafeTargetEncoder requires y at fit time (it is a "
                "supervised transform); received y=None."
            )

        col = self._as_1d(X)
        y_arr = np.asarray(y).ravel()

        if len(col) != len(y_arr):
            raise ValueError("X and y must have the same length.")

        # ---------------------------------------------------------
        # Validate smoothing
        # ---------------------------------------------------------
        if self.smoothing < 0:
            raise ValueError("smoothing must be >= 0.")

        # ---------------------------------------------------------
        # Determine target type
        # ---------------------------------------------------------
        self.target_type_ = self._detect_target_type(y_arr)

        # =========================================================
        # NUMERIC TARGET
        # =========================================================
        if self.target_type_ == "numeric":

            y_numeric = y_arr.astype(float)

            self.global_mean_ = float(np.mean(y_numeric))

            categories, counts = np.unique(
                col,
                return_counts=True
            )

            mapping = {}

            for cat, count in zip(categories, counts):

                cat_mean = float(
                    np.mean(y_numeric[col == cat])
                )

                smoothed = (
                    count * cat_mean
                    + self.smoothing * self.global_mean_
                ) / (
                    count + self.smoothing
                )

                mapping[cat] = smoothed

            self.mapping_ = mapping

            # Numeric target does not need class information
            self.target_classes_ = None
            self.target_mapping_ = None

        # =========================================================
        # BINARY CATEGORICAL TARGET
        # =========================================================
        elif self.target_type_ == "binary":

            self.target_classes_ = np.unique(y_arr)

            # Deterministic mapping:
            #
            # class 0 -> 0
            # class 1 -> 1
            #
            self.target_mapping_ = {
                category: float(index)
                for index, category
                in enumerate(self.target_classes_)
            }

            y_numeric = np.array(
                [
                    self.target_mapping_[value]
                    for value in y_arr
                ],
                dtype=float
            )

            self.global_mean_ = float(
                np.mean(y_numeric)
            )

            categories, counts = np.unique(
                col,
                return_counts=True
            )

            mapping = {}

            for cat, count in zip(categories, counts):

                cat_mean = float(
                    np.mean(y_numeric[col == cat])
                )

                smoothed = (
                    count * cat_mean
                    + self.smoothing * self.global_mean_
                ) / (
                    count + self.smoothing
                )

                mapping[cat] = smoothed

            self.mapping_ = mapping

        # =========================================================
        # MULTICLASS CATEGORICAL TARGET
        # =========================================================
        elif self.target_type_ == "multiclass":

            self.target_classes_ = np.unique(y_arr)

            # Deterministic class mapping.
            #
            # IMPORTANT:
            # These numbers are only identifiers.
            # They are NOT averaged for multiclass encoding.
            self.target_mapping_ = {
                category: index
                for index, category
                in enumerate(self.target_classes_)
            }

            categories = np.unique(col)

            # Global probability of every target class
            self.global_probabilities_ = {}

            for target_class in self.target_classes_:

                self.global_probabilities_[target_class] = float(
                    np.mean(y_arr == target_class)
                )

            # Mapping:
            #
            # feature_category ->
            # {
            #     target_class_1: probability,
            #     target_class_2: probability,
            #     ...
            # }
            self.mapping_ = {}

            for cat in categories:

                mask = col == cat
                category_targets = y_arr[mask]

                category_count = len(category_targets)

                class_probabilities = {}

                for target_class in self.target_classes_:

                    class_count = np.sum(
                        category_targets == target_class
                    )

                    # Raw probability for this category
                    category_probability = (
                        class_count / category_count
                    )

                    # Global probability for this target class
                    global_probability = (
                        self.global_probabilities_[target_class]
                    )

                    # M-estimate smoothing
                    smoothed_probability = (
                        category_count * category_probability
                        + self.smoothing * global_probability
                    ) / (
                        category_count + self.smoothing
                    )

                    class_probabilities[target_class] = (
                        float(smoothed_probability)
                    )

                self.mapping_[cat] = class_probabilities

            # Not needed for multiclass calculations,
            # but kept for consistency.
            self.global_mean_ = float(
                np.mean(
                    [
                        self.target_mapping_[value]
                        for value in y_arr
                    ]
                )
            )

        else:
            raise ValueError(
                f"Unsupported target type: {self.target_type_}"
            )

        self.n_features_in_ = 1

        return self

    def transform(self, X):
        check_is_fitted(
            self,
            [
                "mapping_",
                "target_type_"
            ]
        )

        col = self._as_1d(X)

        # =========================================================
        # NUMERIC TARGET
        # =========================================================
        if self.target_type_ == "numeric":

            out = np.array(
                [
                    self.mapping_.get(
                        value,
                        self.global_mean_
                    )
                    for value in col
                ],
                dtype=float
            ).reshape(-1, 1)

            return out

        # =========================================================
        # BINARY TARGET
        # =========================================================
        if self.target_type_ == "binary":

            out = np.array(
                [
                    self.mapping_.get(
                        value,
                        self.global_mean_
                    )
                    for value in col
                ],
                dtype=float
            ).reshape(-1, 1)

            return out

        # =========================================================
        # MULTICLASS TARGET
        # =========================================================
        if self.target_type_ == "multiclass":

            result = []

            for value in col:

                # -------------------------------------------------
                # Category was present during training
                # -------------------------------------------------
                if value in self.mapping_:

                    encoded = self.mapping_[value]

                # -------------------------------------------------
                # Unseen category during transform
                #
                # Use GLOBAL TRAINING probabilities.
                #
                # Never calculate anything from test data.
                # -------------------------------------------------
                else:

                    encoded = self.global_probabilities_

                row = [
                    encoded[target_class]
                    for target_class
                    in self.target_classes_
                ]

                result.append(row)

            return np.asarray(
                result,
                dtype=float
            )

        raise ValueError(
            f"Unsupported target type: {self.target_type_}"
        )

    def get_feature_names_out(self, input_features=None):

        # ---------------------------------------------------------
        # Determine original feature name
        # ---------------------------------------------------------
        if input_features is None:
            feature_name = "target_encoded"

        else:
            input_features = np.asarray(
                input_features,
                dtype=object
            )

            if len(input_features) != 1:
                raise ValueError(
                    "LeakageSafeTargetEncoder only supports "
                    "a single input feature."
                )

            feature_name = str(
                input_features[0]
            )

        # ---------------------------------------------------------
        # Multiclass target
        #
        # Produce one feature per target class.
        # ---------------------------------------------------------
        if (
            hasattr(self, "target_type_")
            and self.target_type_ == "multiclass"
        ):

            return np.asarray(
                [
                    f"{feature_name}_target_{str(target_class)}"
                    for target_class
                    in self.target_classes_
                ],
                dtype=object
            )

        # ---------------------------------------------------------
        # Numeric / binary target
        #
        # Produce one encoded feature.
        # ---------------------------------------------------------
        return np.asarray(
            [
                f"{feature_name}_target_enc"
            ],
            dtype=object
        )

    @staticmethod
    def _detect_target_type(y_arr: np.ndarray) -> str:
        """Detect whether the target is numeric, binary, or multiclass."""

        # ---------------------------------------------------------
        # First try numeric conversion.
        # ---------------------------------------------------------
        try:

            y_numeric = y_arr.astype(float)

            # Numeric target
            #
            # This includes:
            #   regression targets
            #   already-numeric classification targets
            #
            if np.all(np.isfinite(y_numeric)):
                return "numeric"

        except (ValueError, TypeError):

            pass

        # ---------------------------------------------------------
        # Categorical target
        # ---------------------------------------------------------
        unique_values = np.unique(y_arr)

        if len(unique_values) == 2:
            return "binary"

        if len(unique_values) > 2:
            return "multiclass"

        raise ValueError(
            "Target must contain at least two unique values."
        )

    @staticmethod
    def _as_1d(X) -> np.ndarray:

        arr = np.asarray(X)

        if arr.ndim == 2:

            if arr.shape[1] != 1:
                raise ValueError(
                    "LeakageSafeTargetEncoder only supports a single "
                    "column, "
                    f"got shape {arr.shape}."
                )

            arr = arr.ravel()

        elif arr.ndim != 1:

            raise ValueError(
                "Input must be a 1D array or a 2D array with one column."
            )

        # ---------------------------------------------------------
        # Treat missing values as their own category rather than
        # crashing.
        #
        # Upstream missing-value handling should normally run first.
        # ---------------------------------------------------------
        cleaned = []

        for value in arr:

            if value is None:

                cleaned.append("__MISSING__")

            elif isinstance(value, float) and np.isnan(value):

                cleaned.append("__MISSING__")

            else:

                cleaned.append(value)

        return np.asarray(
            cleaned,
            dtype=object
        )