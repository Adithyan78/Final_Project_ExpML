import pytest

from Server.Auto_ml.modules.intelligent_preprocessing_module.preprocessing_module.condition_evaluator import CompiledCondition
from Server.Auto_ml.modules.intelligent_preprocessing_module.preprocessing_module.exceptions import ConditionEvaluationError


def _cond(expr):
    return CompiledCondition.build(expr)


def test_simple_numeric_comparison():
    c = _cond("column.missing_pct > 60")
    assert c.evaluate({"missing_pct": 77.1}) is True
    assert c.evaluate({"missing_pct": 10.0}) is False


def test_chained_comparison_and_boolean_and():
    c = _cond("column.type == 'numeric' and 5 < column.missing_pct <= 60")
    assert c.evaluate({"type": "numeric", "missing_pct": 19.86}) is True
    assert c.evaluate({"type": "numeric", "missing_pct": 61}) is False
    assert c.evaluate({"type": "categorical", "missing_pct": 20}) is False


def test_boolean_or_and_not():
    c = _cond("column.type == 'categorical' or not column.id_like")
    assert c.evaluate({"type": "categorical", "id_like": False}) is True
    assert c.evaluate({"type": "numeric", "id_like": False}) is True
    assert c.evaluate({"type": "numeric", "id_like": True}) is False


def test_membership_in_list():
    c = _cond("'high_missing' in column.flags")
    assert c.evaluate({"flags": ["high_missing", "139_rare_categories"]}) is True
    assert c.evaluate({"flags": []}) is False


def test_boolean_literal_comparison():
    # YAML-style lowercase `true` is not a valid Python name/literal, and
    # must be rejected at build (validation) time, not silently accepted.
    with pytest.raises(ConditionEvaluationError):
        _cond("column.id_like == true")


def test_correct_boolean_literal_form():
    c = _cond("column.id_like == True")
    assert c.evaluate({"id_like": True}) is True
    assert c.evaluate({"id_like": False}) is False


def test_missing_attribute_resolves_to_none_not_crash_on_equality():
    c = _cond("column.some_undeclared_field == None")
    assert c.evaluate({}) is True


@pytest.mark.parametrize(
    "malicious",
    [
        "__import__('os').system('echo hi')",
        "column.__class__",
        "[x for x in range(10)]",
        "open('/etc/passwd').read()",
        "column.missing_pct.__class__",
        "some_other_name.missing_pct > 1",
        "(lambda: 1)()",
        "column.a.b",
    ],
)
def test_disallowed_constructs_are_rejected(malicious):
    with pytest.raises(ConditionEvaluationError):
        CompiledCondition.build(malicious)


def test_syntax_error_is_reported_clearly():
    with pytest.raises(ConditionEvaluationError):
        CompiledCondition.build("column.missing_pct >")
