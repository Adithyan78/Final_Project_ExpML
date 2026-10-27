"""Translate the analyzer's profile JSON into the flat per-column "facts"
dictionaries that rule conditions are evaluated against (exposed as the
`column` variable, e.g. `column.missing_pct`).

This is the ONLY place that needs to know the analyzer's JSON schema. If
the analyzer's profile format changes, this adapter is what should change
-- the rule engine, condition evaluator and action registry stay generic.
"""

from __future__ import annotations

from typing import Any, Dict, List

# Fields copied straight through from analyzer_profile["columns"][col] into
# the per-column facts dict, if present. Anything not listed here that a
# custom analyzer profile happens to include is passed through too (see
# build_column_facts), so extending the analyzer does not require
# touching this file for run-of-the-mill additional numeric/boolean facts.
_PASSTHROUGH_FIELDS = (
    "dtype",
    "n_unique",
    "unique_ratio",
    "missing_count",
    "missing_pct",
    "top_category_share",
    "n_rare_categories",
    "outlier_count",
    "outlier_pct",
    "skew",
    "q1",
    "q3",
    "lower_bound",
    "upper_bound",
    "statistics_sampled",
)


def _normalize_type(inferred_type: str) -> str:
    inferred_type = (inferred_type or "").lower()
    if inferred_type in ("numeric", "number", "numerical"):
        return "numeric"
    if inferred_type in ("categorical", "category"):
        return "categorical"
    # Fall back to the raw value so an unusual analyzer type at least
    # participates in equality checks like `column.type == 'text'`.
    return inferred_type


def build_column_facts(
    analyzer_profile: Dict[str, Any], column: str
) -> Dict[str, Any]:
    """Build the fact dict for a single column, merging:
      * analyzer_profile["columns"][column]        (per-column stats)
      * analyzer_profile["target_association"][column]  (score/leakage)
    """
    columns_section = analyzer_profile.get("columns", {}) or {}
    col_info = dict(columns_section.get(column, {}) or {})

    facts: Dict[str, Any] = {"name": column, "cardinality": col_info.get("n_unique")}

    for field in _PASSTHROUGH_FIELDS:
        if field in col_info:
            facts[field] = col_info[field]

    # Pass through ANY other scalar/list field the analyzer happens to
    # provide, so future analyzer fields are usable in rule conditions
    # without a code change here.
    for key, value in col_info.items():
        facts.setdefault(key, value)

    facts["type"] = _normalize_type(col_info.get("inferred_type", ""))
    facts["id_like"] = bool(col_info.get("id_like", False))
    facts["flags"] = list(col_info.get("flags", []) or [])

    target_assoc = (analyzer_profile.get("target_association", {}) or {}).get(column)
    if target_assoc:
        facts["target_association_score"] = target_assoc.get("score")
        facts["target_association_method"] = target_assoc.get("method")
        facts["target_leakage_risk"] = bool(target_assoc.get("leakage_risk", False))
    else:
        facts["target_association_score"] = None
        facts["target_association_method"] = None
        facts["target_leakage_risk"] = False

    return facts


def build_all_column_facts(
    analyzer_profile: Dict[str, Any], columns: List[str]
) -> Dict[str, Dict[str, Any]]:
    return {col: build_column_facts(analyzer_profile, col) for col in columns}


def target_column_name(analyzer_profile: Dict[str, Any]) -> str:
    return (analyzer_profile.get("target", {}) or {}).get("name")
