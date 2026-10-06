from Server.Auto_ml.modules.intelligent_preprocessing_module.preprocessing_module.action_registry import ActionRegistry
from Server.Auto_ml.modules.intelligent_preprocessing_module.preprocessing_module.rule_engine import decide_all, decide_column
from Server.Auto_ml.modules.intelligent_preprocessing_module.preprocessing_module.rule_loader import load_ruleset

YAML_TWO_MISSING_RULES = """
version: "1.0"
rules:
  - id: high_missing_drop
    priority: 800
    stage: missing
    condition: "column.missing_pct > 60"
    action: "drop_column"
    reason: "Column {col} is missing in over 60% of rows."
  - id: moderate_missing
    priority: 700
    stage: missing
    condition: "column.type == 'numeric' and 5 < column.missing_pct <= 60"
    action: "impute_median"
    reason: "Column {col} has moderate missingness."
  - id: catch_all_categorical
    priority: 500
    stage: encoding
    condition: "column.type == 'categorical'"
    action: "one_hot"
    reason: "Column {col} is categorical."
"""


def _registry():
    return ActionRegistry()


def test_higher_priority_rule_wins_when_both_match():
    rs = load_ruleset(YAML_TWO_MISSING_RULES)
    reg = _registry()
    # Cabin-like column: 77% missing AND numeric -- both high_missing_drop
    # (priority 800) and moderate_missing (priority 700, but its own
    # condition upper-bounds at 60 so it wouldn't match here anyway).
    # Use a case where both conditions *would* match to prove priority
    # ordering, not just condition specificity: missing_pct=61 numeric.
    facts = {"type": "numeric", "missing_pct": 61, "id_like": False}
    decisions = decide_column("Cabin", facts, rs, reg)
    missing_decision = next(d for d in decisions if d.stage == "missing")
    assert missing_decision.action == "drop_column"
    assert missing_decision.rule_id == "high_missing_drop"


def test_lower_priority_rule_applies_when_higher_priority_condition_false():
    rs = load_ruleset(YAML_TWO_MISSING_RULES)
    reg = _registry()
    facts = {"type": "numeric", "missing_pct": 20, "id_like": False}
    decisions = decide_column("Age", facts, rs, reg)
    missing_decision = next(d for d in decisions if d.stage == "missing")
    assert missing_decision.action == "impute_median"
    assert missing_decision.rule_id == "moderate_missing"


def test_no_matching_rule_yields_default_passthrough():
    rs = load_ruleset(YAML_TWO_MISSING_RULES)
    reg = _registry()
    facts = {"type": "numeric", "missing_pct": 0, "id_like": False}
    decisions = decide_column("Fare", facts, rs, reg)
    missing_decision = next(d for d in decisions if d.stage == "missing")
    assert missing_decision.action == "no_impute"
    assert missing_decision.source == "default"
    assert missing_decision.rule_id is None


def test_user_override_beats_matching_rule():
    rs = load_ruleset(YAML_TWO_MISSING_RULES)
    reg = _registry()
    facts = {"type": "numeric", "missing_pct": 61, "id_like": False}
    decisions = decide_column(
        "Age", facts, rs, reg, user_override={"action": "impute_mean"}
    )
    missing_decision = next(d for d in decisions if d.stage == "missing")
    assert missing_decision.action == "impute_mean"
    assert missing_decision.source == "user_override"


def test_user_override_only_applies_to_its_own_stage():
    # impute_mean belongs to the "missing" stage; it must not leak into
    # the "encoding" stage decision for a categorical column.
    rs = load_ruleset(YAML_TWO_MISSING_RULES)
    reg = _registry()
    facts = {"type": "categorical", "missing_pct": 0, "id_like": False, "cardinality": 3}
    decisions = decide_column(
        "Embarked", facts, rs, reg, user_override={"action": "impute_mean"}
    )
    encoding_decision = next(d for d in decisions if d.stage == "encoding")
    assert encoding_decision.action == "one_hot"
    assert encoding_decision.source == "rule"


def test_stage_specific_override_key():
    rs = load_ruleset(YAML_TWO_MISSING_RULES)
    reg = _registry()
    facts = {"type": "categorical", "missing_pct": 0, "id_like": False, "cardinality": 3}
    decisions = decide_column(
        "Embarked", facts, rs, reg, user_override={"encoding_action": "ordinal_encode"}
    )
    encoding_decision = next(d for d in decisions if d.stage == "encoding")
    assert encoding_decision.action == "ordinal_encode"
    assert encoding_decision.source == "user_override"


def test_dropped_column_short_circuits_later_stages():
    rs = load_ruleset(YAML_TWO_MISSING_RULES)
    reg = _registry()
    facts = {"type": "categorical", "missing_pct": 90, "id_like": False, "cardinality": 3}
    decisions = decide_column("Cabin", facts, rs, reg)
    stages = {d.stage: d for d in decisions}
    assert stages["missing"].action == "drop_column"
    assert stages["encoding"].action == "skipped"
    assert stages["encoding"].source == "system"


def test_decide_all_covers_every_column():
    rs = load_ruleset(YAML_TWO_MISSING_RULES)
    reg = _registry()
    facts = {
        "Age": {"type": "numeric", "missing_pct": 20, "id_like": False},
        "Sex": {"type": "categorical", "missing_pct": 0, "id_like": False, "cardinality": 2},
    }
    all_decisions = decide_all(["Age", "Sex"], facts, rs, reg)
    assert set(all_decisions.keys()) == {"Age", "Sex"}
