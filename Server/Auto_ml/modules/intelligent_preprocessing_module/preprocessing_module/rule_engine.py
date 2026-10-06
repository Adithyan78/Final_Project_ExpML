"""Applies a RuleSet (+ optional user overrides) to every column of a
dataset and produces an ordered list of preprocessing Decisions.

Precedence, per column per stage:

    1. user_config override for that column/stage   (highest)
    2. highest-priority matching YAML rule for that stage
    3. a neutral "no matching rule" default (passthrough)

If a column is dropped at the `missing` stage, every later stage for that
column is short-circuited (recorded as "skipped", not silently omitted).
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Optional

from .action_registry import ActionRegistry
from .exceptions import UnknownActionError
from .rule_schema import RuleSet

STAGE_SEQUENCE_NUMERIC = ("missing", "scaling")
STAGE_SEQUENCE_CATEGORICAL = ("missing", "encoding")

_DEFAULT_ACTION_BY_STAGE = {
    "missing": "no_impute",
    "scaling": "no_scale",
    "encoding": "no_encode",
}


@dataclass
class Decision:
    column: str
    stage: str
    action: str
    reason: str
    rule_id: Optional[str]
    source: str  # "user_override" | "rule" | "default" | "system"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _stage_sequence_for(column_type: str) -> tuple:
    if column_type == "numeric":
        return STAGE_SEQUENCE_NUMERIC
    # Categorical, and anything unrecognized, is routed through the
    # encoding stage rather than silently dropped.
    return STAGE_SEQUENCE_CATEGORICAL


def _resolve_override_action(
    override: Dict[str, Any], stage: str, action_registry: ActionRegistry
) -> Optional[str]:
    stage_key = f"{stage}_action"
    if stage_key in override:
        return override[stage_key]
    if "action" in override:
        candidate = override["action"]
        # A bare {"action": ...} override only applies at the stage that
        # action is actually registered for, so a single override dict
        # can't accidentally clobber an unrelated stage.
        try:
            if action_registry.stage_of(candidate) == stage:
                return candidate
        except UnknownActionError:
            raise
    return None


def decide_column(
    column: str,
    facts: Dict[str, Any],
    ruleset: RuleSet,
    action_registry: ActionRegistry,
    user_override: Optional[Dict[str, Any]] = None,
) -> List[Decision]:
    decisions: List[Decision] = []
    stages = _stage_sequence_for(facts.get("type"))

    dropped = False
    for stage in stages:
        if dropped:
            decisions.append(
                Decision(
                    column=column,
                    stage=stage,
                    action="skipped",
                    reason=f"Column '{column}' was dropped in an earlier stage; "
                    f"'{stage}' stage skipped.",
                    rule_id=None,
                    source="system",
                )
            )
            continue

        chosen_action = None
        source = None
        rule_id = None
        reason = None

        if user_override:
            chosen_action = _resolve_override_action(user_override, stage, action_registry)
            if chosen_action is not None:
                source = "user_override"
                reason = (
                    f"User override: action '{chosen_action}' explicitly requested "
                    f"for column '{column}'."
                )

        if chosen_action is None:
            for rule in ruleset.rules_for_stage(stage):
                if rule.matches(facts):
                    chosen_action = rule.action
                    source = "rule"
                    rule_id = rule.id
                    reason = rule.render_reason(column)
                    break

        if chosen_action is None:
            chosen_action = _DEFAULT_ACTION_BY_STAGE[stage]
            source = "default"
            reason = (
                f"No rule matched column '{column}' at stage '{stage}'; "
                f"leaving it unchanged at this stage."
            )

        # Validate early -- an override or rule pointing at an unknown
        # action should fail loudly and specifically, not deep inside
        # sklearn's fit().
        action_registry.get(chosen_action)

        decisions.append(
            Decision(
                column=column,
                stage=stage,
                action=chosen_action,
                reason=reason,
                rule_id=rule_id,
                source=source,
            )
        )

        if stage == "missing" and chosen_action == "drop_column":
            dropped = True

    return decisions


def decide_all(
    columns: List[str],
    column_facts: Dict[str, Dict[str, Any]],
    ruleset: RuleSet,
    action_registry: ActionRegistry,
    user_config: Optional[Dict[str, Dict[str, Any]]] = None,
) -> Dict[str, List[Decision]]:
    user_config = user_config or {}
    result = {}
    for col in columns:
        result[col] = decide_column(
            col,
            column_facts[col],
            ruleset,
            action_registry,
            user_override=user_config.get(col),
        )
    return result
