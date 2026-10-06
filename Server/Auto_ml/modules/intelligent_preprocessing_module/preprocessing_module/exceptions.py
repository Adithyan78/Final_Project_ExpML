"""Custom exceptions for the preprocessing module.

Keeping a dedicated exception hierarchy makes failures easy to catch and
reason about from calling code (analyzer, model-training layer, UI, etc.)
without those modules needing to know internal implementation details.
"""


class PreprocessingModuleError(Exception):
    """Base class for every error raised by the preprocessing module."""


class RuleValidationError(PreprocessingModuleError):
    """Raised when a YAML rules file fails schema / semantic validation."""


class ConditionEvaluationError(PreprocessingModuleError):
    """Raised when a rule's `condition` expression cannot be safely parsed
    or evaluated (e.g. it uses a disallowed construct, or references a
    column attribute that does not exist)."""


class UnknownActionError(PreprocessingModuleError):
    """Raised when a rule (or a user override) references an action name
    that is not present in the action registry."""


class LeakageError(PreprocessingModuleError):
    """Raised when an operation would risk leaking information from
    validation/test data into a fitted transformer, or from the target
    into the feature set."""


class EngineNotFittedError(PreprocessingModuleError):
    """Raised when `.transform()` is called before `.fit_transform()`."""
