"""
Intelligent Preprocessing Module
=================================

A reusable, YAML-driven preprocessing engine:

    result = engine.fit_transform(X_train, y_train, analyzer_profile, user_config=None)
    X_test_final = engine.transform(X_test)

Design principle:  YAML decides -> Python executes -> provenance tracks -> logs record.
"""

from .engine import PreprocessingEngine
from .exceptions import (
    RuleValidationError,
    ConditionEvaluationError,
    UnknownActionError,
    LeakageError,
)

__all__ = [
    "PreprocessingEngine",
    "RuleValidationError",
    "ConditionEvaluationError",
    "UnknownActionError",
    "LeakageError",
]

__version__ = "1.0.0"
