"""Extensible registry of preprocessing actions.

Every action a rule (or a user override) can name must be registered here
exactly once, tagged with the pipeline `stage` it belongs to, and given a
`builder` that returns either:

  * a fitted-on-call sklearn-compatible transformer instance, or
  * the sentinel string "passthrough" (sklearn Pipeline/ColumnTransformer
    both understand this literally), or
  * the sentinel DROP for "remove this column entirely".

Adding a new action (e.g. a Yeo-Johnson power transform) means adding one
entry here -- nothing in the rule engine, YAML schema, or condition
evaluator needs to change.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, NamedTuple

from sklearn.impute import SimpleImputer
from sklearn.preprocessing import (
    OneHotEncoder,
    OrdinalEncoder,
    RobustScaler,
    StandardScaler,
    MinMaxScaler,
)

from .exceptions import UnknownActionError
from .transformers import LeakageSafeTargetEncoder

DROP = "__DROP_COLUMN__"
PASSTHROUGH = "passthrough"


class ActionSpec(NamedTuple):
    name: str
    stage: str  # one of rule_schema.KNOWN_STAGES
    builder: Callable[[Dict[str, Any]], Any]
    requires_y: bool = False


def _build_impute_median(params: Dict[str, Any]):
    return SimpleImputer(strategy="median")


def _build_impute_mean(params: Dict[str, Any]):
    return SimpleImputer(strategy="mean")


def _build_impute_most_frequent(params: Dict[str, Any]):
    return SimpleImputer(strategy="most_frequent")


def _build_impute_constant(params: Dict[str, Any]):
    fill_value = params.get("fill_value", "missing")
    return SimpleImputer(strategy="constant", fill_value=fill_value)


def _build_drop_column(params: Dict[str, Any]):
    return DROP


def _build_one_hot(params: Dict[str, Any]):
    return OneHotEncoder(handle_unknown="ignore", sparse_output=False)


def _build_ordinal_encode(params: Dict[str, Any]):
    return OrdinalEncoder(handle_unknown="use_encoded_value", unknown_value=-1)


def _build_target_encode(params: Dict[str, Any]):
    smoothing = params.get("target_encode_smoothing", 10.0)
    return LeakageSafeTargetEncoder(smoothing=smoothing)


def _build_standard_scale(params: Dict[str, Any]):
    return StandardScaler()


def _build_robust_scale(params: Dict[str, Any]):
    return RobustScaler()


def _build_minmax_scale(params: Dict[str, Any]):
    return MinMaxScaler()


def _build_passthrough(params: Dict[str, Any]):
    return PASSTHROUGH


DEFAULT_ACTION_REGISTRY: Dict[str, ActionSpec] = {
    # -- missing stage --
    "drop_column": ActionSpec("drop_column", "missing", _build_drop_column),
    "impute_median": ActionSpec("impute_median", "missing", _build_impute_median),
    "impute_mean": ActionSpec("impute_mean", "missing", _build_impute_mean),
    "impute_most_frequent": ActionSpec(
        "impute_most_frequent", "missing", _build_impute_most_frequent
    ),
    "impute_constant": ActionSpec("impute_constant", "missing", _build_impute_constant),
    "no_impute": ActionSpec("no_impute", "missing", _build_passthrough),
    # -- scaling stage --
    "standard_scale": ActionSpec("standard_scale", "scaling", _build_standard_scale),
    "robust_scale": ActionSpec("robust_scale", "scaling", _build_robust_scale),
    "minmax_scale": ActionSpec("minmax_scale", "scaling", _build_minmax_scale),
    "no_scale": ActionSpec("no_scale", "scaling", _build_passthrough),
    # -- encoding stage --
    "one_hot": ActionSpec("one_hot", "encoding", _build_one_hot),
    "ordinal_encode": ActionSpec("ordinal_encode", "encoding", _build_ordinal_encode),
    "target_encode": ActionSpec(
        "target_encode", "encoding", _build_target_encode, requires_y=True
    ),
    "no_encode": ActionSpec("no_encode", "encoding", _build_passthrough),
}


class ActionRegistry:
    """Thin wrapper so the engine can be handed a custom/extended registry
    (e.g. from a plugin) without touching module-level global state."""

    def __init__(self, actions: Dict[str, ActionSpec] = None):
        self._actions = dict(actions if actions is not None else DEFAULT_ACTION_REGISTRY)

    def register(self, spec: ActionSpec, overwrite: bool = False) -> None:
        if not overwrite and spec.name in self._actions:
            raise UnknownActionError(
                f"Action {spec.name!r} is already registered; pass overwrite=True to replace it."
            )
        self._actions[spec.name] = spec

    def get(self, name: str) -> ActionSpec:
        try:
            return self._actions[name]
        except KeyError:
            raise UnknownActionError(
                f"Action {name!r} is not registered. Known actions: {sorted(self._actions)}."
            )

    def known_action_names(self) -> set:
        return set(self._actions.keys())

    def build(self, name: str, params: Dict[str, Any]):
        spec = self.get(name)
        return spec.builder(params or {})

    def stage_of(self, name: str) -> str:
        return self.get(name).stage
