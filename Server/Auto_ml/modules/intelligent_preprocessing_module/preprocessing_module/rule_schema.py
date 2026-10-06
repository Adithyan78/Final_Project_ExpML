"""Schema + validation for the versioned YAML rules file.

The rules file format is:

    version: "1.0"
    rules:
      - id: high_missing_drop
        priority: 800
        stage: missing
        condition: "column.missing_pct > 60"
        action: "drop_column"
        reason: "Column {col} is missing in over 60% of rows."

Validation is intentionally strict: a malformed rules file should fail
loudly at load time (RuleValidationError) rather than silently doing the
wrong thing during a fit().
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .condition_evaluator import CompiledCondition
from .exceptions import RuleValidationError

SUPPORTED_RULESET_VERSIONS = {"1.0"}

# Stages are processed in this fixed order for any single column. A rule
# is free to target any stage; "missing" conditions are generally checked
# first since a dropped column short-circuits every later stage.
KNOWN_STAGES = ("missing", "scaling", "encoding")

REQUIRED_RULE_FIELDS = ("id", "priority", "stage", "condition", "action", "reason")


@dataclass
class Rule:
    id: str
    priority: int
    stage: str
    condition_raw: str
    action: str
    reason_template: str
    compiled_condition: CompiledCondition = field(repr=False)

    def matches(self, column_facts: Dict[str, Any]) -> bool:
        return self.compiled_condition.evaluate(column_facts)

    def render_reason(self, col: str) -> str:
        try:
            return self.reason_template.format(col=col)
        except (KeyError, IndexError):
            # A reason template with an unexpected placeholder shouldn't
            # crash the whole engine -- fall back to the raw template.
            return self.reason_template


@dataclass
class RuleSet:
    version: str
    rules: List[Rule]

    def rules_for_stage(self, stage: str) -> List[Rule]:
        # Highest priority first; ties broken by rule id for determinism.
        return sorted(
            (r for r in self.rules if r.stage == stage),
            key=lambda r: (-r.priority, r.id),
        )


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise RuleValidationError(message)


def validate_and_build_ruleset(
    raw: Dict[str, Any], known_actions: Optional[set] = None
) -> RuleSet:
    """Validate a parsed YAML document and build a RuleSet.

    `known_actions`, when provided, causes every rule's `action` field to
    be checked against the action registry at load time so typos are
    caught immediately instead of at fit() time.
    """
    _require(isinstance(raw, dict), "Rules file must be a YAML mapping at the top level.")
    _require("version" in raw, "Rules file is missing required top-level key 'version'.")
    _require("rules" in raw, "Rules file is missing required top-level key 'rules'.")

    version = str(raw["version"])
    _require(
        version in SUPPORTED_RULESET_VERSIONS,
        f"Unsupported rules file version {version!r}. "
        f"Supported versions: {sorted(SUPPORTED_RULESET_VERSIONS)}.",
    )

    raw_rules = raw["rules"]
    _require(isinstance(raw_rules, list) and len(raw_rules) > 0, "'rules' must be a non-empty list.")

    seen_ids = set()
    rules: List[Rule] = []
    for idx, raw_rule in enumerate(raw_rules):
        _require(isinstance(raw_rule, dict), f"Rule at index {idx} must be a mapping.")
        missing_fields = [f for f in REQUIRED_RULE_FIELDS if f not in raw_rule]
        _require(
            not missing_fields,
            f"Rule at index {idx} is missing required field(s): {missing_fields}.",
        )

        rule_id = str(raw_rule["id"])
        _require(rule_id not in seen_ids, f"Duplicate rule id {rule_id!r}.")
        seen_ids.add(rule_id)

        _require(
            isinstance(raw_rule["priority"], int),
            f"Rule {rule_id!r}: 'priority' must be an integer.",
        )

        stage = str(raw_rule["stage"])
        _require(
            stage in KNOWN_STAGES,
            f"Rule {rule_id!r}: 'stage' {stage!r} is not one of {KNOWN_STAGES}.",
        )

        action = str(raw_rule["action"])
        if known_actions is not None:
            _require(
                action in known_actions,
                f"Rule {rule_id!r}: action {action!r} is not registered. "
                f"Known actions: {sorted(known_actions)}.",
            )

        condition_raw = str(raw_rule["condition"])
        compiled = CompiledCondition.build(condition_raw)  # raises ConditionEvaluationError

        reason_template = str(raw_rule["reason"])

        rules.append(
            Rule(
                id=rule_id,
                priority=raw_rule["priority"],
                stage=stage,
                condition_raw=condition_raw,
                action=action,
                reason_template=reason_template,
                compiled_condition=compiled,
            )
        )

    return RuleSet(version=version, rules=rules)
