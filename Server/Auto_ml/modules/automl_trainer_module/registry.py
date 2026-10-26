"""Model registry: every classical-ML candidate, its default factory and tuning space."""
from __future__ import annotations

import importlib.util
from dataclasses import dataclass, field
from typing import Any, Callable

from scipy.stats import loguniform, randint, uniform
from sklearn.dummy import DummyClassifier, DummyRegressor
from sklearn.ensemble import (
    AdaBoostClassifier,
    ExtraTreesClassifier,
    ExtraTreesRegressor,
    GradientBoostingClassifier,
    GradientBoostingRegressor,
    HistGradientBoostingClassifier,
    HistGradientBoostingRegressor,
    RandomForestClassifier,
    RandomForestRegressor,
)
from sklearn.linear_model import ElasticNet, LogisticRegression, Ridge
from sklearn.naive_bayes import GaussianNB
from sklearn.neighbors import KNeighborsClassifier, KNeighborsRegressor
from sklearn.svm import SVC, SVR
from sklearn.tree import DecisionTreeClassifier, DecisionTreeRegressor


@dataclass
class ModelSpec:
    name: str
    task: str
    family: str                                 # linear | tree | bagging | boosting | kernel | distance | bayes | baseline
    factory: Callable[[dict, int], Any]         # (context, seed) -> unfitted estimator
    space: dict = field(default_factory=dict)   # RandomizedSearchCV distributions
    requires: str | None = None                 # optional third-party import
    baseline: bool = False

    @property
    def available(self) -> bool:
        return self.requires is None or importlib.util.find_spec(self.requires) is not None


def _bal(ctx):
    return "balanced" if ctx.get("imbalanced") else None


def _xgb_clf(ctx, seed):
    from xgboost import XGBClassifier
    return XGBClassifier(n_estimators=200, eval_metric="logloss", n_jobs=1, random_state=seed, verbosity=0)


def _xgb_reg(ctx, seed):
    from xgboost import XGBRegressor
    return XGBRegressor(n_estimators=200, n_jobs=1, random_state=seed, verbosity=0)


def _lgbm_clf(ctx, seed):
    from lightgbm import LGBMClassifier
    return LGBMClassifier(n_estimators=200, n_jobs=1, random_state=seed, verbose=-1, class_weight=_bal(ctx))


def _lgbm_reg(ctx, seed):
    from lightgbm import LGBMRegressor
    return LGBMRegressor(n_estimators=200, n_jobs=1, random_state=seed, verbose=-1)


_TREE = {"n_estimators": randint(100, 500), "max_depth": [None, 4, 6, 8, 12, 20],
         "min_samples_leaf": randint(1, 10), "max_features": ["sqrt", "log2", 0.5]}
_BOOST = {"n_estimators": randint(100, 500), "learning_rate": loguniform(0.01, 0.3),
          "max_depth": randint(2, 7), "subsample": uniform(0.6, 0.4)}
_XGB = {**_BOOST, "colsample_bytree": uniform(0.5, 0.5)}
_LGBM = {"n_estimators": randint(100, 500), "learning_rate": loguniform(0.01, 0.3),
         "num_leaves": randint(8, 64), "min_child_samples": randint(5, 40),
         "subsample": uniform(0.6, 0.4), "subsample_freq": [1]}
_HGB = {"learning_rate": loguniform(0.01, 0.3), "max_iter": randint(100, 500),
        "max_leaf_nodes": randint(8, 64), "l2_regularization": loguniform(1e-3, 10)}
_CW = [None, "balanced"]

