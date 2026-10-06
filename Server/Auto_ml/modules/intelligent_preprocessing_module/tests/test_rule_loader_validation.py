import pytest

from Server.Auto_ml.modules.intelligent_preprocessing_module.preprocessing_module.exceptions import ConditionEvaluationError, RuleValidationError
from Server.Auto_ml.modules.intelligent_preprocessing_module.preprocessing_module.rule_loader import load_ruleset

VALID_YAML = """
version: "1.0"
rules:
  - id: r1
    priority: 800
    stage: missing
    condition: "column.missing_pct > 60"
    action: "drop_column"
    reason: "Column {col} is missing too much."
  - id: r2
    priority: 500
    stage: encoding
    condition: "column.type == 'categorical'"
    action: "one_hot"
    reason: "Column {col} is categorical."
"""


def test_valid_ruleset_loads():
    rs = load_ruleset(VALID_YAML)
    assert rs.version == "1.0"
    assert len(rs.rules) == 2


def test_missing_version_key_rejected():
    bad = "rules:\n  - id: r1\n    priority: 1\n    stage: missing\n    condition: \"column.missing_pct > 1\"\n    action: drop_column\n    reason: \"x\"\n"
    with pytest.raises(RuleValidationError):
        load_ruleset(bad)


def test_unsupported_version_rejected():
    bad = VALID_YAML.replace('"1.0"', '"9.9"')
    with pytest.raises(RuleValidationError):
        load_ruleset(bad)


def test_empty_rules_list_rejected():
    bad = "version: \"1.0\"\nrules: []\n"
    with pytest.raises(RuleValidationError):
        load_ruleset(bad)


def test_missing_required_field_rejected():
    bad = """
version: "1.0"
rules:
  - id: r1
    priority: 1
    stage: missing
    action: drop_column
    reason: "x"
"""
    with pytest.raises(RuleValidationError):
        load_ruleset(bad)


def test_duplicate_rule_id_rejected():
    bad = """
version: "1.0"
rules:
  - id: dup
    priority: 1
    stage: missing
    condition: "column.missing_pct > 1"
    action: drop_column
    reason: "x"
  - id: dup
    priority: 2
    stage: missing
    condition: "column.missing_pct > 2"
    action: drop_column
    reason: "y"
"""
    with pytest.raises(RuleValidationError):
        load_ruleset(bad)


def test_invalid_stage_rejected():
    bad = """
version: "1.0"
rules:
  - id: r1
    priority: 1
    stage: not_a_real_stage
    condition: "column.missing_pct > 1"
    action: drop_column
    reason: "x"
"""
    with pytest.raises(RuleValidationError):
        load_ruleset(bad)


def test_non_integer_priority_rejected():
    bad = """
version: "1.0"
rules:
  - id: r1
    priority: "high"
    stage: missing
    condition: "column.missing_pct > 1"
    action: drop_column
    reason: "x"
"""
    with pytest.raises(RuleValidationError):
        load_ruleset(bad)


def test_unknown_action_rejected_when_registry_supplied():
    bad = """
version: "1.0"
rules:
  - id: r1
    priority: 1
    stage: missing
    condition: "column.missing_pct > 1"
    action: "teleport_column_to_mars"
    reason: "x"
"""
    with pytest.raises(RuleValidationError):
        load_ruleset(bad, known_actions={"drop_column", "impute_median"})


def test_malformed_condition_raises_condition_error():
    bad = """
version: "1.0"
rules:
  - id: r1
    priority: 1
    stage: missing
    condition: "column.missing_pct >"
    action: drop_column
    reason: "x"
"""
    with pytest.raises(ConditionEvaluationError):
        load_ruleset(bad)


def test_rules_for_stage_orders_by_priority_desc_then_id():
    rs = load_ruleset(VALID_YAML)
    stage_rules = rs.rules_for_stage("missing")
    assert [r.id for r in stage_rules] == ["r1"]
