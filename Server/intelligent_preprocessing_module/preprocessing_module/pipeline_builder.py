"""Turn the per-column, per-stage Decisions produced by the rule engine
into a single fitted-together `sklearn.compose.ColumnTransformer`.

Each surviving (non-dropped) column becomes one entry in the
ColumnTransformer, built as a small `Pipeline` chaining its stages in a
fixed order (missing -> scaling|encoding). Dropped columns are simply
left out of the ColumnTransformer (equivalent to `drop`), and are
reported separately so callers know which raw columns produced zero
output features.
"""

from __future__ import annotations

from typing import Any, Dict, List, Tuple

from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline

from .action_registry import DROP, ActionRegistry
from .rule_engine import Decision

# Fixed intra-column execution order. `missing` always runs first because
# imputation must happen before scaling/encoding can act on clean values.
_STAGE_ORDER = {"missing": 0, "scaling": 1, "encoding": 1}


def _sort_stage_decisions(decisions: List[Decision]) -> List[Decision]:
    return sorted(decisions, key=lambda d: _STAGE_ORDER.get(d.stage, 99))


def build_column_transformer(
    columns: List[str],
    decisions_by_column: Dict[str, List[Decision]],
    action_registry: ActionRegistry,
    action_params: Dict[str, Any] = None,
) -> Tuple[ColumnTransformer, List[str]]:
    """Returns (column_transformer, dropped_columns)."""
    action_params = action_params or {}
    transformers: List[Tuple[str, Any, List[str]]] = []
    dropped_columns: List[str] = []

    for col in columns:
        stage_decisions = _sort_stage_decisions(decisions_by_column[col])

        steps = []
        column_dropped = False
        for decision in stage_decisions:
            if decision.action == "skipped":
                continue
            built = action_registry.build(decision.action, action_params)
            if built == DROP:
                column_dropped = True
                break
            steps.append((decision.stage, built))

        if column_dropped:
            dropped_columns.append(col)
            continue

        if not steps:
            # Every stage was a no-op default; still an explicit,
            # provenance-tracked passthrough rather than an implicit one.
            transformers.append((col, "passthrough", [col]))
        elif len(steps) == 1:
            transformers.append((col, steps[0][1], [col]))
        else:
            transformers.append((col, Pipeline(steps), [col]))

    column_transformer = ColumnTransformer(
        transformers=transformers,
        remainder="drop",
        verbose_feature_names_out=False,
    )
    return column_transformer, dropped_columns