REGISTRY: list[ModelSpec] = [
    # ---- classification ---------------------------------------------------
    ModelSpec("DummyBaseline", "classification", "baseline",
              lambda c, s: DummyClassifier(strategy="prior"), baseline=True),
    ModelSpec("LogisticRegression", "classification", "linear",
              lambda c, s: LogisticRegression(max_iter=2000, class_weight=_bal(c), random_state=s),
              {"C": loguniform(1e-3, 1e2), "class_weight": _CW}),
    ModelSpec("KNN", "classification", "distance", lambda c, s: KNeighborsClassifier(),
              {"n_neighbors": randint(3, 31), "weights": ["uniform", "distance"], "p": [1, 2]}),
    ModelSpec("GaussianNB", "classification", "bayes", lambda c, s: GaussianNB(),
              {"var_smoothing": loguniform(1e-11, 1e-5)}),
    ModelSpec("SVC", "classification", "kernel",
              lambda c, s: SVC(class_weight=_bal(c), random_state=s),
              {"C": loguniform(1e-1, 1e2), "gamma": loguniform(1e-4, 1e0), "class_weight": _CW}),
    ModelSpec("DecisionTree", "classification", "tree",
              lambda c, s: DecisionTreeClassifier(class_weight=_bal(c), random_state=s),
              {"max_depth": [3, 4, 5, 7, 10, None], "min_samples_leaf": randint(1, 20), "class_weight": _CW}),
    ModelSpec("RandomForest", "classification", "bagging",
              lambda c, s: RandomForestClassifier(n_estimators=200, class_weight=_bal(c), n_jobs=1, random_state=s),
              {**_TREE, "class_weight": _CW}),
    ModelSpec("ExtraTrees", "classification", "bagging",
              lambda c, s: ExtraTreesClassifier(n_estimators=200, class_weight=_bal(c), n_jobs=1, random_state=s),
              {**_TREE, "class_weight": _CW}),
    ModelSpec("GradientBoosting", "classification", "boosting",
              lambda c, s: GradientBoostingClassifier(random_state=s), _BOOST),
    ModelSpec("HistGradientBoosting", "classification", "boosting",
              lambda c, s: HistGradientBoostingClassifier(class_weight=_bal(c), random_state=s), _HGB),
    ModelSpec("AdaBoost", "classification", "boosting",
              lambda c, s: AdaBoostClassifier(random_state=s),
              {"n_estimators": randint(50, 300), "learning_rate": loguniform(0.01, 1.5)}),
    ModelSpec("XGBoost", "classification", "boosting", _xgb_clf, _XGB, requires="xgboost"),
    ModelSpec("LightGBM", "classification", "boosting", _lgbm_clf, _LGBM, requires="lightgbm"),
    # ---- regression -------------------------------------------------------
    ModelSpec("DummyBaseline", "regression", "baseline",
              lambda c, s: DummyRegressor(strategy="mean"), baseline=True),
    ModelSpec("Ridge", "regression", "linear", lambda c, s: Ridge(random_state=s),
              {"alpha": loguniform(1e-3, 1e3)}),
    ModelSpec("ElasticNet", "regression", "linear",
              lambda c, s: ElasticNet(max_iter=5000, random_state=s),
              {"alpha": loguniform(1e-4, 1e1), "l1_ratio": uniform(0.05, 0.9)}),
    ModelSpec("KNN", "regression", "distance", lambda c, s: KNeighborsRegressor(),
              {"n_neighbors": randint(3, 31), "weights": ["uniform", "distance"], "p": [1, 2]}),
    ModelSpec("SVR", "regression", "kernel", lambda c, s: SVR(),
              {"C": loguniform(1e-1, 1e2), "gamma": loguniform(1e-4, 1e0), "epsilon": loguniform(1e-3, 1e0)}),
    ModelSpec("DecisionTree", "regression", "tree", lambda c, s: DecisionTreeRegressor(random_state=s),
              {"max_depth": [3, 4, 5, 7, 10, None], "min_samples_leaf": randint(1, 20)}),
    ModelSpec("RandomForest", "regression", "bagging",
              lambda c, s: RandomForestRegressor(n_estimators=200, n_jobs=1, random_state=s), _TREE),
    ModelSpec("ExtraTrees", "regression", "bagging",
              lambda c, s: ExtraTreesRegressor(n_estimators=200, n_jobs=1, random_state=s), _TREE),
    ModelSpec("GradientBoosting", "regression", "boosting",
              lambda c, s: GradientBoostingRegressor(random_state=s), _BOOST),
    ModelSpec("HistGradientBoosting", "regression", "boosting",
              lambda c, s: HistGradientBoostingRegressor(random_state=s), _HGB),
    ModelSpec("XGBoost", "regression", "boosting", _xgb_reg, _XGB, requires="xgboost"),
    ModelSpec("LightGBM", "regression", "boosting", _lgbm_reg, _LGBM, requires="lightgbm"),
]


def specs_for(task: str) -> dict[str, ModelSpec]:
    return {s.name: s for s in REGISTRY if s.task == task}
