"""Build the feature-provenance log: for every OUTPUT feature produced by
the fitted ColumnTransformer, record which raw column it came from and
which transformation(s) produced it, e.g.:

    {"output_feature": "Sex_male", "source_column": "Sex", "transformation": "one_hot"}
"""

from __future__ import annotations

from typing import Any, Dict, List

from sklearn.compose import ColumnTransformer

from .rule_engine import Decision

_NOOP_ACTIONS = {"skipped", "no_impute", "no_scale", "no_encode"}


def _transformation_label(decisions: List[Decision]) -> str:
    applied = [d.action for d in decisions if d.action not in _NOOP_ACTIONS]
    return "+".join(applied) if applied else "passthrough"


def build_feature_provenance(
    fitted_column_transformer: ColumnTransformer,
    decisions_by_column: Dict[str, List[Decision]],
) -> List[Dict[str, Any]]:
    provenance: List[Dict[str, Any]] = []

    for name, trans, cols in fitted_column_transformer.transformers_:
        if name == "remainder":
            continue
        if trans == "drop":
            continue

        source_col = cols[0] if isinstance(cols, (list, tuple)) else cols
        transformation = _transformation_label(decisions_by_column.get(source_col, []))

        if trans == "passthrough":
            output_names = list(cols) if isinstance(cols, (list, tuple)) else [cols]
        elif hasattr(trans, "get_feature_names_out"):
            output_names = list(trans.get_feature_names_out(cols))
        else:  # pragma: no cover - defensive fallback for exotic custom transformers
            output_names = list(cols)

        for output_feature in output_names:
            provenance.append(
                {
                    "output_feature": output_feature,
                    "source_column": source_col,
                    "transformation": transformation,
                }
            )

    return provenance
