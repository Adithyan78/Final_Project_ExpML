"""Efficient search: successive-halving screening and budgeted hyperparameter tuning."""
from __future__ import annotations

import logging
import math
import time
import warnings

import pandas as pd
from sklearn.model_selection import RandomizedSearchCV, train_test_split

from .config import TrainingConfig
from .evaluation import cv_evaluate, is_better, make_splitter, rank_key
from .registry import ModelSpec

log = logging.getLogger("automl_trainer")


class Budget:
    """Soft wall-clock budget, checked between models."""

    def __init__(self, seconds: float | None):
        self.seconds, self.start = seconds, time.perf_counter()

    def exceeded(self) -> bool:
        return self.seconds is not None and time.perf_counter() - self.start > self.seconds

    def elapsed(self) -> float:
        return time.perf_counter() - self.start


def subsample(task: str, X: pd.DataFrame, y: pd.Series, max_rows: int, seed: int):
    """Stratified subsample for the cheap rung. Returns (X, y, was_subsampled)."""
    if len(X) <= max_rows:
        return X, y, False
    strat = y if task == "classification" and y.value_counts().min() >= 2 else None
    X_s, _, y_s, _ = train_test_split(X, y, train_size=max_rows, stratify=strat, random_state=seed)
    return X_s.reset_index(drop=True), y_s.reset_index(drop=True), True


def screen(names, specs: dict[str, ModelSpec], ctx, cfg: TrainingConfig, X, y, cv, scorers,
           budget: Budget, label: str):
    """Cross-validate each model; failures and budget overruns are recorded, never raised."""
    scores, failures = {}, {}
    for n in names:
        scored_real = any(not specs[k].baseline for k in scores)
        if budget.exceeded() and not specs[n].baseline and scored_real:  # always evaluate at least one model
            failures[n] = "Skipped: time budget exhausted."
            continue
        try:
            scores[n] = cv_evaluate(specs[n].factory(ctx, cfg.random_state), X, y, cv, scorers, cfg.n_jobs)
        except Exception as exc:  # one bad model must not kill the run
            failures[n] = f"{type(exc).__name__}: {exc}"
            log.error("%s: %s failed: %s", label, n, failures[n])
    return scores, failures


def prune(scores: dict, baseline: dict | None, cfg: TrainingConfig, primary: str, secondary: str):
    """Keep the top fraction (at least keep_min); drop anything not better than the dummy baseline."""
    ranked = sorted(scores, key=lambda n: rank_key(scores[n], primary, secondary))
    keep_n = max(cfg.keep_min, math.ceil(len(ranked) * cfg.keep_fraction))
    kept, dropped = [], {}
    for i, n in enumerate(ranked):
        beats_base = baseline is None or is_better(scores[n][f"cv_{primary}_mean"],
                                                   baseline[f"cv_{primary}_mean"], primary)
        if i < keep_n and (beats_base or len(kept) < 1):
            kept.append(n)
        elif not beats_base:
            dropped[n] = "Not better than the dummy baseline."
        else:
            dropped[n] = f"Outside the top {keep_n} after screening."
    return kept, dropped


def tune(spec: ModelSpec, ctx, cfg: TrainingConfig, X, y, cv, scorer) -> dict:
    """Randomized search (seeded). Returns the best params and the search's own (optimistic) score."""
    search = RandomizedSearchCV(
        spec.factory(ctx, cfg.random_state), spec.space, n_iter=cfg.tune_iterations, scoring=scorer,
        cv=cv, random_state=cfg.random_state, n_jobs=cfg.n_jobs, refit=False, error_score="raise")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        search.fit(X, y)
    params = {k: (v.item() if hasattr(v, "item") else v) for k, v in search.best_params_.items()}
    return {"best_params": params, "search_best_score": round(abs(float(search.best_score_)), 4),
            "n_iter": cfg.tune_iterations}
